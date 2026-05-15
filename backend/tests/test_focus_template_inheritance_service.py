"""Focus Template Inheritance — service-layer + resolver tests.

Covers sub-arc B-1 service surface:

    TestFocusCoresService       — Tier 1 CRUD + versioning + counts
    TestFocusTemplatesService   — Tier 2 CRUD + rows validation
    TestFocusCompositionsService — Tier 3 lazy fork + deltas + reset
    TestResolver                — three-tier inheritance walk + composition

All tests share a clean-slate autouse fixture so the new tables stay
isolated. Companies created per test are torn down on cleanup.
"""

from __future__ import annotations

import uuid

import pytest

from app.database import SessionLocal
from app.models.company import Company
from app.models.focus_composition import FocusComposition
from app.models.focus_core import FocusCore
from app.models.focus_template import FocusTemplate
from app.services.focus_template_inheritance import (
    CompositionNotFound,
    CoreNotFound,
    CoreSlugImmutable,
    FocusCoreError,
    FocusTemplateError,
    FocusTemplateNotFound,
    InvalidCompositionShape,
    InvalidCoreShape,
    InvalidTemplateShape,
    TemplateNotFound,
    TemplateScopeMismatch,
    count_compositions_referencing,
    count_templates_referencing,
    create_core,
    create_or_update_composition,
    create_template,
    get_composition_by_tenant_template,
    get_core_by_id,
    get_core_by_slug,
    get_template_by_id,
    get_template_by_slug,
    list_cores,
    list_templates,
    reset_composition_to_default,
    reset_placement_to_default,
    resolve_focus,
    update_core,
    update_template,
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
            s.query(FocusComposition).delete()
            s.query(FocusTemplate).delete()
            s.query(FocusCore).delete()
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
            name=f"FTI Test {suffix}",
            slug=f"fti-{suffix}",
            is_active=True,
            vertical="funeral_home",
        )
        s.add(co)
        s.commit()
        yield co.id
        # Cascade: focus_compositions delete via FK on cleanup fixture.
        s.delete(co)
        s.commit()
    finally:
        s.close()


def _make_core(db, *, slug: str = "scheduling-kanban", **kwargs) -> FocusCore:
    defaults = dict(
        core_slug=slug,
        display_name="Scheduling Kanban",
        description="Kanban core",
        registered_component_kind="focus-core",
        registered_component_name="SchedulingKanbanCore",
        default_starting_column=0,
        default_column_span=12,
        default_row_index=0,
        min_column_span=8,
        max_column_span=12,
        canvas_config={},
    )
    defaults.update(kwargs)
    return create_core(db, **defaults)


def _make_template(
    db,
    *,
    core_id: str,
    slug: str = "scheduling-fh",
    scope: str = "vertical_default",
    vertical: str | None = "funeral_home",
    rows: list | None = None,
    canvas_config: dict | None = None,
) -> FocusTemplate:
    return create_template(
        db,
        scope=scope,
        vertical=vertical,
        template_slug=slug,
        display_name="Test Template",
        description="t",
        inherits_from_core_id=core_id,
        rows=rows or [],
        canvas_config=canvas_config or {},
    )


# ═══ Tier 1 — Cores ═════════════════════════════════════════════


