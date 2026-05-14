"""Focus Template Inheritance sub-arc A — structural schema tests.

Covers ORM + DB-level constraint shape only. Service layer + API
endpoints land in sub-arc B; this suite asserts that the migration
created the substrate the resolver will build against.

Test classes:
    TestFocusCoreModel              — Tier 1 (focus_cores)
    TestFocusTemplateModel          — Tier 2 (focus_templates)
    TestFocusCompositionModel       — Tier 3 (focus_compositions)
    TestMigrationShape              — substrate state verification
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError


# ─── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture(autouse=True)
def _cleanup_new_tables():
    """Wipe the three new tables before + after each test to keep
    runs isolated. Order honors FK chain compositions → templates → cores.
    """
    from app.database import SessionLocal
    from app.models.focus_composition import FocusComposition
    from app.models.focus_template import FocusTemplate
    from app.models.focus_core import FocusCore

    def _wipe():
        db = SessionLocal()
        try:
            db.query(FocusComposition).delete()
            db.query(FocusTemplate).delete()
            db.query(FocusCore).delete()
            db.commit()
        finally:
            db.close()

    _wipe()
    yield
    _wipe()


@pytest.fixture
def make_company():
    """Factory that creates a minimal Company and returns its id."""
    from app.database import SessionLocal
    from app.models.company import Company

    created_ids: list[str] = []

    def _make() -> str:
        db = SessionLocal()
        try:
            suffix = uuid.uuid4().hex[:6]
            co = Company(
                id=str(uuid.uuid4()),
                name=f"FT Test Co {suffix}",
                slug=f"ft-test-{suffix}",
                is_active=True,
                vertical="manufacturing",
            )
            db.add(co)
            db.commit()
            created_ids.append(co.id)
            return co.id
        finally:
            db.close()

    yield _make

    # Cleanup any companies this factory created.
    db = SessionLocal()
    try:
        for cid in created_ids:
            db.query(Company).filter(Company.id == cid).delete()
        db.commit()
    finally:
        db.close()


# ─── Helpers ───────────────────────────────────────────────────────


def _make_core(db_session, **overrides):
    from app.models.focus_core import FocusCore

    suffix = uuid.uuid4().hex[:6]
    defaults = dict(
        core_slug=f"test-core-{suffix}",
        display_name="Test Core",
        registered_component_kind="focus",
        registered_component_name="TestCore",
    )
    defaults.update(overrides)
    core = FocusCore(**defaults)
    db_session.add(core)
    db_session.commit()
    return core


def _make_template(db_session, core, **overrides):
    from app.models.focus_template import FocusTemplate

    suffix = uuid.uuid4().hex[:6]
    defaults = dict(
        scope="platform_default",
        vertical=None,
        template_slug=f"test-tpl-{suffix}",
        display_name="Test Template",
        inherits_from_core_id=core.id,
        inherits_from_core_version=core.version,
    )
    defaults.update(overrides)
    tpl = FocusTemplate(**defaults)
    db_session.add(tpl)
    db_session.commit()
    return tpl


# ─── TestFocusCoreModel ────────────────────────────────────────────


class TestFocusCoreModel:
    def test_create_minimal(self, db_session):
        from app.models.focus_core import FocusCore

        core = FocusCore(
            core_slug="dispatcher",
            display_name="Dispatcher Kanban",
            registered_component_kind="focus",
            registered_component_name="DispatcherFocus",
        )
        db_session.add(core)
        db_session.commit()
        assert core.id is not None
        assert core.version == 1
        assert core.is_active is True
        assert core.canvas_config == {}
        assert core.default_starting_column == 0
        assert core.default_column_span == 12
        assert core.min_column_span == 6
        assert core.max_column_span == 12

    def test_unique_active_slug(self, db_session):
        from app.models.focus_core import FocusCore

        _make_core(db_session, core_slug="dup-slug")
        dup = FocusCore(
            core_slug="dup-slug",
            display_name="Dup",
            registered_component_kind="focus",
            registered_component_name="X",
        )
        db_session.add(dup)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_inactive_rows_allow_duplicates(self, db_session):
        from app.models.focus_core import FocusCore

        c1 = _make_core(db_session, core_slug="hist-slug")
        # Deactivate the first; second active row with same slug must succeed.
        c1.is_active = False
        db_session.commit()
        c2 = FocusCore(
            core_slug="hist-slug",
            display_name="Replacement",
            registered_component_kind="focus",
            registered_component_name="Y",
            version=2,
        )
        db_session.add(c2)
        db_session.commit()
        # Both rows present, only one active per slug.
        rows = (
            db_session.query(FocusCore)
            .filter(FocusCore.core_slug == "hist-slug")
            .all()
        )
        assert len(rows) == 2
        assert sum(1 for r in rows if r.is_active) == 1

    def test_default_geometry_check_constraints(self, db_session):
        # starting_column + span > 12 must be rejected.
        from app.models.focus_core import FocusCore

        core = FocusCore(
            core_slug="bad-geom",
            display_name="Bad",
            registered_component_kind="focus",
            registered_component_name="X",
            default_starting_column=10,
            default_column_span=8,  # 10 + 8 = 18 > 12
        )
        db_session.add(core)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_min_max_column_span_check_constraints(self, db_session):
        from app.models.focus_core import FocusCore

        # max < min must be rejected.
        bad = FocusCore(
            core_slug="bad-minmax",
            display_name="Bad",
            registered_component_kind="focus",
            registered_component_name="X",
            min_column_span=8,
            max_column_span=4,
            default_column_span=8,
        )
        db_session.add(bad)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_default_column_span_within_min_max(self, db_session):
        from app.models.focus_core import FocusCore

        # default_column_span outside [min, max] must be rejected.
        bad = FocusCore(
            core_slug="bad-default-span",
            display_name="Bad",
            registered_component_kind="focus",
            registered_component_name="X",
            min_column_span=6,
            max_column_span=10,
            default_column_span=12,  # > max=10
        )
        db_session.add(bad)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


# ─── TestFocusTemplateModel ────────────────────────────────────────


class TestFocusTemplateModel:
    def test_create_minimal_platform_default(self, db_session):
        core = _make_core(db_session)
        tpl = _make_template(db_session, core)
        assert tpl.id is not None
        assert tpl.scope == "platform_default"
        assert tpl.vertical is None
        assert tpl.rows == []
        assert tpl.canvas_config == {}
        assert tpl.version == 1
        assert tpl.is_active is True
        assert tpl.inherits_from_core_id == core.id

    def test_create_minimal_vertical_default(self, db_session):
        core = _make_core(db_session)
        tpl = _make_template(
            db_session,
            core,
            scope="vertical_default",
            vertical="manufacturing",
        )
        assert tpl.scope == "vertical_default"
        assert tpl.vertical == "manufacturing"

    def test_scope_vertical_correlation_check(self, db_session):
        # platform_default + non-null vertical must be rejected.
        from app.models.focus_template import FocusTemplate

        core = _make_core(db_session)
        bad = FocusTemplate(
            scope="platform_default",
            vertical="manufacturing",
            template_slug="bad-correlation",
            display_name="Bad",
            inherits_from_core_id=core.id,
            inherits_from_core_version=core.version,
        )
        db_session.add(bad)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_scope_vertical_correlation_check_inverse(self, db_session):
        # vertical_default + null vertical must be rejected.
        from app.models.focus_template import FocusTemplate

        core = _make_core(db_session)
        bad = FocusTemplate(
            scope="vertical_default",
            vertical=None,
            template_slug="bad-correlation-2",
            display_name="Bad",
            inherits_from_core_id=core.id,
            inherits_from_core_version=core.version,
        )
        db_session.add(bad)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_invalid_scope_rejected(self, db_session):
        from app.models.focus_template import FocusTemplate

        core = _make_core(db_session)
        bad = FocusTemplate(
            scope="tenant_override",  # Not allowed on focus_templates
            vertical=None,
            template_slug="bad-scope",
            display_name="Bad",
            inherits_from_core_id=core.id,
            inherits_from_core_version=core.version,
        )
        db_session.add(bad)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_fk_to_focus_cores(self, db_session):
        from app.models.focus_template import FocusTemplate

        # Non-existent core_id must be rejected.
        bad = FocusTemplate(
            scope="platform_default",
            vertical=None,
            template_slug="bad-fk-core",
            display_name="Bad",
            inherits_from_core_id=str(uuid.uuid4()),
            inherits_from_core_version=1,
        )
        db_session.add(bad)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_fk_to_verticals(self, db_session):
        from app.models.focus_template import FocusTemplate

        core = _make_core(db_session)
        # Non-existent vertical slug must be rejected.
        bad = FocusTemplate(
            scope="vertical_default",
            vertical="not_a_real_vertical",
            template_slug="bad-fk-vertical",
            display_name="Bad",
            inherits_from_core_id=core.id,
            inherits_from_core_version=core.version,
        )
        db_session.add(bad)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_unique_active_per_scope_vertical_slug(self, db_session):
        from app.models.focus_template import FocusTemplate

        core = _make_core(db_session)
        _make_template(
            db_session,
            core,
            scope="vertical_default",
            vertical="manufacturing",
            template_slug="dup-tpl",
        )
        # Same tuple with is_active=true must fail.
        dup = FocusTemplate(
            scope="vertical_default",
            vertical="manufacturing",
            template_slug="dup-tpl",
            display_name="Dup",
            inherits_from_core_id=core.id,
            inherits_from_core_version=core.version,
        )
        db_session.add(dup)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


# ─── TestFocusCompositionModel ─────────────────────────────────────


class TestFocusCompositionModel:
    def test_create_minimal(self, db_session, make_company):
        from app.models.focus_composition import FocusComposition

        company_id = make_company()
        core = _make_core(db_session)
        tpl = _make_template(db_session, core)
        comp = FocusComposition(
            tenant_id=company_id,
            inherits_from_template_id=tpl.id,
            inherits_from_template_version=tpl.version,
        )
        db_session.add(comp)
        db_session.commit()
        assert comp.id is not None
        assert comp.deltas == {}
        assert comp.canvas_config_overrides == {}
        assert comp.version == 1
        assert comp.is_active is True

    def test_fk_to_template(self, db_session, make_company):
        from app.models.focus_composition import FocusComposition

        company_id = make_company()
        bad = FocusComposition(
            tenant_id=company_id,
            inherits_from_template_id=str(uuid.uuid4()),
            inherits_from_template_version=1,
        )
        db_session.add(bad)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_fk_to_companies_cascade(self, db_session, make_company):
        """Deleting the parent Company must cascade-delete its
        focus_compositions rows."""
        from app.models.company import Company
        from app.models.focus_composition import FocusComposition

        company_id = make_company()
        core = _make_core(db_session)
        tpl = _make_template(db_session, core)
        comp = FocusComposition(
            tenant_id=company_id,
            inherits_from_template_id=tpl.id,
            inherits_from_template_version=tpl.version,
        )
        db_session.add(comp)
        db_session.commit()
        comp_id = comp.id

        db_session.query(Company).filter(Company.id == company_id).delete()
        db_session.commit()

        remaining = (
            db_session.query(FocusComposition)
            .filter(FocusComposition.id == comp_id)
            .first()
        )
        assert remaining is None

    def test_unique_active_per_tenant_template(self, db_session, make_company):
        from app.models.focus_composition import FocusComposition

        company_id = make_company()
        core = _make_core(db_session)
        tpl = _make_template(db_session, core)
        c1 = FocusComposition(
            tenant_id=company_id,
            inherits_from_template_id=tpl.id,
            inherits_from_template_version=tpl.version,
        )
        db_session.add(c1)
        db_session.commit()

        # Second active row with same (tenant, template) must fail.
        c2 = FocusComposition(
            tenant_id=company_id,
            inherits_from_template_id=tpl.id,
            inherits_from_template_version=tpl.version,
        )
        db_session.add(c2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

        # But after deactivating c1, second active row should succeed.
        c1.is_active = False
        db_session.commit()
        c3 = FocusComposition(
            tenant_id=company_id,
            inherits_from_template_id=tpl.id,
            inherits_from_template_version=tpl.version,
            version=2,
        )
        db_session.add(c3)
        db_session.commit()

    def test_deltas_default_empty_object(self, db_session, make_company):
        from app.models.focus_composition import FocusComposition

        company_id = make_company()
        core = _make_core(db_session)
        tpl = _make_template(db_session, core)
        comp = FocusComposition(
            tenant_id=company_id,
            inherits_from_template_id=tpl.id,
            inherits_from_template_version=tpl.version,
        )
        db_session.add(comp)
        db_session.commit()
        db_session.refresh(comp)
        assert comp.deltas == {}

    def test_canvas_config_overrides_default_empty_object(
        self, db_session, make_company
    ):
        from app.models.focus_composition import FocusComposition

        company_id = make_company()
        core = _make_core(db_session)
        tpl = _make_template(db_session, core)
        comp = FocusComposition(
            tenant_id=company_id,
            inherits_from_template_id=tpl.id,
            inherits_from_template_version=tpl.version,
        )
        db_session.add(comp)
        db_session.commit()
        db_session.refresh(comp)
        assert comp.canvas_config_overrides == {}


# ─── TestMigrationShape ────────────────────────────────────────────


class TestMigrationShape:
    def test_focus_compositions_dropped_and_recreated(self, db_session):
        """Post-r96, focus_compositions exists but has the new shape —
        no `scope` / `vertical` / `focus_type` / `rows` / `kind` /
        `pages` columns, but has `tenant_id` (NOT NULL) +
        `inherits_from_template_id` + `deltas` +
        `canvas_config_overrides`.
        """
        insp = sa.inspect(db_session.bind)
        cols = {c["name"] for c in insp.get_columns("focus_compositions")}
        # New columns present:
        assert "tenant_id" in cols
        assert "inherits_from_template_id" in cols
        assert "inherits_from_template_version" in cols
        assert "deltas" in cols
        assert "canvas_config_overrides" in cols
        # Old columns removed:
        assert "scope" not in cols
        assert "vertical" not in cols
        assert "focus_type" not in cols
        assert "rows" not in cols
        assert "kind" not in cols
        assert "pages" not in cols
        assert "canvas_config" not in cols
        assert "placements" not in cols

    def test_inherits_from_columns_present(self, db_session):
        """Forward-compat: both `_id` and `_version` columns must
        ship on focus_templates AND focus_compositions, even though
        v1 resolver in sub-arc B ignores the version."""
        insp = sa.inspect(db_session.bind)
        tpl_cols = {c["name"] for c in insp.get_columns("focus_templates")}
        assert "inherits_from_core_id" in tpl_cols
        assert "inherits_from_core_version" in tpl_cols
        comp_cols = {
            c["name"] for c in insp.get_columns("focus_compositions")
        }
        assert "inherits_from_template_id" in comp_cols
        assert "inherits_from_template_version" in comp_cols

    def test_indexes_present(self, db_session):
        insp = sa.inspect(db_session.bind)
        core_idx = {i["name"] for i in insp.get_indexes("focus_cores")}
        assert "ix_focus_cores_active_slug" in core_idx

        tpl_idx = {i["name"] for i in insp.get_indexes("focus_templates")}
        assert "ix_focus_templates_active" in tpl_idx
        assert "ix_focus_templates_lookup" in tpl_idx

        comp_idx = {
            i["name"] for i in insp.get_indexes("focus_compositions")
        }
        assert "ix_focus_compositions_active_per_tenant_template" in comp_idx
        assert "ix_focus_compositions_tenant_template" in comp_idx
