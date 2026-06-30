"""Demo artifacts 3d Part 1 — notify_via_contact_preference node (STANDALONE).

The node's OWN correctness, independent of any workflow: given a target customer
with a contact preference set, it dispatches via THAT channel. Three cases:

  1. email → email channel   (branches to the email send path)
  2. sms   → sms channel      (branches to the sms send path)
  3. phone → raises a clear "no send path" error (fails LOUD on an unsupported
     channel — never silent-fallback to email)

Case 3 is load-bearing: every real customer is 'email' today, so the raise path
is exercised ONLY here until some future funeral home sets a phone/mail
preference. This test is the sole place that fail-loud behavior is verified.

The node reads `customer.preferred_delivery_method` (reused as the
notification-preference proxy — see the handler's FIELD NOTE).
"""
from __future__ import annotations

import uuid

import pytest

from app.database import SessionLocal
from app.models.company import Company
from app.models.customer import Customer
from app.models.workflow import Workflow, WorkflowRun
from app.services.workflow_engine import _execute_notify_via_contact_preference


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


def _company_run_customer(db, *, preference: str) -> tuple[Company, WorkflowRun, Customer]:
    suffix = uuid.uuid4().hex[:6]
    co = Company(
        id=str(uuid.uuid4()), name=f"NV-{suffix}", slug=f"nv-{suffix}",
        is_active=True, vertical="manufacturing",
    )
    db.add(co)
    db.commit()
    wf = Workflow(
        id=str(uuid.uuid4()), name=f"wf-{suffix}", trigger_type="manual",
        company_id=co.id,
    )
    db.add(wf)
    db.commit()
    run = WorkflowRun(
        id=str(uuid.uuid4()), workflow_id=wf.id, company_id=co.id,
        trigger_source="test",
    )
    db.add(run)
    db.commit()
    cust = Customer(
        id=str(uuid.uuid4()), company_id=co.id, name="Hopkins FH",
        is_active=True, email="ops@hopkinsfh.example.com", phone="+15555550123",
        preferred_delivery_method=preference,
    )
    db.add(cust)
    db.commit()
    return co, run, cust


def test_email_preference_dispatches_via_email(db):
    _, run, cust = _company_run_customer(db, preference="email")
    out = _execute_notify_via_contact_preference(
        db, {"customer_id": cust.id, "subject": "Proof ready", "body": "Hi"}, run
    )
    # Branched to the EMAIL channel (a real delivery row, addressed by email).
    assert out["channel"] == "email"
    assert out["preferred_method"] == "email"
    assert out["recipient"] == "ops@hopkinsfh.example.com"
    assert out["delivery_id"]


def test_sms_preference_dispatches_via_sms(db):
    _, run, cust = _company_run_customer(db, preference="sms")
    out = _execute_notify_via_contact_preference(
        db, {"customer_id": cust.id, "body": "Your proof is ready"}, run
    )
    # Branched to the SMS channel (a DIFFERENT path — proves it keys off
    # preference, not just emails-and-claims-to-notify).
    assert out["channel"] == "sms"
    assert out["preferred_method"] == "sms"
    assert out["recipient"] == "+15555550123"


def test_phone_preference_raises_no_send_path(db):
    _, run, cust = _company_run_customer(db, preference="phone")
    with pytest.raises(ValueError, match="no send path for channel 'phone'"):
        _execute_notify_via_contact_preference(
            db, {"customer_id": cust.id, "body": "x"}, run
        )
    # Fails LOUD on an unsupported channel — never silent-fallback to email.