class TestFocusCoresService:
    def test_create_and_get(self, db):
        c = _make_core(db, slug="kb-1")
        assert c.id
        assert c.version == 1
        assert c.is_active is True
        got = get_core_by_id(db, c.id)
        assert got.id == c.id
        got_slug = get_core_by_slug(db, "kb-1")
        assert got_slug.id == c.id

    def test_create_rejects_duplicate_active(self, db):
        _make_core(db, slug="kb-dup")
        with pytest.raises(FocusCoreError):
            _make_core(db, slug="kb-dup")

    def test_update_versions(self, db):
        c1 = _make_core(db, slug="kb-up")
        c2 = update_core(
            db, c1.id, display_name="Renamed", updated_by=None
        )
        assert c2.id != c1.id
        assert c2.version == c1.version + 1
        assert c2.display_name == "Renamed"
        # Prior row deactivated.
        db.refresh(c1)
        assert c1.is_active is False
        # Active row by slug = new one.
        active = get_core_by_slug(db, "kb-up")
        assert active.id == c2.id

    def test_update_rejects_slug_change(self, db):
        c1 = _make_core(db, slug="kb-slug")
        with pytest.raises(CoreSlugImmutable):
            update_core(db, c1.id, core_slug="kb-different", updated_by=None)

    def test_list_active_only(self, db):
        c1 = _make_core(db, slug="kb-a")
        _make_core(db, slug="kb-b")
        update_core(db, c1.id, display_name="v2", updated_by=None)
        active = list_cores(db)
        slugs = {c.core_slug for c in active}
        assert slugs == {"kb-a", "kb-b"}
        # include_inactive returns 3 rows (a-v1, a-v2, b)
        all_rows = list_cores(db, include_inactive=True)
        assert len(all_rows) == 3

    def test_count_templates_referencing(self, db):
        c = _make_core(db, slug="kb-c")
        assert count_templates_referencing(db, c.id) == 0
        _make_template(db, core_id=c.id, slug="t1")
        _make_template(
            db, core_id=c.id, slug="t2", vertical="manufacturing"
        )
        assert count_templates_referencing(db, c.id) == 2

    def test_invalid_geometry_rejected(self, db):
        with pytest.raises(InvalidCoreShape):
            _make_core(
                db,
                slug="kb-geom",
                default_starting_column=10,
                default_column_span=5,  # 10 + 5 > 12
            )
        with pytest.raises(InvalidCoreShape):
            _make_core(
                db, slug="kb-minmax", min_column_span=10, max_column_span=4
            )

    def test_update_cannot_target_inactive(self, db):
        c1 = _make_core(db, slug="kb-in")
        update_core(db, c1.id, display_name="v2", updated_by=None)
        with pytest.raises(FocusCoreError):
            update_core(db, c1.id, display_name="never", updated_by=None)


# ═══ Tier 2 — Templates ═════════════════════════════════════════


