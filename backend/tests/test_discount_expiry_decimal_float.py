"""`run_discount_expiry_monitor` — the Decimal*float crash and the falsy zero.

⚠️ FOUND BY RUNNING THE REPAIRED PATH, NOT BY READING IT. (c) commit 2b wrote a
test for the job's newly-authored failure count; that test seeded ONE invoice,
took the single-invoice branch, and the job raised TypeError before reaching
anything the test was about.

The expression `float(inv.discounted_total or inv.total * 0.95)` carried two
defects at once, and the second would never have raised:

  1. `inv.total * 0.95` is Decimal * float -> TypeError. It sits OUTSIDE the
     function's only try (which spans the alert construction), so it does not
     degrade the run -- it ENDS it. Every tenant with exactly one invoice in a
     discount-deadline group and a NULL discounted_total lost the whole job.

  2. `or` is falsy-testing a NUMERIC column. A real discounted_total of 0.00
     was treated as absent and silently replaced with 95% of the total. No
     exception, no log -- just a wrong number in a customer-facing message.

Money math is hand-proven here, per CLAUDE.md: total 100.00, so
100.00 * 0.95 = 95.00 and 100.00 * 0.05 = 5.00. Both literals are stated, not
computed from the code under test.
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
            "DELETE FROM invoices WHERE company_id=:t AND number LIKE 'DISCFIX-%'"), {"t": TENANT})
        db_session.execute(text(
            "DELETE FROM customers WHERE company_id=:t AND name='Discount Fix Fixture'"), {"t": TENANT})
        db_session.commit()
    purge(); yield; purge()


def _one_invoice(db, *, discounted_total):
    """ONE invoice on its own deadline — the single-invoice branch, which is
    the branch that crashed. A two-invoice group takes the other path."""
    from app.models.customer import Customer
    from app.models.invoice import Invoice

    c = Customer(id=str(uuid.uuid4()), company_id=TENANT, name="Discount Fix Fixture",
                 account_number=f"DF-{uuid.uuid4().hex[:6]}", is_active=True)
    db.add(c); db.commit()
    inv = Invoice(
        id=str(uuid.uuid4()), company_id=TENANT, customer_id=c.id,
        number=f"DISCFIX-{uuid.uuid4().hex[:6]}", status="sent",
        invoice_date=datetime.now(timezone.utc),
        due_date=datetime.now(timezone.utc) + timedelta(days=30),
        discount_deadline=date.today() + timedelta(days=2),
        subtotal=Decimal("100.00"), tax_amount=Decimal("0.00"), total=Decimal("100.00"),
        discounted_total=discounted_total,
    )
    db.add(inv); db.commit()
    return inv


def _alert_message(db):
    from app.models.agent import AgentAlert
    rows = (db.query(AgentAlert)
            .filter(AgentAlert.tenant_id == TENANT,
                    AgentAlert.alert_type == "discount_expiring").all())
    assert len(rows) == 1, f"expected exactly one alert, got {len(rows)}"
    return rows[0].message


def test_a_NULL_discounted_total_does_not_kill_the_job(db_session):
    """THE CRASH. Pre-fix this raised TypeError out of the whole function."""
    from app.services.proactive_agents import run_discount_expiry_monitor

    _one_invoice(db_session, discounted_total=None)

    outcome = run_discount_expiry_monitor(db_session, TENANT)

    assert outcome.state == "ok", outcome
    assert outcome.succeeded == 1
    assert outcome.failed == 0
    # 100.00 * 0.95 = 95.00 (hand-computed, stated as a literal)
    assert "$95.00" in _alert_message(db_session), _alert_message(db_session)


def test_a_ZERO_discounted_total_is_HONOURED_not_treated_as_absent(db_session):
    """THE SILENT ONE. `or` read 0.00 as missing and substituted 95.00 — a
    wrong number with no exception anywhere. This test would have been green
    against the crash too, which is why it is stated separately."""
    from app.services.proactive_agents import run_discount_expiry_monitor

    _one_invoice(db_session, discounted_total=Decimal("0.00"))

    outcome = run_discount_expiry_monitor(db_session, TENANT)

    assert outcome.state == "ok", outcome
    msg = _alert_message(db_session)
    assert "$0.00" in msg, msg
    assert "$95.00" not in msg, f"0.00 was silently replaced by the 95% fallback: {msg}"


def test_a_REAL_discounted_total_is_used_verbatim(db_session):
    """The ordinary case, so the two above are read against a control rather
    than against each other."""
    from app.services.proactive_agents import run_discount_expiry_monitor

    _one_invoice(db_session, discounted_total=Decimal("93.50"))

    outcome = run_discount_expiry_monitor(db_session, TENANT)

    assert outcome.state == "ok", outcome
    msg = _alert_message(db_session)
    assert "$93.50" in msg, msg
    # 100.00 * 0.05 = 5.00 — the savings line is independent of discounted_total
    assert "$5.00" in msg, msg
