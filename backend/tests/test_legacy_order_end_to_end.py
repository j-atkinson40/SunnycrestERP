"""Demo artifacts 3d Part 3 — Legacy Order END-TO-END (the JCF-1 bar).

The first time all four demo artifacts compose in one flow — that composition
working IS the demo's core narrative. Proves the WHOLE chain RUNS against real
substrate and each step produces its real artifact/effect:

  proof generated (Legacy Generation HEADLESS, 3b.1)
    → staged into triage (a real review_approval task)
    → approved (lifecycle transition)
    → emailed (send_document → a real DocumentDelivery)
    → notified (notify_via_contact_preference → a real DocumentDelivery via the
       funeral home's preferred method)

Not "the template seeded" — each handler is invoked in sequence with the Legacy
Order node configs and its real effect asserted.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.database import SessionLocal
from app.models.company import Company
from app.models.customer import Customer
from app.models.sales_order import SalesOrder
from app.models.vault_item import VaultItem
from app.models.workflow import Workflow, WorkflowRun
from app.models.document_delivery import DocumentDelivery
from app.services.tasks.service import transition_task
from app.services.workflow_engine import (
    _execute_notify_via_contact_preference,
    _execute_send_document,
    _handle_create_task,
    _handle_invoke_generation_focus,
)


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


def _legacy_order_setup(db):
    """Company + sales order (deceased) + funeral-home customer (email pref) +
    Workflow + WorkflowRun. Returns (run, sales_order_id, customer)."""
    suffix = uuid.uuid4().hex[:6]
    co = Company(
        id=str(uuid.uuid4()), name=f"LO-{suffix}", slug=f"lo-{suffix}",
        is_active=True, vertical="manufacturing",
    )
    db.add(co)
    db.commit()
    fh = Customer(
        id=str(uuid.uuid4()), company_id=co.id, name="Hopkins FH",
        is_active=True, email="ops@hopkinsfh.example.com",
        phone="+15555550199", preferred_delivery_method="email",
    )
    db.add(fh)
    db.commit()
    order = SalesOrder(
        id=str(uuid.uuid4()), company_id=co.id, number=f"SO-{suffix}",
        customer_id=fh.id, order_date=date.today(), status="confirmed",
        order_type="funeral", subtotal=Decimal("0"), tax_rate=Decimal("0"),
        tax_amount=Decimal("0"), total=Decimal("0"), deceased_name="Mary Q. Public",
    )
    db.add(order)
    db.commit()
    wf = Workflow(
        id=str(uuid.uuid4()), name=f"Legacy Order {suffix}",
        trigger_type="manual", company_id=co.id,
    )
    db.add(wf)
    db.commit()
    run = WorkflowRun(
        id=str(uuid.uuid4()), workflow_id=wf.id, company_id=co.id,
        trigger_source="test",
    )
    db.add(run)
    db.commit()
    return run, order.id, fh


def test_legacy_order_full_chain_produces_every_artifact(db):
    run, order_id, fh = _legacy_order_setup(db)

    # 1) PROOF — Legacy Generation headless (3b.1) produces real proof bytes.
    proof = _handle_invoke_generation_focus(
        db,
        {"focus_id": "legacy_proof_generation", "op_id": "generate_proof",
         "kwargs": {"sales_order_id": order_id}},
        run,
    )
    assert proof["status"] == "applied"
    assert proof["proof_size_bytes"] > 0
    assert proof["deceased_name"] == "Mary Q. Public"

    # 2) TRIAGE — a real review_approval task is staged for approval.
    # review_approval_task is cohort-routed → carries notification_permission_key.
    task_out = _handle_create_task(
        db,
        {"title": "Approve legacy proof", "task_type_key": "review_approval_task",
         "description": "Review the generated legacy proof.",
         "metadata": {"notification_permission_key": "admin"}},
        run,
    )
    assert task_out.get("vault_item_id")
    vi = db.get(VaultItem, task_out["vault_item_id"])
    assert vi is not None and vi.item_type == "task"

    # 3) APPROVE — lifecycle transition (the human triage decision):
    # created → in_progress → done (action shape has no created→done shortcut).
    transition_task(
        db, task_details_id=task_out["task_details_id"], to_state="in_progress",
    )
    td = transition_task(
        db, task_details_id=task_out["task_details_id"], to_state="done",
        resolution_outcome="approved",
    )
    db.commit()
    assert td.current_state == "done"

    # 4) EMAIL — send_document fires → a real DocumentDelivery to the print shop.
    email = _execute_send_document(
        db,
        {"channel": "email",
         "recipient": {"type": "email_address", "value": "print@shop.example.com"},
         "subject": "Approved legacy proof",
         "body": "The attached legacy proof has been approved for print."},
        run, None,
    )
    assert email["delivery_id"]
    assert email["channel"] == "email"
    assert db.get(DocumentDelivery, email["delivery_id"]) is not None

    # 5) NOTIFY — the funeral home is alerted via ITS preferred method (email).
    notify = _execute_notify_via_contact_preference(
        db,
        {"customer_id": fh.id,
         "body": "Your legacy proof has been approved and sent to the print shop."},
        run,
    )
    assert notify["delivery_id"]
    assert notify["channel"] == "email"  # branched on the FH's preference
    assert notify["recipient"] == "ops@hopkinsfh.example.com"

    # The two deliveries are distinct artifacts (print shop vs funeral home).
    assert email["delivery_id"] != notify["delivery_id"]
