"""Edge Panel Inheritance — service-layer + resolver tests (B-1.5).

Covers sub-arc B-1.5 service surface:

    TestEdgePanelTemplatesService — Tier 2 CRUD + pages validation
    TestEdgePanelCompositionsService — Tier 3 lazy fork + deltas + resets
    TestResolver — Tier 2 → Tier 3 → User overrides composition walk

All tests share a clean-slate autouse fixture for the new substrate
tables. Companies and users created per test are torn down on cleanup.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy.orm.attributes import flag_modified

from app.database import SessionLocal
from app.models.company import Company
from app.models.edge_panel_composition import EdgePanelComposition
from app.models.edge_panel_template import EdgePanelTemplate
from app.models.role import Role
from app.models.user import User
from app.services.edge_panel_inheritance import (
    EdgePanelCompositionNotFound,
    EdgePanelTemplateError,
    EdgePanelTemplateNotFound,
    EdgePanelTemplateResolveError,
    EdgePanelTemplateScopeMismatch,
    InvalidEdgePanelShape,
    count_compositions_referencing,
    create_template,
    get_composition_by_id,
    get_composition_by_tenant_template,
    get_template_by_id,
    get_template_by_key,
    list_templates,
    reset_composition,
    reset_page,
    reset_placement,
    resolve_edge_panel,
    update_template,
    upsert_composition,
)


# ─── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture(autouse=True)
def _cleanup():
    def _wipe():
        s = SessionLocal()
        try:
            s.query(EdgePanelComposition).delete()
            s.query(EdgePanelTemplate).delete()
            s.commit()
        finally:
            s.close()

    _wipe()
    yield
    _wipe()


@pytest.fixture
def tenant_company():
    s = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"EP Test {suffix}",
            slug=f"ep-{suffix}",
            is_active=True,
            vertical="funeral_home",
        )
        s.add(co)
        s.commit()
        yield co.id
        # Compositions cascade via FK; clean explicitly anyway.
        s.query(EdgePanelComposition).filter(
            EdgePanelComposition.tenant_id == co.id
        ).delete()
        s.delete(co)
        s.commit()
    finally:
        s.close()


@pytest.fixture
def tenant_user(tenant_company):
    """Create a user inside tenant_company for resolver user-id tests."""
    s = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        role = Role(
            id=str(uuid.uuid4()),
            company_id=tenant_company,
            name="Admin",
            slug="admin",
            is_system=True,
        )
        s.add(role)
        s.flush()
        u = User(
            id=str(uuid.uuid4()),
            company_id=tenant_company,
            email=f"epu-{suffix}@ep.test",
            hashed_password="x",
            first_name="E",
            last_name="P",
            role_id=role.id,
            is_active=True,
            preferences={},
        )
        s.add(u)
        s.commit()
        yield u.id
        s.query(User).filter(User.id == u.id).delete()
        s.query(Role).filter(Role.id == role.id).delete()
        s.commit()
    finally:
        s.close()


# ─── Helpers ───────────────────────────────────────────────────────


def _label_placement(pid: str, *, text: str = "QUICK") -> dict:
    return {
        "placement_id": pid,
        "component_kind": "edge-panel-label",
        "component_name": "default",
        "starting_column": 0,
        "column_span": 12,
        "prop_overrides": {"text": text},
        "display_config": {},
    }


def _button_placement(pid: str, name: str = "navigate-to-pulse") -> dict:
    return {
        "placement_id": pid,
        "component_kind": "button",
        "component_name": name,
        "starting_column": 0,
        "column_span": 12,
        "prop_overrides": {},
        "display_config": {},
    }


def _row(*, row_id: str, placements: list[dict]) -> dict:
    return {
        "row_id": row_id,
        "column_count": 12,
        "row_height": "auto",
        "column_widths": None,
        "nested_rows": None,
        "placements": placements,
    }


def _page(
    *,
    page_id: str,
    name: str,
    placements_by_row: list[list[dict]],
    canvas_config: dict | None = None,
) -> dict:
    return {
        "page_id": page_id,
        "name": name,
        "rows": [
            _row(row_id=f"{page_id}-r{idx}", placements=plist)
            for idx, plist in enumerate(placements_by_row)
        ],
        "canvas_config": canvas_config or {"gap_size": 10},
    }


def _platform_template(db, *, panel_key="default") -> EdgePanelTemplate:
    pages = [
        _page(
            page_id="quick-actions",
            name="Quick Actions",
            placements_by_row=[
                [_label_placement("lbl-qa")],
                [_button_placement("btn-pulse")],
            ],
        ),
    ]
    return create_template(
        db,
        scope="platform_default",
        vertical=None,
        panel_key=panel_key,
        display_name="Platform default",
        description=None,
        pages=pages,
        canvas_config={},
    )


def _vertical_template(db, *, vertical="funeral_home") -> EdgePanelTemplate:
    pages = [
        _page(
            page_id="quick-actions",
            name="Quick Actions",
            placements_by_row=[
                [_label_placement("lbl-qa")],
                [_button_placement("btn-scheduling", "open-funeral-scheduling-focus")],
            ],
        ),
        _page(
            page_id="dispatch",
            name="Dispatch",
            placements_by_row=[
                [_label_placement("lbl-d", text="DISPATCH")],
                [_button_placement("btn-cement", "trigger-cement-order-workflow")],
            ],
        ),
    ]
    return create_template(
        db,
        scope="vertical_default",
        vertical=vertical,
        panel_key="default",
        display_name=f"{vertical} default",
        description=None,
        pages=pages,
        canvas_config={"default_page_index": 0},
    )


# ═══ Tier 2 — Templates ═══════════════════════════════════════════


class TestEdgePanelTemplatesService:
    def test_create_and_read(self, db):
        row = _platform_template(db)
        assert row.id
        assert row.scope == "platform_default"
        assert row.vertical is None
        assert row.panel_key == "default"
        assert row.version == 1
        assert row.is_active is True

        fetched = get_template_by_id(db, row.id)
        assert fetched is not None and fetched.id == row.id

        by_key = get_template_by_key(
            db, "default", scope="platform_default", vertical=None
        )
        assert by_key is not None and by_key.id == row.id

    def test_version_bumps_and_deactivates_prior(self, db):
        v1 = _platform_template(db)
        # Re-create at same tuple → version 2; v1 deactivated.
        v2 = create_template(
            db,
            scope="platform_default",
            vertical=None,
            panel_key="default",
            display_name="Platform default v2",
            description=None,
            pages=v1.pages,
            canvas_config={},
        )
        assert v2.version == 2
        assert v2.is_active is True

        db.refresh(v1)
        assert v1.is_active is False

    def test_update_template_versions(self, db):
        v1 = _platform_template(db)
        v2 = update_template(
            db, v1.id, display_name="renamed v2", updated_by=None
        )
        assert v2.version == 2
        assert v2.display_name == "renamed v2"
        assert v2.panel_key == v1.panel_key  # immutable identity
        db.refresh(v1)
        assert v1.is_active is False

    def test_panel_key_is_immutable_through_update(self, db):
        # update_template signature has no panel_key kwarg; identity
        # fields stay locked to the prior row.
        v1 = _platform_template(db)
        v2 = update_template(db, v1.id, display_name="x", updated_by=None)
        assert v2.panel_key == "default"

    def test_list_with_filters(self, db):
        _platform_template(db)
        _vertical_template(db, vertical="funeral_home")
        _vertical_template(db, vertical="manufacturing")
        all_rows = list_templates(db)
        assert len(all_rows) == 3
        platform_only = list_templates(db, scope="platform_default")
        assert len(platform_only) == 1
        fh_only = list_templates(
            db, scope="vertical_default", vertical="funeral_home"
        )
        assert len(fh_only) == 1

    def test_count_compositions_referencing(self, db, tenant_company):
        t = _platform_template(db)
        assert count_compositions_referencing(db, t.id) == 0
        upsert_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"hidden_page_ids": []},
        )
        assert count_compositions_referencing(db, t.id) == 1

    def test_pages_validation_rejects_bad_shapes(self, db):
        # Pages not a list.
        with pytest.raises(InvalidEdgePanelShape):
            create_template(
                db,
                scope="platform_default",
                vertical=None,
                panel_key="bad",
                display_name="bad",
                pages="not-a-list",  # type: ignore
            )
        # Page missing page_id.
        with pytest.raises(InvalidEdgePanelShape):
            create_template(
                db,
                scope="platform_default",
                vertical=None,
                panel_key="bad",
                display_name="bad",
                pages=[{"name": "X", "rows": []}],
            )
        # Placement out-of-bounds geometry.
        with pytest.raises(InvalidEdgePanelShape):
            create_template(
                db,
                scope="platform_default",
                vertical=None,
                panel_key="bad",
                display_name="bad",
                pages=[
                    {
                        "page_id": "p1",
                        "name": "P1",
                        "rows": [
                            {
                                "row_id": "r0",
                                "column_count": 12,
                                "placements": [
                                    {
                                        "placement_id": "x",
                                        "component_kind": "button",
                                        "component_name": "go",
                                        "starting_column": 5,
                                        "column_span": 10,  # 5+10 > 12
                                    }
                                ],
                            }
                        ],
                    }
                ],
            )

    def test_duplicate_page_id_rejected(self, db):
        with pytest.raises(InvalidEdgePanelShape):
            create_template(
                db,
                scope="platform_default",
                vertical=None,
                panel_key="dup",
                display_name="dup",
                pages=[
                    _page(
                        page_id="p1",
                        name="A",
                        placements_by_row=[[_label_placement("lbl-1")]],
                    ),
                    _page(
                        page_id="p1",
                        name="B",
                        placements_by_row=[[_label_placement("lbl-2")]],
                    ),
                ],
            )

    def test_scope_mismatch_rejected(self, db):
        with pytest.raises(EdgePanelTemplateScopeMismatch):
            create_template(
                db,
                scope="platform_default",
                vertical="funeral_home",  # invalid for platform_default
                panel_key="bad",
                display_name="bad",
                pages=[],
            )
        with pytest.raises(EdgePanelTemplateScopeMismatch):
            create_template(
                db,
                scope="vertical_default",
                vertical=None,  # missing
                panel_key="bad",
                display_name="bad",
                pages=[],
            )


# ═══ Tier 3 — Compositions ══════════════════════════════════════


class TestEdgePanelCompositionsService:
    def test_lazy_fork_creates_on_first_upsert(self, db, tenant_company):
        t = _platform_template(db)
        assert (
            get_composition_by_tenant_template(db, tenant_company, t.id) is None
        )
        comp = upsert_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"hidden_page_ids": []},
        )
        assert comp.version == 1
        assert comp.tenant_id == tenant_company
        assert comp.inherits_from_template_id == t.id
        # inherits_from_template_version captured from live template.
        assert comp.inherits_from_template_version == t.version

    def test_upsert_versions_existing(self, db, tenant_company):
        t = _platform_template(db)
        c1 = upsert_composition(
            db, tenant_id=tenant_company, template_id=t.id, deltas=None
        )
        c2 = upsert_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"hidden_page_ids": ["dispatch"]},
        )
        assert c2.version == 2
        db.refresh(c1)
        assert c1.is_active is False

    def test_reset_composition(self, db, tenant_company):
        t = _vertical_template(db, vertical="funeral_home")
        c1 = upsert_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"hidden_page_ids": ["dispatch"]},
        )
        c2 = reset_composition(db, tenant_company, t.id)
        assert c2.version == c1.version + 1
        assert c2.deltas["hidden_page_ids"] == []

    def test_reset_composition_raises_when_missing(self, db, tenant_company):
        t = _platform_template(db)
        with pytest.raises(EdgePanelCompositionNotFound):
            reset_composition(db, tenant_company, t.id)

    def test_reset_page_drops_one_page_override(self, db, tenant_company):
        t = _vertical_template(db, vertical="funeral_home")
        c1 = upsert_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={
                "page_overrides": {
                    "quick-actions": {
                        "hidden_placement_ids": ["btn-scheduling"]
                    },
                    "dispatch": {"hidden_placement_ids": ["btn-cement"]},
                }
            },
        )
        c2 = reset_page(db, c1.id, "dispatch")
        assert "dispatch" not in c2.deltas["page_overrides"]
        assert "quick-actions" in c2.deltas["page_overrides"]
        assert c2.version == c1.version + 1

    def test_reset_placement_within_page(self, db, tenant_company):
        t = _vertical_template(db, vertical="funeral_home")
        c1 = upsert_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={
                "page_overrides": {
                    "quick-actions": {
                        "hidden_placement_ids": ["btn-scheduling", "btn-other"],
                        "placement_geometry_overrides": {
                            "btn-scheduling": {
                                "starting_column": 0,
                                "column_span": 6,
                            },
                            "btn-other": {
                                "starting_column": 6,
                                "column_span": 6,
                            },
                        },
                        "placement_order": ["btn-other", "btn-scheduling"],
                    }
                }
            },
        )
        c2 = reset_placement(db, c1.id, "quick-actions", "btn-scheduling")
        po = c2.deltas["page_overrides"]["quick-actions"]
        assert "btn-scheduling" not in po["hidden_placement_ids"]
        assert "btn-other" in po["hidden_placement_ids"]
        assert "btn-scheduling" not in po["placement_geometry_overrides"]
        assert "btn-scheduling" not in po["placement_order"]

    def test_geometry_override_out_of_bounds_rejected(self, db, tenant_company):
        t = _platform_template(db)
        with pytest.raises(InvalidEdgePanelShape):
            upsert_composition(
                db,
                tenant_id=tenant_company,
                template_id=t.id,
                deltas={
                    "page_overrides": {
                        "quick-actions": {
                            "placement_geometry_overrides": {
                                "btn-pulse": {
                                    "starting_column": 8,
                                    "column_span": 10,  # 8+10 > 12
                                }
                            }
                        }
                    }
                },
            )

    def test_unknown_delta_key_rejected(self, db, tenant_company):
        t = _platform_template(db)
        with pytest.raises(InvalidEdgePanelShape):
            upsert_composition(
                db,
                tenant_id=tenant_company,
                template_id=t.id,
                deltas={"nope": []},
            )

    def test_orphan_page_id_at_write_rejected(self, db, tenant_company):
        t = _platform_template(db)
        # `quick-actions` exists; `nonsense` doesn't.
        with pytest.raises(InvalidEdgePanelShape):
            upsert_composition(
                db,
                tenant_id=tenant_company,
                template_id=t.id,
                deltas={
                    "page_overrides": {
                        "nonsense": {"hidden_placement_ids": []}
                    }
                },
            )

    def test_canvas_config_overrides_default_empty(self, db, tenant_company):
        t = _platform_template(db)
        c = upsert_composition(
            db, tenant_id=tenant_company, template_id=t.id, deltas=None
        )
        assert c.canvas_config_overrides == {}


# ═══ Resolver ════════════════════════════════════════════════════


class TestResolver:
    def test_platform_default_no_tenant_no_user(self, db):
        t = _platform_template(db)
        result = resolve_edge_panel(
            db, panel_key="default", vertical=None, tenant_id=None
        )
        assert result.template_id == t.id
        assert result.template_scope == "platform_default"
        assert result.template_vertical is None
        assert len(result.pages) == 1
        assert result.pages[0]["page_id"] == "quick-actions"
        assert result.sources["composition"] is None
        assert result.sources["user_override"]["applied"] is False

    def test_vertical_wins_over_platform(self, db):
        _platform_template(db)
        v_fh = _vertical_template(db, vertical="funeral_home")
        result = resolve_edge_panel(
            db, panel_key="default", vertical="funeral_home"
        )
        assert result.template_id == v_fh.id
        assert result.template_scope == "vertical_default"
        assert result.template_vertical == "funeral_home"

    def test_tenant_without_fork_yields_bare_tier2(self, db, tenant_company):
        t = _vertical_template(db, vertical="funeral_home")
        result = resolve_edge_panel(
            db,
            panel_key="default",
            vertical="funeral_home",
            tenant_id=tenant_company,
        )
        assert result.template_id == t.id
        assert result.sources["composition"] is None
        assert len(result.pages) == 2

    def test_tenant_hidden_page_ids_drops_pages(self, db, tenant_company):
        t = _vertical_template(db, vertical="funeral_home")
        upsert_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"hidden_page_ids": ["dispatch"]},
        )
        result = resolve_edge_panel(
            db,
            panel_key="default",
            vertical="funeral_home",
            tenant_id=tenant_company,
        )
        assert len(result.pages) == 1
        assert result.pages[0]["page_id"] == "quick-actions"
        assert result.sources["composition"] is not None

    def test_tenant_additional_pages_appended(self, db, tenant_company):
        t = _platform_template(db)
        extra_page = _page(
            page_id="tenant-extra",
            name="Tenant Extra",
            placements_by_row=[[_button_placement("btn-tenant-extra")]],
        )
        upsert_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"additional_pages": [extra_page]},
        )
        result = resolve_edge_panel(
            db, panel_key="default", tenant_id=tenant_company
        )
        assert [p["page_id"] for p in result.pages] == [
            "quick-actions",
            "tenant-extra",
        ]

    def test_tenant_page_order(self, db, tenant_company):
        t = _vertical_template(db, vertical="funeral_home")
        upsert_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"page_order": ["dispatch", "quick-actions"]},
        )
        result = resolve_edge_panel(
            db,
            panel_key="default",
            vertical="funeral_home",
            tenant_id=tenant_company,
        )
        assert [p["page_id"] for p in result.pages] == [
            "dispatch",
            "quick-actions",
        ]

    def test_tenant_page_override_hidden_placement(self, db, tenant_company):
        t = _vertical_template(db, vertical="funeral_home")
        upsert_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={
                "page_overrides": {
                    "quick-actions": {
                        "hidden_placement_ids": ["btn-scheduling"]
                    }
                }
            },
        )
        result = resolve_edge_panel(
            db,
            panel_key="default",
            vertical="funeral_home",
            tenant_id=tenant_company,
        )
        qa = next(p for p in result.pages if p["page_id"] == "quick-actions")
        placement_ids = [
            pl["placement_id"] for r in qa["rows"] for pl in r["placements"]
        ]
        assert "btn-scheduling" not in placement_ids
        assert "lbl-qa" in placement_ids

    def test_tenant_additional_placements(self, db, tenant_company):
        t = _vertical_template(db, vertical="funeral_home")
        upsert_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={
                "page_overrides": {
                    "quick-actions": {
                        "additional_placements": [
                            {
                                "placement_id": "btn-tenant",
                                "component_kind": "button",
                                "component_name": "open-tenant-view",
                                "starting_column": 0,
                                "column_span": 12,
                                "row_index": 1,
                            }
                        ]
                    }
                }
            },
        )
        result = resolve_edge_panel(
            db,
            panel_key="default",
            vertical="funeral_home",
            tenant_id=tenant_company,
        )
        qa = next(p for p in result.pages if p["page_id"] == "quick-actions")
        placement_ids = [
            pl["placement_id"] for r in qa["rows"] for pl in r["placements"]
        ]
        assert "btn-tenant" in placement_ids

    def test_tenant_placement_geometry_overrides(self, db, tenant_company):
        t = _vertical_template(db, vertical="funeral_home")
        upsert_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={
                "page_overrides": {
                    "quick-actions": {
                        "placement_geometry_overrides": {
                            "btn-scheduling": {
                                "starting_column": 0,
                                "column_span": 6,
                            }
                        }
                    }
                }
            },
        )
        result = resolve_edge_panel(
            db,
            panel_key="default",
            vertical="funeral_home",
            tenant_id=tenant_company,
        )
        qa = next(p for p in result.pages if p["page_id"] == "quick-actions")
        sched = next(
            pl
            for r in qa["rows"]
            for pl in r["placements"]
            if pl["placement_id"] == "btn-scheduling"
        )
        assert sched["starting_column"] == 0
        assert sched["column_span"] == 6

    def test_user_overrides_combine_with_tenant(
        self, db, tenant_company, tenant_user
    ):
        t = _vertical_template(db, vertical="funeral_home")
        upsert_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={
                "page_overrides": {
                    "quick-actions": {
                        "hidden_placement_ids": ["btn-scheduling"]
                    }
                }
            },
        )
        # Plant user override that hides the label too.
        s = SessionLocal()
        try:
            u = s.query(User).filter(User.id == tenant_user).first()
            u.preferences = {
                "edge_panel_overrides": {
                    "default": {
                        "page_overrides": {
                            "quick-actions": {
                                "hidden_placement_ids": ["lbl-qa"]
                            }
                        }
                    }
                }
            }
            flag_modified(u, "preferences")
            s.commit()
        finally:
            s.close()
        result = resolve_edge_panel(
            db,
            panel_key="default",
            vertical="funeral_home",
            tenant_id=tenant_company,
            user_id=tenant_user,
        )
        assert result.sources["user_override"]["applied"] is True
        qa = next(p for p in result.pages if p["page_id"] == "quick-actions")
        placement_ids = [
            pl["placement_id"] for r in qa["rows"] for pl in r["placements"]
        ]
        assert "btn-scheduling" not in placement_ids
        assert "lbl-qa" not in placement_ids

    def test_user_hides_page_tenant_added(self, db, tenant_company, tenant_user):
        t = _platform_template(db)
        extra_page = _page(
            page_id="tenant-extra",
            name="Tenant Extra",
            placements_by_row=[[_button_placement("btn-extra")]],
        )
        upsert_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"additional_pages": [extra_page]},
        )
        s = SessionLocal()
        try:
            u = s.query(User).filter(User.id == tenant_user).first()
            u.preferences = {
                "edge_panel_overrides": {
                    "default": {"hidden_page_ids": ["tenant-extra"]}
                }
            }
            flag_modified(u, "preferences")
            s.commit()
        finally:
            s.close()
        result = resolve_edge_panel(
            db,
            panel_key="default",
            tenant_id=tenant_company,
            user_id=tenant_user,
        )
        page_ids = [p["page_id"] for p in result.pages]
        assert "tenant-extra" not in page_ids
        assert "quick-actions" in page_ids

    def test_orphan_page_id_silent_drop_in_user_overrides(
        self, db, tenant_company, tenant_user
    ):
        _platform_template(db)
        s = SessionLocal()
        try:
            u = s.query(User).filter(User.id == tenant_user).first()
            u.preferences = {
                "edge_panel_overrides": {
                    "default": {
                        "page_overrides": {
                            "no-such-page": {"hidden_placement_ids": []}
                        }
                    }
                }
            }
            flag_modified(u, "preferences")
            s.commit()
        finally:
            s.close()
        # Should NOT raise — orphan dropped silently at debug.
        result = resolve_edge_panel(
            db,
            panel_key="default",
            tenant_id=tenant_company,
            user_id=tenant_user,
        )
        assert [p["page_id"] for p in result.pages] == ["quick-actions"]

    def test_orphan_placement_id_silent_drop(self, db, tenant_company):
        t = _platform_template(db)
        # Construct deltas where geometry_override key doesn't match
        # any placement. Write-time validation allows this (it only
        # rejects orphan page_ids); resolver drops at read.
        upsert_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={
                "page_overrides": {
                    "quick-actions": {
                        "placement_geometry_overrides": {
                            "no-such-placement": {
                                "starting_column": 0,
                                "column_span": 6,
                            }
                        }
                    }
                }
            },
        )
        result = resolve_edge_panel(
            db, panel_key="default", tenant_id=tenant_company
        )
        assert len(result.pages) == 1

    def test_edge_panel_template_not_found_raises(self, db):
        with pytest.raises(EdgePanelTemplateResolveError):
            resolve_edge_panel(db, panel_key="nonexistent")

    def test_canvas_config_compose_template_plus_tenant(self, db, tenant_company):
        t = _vertical_template(db, vertical="funeral_home")
        # Template carries default_page_index=0.
        upsert_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            canvas_config_overrides={"gap_size": 16},
        )
        result = resolve_edge_panel(
            db,
            panel_key="default",
            vertical="funeral_home",
            tenant_id=tenant_company,
        )
        assert result.canvas_config["default_page_index"] == 0
        assert result.canvas_config["gap_size"] == 16
