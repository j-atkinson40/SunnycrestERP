"""Demo artifacts 3d/3a.1 — Legacy Order END-TO-END (the corrected loop).

3d's test asserted "a task was created" — but create_task staged into a
lifecycle state NO triage queue reads, so the proof never surfaced for
approval. 3a.1 repaired the staging (create_task → invoke_review_focus) so the
proof becomes a WorkflowReviewItem in workflow_review_triage. THIS test asserts
the RIGHT thing — the full demo spine, run through the real engine:

  Legacy Order runs → proof generated (3b.1 headless)
    → PAUSES on a WorkflowReviewItem that SURFACES in workflow_review_triage
       (the gap 3d missed — assert it actually appears)
    → approve via the real triage decision (commit_decision)
    → the run ADVANCES → send_document fires (print shop)
        + notify_via_contact_preference fires (funeral home, its preference)

Driven through start_run / advance_run over real WorkflowStep rows — not a
handler sequence — so the pause + resume are the engine's, not the test's.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.database import SessionLocal
from app.models.company import Company
from app.models.customer import Customer
from app.models.document_delivery import DocumentDelivery
from app.models.role import Role
from app.models.sales_order import SalesOrder
from app.models.user import User
from app.models.workflow import Workflow, WorkflowStep
from app.services.triage.engine import _dq_workflow_review
from app.services.workflow_engine import start_run
from app.services.workflows.workflow_review_adapter import commit_decision


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


def _setup(db):
    """Company + FH customer (email pref) + sales order (deceased) + approver
    user. Returns (company_id, order_id, fh, user)."""
    sfx = uuid.uuid4().hex[:6]
    co = Company(
        id=str(uuid.uuid4()), name=f"LO-{sfx}", slug=f"lo-{sfx}",
        is_active=True, vertical="manufacturing",
    )
    db.add(co)
    db.commit()
    role = Role(id=str(uuid.uuid4()), company_id=co.id, name="Admin",
                slug="admin", is_system=True)
    db.add(role)
    db.commit()
    user = User(
        id=str(uuid.uuid4()), email=f"approver-{sfx}@x.test", hashed_password="x",
        first_name="A", last_name="B", company_id=co.id, role_id=role.id,
        is_active=True,
    )
    db.add(user)
    fh = Customer(
        id=str(uuid.uuid4()), company_id=co.id, name="Hopkins FH", is_active=True,
        email="ops@hopkinsfh.example.com", phone="+15555550199",
        preferred_delivery_method="email",
    )
    db.add(fh)
    db.commit()
    order = SalesOrder(
        id=str(uuid.uuid4()), company_id=co.id, number=f"SO-{sfx}",
        customer_id=fh.id, order_date=date.today(), status="confirmed",
        order_type="funeral", subtotal=Decimal("0"), tax_rate=Decimal("0"),
        tax_amount=Decimal("0"), total=Decimal("0"), deceased_name="Mary Q. Public",
    )
    db.add(order)
    db.commit()
    return co.id, order.id, fh, user


def _build_workflow(db, *, company_id, order_id, fh_id) -> str:
    """The repaired Legacy Order as real WorkflowStep rows: gen → review (pause)
    → send_document → notify. Literal ids (no variable resolution needed)."""
    wf = Workflow(
        id=str(uuid.uuid4()), name="Legacy Order E2E", company_id=company_id,
        vertical="manufacturing", tier=4, scope="tenant", is_active=True,
        trigger_type="manual", trigger_config={},
    )
    db.add(wf)
    db.commit()
    steps = [
        (1, "gen", "action", {
            "action_type": "invoke_generation_focus",
            "focus_id": "legacy_proof_generation", "op_id": "generate_proof",
            "kwargs": {"sales_order_id": order_id}}),
        (2, "review", "action", {
            "action_type": "invoke_review_focus",
            "review_focus_id": "legacy_proof_review",
            "input_data": {"sales_order_id": order_id,
                           "deceased_name": "Mary Q. Public"}}),
        (3, "email", "send_document", {
            "channel": "email",
            "recipient": {"type": "email_address",
                          "value": "print@shop.example.com"},
            "subject": "Approved legacy proof", "body": "approved for print"}),
        (4, "notify", "action", {
            "action_type": "notify_via_contact_preference",
            "customer_id": fh_id,
            "body": "Your legacy proof has been approved and sent to print."}),
    ]
    for order_n, key, st, cfg in steps:
        db.add(WorkflowStep(
            id=str(uuid.uuid4()), workflow_id=wf.id, step_order=order_n,
            step_key=key, step_type=st, config=cfg))
    db.commit()
    return wf.id


def test_legacy_order_loop_proof_surfaces_then_approve_advances(db):
    company_id, order_id, fh, user = _setup(db)
    wf_id = _build_workflow(db, company_id=company_id, order_id=order_id, fh_id=fh.id)

    # Run: gen produces the proof, then the run PAUSES on the review step.
    run = start_run(
        db, workflow_id=wf_id, company_id=company_id,
        triggered_by_user_id=user.id, trigger_source="test",
    )
    assert run.status == "awaiting_approval"  # paused on invoke_review_focus

    # THE GAP 3d MISSED: the proof SURFACES in workflow_review_triage.
    items = _dq_workflow_review(db, user)
    mine = [i for i in items if i["run_id"] == run.id]
    assert len(mine) == 1, "proof did not surface in workflow_review_triage"
    review_item_id = mine[0]["id"]
    assert mine[0]["input_data"]["deceased_name"] == "Mary Q. Public"

    # APPROVE via the real triage decision → the run ADVANCES.
    commit_decision(
        db, item_id=review_item_id, decision="approve", user_id=user.id,
        company_id=company_id,
    )
    db.refresh(run)
    assert run.status in ("completed", "complete"), run.status

    # send_document (print shop) + notify (FH via its email preference) fired.
    deliveries = (
        db.query(DocumentDelivery)
        .filter(DocumentDelivery.caller_workflow_run_id == run.id)
        .all()
    )
    assert len(deliveries) >= 2, f"expected print-shop + FH deliveries, got {len(deliveries)}"
    recipients = {d.recipient_value for d in deliveries}
    assert "print@shop.example.com" in recipients
    assert "ops@hopkinsfh.example.com" in recipients  # the FH, via preference
