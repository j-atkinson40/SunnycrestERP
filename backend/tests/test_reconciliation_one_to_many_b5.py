"""Books Review Arc B B-5 — one-to-many (a single deposit covering N payments).

Pins:
  * the subset-sum finder: k=2, k=3 (case 7), and the EXCLUSIONS stated in code —
    4+ payments and fee-netted totals do NOT surface; claimed members excluded;
  * run_matching surfaces a payment_group candidate (members in rejection_detail);
  * the synthetic group id is reproducible + carries the grp_ marker;
  * candidate_record_type CHECK (r152) rejects an unknown type;
  * ACCEPT is ALL-OR-NONE — the most important pin: a member pre-claimed → the
    accept fails, ZERO new claims, the transaction stays unmatched (a partial
    claim would leave payments in an inconsistent state with no error).

Money is hand-math'd; cleans up its own `b5rec-*` tenants.
"""
from __future__ import annotations

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
from app.models.role import Role
from app.models.user import User
from app.services import reconciliation_service
from app.services.reconciliation_service import _find_payment_group, _payment_group_id, run_matching
from app.services.triage.action_handlers import _handle_reconciliation_accept
from tests._cleanup import purge_companies_by_slug

_SLUG = "b5rec-"


# ── pure subset-sum unit tests (no DB) ───────────────────────────────────────
def _pool(*amounts: str):
    return [
        ("customer_payment", f"p{i}", date(2026, 7, 15), None, Decimal(a))
        for i, a in enumerate(amounts)
    ]


def test_find_group_k3_is_case_7():
    # HAND MATH: 1890.00 + 2142.50 + 815.00 = 4847.50.
    pool = _pool("1890.00", "2142.50", "815.00", "999.99")
    g = _find_payment_group(pool, Decimal("4847.50"), set())
    assert g is not None
    assert sorted(m[4] for m in g) == [Decimal("815.00"), Decimal("1890.00"), Decimal("2142.50")]


def test_find_group_k2():
    pool = _pool("300.00", "200.00", "50.00")  # 300 + 200 = 500
    g = _find_payment_group(pool, Decimal("500.00"), set())
    assert g is not None and len(g) == 2 and sum(m[4] for m in g) == Decimal("500.00")


def test_no_group_for_4_payments_is_excluded():
    # 100+200+300+400 = 1000, but NO 2- or 3-subset sums to 1000 → k<=3 excludes it.
    pool = _pool("100.00", "200.00", "300.00", "400.00")
    assert _find_payment_group(pool, Decimal("1000.00"), set()) is None


def test_no_group_when_total_is_off_by_a_fee():
    # exact members sum to 4847.50; a deposit $10 short (a netted fee) → no exact subset.
    pool = _pool("1890.00", "2142.50", "815.00")
    assert _find_payment_group(pool, Decimal("4837.50"), set()) is None


def test_claimed_members_are_excluded():
    pool = _pool("300.00", "200.00")  # p0=300, p1=200
    assert _find_payment_group(pool, Decimal("500.00"), {("customer_payment", "p0")}) is None


def test_group_id_is_reproducible_and_marked():
    a = _payment_group_id(["c", "a", "b"])
    b = _payment_group_id(["b", "c", "a"])  # order-independent
    assert a == b and a.startswith("grp_") and len(a) <= 36


# ── DB fixture ───────────────────────────────────────────────────────────────
@pytest.fixture
def env():
    s = SessionLocal()
    sfx = uuid.uuid4().hex[:8]
    co = Company(id=str(uuid.uuid4()), name=f"B5 {sfx}", slug=f"{_SLUG}{sfx}",
                 is_active=True, vertical="manufacturing")
    s.add(co); s.flush()
    role = Role(id=str(uuid.uuid4()), company_id=co.id, name="Admin", slug="admin")
    s.add(role); s.flush()
    user = User(id=str(uuid.uuid4()), company_id=co.id, role_id=role.id,
                email=f"b5-{sfx}@test.local", hashed_password="x",
                first_name="B", last_name="Five", is_active=True)
    s.add(user); s.flush()
    acct = FinancialAccount(id=str(uuid.uuid4()), tenant_id=co.id,
                            account_type="checking", account_name="Operating")
    s.add(acct)
    run = ReconciliationRun(id=str(uuid.uuid4()), tenant_id=co.id, financial_account_id=acct.id,
                            statement_date=date(2026, 7, 31), statement_closing_balance=Decimal("0"),
                            period_start=date(2026, 7, 1), opening_balance=Decimal("0"))
    s.add(run); s.commit()
    yield type("E", (), {"s": s, "co": co.id, "user": user, "run": run})()
    s.rollback()
    try:
        purge_companies_by_slug(s, f"{_SLUG}%")
    finally:
        s.close()


def _cp(env, total, day=15):
    cust = Customer(id=str(uuid.uuid4()), company_id=env.co, name="Cust", is_active=True)
    env.s.add(cust); env.s.flush()
    p = CustomerPayment(id=str(uuid.uuid4()), company_id=env.co, customer_id=cust.id,
                        payment_date=datetime(2026, 7, day, 12, tzinfo=timezone.utc),
                        total_amount=Decimal(total), payment_method="check")
    env.s.add(p); env.s.flush()
    return p