class TestFocusTemplatesService:
    def test_create_platform_default(self, db):
        c = _make_core(db, slug="kb-pd")
        t = create_template(
            db,
            scope="platform_default",
            vertical=None,
            template_slug="t-pd",
            display_name="Platform Default",
            inherits_from_core_id=c.id,
            rows=[],
            canvas_config={},
        )
        assert t.id
        assert t.scope == "platform_default"
        assert t.vertical is None
        assert t.inherits_from_core_version == c.version

    def test_create_vertical_default(self, db):
        c = _make_core(db, slug="kb-vd")
        t = _make_template(db, core_id=c.id, slug="t-vd")
        assert t.scope == "vertical_default"
        assert t.vertical == "funeral_home"

    def test_create_rejects_scope_mismatch(self, db):
        c = _make_core(db, slug="kb-sm")
        with pytest.raises(TemplateScopeMismatch):
            create_template(
                db,
                scope="platform_default",
                vertical="funeral_home",  # wrong
                template_slug="bad-pd",
                display_name="x",
                inherits_from_core_id=c.id,
            )
        with pytest.raises(TemplateScopeMismatch):
            create_template(
                db,
                scope="vertical_default",
                vertical=None,  # wrong
                template_slug="bad-vd",
                display_name="x",
                inherits_from_core_id=c.id,
            )

    def test_rows_validation_valid(self, db):
        c = _make_core(db, slug="kb-rv")
        rows = [
            {
                "row_id": "r1",
                "column_count": 12,
                "column_widths": None,
                "placements": [
                    {
                        "placement_id": "today",
                        "component_kind": "widget",
                        "component_name": "today",
                        "starting_column": 0,
                        "column_span": 12,
                    }
                ],
            }
        ]
        t = _make_template(db, core_id=c.id, rows=rows)
        assert t.rows == rows

    def test_rows_validation_invalid_shapes(self, db):
        c = _make_core(db, slug="kb-rinv")
        bad_shapes = [
            # rows not list
            {"row_id": "r1", "column_count": 12, "placements": []},
            # column_count out of range
            [{"row_id": "r1", "column_count": 13, "placements": []}],
            # placement starting_column negative
            [
                {
                    "row_id": "r1",
                    "column_count": 12,
                    "placements": [
                        {
                            "placement_id": "x",
                            "component_kind": "widget",
                            "component_name": "x",
                            "starting_column": -1,
                            "column_span": 1,
                        }
                    ],
                }
            ],
            # placement exceeds row column_count
            [
                {
                    "row_id": "r1",
                    "column_count": 6,
                    "placements": [
                        {
                            "placement_id": "x",
                            "component_kind": "widget",
                            "component_name": "x",
                            "starting_column": 4,
                            "column_span": 4,  # 4 + 4 > 6
                        }
                    ],
                }
            ],
        ]
        for bad in bad_shapes:
            with pytest.raises(InvalidTemplateShape):
                _make_template(db, core_id=c.id, slug="bad-row", rows=bad)

    def test_duplicate_placement_id_rejected(self, db):
        c = _make_core(db, slug="kb-dup-pid")
        rows = [
            {
                "row_id": "r1",
                "column_count": 12,
                "placements": [
                    {
                        "placement_id": "same",
                        "component_kind": "widget",
                        "component_name": "a",
                        "starting_column": 0,
                        "column_span": 6,
                    },
                    {
                        "placement_id": "same",  # duplicate
                        "component_kind": "widget",
                        "component_name": "b",
                        "starting_column": 6,
                        "column_span": 6,
                    },
                ],
            }
        ]
        with pytest.raises(InvalidTemplateShape):
            _make_template(db, core_id=c.id, rows=rows)

    def test_is_core_placement_must_match_core(self, db):
        c = _make_core(
            db, slug="kb-core-match", registered_component_name="MatchMe"
        )
        rows = [
            {
                "row_id": "r1",
                "column_count": 12,
                "placements": [
                    {
                        "placement_id": "core",
                        "is_core": True,
                        "component_kind": "focus-core",
                        "component_name": "WrongName",  # mismatch
                        "starting_column": 0,
                        "column_span": 12,
                    }
                ],
            }
        ]
        with pytest.raises(InvalidTemplateShape):
            _make_template(db, core_id=c.id, rows=rows)

        rows[0]["placements"][0]["component_name"] = "MatchMe"
        t = _make_template(db, core_id=c.id, rows=rows)
        assert t.rows[0]["placements"][0]["is_core"] is True

    def test_at_most_one_is_core_placement(self, db):
        c = _make_core(db, slug="kb-2core")
        rows = [
            {
                "row_id": "r1",
                "column_count": 12,
                "placements": [
                    {
                        "placement_id": "c1",
                        "is_core": True,
                        "component_kind": c.registered_component_kind,
                        "component_name": c.registered_component_name,
                        "starting_column": 0,
                        "column_span": 6,
                    },
                    {
                        "placement_id": "c2",
                        "is_core": True,
                        "component_kind": c.registered_component_kind,
                        "component_name": c.registered_component_name,
                        "starting_column": 6,
                        "column_span": 6,
                    },
                ],
            }
        ]
        with pytest.raises(InvalidTemplateShape):
            _make_template(db, core_id=c.id, rows=rows)

    def test_update_versions(self, db):
        c = _make_core(db, slug="kb-tu")
        t1 = _make_template(db, core_id=c.id, slug="tu")
        t2 = update_template(
            db, t1.id, display_name="New Name", updated_by=None
        )
        assert t2.id != t1.id
        assert t2.version == t1.version + 1
        db.refresh(t1)
        assert t1.is_active is False
        active = get_template_by_slug(
            db, "tu", scope="vertical_default", vertical="funeral_home"
        )
        assert active.id == t2.id

    def test_scope_vertical_slug_uniqueness_via_service(self, db):
        c = _make_core(db, slug="kb-uq")
        t1 = _make_template(db, core_id=c.id, slug="dup-slug")
        # Creating "again" at the same tuple should DEACTIVATE t1 and
        # version a new active row (per workflow precedent + investigation).
        t2 = _make_template(db, core_id=c.id, slug="dup-slug")
        assert t2.id != t1.id
        assert t2.version == t1.version + 1
        db.refresh(t1)
        assert t1.is_active is False

    def test_inactive_core_reference_rejected(self, db):
        c1 = _make_core(db, slug="kb-inact")
        update_core(db, c1.id, display_name="v2", updated_by=None)
        # c1 is now inactive
        with pytest.raises(InvalidTemplateShape):
            create_template(
                db,
                scope="vertical_default",
                vertical="funeral_home",
                template_slug="inactive-ref",
                display_name="x",
                inherits_from_core_id=c1.id,  # inactive
            )

    def test_count_compositions_referencing(self, db, tenant_company):
        c = _make_core(db, slug="kb-cc")
        t = _make_template(db, core_id=c.id, slug="cc")
        assert count_compositions_referencing(db, t.id) == 0
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"hidden_placement_ids": []},
        )
        assert count_compositions_referencing(db, t.id) == 1


