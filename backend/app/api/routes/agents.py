"""Agent API routes — alerts, collections, payment runs, activity log, accounting agents."""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.database import SessionLocal, get_db
from app.models.agent import AgentJob
from app.models.agent_anomaly import AgentAnomaly
from app.models.agent_schedule import AgentSchedule
from app.models.user import User
from app.schemas.agent import (
    AgentAnomalyResponse,
    AgentJobCreate,
    AgentJobListItem,
    AgentJobResponse,
    AgentScheduleCreate,
    AgentScheduleResponse,
    AnomalyResolve,
    ApprovalAction,
    PeriodLockResponse,
)
from app.services.agent_service import (
    get_activity_log,
    get_alerts,
    get_collection_sequence,
    pause_collection,
    resolve_alert,
    run_ap_upcoming_payments,
    run_ar_aging_monitor,
    run_collections_sequence,
)
from app.services.agents.agent_runner import AgentRunner
from app.services.agents.approval_gate import ApprovalGateService
from app.services.agents.period_lock import PeriodLockService

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Manual job triggers (for testing and admin use)
# ---------------------------------------------------------------------------


class TriggerRequest(BaseModel):
    job_type: str  # ar_aging_monitor, collections_sequence, ap_upcoming_payments


@router.post("/jobs/trigger")
def trigger_job(
    body: TriggerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually trigger an agent job."""
    # Direct runners (run for current tenant with current DB session)
    direct_runners = {
        "ar_aging_monitor": run_ar_aging_monitor,
        "collections_sequence": run_collections_sequence,
        "ap_upcoming_payments": run_ap_upcoming_payments,
    }
    runner = direct_runners.get(body.job_type)
    if runner:
        result = runner(db, current_user.company_id)
        return result

    # Scheduler-registered jobs (run via scheduler wrappers)
    from app.scheduler import JOB_REGISTRY
    scheduled_runner = JOB_REGISTRY.get(body.job_type)
    if scheduled_runner:
        import threading
        threading.Thread(target=scheduled_runner, daemon=True).start()
        return {"job_type": body.job_type, "status": "triggered_async"}

    raise HTTPException(
        status_code=400,
        detail=f"Unknown job type: {body.job_type}. Available: {list(direct_runners.keys()) + list(JOB_REGISTRY.keys())}",
    )


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------


@router.get("/alerts")
def list_alerts(
    severity: str | None = Query(None),
    resolved: bool | None = Query(None),
    limit: int = Query(50, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get agent alerts for the current tenant."""
    return get_alerts(db, current_user.company_id, severity=severity, resolved=resolved, limit=limit)


@router.post("/alerts/{alert_id}/resolve")
def resolve_alert_endpoint(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Resolve an agent alert."""
    success = resolve_alert(db, alert_id, current_user.company_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "ok"}


@router.post("/alerts/{alert_id}/dismiss")
def dismiss_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dismiss (resolve) an info alert."""
    success = resolve_alert(db, alert_id, current_user.company_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------


@router.get("/collections/{sequence_id}")
def get_collection(
    sequence_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a collection sequence with draft email for review."""
    result = get_collection_sequence(db, sequence_id, current_user.company_id)
    if not result:
        raise HTTPException(status_code=404, detail="Collection sequence not found")
    return result


class CollectionSendRequest(BaseModel):
    subject: str
    body: str
    recipient_email: str


@router.post("/collections/{sequence_id}/send")
def send_collection(
    sequence_id: str,
    body: CollectionSendRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a reviewed collection email."""
    from app.models.agent import AgentCollectionSequence
    from app.services.agent_service import log_activity

    seq = (
        db.query(AgentCollectionSequence)
        .filter(AgentCollectionSequence.id == sequence_id, AgentCollectionSequence.tenant_id == current_user.company_id)
        .first()
    )
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence not found")

    # Track whether the draft was edited before sending
    original = seq.original_draft_body or seq.draft_body or ""
    current = body.body or ""
    seq.sent_without_edit = (original.strip() == current.strip())

    # Send via email service
    from app.services.email_service import email_service
    from app.models.company import Company
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    tenant_name = company.name if company else "Your supplier"
    reply_to = company.email if (company and hasattr(company, "email") and company.email) else current_user.email
    email_service.send_collections_email(
        customer_email=body.recipient_email,
        customer_name=seq.customer_name or "Valued Customer",
        subject=body.subject,
        body=current,
        tenant_name=tenant_name,
        reply_to_email=reply_to,
    )

    from datetime import datetime, timezone
    seq.last_sent_at = datetime.now(timezone.utc)
    if seq.sequence_step < 3:
        seq.sequence_step += 1
    else:
        seq.completed = True

    log_activity(
        db, current_user.company_id, "collection_email_sent",
        f"Step {seq.sequence_step - 1} email sent to {body.recipient_email}",
        record_type="collection_sequence", record_id=sequence_id,
        approved_by=current_user.id,
    )
    db.commit()
    return {"status": "sent"}


class PauseRequest(BaseModel):
    reason: str


@router.post("/collections/{sequence_id}/pause")
def pause_collection_endpoint(
    sequence_id: str,
    body: PauseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pause a collection sequence."""
    success = pause_collection(db, sequence_id, current_user.company_id, body.reason)
    if not success:
        raise HTTPException(status_code=404, detail="Sequence not found")
    return {"status": "paused"}


# ---------------------------------------------------------------------------
# Activity log
# ---------------------------------------------------------------------------


@router.get("/activity-log")
def list_activity_log(
    limit: int = Query(100, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get agent activity log."""
    return get_activity_log(db, current_user.company_id, limit=limit)


# ═══════════════════════════════════════════════════════════════════════════
# ACCOUNTING AGENT INFRASTRUCTURE
# ═══════════════════════════════════════════════════════════════════════════


def _run_agent_background(job_id: str):
    """Execute an agent job in a background thread with its own session."""
    db = SessionLocal()
    try:
        AgentRunner.run_job(job_id, db)
    except Exception as e:
        logger.error("Background agent job %s failed: %s", job_id, e)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Accounting agent job CRUD
# ---------------------------------------------------------------------------


@router.post("/accounting", status_code=201, response_model=AgentJobResponse)
def create_accounting_job(
    body: AgentJobCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create an accounting agent job and trigger execution in the background."""
    job = AgentRunner.create_job(
        db=db,
        tenant_id=current_user.company_id,
        job_type=body.job_type,
        period_start=body.period_start,
        period_end=body.period_end,
        dry_run=body.dry_run,
        triggered_by=current_user.id,
        trigger_type="manual",
    )
    background_tasks.add_task(_run_agent_background, job.id)
    return AgentJobResponse.model_validate(job)


@router.get("/accounting", response_model=list[AgentJobListItem])
def list_accounting_jobs(
    job_type: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List accounting agent jobs for the current tenant."""
    q = db.query(AgentJob).filter(
        AgentJob.tenant_id == current_user.company_id,
        AgentJob.period_start.isnot(None),  # Distinguish from legacy nightly jobs
    )
    if job_type:
        q = q.filter(AgentJob.job_type == job_type)
    if status_filter:
        q = q.filter(AgentJob.status == status_filter)

    jobs = q.order_by(desc(AgentJob.created_at)).offset(offset).limit(limit).all()
    return [AgentJobListItem.model_validate(j) for j in jobs]


@router.get("/accounting/{job_id}", response_model=AgentJobResponse)
def get_accounting_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get full accounting job detail with run_log."""
    job = AgentRunner.get_job_status(db, job_id, current_user.company_id)
    return AgentJobResponse.model_validate(job)


@router.get("/accounting/{job_id}/report", response_class=HTMLResponse)
def get_accounting_report(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get rendered HTML report for an accounting agent job."""
    job = AgentRunner.get_job_status(db, job_id, current_user.company_id)
    html = ApprovalGateService.generate_review_html(job)
    return HTMLResponse(content=html)


# ---------------------------------------------------------------------------
# Anomalies
# ---------------------------------------------------------------------------


@router.get("/accounting/{job_id}/anomalies", response_model=list[AgentAnomalyResponse])
def list_accounting_anomalies(
    job_id: str,
    severity: str | None = Query(None),
    resolved: bool | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List anomalies for an accounting job."""
    AgentRunner.get_job_status(db, job_id, current_user.company_id)
    q = db.query(AgentAnomaly).filter(AgentAnomaly.agent_job_id == job_id)
    if severity:
        q = q.filter(AgentAnomaly.severity == severity)
    if resolved is not None:
        q = q.filter(AgentAnomaly.resolved == resolved)
    return [AgentAnomalyResponse.model_validate(a) for a in q.all()]


@router.post("/accounting/{job_id}/anomalies/{anomaly_id}/resolve")
def resolve_accounting_anomaly(
    job_id: str,
    anomaly_id: str,
    body: AnomalyResolve,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark an anomaly as resolved."""
    AgentRunner.get_job_status(db, job_id, current_user.company_id)
    anomaly = (
        db.query(AgentAnomaly)
        .filter(AgentAnomaly.id == anomaly_id, AgentAnomaly.agent_job_id == job_id)
        .first()
    )
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")

    anomaly.resolved = True
    anomaly.resolved_by = current_user.id
    anomaly.resolved_at = datetime.now(timezone.utc)
    anomaly.resolution_note = body.resolution_note
    db.commit()
    return {"detail": "Anomaly resolved"}


# ---------------------------------------------------------------------------
# Approval webhook (token-based auth — no user session required)
# ---------------------------------------------------------------------------


@router.post("/approve/{token}")
def approve_via_token(
    token: str,
    body: ApprovalAction,
    db: Session = Depends(get_db),
):
    """Process approval/rejection via secure token (from email link)."""
    job = ApprovalGateService.process_approval(token, body, db)
    return AgentJobResponse.model_validate(job)


@router.get("/approve/{token}", response_class=HTMLResponse)
def approval_form(
    token: str,
    action: str = Query("approve"),
    db: Session = Depends(get_db),
):
    """Render a confirmation form for email button clicks."""
    job = db.query(AgentJob).filter(AgentJob.approval_token == token).first()
    if not job:
        return HTMLResponse(
            content="<h1>Invalid or expired token</h1><p>This approval link is no longer valid.</p>",
            status_code=404,
        )

    from app.services.agents.approval_gate import JOB_TYPE_LABELS
    label = JOB_TYPE_LABELS.get(job.job_type, job.job_type)
    period = f"{job.period_start} – {job.period_end}" if job.period_start else ""

    if action == "approve":
        form_html = f"""
        <h1>Approve: {label}</h1>
        <p>Period: {period}</p>
        <p>This will lock the period and mark the job as complete.</p>
        <form method="POST" action="/api/v1/agents/approve/{token}"
              enctype="application/json">
            <button type="submit" style="background:#16a34a;color:#fff;padding:12px 32px;
                border:none;border-radius:6px;font-size:16px;cursor:pointer;">
                Confirm Approval
            </button>
        </form>"""
    else:
        form_html = f"""
        <h1>Reject: {label}</h1>
        <p>Period: {period}</p>
        <form method="POST" action="/api/v1/agents/approve/{token}">
            <label>Rejection reason (required):</label><br>
            <textarea name="rejection_reason" rows="4"
                style="width:100%;margin:8px 0;" required></textarea><br>
            <button type="submit" style="background:#dc2626;color:#fff;padding:12px 32px;
                border:none;border-radius:6px;font-size:16px;cursor:pointer;">
                Confirm Rejection
            </button>
        </form>"""

    return HTMLResponse(content=f"""<!DOCTYPE html><html>
    <head><style>body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
        max-width:600px;margin:40px auto;padding:0 20px;}}</style></head>
    <body>{form_html}</body></html>""")


# ---------------------------------------------------------------------------
# Period locks
# ---------------------------------------------------------------------------


@router.get("/periods/locked", response_model=list[PeriodLockResponse])
def list_locked_periods(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List active period locks for the current tenant."""
    locks = PeriodLockService.get_active_locks(db, current_user.company_id)
    return [PeriodLockResponse.model_validate(l) for l in locks]


@router.get("/periods/check")
def check_period_lock(
    start_date: str = Query(...),
    end_date: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check if a date range overlaps with a locked period."""
    from datetime import date as date_type
    try:
        start = date_type.fromisoformat(start_date)
        end = date_type.fromisoformat(end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format (use YYYY-MM-DD)")

    locked = PeriodLockService.is_period_locked(db, current_user.company_id, start, end)
    result: dict = {"locked": locked}
    if locked:
        lock = PeriodLockService._find_overlapping_lock(db, current_user.company_id, start, end)
        if lock:
            result["lock"] = PeriodLockResponse.model_validate(lock).model_dump(mode="json")
    return result


@router.post("/periods/{lock_id}/unlock")
def unlock_period(
    lock_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Admin-only: unlock a period."""
    lock = PeriodLockService.unlock_period(db, lock_id, current_user.id)
    return PeriodLockResponse.model_validate(lock)


# ---------------------------------------------------------------------------
# Schedules
# ---------------------------------------------------------------------------


@router.post("/schedules", response_model=AgentScheduleResponse)
def create_or_update_schedule(
    body: AgentScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create or update an agent schedule."""
    existing = (
        db.query(AgentSchedule)
        .filter(
            AgentSchedule.tenant_id == current_user.company_id,
            AgentSchedule.job_type == body.job_type.value,
        )
        .first()
    )
    if existing:
        existing.is_enabled = body.is_enabled
        existing.cron_expression = body.cron_expression
        existing.run_day_of_month = body.run_day_of_month
        existing.run_hour = body.run_hour
        existing.timezone = body.timezone
        existing.auto_approve = body.auto_approve
        existing.notify_emails = body.notify_emails
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return AgentScheduleResponse.model_validate(existing)

    schedule = AgentSchedule(
        id=str(uuid.uuid4()),
        tenant_id=current_user.company_id,
        job_type=body.job_type.value,
        is_enabled=body.is_enabled,
        cron_expression=body.cron_expression,
        run_day_of_month=body.run_day_of_month,
        run_hour=body.run_hour,
        timezone=body.timezone,
        auto_approve=body.auto_approve,
        notify_emails=body.notify_emails,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return AgentScheduleResponse.model_validate(schedule)


@router.post("/schedules/{job_type}/toggle")
def toggle_schedule(
    job_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Enable or disable a schedule."""
    schedule = (
        db.query(AgentSchedule)
        .filter(
            AgentSchedule.tenant_id == current_user.company_id,
            AgentSchedule.job_type == job_type,
        )
        .first()
    )
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    schedule.is_enabled = not schedule.is_enabled
    schedule.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"job_type": job_type, "is_enabled": schedule.is_enabled}