def _txn(env, *, amount, day=15, with_exception=True, order=0):
    t = ReconciliationTransaction(
        id=str(uuid.uuid4()), tenant_id=env.co, reconciliation_run_id=env.run.id,
        transaction_date=date(2026, 7, day), description=f"deposit {amount}",
        amount=Decimal(amount), transaction_type="credit", match_status="unmatched", sort_order=order)
    env.s.add(t); env.s.flush()
    e = None
    if with_exception:
        e = ReconciliationException(id=str(uuid.uuid4()), tenant_id=env.co,
                                    reconciliation_transaction_id=t.id, reconciliation_run_id=env.run.id)
        env.s.add(e); env.s.flush()
    return t, e


def _group_candidate(env, txn, members):
    ids = [m[0] for m in members]
    c = ReconciliationMatchCandidate(
        id=str(uuid.uuid4()), tenant_id=env.co, reconciliation_transaction_id=txn.id,
        candidate_record_type="payment_group", candidate_record_id=_payment_group_id(ids),
        score=Decimal("0.850"), rank=1, rejection_reason=None,
        rejection_detail={
            "member_count": len(members),
            "member_total": str(sum((Decimal(m[1]) for m in members), Decimal(0))),
            "members": [{"type": "customer_payment", "id": m[0], "amount": m[1]} for m in members],
        })
    env.s.add(c); env.s.flush()
    return c


def _ctx(env, txn_id, **payload):
    return {"db": env.s, "user": env.user, "entity_type": "reconciliation_exception",
            "entity_id": txn_id, "queue_id": "reconciliation_review_triage",
            "action_id": "accept", "reason": None, "reason_code": None,
            "note": None, "payload": payload}


def _claim_ids(env):
    return {cl.payment_id for cl in env.s.query(ReconciliationPaymentClaim).filter(
        ReconciliationPaymentClaim.tenant_id == env.co).all()}


# ── matcher surfaces the group ───────────────────────────────────────────────
def test_run_matching_surfaces_a_combined_candidate(env):
    t, _e = _txn(env, amount="4847.50", with_exception=False)
    _cp(env, "1890.00"); _cp(env, "2142.50"); _cp(env, "815.00")
    env.s.commit()
    run_matching(env.s, env.run, env.co)
    env.s.commit()
    groups = env.s.query(ReconciliationMatchCandidate).filter(
        ReconciliationMatchCandidate.reconciliation_transaction_id == t.id,
        ReconciliationMatchCandidate.candidate_record_type == "payment_group").all()
    assert len(groups) == 1
    detail = groups[0].rejection_detail
    assert detail["member_count"] == 3 and detail["member_total"] == "4847.50"


# ── the CHECK ────────────────────────────────────────────────────────────────
def test_candidate_record_type_check_rejects_unknown_type(env):
    t, _e = _txn(env, amount="100.00")
    env.s.add(ReconciliationMatchCandidate(
        id=str(uuid.uuid4()), tenant_id=env.co, reconciliation_transaction_id=t.id,
        candidate_record_type="bogus_type", candidate_record_id="x",
        score=Decimal("0.5"), rank=1))
    with pytest.raises(IntegrityError):
        env.s.commit()
    env.s.rollback()


# ── accept: all-or-none ──────────────────────────────────────────────────────
def test_accept_group_claims_all_members(env):
    t, e = _txn(env, amount="4847.50")
    p1, p2, p3 = _cp(env, "1890.00"), _cp(env, "2142.50"), _cp(env, "815.00")
    c = _group_candidate(env, t, [(p1.id, "1890.00"), (p2.id, "2142.50"), (p3.id, "815.00")])
    env.s.commit()

    res = _handle_reconciliation_accept(_ctx(env, t.id, candidate_id=c.id))
    env.s.commit()
    assert res["status"] == "applied"
    env.s.refresh(t); env.s.refresh(e)
    assert t.match_status == "manually_matched"
    assert t.matched_record_type == "payment_group"
    assert t.matched_record_id == c.candidate_record_id
    assert e.resolved is True
    assert _claim_ids(env) == {p1.id, p2.id, p3.id}  # all three


def test_accept_group_is_all_or_none_when_a_member_is_preclaimed(env):
    # THE pin: member 2 already claimed by another transaction → the whole accept
    # fails, ZERO new claims, the transaction stays unmatched. A partial claim
    # (p1 + p3 claimed, p2 not) would be worse than not supporting one-to-many.
    t, e = _txn(env, amount="4847.50")
    p1, p2, p3 = _cp(env, "1890.00"), _cp(env, "2142.50"), _cp(env, "815.00")
    c = _group_candidate(env, t, [(p1.id, "1890.00"), (p2.id, "2142.50"), (p3.id, "815.00")])
    dummy, _ = _txn(env, amount="1.00", with_exception=False, order=9)
    env.s.add(ReconciliationPaymentClaim(
        tenant_id=env.co, payment_type="customer_payment", payment_id=p2.id,
        reconciliation_transaction_id=dummy.id, reconciliation_run_id=env.run.id))
    env.s.commit()

    res = _handle_reconciliation_accept(_ctx(env, t.id, candidate_id=c.id))
    env.s.commit()
    assert res["status"] == "errored"
    env.s.refresh(t); env.s.refresh(e)
    assert t.match_status == "unmatched"          # no partial state
    assert e.resolved is False
    assert _claim_ids(env) == {p2.id}             # only the pre-existing; p1/p3 NOT claimed