# ═══ Tier 3 — Compositions ══════════════════════════════════════


class TestFocusCompositionsService:
    def test_lazy_fork_create(self, db, tenant_company):
        c = _make_core(db, slug="kb-lf")
        t = _make_template(db, core_id=c.id)
        assert (
            get_composition_by_tenant_template(db, tenant_company, t.id)
            is None
        )
        row = create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"hidden_placement_ids": ["x"]},
        )
        assert row.version == 1
        assert row.tenant_id == tenant_company
        assert row.inherits_from_template_id == t.id
        assert row.inherits_from_template_version == t.version

    def test_subsequent_update_versions(self, db, tenant_company):
        c = _make_core(db, slug="kb-up")
        t = _make_template(db, core_id=c.id)
        r1 = create_or_update_composition(
            db, tenant_id=tenant_company, template_id=t.id, deltas=None
        )
        r2 = create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"hidden_placement_ids": ["x"]},
        )
        assert r2.id != r1.id
        assert r2.version == 2
        db.refresh(r1)
        assert r1.is_active is False

    def test_reset_composition(self, db, tenant_company):
        c = _make_core(db, slug="kb-rs")
        t = _make_template(db, core_id=c.id)
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"hidden_placement_ids": ["x"]},
            canvas_config_overrides={"gap_size": 99},
        )
        r = reset_composition_to_default(db, tenant_company, t.id)
        assert r.deltas == {
            "hidden_placement_ids": [],
            "additional_placements": [],
            "placement_order": [],
            "placement_geometry_overrides": {},
            "core_geometry_override": None,
            # Sub-arc B-3 added chrome_overrides to the deltas vocabulary.
            "chrome_overrides": {},
            # Sub-arc B-4 added substrate_overrides to the deltas vocabulary.
            "substrate_overrides": {},
            # Sub-arc B-5 added typography_overrides to the deltas vocabulary.
            "typography_overrides": {},
        }
        assert r.canvas_config_overrides == {}

    def test_reset_composition_when_absent_raises(self, db, tenant_company):
        c = _make_core(db, slug="kb-rsabs")
        t = _make_template(db, core_id=c.id)
        with pytest.raises(CompositionNotFound):
            reset_composition_to_default(db, tenant_company, t.id)

    def test_reset_placement(self, db, tenant_company):
        c = _make_core(db, slug="kb-rsp")
        t = _make_template(db, core_id=c.id)
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={
                "hidden_placement_ids": ["today", "anomalies"],
                "placement_geometry_overrides": {
                    "today": {"starting_column": 0, "column_span": 6},
                    "anomalies": {"starting_column": 6, "column_span": 6},
                },
                "placement_order": ["today", "anomalies"],
            },
        )
        r = reset_placement_to_default(db, tenant_company, t.id, "today")
        assert r.deltas["hidden_placement_ids"] == ["anomalies"]
        assert "today" not in r.deltas["placement_geometry_overrides"]
        assert "anomalies" in r.deltas["placement_geometry_overrides"]
        assert r.deltas["placement_order"] == ["anomalies"]

    def test_core_geometry_override_out_of_bounds_rejected(
        self, db, tenant_company
    ):
        c = _make_core(
            db, slug="kb-oob", min_column_span=8, max_column_span=12
        )
        t = _make_template(db, core_id=c.id)
        with pytest.raises(InvalidCompositionShape):
            create_or_update_composition(
                db,
                tenant_id=tenant_company,
                template_id=t.id,
                deltas={
                    "core_geometry_override": {
                        "starting_column": 0,
                        "column_span": 4,  # < min 8
                        "row_index": 0,
                    }
                },
            )

    def test_orphan_placement_id_accepted_at_write(self, db, tenant_company):
        """Writing a hidden_placement_id that doesn't exist in the
        template is permitted — resolver silently drops at READ
        time. Important for graceful upstream-change recovery."""
        c = _make_core(db, slug="kb-orph")
        t = _make_template(db, core_id=c.id)
        r = create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"hidden_placement_ids": ["nonexistent"]},
        )
        assert "nonexistent" in r.deltas["hidden_placement_ids"]

    def test_unknown_delta_key_rejected(self, db, tenant_company):
        c = _make_core(db, slug="kb-uk")
        t = _make_template(db, core_id=c.id)
        with pytest.raises(InvalidCompositionShape):
            create_or_update_composition(
                db,
                tenant_id=tenant_company,
                template_id=t.id,
                deltas={"some_future_key": "value"},
            )


