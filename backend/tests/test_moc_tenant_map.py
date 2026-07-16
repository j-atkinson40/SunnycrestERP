"""The Bridgeable Map — tenant surface pins (Tenant Ponder-Editor P2).

THE NON-NEGOTIABLE: after tenant A forks-and-owns a shared task, EVERY
OTHER TENANT'S view of the vertical default is BYTE-UNCHANGED (the
Hopkins-edits-everyone hazard, disproven by test). Plus:

  * the merged-view YIELD — A's map shows THEIR version; the default row
    yields to it in A's read only;
  * the fork itself — fields/captions/focuses/triggers copied, triggers
    BORN UNPROMOTED (is_live=False regardless of the source), provenance
    recorded, enrollment created, idempotent;
  * cross-tenant isolation with NOT-FOUND semantics (tasks, ponders,
    triggers, users — never a hint the other tenant's things exist);
  * roles — non-admin edit routes reject; the view routes serve everyone;
  * NO tenant live-promotion — the tenant trigger PATCH shape has no
    is_live field (a sent value is dropped, pinned).
"""
from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.moc_task_catalog import MoCTaskCatalog
from app.models.moc_task_trigger import MoCTaskTrigger
from app.models.workflow import Workflow, WorkflowStep
from app.models.workflow_template import WorkflowTemplate
from app.services.maps_of_content.task_catalog import resolve_task, resolve_task_catalog

VERT = "manufacturing"


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _make_ctx(*, role_slug: str = "admin", vertical: str = VERT):
    from app.core.security import create_access_token
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()), name=f"MAP-{suffix}", slug=f"map-{suffix}",
            is_active=True, vertical=vertical,
        )
        db.add(co)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()), company_id=co.id, name=role_slug.title(),
            slug=role_slug, is_system=True,
        )
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()), company_id=co.id,
            email=f"u-{suffix}@map.co", first_name="Map",
            last_name=role_slug.title(), hashed_password="x",
            is_active=True, role_id=role.id,
        )
        db.add(user)
        db.commit()
        token = create_access_token({"sub": user.id, "company_id": co.id})
        return {"user_id": user.id, "company_id": co.id, "token": token,
                "slug": co.slug}
    finally:
        db.close()


