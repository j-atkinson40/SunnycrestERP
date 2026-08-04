"""Books Review Arc B B-4 — flag / park substrate + the two return hooks.

Pins the operator's review criteria:
  * the return trigger is a DISCRIMINATED SHAPE — return_trigger_kind names the
    mechanism (task_completed / document_attached / terminal), legible from the row;
  * NO scheduler — ask returns via the task-completion subscriber (registered),
    hold returns via a synchronous document-attach hook, terminal has no evaluator;
  * the flag_id FK is real (bogus id → IntegrityError; deleting a flag SET NULLs it);
  * terminal ("accept as a reconciling item") flows the amount to the run's
    reconciling difference (adjustments_total + difference), hand-proven;
  * SAME exception reopens on return (flag_id cleared), park row kept as history.

Cleans up its own `b4rec-*` tenants via the shared FK-safe helper.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

import app.services.tasks  # noqa: F401 — activates the subscriber registry
from app.database import SessionLocal
from app.models.company import Company
from app.models.financial_account import (
    FinancialAccount,
    ReconciliationException,
    ReconciliationFlag,
    ReconciliationRun,
    ReconciliationTransaction,
)
from app.models.role import Role
from app.models.user import User
from app.services import reconciliation_flags
from app.services.agents.period_lock import PeriodLockService
from app.services.tasks.subscribers.registry import emit_event, get_subscribers
from app.services.triage.action_handlers import _handle_reconciliation_flag
from app.services.triage.engine import _dq_reconciliation_review
from tests._cleanup import purge_companies_by_slug

_SLUG = "b4rec-"


@pytest.fixture
def env():
    s = SessionLocal()
    sfx = uuid.uuid4().hex[:8]
    co = Company(id=str(uuid.uuid4()), name=f"B4 {sfx}", slug=f"{_SLUG}{sfx}",
                 is_active=True, vertical="manufacturing")
    s.add(co); s.flush()
    role = Role(id=str(uuid.uuid4()), company_id=co.id, name="Admin", slug="admin")
    s.add(role); s.flush()
    user = User(id=str(uuid.uuid4()), company_id=co.id, role_id=role.id,
                email=f"b4-{sfx}@test.local", hashed_password="x",
                first_name="B", last_name="Four", is_active=True)
    recipient = User(id=str(uuid.uuid4()), company_id=co.id, role_id=role.id,
                     email=f"b4r-{sfx}@test.local", hashed_password="x",
                     first_name="Dana", last_name="R", is_active=True)
    s.add_all([user, recipient]); s.flush()
    acct = FinancialAccount(id=str(uuid.uuid4()), tenant_id=co.id,
                            account_type="checking", account_name="Operating")
    s.add(acct)
    run = ReconciliationRun(id=str(uuid.uuid4()), tenant_id=co.id, financial_account_id=acct.id,
                            statement_date=date(2026, 7, 31), statement_closing_balance=Decimal("0"),
                            period_start=date(2026, 7, 1), opening_balance=Decimal("0"),
                            outstanding_checks_total=Decimal("0"), outstanding_deposits_total=Decimal("0"))
    s.add(run); s.commit()
    yield type("E", (), {"s": s, "co": co.id, "user": user, "recipient": recipient, "run": run})()
    s.rollback()
    try:
        purge_companies_by_slug(s, f"{_SLUG}%")
    finally:
        s.close()


def _txn(env, *, amount="377.00", day=15, status="unmatched"):
    t = ReconciliationTransaction(
        id=str(uuid.uuid4()), tenant_id=env.co, reconciliation_run_id=env.run.id,
        transaction_date=date(2026, 7, day), description=f"deposit {amount}",
        amount=Decimal(amount), transaction_type="credit", match_status=status, sort_order=0)
    env.s.add(t); env.s.flush()
    e = ReconciliationException(id=str(uuid.uuid4()), tenant_id=env.co,
                               reconciliation_transaction_id=t.id, reconciliation_run_id=env.run.id)
    env.s.add(e); env.s.flush()
    return t, e


def _in_queue(env, txn_id):
    return txn_id in {r["id"] for r in _dq_reconciliation_review(env.s, env.user)}


def _ctx(env, txn_id, **payload):
    return {"db": env.s, "user": env.user, "entity_type": "reconciliation_exception",
            "entity_id": txn_id, "queue_id": "reconciliation_review_triage",
            "action_id": "flag", "reason": None, "reason_code": None,
            "note": payload.pop("note", None), "payload": payload}


# ── the discriminated return trigger ─────────────────────────────────────────
def test_return_trigger_kind_names_the_mechanism_per_destination(env):
    t1, e1 = _txn(env); t2, e2 = _txn(env); t3, e3 = _txn(env)
    f_ask = reconciliation_flags.create_flag(env.s, user=env.user, txn=t1, exception=e1,
                                             destination="ask_someone", recipient_user_id=env.recipient.id)
    f_hold = reconciliation_flags.create_flag(env.s, user=env.user, txn=t2, exception=e2,
                                              destination="hold_for_documentation")
    f_term = reconciliation_flags.create_flag(env.s, user=env.user, txn=t3, exception=e3,
                                              destination="accept_reconciling")
    env.s.commit()
    assert f_ask.return_trigger_kind == "task_completed" and f_ask.task_id is not None
    assert f_hold.return_trigger_kind == "document_attached"
    assert f_term.return_trigger_kind == "terminal" and f_term.returned_at is not None


# ── no scheduler — the hook is wired ─────────────────────────────────────────
def test_task_completion_subscriber_is_registered_no_sweep(env):
    assert "reconciliation_flag_returner" in get_subscribers()


# ── ask someone: parks + creates task + leaves queue; return reopens SAME exc ─
def test_ask_someone_parks_and_task_completion_reopens_same_exception(env):
    t, e = _txn(env)
    res = _handle_reconciliation_flag(_ctx(env, t.id, destination="ask_someone",
                                          recipient_user_id=env.recipient.id, note="who is this from?"))
    env.s.commit()
    assert res["status"] == "applied"
    env.s.refresh(e)
    assert e.flag_id is not None                 # actively parked
    assert not _in_queue(env, t.id)              # out of the queue
    flag = env.s.query(ReconciliationFlag).filter(ReconciliationFlag.id == e.flag_id).one()
    assert flag.task_id is not None

    # complete the task → the SAME exception reopens (via the registry subscriber).
    emit_event(env.s, event_type="task_completed", task_details_id=str(uuid.uuid4()),
               actor_user_id=env.recipient.id, payload={"vault_item_id": flag.task_id})
    env.s.commit()
    env.s.refresh(e); env.s.refresh(flag)
    assert e.flag_id is None                      # reopened — SAME exception
    assert _in_queue(env, t.id)
    assert flag.returned_at is not None           # park row persists as history


# ── hold for docs: synchronous document-attach hook returns it ───────────────
def test_hold_for_docs_returns_synchronously_on_document_attach(env):
    t, e = _txn(env)
    reconciliation_flags.create_flag(env.s, user=env.user, txn=t, exception=e,
                                     destination="hold_for_documentation")
    env.s.commit()
    assert not _in_queue(env, t.id)

    n = reconciliation_flags.return_flags_on_document_attach(env.s, e.id, document_id="doc-123")
    env.s.commit()
    assert n == 1
    env.s.refresh(e)
    assert e.flag_id is None and _in_queue(env, t.id)
    flag = env.s.query(ReconciliationFlag).filter(
        ReconciliationFlag.reconciliation_exception_id == e.id).one()
    assert flag.returned_at is not None and "doc-123" in (flag.return_note or "")


# ── terminal: amount flows to the run's reconciling difference ───────────────
def test_accept_reconciling_flows_amount_to_run_summary(env):
    t, e = _txn(env, amount="377.00")
    # HAND MATH: run starts adjustments_total 0; one reconciling item of 377.00
    # → adjustments_total = 0 + 377.00 = 377.00.
    reconciliation_flags.create_flag(env.s, user=env.user, txn=t, exception=e,
                                     destination="accept_reconciling", note="bank interest")
    env.s.commit()
    env.s.refresh(t); env.s.refresh(e); env.s.refresh(env.run)
    assert env.run.adjustments_total == Decimal("377.00")   # money landed in the summary
    assert t.match_status == "reconciling_item"             # off "unmatched"
    assert e.resolved is True
    assert not _in_queue(env, t.id)


def test_accept_reconciling_is_period_lock_gated(env):
    t, e = _txn(env, amount="377.00")
    PeriodLockService.lock_period(env.s, env.co, date(2026, 7, 1), date(2026, 7, 31), reason="closed")
    env.s.commit()
    res = _handle_reconciliation_flag(_ctx(env, t.id, destination="accept_reconciling"))
    assert res["status"] == "errored" and "locked" in res["message"].lower()
    env.s.refresh(t); env.s.refresh(env.run)
    assert t.match_status == "unmatched"                    # no write into a closed period
    assert env.run.adjustments_total in (None, Decimal("0"), Decimal("0.00"))


# ── the flag_id FK is real ───────────────────────────────────────────────────
def test_flag_id_fk_rejects_a_bogus_id(env):
    _t, e = _txn(env)
    e.flag_id = "not-a-real-flag-id"
    with pytest.raises(IntegrityError):
        env.s.commit()
    env.s.rollback()


def test_deleting_a_flag_set_nulls_the_exception_link(env):
    t, e = _txn(env)
    reconciliation_flags.create_flag(env.s, user=env.user, txn=t, exception=e,
                                     destination="hold_for_documentation")
    env.s.commit()
    flag_id = e.flag_id
    assert flag_id is not None
    env.s.execute(text("DELETE FROM reconciliation_flags WHERE id=:i"), {"i": flag_id})
    env.s.commit()
    env.s.refresh(e)
    assert e.flag_id is None                                 # ondelete SET NULL


# ── guard ────────────────────────────────────────────────────────────────────
def test_cannot_flag_an_already_parked_item(env):
    t, e = _txn(env)
    reconciliation_flags.create_flag(env.s, user=env.user, txn=t, exception=e,
                                     destination="hold_for_documentation")
    env.s.commit()
    res = _handle_reconciliation_flag(_ctx(env, t.id, destination="ask_someone",
                                          recipient_user_id=env.recipient.id))
    assert res["status"] == "errored" and "parked" in res["message"].lower()
