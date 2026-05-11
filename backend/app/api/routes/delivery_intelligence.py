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
    DEFAULT_CONFIG,
    build_forecast_range,
    check_order_conflict,
    get_active_conflicts,
    get_blocks,
    get_config,
    get_drivers,
    get_forecasts,
    resolve_conflict,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class ConfigUpdate(BaseModel):
    config: dict


@router.get("/config")
def get_delivery_config(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get delivery intelligence configuration."""
    return get_config(db, current_user.company_id)


@router.patch("/config")
def update_delivery_config(
    body: ConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update delivery intelligence configuration."""
    from app.models.company import Company
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if not company:
        raise HTTPException(status_code=404)

    # Merge with existing config
    current = get_config(db, current_user.company_id)
    updated = {**current, **body.config}

    # Validate
    if "flag_at_risk_level" in updated:
        if updated["flag_at_risk_level"] not in ("moderate", "high"):
            raise HTTPException(status_code=400, detail="flag_at_risk_level must be 'moderate' or 'high'")
    if "minimum_days_to_flag" in updated:
        if not (1 <= updated["minimum_days_to_flag"] <= 60):
            raise HTTPException(status_code=400, detail="minimum_days_to_flag must be 1-60")

    # Save to tenant_settings
    settings = dict(company.settings or {})
    settings["delivery_intelligence_config"] = updated
    company.settings = settings
    db.commit()

    return updated


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


# R-7-ε: function renamed from `list_drivers` to `list_intelligence_drivers`
# to resolve FastAPI duplicate Operation ID collision with the canonical
# driver-CRUD endpoint at `app/api/routes/deliveries.py::list_drivers`.
# Both routes serve `/drivers` under different router prefixes
# (delivery-intelligence vs deliveries) but FastAPI's default
# operationId derivation uses the function name. Distinct names keep
# OpenAPI client SDK generators + tooling integrations functional.
@router.get("/drivers")
def list_intelligence_drivers(
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
