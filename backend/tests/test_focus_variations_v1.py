"""Focus Variations V-1 — fork-menu blast radius + the guided flow.

Pins:
  1. `admin_core_usage` is LINEAGE-aware — templates created against a prior
     core version still count after the core bumps (the fork menu's blast
     radius must be REAL; the exact-id filter undercounted to zero).
  2. The guided flow (one POST) creates + pins + wires + authors:
     Tier 2 variation at the home vertical, inherits_from_core_version pinned
     to the live core, slug-keyed join rows for EVERY chosen vertical
     (multi-vertical round-trip), the task's focus set gains the variation,
     and each chosen vertical's map page carries the auto-authored ref
     (creation lights the maps).
  3. A display-name collision mints a FRESH lineage (never version-bumps an
     existing template out from under its owner).

State-immunity: unique-slug fixtures; page sections snapshotted + restored;
no global wipes.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.database import SessionLocal
from app.models.focus_core import FocusCore
from app.models.focus_template import FocusTemplate
from app.models.focus_template_vertical import FocusTemplateVertical
from app.models.moc_page import MoCPage
from app.models.moc_task_catalog import MoCTaskCatalog
from app.models.platform_user import PlatformUser
from app.services.focus_template_inheritance import (
    create_core,
    create_template,
    get_template_by_id,
    update_core,
)
from app.services.maps_of_content.task_catalog import upsert_task

MOC_ROOT = "/api/platform/admin/moc"
FTI_ROOT = "/api/platform/admin/focus-template-inheritance"
VERTICALS = ["manufacturing", "funeral_home"]


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def admin_headers():
    s = SessionLocal()
    suffix = uuid.uuid4().hex[:6]
    admin = PlatformUser(
        id=str(uuid.uuid4()),
        email=f"fv-{suffix}@bridgeable.test",
        hashed_password="x",
        first_name="F",
        last_name="V",
        role="super_admin",
        is_active=True,
    )
    s.add(admin)
    s.commit()
    token = create_access_token({"sub": admin.id}, realm="platform")
    yield {"Authorization": f"Bearer {token}"}
    s.delete(admin)
    s.commit()
    s.close()


@pytest.fixture
def env(db):
    """Unique-slug core + snapshot/restore of both verticals' page sections
    (the flow authors refs onto REAL vertical pages — never leave residue)."""
    suffix = uuid.uuid4().hex[:8]
    core = create_core(
        db,
        core_slug=f"fv-core-{suffix}",
        display_name=f"FV Core {suffix}",
        registered_component_kind="focus-core",
        registered_component_name="SchedulingKanbanCore",
        default_starting_column=0,
        default_column_span=12,
        default_row_index=0,
        min_column_span=8,
        max_column_span=12,
        canvas_config={},
    )
    snapshots: dict[str, list | None] = {}
    created_pages: list[str] = []
    for v in VERTICALS:
        page = (
            db.query(MoCPage)
            .filter(MoCPage.scope == "vertical_default",
                    MoCPage.vertical == v, MoCPage.is_active.is_(True))
            .first()
        )
        if page is None:
            from app.services.maps_of_content import service as moc_service

            page = moc_service.create_page(
                db, scope="vertical_default", vertical=v,
                slug=f"map-{v}", title=v.title(), sections=[],
            )
            created_pages.append(page.id)
            snapshots[v] = None
        else:
            snapshots[v] = [dict(s_) for s_ in (page.sections or [])]
    yield {"db": db, "core": core, "suffix": suffix}
    s = SessionLocal()
    try:
        s.query(MoCTaskCatalog).filter(
            MoCTaskCatalog.name.like(f"%{suffix}%")
        ).delete(synchronize_session=False)
        s.query(FocusTemplateVertical).filter(
            FocusTemplateVertical.template_slug.like(f"fv-var-{suffix}%")
        ).delete(synchronize_session=False)
        s.query(FocusTemplate).filter(
            FocusTemplate.template_slug.like(f"fv-var-{suffix}%")
        ).delete(synchronize_session=False)
        s.query(FocusCore).filter(
            FocusCore.core_slug == f"fv-core-{suffix}"
        ).delete(synchronize_session=False)
        for v in VERTICALS:
            page = (
                s.query(MoCPage)
                .filter(MoCPage.scope == "vertical_default",
                        MoCPage.vertical == v, MoCPage.is_active.is_(True))
                .first()
            )
            if page is None:
                continue
            if page.id in created_pages:
                s.delete(page)
            elif snapshots.get(v) is not None:
                page.sections = snapshots[v]
                s.add(page)
        s.commit()
    finally:
        s.close()


# ── 1. blast radius is lineage-aware ────────────────────────────────


def test_core_usage_is_lineage_aware(client, env, admin_headers):
    db, core, suffix = env["db"], env["core"], env["suffix"]
    create_template(
        db, scope="vertical_default", vertical="manufacturing",
        template_slug=f"fv-var-{suffix}-a", display_name="A",
        inherits_from_core_id=core.id, rows=[], canvas_config={},
    )
    v2 = update_core(db, core.id, display_name=f"FV Core {suffix} v2")
    assert v2.id != core.id
    create_template(
        db, scope="vertical_default", vertical="funeral_home",
        template_slug=f"fv-var-{suffix}-b", display_name="B",
        inherits_from_core_id=v2.id, rows=[], canvas_config={},
    )
    r = client.get(f"{FTI_ROOT}/cores/{v2.id}/usage", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    slugs = {t["template_slug"] for t in body["templates"]}
    # BOTH templates count — the one against v1's id AND the one against
    # v2's (pre-fix: the exact-id filter dropped the v1-pinned template).
    assert {f"fv-var-{suffix}-a", f"fv-var-{suffix}-b"} <= slugs
    assert body["templates_count"] >= 2


# ── 2. the guided flow: creates + pins + wires + authors ────────────


def test_variation_flow_creates_pins_wires_authors(client, env, admin_headers):
    db, core, suffix = env["db"], env["core"], env["suffix"]
    task = upsert_task(
        db, vertical="manufacturing", name=f"FV Task {suffix}",
    )
    db.commit()

    r = client.post(
        f"{MOC_ROOT}/focus-variations",
        headers=admin_headers,
        json={
            "core_id": core.id,
            "display_name": f"fv-var-{suffix} scheduling",
            "verticals": VERTICALS,
            "task_ids": [task.id],
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["home_vertical"] == "manufacturing"
    assert body["wired_task_ids"] == [task.id]
    assert set(body["authored_verticals"]) == set(VERTICALS)

    # CREATED + PINNED: the r96 column earning its keep.
    tmpl = get_template_by_id(db, body["template_id"])
    assert tmpl is not None and tmpl.is_active
    assert tmpl.scope == "vertical_default"
    assert tmpl.vertical == "manufacturing"
    assert tmpl.inherits_from_core_id == core.id
    assert tmpl.inherits_from_core_version == core.version

    # JOINED: multi-vertical round-trip (home included — uniform reads).
    joins = {
        j.vertical
        for j in db.query(FocusTemplateVertical).filter(
            FocusTemplateVertical.template_slug == body["template_slug"]
        )
    }
    assert joins == set(VERTICALS)

    # WIRED: the task's focus set gained the variation.
    db.expire_all()
    t = db.get(MoCTaskCatalog, task.id)
    assert body["template_id"] in [f.focus_template_id for f in t.focuses]

    # AUTHORED: each chosen vertical's map carries the ref.
    for v in VERTICALS:
        page = (
            db.query(MoCPage)
            .filter(MoCPage.scope == "vertical_default",
                    MoCPage.vertical == v, MoCPage.is_active.is_(True))
            .first()
        )
        rows = [
            row
            for s_ in page.sections
            for row in s_.get("rows", [])
            if row.get("artifact_id") == body["template_id"]
        ]
        assert len(rows) == 1, f"ref missing (or duplicated) on {v}"
        assert rows[0]["builder"] == "focuses"


# ── 3. a name collision mints a fresh lineage ───────────────────────


def test_variation_name_collision_mints_fresh_lineage(client, env, admin_headers):
    db, core, suffix = env["db"], env["core"], env["suffix"]
    name = f"fv-var-{suffix} twice"
    r1 = client.post(
        f"{MOC_ROOT}/focus-variations", headers=admin_headers,
        json={"core_id": core.id, "display_name": name,
              "verticals": ["manufacturing"], "task_ids": []},
    )
    r2 = client.post(
        f"{MOC_ROOT}/focus-variations", headers=admin_headers,
        json={"core_id": core.id, "display_name": name,
              "verticals": ["manufacturing"], "task_ids": []},
    )
    assert r1.status_code == 201 and r2.status_code == 201
    slug1, slug2 = r1.json()["template_slug"], r2.json()["template_slug"]
    assert slug1 != slug2                       # fresh lineage, not a hijack
    first = get_template_by_id(env["db"], r1.json()["template_id"])
    db.expire_all()
    assert first is not None and first.is_active  # the original untouched
    assert first.version == 1                     # never version-bumped
