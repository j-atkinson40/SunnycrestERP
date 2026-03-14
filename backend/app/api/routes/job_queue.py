"""Job queue management and sync monitoring endpoints."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database import get_db
from app.models.company import Company
from app.models.sync_log import SyncLog
from app.models.user import User
from app.schemas.job_queue import (
    JobEnqueueRequest,
    JobResponse,
    QueueStatsResponse,
    SyncDashboardResponse,
    SyncHealthTenant,
)
from app.services import job_queue_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Queue management
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=QueueStatsResponse)
def queue_stats(
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get queue depth, worker status, and dead letter count."""
    stats = job_queue_service.get_queue_stats(db)
    return QueueStatsResponse(**stats)


@router.post("/enqueue", response_model=JobResponse, status_code=201)
def enqueue_job(
    body: JobEnqueueRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Manually enqueue a background job."""
    job = job_queue_service.enqueue(
        db=db,
        company_id=current_user.company_id,
        job_type=body.job_type,
        payload=body.payload,
        priority=body.priority,
        max_retries=body.max_retries,
        delay_seconds=body.delay_seconds,
        created_by=current_user.id,
    )
    return job


@router.get("/jobs", response_model=dict)
def list_jobs(
    status: str | None = None,
    job_type: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List jobs with optional filters."""
    result = job_queue_service.get_jobs(
        db,
        company_id=current_user.company_id,
        status=status,
        job_type=job_type,
        page=page,
        per_page=per_page,
    )
    result["items"] = [
        JobResponse.model_validate(j).model_dump() for j in result["items"]
    ]
    return result


@router.get("/dead-letter", response_model=dict)
def list_dead_letter(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List dead-lettered jobs."""
    result = job_queue_service.get_dead_letter_jobs(db, page, per_page)
    result["items"] = [
        JobResponse.model_validate(j).model_dump() for j in result["items"]
    ]
    return result


@router.post("/dead-letter/{job_id}/retry", response_model=JobResponse)
def retry_dead_letter(
    job_id: str,
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Manually retry a dead-lettered job."""
    job = job_queue_service.retry_dead_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Dead letter job not found")
    return job


# ---------------------------------------------------------------------------
# Sync monitoring dashboard
# ---------------------------------------------------------------------------


@router.get("/sync-dashboard", response_model=SyncDashboardResponse)
def sync_dashboard(
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get sync health for all tenants + queue stats."""
    cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    cutoff_yellow = datetime.now(timezone.utc) - timedelta(hours=6)

    # Get all active companies
    companies = db.query(Company).filter(Company.is_active.is_(True)).all()

    tenants: list[SyncHealthTenant] = []

    for company in companies:
        # Last sync log
        last_sync = (
            db.query(SyncLog)
            .filter(SyncLog.company_id == company.id)
            .order_by(SyncLog.created_at.desc())
            .first()
        )

        # 24h counts
        total_24h = (
            db.query(func.count(SyncLog.id))
            .filter(
                SyncLog.company_id == company.id,
                SyncLog.created_at >= cutoff_24h,
            )
            .scalar()
            or 0
        )
        failed_24h = (
            db.query(func.count(SyncLog.id))
            .filter(
                SyncLog.company_id == company.id,
                SyncLog.created_at >= cutoff_24h,
                SyncLog.status == "failed",
            )
            .scalar()
            or 0
        )

        # Determine health status
        if last_sync is None:
            health = "green"  # No syncs = no problems
        elif last_sync.status == "failed":
            # Check if 3+ consecutive failures
            recent_syncs = (
                db.query(SyncLog.status)
                .filter(SyncLog.company_id == company.id)
                .order_by(SyncLog.created_at.desc())
                .limit(3)
                .all()
            )
            consecutive_failures = sum(
                1 for (s,) in recent_syncs if s == "failed"
            )
            health = "red" if consecutive_failures >= 3 else "yellow"
        elif last_sync.created_at and last_sync.created_at < cutoff_yellow:
            health = "yellow"  # No sync in 6+ hours
        else:
            health = "green"

        tenants.append(
            SyncHealthTenant(
                company_id=company.id,
                company_name=company.name,
                status=health,
                last_sync_at=last_sync.created_at if last_sync else None,
                last_sync_type=last_sync.sync_type if last_sync else None,
                last_sync_status=last_sync.status if last_sync else None,
                error_message=last_sync.error_message if last_sync else None,
                total_syncs_24h=total_24h,
                failed_syncs_24h=failed_24h,
            )
        )

    queue = job_queue_service.get_queue_stats(db)

    return SyncDashboardResponse(
        tenants=tenants,
        queue_stats=QueueStatsResponse(**queue),
    )