# ═══ Resolver ═══════════════════════════════════════════════════


class TestResolver:
    def test_platform_default_no_tenant(self, db):
        c = _make_core(db, slug="kb-pd-only")
        create_template(
            db,
            scope="platform_default",
            vertical=None,
            template_slug="pd-only",
            display_name="PD",
            inherits_from_core_id=c.id,
            rows=[],
        )
        resolved = resolve_focus(
            db, template_slug="pd-only", vertical=None, tenant_id=None
        )
        assert resolved.template_scope == "platform_default"
        assert resolved.template_vertical is None
        # Core injected as a placement.
        assert len(resolved.rows) == 1
        assert any(
            p.get("is_core") is True for p in resolved.rows[0]["placements"]
        )
        assert resolved.core_slug == "kb-pd-only"
        assert resolved.sources["tenant"] is None

    def test_vertical_default_no_tenant(self, db):
        c = _make_core(db, slug="kb-vd-only")
        _make_template(db, core_id=c.id, slug="vd-only")
        resolved = resolve_focus(
            db, template_slug="vd-only", vertical="funeral_home"
        )
        assert resolved.template_scope == "vertical_default"
        assert resolved.template_vertical == "funeral_home"

    def test_vertical_wins_when_both_exist(self, db):
        c = _make_core(db, slug="kb-both")
        create_template(
            db,
            scope="platform_default",
            vertical=None,
            template_slug="both",
            display_name="PD",
            inherits_from_core_id=c.id,
        )
        create_template(
            db,
            scope="vertical_default",
            vertical="funeral_home",
            template_slug="both",
            display_name="VD",
            inherits_from_core_id=c.id,
        )
        r = resolve_focus(db, template_slug="both", vertical="funeral_home")
        assert r.template_scope == "vertical_default"
        # Without vertical hint, falls back to platform_default.
        r2 = resolve_focus(db, template_slug="both", vertical=None)
        assert r2.template_scope == "platform_default"

    def test_tenant_no_fork_lazy_pre_edit(self, db, tenant_company):
        c = _make_core(db, slug="kb-lazy")
        _make_template(db, core_id=c.id, slug="lazy")
        r = resolve_focus(
            db,
            template_slug="lazy",
            vertical="funeral_home",
            tenant_id=tenant_company,
        )
        assert r.sources["tenant"] is None

    def test_tenant_fork_no_deltas(self, db, tenant_company):
        c = _make_core(db, slug="kb-fnd")
        t = _make_template(db, core_id=c.id, slug="fnd")
        create_or_update_composition(
            db, tenant_id=tenant_company, template_id=t.id, deltas=None
        )
        r = resolve_focus(
            db,
            template_slug="fnd",
            vertical="funeral_home",
            tenant_id=tenant_company,
        )
        assert r.sources["tenant"] is not None
        # Only the core is in rows.
        flat_placements = [
            p for row in r.rows for p in row["placements"]
        ]
        assert len(flat_placements) == 1
        assert flat_placements[0]["is_core"] is True

    def test_hidden_placement_ids_apply(self, db, tenant_company):
        c = _make_core(db, slug="kb-hp")
        rows = [
            {
                "row_id": "r1",
                "column_count": 12,
                "placements": [
                    {
                        "placement_id": "today",
                        "component_kind": "widget",
                        "component_name": "today",
                        "starting_column": 0,
                        "column_span": 12,
                    }
                ],
            }
        ]
        t = _make_template(db, core_id=c.id, slug="hp", rows=rows)
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={"hidden_placement_ids": ["today"]},
        )
        r = resolve_focus(
            db, template_slug="hp", vertical="funeral_home", tenant_id=tenant_company
        )
        placements = [p for row in r.rows for p in row["placements"]]
        ids = [p["placement_id"] for p in placements]
        assert "today" not in ids
        # Core still present.
        assert any(p.get("is_core") for p in placements)

    def test_additional_placements_apply(self, db, tenant_company):
        c = _make_core(db, slug="kb-add")
        rows = [
            {
                "row_id": "r1",
                "column_count": 12,
                "placements": [],
            }
        ]
        t = _make_template(db, core_id=c.id, slug="add", rows=rows)
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={
                "additional_placements": [
                    {
                        "placement_id": "extra",
                        "component_kind": "widget",
                        "component_name": "extra",
                        "row_index": 0,
                        "starting_column": 0,
                        "column_span": 6,
                    }
                ]
            },
        )
        r = resolve_focus(
            db, template_slug="add", vertical="funeral_home", tenant_id=tenant_company
        )
        flat = [p for row in r.rows for p in row["placements"]]
        ids = {p["placement_id"] for p in flat}
        assert "extra" in ids

    def test_placement_geometry_overrides_apply(self, db, tenant_company):
        c = _make_core(db, slug="kb-pgo")
        rows = [
            {
                "row_id": "r1",
                "column_count": 12,
                "placements": [
                    {
                        "placement_id": "today",
                        "component_kind": "widget",
                        "component_name": "today",
                        "starting_column": 0,
                        "column_span": 12,
                    }
                ],
            }
        ]
        t = _make_template(db, core_id=c.id, slug="pgo", rows=rows)
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={
                "placement_geometry_overrides": {
                    "today": {"starting_column": 0, "column_span": 6}
                }
            },
        )
        r = resolve_focus(
            db, template_slug="pgo", vertical="funeral_home", tenant_id=tenant_company
        )
        today = next(
            p
            for row in r.rows
            for p in row["placements"]
            if p["placement_id"] == "today"
        )
        assert today["column_span"] == 6

    def test_core_geometry_override_applies(self, db, tenant_company):
        c = _make_core(
            db, slug="kb-cgo", min_column_span=6, max_column_span=12
        )
        t = _make_template(db, core_id=c.id, slug="cgo")
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={
                "core_geometry_override": {
                    "starting_column": 3,
                    "column_span": 6,
                    "row_index": 0,
                }
            },
        )
        r = resolve_focus(
            db, template_slug="cgo", vertical="funeral_home", tenant_id=tenant_company
        )
        core_p = next(
            p for row in r.rows for p in row["placements"] if p.get("is_core")
        )
        assert core_p["starting_column"] == 3
        assert core_p["column_span"] == 6

    def test_orphan_geometry_override_silently_dropped(
        self, db, tenant_company
    ):
        c = _make_core(db, slug="kb-orph2")
        t = _make_template(db, core_id=c.id, slug="orph2")
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={
                "placement_geometry_overrides": {
                    "ghost": {"starting_column": 0, "column_span": 4}
                }
            },
        )
        # No raise — orphan silently dropped.
        r = resolve_focus(
            db, template_slug="orph2", vertical="funeral_home", tenant_id=tenant_company
        )
        # Core only, ghost wasn't synthesized.
        flat = [p for row in r.rows for p in row["placements"]]
        ids = {p["placement_id"] for p in flat}
        assert "ghost" not in ids

    def test_unknown_template_raises(self, db):
        with pytest.raises(FocusTemplateNotFound):
            resolve_focus(db, template_slug="nonexistent", vertical=None)

    def test_composition_order_determinism(self, db, tenant_company):
        """All deltas + canvas_config_overrides applied in canonical
        order produces a stable result on re-resolve."""
        c = _make_core(db, slug="kb-det")
        rows = [
            {
                "row_id": "r1",
                "column_count": 12,
                "placements": [
                    {
                        "placement_id": "a",
                        "component_kind": "widget",
                        "component_name": "a",
                        "starting_column": 0,
                        "column_span": 6,
                    },
                    {
                        "placement_id": "b",
                        "component_kind": "widget",
                        "component_name": "b",
                        "starting_column": 6,
                        "column_span": 6,
                    },
                ],
            }
        ]
        t = _make_template(
            db,
            core_id=c.id,
            slug="det",
            rows=rows,
            canvas_config={"gap_size": 4},
        )
        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={
                "placement_order": ["b", "a"],
                "placement_geometry_overrides": {
                    "a": {"starting_column": 6, "column_span": 6}
                },
            },
            canvas_config_overrides={"gap_size": 8, "padding": 12},
        )
        r1 = resolve_focus(
            db, template_slug="det", vertical="funeral_home", tenant_id=tenant_company
        )
        r2 = resolve_focus(
            db, template_slug="det", vertical="funeral_home", tenant_id=tenant_company
        )
        # Deterministic.
        assert r1.rows == r2.rows
        # canvas_config merge: template values + overrides on top.
        assert r1.canvas_config == {"gap_size": 8, "padding": 12}


