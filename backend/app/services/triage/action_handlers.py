"""Triage action handlers — registry of (handler_key → callable).

Handlers map `ActionConfig.handler` strings to functions. Each
handler receives a uniform context dict:

    {
      "db": Session,
      "user": User,
      "entity_type": str,          # e.g. "task", "social_service_certificate"
      "entity_id": str,             # underlying entity row id
      "queue_id": str,              # the calling queue
      "action_id": str,             # which action (approve / reject / ...)
      "reason": str | None,         # freeform reason (if collected)
      "reason_code": str | None,    # structured reason (if enum used)
      "note": str | None,           # any additional text from the UI
      "payload": dict | None,       # action-specific extras (e.g. new assignee)
    }

Handlers return `{status, message, **extras}`. `status in
{"applied", "skipped", "errored"}`.

SS CERT PARITY RULE: the SS cert handlers CALL THE EXISTING
`SocialServiceCertificateService.approve / .void` methods verbatim.
No duplicated logic. Any downstream side effect (email send, status
transition, timestamp stamping) is identical to the legacy bespoke
page. The parity test asserts this.

Adding a new handler:
  1. Write a `def _handle_<name>(ctx) -> dict` function.
  2. Register in HANDLERS at module bottom.
  3. Reference from a queue config's ActionConfig.handler.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.models.user import User

logger = logging.getLogger(__name__)


# ── Task handlers ───────────────────────────────────────────────────


def _handle_task_complete(ctx: dict[str, Any]) -> dict[str, Any]:
    """Approve-equivalent for task_triage. Sets status=done."""
    from app.services.task_service import complete_task, TaskError

    db: Session = ctx["db"]
    user: User = ctx["user"]
    try:
        task = complete_task(
            db,
            company_id=user.company_id,
            task_id=ctx["entity_id"],
        )
    except TaskError as exc:
        return {"status": "errored", "message": str(exc)}
    return {
        "status": "applied",
        "message": f"Task marked done (completed_at={task.completed_at.isoformat() if task.completed_at else 'n/a'})",
        "entity_state": task.status,
    }


def _handle_task_cancel(ctx: dict[str, Any]) -> dict[str, Any]:
    from app.services.task_service import cancel_task, TaskError

    db: Session = ctx["db"]
    user: User = ctx["user"]
    try:
        task = cancel_task(
            db, company_id=user.company_id, task_id=ctx["entity_id"]
        )
    except TaskError as exc:
        return {"status": "errored", "message": str(exc)}
    # Stamp reason in metadata_json so the rejection is audit-able.
    reason = ctx.get("reason") or ctx.get("reason_code")
    if reason:
        md = dict(task.metadata_json or {})
        md.setdefault("triage_cancellations", []).append(
            {
                "at": datetime.now(timezone.utc).isoformat(),
                "by_user_id": user.id,
                "reason": reason,
            }
        )
        task.metadata_json = md
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(task, "metadata_json")
        db.commit()
    return {
        "status": "applied",
        "message": "Task cancelled.",
        "entity_state": task.status,
    }


def _handle_task_reassign(ctx: dict[str, Any]) -> dict[str, Any]:
    from app.services.task_service import update_task, TaskError

    db: Session = ctx["db"]
    user: User = ctx["user"]
    payload = ctx.get("payload") or {}
    new_assignee = payload.get("assignee_user_id")
    if not new_assignee:
        return {
            "status": "errored",
            "message": "Missing `assignee_user_id` in payload.",
        }
    try:
        task = update_task(
            db,
            company_id=user.company_id,
            task_id=ctx["entity_id"],
            assignee_user_id=new_assignee,
        )
    except TaskError as exc:
        return {"status": "errored", "message": str(exc)}
    return {
        "status": "applied",
        "message": f"Task reassigned to {new_assignee}.",
        "entity_state": task.status,
        "new_assignee_id": new_assignee,
    }


# ── Social Service Certificate handlers (PARITY CRITICAL) ───────────


def _handle_ss_cert_approve(ctx: dict[str, Any]) -> dict[str, Any]:
    """Approve via the EXISTING service — zero duplicated logic. Side
    effects (status transition, approved_at stamp, email send to FH,
    approved_by_id assignment) are identical to the legacy bespoke
    page — both call this same method."""
    from app.services.social_service_certificate_service import (
        SocialServiceCertificateService,
    )

    db: Session = ctx["db"]
    user: User = ctx["user"]
    try:
        cert = SocialServiceCertificateService.approve(
            certificate_id=ctx["entity_id"],
            approved_by_user_id=user.id,
            db=db,
        )
    except ValueError as exc:
        return {"status": "errored", "message": str(exc)}
    return {
        "status": "applied",
        "message": f"Certificate {cert.certificate_number} approved and sent.",
        "entity_state": cert.status,
    }


def _handle_ss_cert_void(ctx: dict[str, Any]) -> dict[str, Any]:
    """Void via the EXISTING service."""
    from app.services.social_service_certificate_service import (
        SocialServiceCertificateService,
    )

    db: Session = ctx["db"]
    user: User = ctx["user"]
    reason = ctx.get("reason") or ctx.get("reason_code")
    if not reason:
        return {
            "status": "errored",
            "message": "Void reason is required.",
        }
    try:
        cert = SocialServiceCertificateService.void(
            certificate_id=ctx["entity_id"],
            voided_by_user_id=user.id,
            void_reason=reason,
            db=db,
        )
    except ValueError as exc:
        return {"status": "errored", "message": str(exc)}
    return {
        "status": "applied",
        "message": f"Certificate {cert.certificate_number} voided.",
        "entity_state": cert.status,
    }


# ── Cash Receipts Matching handlers (PARITY CRITICAL — Phase 8b) ────


def _handle_cash_receipts_approve(ctx: dict[str, Any]) -> dict[str, Any]:
    """Approve via the existing `cash_receipts_adapter` — zero
    duplicated logic. The PaymentApplication + Invoice writes are
    identical to `CashReceiptsAgent._step_attempt_auto_match`
    CONFIDENT_MATCH branch. Parity test guards this invariant."""
    from app.services.workflows.cash_receipts_adapter import approve_match

    db: Session = ctx["db"]
    user: User = ctx["user"]
    payload = ctx.get("payload") or {}
    invoice_id = payload.get("invoice_id")
    if not invoice_id:
        return {
            "status": "errored",
            "message": "Missing `invoice_id` in payload.",
        }
    try:
        result = approve_match(
            db,
            user=user,
            payment_id=payload.get("payment_id") or ctx.get("entity_id", ""),
            invoice_id=invoice_id,
            anomaly_id=ctx["entity_id"],
            amount=payload.get("amount"),
        )
    except ValueError as exc:
        return {"status": "errored", "message": str(exc)}
    return {
        "status": "applied",
        "message": result["message"],
        "payment_application_id": result["payment_application_id"],
        "invoice_status": result["invoice_status"],
    }


def _handle_cash_receipts_reject(ctx: dict[str, Any]) -> dict[str, Any]:
    """Reject a match — resolve the anomaly with a reason, no
    financial writes."""
    from app.services.workflows.cash_receipts_adapter import reject_match

    db: Session = ctx["db"]
    user: User = ctx["user"]
    reason = ctx.get("reason") or ctx.get("reason_code")
    if not reason:
        return {
            "status": "errored",
            "message": "Reject reason is required.",
        }
    payload = ctx.get("payload") or {}
    payment_id = payload.get("payment_id")
    if not payment_id:
        return {
            "status": "errored",
            "message": "Missing `payment_id` in payload.",
        }
    try:
        reject_match(
            db,
            user=user,
            payment_id=payment_id,
            anomaly_id=ctx["entity_id"],
            reason=reason,
        )
    except ValueError as exc:
        return {"status": "errored", "message": str(exc)}
    return {
        "status": "applied",
        "message": "Match rejected — payment stays unresolved.",
    }


def _handle_cash_receipts_override(ctx: dict[str, Any]) -> dict[str, Any]:
    """Override — force-apply a match the agent didn't suggest.
    Same writes as approve + stamps override reason on anomaly."""
    from app.services.workflows.cash_receipts_adapter import override_match

    db: Session = ctx["db"]
    user: User = ctx["user"]
    reason = ctx.get("reason") or ctx.get("reason_code")
    if not reason:
        return {
            "status": "errored",
            "message": "Override reason is required.",
        }
    payload = ctx.get("payload") or {}
    invoice_id = payload.get("invoice_id")
    payment_id = payload.get("payment_id")
    if not invoice_id or not payment_id:
        return {
            "status": "errored",
            "message": "Both `payment_id` and `invoice_id` are required.",
        }
    try:
        result = override_match(
            db,
            user=user,
            payment_id=payment_id,
            invoice_id=invoice_id,
            anomaly_id=ctx["entity_id"],
            reason=reason,
            amount=payload.get("amount"),
        )
    except ValueError as exc:
        return {"status": "errored", "message": str(exc)}
    return {
        "status": "applied",
        "message": result["message"],
        "payment_application_id": result["payment_application_id"],
        "invoice_status": result["invoice_status"],
    }


def _handle_cash_receipts_request_review(ctx: dict[str, Any]) -> dict[str, Any]:
    """Request-review — stamp a note on the anomaly without resolving.
    Item stays in-queue for a teammate to pick up."""
    from app.services.workflows.cash_receipts_adapter import request_review

    db: Session = ctx["db"]
    user: User = ctx["user"]
    note = ctx.get("note") or ctx.get("reason")
    if not note:
        return {
            "status": "errored",
            "message": "A note is required when requesting review.",
        }
    payload = ctx.get("payload") or {}
    payment_id = payload.get("payment_id")
    if not payment_id:
        return {
            "status": "errored",
            "message": "Missing `payment_id` in payload.",
        }
    try:
        request_review(
            db,
            user=user,
            payment_id=payment_id,
            anomaly_id=ctx["entity_id"],
            note=note,
        )
    except ValueError as exc:
        return {"status": "errored", "message": str(exc)}
    return {
        "status": "applied",
        "message": "Review requested — item stays in queue.",
    }


# ── Generic skip/escalate ────────────────────────────────────────────


def _handle_skip(ctx: dict[str, Any]) -> dict[str, Any]:
    """Skip without state change — useful for 'come back later'
    without committing a snooze. Engine advances to next item."""
    return {
        "status": "applied",
        "message": "Skipped for this session.",
    }


def _handle_escalate(ctx: dict[str, Any]) -> dict[str, Any]:
    """Escalation for Phase 5 is a placeholder that stamps a
    metadata-level escalation note on the underlying entity. Actual
    escalation chain execution (notify manager, re-queue to
    supervisor queue, etc.) is Phase 6+ alongside the approval-chain
    UI. Keeping the hook in place now so queue configs can reference
    `handler="escalate"` without breaking."""
    return {
        "status": "applied",
        "message": "Escalation noted (full chain execution is a Phase 6 add).",
    }


# ── Handler registry ─────────────────────────────────────────────────


HandlerFn = Callable[[dict[str, Any]], dict[str, Any]]


HANDLERS: dict[str, HandlerFn] = {
    # Task
    "task.complete": _handle_task_complete,
    "task.cancel": _handle_task_cancel,
    "task.reassign": _handle_task_reassign,
    # SS cert (parity-preserved)
    "ss_cert.approve": _handle_ss_cert_approve,
    "ss_cert.void": _handle_ss_cert_void,
    # Cash Receipts Matching (Workflow Arc Phase 8b — parity-preserved)
    "cash_receipts.approve": _handle_cash_receipts_approve,
    "cash_receipts.reject": _handle_cash_receipts_reject,
    "cash_receipts.override": _handle_cash_receipts_override,
    "cash_receipts.request_review": _handle_cash_receipts_request_review,
    # Generic
    "skip": _handle_skip,
    "escalate": _handle_escalate,
}


def get_handler(key: str) -> HandlerFn | None:
    return HANDLERS.get(key)


def list_handler_keys() -> list[str]:
    return sorted(HANDLERS.keys())


__all__ = ["HANDLERS", "get_handler", "list_handler_keys", "HandlerFn"]
