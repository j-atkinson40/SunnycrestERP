"""Month-End Close — parity adapter (Workflow Arc Phase 8c).

Thin bridge between the workflow engine / triage engine and the
existing `MonthEndCloseAgent` + `ApprovalGateService._process_approve`
full-approval path. Preserves all side effects via service reuse.

The central parity claim of Phase 8c for month-end close:
  For a given AgentJob that reached `awaiting_approval`, approving
  via triage produces IDENTICAL side effects to calling
  `ApprovalGateService._process_approve` directly from the legacy
  /agents/:id/review page:
    - 1 StatementRun row
    - N CustomerStatement rows (one per eligible customer)
    - Auto-approved CustomerStatementItem rows for non-critical
      customers (status = approved, auto-approval note stamped)
    - 1 PeriodLock row (positive assertion — this is the full-approval
      agent that writes financial period state)
    - Updated `agent_jobs.status="complete"` + `.completed_at`
    - Updated `agent_jobs.report_payload` with statement_run_id,
      statement_items_auto_approved, statement_items_total

Verified by `test_month_end_close_migration_parity.py` (BLOCKING).

Rollback gap (pre-existing, NOT fixed in Phase 8c):
  `ApprovalGateService._trigger_statement_run` catches all exceptions
  (approval_gate.py:359), logs, writes `statement_run_error` into
  `report_payload`, and returns silently. Execution proceeds to the
  period lock at line 251 — which still fires. Net effect if
  statement generation fails halfway: partial CustomerStatement rows
  committed + period locked + operator has no signal beyond
  `report_payload.statement_run_error`. Phase 8c preserves this
  behavior verbatim for parity; the correctness fix is flagged in
  WORKFLOW_MIGRATION_TEMPLATE.md §11 for a dedicated cleanup session.

Public functions:

  run_close_pipeline(db, *, company_id, triggered_by_user_id,
                     period_start=None, period_end=None, dry_run=False,
                     trigger_source="workflow") -> dict
      Execute the 8-step close agent. Creates an AgentJob row +
      runs it to `awaiting_approval`. Returns a summary with the
      agent_job_id + anomaly counts. Period defaults to the
      previous calendar month when not supplied (matches the
      operational convention of closing the month just ended).

  approve_close(db, *, user, agent_job_id) -> dict
      Triage "approve" action. Delegates to
      `ApprovalGateService._process_approve` via a synthesized
      ApprovalAction(action="approve"). Preserves all side effects
      (statement run + period lock + auto-approval).

  reject_close(db, *, user, agent_job_id, reason) -> dict
      Triage "reject" action. Delegates to `_process_reject` —
      status flips to rejected, reason captured, NO period lock,
      NO statement run.

Zero-duplication discipline:
  - `run_close_pipeline` delegates the 8-step execution entirely to
    `AgentRunner.run_job`.
  - `approve_close` delegates side effects entirely to
    `ApprovalGateService._process_approve`.
  - `reject_close` delegates to `_process_reject`.
  - This module adds tenant-scoped loading + a consistent return
    shape; it does NOT re-implement any of the real logic.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.agent import AgentJob
from app.models.user import User
from app.schemas.agent import AgentJobStatus, AgentJobType, ApprovalAction

logger = logging.getLogger(__name__)


# ── Pipeline entry (workflow-step surface) ───────────────────────────


def _default_prior_month_period() -> tuple[date, date]:
    """Previous calendar month — operational convention for month-end
    close when no explicit period is supplied."""
    today = date.today()
    first_of_this_month = today.replace(day=1)
    last_of_prior_month = first_of_this_month.replace(day=1)
    # Subtract one day to land on the last day of the prior month.
    from datetime import timedelta

    last_of_prior = first_of_this_month - timedelta(days=1)
    first_of_prior = last_of_prior.replace(day=1)
    return (first_of_prior, last_of_prior)


def run_close_pipeline(
    db: Session,
    *,
    company_id: str,
    triggered_by_user_id: str | None,
    period_start: date | None = None,
    period_end: date | None = None,
    dry_run: bool = False,
    trigger_source: str = "workflow",
) -> dict[str, Any]:
    """Create + execute a MonthEndCloseAgent job end-to-end.

    Agent runs through 8 read-only analysis steps and lands in
    `awaiting_approval`. Writes happen later, on `approve_close`.
    """
    from app.services.agents.agent_runner import AgentRunner

    if period_start is None or period_end is None:
        period_start, period_end = _default_prior_month_period()

    job = AgentJob(
        id=str(uuid.uuid4()),
        tenant_id=company_id,
        job_type=AgentJobType.MONTH_END_CLOSE.value,
        status=AgentJobStatus.PENDING.value,
        period_start=period_start,
        period_end=period_end,
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
        report.get("executive_summary", {}) if isinstance(report, dict) else {}
    )
    return {
        "agent_job_id": job.id,
        "status": job.status,
        "anomaly_count": job.anomaly_count,
        "critical_count": exec_summary.get("critical_anomaly_count", 0),
        "warning_count": exec_summary.get("warning_anomaly_count", 0),
        "info_count": exec_summary.get("info_anomaly_count", 0),
        "period_start": period_start.isoformat() if period_start else None,
        "period_end": period_end.isoformat() if period_end else None,
        "dry_run": dry_run,
    }


# ── Tenant-scoped job loader (defense-in-depth) ─────────────────────


def _load_job_scoped(
    db: Session, *, agent_job_id: str, company_id: str
) -> AgentJob:
    job = (
        db.query(AgentJob)
        .filter(
            AgentJob.id == agent_job_id,
            AgentJob.tenant_id == company_id,
        )
        .first()
    )
    if job is None:
        raise ValueError(
            f"AgentJob {agent_job_id} not found for this tenant"
        )
    return job


# ── Triage action helpers ────────────────────────────────────────────


def approve_close(
    db: Session,
    *,
    user: User,
    agent_job_id: str,
) -> dict[str, Any]:
    """Approve via the existing `ApprovalGateService._process_approve`
    full-approval path. Triggers statement run + period lock +
    auto-approval of unflagged statement items.

    **Zero logic duplication.** Statement-run rollback gap noted in
    module docstring is preserved verbatim.
    """
    from app.services.agents.approval_gate import ApprovalGateService

    job = _load_job_scoped(
        db, agent_job_id=agent_job_id, company_id=user.company_id
    )
    if job.status != "awaiting_approval":
        raise ValueError(
            f"Job {agent_job_id} is not awaiting approval "
            f"(status={job.status})"
        )

    # Stamp approver attribution (process_approve only sets approved_at).
    job.approved_by = user.id
    db.flush()

    # Use the full approval path — it handles statement_run +
    # period_lock + auto-approval + status transitions identically
    # to the legacy email-token + /agents/:id/review endpoints.
    action = ApprovalAction(action="approve")
    result = ApprovalGateService._process_approve(job, action, db)

    payload = result.report_payload or {}
    return {
        "status": "applied",
        "message": (
            f"Month-end close approved for "
            f"{result.period_start:%B %Y}. Statement run + period "
            f"lock written."
        ),
        "agent_job_id": result.id,
        "entity_state": result.status,
        "statement_run_id": payload.get("statement_run_id"),
        "statement_items_auto_approved": payload.get(
            "statement_items_auto_approved", 0
        ),
        "statement_items_total": payload.get("statement_items_total", 0),
    }


def reject_close(
    db: Session,
    *,
    user: User,
    agent_job_id: str,
    reason: str,
) -> dict[str, Any]:
    """Reject via `_process_reject`. Status flips to rejected, reason
    captured, NO period lock, NO statement run."""
    from app.services.agents.approval_gate import ApprovalGateService

    if not reason:
        raise ValueError("Reject reason is required")

    job = _load_job_scoped(
        db, agent_job_id=agent_job_id, company_id=user.company_id
    )
    if job.status != "awaiting_approval":
        raise ValueError(
            f"Job {agent_job_id} is not awaiting approval "
            f"(status={job.status})"
        )

    # approved_by is conventionally used for both approve and reject
    # attribution in the legacy code; keep the invariant.
    job.approved_by = user.id
    db.flush()
    action = ApprovalAction(action="reject", rejection_reason=reason)
    result = ApprovalGateService._process_reject(job, action, db)
    return {
        "status": "applied",
        "message": f"Month-end close rejected: {reason}",
        "agent_job_id": result.id,
        "entity_state": result.status,
        "rejection_reason": result.rejection_reason,
    }


def request_review_close(
    db: Session,
    *,
    user: User,
    agent_job_id: str,
    note: str,
) -> dict[str, Any]:
    """Request-review action. Stamps a note on the job's
    `report_payload.review_requests` list without changing status —
    the job stays `awaiting_approval` for someone else to pick up."""
    if not note:
        raise ValueError("A note is required when requesting review")

    job = _load_job_scoped(
        db, agent_job_id=agent_job_id, company_id=user.company_id
    )
    payload = dict(job.report_payload or {})
    reviews = list(payload.get("review_requests", []))
    reviews.append(
        {
            "by_user_id": user.id,
            "at": datetime.now(timezone.utc).isoformat(),
            "note": note,
        }
    )
    payload["review_requests"] = reviews
    job.report_payload = payload
    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(job, "report_payload")
    db.commit()
    return {
        "status": "applied",
        "message": "Review requested — job stays in queue.",
        "agent_job_id": job.id,
        "entity_state": job.status,
    }


__all__ = [
    "run_close_pipeline",
    "approve_close",
    "reject_close",
    "request_review_close",
]
