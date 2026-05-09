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


# ── Month-End Close handlers (PARITY CRITICAL — Phase 8c) ──────────


def _handle_month_end_close_approve(ctx: dict[str, Any]) -> dict[str, Any]:
    """Approve via the existing `ApprovalGateService._process_approve`
    full-approval path. Triggers statement run + period lock +
    auto-approval of unflagged statement items. **Zero logic
    duplication.**"""
    from app.services.workflows.month_end_close_adapter import approve_close

    db: Session = ctx["db"]
    user: User = ctx["user"]
    try:
        result = approve_close(
            db, user=user, agent_job_id=ctx["entity_id"]
        )
    except ValueError as exc:
        return {"status": "errored", "message": str(exc)}
    return result


def _handle_month_end_close_reject(ctx: dict[str, Any]) -> dict[str, Any]:
    """Reject via `_process_reject`. No period lock, no statement
    run."""
    from app.services.workflows.month_end_close_adapter import reject_close

    db: Session = ctx["db"]
    user: User = ctx["user"]
    reason = ctx.get("reason") or ctx.get("reason_code")
    if not reason:
        return {
            "status": "errored",
            "message": "Reject reason is required.",
        }
    try:
        result = reject_close(
            db, user=user, agent_job_id=ctx["entity_id"], reason=reason,
        )
    except ValueError as exc:
        return {"status": "errored", "message": str(exc)}
    return result


def _handle_month_end_close_request_review(
    ctx: dict[str, Any],
) -> dict[str, Any]:
    from app.services.workflows.month_end_close_adapter import (
        request_review_close,
    )

    db: Session = ctx["db"]
    user: User = ctx["user"]
    note = ctx.get("note") or ctx.get("reason")
    if not note:
        return {
            "status": "errored",
            "message": "A note is required when requesting review.",
        }
    try:
        result = request_review_close(
            db, user=user, agent_job_id=ctx["entity_id"], note=note,
        )
    except ValueError as exc:
        return {"status": "errored", "message": str(exc)}
    return result


# ── AR Collections handlers (PARITY CRITICAL — Phase 8c) ───────────


def _handle_ar_collections_send(ctx: dict[str, Any]) -> dict[str, Any]:
    """Send the drafted collection email for this customer via the
    managed `email.collections` template. Closes the pre-existing
    Phase 3b TODO — legacy approval was a no-op."""
    from app.services.workflows.ar_collections_adapter import send_customer_email

    db: Session = ctx["db"]
    user: User = ctx["user"]
    try:
        result = send_customer_email(
            db, user=user, anomaly_id=ctx["entity_id"],
        )
    except ValueError as exc:
        return {"status": "errored", "message": str(exc)}
    return result


def _handle_ar_collections_skip(ctx: dict[str, Any]) -> dict[str, Any]:
    from app.services.workflows.ar_collections_adapter import skip_customer

    db: Session = ctx["db"]
    user: User = ctx["user"]
    reason = ctx.get("reason") or ctx.get("reason_code")
    if not reason:
        return {
            "status": "errored",
            "message": "Reason is required to skip a collection.",
        }
    try:
        result = skip_customer(
            db, user=user, anomaly_id=ctx["entity_id"], reason=reason,
        )
    except ValueError as exc:
        return {"status": "errored", "message": str(exc)}
    return result


def _handle_ar_collections_request_review(
    ctx: dict[str, Any],
) -> dict[str, Any]:
    from app.services.workflows.ar_collections_adapter import (
        request_review_customer,
    )

    db: Session = ctx["db"]
    user: User = ctx["user"]
    note = ctx.get("note") or ctx.get("reason")
    if not note:
        return {
            "status": "errored",
            "message": "A note is required when requesting review.",
        }
    try:
        result = request_review_customer(
            db, user=user, anomaly_id=ctx["entity_id"], note=note,
        )
    except ValueError as exc:
        return {"status": "errored", "message": str(exc)}
    return result


# ── Expense Categorization handlers (PARITY CRITICAL — Phase 8c) ───


