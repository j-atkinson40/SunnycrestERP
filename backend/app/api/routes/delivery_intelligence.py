"""Delivery intelligence API routes."""

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.delivery_intelligence_service import (
    build_forecast_range,
    check_order_conflict,
    get_active_conflicts,
    get_blocks,
    get_drivers,
    get_forecasts,
    resolve_conflict,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class ConflictCheckRequest(BaseModel):
    order_id: str | None = None
    delivery_date: str
    product_type: str
    customer_name: str | None = None


class ConflictResolveRequest(BaseModel):
    resolution: str  # 'resolved' | 'accepted'
    note: str | None = None


@router.get("/forecasts")
def list_forecasts(
    days: int = Query(21, ge=7, le=60),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_forecasts(db, current_user.company_id, days)


@router.post("/forecasts/refresh")
def refresh_forecasts(
    days: int = Query(21),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return build_forecast_range(db, current_user.company_id, days)


@router.get("/conflicts")
def list_conflicts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_active_conflicts(db, current_user.company_id)


@router.post("/check-conflict")
def check_conflict(
    body: ConflictCheckRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    delivery_date = date.fromisoformat(body.delivery_date)
    result = check_order_conflict(
        db, current_user.company_id, body.order_id,
        delivery_date, body.product_type, body.customer_name,
    )
    if not result:
        return {"conflict": False}
    return {"conflict": True, **result}


@router.patch("/conflicts/{conflict_id}/resolve")
def resolve(
    conflict_id: str,
    body: ConflictResolveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.resolution not in ("resolved", "accepted"):
        raise HTTPException(status_code=400, detail="Invalid resolution")
    if not resolve_conflict(db, conflict_id, body.resolution, current_user.id, body.note):
        raise HTTPException(status_code=404)
    return {"status": "ok"}


@router.get("/blocks")
def list_blocks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_blocks(db, current_user.company_id)


@router.get("/drivers")
def list_drivers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_drivers(db, current_user.company_id)


@router.get("/capacity-summary")
def capacity_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """14-day capacity summary for Operations Board zone."""
    forecasts = get_forecasts(db, current_user.company_id, 14)
    conflicts = get_active_conflicts(db, current_user.company_id)
    blocks = get_blocks(db, current_user.company_id)
    return {
        "forecasts": forecasts,
        "active_conflicts": len(conflicts),
        "conflicts": conflicts[:5],  # top 5 most urgent
        "active_blocks": len(blocks),
    }
