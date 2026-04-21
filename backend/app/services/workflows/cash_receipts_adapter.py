"""Cash Receipts Matching — parity adapter (Workflow Arc Phase 8b).

Thin bridge between workflow engine steps / triage actions and the
existing `CashReceiptsAgent` service. This module exists to preserve
side-effect parity between the legacy agent-runner path and the new
workflow/triage path — not to re-implement matching logic.

The central parity claim of Phase 8b:
  For a given (payment, invoice) pair, the CustomerPaymentApplication
  row written by the legacy `CashReceiptsAgent._step_attempt_auto_match`
  CONFIDENT_MATCH branch is IDENTICAL to the row written by
  `approve_match()` below. Identical payment_id, invoice_id,
  amount_applied. Identical Invoice.amount_paid + Invoice.status
  mutations. Verified by `test_cash_receipts_migration_parity.py`.

Public functions (the surface workflow engine + triage call):

  run_match_pipeline(db, *, company_id, triggered_by_user_id,
                     dry_run, trigger_source) -> dict
      Execute the 4-step matching agent. Creates an AgentJob row +
      runs it to awaiting_approval. The AgentJob is the container
      for anomalies the triage queue will pull from. Returns a
      summary dict with counts + job_id for downstream steps.

  approve_match(db, *, user, payment_id, invoice_id, anomaly_id,
                amount=None) -> dict
      Triage "approve" action. Creates the CustomerPaymentApplication
      row + updates Invoice + resolves the anomaly. This is the
      manual counterpart to the agent's inline CONFIDENT_MATCH write.

  reject_match(db, *, user, payment_id, anomaly_id, reason) -> dict
      Triage "reject" action. Resolves the anomaly with a note; no
      financial writes. Payment stays unmatched and can be re-queued
      in a subsequent run.

  override_match(db, *, user, payment_id, invoice_id, anomaly_id,
                 reason, amount=None) -> dict
      Triage "override" action. Same financial writes as
      approve_match but stamps an override reason on the anomaly.
      Used when the user force-applies a match the agent classified
      as UNRESOLVABLE or suggested differently.

  request_review(db, *, user, payment_id, anomaly_id, note) -> dict
      Triage "request_review" action. Escalates to a teammate by
      stamping a review note without resolving the anomaly. The item
      stays in-queue but is marked for attention.

Zero-duplication discipline:
  - `approve_match` writes the same `CustomerPaymentApplication` +
    `Invoice` mutations as `CashReceiptsAgent._step_attempt_auto_match`
    CONFIDENT_MATCH branch. If the agent's write shape ever changes,
    this function must change in lock-step. Parity test guards it.
  - `run_match_pipeline` DELEGATES the entire 4-step execution to the
    existing `CashReceiptsAgent.execute()` via the agent runner; no
    step logic lives in this module.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.agent import AgentJob
from app.models.agent_anomaly import AgentAnomaly
from app.models.customer_payment import (
    CustomerPayment,
    CustomerPaymentApplication,
)
from app.models.invoice import Invoice
from app.models.user import User
from app.schemas.agent import AgentJobStatus, AgentJobType

logger = logging.getLogger(__name__)


# ── Pipeline entry (workflow-step surface) ───────────────────────────


def run_match_pipeline(
    db: Session,
    *,
    company_id: str,
    triggered_by_user_id: str | None,
    dry_run: bool = False,
    trigger_source: str = "workflow",
) -> dict[str, Any]:
    """Create + execute a CashReceiptsAgent job end-to-end.

    Called by the `call_service_method` workflow step (see
    workflow_engine). Returns a structured summary suitable for
    downstream workflow variable resolution.

    The AgentJob row the agent creates serves as the container
    anomalies hang off — the triage queue reads them via the
    `_dq_cash_receipts_matching_triage` builder.

    dry_run=False means real writes for CONFIDENT_MATCH payments
    (same behavior as the agent-runner path). The workflow's
    trigger_context can set dry_run=True for report-only runs.
    """
    from app.services.agents.agent_runner import AgentRunner

    today = date.today()
    job = AgentJob(
        id=str(uuid.uuid4()),
        tenant_id=company_id,
        job_type=AgentJobType.CASH_RECEIPTS_MATCHING.value,
        status=AgentJobStatus.PENDING.value,
        period_start=today.replace(day=1),
        period_end=today,
        dry_run=dry_run,
        triggered_by=triggered_by_user_id,
        trigger_type=trigger_source,
        run_log=[],
        anomaly_count=0,
    )
    db.add(job)
    db.commit()

    # Delegate to the existing runner — zero logic duplication.
    AgentRunner.run_job(job.id, db)
    db.refresh(job)

    report = job.report_payload or {}
    exec_summary = report.get("executive_summary", {}) if isinstance(report, dict) else {}
    return {
        "agent_job_id": job.id,
        "status": job.status,
        "anomaly_count": job.anomaly_count,
        "confident_matches": exec_summary.get("confident_matches", 0),
        "possible_matches": exec_summary.get("possible_matches", 0),
        "unresolvable": exec_summary.get("unresolvable", 0),
        "unmatched_total": exec_summary.get("unmatched_total", 0),
        "dry_run": dry_run,
    }


# ── Triage action helpers ────────────────────────────────────────────


def _apply_payment_to_invoice(
    db: Session,
    *,
    payment: CustomerPayment,
    invoice: Invoice,
    amount: Decimal | None = None,
) -> CustomerPaymentApplication:
    """Identical write pattern to `CashReceiptsAgent._step_attempt_auto_match`
    CONFIDENT_MATCH branch (agent lines 223–238). Any divergence
    here breaks parity.

    If `amount` is None, applies the full payment amount (matches
    the agent's behavior for a single exact match)."""
    apply_amount = Decimal(str(amount if amount is not None else payment.total_amount or 0))
    if apply_amount <= 0:
        raise ValueError("amount_applied must be > 0")

    app = CustomerPaymentApplication(
        id=str(uuid.uuid4()),
        payment_id=payment.id,
        invoice_id=invoice.id,
        amount_applied=apply_amount,
    )
    db.add(app)
    invoice.amount_paid = Decimal(str(invoice.amount_paid or 0)) + apply_amount
    if invoice.amount_paid >= Decimal(str(invoice.total or 0)):
        invoice.status = "paid"
        invoice.paid_at = datetime.now(timezone.utc)
    db.flush()
    return app


def _resolve_anomaly(
    db: Session,
    *,
    anomaly: AgentAnomaly,
    user_id: str,
    note: str,
) -> None:
    """Mark an anomaly as resolved with an audit trail. Same fields
    the existing `/api/v1/agents/accounting/.../anomalies/.../resolve`
    route writes."""
    anomaly.resolved = True
    anomaly.resolved_by = user_id
    anomaly.resolved_at = datetime.now(timezone.utc)
    anomaly.resolution_note = note
    db.flush()


def _load_anomaly_scoped(
    db: Session, *, anomaly_id: str, company_id: str
) -> AgentAnomaly:
    """Fetch an AgentAnomaly and verify it belongs to a job owned by
    the given tenant. Prevents cross-tenant anomaly mutation."""
    row = (
        db.query(AgentAnomaly)
        .join(AgentJob, AgentJob.id == AgentAnomaly.agent_job_id)
        .filter(
            AgentAnomaly.id == anomaly_id,
            AgentJob.tenant_id == company_id,
        )
        .first()
    )
    if row is None:
        raise ValueError(f"Anomaly {anomaly_id} not found for this tenant")
    return row


def _load_payment_scoped(
    db: Session, *, payment_id: str, company_id: str
) -> CustomerPayment:
    payment = (
        db.query(CustomerPayment)
        .filter(
            CustomerPayment.id == payment_id,
            CustomerPayment.company_id == company_id,
            CustomerPayment.deleted_at.is_(None),
        )
        .first()
    )
    if payment is None:
        raise ValueError(f"Payment {payment_id} not found for this tenant")
    return payment


def _load_invoice_scoped(
    db: Session, *, invoice_id: str, company_id: str
) -> Invoice:
    invoice = (
        db.query(Invoice)
        .filter(
            Invoice.id == invoice_id,
            Invoice.company_id == company_id,
        )
        .first()
    )
    if invoice is None:
        raise ValueError(f"Invoice {invoice_id} not found for this tenant")
    return invoice


def approve_match(
    db: Session,
    *,
    user: User,
    payment_id: str,
    invoice_id: str,
    anomaly_id: str | None = None,
    amount: Decimal | None = None,
) -> dict[str, Any]:
    """Apply a cash payment to an invoice — the triage approve path.

    Equivalent side effect to the agent's CONFIDENT_MATCH branch:
    creates a CustomerPaymentApplication row, increments
    Invoice.amount_paid, flips Invoice.status to "paid" when fully
    applied, resolves the related anomaly (if provided).
    """
    payment = _load_payment_scoped(
        db, payment_id=payment_id, company_id=user.company_id
    )
    invoice = _load_invoice_scoped(
        db, invoice_id=invoice_id, company_id=user.company_id
    )

    app = _apply_payment_to_invoice(
        db, payment=payment, invoice=invoice, amount=amount
    )

    anomaly_resolved = False
    if anomaly_id:
        anomaly = _load_anomaly_scoped(
            db, anomaly_id=anomaly_id, company_id=user.company_id
        )
        _resolve_anomaly(
            db,
            anomaly=anomaly,
            user_id=user.id,
            note=(
                f"Approved via triage — applied ${app.amount_applied} "
                f"to invoice {invoice.number}"
            ),
        )
        anomaly_resolved = True

    db.commit()
    return {
        "status": "applied",
        "message": (
            f"Applied ${app.amount_applied} to invoice {invoice.number}"
        ),
        "payment_application_id": app.id,
        "payment_id": payment.id,
        "invoice_id": invoice.id,
        "amount_applied": float(app.amount_applied),
        "invoice_status": invoice.status,
        "anomaly_resolved": anomaly_resolved,
    }


def reject_match(
    db: Session,
    *,
    user: User,
    payment_id: str,
    anomaly_id: str,
    reason: str,
) -> dict[str, Any]:
    """Triage reject action. Resolves the anomaly with a reason; no
    financial writes. The payment stays unapplied and will re-surface
    in the next agent run unless manually archived elsewhere."""
    if not reason:
        raise ValueError("reason is required to reject a match")
    # Verify payment is scoped to tenant (defense-in-depth even though
    # the anomaly lookup is scoped).
    _load_payment_scoped(
        db, payment_id=payment_id, company_id=user.company_id
    )
    anomaly = _load_anomaly_scoped(
        db, anomaly_id=anomaly_id, company_id=user.company_id
    )
    _resolve_anomaly(
        db,
        anomaly=anomaly,
        user_id=user.id,
        note=f"Rejected via triage — {reason}",
    )
    db.commit()
    return {
        "status": "applied",
        "message": "Match rejected. Payment stays unresolved.",
        "payment_id": payment_id,
        "anomaly_id": anomaly_id,
        "anomaly_resolved": True,
    }


def override_match(
    db: Session,
    *,
    user: User,
    payment_id: str,
    invoice_id: str,
    anomaly_id: str,
    reason: str,
    amount: Decimal | None = None,
) -> dict[str, Any]:
    """Triage override action. Same writes as approve_match but the
    anomaly resolution note records the override reason. Used when
    the user force-applies a match the agent didn't suggest (e.g.,
    an UNRESOLVABLE payment where the user knows which invoice it
    belongs to)."""
    if not reason:
        raise ValueError("reason is required to override a match")
    payment = _load_payment_scoped(
        db, payment_id=payment_id, company_id=user.company_id
    )
    invoice = _load_invoice_scoped(
        db, invoice_id=invoice_id, company_id=user.company_id
    )
    anomaly = _load_anomaly_scoped(
        db, anomaly_id=anomaly_id, company_id=user.company_id
    )

    app = _apply_payment_to_invoice(
        db, payment=payment, invoice=invoice, amount=amount
    )
    _resolve_anomaly(
        db,
        anomaly=anomaly,
        user_id=user.id,
        note=(
            f"Override applied via triage — ${app.amount_applied} to "
            f"invoice {invoice.number}. Reason: {reason}"
        ),
    )
    db.commit()
    return {
        "status": "applied",
        "message": (
            f"Override applied: ${app.amount_applied} to invoice {invoice.number}"
        ),
        "payment_application_id": app.id,
        "payment_id": payment.id,
        "invoice_id": invoice.id,
        "amount_applied": float(app.amount_applied),
        "invoice_status": invoice.status,
        "anomaly_resolved": True,
        "override_reason": reason,
    }


def request_review(
    db: Session,
    *,
    user: User,
    payment_id: str,
    anomaly_id: str,
    note: str,
) -> dict[str, Any]:
    """Triage request_review action. Stamps a review note on the
    anomaly without resolving it, leaving the item in-queue for
    someone else to pick up. Think of it as a "needs a second set of
    eyes" flag rather than a decision."""
    if not note:
        raise ValueError("note is required to request review")
    anomaly = _load_anomaly_scoped(
        db, anomaly_id=anomaly_id, company_id=user.company_id
    )
    existing = anomaly.resolution_note or ""
    stamp = (
        f"[review-requested by {user.id} at "
        f"{datetime.now(timezone.utc).isoformat()}] {note}"
    )
    anomaly.resolution_note = f"{existing}\n{stamp}" if existing else stamp
    db.flush()
    db.commit()
    return {
        "status": "applied",
        "message": "Review requested — item stays in queue.",
        "payment_id": payment_id,
        "anomaly_id": anomaly_id,
        "anomaly_resolved": False,
    }


__all__ = [
    "run_match_pipeline",
    "approve_match",
    "reject_match",
    "override_match",
    "request_review",
]