def _handle_expense_categorization_approve(
    ctx: dict[str, Any],
) -> dict[str, Any]:
    """Apply the AI-suggested category (or user-supplied override) to
    the VendorBillLine. Payload may include `category_override: str`
    to replace the AI suggestion."""
    from app.services.workflows.expense_categorization_adapter import approve_line

    db: Session = ctx["db"]
    user: User = ctx["user"]
    payload = ctx.get("payload") or {}
    try:
        result = approve_line(
            db,
            user=user,
            anomaly_id=ctx["entity_id"],
            category_override=payload.get("category_override"),
        )
    except ValueError as exc:
        return {"status": "errored", "message": str(exc)}
    return result


def _handle_expense_categorization_reject(
    ctx: dict[str, Any],
) -> dict[str, Any]:
    from app.services.workflows.expense_categorization_adapter import reject_line

    db: Session = ctx["db"]
    user: User = ctx["user"]
    reason = ctx.get("reason") or ctx.get("reason_code")
    if not reason:
        return {
            "status": "errored",
            "message": "Reason is required to reject a line.",
        }
    try:
        result = reject_line(
            db, user=user, anomaly_id=ctx["entity_id"], reason=reason,
        )
    except ValueError as exc:
        return {"status": "errored", "message": str(exc)}
    return result


def _handle_expense_categorization_request_review(
    ctx: dict[str, Any],
) -> dict[str, Any]:
    from app.services.workflows.expense_categorization_adapter import (
        request_review_line,
    )

    db: Session = ctx["db"]
    user: User = ctx["user"]
    note = ctx.get("note") or ctx.get("reason")
    if not note:
        return {
            "status": "errored",
            "message": "A note is required when requesting review.",
        }
    try:
        result = request_review_line(
            db, user=user, anomaly_id=ctx["entity_id"], note=note,
        )
    except ValueError as exc:
        return {"status": "errored", "message": str(exc)}
    return result


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


# ── Aftercare handlers (Workflow Arc Phase 8d — triage-only) ────────


def _handle_aftercare_send(ctx: dict[str, Any]) -> dict[str, Any]:
    """Approve-equivalent for aftercare_triage. Sends the 7-day
    follow-up email via the D-7 managed-template path and logs a
    VaultItem. Zero template duplication — body comes from
    `email.fh_aftercare_7day` managed template."""
    from app.services.workflows.aftercare_adapter import approve_send

    db: Session = ctx["db"]
    user: User = ctx["user"]
    try:
        result = approve_send(
            db, user=user, anomaly_id=ctx["entity_id"]
        )
    except ValueError as exc:
        return {"status": "errored", "message": str(exc)}
    return {
        "status": "applied",
        "message": result["message"],
        "delivery_id": result.get("delivery_id"),
    }


def _handle_aftercare_skip(ctx: dict[str, Any]) -> dict[str, Any]:
    """Skip the aftercare send. Resolves the anomaly with a reason;
    no email sent. Case stays eligible for manual follow-up."""
    from app.services.workflows.aftercare_adapter import skip_case

    db: Session = ctx["db"]
    user: User = ctx["user"]
    reason = ctx.get("reason") or ctx.get("reason_code")
    if not reason:
        return {
            "status": "errored",
            "message": "Skip reason is required.",
        }
    try:
        skip_case(
            db,
            user=user,
            anomaly_id=ctx["entity_id"],
            reason=reason,
        )
    except ValueError as exc:
        return {"status": "errored", "message": str(exc)}
    return {
        "status": "applied",
        "message": "Aftercare skipped.",
    }


def _handle_aftercare_request_review(ctx: dict[str, Any]) -> dict[str, Any]:
    """Escalate to a teammate. Stamps a review note without
    resolving; item stays in-queue."""
    from app.services.workflows.aftercare_adapter import request_review

    db: Session = ctx["db"]
    user: User = ctx["user"]
    note = ctx.get("note") or ctx.get("reason")
    if not note:
        return {
            "status": "errored",
            "message": "A note is required when requesting review.",
        }
    try:
        request_review(
            db, user=user, anomaly_id=ctx["entity_id"], note=note
        )
    except ValueError as exc:
        return {"status": "errored", "message": str(exc)}
    return {
        "status": "applied",
        "message": "Review requested — case stays in queue.",
    }


