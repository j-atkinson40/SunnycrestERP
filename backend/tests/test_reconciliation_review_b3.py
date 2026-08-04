"""Books Review Arc B B-3 — reconciliation triage queue, source builder + Accept.

Pins the load-bearing calls:
  * the source builder filters on the SOURCE TRANSACTION's match_status, NOT on
    reconciliation_exceptions.resolved (the invariant that keeps the exception a
    workspace object, not a second source of truth);
  * candidates ride each row (Option A);
  * Accept DISPATCHES BY ITEM DATA — commits the SELECTED candidate (top by
    default), reusing the Arc A claim path;
  * PARITY: manual accept and auto-commit produce identical state (same claim
    row, same matched_record_*, same confidence), differing ONLY in match_status
    + provenance — the highest-value pin in the sub-arc;
  * Accept honors the period lock (a human click never writes a closed period);
  * the coding branch requires a coding.

Cleans up its own `b3rec-*` tenants via the shared FK-safe helper.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

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
from app.models.role import Role
from app.models.user import User
from app.services import reconciliation_service
from app.services.agents.period_lock import PeriodLockService
from app.services.triage.action_handlers import _handle_reconciliation_accept
from app.services.triage.engine import _dq_reconciliation_review
from tests._cleanup import purge_companies_by_slug

_SLUG = "b3rec-"


@pytest.fixture
def env():
    s = SessionLocal()
    sfx = uuid.uuid4().hex[:8]
    co = Company(id=str(uuid.uuid4()), name=f"B3 {sfx}", slug=f"{_SLUG}{sfx}",
                 is_active=True, vertical="manufacturing")
    s.add(co); s.flush()
    role = Role(id=str(uuid.uuid4()), company_id=co.id, name="Admin", slug="admin")
    s.add(role); s.flush()
    user = User(id=str(uuid.uuid4()), company_id=co.id, role_id=role.id,
                email=f"b3-{sfx}@test.local", hashed_password="x",
                first_name="B", last_name="Three", is_active=True)
    s.add(user); s.flush()
    acct = FinancialAccount(id=str(uuid.uuid4()), tenant_id=co.id,
                            account_type="checking", account_name="Operating")
    s.add(acct); s.commit()
    yield type("Env", (), {"s": s, "co": co.id, "user": user, "acct": acct.id})()
    s.rollback()
    try:
        purge_companies_by_slug(s, f"{_SLUG}%")
    finally:
        s.close()


def _run(env):
    r = ReconciliationRun(id=str(uuid.uuid4()), tenant_id=env.co, financial_account_id=env.acct,
                          statement_date=date(2026, 7, 31), statement_closing_balance=Decimal("0"),
                          period_start=date(2026, 7, 1), opening_balance=Decimal("0"))
    env.s.add(r); env.s.flush()
    return r


def _txn(env, run, *, amount, day=15, status="unmatched", order=0):
    t = ReconciliationTransaction(
        id=str(uuid.uuid4()), tenant_id=env.co, reconciliation_run_id=run.id,
        transaction_date=date(2026, 7, day), description=f"deposit {amount}",
        amount=Decimal(amount), transaction_type="credit", match_status=status, sort_order=order)
    env.s.add(t); env.s.flush()
    return t


def _cp(env, *, total, day=15):
    cust = Customer(id=str(uuid.uuid4()), company_id=env.co, name="Cust", is_active=True)
    env.s.add(cust); env.s.flush()
    p = CustomerPayment(id=str(uuid.uuid4()), company_id=env.co, customer_id=cust.id,
                        payment_date=datetime(2026, 7, day, 12, tzinfo=timezone.utc),
                        total_amount=Decimal(total), payment_method="check")
    env.s.add(p); env.s.flush()
    return p


def _cand(env, txn, *, ptype="customer_payment", pid, score="0.980", rank=1, reason=None, detail=None):
    c = ReconciliationMatchCandidate(
        id=str(uuid.uuid4()), tenant_id=env.co, reconciliation_transaction_id=txn.id,
        candidate_record_type=ptype, candidate_record_id=pid, score=Decimal(score),
        rank=rank, rejection_reason=reason, rejection_detail=detail)
    env.s.add(c); env.s.flush()
    return c


def _exc(env, txn, run, *, resolved=False):
    e = ReconciliationException(id=str(uuid.uuid4()), tenant_id=env.co,
                               reconciliation_transaction_id=txn.id,
                               reconciliation_run_id=run.id, resolved=resolved)
    env.s.add(e); env.s.flush()
    return e


def _ctx(env, txn_id, **kw):
    return {"db": env.s, "user": env.user, "entity_type": "reconciliation_exception",
            "entity_id": txn_id, "queue_id": "reconciliation_review_triage",
            "action_id": "accept", "reason": None, "reason_code": None,
            "note": kw.pop("note", None), "payload": kw.pop("payload", {})}


# ── source builder ───────────────────────────────────────────────────────────
def test_builder_filters_on_match_status_not_resolved(env):
    run = _run(env)
    # (a) unmatched txn + RESOLVED exception → STILL surfaces (resolved ignored).
    t_open = _txn(env, run, amount="100.00", order=0)
    _exc(env, t_open, run, resolved=True)
    # (b) manually_matched txn + UNRESOLVED exception → does NOT surface
    #     (transaction status is authority).
    t_done = _txn(env, run, amount="200.00", status="manually_matched", order=1)
    _exc(env, t_done, run, resolved=False)
    env.s.commit()

    ids = {r["id"] for r in _dq_reconciliation_review(env.s, env.user)}
    assert t_open.id in ids       # resolved flag did not hide it
    assert t_done.id not in ids   # match_status moved it off the queue


def test_builder_emits_candidates_option_a(env):
    run = _run(env)
    t = _txn(env, run, amount="488.00")
    _exc(env, t, run)
    _cand(env, t, pid="p-viable", rank=1)
    _cand(env, t, pid="p-near", rank=2, score="0.400", reason="AMOUNT_MISMATCH",
          detail={"amount_delta": "8.00"})
    env.s.commit()

    row = next(r for r in _dq_reconciliation_review(env.s, env.user) if r["id"] == t.id)
    assert [c["candidate_record_id"] for c in row["candidates"]] == ["p-viable", "p-near"]
    assert row["candidates"][1]["rejection_reason"] == "AMOUNT_MISMATCH"
    assert row["candidates"][1]["rejection_detail"] == {"amount_delta": "8.00"}


# ── Accept: selected candidate ──────────────────────────────────────────────
def test_accept_commits_the_selected_candidate_not_the_top(env):
    run = _run(env)
    t = _txn(env, run, amount="500.00")
    exc = _exc(env, t, run)
    pay1 = _cp(env, total="500.00"); pay2 = _cp(env, total="500.00")
    _cand(env, t, pid=pay1.id, rank=1)
    c2 = _cand(env, t, pid=pay2.id, rank=2)
    env.s.commit()

    # select ROW 2 (pay2) — must commit pay2, not the top.
    res = _handle_reconciliation_accept(_ctx(env, t.id, payload={"candidate_id": c2.id}))
    env.s.commit()
    assert res["status"] == "applied"
    env.s.refresh(t); env.s.refresh(exc)
    assert t.matched_record_id == pay2.id
    assert t.match_status == "manually_matched"
    assert exc.resolved is True and exc.chosen_candidate_id == c2.id
    # claim is on pay2, not pay1
    claims = env.s.query(ReconciliationPaymentClaim).filter(
        ReconciliationPaymentClaim.tenant_id == env.co).all()
    assert [cl.payment_id for cl in claims] == [pay2.id]


def test_accept_defaults_to_top_candidate(env):
    run = _run(env)
    t = _txn(env, run, amount="500.00")
    _exc(env, t, run)
    pay1 = _cp(env, total="500.00"); pay2 = _cp(env, total="500.00")
    _cand(env, t, pid=pay1.id, rank=1)
    _cand(env, t, pid=pay2.id, rank=2)
    env.s.commit()

    _handle_reconciliation_accept(_ctx(env, t.id))  # no candidate_id → top
    env.s.commit()
    env.s.refresh(t)
    assert t.matched_record_id == pay1.id


# ── PARITY (highest value) ──────────────────────────────────────────────────
def test_manual_accept_matches_auto_commit_state(env):
    # AUTO: a clean single-candidate case → run_matching auto-commits.
    run_a = _run(env)
    pay_a = _cp(env, total="500.00", day=15)
    ta = _txn(env, run_a, amount="500.00", day=15)
    env.s.commit()
    reconciliation_service.run_matching(env.s, run_a, env.co)
    env.s.commit()
    env.s.refresh(ta)

    # MANUAL: an ambiguous case (2 viable) → run_matching does NOT auto-commit;
    # the human accepts the chosen payment.
    run_b = _run(env)
    pay_b1 = _cp(env, total="500.00", day=15)
    pay_b2 = _cp(env, total="500.00", day=15)
    tb = _txn(env, run_b, amount="500.00", day=15)
    env.s.commit()
    reconciliation_service.run_matching(env.s, run_b, env.co)  # ambiguous → unmatched + candidates
    env.s.commit()
    env.s.refresh(tb)
    assert tb.match_status == "unmatched"
    cand_b1 = env.s.query(ReconciliationMatchCandidate).filter(
        ReconciliationMatchCandidate.reconciliation_transaction_id == tb.id,
        ReconciliationMatchCandidate.candidate_record_id == pay_b1.id).one()
    _handle_reconciliation_accept(_ctx(env, tb.id, payload={"candidate_id": cand_b1.id}))
    env.s.commit()
    env.s.refresh(tb)

    # IDENTICAL state, modulo match_status + provenance:
    assert ta.matched_record_type == tb.matched_record_type == "customer_payment"
    assert ta.match_confidence == tb.match_confidence            # both 0.980 (same day)
    assert ta.matched_record_id == pay_a.id
    assert tb.matched_record_id == pay_b1.id
    # each has exactly one claim row, for its own committed payment
    claims = {cl.payment_id for cl in env.s.query(ReconciliationPaymentClaim).filter(
        ReconciliationPaymentClaim.tenant_id == env.co).all()}
    assert pay_a.id in claims and pay_b1.id in claims
    # THE difference: status + provenance only
    assert ta.match_status == "auto_cleared"
    assert tb.match_status == "manually_matched"
    assert ta.reviewed_by is None
    assert tb.reviewed_by == env.user.id


# ── period lock ─────────────────────────────────────────────────────────────
def test_accept_is_blocked_by_a_locked_period(env):
    run = _run(env)
    t = _txn(env, run, amount="500.00", day=15)
    _exc(env, t, run)
    pay = _cp(env, total="500.00")
    _cand(env, t, pid=pay.id, rank=1)
    PeriodLockService.lock_period(env.s, env.co, date(2026, 7, 1), date(2026, 7, 31),
                                  reason="closed")
    env.s.commit()

    res = _handle_reconciliation_accept(_ctx(env, t.id))
    assert res["status"] == "errored" and "locked" in res["message"].lower()
    env.s.refresh(t)
    assert t.match_status == "unmatched"                        # no write into a closed period
    assert env.s.query(ReconciliationPaymentClaim).filter(
        ReconciliationPaymentClaim.tenant_id == env.co).count() == 0


# ── coding branch + guards ──────────────────────────────────────────────────
def test_coding_accept_requires_and_records_a_coding(env):
    run = _run(env)
    t = _txn(env, run, amount="377.00")
    exc = _exc(env, t, run)                                     # no candidates
    env.s.commit()

    # no coding → error
    assert _handle_reconciliation_accept(_ctx(env, t.id))["status"] == "errored"
    # with coding → applied
    res = _handle_reconciliation_accept(_ctx(env, t.id, payload={"coding": "6100 · Interest"}))
    env.s.commit()
    assert res["status"] == "applied"
    env.s.refresh(t); env.s.refresh(exc)
    assert t.match_status == "manually_matched" and t.match_notes == "6100 · Interest"
    assert exc.resolved is True


def test_accept_on_already_resolved_item_errors(env):
    run = _run(env)
    t = _txn(env, run, amount="500.00", status="manually_matched")
    _exc(env, t, run)
    env.s.commit()
    assert _handle_reconciliation_accept(_ctx(env, t.id))["status"] == "errored"
