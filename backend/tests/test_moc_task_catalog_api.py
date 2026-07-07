"""MoC-2b — task-catalog read endpoint (GET /api/platform/admin/moc/tasks).

Asserts the endpoint resolves the vertical's catalog over HTTP (platform-auth
gated), returning each task's workflow + focuses through the SAME resolver the
cards use — a real ref resolves to deep-linkable routing; an absent ref
resolves orphan-tolerant (workflow null / focuses []), never errors.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text as sql_text

from app.core.security import create_access_token
from app.database import SessionLocal
from app.models.platform_user import PlatformUser
from app.services.maps_of_content.task_catalog import upsert_task

VERT = "manufacturing"
URL = "/api/platform/admin/moc/tasks"


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture
def ctx():
    """A platform admin + a real workflow/focus + two catalog tasks (one with
    real refs, one with none). Cleans up after."""
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:6]
    pu = PlatformUser(
        id=str(uuid.uuid4()), email=f"moc2b-{suffix}@bridgeable.test",
        hashed_password="x", first_name="P", last_name="A",
        role="super_admin", is_active=True,
    )
    db.add(pu)
    # A real workflow_template + focus_template (reuse an existing core).
    wf_id = str(uuid.uuid4())
    db.execute(
        sql_text(
            "INSERT INTO workflow_templates (id, scope, workflow_type, "
            "display_name, vertical, is_active) VALUES (:id, 'vertical_default', "
            ":wt, 'MoC2b WF', :v, true)"
        ),
        {"id": wf_id, "wt": f"moc2b_{suffix}", "v": VERT},
    )
    # HERMETIC core (state-immunity): the old 'borrow a core from any
    # focus_templates row' broke whenever the focus tables were empty (e.g.
    # after suites whose fixtures wipe them). Create our own; delete in
    # teardown after the template that references it.
    core_id = str(uuid.uuid4())
    db.execute(
        sql_text(
            "INSERT INTO focus_cores (id, core_slug, display_name, "
            "registered_component_kind, registered_component_name) "
            "VALUES (:id, :slug, 'MoC2b Core', 'focus-core', "
            "'SchedulingKanbanCore')"
        ),
        {"id": core_id, "slug": f"moc2b-core-{suffix}"},
    )
    core = (core_id, 1)
    fc_id = str(uuid.uuid4())
    db.execute(
        sql_text(
            "INSERT INTO focus_templates (id, scope, template_slug, "
            "display_name, inherits_from_core_id, inherits_from_core_version, "
            "vertical, is_active) VALUES (:id, 'vertical_default', :slug, "
            "'MoC2b Focus', :core, :cver, :v, true)"
        ),
        {"id": fc_id, "slug": f"moc2b-focus-{suffix}", "core": core[0],
         "cver": core[1], "v": VERT},
    )
    real_name = f"MoC2b Real {suffix}"
    empty_name = f"MoC2b Empty {suffix}"
    upsert_task(
        db, vertical=VERT, name=real_name, frequency="End of Month",
        task_type="Accounting", description="real refs",
        workflow_template_id=wf_id, focus_template_ids=[fc_id],
    )
    upsert_task(
        db, vertical=VERT, name=empty_name, frequency="On demand",
        task_type="Operations", description="no refs",
        workflow_template_id=None, focus_template_ids=[],
    )
    db.commit()
    token = create_access_token({"sub": pu.id}, realm="platform")
    yield {
        "token": token, "wf_id": wf_id, "wt": f"moc2b_{suffix}", "fc_id": fc_id,
        "real_name": real_name, "empty_name": empty_name,
    }
    # teardown
    db.execute(
        sql_text("DELETE FROM moc_task_catalog WHERE vertical = :v AND name IN "
                 "(:a, :b)"),
        {"v": VERT, "a": real_name, "b": empty_name},
    )
    db.execute(sql_text("DELETE FROM focus_templates WHERE id = :id"), {"id": fc_id})
    db.execute(sql_text("DELETE FROM focus_cores WHERE id = :id"), {"id": core_id})
    db.execute(sql_text("DELETE FROM workflow_templates WHERE id = :id"), {"id": wf_id})
    db.execute(sql_text("DELETE FROM platform_users WHERE id = :id"), {"id": pu.id})
    db.commit()
    db.close()


def test_tasks_endpoint_requires_platform_auth(client):
    assert client.get(f"{URL}?vertical={VERT}").status_code in (401, 403)


def test_tasks_endpoint_resolves_catalog(client, ctx):
    resp = client.get(
        f"{URL}?vertical={VERT}",
        headers={"Authorization": f"Bearer {ctx['token']}"},
    )
    assert resp.status_code == 200, resp.text
    by_name = {t["name"]: t for t in resp.json()}

    # Real-ref task: workflow resolves to DEEP-LINKABLE routing; focus present.
    real = by_name[ctx["real_name"]]
    assert real["frequency"] == "End of Month"
    assert real["task_type"] == "Accounting"
    assert real["workflow"] is not None
    assert real["workflow"]["available"] is True
    assert real["workflow"]["routing"]["workflow_type"] == ctx["wt"]
    assert len(real["focuses"]) == 1
    assert real["focuses"][0]["routing"]["template_slug"]

    # Empty-ref task: orphan-tolerant over HTTP — workflow null, focuses [].
    empty = by_name[ctx["empty_name"]]
    assert empty["workflow"] is None
    assert empty["focuses"] == []
    assert empty["description"] == "no refs"  # descriptive cells still populate