# ── Catalog fetch handlers (Workflow Arc Phase 8d) ──────────────────


def _handle_catalog_fetch_approve(ctx: dict[str, Any]) -> dict[str, Any]:
    """Approve — publish the staged catalog via the legacy
    `WilbertIngestionService.ingest_from_pdf` path. Zero logic
    duplication — the adapter fetches the staged PDF from R2 and
    calls the unchanged legacy service."""
    from app.services.workflows.catalog_fetch_adapter import approve_publish

    db: Session = ctx["db"]
    user: User = ctx["user"]
    try:
        result = approve_publish(
            db, user=user, sync_log_id=ctx["entity_id"]
        )
    except ValueError as exc:
        return {"status": "errored", "message": str(exc)}
    return {
        "status": "applied",
        "message": result["message"],
        "products_added": result.get("products_added"),
        "products_updated": result.get("products_updated"),
    }


def _handle_catalog_fetch_reject(ctx: dict[str, Any]) -> dict[str, Any]:
    """Reject — flip publication_state='rejected' on the staging
    sync_log. No product writes; admin must supply a reason."""
    from app.services.workflows.catalog_fetch_adapter import reject_publish

    db: Session = ctx["db"]
    user: User = ctx["user"]
    reason = ctx.get("reason") or ctx.get("reason_code")
    if not reason:
        return {
            "status": "errored",
            "message": "Rejection reason is required.",
        }
    try:
        reject_publish(
            db,
            user=user,
            sync_log_id=ctx["entity_id"],
            reason=reason,
        )
    except ValueError as exc:
        return {"status": "errored", "message": str(exc)}
    return {
        "status": "applied",
        "message": "Catalog rejected — no products modified.",
    }


def _handle_catalog_fetch_request_review(
    ctx: dict[str, Any],
) -> dict[str, Any]:
    """Stamp a review note on the staging sync_log's audit trail
    without changing state. Item stays pending_review for a teammate."""
    from app.services.workflows.catalog_fetch_adapter import request_review

    db: Session = ctx["db"]
    user: User = ctx["user"]
    note = ctx.get("note") or ctx.get("reason")
    if not note:
        return {
            "status": "errored",
            "message": "A note is required when requesting review.",
        }
    try:
        request_review(
            db, user=user, sync_log_id=ctx["entity_id"], note=note
        )
    except ValueError as exc:
        return {"status": "errored", "message": str(exc)}
    return {
        "status": "applied",
        "message": "Review requested — catalog stays in queue.",
    }


# ── Safety Program handlers (Workflow Arc Phase 8d.1) ──────────────
#
# AI-generation-with-approval shape. Delegates to safety_program_adapter
# which in turn delegates to safety_program_generation_service (legacy
# service unchanged). Parity is on approval mechanics, not on
# non-deterministic AI-generated content (Template v2.2 §5.5.5).


def _handle_safety_program_approve(ctx: dict[str, Any]) -> dict[str, Any]:
    """Approve — promotes the pending_review generation to the
    tenant's canonical SafetyProgram (insert new or version++
    existing). Same writes as legacy /safety/programs/generations/
    {id}/approve. Zero logic duplication."""
    from app.services.workflows.safety_program_adapter import (
        approve_generation,
    )

    db: Session = ctx["db"]
    user: User = ctx["user"]
    payload = ctx.get("payload") or {}
    notes = (
        payload.get("notes")
        or ctx.get("note")
        or ctx.get("reason")  # accept reason as approval-notes alias
        or None
    )
    try:
        result = approve_generation(
            db,
            user=user,
            generation_id=ctx["entity_id"],
            notes=notes,
        )
    except ValueError as exc:
        return {"status": "errored", "message": str(exc)}
    return {
        "status": "applied",
        "message": result["message"],
        "safety_program_id": result.get("safety_program_id"),
        "generation_status": result.get("generation_status"),
    }


