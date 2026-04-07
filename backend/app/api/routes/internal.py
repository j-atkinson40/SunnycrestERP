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


@router.get("/trigger-auto-delivery")
def preview_auto_delivery(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Preview which orders are eligible for auto-delivery today."""
    from datetime import date
    from app.models.sales_order import SalesOrder
    from app.models.invoice import Invoice
    from app.models.customer import Customer

    today = date.today()
    tenant_id = current_user.company_id

    skip_statuses = {"canceled", "cancelled", "postponed"}
    already_invoiced = set(
        r[0] for r in db.query(Invoice.sales_order_id)
        .filter(Invoice.company_id == tenant_id, Invoice.sales_order_id.isnot(None))
        .all()
    )

    # All non-terminal funeral orders
    all_orders = (
        db.query(SalesOrder)
        .filter(
            SalesOrder.company_id == tenant_id,
            ~SalesOrder.status.in_(skip_statuses),
            SalesOrder.status.in_(["confirmed", "processing", "shipped", "delivered"]),
        )
        .order_by(SalesOrder.scheduled_date.asc().nullslast())
        .all()
    )

    # Batch load customer names
    cust_ids = {o.customer_id for o in all_orders if o.customer_id}
    customers = {c.id: c.name for c in db.query(Customer).filter(Customer.id.in_(cust_ids)).all()} if cust_ids else {}

    eligible = []
    ineligible = []

    for o in all_orders:
        info = {
            "order_id": o.id,
            "order_number": o.number,
            "customer_name": customers.get(o.customer_id, "Unknown"),
            "scheduled_date": str(o.scheduled_date) if o.scheduled_date else None,
            "required_date": str(o.required_date) if o.required_date else None,
            "status": o.status,
        }

        if o.id in already_invoiced:
            ineligible.append({**info, "reason_skipped": "already invoiced"})
        elif o.scheduled_date and o.scheduled_date <= today:
            eligible.append({**info, "reason_eligible": f"scheduled_date {o.scheduled_date} <= today"})
        elif o.scheduled_date and o.scheduled_date > today:
            ineligible.append({**info, "reason_skipped": f"scheduled for {o.scheduled_date} (future)"})
        elif o.required_date:
            req_date = o.required_date.date() if hasattr(o.required_date, "date") else o.required_date
            if req_date <= today:
                eligible.append({**info, "reason_eligible": f"required_date {req_date} <= today (no scheduled_date)"})
            else:
                ineligible.append({**info, "reason_skipped": f"required_date {req_date} is future"})
        else:
            ineligible.append({**info, "reason_skipped": "no scheduled_date or required_date set"})

    return {
        "date": str(today),
        "tenant_id": tenant_id,
        "eligible_count": len(eligible),
        "ineligible_count": len(ineligible),
        "eligible_orders": eligible,
        "ineligible_orders": ineligible,
    }


@router.post("/trigger-auto-delivery")
def execute_auto_delivery(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Execute the auto-delivery job for the current tenant only."""
    from app.services.draft_invoice_service import generate_draft_invoices

    logger.info(f"Manual auto-delivery trigger by {current_user.email}")
    try:
        generate_draft_invoices(db, current_user.company_id)
        return {
            "status": "completed",
            "triggered_by": current_user.email,
            "triggered_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Auto-delivery trigger failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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
