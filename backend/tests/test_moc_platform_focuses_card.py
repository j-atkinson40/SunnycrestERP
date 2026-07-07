"""Platform MoC Focuses card (Focus Variations V-1, commit 3).

The platform map's Focuses card shows the Tier 1 core defaults (builder
'focus-cores' — the fork-menu targets) + platform_default Tier 2 templates.
Pins: (1) the seed authors the focus-defaults section query-built (content-
agnostic — no hardcoded slugs); (2) the focus-cores resolver resolves + carries
the Focus-editor routing; (3) core refs survive a core version bump (the same
slug rebind as _resolve_focus).

State-immunity: fixture-scoped assertions (my unique-slug core's row).
Teardown re-runs the seed after deleting fixture rows so the dev platform
page never retains refs to deleted fixture cores.
"""

from __future__ import annotations

import uuid

import pytest

from app.database import SessionLocal
from app.models.focus_core import FocusCore
from app.services.focus_template_inheritance import create_core, update_core
from app.services.maps_of_content.service import resolve_references
from scripts import seed_moc_platform as seed_mod


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def core(db):
    suffix = uuid.uuid4().hex[:8]
    row = create_core(
        db,
        core_slug=f"card-core-{suffix}",
        display_name=f"Card Core {suffix}",
        registered_component_kind="focus-core",
        registered_component_name="SchedulingKanbanCore",
        default_starting_column=0,
        default_column_span=12,
        default_row_index=0,
        min_column_span=8,
        max_column_span=12,
        canvas_config={},
    )
    yield row
    s = SessionLocal()
    try:
        s.query(FocusCore).filter(
            FocusCore.core_slug == f"card-core-{suffix}"
        ).delete(synchronize_session=False)
        s.commit()
        # Restore the platform page's query-built sections WITHOUT the
        # deleted fixture core (never leave a fixture ref on the dev page).
        seed_mod.seed(s)
    finally:
        s.close()


def test_seed_authors_focus_defaults_section(db, core):
    result = seed_mod.seed(db)
    assert result["focus_rows"] >= 1
    from app.models.moc_page import MoCPage

    row = (
        db.query(MoCPage)
        .filter(MoCPage.scope == "platform_default",
                MoCPage.slug == seed_mod.SLUG,
                MoCPage.is_active.is_(True))
        .first()
    )
    assert row is not None
    sections = {s["section_id"]: s for s in row.sections}
    assert "focus-defaults" in sections
    mine = [r for r in sections["focus-defaults"]["rows"]
            if r["artifact_id"] == core.id]
    assert len(mine) == 1                       # my core authored, exactly once
    assert mine[0]["builder"] == "focus-cores"
    assert mine[0]["label"] == core.display_name


def test_focus_core_resolver_resolves_and_routes(db, core):
    sections = [{
        "section_id": "s1", "title": "Focuses", "order": 0,
        "rows": [{"row_id": "r1", "builder": "focus-cores",
                  "artifact_id": core.id, "label": "Authored", "order": 0}],
    }]
    res = resolve_references(db, sections)[0]["rows"][0]["resolution"]
    assert res["exists"] is True and res["available"] is True
    assert res["label"] == core.display_name
    assert res["routing"]["core_slug"] == core.core_slug


def test_focus_core_ref_survives_version_bump(db, core):
    v2 = update_core(db, core.id, display_name=f"{core.display_name} v2")
    assert v2.id != core.id and v2.version == 2

    sections = [{
        "section_id": "s1", "title": "Focuses", "order": 0,
        "rows": [{"row_id": "r1", "builder": "focus-cores",
                  "artifact_id": core.id, "label": "Authored", "order": 0}],
    }]
    res = resolve_references(db, sections)[0]["rows"][0]["resolution"]
    assert res["available"] is True
    assert res["artifact_id"] == v2.id          # rebound to the ACTIVE row
    assert res["label"].endswith("v2")