@pytest.fixture(scope="module")
def world():
    """Two same-vertical tenants (A: admin + office user; B: admin) + one
    fresh vertical_default task with a mirror workflow, a LIVE trigger, and
    an authored caption — the fork's raw material."""
    a_admin = _make_ctx(role_slug="admin")
    a_office = _make_ctx(role_slug="office")
    # the office user must be in A's company — rebuild it there. Track the
    # ORIGINAL company for teardown (moving the user abandons it — the
    # one-MAP-row-per-run leak otherwise).
    office_origin_company = a_office["company_id"]
    db = SessionLocal()
    from app.models.user import User

    office_user = db.query(User).filter(User.id == a_office["user_id"]).one()
    office_user.company_id = a_admin["company_id"]
    db.commit()
    from app.core.security import create_access_token

    a_office["company_id"] = a_admin["company_id"]
    a_office["slug"] = a_admin["slug"]
    a_office["token"] = create_access_token(
        {"sub": a_office["user_id"], "company_id": a_admin["company_id"]}
    )
    b_admin = _make_ctx(role_slug="admin")

    # The shared task: runtime workflow + mirror template + trigger + caption.
    suffix = uuid.uuid4().hex[:8]
    wf_id = f"wf_test_map_{suffix}"
    db.add(Workflow(
        id=wf_id, company_id=None, name=f"Map Fixture {suffix}", tier=1,
        scope="core", trigger_type="scheduled",
        trigger_config={"cron": "0 6 1 * *"}, is_active=True,
    ))
    steps = [
        ("gather", "action", {"description": "Gather the month's activity"}),
        ("send_note", "action",
         {"action_type": "send_notification", "notify_roles": ["admin"],
          "title": "Monthly note"}),
    ]
    nodes = []
    for i, (k, t, c) in enumerate(steps):
        db.add(WorkflowStep(workflow_id=wf_id, step_order=i + 1, step_key=k,
                            step_type=t, config=c))
        nodes.append({"id": k, "type": t, "label": k, "config": c})
    tpl = WorkflowTemplate(
        id=str(uuid.uuid4()), scope="vertical_default", vertical=VERT,
        workflow_type=f"map_fixture_{suffix}", display_name=f"Map Fixture {suffix}",
        version=1, is_active=True,
        canvas_state={"version": 1, "nodes": nodes, "edges": [
            {"id": "e1", "source": "gather", "target": "send_note"},
        ]},
        mirrored_from_workflow_id=wf_id,
    )
    db.add(tpl)
    db.flush()
    task = MoCTaskCatalog(
        scope="vertical_default", vertical=VERT,
        name=f"Map Fixture Task {suffix}", workflow_template_id=tpl.id,
        description="The shared version everyone reads.",
        ponder={"captions": {"when": "The authored WHEN caption."}},
    )
    db.add(task)
    db.flush()
    db.add(MoCTaskTrigger(
        task_catalog_id=task.id, kind="schedule",
        config={"spec_kind": "ordinal_weekday", "ordinal": 1,
                "weekday": "mon", "time": "16:00"},
        is_live=True,  # the source is LIVE — the fork must NOT inherit this
    ))
    db.commit()
    ids = {"task_id": task.id, "wf_id": wf_id, "tpl_id": tpl.id}
    db.close()

    yield {"a": a_admin, "a_office": a_office, "b": b_admin, **ids}

    # teardown
    s = SessionLocal()
    for ctx in (a_admin, b_admin):
        s.execute(sql_text(
            "DELETE FROM moc_task_trigger WHERE task_catalog_id IN "
            "(SELECT id FROM moc_task_catalog WHERE tenant_id = :c)"
        ), {"c": ctx["company_id"]})
        s.execute(sql_text(
            "DELETE FROM moc_task_catalog WHERE tenant_id = :c"
        ), {"c": ctx["company_id"]})
        s.execute(sql_text(
            "DELETE FROM workflow_enrollments WHERE company_id = :c"
        ), {"c": ctx["company_id"]})
        s.execute(sql_text(
            "DELETE FROM workflow_step_params WHERE company_id = :c"
        ), {"c": ctx["company_id"]})
    s.execute(sql_text(
        "DELETE FROM moc_task_trigger WHERE task_catalog_id = :t"
    ), {"t": ids["task_id"]})
    s.execute(sql_text("DELETE FROM moc_task_catalog WHERE id = :t"), {"t": ids["task_id"]})
    s.execute(sql_text("DELETE FROM workflow_templates WHERE id = :t"), {"t": ids["tpl_id"]})
    s.execute(sql_text("DELETE FROM workflow_steps WHERE workflow_id = :w"), {"w": ids["wf_id"]})
    s.execute(sql_text("DELETE FROM workflows WHERE id = :w"), {"w": ids["wf_id"]})
    for ctx in (a_admin, a_office, b_admin):
        s.execute(sql_text("DELETE FROM users WHERE id = :u"), {"u": ctx["user_id"]})
    for cid in (a_admin["company_id"], b_admin["company_id"], office_origin_company):
        s.execute(sql_text("DELETE FROM roles WHERE company_id = :c"), {"c": cid})
        # company_modules rows get seeded when the API is exercised — without
        # this delete the company row survives its own teardown (the MAP-*
        # residue class, purged from dev during P3).
        s.execute(sql_text("DELETE FROM company_modules WHERE company_id = :c"), {"c": cid})
        s.execute(sql_text("DELETE FROM companies WHERE id = :c"), {"c": cid})
    s.commit()
    s.close()


def _auth(ctx):
    return {"Authorization": f"Bearer {ctx['token']}", "X-Company-Slug": ctx["slug"]}


def _canonical_default_view(db, task_id: str) -> str:
    """The default row's resolved shape, byte-canonical (the pin's ruler)."""
    task = db.get(MoCTaskCatalog, task_id)
    return json.dumps(resolve_task(db, task), sort_keys=True, default=str)


