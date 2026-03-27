"""Agent API routes — alerts, collections, payment runs, activity log."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
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
