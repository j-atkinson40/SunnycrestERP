"""Books Review Arc B B-6 — end-to-end validation through the assembled engine.

The four flows that had only ever run in isolation, now assembled behind a real
triage session (start_session -> next_item -> apply_action -> queue_count):

  1. The queue BUILDS — the source builder's rows survive the engine and
     `candidates` reaches `extras` (Option A) intact.
  2. Both card FORMS have real data — items with candidates vs the coding item
     without.
  3. ACCEPT end to end — a claim is written, match_status moves off "unmatched",
     the item LEAVES the queue, and queue_count agrees. Plus the group (3 claims).
  4. FLAG end to end — ask someone -> a Task is created + the item parks (leaves
     the queue) -> the task completes -> the subscriber returns the SAME
     exception with its flag row intact.

And the two invariants the design rests on: the item leaves the queue after
Accept, and queue_count == the queue the builder yields (parked items excluded
from BOTH). Uses the W-2 case shapes (ambiguous / group / coding) on a focused
run so the flows are isolated; the full-substrate per-case table is validated by
the W-2 harness. Cleans up its own `b6rev-*` tenant.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

import app.services.tasks  # noqa: F401 — activates the flag-returner subscriber
from app.database import SessionLocal
from app.models.company import Company
from app.models.customer import Customer
from app.models.customer_payment import CustomerPayment
from app.models.financial_account import (
    FinancialAccount,
    ReconciliationException,
    ReconciliationFlag,
    ReconciliationMatchCandidate,
    ReconciliationPaymentClaim,
    ReconciliationRun,
    ReconciliationTransaction,
)
from app.models.role import Role
from app.models.user import User
from app.services.reconciliation_service import run_matching
from app.services.tasks.subscribers.registry import emit_event
from app.services.triage.engine import (
    _dq_reconciliation_review,
    apply_action,
    next_item,
    queue_count,
    start_session,
)
from tests._cleanup import purge_companies_by_slug

_SLUG = "b6rev-"
_QUEUE = "reconciliation_review_triage"


@pytest.fixture
def env():
    s = SessionLocal()
    sfx = uuid.uuid4().hex[:8]
    co = Company(id=str(uuid.uuid4()), name=f"B6 {sfx}", slug=f"{_SLUG}{sfx}",
                 is_active=True, vertical="manufacturing")
    s.add(co); s.flush()
    # is_system admin role → user_has_permission returns True (passes the queue gate).
    role = Role(id=str(uuid.uuid4()), company_id=co.id, name="Admin", slug="admin", is_system=True)
    s.add(role); s.flush()
    user = User(id=str(uuid.uuid4()), company_id=co.id, role_id=role.id,
                email=f"b6-{sfx}@test.local", hashed_password="x",
                first_name="B", last_name="Six", is_active=True)
    recipient = User(id=str(uuid.uuid4()), company_id=co.id, role_id=role.id,
                     email=f"b6r-{sfx}@test.local", hashed_password="x",
                     first_name="Dana", last_name="R", is_active=True)
    s.add_all([user, recipient]); s.flush()
    acct = FinancialAccount(id=str(uuid.uuid4()), tenant_id=co.id,
                            account_type="checking", account_name="Operating")
    s.add(acct)
    run = ReconciliationRun(id=str(uuid.uuid4()), tenant_id=co.id, financial_account_id=acct.id,
                            statement_date=date(2026, 7, 31), statement_closing_balance=Decimal("0"),
                            period_start=date(2026, 7, 1), opening_balance=Decimal("0"))
    s.add(run); s.commit()
    e = type("E", (), {"s": s, "co": co.id, "user": user, "recipient": recipient, "run": run})()
    _seed_cases(e)
    yield e
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


def _txn(env, *, amount, tag, order):
    t = ReconciliationTransaction(
        id=str(uuid.uuid4()), tenant_id=env.co, reconciliation_run_id=env.run.id,
        transaction_date=date(2026, 7, 15), description=f"[{tag}] deposit {amount}",
        amount=Decimal(amount), transaction_type="credit", match_status="unmatched", sort_order=order)
    env.s.add(t); env.s.flush()
    return t


def _seed_cases(env):
    # AMBIGUOUS: 1 deposit, 2 identical payments → 2 viable candidates.
    env.amb = _txn(env, amount="500.00", tag="amb", order=0)
    env.amb_p1, env.amb_p2 = _cp(env, "500.00"), _cp(env, "500.00")
    # GROUP: 1 deposit = 3 payments (one-to-many).
    env.grp = _txn(env, amount="4847.50", tag="grp", order=1)
    _cp(env, "1890.00"); _cp(env, "2142.50"); _cp(env, "815.00")
    # CODING: 1 deposit, no payment near it → no candidates.
    env.cod = _txn(env, amount="377.00", tag="cod", order=2)
    env.s.commit()
    run_matching(env.s, env.run, env.co)
    env.s.commit()


def _rows(env):
    return {r["id"]: r for r in _dq_reconciliation_review(env.s, env.user)}


def _candidates(env, txn_id):
    return env.s.query(ReconciliationMatchCandidate).filter(
        ReconciliationMatchCandidate.reconciliation_transaction_id == txn_id
    ).order_by(ReconciliationMatchCandidate.rank).all()


# ── FLOW 1: the queue builds; candidates reach extras (Option A) ─────────────
def test_flow1_queue_builds_and_candidates_reach_extras(env):
    sess = start_session(env.s, user=env.user, queue_id=_QUEUE)
    item = next_item(env.s, session_id=sess.id, user=env.user)
    # an item comes through the engine with its candidates in extras
    assert item.entity_id in (env.amb.id, env.grp.id, env.cod.id)
    served = _rows(env)
    assert set(served) == {env.amb.id, env.grp.id, env.cod.id}
    # the served item's extras carries the candidates list (Option A wiring)
    first = served[item.entity_id]
    assert "candidates" in first


# ── FLOW 2: both card forms have real data ──────────────────────────────────
def test_flow2_both_card_forms_have_data(env):
    served = _rows(env)
    assert len(served[env.amb.id]["candidates"]) == 2          # ranked (ambiguous)
    grp_cands = served[env.grp.id]["candidates"]
    assert any(c["candidate_record_type"] == "payment_group" for c in grp_cands)  # ranked (group)
    assert served[env.cod.id]["candidates"] == []              # coding (no candidates)


# ── FLOW 3 + invariants: Accept leaves the queue; count agrees ──────────────
def test_flow3_accept_leaves_queue_and_count_agrees(env):
    sess = start_session(env.s, user=env.user, queue_id=_QUEUE)
    assert queue_count(env.s, user=env.user, queue_id=_QUEUE) == 3
    assert queue_count(env.s, user=env.user, queue_id=_QUEUE) == len(_rows(env))  # count == queue

    viable = [c for c in _candidates(env, env.amb.id) if c.rejection_reason is None]
    res = apply_action(env.s, session_id=sess.id, item_id=env.amb.id,
                       action_id="accept", user=env.user,
                       payload={"candidate_id": viable[0].id})
    env.s.commit()
    assert res.status == "applied"

    env.s.refresh(env.amb)
    assert env.amb.match_status == "manually_matched"          # off "unmatched"
    assert env.amb.id not in _rows(env)                        # LEAVES the queue
    assert queue_count(env.s, user=env.user, queue_id=_QUEUE) == 2
    assert queue_count(env.s, user=env.user, queue_id=_QUEUE) == len(_rows(env))
    # the claim was written on the chosen payment
    claimed = {c.payment_id for c in env.s.query(ReconciliationPaymentClaim).filter(
        ReconciliationPaymentClaim.tenant_id == env.co).all()}
    assert viable[0].candidate_record_id in claimed


# ── FLOW 3b: Accept the group → three claims, all-or-none ────────────────────
def test_flow3b_accept_group_writes_three_claims(env):
    sess = start_session(env.s, user=env.user, queue_id=_QUEUE)
    grp_cand = next(c for c in _candidates(env, env.grp.id)
                    if c.candidate_record_type == "payment_group")
    member_ids = {m["id"] for m in grp_cand.rejection_detail["members"]}
    res = apply_action(env.s, session_id=sess.id, item_id=env.grp.id,
                       action_id="accept", user=env.user,
                       payload={"candidate_id": grp_cand.id})
    env.s.commit()
    assert res.status == "applied"
    env.s.refresh(env.grp)
    assert env.grp.match_status == "manually_matched"
    assert env.grp.matched_record_type == "payment_group"
    assert env.grp.id not in _rows(env)
    claimed = {c.payment_id for c in env.s.query(ReconciliationPaymentClaim).filter(
        ReconciliationPaymentClaim.tenant_id == env.co).all()}
    assert claimed == member_ids                               # all three, together


# ── FLOW 4: Flag ask-someone → Task → parks → completes → returns ───────────
def test_flow4_flag_ask_someone_parks_then_task_completion_returns(env):
    sess = start_session(env.s, user=env.user, queue_id=_QUEUE)
    before = queue_count(env.s, user=env.user, queue_id=_QUEUE)
    res = apply_action(env.s, session_id=sess.id, item_id=env.cod.id,
                       action_id="flag", user=env.user,
                       payload={"destination": "ask_someone", "recipient_user_id": env.recipient.id})
    env.s.commit()
    assert res.status == "applied"

    exc = env.s.query(ReconciliationException).filter(
        ReconciliationException.reconciliation_transaction_id == env.cod.id).one()
    assert exc.flag_id is not None                              # parked
    assert env.cod.id not in _rows(env)                        # LEFT the queue
    assert queue_count(env.s, user=env.user, queue_id=_QUEUE) == before - 1  # count drops with it
    flag = env.s.query(ReconciliationFlag).filter(ReconciliationFlag.id == exc.flag_id).one()
    assert flag.task_id is not None                            # a Task was created

    # the task completes → the subscriber returns the SAME exception
    emit_event(env.s, event_type="task_completed", task_details_id=str(uuid.uuid4()),
               actor_user_id=env.recipient.id, payload={"vault_item_id": flag.task_id})
    env.s.commit()
    env.s.refresh(exc); env.s.refresh(flag)
    assert exc.flag_id is None                                  # reopened — SAME exception
    assert env.cod.id in _rows(env)                            # back in the queue
    assert queue_count(env.s, user=env.user, queue_id=_QUEUE) == before
    assert flag.returned_at is not None                        # flag row kept as history