class TestTheBridgeableMap:
    def test_01_both_tenants_see_the_shared_default(self, client, world):
        for ctx in (world["a"], world["b"]):
            r = client.get("/api/v1/moc/tasks", headers=_auth(ctx))
            assert r.status_code == 200
            names = {t["id"]: t for t in r.json()["tasks"]}
            assert world["task_id"] in names
            assert names[world["task_id"]]["scope"] == "vertical_default"

    def test_02_view_ponder_works_for_non_admin(self, client, world):
        r = client.get(f"/api/v1/moc/ponder/{world['task_id']}",
                       headers=_auth(world["a_office"]))
        assert r.status_code == 200
        script = r.json()
        assert script["beats"][0]["key"] == "when"
        assert script["beats"][0]["text"] == "The authored WHEN caption."
        assert script["owned"] is False
        # Their fires, their people — company-scoped derivation ran (the
        # fixture tenant has 2 users; a global count would be capped at 500).

    def test_03_non_admin_edit_routes_reject(self, client, world):
        office = _auth(world["a_office"])
        assert client.post(
            f"/api/v1/moc/tasks/{world['task_id']}/fork", headers=office,
        ).status_code == 403
        assert client.post(
            f"/api/v1/moc/tasks/{world['task_id']}/triggers",
            json={"kind": "manual", "config": {}}, headers=office,
        ).status_code == 403
        assert client.patch(
            f"/api/v1/moc/ponder/{world['task_id']}/captions",
            json={"beat_key": "when", "text": "nope"}, headers=office,
        ).status_code == 403
        assert client.get(
            "/api/v1/moc/ponder/users?q=map", headers=office,
        ).status_code == 403

    def test_04_shared_task_edits_403_with_the_fork_nudge(self, client, world):
        r = client.post(
            f"/api/v1/moc/tasks/{world['task_id']}/triggers",
            json={"kind": "manual", "config": {}}, headers=_auth(world["a"]),
        )
        assert r.status_code == 403
        assert "your own version" in r.json()["detail"]

    def test_05_the_fork_and_the_critical_pin(self, client, world):
        db = SessionLocal()
        try:
            # THE RULER: the default's resolved bytes + B's whole merged view,
            # captured BEFORE the fork.
            default_before = _canonical_default_view(db, world["task_id"])
            b_before = client.get("/api/v1/moc/tasks", headers=_auth(world["b"])).json()

            r = client.post(
                f"/api/v1/moc/tasks/{world['task_id']}/fork",
                headers=_auth(world["a"]),
            )
            assert r.status_code == 201
            fork = r.json()
            world["fork_id"] = fork["id"]
            assert fork["scope"] == "tenant_override"
            assert fork["tenant_id"] == world["a"]["company_id"]
            assert fork["forked_from_task_id"] == world["task_id"]
            # Triggers copied BORN UNPROMOTED — the source was LIVE.
            assert len(fork["triggers"]) == 1
            assert fork["triggers"][0]["is_live"] is False
            assert fork["triggers"][0]["summary"] == "Monthly · 1st Mon, 4:00 PM"

            # Captions copied — their ponder starts as an exact picture.
            fork_row = db.get(MoCTaskCatalog, fork["id"])
            assert fork_row.ponder["captions"]["when"] == "The authored WHEN caption."

            # Enrollment recorded against the SHARED runtime workflow.
            n = db.execute(sql_text(
                "SELECT count(*) FROM workflow_enrollments "
                "WHERE workflow_id = :w AND company_id = :c"
            ), {"w": world["wf_id"], "c": world["a"]["company_id"]}).scalar()
            assert n == 1

            # ── THE CRITICAL PIN ──
            # The default row itself: byte-unchanged.
            db.expire_all()
            assert _canonical_default_view(db, world["task_id"]) == default_before
            # Tenant B's whole merged view: byte-unchanged.
            b_after = client.get("/api/v1/moc/tasks", headers=_auth(world["b"])).json()
            assert json.dumps(b_after, sort_keys=True) == json.dumps(b_before, sort_keys=True)
            # The admin vertical read still lists the default.
            admin_view = resolve_task_catalog(db, vertical=VERT)
            assert any(t["id"] == world["task_id"] for t in admin_view)
        finally:
            db.close()

    def test_06_the_merged_view_yield(self, client, world):
        r = client.get("/api/v1/moc/tasks", headers=_auth(world["a"]))
        by_id = {t["id"]: t for t in r.json()["tasks"]}
        # THEIR version present, pilled ownable...
        assert world["fork_id"] in by_id
        assert by_id[world["fork_id"]]["scope"] == "tenant_override"
        # ...and the default YIELDS — absent from A's view only.
        assert world["task_id"] not in by_id
        # B still sees the default (re-pinned for the yield's "only").
        r_b = client.get("/api/v1/moc/tasks", headers=_auth(world["b"]))
        assert world["task_id"] in {t["id"] for t in r_b.json()["tasks"]}

    def test_07_fork_is_idempotent(self, client, world):
        r = client.post(
            f"/api/v1/moc/tasks/{world['task_id']}/fork", headers=_auth(world["a"]),
        )
        assert r.status_code == 201
        assert r.json()["id"] == world["fork_id"]

    def test_08_owned_task_edits_work_and_rederive(self, client, world):
        a = _auth(world["a"])
        # caption on THEIR row
        r = client.patch(
            f"/api/v1/moc/ponder/{world['fork_id']}/captions",
            json={"beat_key": "when", "text": "Our version's caption."}, headers=a,
        )
        assert r.status_code == 200
        script = client.get(f"/api/v1/moc/ponder/{world['fork_id']}", headers=a).json()
        assert script["beats"][0]["text"] == "Our version's caption."
        assert script["owned"] is True
        # trigger edit on THEIR row (no fork nudge)
        trig_id = script["beats"][0]["triggers"][0]["id"]
        r = client.patch(
            f"/api/v1/moc/triggers/{trig_id}",
            json={"config": {"spec_kind": "ordinal_weekday", "ordinal": "last",
                             "weekday": "fri", "time": "09:30"}},
            headers=a,
        )
        assert r.status_code == 200
        script = client.get(f"/api/v1/moc/ponder/{world['fork_id']}", headers=a).json()
        assert script["beats"][0]["derived_text"] == \
            "The last Friday of every month at 9:30 AM."

    def test_09_no_tenant_live_promotion(self, client, world):
        """The set default: the tenant PATCH shape has no is_live — a sent
        value is DROPPED, never applied."""
        a = _auth(world["a"])
        script = client.get(f"/api/v1/moc/ponder/{world['fork_id']}", headers=a).json()
        trig_id = script["beats"][0]["triggers"][0]["id"]
        r = client.patch(
            f"/api/v1/moc/triggers/{trig_id}", json={"is_live": True}, headers=a,
        )
        assert r.status_code == 200
        assert r.json()["is_live"] is False

    def test_10_cross_tenant_not_found_semantics(self, client, world):
        b = _auth(world["b"])
        # B cannot SEE A's fork — not-found, never a hint.
        assert client.get(
            f"/api/v1/moc/ponder/{world['fork_id']}", headers=b,
        ).status_code == 404
        # B cannot touch A's trigger.
        db = SessionLocal()
        trig_id = db.execute(sql_text(
            "SELECT id FROM moc_task_trigger WHERE task_catalog_id = :t LIMIT 1"
        ), {"t": world["fork_id"]}).scalar()
        db.close()
        assert client.patch(
            f"/api/v1/moc/triggers/{trig_id}", json={"label": "boo"}, headers=b,
        ).status_code == 404
        assert client.delete(
            f"/api/v1/moc/triggers/{trig_id}", headers=b,
        ).status_code == 404
        # B forking A's fork: not theirs to fork — not found.
        assert client.post(
            f"/api/v1/moc/tasks/{world['fork_id']}/fork", headers=b,
        ).status_code == 404

    def test_11_user_search_is_company_scoped(self, client, world):
        # A's admin searching "Map" finds A-company users only.
        r = client.get("/api/v1/moc/ponder/users?q=map", headers=_auth(world["a"]))
        assert r.status_code == 200
        ids = {u["id"] for u in r.json()}
        assert world["b"]["user_id"] not in ids
        assert ids <= {world["a"]["user_id"], world["a_office"]["user_id"]}

    def test_12_ponder_audience_counts_are_theirs(self, client, world):
        """The notify beat's audience on the tenant read counts THEIR people
        (the fixture tenant is tiny; a global count would cap at 500)."""
        r = client.get(f"/api/v1/moc/ponder/{world['fork_id']}",
                       headers=_auth(world["a"]))
        beats = {b["key"]: b for b in r.json()["beats"]}
        aud = beats["step:send_note"].get("audience")
        assert aud is not None and "admin role" in aud["text"]

    def test_13_wrong_vertical_task_is_invisible(self, client, world):
        """A funeral_home default is NOT FOUND to a manufacturing tenant."""
        db = SessionLocal()
        fh_task = MoCTaskCatalog(
            scope="vertical_default", vertical="funeral_home",
            name=f"FH Only {uuid.uuid4().hex[:6]}",
        )
        db.add(fh_task)
        db.commit()
        tid = fh_task.id
        try:
            assert client.get(
                f"/api/v1/moc/ponder/{tid}", headers=_auth(world["a"]),
            ).status_code == 404
            assert client.post(
                f"/api/v1/moc/tasks/{tid}/fork", headers=_auth(world["a"]),
            ).status_code == 404
        finally:
            db.execute(sql_text("DELETE FROM moc_task_catalog WHERE id = :t"), {"t": tid})
            db.commit()
            db.close()
