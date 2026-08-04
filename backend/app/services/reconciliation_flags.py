"""Books Review Arc B B-4 — flag / park service.

Three destinations, THREE return mechanisms (a discriminated shape, not a uniform
timestamp):
  * ask_someone           → create a Task assigned to the recipient; the return
                            fires from the task-completion subscriber (task_id).
  * hold_for_documentation → park; the return fires SYNCHRONOUSLY when a document
                            is attached to the exception (return_flags_on_document_attach).
  * accept_reconciling    → TERMINAL: no evaluator. The amount flows to the run's
                            reconciling difference via the Arc A adjustment path
                            (create_adjustment recomputes adjustments_total +
                            difference, which the reconciliation summary reads).

NO SCHEDULER. ask/hold parks are returned by an event (task completion) or a
synchronous hook (document attach); terminal has no evaluator at all.

Same-exception-reopen: parking sets `exception.flag_id` (active park → excluded
from the queue). On return the flag's `returned_at` is stamped and `flag_id` is
CLEARED — the SAME exception reopens; the flag row persists as queryable history.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.user import User


def create_flag(
    db: Session,
    *,
    user: User,
    txn,
    exception,
    destination: str,
    note: str | None = None,
    recipient_user_id: str | None = None,
):
    """Create a park record for `exception`. Mutates in place; does NOT commit
    (the caller owns the transaction). Raises ValueError on a bad request or a
    locked period (terminal only)."""
    from app.models.financial_account import ReconciliationFlag

    now = datetime.now(timezone.utc)

    if destination == "ask_someone":
        if not recipient_user_id:
            raise ValueError("Ask someone requires a recipient.")
        flag = ReconciliationFlag(
            tenant_id=user.company_id,
            reconciliation_exception_id=exception.id,
            destination="ask_someone",
            return_trigger_kind="task_completed",
            owner_user_id=recipient_user_id,
            note=note,
            created_by=user.id,
        )
        db.add(flag)
        db.flush()
        # The Task IS the ask; its completion IS the answer. Idempotency key is
        # per-flag so a re-ask after a return creates a fresh task.
        from app.services.tasks.service import create_task_with_provenance

        td = create_task_with_provenance(
            db,
            company_id=user.company_id,
            provenance_kind="triage_event",
            provenance_ref_type="reconciliation_exception",
            provenance_ref_id=exception.id,
            event_kind=f"recon_flag_ask:{flag.id}",
            task_type_key="generic_task",
            title=f"Reconciliation question: {txn.description}",
            description=note,
            created_by_user_id=user.id,
            assignee_user_id=recipient_user_id,
        )
        flag.task_id = td.vault_item_id
        exception.flag_id = flag.id  # active park → out of queue
        return flag

    if destination == "hold_for_documentation":
        flag = ReconciliationFlag(
            tenant_id=user.company_id,
            reconciliation_exception_id=exception.id,
            destination="hold_for_documentation",
            return_trigger_kind="document_attached",
            owner_user_id=user.id,
            note=note,
            created_by=user.id,
        )
        db.add(flag)
        db.flush()
        exception.flag_id = flag.id  # active park → out of queue
        return flag

    if destination == "accept_reconciling":
        # TERMINAL — a money-affecting decision, so it hits the same period-lock
        # gate the auto/accept paths do.
        from app.services.agents.period_lock import PeriodLockService

        lock = PeriodLockService.check_date_in_locked_period(
            db, user.company_id, txn.transaction_date
        )
        if lock is not None:
            raise ValueError(
                f"Period {lock.period_start}–{lock.period_end} is locked; "
                "unlock it to accept this as a reconciling item."
            )
        flag = ReconciliationFlag(
            tenant_id=user.company_id,
            reconciliation_exception_id=exception.id,
            destination="accept_reconciling",
            return_trigger_kind="terminal",
            owner_user_id=None,
            note=note,
            created_by=user.id,
            returned_at=now,  # terminal — no waiting park
        )
        db.add(flag)
        db.flush()
        # The amount flows to the run's reconciling difference via the Arc A
        # adjustment path (recomputes adjustments_total + difference).
        from app.services.reconciliation_service import create_adjustment

        create_adjustment(
            db,
            run_id=txn.reconciliation_run_id,
            company_id=user.company_id,
            created_by=user.id,
            adjustment_type="reconciling_item",
            description=note or f"Reconciling item: {txn.description}",
            amount=txn.amount,
        )
        txn.match_status = "reconciling_item"  # off "unmatched" → out of queue
        txn.reviewed_by = user.id
        txn.reviewed_at = now
        exception.resolved = True
        exception.resolved_by = user.id
        exception.resolved_at = now
        exception.resolution_note = note
        return flag

    raise ValueError(f"Unknown flag destination: {destination!r}")


def return_flags_on_task_completed(db: Session, vault_item_id: str, *, return_note: str | None = None) -> int:
    """Return every active task_completed park whose task matches. The SAME
    exception reopens (flag_id cleared); the flag row stays as history. Returns
    the count returned. Does NOT commit."""
    from app.models.financial_account import ReconciliationException, ReconciliationFlag

    now = datetime.now(timezone.utc)
    flags = (
        db.query(ReconciliationFlag)
        .filter(
            ReconciliationFlag.task_id == vault_item_id,
            ReconciliationFlag.return_trigger_kind == "task_completed",
            ReconciliationFlag.returned_at.is_(None),
        )
        .all()
    )
    for flag in flags:
        flag.returned_at = now
        if return_note:
            flag.return_note = return_note
        exc = (
            db.query(ReconciliationException)
            .filter(ReconciliationException.id == flag.reconciliation_exception_id)
            .first()
        )
        if exc is not None and exc.flag_id == flag.id:
            exc.flag_id = None  # SAME exception reopens
    return len(flags)


def return_flags_on_document_attach(
    db: Session, exception_id: str, *, document_id: str | None = None, return_note: str | None = None
) -> int:
    """SYNCHRONOUS return hook — called by the document-attach action. Returns
    every active document_attached park on the exception. Does NOT commit."""
    from app.models.financial_account import ReconciliationException, ReconciliationFlag

    now = datetime.now(timezone.utc)
    flags = (
        db.query(ReconciliationFlag)
        .filter(
            ReconciliationFlag.reconciliation_exception_id == exception_id,
            ReconciliationFlag.return_trigger_kind == "document_attached",
            ReconciliationFlag.returned_at.is_(None),
        )
        .all()
    )
    note = return_note or (f"document {document_id} attached" if document_id else "document attached")
    for flag in flags:
        flag.returned_at = now
        flag.return_note = note
        exc = (
            db.query(ReconciliationException)
            .filter(ReconciliationException.id == exception_id)
            .first()
        )
        if exc is not None and exc.flag_id == flag.id:
            exc.flag_id = None  # SAME exception reopens
    return len(flags)
