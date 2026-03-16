"""Platform admin — system health and monitoring routes."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_platform_role
from app.database import get_db
from app.models.platform_user import PlatformUser

router = APIRouter()


@router.get("/health")
def system_health(
    _user: PlatformUser = Depends(require_platform_role("super_admin", "support", "viewer")),
    db: Session = Depends(get_db),
):
    """System-wide health overview."""
    from app.models.company import Company
    from app.models.job_queue import Job
    from app.models.user import User

    cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)

    total_tenants = db.query(Company).count()
    active_tenants = db.query(Company).filter(Company.is_active.is_(True)).count()
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active.is_(True)).count()

    total_jobs_24h = db.query(Job).filter(Job.created_at >= cutoff_24h).count()
    failed_jobs_24h = (
        db.query(Job)
        .filter(Job.created_at >= cutoff_24h, Job.status.in_(["failed", "dead"]))
        .count()
    )

    redis_connected = False
    try:
        from app.core.redis import get_redis
        r = get_redis()
        if r:
            r.ping()
            redis_connected = True
    except Exception:
        pass

    return {
        "total_tenants": total_tenants,
        "active_tenants": active_tenants,
        "total_users": total_users,
        "active_users": active_users,
        "total_jobs_24h": total_jobs_24h,
        "failed_jobs_24h": failed_jobs_24h,
        "redis_connected": redis_connected,
        "db_connected": True,
    }


@router.get("/jobs")
def list_recent_jobs(
    _user: PlatformUser = Depends(require_platform_role("super_admin", "support")),
    db: Session = Depends(get_db),
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
):
    """Recent background jobs across all tenants."""
    from app.models.job_queue import Job

    query = db.query(Job)
    if status_filter:
        query = query.filter(Job.status == status_filter)

    jobs = query.order_by(Job.created_at.desc()).limit(limit).all()
    return [
        {
            "id": j.id,
            "company_id": j.company_id,
            "job_type": j.job_type,
            "status": j.status,
            "created_at": j.created_at,
            "started_at": j.started_at,
            "completed_at": j.completed_at,
            "error_message": j.error_message,
            "attempts": j.attempts,
        }
        for j in jobs
    ]


@router.get("/syncs")
def list_recent_syncs(
    _user: PlatformUser = Depends(require_platform_role("super_admin", "support", "viewer")),
    db: Session = Depends(get_db),
    tenant_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Recent sync logs across all tenants (or filtered by tenant)."""
    from app.models.sync_log import SyncLog

    query = db.query(SyncLog)
    if tenant_id:
        query = query.filter(SyncLog.company_id == tenant_id)

    syncs = query.order_by(SyncLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": s.id,
            "company_id": s.company_id,
            "direction": s.direction,
            "entity_type": s.entity_type,
            "status": s.status,
            "records_synced": s.records_synced,
            "error_message": s.error_message,
            "created_at": s.created_at,
        }
        for s in syncs
    ]
