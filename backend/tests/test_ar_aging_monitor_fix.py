"""`ar_aging_monitor` — the date normalisation and the dedup, together.

Item 0c. The two land in one commit because the DATE FIX IS WHAT MAKES THE
DEDUP DEFECT LIVE: the job has produced nothing since 2026-07-16, so
`ar_aging_61` creating outside its guard and `ar_aging_90` creating
unconditionally have never once fired. Fixing the date alone would turn a job
that writes nothing into one that writes two alerts a night, for as long as an
invoice stays open, with no unique constraint anywhere to stop it.

⚠️ THE FIXTURE USES A `datetime` due_date BECAUSE THE COLUMN IS ONE.
`Invoice.due_date` is `DateTime(timezone=True), nullable=False`. A fixture
passing a `date` would exercise a shape the production path cannot produce and
would have passed against the bug.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.models.agent import AgentAlert
from app.models.invoice import Invoice
from app.services.agent_service import run_ar_aging_monitor
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
    """This file COMMITS (create_alert does). Purge what it writes."""
    def purge():
        db_session.execute(text(
            "DELETE FROM agent_alerts WHERE tenant_id=:t AND alert_type LIKE 'ar_aging%'"),
            {"t": TENANT})
        db_session.execute(text(
            "DELETE FROM agent_collection_sequences WHERE tenant_id=:t"), {"t": TENANT})
        db_session.execute(text(
            "DELETE FROM invoices WHERE company_id=:t AND number LIKE 'AGING-%'"),
            {"t": TENANT})
        db_session.execute(text(
            "DELETE FROM customers WHERE company_id=:t AND name='Aging Fixture'"),
            {"t": TENANT})
        db_session.commit()
    purge(); yield; purge()


def _customer(db) -> str:
    cid = str(uuid.uuid4()); now = datetime.now(timezone.utc)
    db.execute(text(
        "INSERT INTO customers (id, company_id, name, current_balance, created_at,"
        " updated_at) VALUES (:i,:t,'Aging Fixture',0,:ts,:ts)"),
        {"i": cid, "t": TENANT, "ts": now})
    db.commit(); return cid


def _overdue(db, days: int) -> Invoice:
    """An open invoice `days` past due, with a DATETIME due_date."""
    inv = Invoice(
        id=str(uuid.uuid4()), company_id=TENANT, customer_id=_customer(db),
        number=f"AGING-{uuid.uuid4().hex[:6]}", status="sent",
        invoice_date=datetime.now(timezone.utc) - timedelta(days=days + 30),
        due_date=datetime.now(timezone.utc) - timedelta(days=days),
        subtotal=Decimal("500.00"), tax_amount=Decimal("0.00"),
        total=Decimal("500.00"),
    )
    db.add(inv); db.commit(); return inv


def _alerts(db, kind: str, invoice_id: str | None = None):
    """⚠️ SCOPED TO ONE INVOICE BY DEFAULT — the delta, not the world.

    The first version counted every alert of a type on the tenant and asserted
    == 1. The dev database holds other TESTCO invoices in the same aging bands,
    so it read 3 where the fixture made 1. The count was correct about the
    world and wrong about this test's claim.
    """
    q = db.query(AgentAlert).filter(
        AgentAlert.tenant_id == TENANT, AgentAlert.alert_type == kind
    )
    rows = q.all()
    if invoice_id is None:
        return rows
    return [a for a in rows
            if isinstance(a.action_payload, dict)
            and a.action_payload.get("invoice_id") == invoice_id]


# ── the date fix ─────────────────────────────────────────────────────────


def test_a_datetime_due_date_no_longer_raises(db_session):
    """⚠️ The 163-failure bug. `date.today() - DateTime` raised on the FIRST
    invoice, before the `days_overdue <= 0` guard could skip anything."""
    _overdue(db_session, 100)
    result = run_ar_aging_monitor(db_session, TENANT)
    assert "error" not in result, result
    assert result["invoices_checked"] >= 1


def test_a_not_yet_due_invoice_is_skipped_not_crashed_on(db_session):
    inv = Invoice(
        id=str(uuid.uuid4()), company_id=TENANT, customer_id=_customer(db_session),
        number=f"AGING-{uuid.uuid4().hex[:6]}", status="sent",
        invoice_date=datetime.now(timezone.utc),
        due_date=datetime.now(timezone.utc) + timedelta(days=10),
        subtotal=Decimal("1.00"), tax_amount=Decimal("0.00"), total=Decimal("1.00"),
    )
    db_session.add(inv); db_session.commit()
    result = run_ar_aging_monitor(db_session, TENANT)
    assert "error" not in result
    assert _alerts(db_session, "ar_aging_90", inv.id) == []


# ── the dedup, per band ──────────────────────────────────────────────────


@pytest.mark.parametrize("days,kind", [(45, "ar_aging_31"), (75, "ar_aging_61"),
                                       (120, "ar_aging_90")])
def test_a_band_emits_ONCE_and_a_second_run_emits_NOTHING(db_session, days, kind):
    """⚠️ THE TEST THAT MATTERS, and the case the two defects disagree on.

    A single run cannot distinguish a guarded branch from an unguarded one —
    both emit one alert. The SECOND run is where `ar_aging_61` and
    `ar_aging_90` used to emit again, and again, nightly, without bound.
    """
    inv = _overdue(db_session, days)

    run_ar_aging_monitor(db_session, TENANT)
    after_first = len(_alerts(db_session, kind, inv.id))
    assert after_first == 1, f"{kind}: expected 1, got {after_first}"

    run_ar_aging_monitor(db_session, TENANT)
    run_ar_aging_monitor(db_session, TENANT)
    after_third = len(_alerts(db_session, kind, inv.id))
    assert after_third == 1, (
        f"{kind} re-fired: {after_third} alerts after three runs. "
        "agent_alerts has no unique constraint, so nothing else stops this."
    )


def test_the_subject_is_STRUCTURED_not_parsed_from_the_title(db_session):
    """The invoice number is in the title. The dedup must not read it there."""
    inv = _overdue(db_session, 120)
    run_ar_aging_monitor(db_session, TENANT)
    alert = _alerts(db_session, "ar_aging_90", inv.id)[0]
    assert alert.action_payload == {"invoice_id": inv.id}
    # Prose carries the number too — in the MESSAGE for this band, not the
    # title. Which is the point: the key is the field, wherever the prose puts
    # it, and a dedup reading prose would have to know which of the three
    # branches wrote it.
    assert inv.number in (alert.title + alert.message)


def test_two_invoices_in_one_band_get_one_alert_EACH(db_session):
    """Dedup is per INVOICE, not per band. A guard keyed on alert_type alone
    would collapse these to one and silently drop a customer's balance."""
    a = _overdue(db_session, 120)
    b = _overdue(db_session, 130)
    run_ar_aging_monitor(db_session, TENANT)
    run_ar_aging_monitor(db_session, TENANT)
    assert len(_alerts(db_session, "ar_aging_90", a.id)) == 1
    assert len(_alerts(db_session, "ar_aging_90", b.id)) == 1
