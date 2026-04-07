"""Internal endpoints — job triggers, scheduler health."""

import logging
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


class TriggerRequest(BaseModel):
    job_type: str


@router.post("/jobs/trigger")
def trigger_job(
    body: TriggerRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Manually trigger a scheduled job. Admin only. Runs async in background."""
    from app.scheduler import JOB_REGISTRY

    func = JOB_REGISTRY.get(body.job_type)
    if not func:
        available = sorted(JOB_REGISTRY.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Unknown job: {body.job_type}. Available: {available}",
        )

    logger.info(f"Manual trigger: {body.job_type} by {current_user.email}")
    thread = threading.Thread(target=func, daemon=True)
    thread.start()
    return {
        "status": "triggered_async",
        "job_type": body.job_type,
        "triggered_by": current_user.email,
        "triggered_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/jobs/registry")
def list_jobs(
    current_user: User = Depends(get_current_user),
):
    """List all registered jobs."""
    from app.scheduler import JOB_REGISTRY

    return {"jobs": sorted(JOB_REGISTRY.keys()), "count": len(JOB_REGISTRY)}


@router.get("/jobs/runs")
def list_job_runs(
    limit: int = 50,
    job_type: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List recent job runs from the audit log."""
    from app.models.job_run import JobRun

    q = db.query(JobRun).order_by(JobRun.started_at.desc())
    if job_type:
        q = q.filter(JobRun.job_type == job_type)
    runs = q.limit(limit).all()
    return [
        {
            "id": r.id,
            "job_type": r.job_type,
            "trigger": r.trigger,
            "status": r.status,
            "tenant_count": r.tenant_count,
            "success_count": r.success_count,
            "error_count": r.error_count,
            "duration_seconds": r.duration_seconds,
            "error_message": r.error_message,
            "triggered_by": r.triggered_by,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        }
        for r in runs
    ]


@router.get("/scheduler/status")
def scheduler_status(
    current_user: User = Depends(get_current_user),
):
    """Get scheduler health and next-run times."""
    from app.scheduler import scheduler

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append(
            {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat()
                if job.next_run_time
                else None,
            }
        )

    return {
        "running": scheduler.running,
        "job_count": len(jobs),
        "jobs": jobs,
    }