# ═══ TestResolverSlugBasedLookup (sub-arc C-2.1.2) ═════════════════
#
# Verifies the resolver follows the active core BY SLUG, not by the
# template's stored `inherits_from_core_id`. The stored id becomes
# audit/lineage; the live cascade always resolves through the slug.
#
# Pre-C-2.1.2 the resolver did `db.query(FocusCore).filter(id == ...)`
# which would happily return inactive rows or fail when the bumped
# version's id moved on. Post-C-2.1.2 it does
# `slug_by_id → active_core_by_slug`, so cross-session version bumps
# propagate transparently to every dependent template.


class TestResolverSlugBasedLookup:
    def test_resolver_follows_slug_when_stored_id_active(
        self, db, tenant_company
    ):
        """Regression: stored UUID is the active row — slug lookup
        returns the same row. Existing in-place mutation cascade
        still works (same row id → same row resolved)."""
        c = _make_core(db, slug="slug-1")
        _make_template(db, core_id=c.id, slug="slug-tpl-1")
        r = resolve_focus(
            db,
            template_slug="slug-tpl-1",
            vertical="funeral_home",
            tenant_id=tenant_company,
        )
        assert r.core_id == c.id
        assert r.core_slug == "slug-1"
        assert r.core_version == 1

    def test_resolver_follows_slug_after_cross_session_version_bump(
        self, db, tenant_company
    ):
        """New behavior: an out-of-session core version-bump strands
        the template's stored UUID on the now-inactive row. The
        resolver MUST still produce the new active core's view —
        otherwise every template referencing that core silently
        renders stale chrome/geometry until it's manually re-pointed.
        """
        c1 = _make_core(db, slug="slug-2")
        _make_template(db, core_id=c1.id, slug="slug-tpl-2")
        # Out-of-session version bump (no edit_session_id → bumps).
        c2 = update_core(
            db,
            c1.id,
            display_name="v2",
            chrome={"preset": "frosted"},
            updated_by=None,
        )
        # The template's stored inherits_from_core_id still points at
        # c1.id — that's the audit trail. The resolver must follow
        # the slug to c2.
        assert c2.id != c1.id
        r = resolve_focus(
            db,
            template_slug="slug-tpl-2",
            vertical="funeral_home",
            tenant_id=tenant_company,
        )
        assert r.core_id == c2.id  # active row id
        assert r.core_slug == "slug-2"  # same slug
        assert r.core_version == c2.version
        # And the bumped chrome surfaces through the live cascade.
        assert r.resolved_chrome is not None
        assert r.resolved_chrome.get("preset") == "frosted"

    def test_resolver_orphan_slug_raises(self, db, tenant_company):
        """Operational-integrity guard: every slug must have an
        active row. If a manual DB intervention deactivated the only
        row, the resolver surfaces an explicit error rather than
        silently swallowing — the partial unique index
        `ix_focus_cores_active_slug` would normally prevent this
        state, but the assertion is the canonical safety net."""
        c = _make_core(db, slug="slug-3")
        _make_template(db, core_id=c.id, slug="slug-tpl-3")
        c.is_active = False
        db.commit()
        with pytest.raises(FocusTemplateNotFound) as ei:
            resolve_focus(
                db,
                template_slug="slug-tpl-3",
                vertical="funeral_home",
                tenant_id=tenant_company,
            )
        msg = str(ei.value)
        assert "slug-3" in msg
        assert "active" in msg.lower() or "orphan" in msg.lower()

    def test_resolver_in_place_mutation_propagates_without_id_change(
        self, db, tenant_company
    ):
        """Regression: an in-place mutation (same session token)
        leaves the row id stable. The resolver still returns the
        same core_id, AND the mutated chrome surfaces — same as
        pre-C-2.1.2 plus session-aware mutation."""
        import uuid as _uuid
        c = _make_core(db, slug="slug-4")
        _make_template(db, core_id=c.id, slug="slug-tpl-4")
        sid = str(_uuid.uuid4())
        updated = update_core(
            db,
            c.id,
            chrome={"preset": "card", "elevation": 90},
            edit_session_id=sid,
            updated_by=None,
        )
        assert updated.id == c.id
        r = resolve_focus(
            db,
            template_slug="slug-tpl-4",
            vertical="funeral_home",
            tenant_id=tenant_company,
        )
        assert r.core_id == c.id
        assert r.resolved_chrome is not None
        assert r.resolved_chrome.get("preset") == "card"
        assert r.resolved_chrome.get("elevation") == 90