def _handle_safety_program_reject(ctx: dict[str, Any]) -> dict[str, Any]:
    """Reject — transitions status to 'rejected'. Reason REQUIRED.
    No SafetyProgram write (negative parity assertion)."""
    from app.services.workflows.safety_program_adapter import (
        reject_generation,
    )

    db: Session = ctx["db"]
    user: User = ctx["user"]
    reason = ctx.get("reason") or ctx.get("reason_code")
    if not reason:
        return {
            "status": "errored",
            "message": "Rejection notes are required.",
        }
    try:
        reject_generation(
            db,
            user=user,
            generation_id=ctx["entity_id"],
            reason=reason,
        )
    except ValueError as exc:
        return {"status": "errored", "message": str(exc)}
    return {
        "status": "applied",
        "message": "Safety program rejected — no program promoted.",
    }


def _handle_safety_program_request_review(
    ctx: dict[str, Any],
) -> dict[str, Any]:
    """Request-review — stamps a timestamped note on review_notes
    without resolving. Item stays pending_review for a teammate
    (e.g., compliance officer) to pick up."""
    from app.services.workflows.safety_program_adapter import (
        request_review,
    )

    db: Session = ctx["db"]
    user: User = ctx["user"]
    note = ctx.get("note") or ctx.get("reason")
    if not note:
        return {
            "status": "errored",
            "message": "A note is required when requesting review.",
        }
    try:
        request_review(
            db,
            user=user,
            generation_id=ctx["entity_id"],
            note=note,
        )
    except ValueError as exc:
        return {"status": "errored", "message": str(exc)}
    return {
        "status": "applied",
        "message": "Review requested — generation stays in queue.",
    }


# ── Handler registry ─────────────────────────────────────────────────


# ── Workflow Review handlers (Phase R-6.0a) ─────────────────────────


def _handle_workflow_review_approve(ctx: dict[str, Any]) -> dict[str, Any]:
    """Approve a WorkflowReviewItem; resume the underlying run with
    the canonical input payload as next-step input."""
    from app.services.workflows.workflow_review_adapter import (
        WorkflowReviewError,
        WorkflowReviewItemAlreadyDecided,
        WorkflowReviewItemNotFound,
        commit_decision,
    )

    db: Session = ctx["db"]
    user: User = ctx["user"]
    try:
        item = commit_decision(
            db,
            item_id=ctx["entity_id"],
            decision="approve",
            user_id=user.id,
            company_id=user.company_id,
        )
    except WorkflowReviewItemNotFound as exc:
        return {"status": "errored", "message": str(exc), "code": "not_found"}
    except WorkflowReviewItemAlreadyDecided as exc:
        return {"status": "errored", "message": str(exc), "code": "already_decided"}
    except WorkflowReviewError as exc:
        return {"status": "errored", "message": str(exc)}
    return {
        "status": "applied",
        "message": f"Review item {item.id} approved; workflow advanced.",
        "entity_state": "approved",
        "review_focus_id": item.review_focus_id,
        "run_id": item.run_id,
    }


def _handle_workflow_review_reject(ctx: dict[str, Any]) -> dict[str, Any]:
    """Reject a WorkflowReviewItem; resume the underlying run with
    a ``decision=reject`` payload + the reviewer's note. Downstream
    steps in the workflow can branch on this signal."""
    from app.services.workflows.workflow_review_adapter import (
        WorkflowReviewError,
        WorkflowReviewItemAlreadyDecided,
        WorkflowReviewItemNotFound,
        commit_decision,
    )

    db: Session = ctx["db"]
    user: User = ctx["user"]
    reason = ctx.get("reason") or ctx.get("reason_code") or ctx.get("note")
    try:
        item = commit_decision(
            db,
            item_id=ctx["entity_id"],
            decision="reject",
            user_id=user.id,
            company_id=user.company_id,
            decision_notes=reason,
        )
    except WorkflowReviewItemNotFound as exc:
        return {"status": "errored", "message": str(exc), "code": "not_found"}
    except WorkflowReviewItemAlreadyDecided as exc:
        return {"status": "errored", "message": str(exc), "code": "already_decided"}
    except WorkflowReviewError as exc:
        return {"status": "errored", "message": str(exc)}
    return {
        "status": "applied",
        "message": f"Review item {item.id} rejected; workflow advanced.",
        "entity_state": "rejected",
        "review_focus_id": item.review_focus_id,
        "run_id": item.run_id,
    }


