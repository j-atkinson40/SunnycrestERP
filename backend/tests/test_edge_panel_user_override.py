"""Edge-panel User-overrides layer — coverage of the fourth resolver
tier (B-2 rewrite).

This file owns the user-overrides assertions. The resolver's lower
tiers (template + tenant composition) get exhaustive unit coverage
in `test_edge_panel_inheritance_service.py::TestResolver`; tenant-
realm endpoint smoke lives in `test_edge_panel_r50.py`. What the
B-1.5 service tests touch on but DO NOT exhaustively cover is the
User layer — the substrate (Tier 2 + Tier 3 + User overrides)
specifies four R-5.0/R-5.1 delta keys on the user blob:

    hidden_page_ids
    additional_pages
    page_order              (or page_order_override — the resolver
                             accepts either spelling per backwards-
                             compatibility with R-5.1 frontend)
    page_overrides          (recursive — per-page placement-level
                             deltas: hidden_placement_ids,
                             additional_placements,
                             placement_geometry_overrides)

Tests verify each key applies correctly + orphan IDs at the User
layer are silently dropped + user-layer overrides stack on top of
the tenant Tier 3 layer.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm.attributes import flag_modified

from app.database import SessionLocal
from app.models.company import Company
from app.models.edge_panel_composition import EdgePanelComposition
from app.models.edge_panel_template import EdgePanelTemplate
from app.models.role import Role
from app.models.user import User
from app.services.edge_panel_inheritance import (
    create_template,
    resolve_edge_panel,
    upsert_composition,
)


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
            name=f"EPU {suffix}",
            slug=f"epu-{suffix}",
            is_active=True,
            vertical="funeral_home",
        )
        s.add(co)
        s.commit()
        yield co.id
        s.query(EdgePanelComposition).filter(
            EdgePanelComposition.tenant_id == co.id
        ).delete()
        s.delete(co)
        s.commit()
    finally:
        s.close()


@pytest.fixture
def tenant_user(tenant_company):
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
            email=f"epu-{suffix}@epu.test",
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


def _label(pid: str, text: str = "QUICK") -> dict:
    return {
        "placement_id": pid,
        "component_kind": "edge-panel-label",
        "component_name": "default",
        "starting_column": 0,
        "column_span": 12,
        "prop_overrides": {"text": text},
        "display_config": {},
    }


def _button(pid: str, name: str = "navigate-to-pulse") -> dict:
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


def _page(*, page_id: str, name: str, rows: list[dict]) -> dict:
    return {
        "page_id": page_id,
        "name": name,
        "rows": rows,
        "canvas_config": {"gap_size": 10},
    }


def _seed_template(db, vertical: str = "funeral_home") -> EdgePanelTemplate:
    return create_template(
        db,
        scope="vertical_default",
        vertical=vertical,
        panel_key="default",
        display_name=f"{vertical} default",
        description=None,
        pages=[
            _page(
                page_id="quick-actions",
                name="Quick Actions",
                rows=[
                    _row(row_id="qa-r0", placements=[_label("lbl-qa")]),
                    _row(row_id="qa-r1", placements=[_button("btn-pulse")]),
                ],
            ),
            _page(
                page_id="dispatch",
                name="Dispatch",
                rows=[
                    _row(
                        row_id="d-r0",
                        placements=[_label("lbl-d", text="DISPATCH")],
                    ),
                    _row(row_id="d-r1", placements=[_button("btn-cement")]),
                ],
            ),
        ],
        canvas_config={"default_page_index": 0},
    )


def _set_user_overrides(user_id: str, panel_key: str, blob: dict) -> None:
    s = SessionLocal()
    try:
        u = s.query(User).filter(User.id == user_id).one()
        prefs = dict(u.preferences or {})
        root = dict(prefs.get("edge_panel_overrides") or {})
        root[panel_key] = blob
        prefs["edge_panel_overrides"] = root
        u.preferences = prefs
        flag_modified(u, "preferences")
        s.commit()
    finally:
        s.close()


# ─── User-layer top-level deltas ──────────────────────────────────


class TestUserHiddenPageIds:
    def test_hides_page(self, db, tenant_user):
        _seed_template(db)
        _set_user_overrides(
            tenant_user, "default", {"hidden_page_ids": ["quick-actions"]}
        )
        r = resolve_edge_panel(
            db,
            panel_key="default",
            vertical="funeral_home",
            tenant_id=None,
            user_id=tenant_user,
        )
        page_ids = [p["page_id"] for p in r.pages]
        assert page_ids == ["dispatch"]
        assert r.sources["user_override"]["applied"] is True

    def test_orphan_page_id_silently_dropped(self, db, tenant_user):
        _seed_template(db)
        _set_user_overrides(
            tenant_user, "default", {"hidden_page_ids": ["does-not-exist"]}
        )
        r = resolve_edge_panel(
            db,
            panel_key="default",
            vertical="funeral_home",
            tenant_id=None,
            user_id=tenant_user,
        )
        assert len(r.pages) == 2


class TestUserAdditionalPages:
    def test_appends_additional_page(self, db, tenant_user):
        _seed_template(db)
        extra = _page(
            page_id="extra",
            name="Extra",
            rows=[_row(row_id="x-r0", placements=[_button("btn-extra")])],
        )
        _set_user_overrides(
            tenant_user, "default", {"additional_pages": [extra]}
        )
        r = resolve_edge_panel(
            db,
            panel_key="default",
            vertical="funeral_home",
            tenant_id=None,
            user_id=tenant_user,
        )
        page_ids = [p["page_id"] for p in r.pages]
        assert "extra" in page_ids


class TestUserPageOrder:
    def test_page_order_reorders(self, db, tenant_user):
        _seed_template(db)
        _set_user_overrides(
            tenant_user,
            "default",
            {"page_order": ["dispatch", "quick-actions"]},
        )
        r = resolve_edge_panel(
            db,
            panel_key="default",
            vertical="funeral_home",
            tenant_id=None,
            user_id=tenant_user,
        )
        page_ids = [p["page_id"] for p in r.pages]
        assert page_ids == ["dispatch", "quick-actions"]

    def test_page_order_override_alias(self, db, tenant_user):
        """R-5.1 frontend writes `page_order_override`; resolver
        accepts either spelling."""
        _seed_template(db)
        _set_user_overrides(
            tenant_user,
            "default",
            {"page_order_override": ["dispatch", "quick-actions"]},
        )
        r = resolve_edge_panel(
            db,
            panel_key="default",
            vertical="funeral_home",
            tenant_id=None,
            user_id=tenant_user,
        )
        page_ids = [p["page_id"] for p in r.pages]
        assert page_ids == ["dispatch", "quick-actions"]


# ─── User-layer per-page deltas (page_overrides recursive) ────────


class TestUserPageOverrides:
    def test_hidden_placement_ids_within_page(self, db, tenant_user):
        _seed_template(db)
        _set_user_overrides(
            tenant_user,
            "default",
            {
                "page_overrides": {
                    "quick-actions": {
                        "hidden_placement_ids": ["btn-pulse"],
                    }
                }
            },
        )
        r = resolve_edge_panel(
            db,
            panel_key="default",
            vertical="funeral_home",
            tenant_id=None,
            user_id=tenant_user,
        )
        qa = next(p for p in r.pages if p["page_id"] == "quick-actions")
        all_pids = [
            pl["placement_id"]
            for row in qa["rows"]
            for pl in (row.get("placements") or [])
        ]
        assert "btn-pulse" not in all_pids
        assert "lbl-qa" in all_pids

    def test_additional_placements_within_page(self, db, tenant_user):
        _seed_template(db)
        _set_user_overrides(
            tenant_user,
            "default",
            {
                "page_overrides": {
                    "quick-actions": {
                        "additional_placements": [
                            _button("btn-user-added", "navigate-to-pulse")
                        ],
                    }
                }
            },
        )
        r = resolve_edge_panel(
            db,
            panel_key="default",
            vertical="funeral_home",
            tenant_id=None,
            user_id=tenant_user,
        )
        qa = next(p for p in r.pages if p["page_id"] == "quick-actions")
        all_pids = [
            pl["placement_id"]
            for row in qa["rows"]
            for pl in (row.get("placements") or [])
        ]
        assert "btn-user-added" in all_pids

    def test_placement_geometry_override_within_page(
        self, db, tenant_user
    ):
        _seed_template(db)
        _set_user_overrides(
            tenant_user,
            "default",
            {
                "page_overrides": {
                    "quick-actions": {
                        "placement_geometry_overrides": {
                            "btn-pulse": {
                                "starting_column": 2,
                                "column_span": 8,
                            }
                        }
                    }
                }
            },
        )
        r = resolve_edge_panel(
            db,
            panel_key="default",
            vertical="funeral_home",
            tenant_id=None,
            user_id=tenant_user,
        )
        qa = next(p for p in r.pages if p["page_id"] == "quick-actions")
        btn = next(
            pl
            for row in qa["rows"]
            for pl in (row.get("placements") or [])
            if pl["placement_id"] == "btn-pulse"
        )
        assert btn["starting_column"] == 2
        assert btn["column_span"] == 8

    def test_orphan_placement_id_in_page_overrides_silently_dropped(
        self, db, tenant_user
    ):
        _seed_template(db)
        _set_user_overrides(
            tenant_user,
            "default",
            {
                "page_overrides": {
                    "quick-actions": {
                        "hidden_placement_ids": ["does-not-exist"],
                    }
                }
            },
        )
        r = resolve_edge_panel(
            db,
            panel_key="default",
            vertical="funeral_home",
            tenant_id=None,
            user_id=tenant_user,
        )
        qa = next(p for p in r.pages if p["page_id"] == "quick-actions")
        all_pids = [
            pl["placement_id"]
            for row in qa["rows"]
            for pl in (row.get("placements") or [])
        ]
        assert "lbl-qa" in all_pids and "btn-pulse" in all_pids


# ─── Stacking — user overrides apply ON TOP OF tenant Tier 3 ──────


class TestStackingOverTenant:
    def test_user_hides_page_tenant_added(
        self, db, tenant_company, tenant_user
    ):
        t = _seed_template(db)
        extra = _page(
            page_id="tenant-extra",
            name="Tenant Extra",
            rows=[
                _row(row_id="te-r0", placements=[_button("btn-tenant")]),
            ],
        )
        upsert_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"additional_pages": [extra]},
        )

        r = resolve_edge_panel(
            db,
            panel_key="default",
            vertical="funeral_home",
            tenant_id=tenant_company,
            user_id=tenant_user,
        )
        # Tier 3 added a page — tenant sees 3 pages.
        assert len(r.pages) == 3
        assert any(p["page_id"] == "tenant-extra" for p in r.pages)

        # User hides it.
        _set_user_overrides(
            tenant_user,
            "default",
            {"hidden_page_ids": ["tenant-extra"]},
        )
        r2 = resolve_edge_panel(
            db,
            panel_key="default",
            vertical="funeral_home",
            tenant_id=tenant_company,
            user_id=tenant_user,
        )
        assert all(p["page_id"] != "tenant-extra" for p in r2.pages)
        assert r2.sources["composition_applied"] is True
        assert r2.sources["user_override"]["applied"] is True

    def test_no_user_id_skips_user_layer(self, db, tenant_user):
        _seed_template(db)
        _set_user_overrides(
            tenant_user, "default", {"hidden_page_ids": ["quick-actions"]}
        )
        # Passing user_id=None bypasses the user layer entirely.
        r = resolve_edge_panel(
            db,
            panel_key="default",
            vertical="funeral_home",
            tenant_id=None,
            user_id=None,
        )
        assert len(r.pages) == 2
        assert r.sources["user_override"]["applied"] is False
