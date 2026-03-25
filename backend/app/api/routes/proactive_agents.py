"""Proactive agent API routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.database import get_db
from app.models.user import User
from app.services.proactive_agents import (
    PROACTIVE_JOBS,
    check_duplicate_bill,
    generate_year_end_checklist,
    run_tax_filing_prep,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/jobs/run/{job_name}")
def run_job_manually(
    job_name: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Manually trigger a proactive agent job (admin only)."""
    job_fn = PROACTIVE_JOBS.get(job_name)
    if not job_fn:
        raise HTTPException(status_code=404, detail=f"Job '{job_name}' not found. Available: {list(PROACTIVE_JOBS.keys())}")
    try:
        result = job_fn(db, current_user.company_id)
        return {"job": job_name, "result": result}
    except Exception as e:
        logger.exception("Proactive job %s failed", job_name)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check-duplicate-bill")
def check_duplicate(
    vendor_id: str = Query(...),
    amount: float = Query(...),
    bill_date: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pre-save duplicate invoice check."""
    from datetime import date as d
    warning = check_duplicate_bill(
        db, current_user.company_id, vendor_id, amount, d.fromisoformat(bill_date),
    )
    if warning:
        return warning
    return {"warning": False}


@router.get("/tax-filing-prep")
def get_tax_filing_prep(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get tax filing preparation data for prior period."""
    return run_tax_filing_prep(db, current_user.company_id)


@router.get("/year-end-checklist")
def get_year_end_checklist(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get personalized year-end closing checklist."""
    items = generate_year_end_checklist(db, current_user.company_id)
    return {"items": items, "total": len(items)}
