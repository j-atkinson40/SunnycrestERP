"""MoC Task Editing 2a — the editable vocabulary + full-CRUD write path (headless).

Assembly tests (the whole write path BEFORE any UI, the JCF-1 discipline): create
→ resolver picks it up; patch sets frequency/type/description + wires workflow + 2
focuses; add a vocabulary value → a task can use it; a frequency NOT in the
vocabulary is REJECTED (the referential guard); delete → gone, no orphan join
rows; vocabulary seed idempotent.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.services.maps_of_content import vocabulary
from app.services.maps_of_content.task_catalog import (
    TaskValidationError,
    create_task,
    delete_task,
    get_task,
    patch_task,
    resolve_task_catalog,
)

VERT = "manufacturing"


@pytest.fixture
def db():
    s = SessionLocal()
    s._created = {"tasks": [], "focuses": [], "workflows": [], "cores": []}
    yield s
    s.rollback()
    for tid in s._created["tasks"]:
        s.execute(sql_text("DELETE FROM moc_task_catalog WHERE id = :id"), {"id": tid})
    for fid in s._created["focuses"]:
        s.execute(sql_text("DELETE FROM focus_templates WHERE id = :id"), {"id": fid})
    for wid in s._created["workflows"]:
        s.execute(sql_text("DELETE FROM workflow_templates WHERE id = :id"), {"id": wid})
    for cid in s._created["cores"]:
        s.execute(sql_text("DELETE FROM focus_cores WHERE id = :id"), {"id": cid})
    s.execute(sql_text("DELETE FROM moc_task_vocabulary WHERE value = 'Weekly'"))
    s.commit()
    s.close()


def _refs(db) -> tuple[str, list[str]]:
    """Seed the vocabulary + return (a workflow_template id, two focus_template
    ids) — all created here (hermetic; doesn't depend on other seeds' rows)."""
    vocabulary.seed_minimal(db)
    wf = str(uuid.uuid4())
    db.execute(
        sql_text(
            "INSERT INTO workflow_templates (id, scope, vertical, workflow_type, "
            "display_name, canvas_state, version, is_active, created_at, updated_at) "
            "VALUES (:id, 'platform_default', NULL, :wt, 'Test WF', "
            "CAST(:cs AS jsonb), 1, true, now(), now())"
        ),
        {"id": wf, "wt": f"test_wf_{uuid.uuid4().hex[:8]}",
         "cs": '{"version":1,"nodes":[],"edges":[]}'},
    )
    db._created["workflows"].append(wf)
    # HERMETIC core (state-immunity): the old `SELECT ... FROM focus_templates
    # LIMIT 1` piggybacked on other seeds' rows — running after a suite whose
    # fixtures wipe the focus tables left core=None and every test here
    # TypeError'd. Create our own Tier 1 core instead.
    from app.services.focus_template_inheritance import create_core

    own_core = create_core(
        db,
        core_slug=f"task-edit-core-{uuid.uuid4().hex[:8]}",
        display_name="Task Editing Core",
        registered_component_kind="focus-core",
        registered_component_name="SchedulingKanbanCore",
        default_starting_column=0,
        default_column_span=12,
        default_row_index=0,
        min_column_span=8,
        max_column_span=12,
        canvas_config={},
    )
    db._created["cores"].append(own_core.id)
    core = (own_core.id, own_core.version)
    focs: list[str] = []
    for i in range(2):
        fid = str(uuid.uuid4())
        db.execute(
            sql_text(
                "INSERT INTO focus_templates (id, scope, template_slug, display_name, "
                "inherits_from_core_id, inherits_from_core_version, is_active, "
                "created_at, updated_at) VALUES (:id, 'platform_default', :slug, :dn, "
                ":c, :cv, true, now(), now())"
            ),
            {"id": fid, "slug": f"test-foc-{uuid.uuid4().hex[:8]}",
             "dn": f"Test Focus {i}", "c": core[0], "cv": core[1]},
        )
        focs.append(fid)
        db._created["focuses"].append(fid)
    db.commit()
    return wf, focs


def test_create_then_resolver_picks_it_up(db):
    wf, _ = _refs(db)
    name = f"Test Task {uuid.uuid4().hex[:6]}"
    task = create_task(db, vertical=VERT, name=name, workflow_template_id=wf)
    db.commit()
    db._created["tasks"].append(task.id)

    by = {t["name"]: t for t in resolve_task_catalog(db, vertical=VERT)}
    assert name in by
    assert by[name]["workflow"] and by[name]["workflow"]["available"]


def test_patch_sets_fields_and_wires_relationships(db):
    wf, focs = _refs(db)
    name = f"Test Task {uuid.uuid4().hex[:6]}"
    task = create_task(db, vertical=VERT, name=name)
    db.commit()
    db._created["tasks"].append(task.id)

    patch_task(
        db, task_id=task.id, frequency="End of Month", task_type="Accounting",
        description="month-end billing", workflow_template_id=wf,
        focus_template_ids=focs,
    )
    db.commit()

    t = get_task(db, task_id=task.id)
    assert t.frequency == "End of Month"
    assert t.task_type == "Accounting"
    assert t.description == "month-end billing"
    assert t.workflow_template_id == wf
    assert [f.focus_template_id for f in t.focuses] == focs


def test_add_vocabulary_value_then_a_task_can_use_it(db):
    _refs(db)
    assert not vocabulary.value_exists(db, kind="frequency", value="Weekly", vertical=VERT)
    vocabulary.add_value(db, kind="frequency", value="Weekly", scope="platform_default")
    db.commit()
    assert vocabulary.value_exists(db, kind="frequency", value="Weekly", vertical=VERT)

    name = f"Test Task {uuid.uuid4().hex[:6]}"
    task = create_task(db, vertical=VERT, name=name, frequency="Weekly")
    db.commit()
    db._created["tasks"].append(task.id)
    assert task.frequency == "Weekly"


def test_bad_frequency_is_rejected(db):
    _refs(db)
    with pytest.raises(TaskValidationError, match="not in the vocabulary"):
        create_task(db, vertical=VERT, name=f"X {uuid.uuid4().hex[:6]}",
                    frequency="Nonexistent Frequency")


def test_delete_removes_task_and_join_rows(db):
    wf, focs = _refs(db)
    name = f"Test Task {uuid.uuid4().hex[:6]}"
    task = create_task(db, vertical=VERT, name=name, workflow_template_id=wf,
                       focus_template_ids=focs)
    db.commit()
    tid = task.id

    join_before = db.execute(
        sql_text("SELECT COUNT(*) FROM moc_task_catalog_focuses WHERE task_catalog_id = :id"),
        {"id": tid},
    ).scalar()
    assert join_before == 2

    assert delete_task(db, task_id=tid) is True
    db.commit()

    assert get_task(db, task_id=tid) is None
    join_after = db.execute(
        sql_text("SELECT COUNT(*) FROM moc_task_catalog_focuses WHERE task_catalog_id = :id"),
        {"id": tid},
    ).scalar()
    assert join_after == 0  # no orphan join rows


def test_vocabulary_seed_idempotent(db):
    vocabulary.seed_minimal(db)
    vocabulary.seed_minimal(db)
    n = db.execute(
        sql_text("SELECT COUNT(*) FROM moc_task_vocabulary WHERE scope = 'platform_default'")
    ).scalar()
    assert n == 4  # no dups


# ── API smoke (the HTTP layer + auth + error mapping) ──────────────────


@pytest.fixture
def api():
    """TestClient + a platform admin token + vocab seeded + a workflow ref."""
    import uuid as _uuid

    from fastapi.testclient import TestClient

    from app.core.security import create_access_token
    from app.main import app
    from app.models.platform_user import PlatformUser

    s = SessionLocal()
    vocabulary.seed_minimal(s)
    suffix = _uuid.uuid4().hex[:6]
    pu = PlatformUser(
        id=str(_uuid.uuid4()), email=f"taskedit-{suffix}@bridgeable.test",
        hashed_password="x", first_name="P", last_name="A",
        role="super_admin", is_active=True,
    )
    s.add(pu)
    s.commit()
    wf = s.execute(sql_text("SELECT id FROM workflow_templates LIMIT 1")).scalar()
    token = create_access_token({"sub": pu.id}, realm="platform")
    created_task_ids: list[str] = []
    yield {
        "client": TestClient(app),
        "h": {"Authorization": f"Bearer {token}"},
        "wf": wf, "tasks": created_task_ids,
    }
    for tid in created_task_ids:
        s.execute(sql_text("DELETE FROM moc_task_catalog WHERE id = :id"), {"id": tid})
    s.execute(sql_text("DELETE FROM moc_task_vocabulary WHERE value = 'Quarterly'"))
    s.execute(sql_text("DELETE FROM platform_users WHERE id = :id"), {"id": pu.id})
    s.commit()
    s.close()


def test_api_requires_platform_auth(api):
    assert api["client"].post("/api/platform/admin/moc/tasks", json={}).status_code in (401, 403)


def test_api_full_crud_roundtrip(api):
    c, h = api["client"], api["h"]
    # GET vocabulary
    vocab_resp = c.get("/api/platform/admin/moc/vocabulary?kind=frequency", headers=h)
    assert vocab_resp.status_code == 200
    assert "End of Month" in [v["value"] for v in vocab_resp.json()]

    # CREATE
    name = f"API Task {uuid.uuid4().hex[:6]}"
    create = c.post(
        "/api/platform/admin/moc/tasks",
        json={"vertical": VERT, "name": name, "workflow_template_id": api["wf"]},
        headers=h,
    )
    assert create.status_code == 201, create.text
    tid = create.json()["id"]
    api["tasks"].append(tid)

    # PATCH a valid frequency
    patch = c.patch(
        f"/api/platform/admin/moc/tasks/{tid}",
        json={"frequency": "End of Month", "task_type": "Accounting"},
        headers=h,
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["frequency"] == "End of Month"

    # DELETE
    assert c.delete(f"/api/platform/admin/moc/tasks/{tid}", headers=h).status_code == 200
    api["tasks"].remove(tid)


def test_api_bad_frequency_400(api):
    c, h = api["client"], api["h"]
    resp = c.post(
        "/api/platform/admin/moc/tasks",
        json={"vertical": VERT, "name": f"Bad {uuid.uuid4().hex[:6]}",
              "frequency": "Totally Made Up"},
        headers=h,
    )
    assert resp.status_code == 400
    assert "vocabulary" in resp.json()["detail"]


def test_api_add_vocabulary_value(api):
    c, h = api["client"], api["h"]
    resp = c.post(
        "/api/platform/admin/moc/vocabulary",
        json={"kind": "frequency", "value": "Quarterly"},
        headers=h,
    )
    assert resp.status_code == 201
    # Now usable
    assert vocabulary.value_exists(SessionLocal(), kind="frequency", value="Quarterly", vertical=VERT)
