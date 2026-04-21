"""Expense Categorization — parity adapter (Workflow Arc Phase 8c).

Thin bridge between the workflow engine / triage engine and the
existing `ExpenseCategorizationAgent` + `VendorBillLine.expense_category`
write path. Preserves side effects via service reuse.

The central parity claim of Phase 8c for expense categorization:
  For a given low-confidence or no-mapping anomaly, calling
  `approve_line` via triage writes `VendorBillLine.expense_category`
  IDENTICAL to what `ApprovalGateService._apply_expense_categories`
  writes for a high-confidence row. The category value written is
  either the AI-suggested `proposed_category` (default) OR a
  user-supplied `category_override` (new capability — backend ready
  for Phase 8e's frontend override UI).

Verified by `test_expense_categorization_migration_parity.py`
(BLOCKING).

**Trigger-type change — explicit deviation, not a bug fix:**
The workflow's trigger_type was `"event"` + `trigger_config.event="expense.created"`
since the Phase 8a seed, but NO event dispatch infrastructure exists
today. Phase 8c switches the seed to `trigger_type="scheduled"` +
`cron="*/15 * * * *"` as a workaround using the Phase 8b.5 scheduled
dispatch. Latency is ~15 min vs. real-time. Flagged in
WORKFLOW_MIGRATION_TEMPLATE.md v2 §7 + CLAUDE.md; real event
infrastructure is future horizontal arc work.

Per-line override path:
  `approve_line(..., category_override=X)` sets
  `VendorBillLine.expense_category = X` instead of the AI suggestion.
  Frontend exposure deferred to Phase 8e's triage UI; backend ships
  the capability.

Public functions:

  run_categorization_pipeline(db, *, company_id, triggered_by_user_id,
                              dry_run=False, trigger_source="workflow")
      -> dict
      Execute the 4-step agent. Agent classifies + resolves GL
      mappings + emits anomalies for low-confidence and no-mapping
      lines.

  approve_line(db, *, user, anomaly_id, category_override=None) -> dict
      Triage "approve" action. Writes `VendorBillLine.expense_category`
      using the AI-suggested category OR the user-supplied
      `category_override`. Resolves the anomaly with a "categorized via
      triage" note.

  reject_line(db, *, user, anomaly_id, reason) -> dict
      Triage "reject" action. Resolves the anomaly with a reason; no
      category write. Line stays uncategorized for manual handling
      outside the agent flow.

  request_review_line(db, *, user, anomaly_id, note) -> dict
      Triage "request_review" action. Stamps review note, leaves
      anomaly unresolved.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.agent import AgentJob
from app.models.agent_anomaly import AgentAnomaly
from app.models.user import User
from app.models.vendor_bill_line import VendorBillLine
from app.schemas.agent import AgentJobStatus, AgentJobType

logger = logging.getLogger(__name__)


# ── Pipeline entry ───────────────────────────────────────────────────


def run_categorization_pipeline(
    db: Session,
    *,
    company_id: str,
    triggered_by_user_id: str | None,
    dry_run: bool = False,
    trigger_source: str = "workflow",
) -> dict[str, Any]:
    """Create + execute an ExpenseCategorizationAgent job end-to-end."""
    from app.services.agents.agent_runner import AgentRunner

    today = date.today()
    first_of_month = today.replace(day=1)

    job = AgentJob(
        id=str(uuid.uuid4()),
        tenant_id=company_id,
        job_type=AgentJobType.EXPENSE_CATEGORIZATION.value,
        status=AgentJobStatus.PENDING.value,
        period_start=first_of_month,
        period_end=today,
        dry_run=dry_run,
        triggered_by=triggered_by_user_id,
        trigger_type=trigger_source,
        run_log=[],
        anomaly_count=0,
    )
    db.add(job)
    db.commit()

    AgentRunner.run_job(job.id, db)
    db.refresh(job)

    report = job.report_payload or {}
    exec_summary = (
        report.get("executive_summary", {})
        if isinstance(report, dict) else {}
    )
    return {
        "agent_job_id": job.id,
        "status": job.status,
        "anomaly_count": job.anomaly_count,
        "uncategorized_found": exec_summary.get("uncategorized_found", 0),
        "auto_apply_ready": exec_summary.get("auto_apply_ready", 0),
        "needs_review": exec_summary.get("needs_review", 0),
        "no_gl_mapping": exec_summary.get("no_gl_mapping", 0),
        "dry_run": dry_run,
    }


# ── Tenant-scoped loaders + helpers ──────────────────────────────────


def _load_anomaly_scoped(
    db: Session, *, anomaly_id: str, company_id: str
) -> AgentAnomaly:
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
        raise ValueError(
            f"Anomaly {anomaly_id} not found for this tenant"
        )
    return row


def _load_vendor_bill_line_scoped(
    db: Session, *, line_id: str, company_id: str
) -> VendorBillLine:
    """VendorBillLine inherits company scoping via its parent
    VendorBill. Validate the join to prevent cross-tenant writes."""
    from app.models.vendor_bill import VendorBill

    line = (
        db.query(VendorBillLine)
        .join(VendorBill, VendorBill.id == VendorBillLine.bill_id)
        .filter(
            VendorBillLine.id == line_id,
            VendorBill.company_id == company_id,
        )
        .first()
    )
    if line is None:
        raise ValueError(
            f"VendorBillLine {line_id} not found for this tenant"
        )
    return line


def _proposed_category_for_line(
    job: AgentJob, line_id: str
) -> str | None:
    """Pull the AI-suggested category for a given line from the job's
    report_payload. Returns None if not found."""
    if not isinstance(job.report_payload, dict):
        return None
    steps = job.report_payload.get("steps") or {}
    # Preferred source: map_to_gl_accounts.mappings carries
    # mapping_status="mapped" with proposed_category. Fallback:
    # classify_expenses.classifications for "no_gl_mapping" or review
    # lines.
    gl_data = steps.get("map_to_gl_accounts") or {}
    for m in gl_data.get("mappings") or []:
        if m.get("line_id") == line_id:
            return m.get("proposed_category")
    classify_data = steps.get("classify_expenses") or {}
    for c in classify_data.get("classifications") or []:
        if c.get("line_id") == line_id:
            return c.get("proposed_category")
    return None


def _resolve_anomaly(
    db: Session,
    *,
    anomaly: AgentAnomaly,
    user_id: str,
    note: str,
) -> None:
    anomaly.resolved = True
    anomaly.resolved_by = user_id
    anomaly.resolved_at = datetime.now(timezone.utc)
    anomaly.resolution_note = note
    db.flush()


# ── Triage action helpers ────────────────────────────────────────────


def approve_line(
    db: Session,
    *,
    user: User,
    anomaly_id: str,
    category_override: str | None = None,
) -> dict[str, Any]:
    """Apply a category to the VendorBillLine. Uses the AI-suggested
    category by default; `category_override` replaces it with a
    user-chosen value.

    Equivalent write pattern to
    `ApprovalGateService._apply_expense_categories`:
    sets `VendorBillLine.expense_category` and resolves the anomaly.
    """
    anomaly = _load_anomaly_scoped(
        db, anomaly_id=anomaly_id, company_id=user.company_id
    )
    if anomaly.entity_type != "vendor_bill_line" or not anomaly.entity_id:
        raise ValueError(
            "Expected anomaly with entity_type='vendor_bill_line' and "
            f"a line_id; got entity_type={anomaly.entity_type!r}"
        )

    line = _load_vendor_bill_line_scoped(
        db, line_id=anomaly.entity_id, company_id=user.company_id
    )

    if category_override:
        category_to_apply = category_override
        source = "user-override"
    else:
        from app.models.agent import AgentJob  # local import to avoid cycle

        job = (
            db.query(AgentJob)
            .filter(AgentJob.id == anomaly.agent_job_id)
            .first()
        )
        if job is None:
            raise ValueError(
                f"AgentJob {anomaly.agent_job_id} not found for anomaly"
            )
        category_to_apply = _proposed_category_for_line(
            job, anomaly.entity_id
        )
        if not category_to_apply:
            raise ValueError(
                f"No AI-suggested category available for line "
                f"{anomaly.entity_id}; provide category_override to "
                "approve this line"
            )
        source = "ai-suggestion"

    line.expense_category = category_to_apply
    db.flush()
    _resolve_anomaly(
        db,
        anomaly=anomaly,
        user_id=user.id,
        note=(
            f"Categorized via triage as '{category_to_apply}' "
            f"({source})"
        ),
    )
    db.commit()
    return {
        "status": "applied",
        "message": (
            f"VendorBillLine categorized as '{category_to_apply}'"
        ),
        "line_id": line.id,
        "category_applied": category_to_apply,
        "source": source,
        "anomaly_resolved": True,
    }


def reject_line(
    db: Session,
    *,
    user: User,
    anomaly_id: str,
    reason: str,
) -> dict[str, Any]:
    """Reject — resolves anomaly with a reason; no category write.
    Line stays uncategorized for manual handling."""
    if not reason:
        raise ValueError("Reason is required to reject a line")

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
        "message": "Line rejected — no category applied.",
        "line_id": anomaly.entity_id,
        "anomaly_resolved": True,
    }


def request_review_line(
    db: Session,
    *,
    user: User,
    anomaly_id: str,
    note: str,
) -> dict[str, Any]:
    if not note:
        raise ValueError("Note is required when requesting review")

    anomaly = _load_anomaly_scoped(
        db, anomaly_id=anomaly_id, company_id=user.company_id
    )
    stamp = (
        f"[review-requested by {user.id} at "
        f"{datetime.now(timezone.utc).isoformat()}] {note}"
    )
    existing = anomaly.resolution_note or ""
    anomaly.resolution_note = (
        f"{existing}\n{stamp}" if existing else stamp
    )
    db.flush()
    db.commit()
    return {
        "status": "applied",
        "message": "Review requested — item stays in queue.",
        "line_id": anomaly.entity_id,
        "anomaly_resolved": False,
    }


__all__ = [
    "run_categorization_pipeline",
    "approve_line",
    "reject_line",
    "request_review_line",
]
