"""Finance charge API routes."""

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.finance_charge_service import (
    approve_all_pending,
    approve_item,
    forgive_item,
    get_run_items,
    get_runs,
    get_settings,
    post_approved_charges,
    run_calculation,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class ForgiveRequest(BaseModel):
    note: str | None = None


@router.get("/settings")
def get_fc_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_settings(db, current_user.company_id)


@router.get("/runs")
def list_runs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_runs(db, current_user.company_id)


@router.post("/runs/calculate")
def calculate(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = run_calculation(db, current_user.company_id, date.today(), "manual")
    if not result:
        raise HTTPException(status_code=400, detail="Finance charges not enabled")
    if result.get("already_exists"):
        raise HTTPException(status_code=409, detail="Run already exists for this month")
    return result


@router.get("/runs/{run_id}")
def get_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.finance_charge import FinanceChargeRun
    run = db.query(FinanceChargeRun).filter(FinanceChargeRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404)
    return {
        "id": run.id,
        "run_number": run.run_number,
        "status": run.status,
        "charge_month": run.charge_month,
        "charge_year": run.charge_year,
        "total_customers_charged": run.total_customers_charged,
        "total_amount_calculated": float(run.total_amount_calculated),
        "total_amount_posted": float(run.total_amount_posted),
        "total_amount_forgiven": float(run.total_amount_forgiven),
    }


@router.get("/runs/{run_id}/items")
def list_items(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_run_items(db, run_id)


@router.patch("/items/{item_id}/approve")
def approve(
    item_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not approve_item(db, item_id, current_user.id):
        raise HTTPException(status_code=400, detail="Cannot approve")
    return {"status": "approved"}


@router.patch("/items/{item_id}/forgive")
def forgive(
    item_id: str,
    body: ForgiveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not forgive_item(db, item_id, current_user.id, body.note):
        raise HTTPException(status_code=400, detail="Cannot forgive")
    return {"status": "forgiven"}


@router.post("/runs/{run_id}/approve-all")
def approve_all(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = approve_all_pending(db, run_id, current_user.id)
    return {"approved": count}


@router.post("/runs/{run_id}/post")
def post_charges(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = post_approved_charges(db, run_id, current_user.company_id, current_user.id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
