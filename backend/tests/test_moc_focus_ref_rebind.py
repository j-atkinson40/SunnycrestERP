"""Focus ref-decay rebind (Focus Variations V-1, commit 1).

focus_template version bumps mint NEW row ids (deactivate prior + insert at
version+1), so anything keyed to a row id decays on the template's next edit:

  1. MoC authored refs + task-catalog focus joins → the pill dims
     (available=False) and its deep-link opens a retained snapshot.
  2. Tier 3 tenant compositions → the tenant's customizations are ORPHANED
     (the resolver matched only the active row's id).

The rebind applies the C-2.1.2 slug-translation canon at read time: the
(scope, vertical, template_slug) tuple is the stable identity; stale ids
re-bind to the lineage's ACTIVE row. These tests pin both reads.

State-immunity: fixtures use unique slugs + a per-test company; assertions
are fixture-scoped. Cleanup deletes ONLY this file's rows (no global wipes —
the dev DB's seeded focus content must survive a run).
"""

from __future__ import annotations

import uuid

import pytest

from app.database import SessionLocal
from app.models.company import Company
from app.models.focus_composition import FocusComposition
from app.models.focus_core import FocusCore
from app.models.focus_template import FocusTemplate
from app.models.moc_task_catalog import MoCTaskCatalog
from app.services.focus_template_inheritance import (
    create_core,
    create_or_update_composition,
    create_template,
    resolve_focus,
    update_template,
)
from app.services.maps_of_content.service import resolve_references
from app.services.maps_of_content.task_catalog import (
    resolve_task_catalog,
    upsert_task,
)


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def env(db):
    """A core + a platform_default template (unique slugs), torn down
    fixture-scoped afterwards."""
    suffix = uuid.uuid4().hex[:8]
    core = create_core(
        db,
        core_slug=f"rebind-core-{suffix}",
        display_name="Rebind Core",
        registered_component_kind="focus-core",
        registered_component_name="SchedulingKanbanCore",
        default_starting_column=0,
        default_column_span=12,
        default_row_index=0,
        min_column_span=8,
        max_column_span=12,
        canvas_config={},
    )
    tmpl = create_template(
        db,
        scope="platform_default",
        vertical=None,
        template_slug=f"rebind-tmpl-{suffix}",
        display_name="Rebind Template",
        inherits_from_core_id=core.id,
        rows=[],
        canvas_config={},
    )
    ctx = {"db": db, "core": core, "tmpl_v1": tmpl, "suffix": suffix,
           "slug": tmpl.template_slug}
    yield ctx
    # Fixture-scoped teardown: this lineage's rows only.
    s = SessionLocal()
    try:
        s.query(FocusComposition).filter(
            FocusComposition.inherits_from_template_id.in_(
                s.query(FocusTemplate.id).filter(
                    FocusTemplate.template_slug == ctx["slug"]
                ).scalar_subquery()
            )
        ).delete(synchronize_session=False)
        s.query(MoCTaskCatalog).filter(
            MoCTaskCatalog.name.like(f"%{suffix}%")
        ).delete(synchronize_session=False)
        s.query(FocusTemplate).filter(
            FocusTemplate.template_slug == ctx["slug"]
        ).delete(synchronize_session=False)
        s.query(FocusCore).filter(
            FocusCore.core_slug == f"rebind-core-{suffix}"
        ).delete(synchronize_session=False)
        s.commit()
    finally:
        s.close()


def _bump(db, template_id: str, *, name: str) -> FocusTemplate:
    """A non-session update → version-bump → NEW row id."""
    return update_template(db, template_id, display_name=name)


# ── 1. MoC authored refs survive a version bump ─────────────────────


def test_moc_ref_survives_version_bump(env):
    db = env["db"]
    v1 = env["tmpl_v1"]
    v2 = _bump(db, v1.id, name="Rebind Template v2")
    assert v2.id != v1.id and v2.version == 2  # the decay-producing mechanics

    sections = [{
        "section_id": "s1", "title": "Focuses", "order": 0,
        "rows": [{"row_id": "r1", "builder": "focuses",
                  "artifact_id": v1.id, "label": "Authored", "order": 0}],
    }]
    resolved = resolve_references(db, sections)
    res = resolved[0]["rows"][0]["resolution"]
    assert res["exists"] is True
    assert res["available"] is True                    # NOT dimmed
    assert res["label"] == "Rebind Template v2"        # the CURRENT name
    assert res["artifact_id"] == v2.id                 # deep-link → ACTIVE row
    assert res["routing"]["template_slug"] == env["slug"]


def test_moc_ref_fully_deactivated_lineage_stays_unavailable(env):
    db = env["db"]
    v1 = env["tmpl_v1"]
    # Deactivate the whole lineage (no active row to rebind to).
    db.query(FocusTemplate).filter(
        FocusTemplate.template_slug == env["slug"]
    ).update({"is_active": False})
    db.commit()
    sections = [{
        "section_id": "s1", "title": "Focuses", "order": 0,
        "rows": [{"row_id": "r1", "builder": "focuses",
                  "artifact_id": v1.id, "label": "Authored", "order": 0}],
    }]
    res = resolve_references(db, sections)[0]["rows"][0]["resolution"]
    assert res["exists"] is True
    assert res["available"] is False


# ── 2. Tier 3 compositions survive a template version bump ──────────


def test_composition_survives_template_version_bump(env):
    db = env["db"]
    v1 = env["tmpl_v1"]
    suffix = env["suffix"]
    co = Company(
        id=str(uuid.uuid4()), name=f"Rebind Co {suffix}",
        slug=f"rebindco-{suffix}", is_active=True, vertical="manufacturing",
    )
    db.add(co)
    db.commit()
    try:
        # Tenant customizes against v1 (a canvas_config override is delta
        # evidence that survives independent of placements).
        create_or_update_composition(
            db, tenant_id=co.id, template_id=v1.id,
            canvas_config_overrides={"gap_size": 99},
        )
        # The default's owner edits → version bump → new row id.
        _bump(db, v1.id, name="Rebind Template v2")

        r = resolve_focus(db, template_slug=env["slug"], vertical=None,
                          tenant_id=co.id)
        # Pre-rebind this lookup MISSED (composition keyed to v1's id) and
        # the tenant's customization silently vanished.
        assert r.canvas_config.get("gap_size") == 99
    finally:
        db.query(FocusComposition).filter(
            FocusComposition.tenant_id == co.id
        ).delete(synchronize_session=False)
        db.delete(co)
        db.commit()


# ── 3. task-catalog focus cells rebind (spread precedence) ──────────


def test_task_focus_cell_rebinds(env):
    db = env["db"]
    v1 = env["tmpl_v1"]
    suffix = env["suffix"]
    upsert_task(
        db, vertical="manufacturing", name=f"Rebind Task {suffix}",
        focus_template_ids=[v1.id],
    )
    v2 = _bump(db, v1.id, name="Rebind Template v2")

    tasks = resolve_task_catalog(db, vertical="manufacturing")
    mine = [t for t in tasks if t["name"] == f"Rebind Task {suffix}"]
    assert len(mine) == 1
    cell = mine[0]["focuses"][0]
    assert cell["available"] is True
    assert cell["artifact_id"] == v2.id     # rebound id WINS over the stored join id
    assert cell["label"] == "Rebind Template v2"
