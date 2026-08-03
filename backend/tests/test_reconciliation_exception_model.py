"""Books Review Phase 2 Arc A-1b — the purpose-built reconciliation exception model.

Pins the DECIDED schema shape (migration r148):
  * candidates key to the TRANSACTION, not the exception (auto-committed matches
    keep their audit trail);
  * the exception carries NO match_status copy (source transaction is authority);
  * one exception per transaction, one candidate per (txn, type, id);
  * rejection_reason is a bounded enum (CHECK) + a structured measured value (JSONB);
  * both tables cascade when the source transaction is deleted.

Cleans up its own `rex-*` tenants via the shared FK-safe helper (COMPANY-LITTER ratchet).
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models.company import Company
from app.models.financial_account import (
    FinancialAccount,
    ReconciliationException,
    ReconciliationMatchCandidate,
    ReconciliationRun,
    ReconciliationTransaction,
)
from tests._cleanup import purge_companies_by_slug

_SLUG_PREFIX = "rex-"


@pytest.fixture
def substrate():
    """A company + financial account + run + one bank transaction to hang
    exceptions/candidates off."""
    s = SessionLocal()
    suffix = uuid.uuid4().hex[:8]
    co = Company(id=str(uuid.uuid4()), name=f"REX {suffix}", slug=f"{_SLUG_PREFIX}{suffix}",
                 is_active=True, vertical="manufacturing")
    s.add(co); s.flush()
    acct = FinancialAccount(id=str(uuid.uuid4()), tenant_id=co.id,
                            account_type="checking", account_name="Operating")
    s.add(acct); s.flush()
    run = ReconciliationRun(id=str(uuid.uuid4()), tenant_id=co.id, financial_account_id=acct.id,
                            statement_date=date(2026, 6, 30), statement_closing_balance=Decimal("0"))
    s.add(run); s.flush()
    txn = ReconciliationTransaction(id=str(uuid.uuid4()), tenant_id=co.id,
                                    reconciliation_run_id=run.id, transaction_date=date(2026, 6, 15),
                                    description="deposit 100.00", amount=Decimal("100.00"),
                                    transaction_type="credit")
    s.add(txn); s.commit()
    ids = {"co": co.id, "run": run.id, "txn": txn.id}
    s.close()
    yield ids
    s = SessionLocal()
    try:
        purge_companies_by_slug(s, f"{_SLUG_PREFIX}%")
    finally:
        s.close()


def _cand(co, txn, *, ptype="customer_payment", pid=None, score="0.980", rank=1,
          reason=None, detail=None):
    return ReconciliationMatchCandidate(
        id=str(uuid.uuid4()), tenant_id=co, reconciliation_transaction_id=txn,
        candidate_record_type=ptype, candidate_record_id=pid or str(uuid.uuid4()),
        score=Decimal(score), rank=rank, rejection_reason=reason, rejection_detail=detail)


def test_exception_carries_no_match_status_copy(substrate):
    """The exception is a workspace object; the transaction is authority on
    open/closed. The model must NOT duplicate match_status."""
    assert not hasattr(ReconciliationException, "match_status"), \
        "exception must not carry a match_status copy — source transaction is authority"
    # It DOES carry resolution state (the workspace record, distinct from match_status).
    for f in ("resolved", "resolved_by", "resolved_at", "resolution_note", "flag_id"):
        assert hasattr(ReconciliationException, f)


def test_candidates_key_to_transaction_not_exception(substrate):
    """Candidates hang off the TRANSACTION so auto-committed matches keep the
    audit of what was considered — there is no exception_id FK on the candidate."""
    assert hasattr(ReconciliationMatchCandidate, "reconciliation_transaction_id")
    assert not hasattr(ReconciliationMatchCandidate, "exception_id"), \
        "candidates key to the transaction, never the exception"
    s = SessionLocal()
    try:
        s.add(_cand(substrate["co"], substrate["txn"], score="0.980", rank=1))
        s.commit()
        got = s.query(ReconciliationMatchCandidate).filter_by(
            reconciliation_transaction_id=substrate["txn"]).all()
        assert len(got) == 1 and got[0].reconciliation_transaction_id == substrate["txn"]
    finally:
        s.rollback(); s.close()


def test_one_exception_per_transaction(substrate):
    s = SessionLocal()
    try:
        s.add(ReconciliationException(
            id=str(uuid.uuid4()), tenant_id=substrate["co"],
            reconciliation_transaction_id=substrate["txn"], reconciliation_run_id=substrate["run"]))
        s.commit()
        s.add(ReconciliationException(
            id=str(uuid.uuid4()), tenant_id=substrate["co"],
            reconciliation_transaction_id=substrate["txn"], reconciliation_run_id=substrate["run"]))
        with pytest.raises(IntegrityError):
            s.commit()
    finally:
        s.rollback(); s.close()


def test_one_candidate_per_txn_type_id(substrate):
    pid = str(uuid.uuid4())
    s = SessionLocal()
    try:
        s.add(_cand(substrate["co"], substrate["txn"], pid=pid, rank=1))
        s.commit()
        s.add(_cand(substrate["co"], substrate["txn"], pid=pid, rank=2))  # same (txn,type,id)
        with pytest.raises(IntegrityError):
            s.commit()
    finally:
        s.rollback(); s.close()


def test_rejection_reason_check_rejects_unknown_code(substrate):
    s = SessionLocal()
    try:
        s.add(_cand(substrate["co"], substrate["txn"], reason="NOT_A_REAL_CODE"))
        with pytest.raises(IntegrityError):
            s.commit()
    finally:
        s.rollback(); s.close()


def test_rejection_reason_accepts_null_and_known_codes(substrate):
    s = SessionLocal()
    try:
        # NULL = a viable/proposed candidate; the known hard-gate codes carry a
        # structured measured value in rejection_detail.
        s.add(_cand(substrate["co"], substrate["txn"], pid="p-viable", rank=1, reason=None))
        s.add(_cand(substrate["co"], substrate["txn"], pid="p-nearmiss", rank=2,
                    reason="OUTSIDE_DATE_WINDOW", detail={"days_diff": 6}))
        s.add(_cand(substrate["co"], substrate["txn"], pid="p-dir", rank=3,
                    reason="DIRECTION_MISMATCH", detail={"txn_type": "credit"}))
        # AMOUNT_MISMATCH — the band-era gate (A-2): in-band but beyond exact tolerance.
        s.add(_cand(substrate["co"], substrate["txn"], pid="p-amt", rank=4,
                    reason="AMOUNT_MISMATCH", detail={"amount_delta": "0.40"}))
        s.commit()
        rows = {c.candidate_record_id: c for c in s.query(ReconciliationMatchCandidate)
                .filter_by(reconciliation_transaction_id=substrate["txn"]).all()}
        assert rows["p-viable"].rejection_reason is None
        assert rows["p-nearmiss"].rejection_reason == "OUTSIDE_DATE_WINDOW"
        assert rows["p-nearmiss"].rejection_detail == {"days_diff": 6}  # measured value round-trips
        assert rows["p-amt"].rejection_reason == "AMOUNT_MISMATCH"
    finally:
        s.rollback(); s.close()


def test_deleting_transaction_cascades_exception_and_candidates(substrate):
    from sqlalchemy import text
    s = SessionLocal()
    try:
        s.add(ReconciliationException(
            id=str(uuid.uuid4()), tenant_id=substrate["co"],
            reconciliation_transaction_id=substrate["txn"], reconciliation_run_id=substrate["run"]))
        s.add(_cand(substrate["co"], substrate["txn"], rank=1))
        s.commit()
        # Delete the source transaction; ondelete=CASCADE must clear both.
        s.execute(text("DELETE FROM reconciliation_transactions WHERE id=:t"), {"t": substrate["txn"]})
        s.commit()
        assert s.query(ReconciliationException).filter_by(
            reconciliation_transaction_id=substrate["txn"]).count() == 0
        assert s.query(ReconciliationMatchCandidate).filter_by(
            reconciliation_transaction_id=substrate["txn"]).count() == 0
    finally:
        s.rollback(); s.close()
