"""(c) commit 2b — the three targets whose FAILURE COUNT HAD TO BE AUTHORED.

⚠️ WHY THIS FILE EXISTS AT ALL. 2b was framed as the mechanical group — the
seven targets that "already count", where migrating means wrapping a value that
was already there. Three of them counted only SUCCESSES:

    activate_scheduled_versions   `except Exception: continue`  — swallowed, unlogged
    enrich_payment_patterns       logged, never counted
    run_discount_expiry_monitor   logged, never counted

So the `failed` count in each is NEW CODE, and new code in the failure branch is
exactly where a miscount lands silently and a type check passes.

It was caught by a break test, not by inspection. Zeroing the increment in
`activate_scheduled_versions` left the whole ratchet green — none of the three
had ANY test. The break test is the only reason this file exists.

Each test injects a failure and asserts the count moved, with a marker count
proving the injection actually fired.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

canonical_tenant = make_canonical_tenant_fixture()
TENANT = TESTCO_ID


@pytest.fixture
def db_session():
    from app.database import SessionLocal
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture(autouse=True)
def _isolate(db_session):
    def purge():
        db_session.execute(text(
            "DELETE FROM agent_alerts WHERE tenant_id=:t AND alert_type='discount_expiring'"), {"t": TENANT})
        db_session.execute(text(
            "DELETE FROM invoices WHERE company_id=:t AND number LIKE 'AUTHCOUNT-%'"), {"t": TENANT})
        db_session.execute(text(
            "DELETE FROM price_list_versions WHERE tenant_id=:t AND version_number >= 90000"), {"t": TENANT})
        # ⚠️ FK ORDER: payments and profiles reference customers. Deleting the
        # customer first raises ForeignKeyViolation -- which this fixture did
        # on its first run.
        db_session.execute(text(
            "DELETE FROM customer_payments WHERE company_id=:t AND customer_id IN "
            "(SELECT id FROM customers WHERE company_id=:t AND name='Authored Count Fixture')"),
            {"t": TENANT})
        db_session.execute(text(
            "DELETE FROM entity_behavioral_profiles WHERE entity_id IN "
            "(SELECT id FROM customers WHERE company_id=:t AND name='Authored Count Fixture')"),
            {"t": TENANT})
        db_session.execute(text(
            "DELETE FROM customers WHERE company_id=:t AND name='Authored Count Fixture'"), {"t": TENANT})
        db_session.commit()
    purge(); yield; purge()


def _customer(db) -> str:
    from app.models.customer import Customer
    c = Customer(id=str(uuid.uuid4()), company_id=TENANT, name="Authored Count Fixture",
                 account_number=f"AC-{uuid.uuid4().hex[:6]}", is_active=True)
    db.add(c); db.commit(); return c.id


# ── 1. activate_scheduled_versions ───────────────────────────────────────


def test_activate_scheduled_versions_COUNTS_ITS_FAILURES(db_session, monkeypatch):
    """The bare `except Exception: continue` returned 0 on a total failure —
    indistinguishable from a day with nothing scheduled."""
    from app.models.price_list_version import PriceListVersion
    from app.services import price_increase_service as pis

    bad = PriceListVersion(id=str(uuid.uuid4()), tenant_id=TENANT, version_number=90001,
                           effective_date=date.today(), status="scheduled")
    good = PriceListVersion(id=str(uuid.uuid4()), tenant_id=TENANT, version_number=90002,
                            effective_date=date.today(), status="scheduled")
    db_session.add_all([bad, good]); db_session.commit()
    bad_id = bad.id

    seen: list[str] = []

    def fake_activate(db, tenant_id, version_id):
        # Fake rather than partial-patch: the real query is GLOBAL (no tenant
        # filter), so ambient scheduled rows from other tests would activate
        # for real and mutate shared state.
        seen.append(version_id)
        if version_id == bad_id:
            raise RuntimeError("injected activation failure")

    monkeypatch.setattr(pis, "activate_version", fake_activate)

    outcome = pis.activate_scheduled_versions(db_session)

    # Control that the injection fired — a marker count, not a green.
    assert bad_id in seen, f"the bad version was never visited: {seen}"

    assert outcome.failed == 1, outcome
    assert outcome.state == "completed_with_errors"
    # Differential: the query is global, so assert the RELATIONSHIP, not totals.
    assert outcome.succeeded == outcome.detail["versions_due"] - 1
    assert outcome.detail["versions_due"] >= 2


# ── 2. run_discount_expiry_monitor ───────────────────────────────────────


def test_discount_expiry_monitor_COUNTS_ITS_FAILURES(db_session, monkeypatch):
    from app.models.invoice import Invoice
    from app.services import proactive_agents

    # ⚠️ TWO invoices sharing one deadline, DELIBERATELY. A single-invoice
    # group takes a branch that raises TypeError on `inv.total * 0.95`
    # (Decimal * float) OUTSIDE the try — a pre-existing defect this file's
    # first draft tripped over. It is NOT fixed here: a correctness fix does
    # not ride inside a migration commit. See the commit that follows 2b.
    cust = _customer(db_session)
    deadline = date.today() + timedelta(days=1)
    for _ in range(2):
        db_session.add(Invoice(
            id=str(uuid.uuid4()), company_id=TENANT, customer_id=cust,
            number=f"AUTHCOUNT-{uuid.uuid4().hex[:6]}", status="sent",
            invoice_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=30),
            discount_deadline=deadline,
            subtotal=Decimal("100.00"), tax_amount=Decimal("0.00"), total=Decimal("100.00"),
        ))
    db_session.commit()

    import app.models.agent as agent_models
    built = {"n": 0}
    real_alert = agent_models.AgentAlert

    class _Exploding(real_alert):
        def __init__(self, *a, **k):
            built["n"] += 1
            raise RuntimeError("injected alert-construction failure")

    monkeypatch.setattr(agent_models, "AgentAlert", _Exploding)

    outcome = proactive_agents.run_discount_expiry_monitor(db_session, TENANT)

    assert built["n"] >= 1, "the alert constructor was never reached"
    assert outcome.detail["invoices_expiring"] >= 2
    assert outcome.failed >= 1
    assert outcome.succeeded == 0
    # ⚠️ The whole point: this is NOT `no_work`. Before 2b it returned
    # {"alerts_created": 0} — byte-identical to the no-invoices early return.
    assert outcome.state == "completed_with_errors"


def test_discount_expiry_NO_WORK_is_distinct_from_ALL_FAILED(db_session):
    """The counterpart. Same zero, different state — which is the distinction
    the old `{"alerts_created": 0}` could not express."""
    from app.services import proactive_agents

    outcome = proactive_agents.run_discount_expiry_monitor(db_session, TENANT)
    assert outcome.detail["invoices_expiring"] == 0
    assert outcome.state == "no_work"
    assert outcome.failed == 0


# ── 3. enrich_payment_patterns ───────────────────────────────────────────


def test_enrich_payment_patterns_COUNTS_ITS_FAILURES(db_session, monkeypatch):
    from app.models.customer_payment import CustomerPayment
    from app.services import proactive_agents

    cust_id = _customer(db_session)
    db_session.add(CustomerPayment(
        id=str(uuid.uuid4()), company_id=TENANT, customer_id=cust_id,
        payment_date=date.today() - timedelta(days=5), total_amount=Decimal("50.00"),
    ))
    db_session.commit()

    import app.models.behavioral_analytics as bam

    class _Broken:
        pass

    monkeypatch.setattr(bam, "EntityBehavioralProfile", _Broken)

    outcome = proactive_agents.enrich_payment_patterns(db_session, TENANT)

    # Control: the customer was actually reached. Without this, a zero `failed`
    # and a zero-customer run are the same green.
    assert outcome.detail["customers_scanned"] >= 1, outcome
    assert outcome.failed >= 1, outcome
    assert outcome.state == "completed_with_errors"
