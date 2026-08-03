"""Books Review Phase 2 Arc A-3 — the durable payment-claim table.

Pins the claim substrate:
  * auto-commit creates a claim row; UNIQUE(payment_id) is enforced;
  * a claim already in the table excludes the payment from auto-commit (recorded
    ALREADY_CLAIMED), regardless of whether an auto_cleared transaction exists —
    the CLAIM TABLE is the source of truth, not the transaction;
  * the claim-race LOSER (_try_claim on an already-claimed payment) returns False,
    logs, does NOT raise, and leaves the session usable — never a bare swallow;
  * a transaction dated in a locked period does NOT auto-commit — recorded
    PERIOD_LOCKED with no claim written;
  * deleting the transaction releases the claim (cascade).

Money is hand-math'd; cleans up its own `a3rec-*` tenants (COMPANY-LITTER ratchet).
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models.company import Company
from app.models.customer import Customer
from app.models.customer_payment import CustomerPayment
from app.models.financial_account import (
    FinancialAccount,
    ReconciliationException,
    ReconciliationMatchCandidate,
    ReconciliationPaymentClaim,
    ReconciliationRun,
    ReconciliationTransaction,
)
from app.services import reconciliation_service
from app.services.agents.period_lock import PeriodLockService
from tests._cleanup import purge_companies_by_slug

_SLUG = "a3rec-"


@pytest.fixture
def env():
    s = SessionLocal()
    suffix = uuid.uuid4().hex[:8]
    co = Company(id=str(uuid.uuid4()), name=f"A3 {suffix}", slug=f"{_SLUG}{suffix}",
                 is_active=True, vertical="manufacturing")
    s.add(co); s.flush()
    acct = FinancialAccount(id=str(uuid.uuid4()), tenant_id=co.id,
                            account_type="checking", account_name="Operating")
    s.add(acct); s.flush()
    run = ReconciliationRun(
        id=str(uuid.uuid4()), tenant_id=co.id, financial_account_id=acct.id,
        statement_date=date(2026, 7, 31), statement_closing_balance=Decimal("0"),
        period_start=date(2026, 7, 1), opening_balance=Decimal("0"))
    s.add(run); s.commit()
    yield type("Env", (), {"s": s, "co": co.id, "run": run})()
    s.rollback()
    try:
        purge_companies_by_slug(s, f"{_SLUG}%")
    finally:
        s.close()


def _cust(env):
    c = Customer(id=str(uuid.uuid4()), company_id=env.co, name="Cust", is_active=True)
    env.s.add(c); env.s.flush()
    return c


def _cp(env, cust, *, total, day=15):
    p = CustomerPayment(id=str(uuid.uuid4()), company_id=env.co, customer_id=cust.id,
                        payment_date=datetime(2026, 7, day, 12, tzinfo=timezone.utc),
                        total_amount=Decimal(total), payment_method="check")
    env.s.add(p); env.s.flush()
    return p


def _txn(env, *, amount, day=15, order=0, run=None):
    t = ReconciliationTransaction(
        id=str(uuid.uuid4()), tenant_id=env.co,
        reconciliation_run_id=(run or env.run).id,
        transaction_date=date(2026, 7, day), description="deposit",
        amount=Decimal(amount), transaction_type="credit", sort_order=order)
    env.s.add(t); env.s.flush()
    return t


def _run2(env):
    r = ReconciliationRun(
        id=str(uuid.uuid4()), tenant_id=env.co, financial_account_id=env.run.financial_account_id,
        statement_date=date(2026, 7, 31), statement_closing_balance=Decimal("0"),
        period_start=date(2026, 7, 1), opening_balance=Decimal("0"))
    env.s.add(r); env.s.flush()
    return r


def _match(env, run=None):
    reconciliation_service.run_matching(env.s, run or env.run, env.co)
    env.s.commit()


def _claims(env, payment_id=None):
    q = env.s.query(ReconciliationPaymentClaim).filter(
        ReconciliationPaymentClaim.tenant_id == env.co)
    if payment_id:
        q = q.filter(ReconciliationPaymentClaim.payment_id == payment_id)
    return q.all()


def test_auto_commit_creates_a_claim_row(env):
    cust = _cust(env)
    pay = _cp(env, cust, total="525.00")
    txn = _txn(env, amount="525.00")
    _match(env)

    env.s.refresh(txn)
    assert txn.match_status == "auto_cleared"
    claims = _claims(env, pay.id)
    assert len(claims) == 1
    assert claims[0].payment_type == "customer_payment"
    assert claims[0].reconciliation_transaction_id == txn.id


def test_payment_id_is_unique_across_claims(env):
    cust = _cust(env)
    pay = _cp(env, cust, total="100.00")
    t1 = _txn(env, amount="100.00", order=0)
    t2 = _txn(env, amount="100.00", order=1)
    env.s.add(ReconciliationPaymentClaim(
        tenant_id=env.co, payment_type="customer_payment", payment_id=pay.id,
        reconciliation_transaction_id=t1.id, reconciliation_run_id=env.run.id))
    env.s.commit()
    env.s.add(ReconciliationPaymentClaim(
        tenant_id=env.co, payment_type="customer_payment", payment_id=pay.id,
        reconciliation_transaction_id=t2.id, reconciliation_run_id=env.run.id))
    with pytest.raises(IntegrityError):
        env.s.commit()
    env.s.rollback()


def test_second_run_records_already_claimed_via_claim_table(env):
    cust = _cust(env)
    pay = _cp(env, cust, total="500.00")
    ta = _txn(env, amount="500.00", run=env.run)
    run_b = _run2(env)
    tb = _txn(env, amount="500.00", run=run_b)
    env.s.commit()

    _match(env, env.run)     # run_a claims the payment
    _match(env, run_b)       # run_b must see the claim

    env.s.refresh(ta); env.s.refresh(tb)
    assert ta.matched_record_id == pay.id
    assert tb.matched_record_id is None
    assert len(_claims(env, pay.id)) == 1     # exactly one claim, not two
    tb_cands = env.s.query(ReconciliationMatchCandidate).filter(
        ReconciliationMatchCandidate.reconciliation_transaction_id == tb.id).all()
    assert [c.rejection_reason for c in tb_cands] == ["ALREADY_CLAIMED"]


def test_pool_exclusion_is_driven_by_the_claim_table_not_the_transaction(env):
    # A claim exists (owned by an unrelated dummy txn), but NO auto_cleared
    # transaction points at the payment. A fresh run must still treat it as
    # claimed — proving the claim TABLE is the source of truth.
    cust = _cust(env)
    pay = _cp(env, cust, total="640.00")
    dummy = _txn(env, amount="1.00", order=99)     # owns the pre-claim, unrelated
    env.s.add(ReconciliationPaymentClaim(
        tenant_id=env.co, payment_type="customer_payment", payment_id=pay.id,
        reconciliation_transaction_id=dummy.id, reconciliation_run_id=env.run.id))
    env.s.commit()

    txn = _txn(env, amount="640.00", order=0)
    _match(env)

    env.s.refresh(txn)
    assert txn.match_status == "unmatched"
    cands = env.s.query(ReconciliationMatchCandidate).filter(
        ReconciliationMatchCandidate.reconciliation_transaction_id == txn.id).all()
    assert [c.rejection_reason for c in cands] == ["ALREADY_CLAIMED"]
    assert len(_claims(env, pay.id)) == 1          # no new claim written


def test_try_claim_race_loser_returns_false_and_session_survives(env, caplog):
    # The concurrency guard, directly: a claim already exists; a second attempt
    # for the same payment_id returns False (NOT raise), logs, and leaves the
    # session usable — never a bare swallow, never a poisoned transaction.
    cust = _cust(env)
    pay = _cp(env, cust, total="333.00")
    t1 = _txn(env, amount="333.00", order=0)
    t2 = _txn(env, amount="333.00", order=1)
    assert reconciliation_service._try_claim(
        env.s, env.co, "customer_payment", pay.id, t1.id, env.run.id) is True
    env.s.commit()

    with caplog.at_level(logging.WARNING):
        lost = reconciliation_service._try_claim(
            env.s, env.co, "customer_payment", pay.id, t2.id, env.run.id)
    assert lost is False
    assert any("claim race lost" in r.message for r in caplog.records)
    # session is NOT poisoned — a query still works, and only one claim exists.
    assert len(_claims(env, pay.id)) == 1


def test_period_locked_txn_records_period_locked_and_writes_no_claim(env):
    cust = _cust(env)
    pay = _cp(env, cust, total="850.00")
    txn = _txn(env, amount="850.00", day=15)
    # lock the whole statement period (txn dated 07-15 falls inside it)
    PeriodLockService.lock_period(env.s, env.co, date(2026, 7, 1), date(2026, 7, 31),
                                  reason="test close")
    _match(env)

    env.s.refresh(txn)
    assert txn.match_status == "unmatched"          # never write into a locked period
    assert txn.matched_record_id is None
    cands = env.s.query(ReconciliationMatchCandidate).filter(
        ReconciliationMatchCandidate.reconciliation_transaction_id == txn.id).all()
    assert [c.rejection_reason for c in cands] == ["PERIOD_LOCKED"]
    assert cands[0].rejection_detail["period_start"] == "2026-07-01"
    assert _claims(env, pay.id) == []               # no claim written
    assert env.s.query(ReconciliationException).filter(
        ReconciliationException.reconciliation_transaction_id == txn.id).count() == 1


def test_deleting_transaction_releases_the_claim(env):
    from sqlalchemy import text
    cust = _cust(env)
    pay = _cp(env, cust, total="475.00")
    txn = _txn(env, amount="475.00")
    _match(env)
    assert len(_claims(env, pay.id)) == 1

    env.s.execute(text("DELETE FROM reconciliation_transactions WHERE id=:t"), {"t": txn.id})
    env.s.commit()
    assert _claims(env, pay.id) == []               # cascade released it