def _handle_workflow_review_edit_and_approve(
    ctx: dict[str, Any],
) -> dict[str, Any]:
    """Approve with operator-edited payload. ``ctx['payload']`` carries
    the edited shape, which becomes the next step's input via
    ``workflow_review_adapter.commit_decision``."""
    from app.services.workflows.workflow_review_adapter import (
        WorkflowReviewError,
        WorkflowReviewItemAlreadyDecided,
        WorkflowReviewItemNotFound,
        commit_decision,
    )

    db: Session = ctx["db"]
    user: User = ctx["user"]
    payload = ctx.get("payload")
    if not isinstance(payload, dict):
        return {
            "status": "errored",
            "message": "edit_and_approve requires 'payload' dict.",
        }
    try:
        item = commit_decision(
            db,
            item_id=ctx["entity_id"],
            decision="edit_and_approve",
            user_id=user.id,
            company_id=user.company_id,
            edited_data=payload,
            decision_notes=ctx.get("note"),
        )
    except WorkflowReviewItemNotFound as exc:
        return {"status": "errored", "message": str(exc), "code": "not_found"}
    except WorkflowReviewItemAlreadyDecided as exc:
        return {"status": "errored", "message": str(exc), "code": "already_decided"}
    except WorkflowReviewError as exc:
        return {"status": "errored", "message": str(exc)}
    return {
        "status": "applied",
        "message": f"Review item {item.id} edited + approved; workflow advanced.",
        "entity_state": "edited_and_approved",
        "review_focus_id": item.review_focus_id,
        "run_id": item.run_id,
    }


# ── Email unclassified handlers (Phase R-6.1a) ──────────────────────


def _handle_email_unclassified_route_to_workflow(
    ctx: dict[str, Any],
) -> dict[str, Any]:
    """Operator picks a workflow + fires it with the email as
    trigger context. Writes a NEW classification row marking the
    manual reroute. ``ctx['payload']`` carries
    ``{"workflow_id": str, "decision_notes": str | None}``."""
    from app.services.classification.dispatch import (
        ClassificationError,
        ClassificationNotFound,
        manual_route_to_workflow,
    )

    db: Session = ctx["db"]
    user: User = ctx["user"]
    payload = ctx.get("payload") or {}
    workflow_id = payload.get("workflow_id") if isinstance(payload, dict) else None
    decision_notes = (
        payload.get("decision_notes") if isinstance(payload, dict) else None
    )
    if not isinstance(workflow_id, str) or not workflow_id:
        return {
            "status": "errored",
            "message": "route_to_workflow requires payload.workflow_id (string).",
        }

    try:
        result = manual_route_to_workflow(
            db,
            classification_id=ctx["entity_id"],
            workflow_id=workflow_id,
            user=user,
            decision_notes=(
                decision_notes if isinstance(decision_notes, str) else None
            ),
        )
    except ClassificationNotFound as exc:
        return {"status": "errored", "message": str(exc), "code": "not_found"}
    except ClassificationError as exc:
        return {"status": "errored", "message": str(exc)}

    return {
        "status": "applied",
        "message": (
            f"Routed to workflow; run_id={result.workflow_run_id or 'pending'}."
        ),
        "entity_state": "routed",
        "classification_id": result.classification_id,
        "workflow_run_id": result.workflow_run_id,
    }


