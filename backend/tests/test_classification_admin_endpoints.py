"""Phase R-6.1a — Admin email-classification endpoint coverage."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, require_admin
from app.api.routes.admin_email_classification import router
from app.database import get_db
from app.models.email_classification import (
    TenantWorkflowEmailRule,
    TenantWorkflowEmailCategory,
    WorkflowEmailClassification,
)
from app.services.classification.audit import write_classification_audit
from tests._classification_fixtures import (  # noqa: F401
    admin_user,
    db,
    make_category,
    make_email_account,
    make_inbound_email,
    make_rule,
    make_workflow,
    tenant_pair,
)


def _make_client(test_db, current_user):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/email-classification")

    def override_db():
        yield test_db

    def override_current_user():
        return current_user

    def override_require_admin():
        return current_user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[require_admin] = override_require_admin
    return TestClient(app)


# ── Rules CRUD ──────────────────────────────────────────────────────


def test_list_rules_empty(db, admin_user):
    client = _make_client(db, admin_user)
    r = client.get("/api/v1/email-classification/rules")
    assert r.status_code == 200
    assert r.json() == {"rules": []}


def test_create_rule(db, admin_user, tenant_pair):
    a, _ = tenant_pair
    wf = make_workflow(db, a)
    client = _make_client(db, admin_user)
    body = {
        "name": "Disinterment intake",
        "priority": 0,
        "match_conditions": {"subject_contains_any": ["disinterment"]},
        "fire_action": {"workflow_id": wf.id},
    }
    r = client.post("/api/v1/email-classification/rules", json=body)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["name"] == "Disinterment intake"
    assert data["priority"] == 0
    assert data["fire_action"]["workflow_id"] == wf.id


def test_create_rule_with_unknown_workflow_400(db, admin_user):
    client = _make_client(db, admin_user)
    body = {
        "name": "Bad rule",
        "priority": 0,
        "match_conditions": {},
        "fire_action": {"workflow_id": "00000000-0000-0000-0000-000000000000"},
    }
    r = client.post("/api/v1/email-classification/rules", json=body)
    assert r.status_code == 400


def test_update_rule(db, admin_user, tenant_pair):
    a, _ = tenant_pair
    rule = make_rule(db, a, priority=0, name="Old name", match_conditions={})
    client = _make_client(db, admin_user)
    r = client.patch(
        f"/api/v1/email-classification/rules/{rule.id}",
        json={"name": "New name"},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "New name"


def test_update_rule_cross_tenant_404(db, admin_user, tenant_pair):
    _, b = tenant_pair
    rule = make_rule(db, b, priority=0, match_conditions={})
    client = _make_client(db, admin_user)
    r = client.patch(
        f"/api/v1/email-classification/rules/{rule.id}",
        json={"name": "X"},
    )
    assert r.status_code == 404


def test_delete_rule_soft_deletes(db, admin_user, tenant_pair):
    a, _ = tenant_pair
    rule = make_rule(db, a, priority=0, match_conditions={})
    client = _make_client(db, admin_user)
    r = client.delete(f"/api/v1/email-classification/rules/{rule.id}")
    assert r.status_code == 200
    db.refresh(rule)
    assert rule.is_active is False


def test_reorder_rules(db, admin_user, tenant_pair):
    a, _ = tenant_pair
    r1 = make_rule(db, a, priority=0, name="A", match_conditions={})
    r2 = make_rule(db, a, priority=1, name="B", match_conditions={})
    client = _make_client(db, admin_user)
    r = client.post(
        "/api/v1/email-classification/rules/reorder",
        json={"rule_ids": [r2.id, r1.id]},
    )
    assert r.status_code == 200
    db.refresh(r1)
    db.refresh(r2)
    assert r2.priority == 0
    assert r1.priority == 1


# ── Taxonomy CRUD ───────────────────────────────────────────────────


def test_get_taxonomy_empty(db, admin_user):
    client = _make_client(db, admin_user)
    r = client.get("/api/v1/email-classification/taxonomy")
    assert r.status_code == 200
    assert r.json() == {"categories": []}


def test_create_category(db, admin_user, tenant_pair):
    a, _ = tenant_pair
    wf = make_workflow(db, a)
    client = _make_client(db, admin_user)
    body = {
        "label": "Pricing inquiries",
        "description": "Customers asking pricing",
        "mapped_workflow_id": wf.id,
    }
    r = client.post(
        "/api/v1/email-classification/taxonomy/nodes", json=body
    )
    assert r.status_code == 201, r.text
    assert r.json()["label"] == "Pricing inquiries"


def test_update_category(db, admin_user, tenant_pair):
    a, _ = tenant_pair
    cat = make_category(db, a, label="Old")
    client = _make_client(db, admin_user)
    r = client.patch(
        f"/api/v1/email-classification/taxonomy/nodes/{cat.id}",
        json={"label": "New"},
    )
    assert r.status_code == 200
    assert r.json()["label"] == "New"


def test_delete_category_cascades_descendants(
    db, admin_user, tenant_pair
):
    a, _ = tenant_pair
    parent = make_category(db, a, label="Parent")
    child = make_category(db, a, label="Child", parent_id=parent.id)
    client = _make_client(db, admin_user)
    r = client.delete(
        f"/api/v1/email-classification/taxonomy/nodes/{parent.id}"
    )
    assert r.status_code == 200
    db.refresh(parent)
    db.refresh(child)
    assert parent.is_active is False
    assert child.is_active is False


# ── Tier 3 enrollment ───────────────────────────────────────────────


def test_tier3_enrollment_toggle(db, admin_user, tenant_pair):
    a, _ = tenant_pair
    wf = make_workflow(db, a)
    client = _make_client(db, admin_user)
    r = client.patch(
        f"/api/v1/email-classification/workflows/{wf.id}/tier3-enrollment",
        json={"enrolled": True},
    )
    assert r.status_code == 200
    assert r.json()["tier3_enrolled"] is True
    db.refresh(wf)
    assert wf.tier3_enrolled is True


def test_tier3_enrollment_cross_tenant_404(db, admin_user, tenant_pair):
    _, b = tenant_pair
    wf = make_workflow(db, b)
    client = _make_client(db, admin_user)
    r = client.patch(
        f"/api/v1/email-classification/workflows/{wf.id}/tier3-enrollment",
        json={"enrolled": True},
    )
    assert r.status_code == 404


# ── Classifications list / get / replay ─────────────────────────────


def test_list_classifications(db, admin_user, tenant_pair):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    msg = make_inbound_email(db, tenant=a, account=acct)
    write_classification_audit(
        db, tenant_id=a.id, email_message_id=msg.id, tier=None
    )
    db.commit()
    client = _make_client(db, admin_user)
    r = client.get("/api/v1/email-classification/classifications")
    assert r.status_code == 200
    rows = r.json()["classifications"]
    assert len(rows) == 1


def test_get_classification_cross_tenant_404(
    db, admin_user, tenant_pair
):
    _, b = tenant_pair
    acct_b = make_email_account(db, b)
    msg_b = make_inbound_email(db, tenant=b, account=acct_b)
    other = write_classification_audit(
        db, tenant_id=b.id, email_message_id=msg_b.id, tier=None
    )
    db.commit()
    client = _make_client(db, admin_user)
    r = client.get(
        f"/api/v1/email-classification/classifications/{other.id}"
    )
    assert r.status_code == 404


def test_replay_classification(db, admin_user, tenant_pair, monkeypatch):
    a, _ = tenant_pair
    acct = make_email_account(db, a)
    msg = make_inbound_email(db, tenant=a, account=acct)
    # Initial classification.
    write_classification_audit(
        db, tenant_id=a.id, email_message_id=msg.id, tier=None
    )
    db.commit()
    client = _make_client(db, admin_user)
    r = client.post(
        f"/api/v1/email-classification/messages/{msg.id}/replay-classification"
    )
    assert r.status_code == 200, r.text
    rows = (
        db.query(WorkflowEmailClassification)
        .filter(WorkflowEmailClassification.email_message_id == msg.id)
        .all()
    )
    assert len(rows) == 2


def test_replay_cross_tenant_404(db, admin_user, tenant_pair):
    _, b = tenant_pair
    acct_b = make_email_account(db, b)
    msg_b = make_inbound_email(db, tenant=b, account=acct_b)
    client = _make_client(db, admin_user)
    r = client.post(
        f"/api/v1/email-classification/messages/{msg_b.id}/replay-classification"
    )
    assert r.status_code == 404


# ── Manual route to workflow ────────────────────────────────────────


def test_manual_route_to_workflow(db, admin_user, tenant_pair, monkeypatch):
    from app.models.workflow import WorkflowRun

    a, _ = tenant_pair
    acct = make_email_account(db, a)
    msg = make_inbound_email(db, tenant=a, account=acct)
    cls = write_classification_audit(
        db, tenant_id=a.id, email_message_id=msg.id, tier=None
    )
    db.commit()
    wf = make_workflow(db, a)

    def stub_start(db_, **kw):
        run = WorkflowRun(
            workflow_id=kw["workflow_id"],
            company_id=kw["company_id"],
            triggered_by_user_id=None,
            trigger_source=kw["trigger_source"],
            trigger_context=kw["trigger_context"],
            status="running",
            input_data={},
            output_data={},
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    monkeypatch.setattr(
        "app.services.classification.dispatch.workflow_engine.start_run",
        stub_start,
    )

    client = _make_client(db, admin_user)
    r = client.post(
        f"/api/v1/email-classification/classifications/{cls.id}/route-to-workflow",
        json={"workflow_id": wf.id, "decision_notes": "Manual route"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["selected_workflow_id"] == wf.id
    assert body["workflow_run_id"] is not None
