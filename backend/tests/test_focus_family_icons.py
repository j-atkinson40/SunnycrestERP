"""Focus family icons (r122) — the core-type icon, lineage-resolved.

Pins: (1) a VARIATION renders its lineage ROOT core's icon (inherited at
read, never copied); (2) changing the core's icon propagates to every
variation immediately — including variations with a STALE pin (identity,
not versioned content; it does NOT ride the offer system); (3) the core
resolver carries the icon + survives the rebind; (4) seeds assign-if-null
(an operator's choice is never clobbered); (5) CoreResponse carries icon
+ the update route's sent-null-clears / omitted-preserves contract.

State-immunity: unique-slug fixtures, fixture-scoped teardown.
"""

from __future__ import annotations

import uuid

import pytest

from app.database import SessionLocal
from app.models.focus_core import FocusCore
from app.models.focus_template import FocusTemplate
from app.services.focus_template_inheritance import (
    create_core,
    create_template,
    update_core,
)
from app.services.maps_of_content.service import resolve_references


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def env(db):
    suffix = uuid.uuid4().hex[:8]
    core = create_core(
        db,
        core_slug=f"icon-core-{suffix}",
        display_name=f"Icon Core {suffix}",
        registered_component_kind="focus-core",
        registered_component_name="SchedulingKanbanCore",
        default_starting_column=0, default_column_span=12,
        default_row_index=0, min_column_span=8, max_column_span=12,
        canvas_config={},
        icon="kanban",
    )
    tmpl = create_template(
        db, scope="vertical_default", vertical="manufacturing",
        template_slug=f"icon-var-{suffix}", display_name="Icon Variation",
        inherits_from_core_id=core.id, rows=[], canvas_config={},
    )
    yield {"db": db, "core": core, "tmpl": tmpl, "suffix": suffix}
    s = SessionLocal()
    try:
        s.query(FocusTemplate).filter(
            FocusTemplate.template_slug == f"icon-var-{suffix}"
        ).delete(synchronize_session=False)
        s.query(FocusCore).filter(
            FocusCore.core_slug == f"icon-core-{suffix}"
        ).delete(synchronize_session=False)
        s.commit()
    finally:
        s.close()


def _resolve(db, builder: str, artifact_id: str) -> dict:
    sections = [{
        "section_id": "s1", "title": "Focuses", "order": 0,
        "rows": [{"row_id": "r1", "builder": builder,
                  "artifact_id": artifact_id, "label": "x", "order": 0}],
    }]
    return resolve_references(db, sections)[0]["rows"][0]["resolution"]


def test_variation_renders_root_core_icon(env):
    res = _resolve(env["db"], "focuses", env["tmpl"].id)
    assert res["icon"] == "kanban"          # inherited at read, never copied


def test_core_icon_change_propagates_even_past_a_stale_pin(env):
    db, core, tmpl = env["db"], env["core"], env["tmpl"]
    # The core bumps (v2) with a NEW icon; the variation's pin stays at v1.
    v2 = update_core(db, core.id, display_name=f"{core.display_name} v2",
                     icon="scale")
    assert v2.version == 2 and v2.id != core.id
    res = _resolve(db, "focuses", tmpl.id)
    # Family identity is the CURRENT icon — not versioned, not offered.
    assert res["icon"] == "scale"
    # And the core resolver rebinds + carries it too (stale core-ref id).
    core_res = _resolve(db, "focus-cores", core.id)
    assert core_res["available"] is True
    assert core_res["icon"] == "scale"


def test_icon_carries_across_bumps_when_not_sent(env):
    db, core = env["db"], env["core"]
    v2 = update_core(db, core.id, display_name="renamed only")
    assert v2.icon == "kanban"              # omitted preserves (the carry)
    v3 = update_core(db, v2.id, icon=None)
    assert v3.icon is None                  # explicit None clears


def test_seed_assign_if_null_never_clobbers(db):
    """The demo seed's COALESCE(icon, :i) discipline: NULL gets the default;
    an operator's choice survives a re-seed."""
    from scripts.seed_demo_artifact_focuses import _upsert_core

    suffix = uuid.uuid4().hex[:8]
    slug = f"seed-icon-{suffix}"
    try:
        cid, _ = _upsert_core(db, slug=slug, display="Seed Icon",
                              component="TriageQueueCore", icon="scale")
        db.commit()
        assert db.get(FocusCore, cid).icon == "scale"     # assigned on create
        # Operator changes it…
        row = db.get(FocusCore, cid)
        row.icon = "gavel"
        db.add(row)
        db.commit()
        # …and the deploy re-seed does NOT clobber.
        _upsert_core(db, slug=slug, display="Seed Icon",
                     component="TriageQueueCore", icon="scale")
        db.commit()
        db.expire_all()
        assert db.get(FocusCore, cid).icon == "gavel"
    finally:
        db.rollback()
        db.query(FocusCore).filter(FocusCore.core_slug == slug).delete(
            synchronize_session=False
        )
        db.commit()


def test_core_response_carries_icon(env):
    from fastapi.testclient import TestClient

    from app.core.security import create_access_token
    from app.models.platform_user import PlatformUser
    from app.main import app

    db = env["db"]
    suffix = env["suffix"]
    admin = PlatformUser(
        id=str(uuid.uuid4()), email=f"icon-{suffix}@bridgeable.test",
        hashed_password="x", first_name="I", last_name="C",
        role="super_admin", is_active=True,
    )
    db.add(admin)
    db.commit()
    try:
        token = create_access_token({"sub": admin.id}, realm="platform")
        client = TestClient(app)
        r = client.get(
            f"/api/platform/admin/focus-template-inheritance/cores/{env['core'].id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["icon"] == "kanban"
    finally:
        db.delete(admin)
        db.commit()