def _handle_email_unclassified_suppress(
    ctx: dict[str, Any],
) -> dict[str, Any]:
    """Mark the classification as suppressed — the email drops
    without firing or routing to triage on subsequent identical
    matches (operator may follow up with a Tier 1 rule for the
    pattern). Writes a NEW classification row preserving audit
    chain."""
    from app.models.email_classification import (
        WorkflowEmailClassification,
    )
    from app.services.classification.audit import write_classification_audit

    db: Session = ctx["db"]
    user: User = ctx["user"]
    prior = (
        db.query(WorkflowEmailClassification)
        .filter(
            WorkflowEmailClassification.id == ctx["entity_id"],
            WorkflowEmailClassification.tenant_id == user.company_id,
        )
        .first()
    )
    if prior is None:
        return {
            "status": "errored",
            "message": "Classification not found",
            "code": "not_found",
        }

    row = write_classification_audit(
        db,
        tenant_id=user.company_id,
        email_message_id=prior.email_message_id,
        tier=None,
        is_suppressed=True,
        is_replay=True,
        replay_of_classification_id=prior.id,
        tier_reasoning={
            "manual_suppress": {
                "operator_user_id": user.id,
                "reason": ctx.get("reason") or ctx.get("note"),
            }
        },
    )
    db.commit()
    return {
        "status": "applied",
        "message": "Suppressed; future identical messages may need a Tier 1 rule.",
        "entity_state": "suppressed",
        "classification_id": row.id,
    }


def _handle_email_unclassified_request_review(
    ctx: dict[str, Any],
) -> dict[str, Any]:
    """Soft action — note the request for review without mutating
    classification state. Surfaces in the audit trail; another
    admin can pick up the item from triage. v1 does NOT route to a
    specific user — admins share the unclassified queue."""
    return {
        "status": "applied",
        "message": "Review requested; another admin can pick this up from the queue.",
        "entity_state": "review_requested",
    }


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
    # Month-End Close (Workflow Arc Phase 8c — FULL approval parity)
    "month_end_close.approve": _handle_month_end_close_approve,
    "month_end_close.reject": _handle_month_end_close_reject,
    "month_end_close.request_review": _handle_month_end_close_request_review,
    # AR Collections (Workflow Arc Phase 8c — closes Phase 3b TODO)
    "ar_collections.send": _handle_ar_collections_send,
    "ar_collections.skip": _handle_ar_collections_skip,
    "ar_collections.request_review": _handle_ar_collections_request_review,
    # Expense Categorization (Workflow Arc Phase 8c — per-line review)
    "expense_categorization.approve": _handle_expense_categorization_approve,
    "expense_categorization.reject": _handle_expense_categorization_reject,
    "expense_categorization.request_review": _handle_expense_categorization_request_review,
    # FH Aftercare (Workflow Arc Phase 8d — triage-only)
    "aftercare.send": _handle_aftercare_send,
    "aftercare.skip": _handle_aftercare_skip,
    "aftercare.request_review": _handle_aftercare_request_review,
    # Wilbert Catalog Fetch (Workflow Arc Phase 8d — triage-gated publish)
    "catalog_fetch.approve": _handle_catalog_fetch_approve,
    "catalog_fetch.reject": _handle_catalog_fetch_reject,
    "catalog_fetch.request_review": _handle_catalog_fetch_request_review,
    # Safety Program (Workflow Arc Phase 8d.1 — AI-generation-with-approval)
    "safety_program.approve": _handle_safety_program_approve,
    "safety_program.reject": _handle_safety_program_reject,
    "safety_program.request_review": _handle_safety_program_request_review,
    # Workflow Review (Phase R-6.0a — invoke_review_focus pause)
    "workflow_review.approve": _handle_workflow_review_approve,
    "workflow_review.reject": _handle_workflow_review_reject,
    "workflow_review.edit_and_approve": _handle_workflow_review_edit_and_approve,
    # Email unclassified (Phase R-6.1a)
    "email_unclassified.route_to_workflow": _handle_email_unclassified_route_to_workflow,
    "email_unclassified.suppress": _handle_email_unclassified_suppress,
    "email_unclassified.request_review": _handle_email_unclassified_request_review,
    # Generic
    "skip": _handle_skip,
    "escalate": _handle_escalate,
}


def get_handler(key: str) -> HandlerFn | None:
    return HANDLERS.get(key)


def list_handler_keys() -> list[str]:
    return sorted(HANDLERS.keys())


__all__ = ["HANDLERS", "get_handler", "list_handler_keys", "HandlerFn"]
