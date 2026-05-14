"""Focus composition layer integration tests (B-2 rewrite).

The old R-3.0-era `focus_compositions` tests were structurally
incompatible with the post-r96 three-tier substrate (focus_cores →
focus_templates → focus_compositions). The vast majority of scope-
walking, CRUD-lifecycle, and validation coverage now lives in:

  - `test_focus_template_schema.py`               (sub-arc A)
  - `test_focus_template_inheritance_service.py`  (B-1, service layer)
  - `test_focus_template_inheritance_admin_api.py` (B-1, admin API)

What this file preserves is the **integration shape** the legacy
suite implicitly tested: a vertical_default template overrides a
platform_default template at the resolver, and a tenant Tier 3
composition layers on top. The B-1 service tests assert these
properties unit-by-unit; this file asserts they compose end-to-end
through the resolver (a thin smoke layer above B-1's exhaustive
coverage).
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
    create_core,
    create_or_update_composition,
    create_template,
    resolve_focus,
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
            name=f"FC Test {suffix}",
            slug=f"fc-{suffix}",
            is_active=True,
            vertical="funeral_home",
        )
        s.add(co)
        s.commit()
        yield co.id
        s.query(FocusComposition).filter(
            FocusComposition.tenant_id == co.id
        ).delete()
        s.delete(co)
        s.commit()
    finally:
        s.close()


def _core(db) -> FocusCore:
    return create_core(
        db,
        core_slug="scheduling-kanban",
        display_name="Scheduling Kanban",
        description=None,
        registered_component_kind="focus-core",
        registered_component_name="SchedulingKanbanCore",
        default_starting_column=0,
        default_column_span=12,
        default_row_index=0,
        min_column_span=8,
        max_column_span=12,
    )


def _template(
    db,
    *,
    core: FocusCore,
    scope: str,
    vertical: str | None,
    slug: str,
) -> FocusTemplate:
    return create_template(
        db,
        scope=scope,
        vertical=vertical,
        template_slug=slug,
        display_name=slug.replace("-", " ").title(),
        description=None,
        inherits_from_core_id=core.id,
        rows=[],
        canvas_config={"gap_size": 10},
    )


class TestResolverComposition:
    """End-to-end resolver smoke — Tier 1 + Tier 2 + Tier 3 cooperate."""

    def test_vertical_wins_over_platform(self, db):
        core = _core(db)
        _template(
            db,
            core=core,
            scope="platform_default",
            vertical=None,
            slug="scheduling-default",
        )
        v = _template(
            db,
            core=core,
            scope="vertical_default",
            vertical="funeral_home",
            slug="scheduling-fh",
        )

        result = resolve_focus(
            db,
            template_slug="scheduling-fh",
            vertical="funeral_home",
            tenant_id=None,
        )
        assert result.template_id == v.id
        assert result.template_scope == "vertical_default"

    def test_tier3_composition_applies_over_template(
        self, db, tenant_company
    ):
        core = _core(db)
        t = _template(
            db,
            core=core,
            scope="vertical_default",
            vertical="funeral_home",
            slug="scheduling-fh",
        )

        create_or_update_composition(
            db,
            tenant_id=tenant_company,
            template_id=t.id,
            deltas={},
            canvas_config_overrides={"padding": 4},
        )

        result = resolve_focus(
            db,
            template_slug="scheduling-fh",
            vertical="funeral_home",
            tenant_id=tenant_company,
        )
        assert result.template_id == t.id
        # canvas_config compose = template + tenant overrides
        assert result.canvas_config.get("padding") == 4
        assert result.canvas_config.get("gap_size") == 10

    def test_unknown_template_raises_not_found(self, db):
        from app.services.focus_template_inheritance import (
            FocusTemplateNotFound,
        )

        with pytest.raises(FocusTemplateNotFound):
            resolve_focus(
                db,
                template_slug="does-not-exist",
                vertical="funeral_home",
                tenant_id=None,
            )
