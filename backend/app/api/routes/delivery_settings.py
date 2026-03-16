"""Delivery settings management routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_module, require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.delivery import DELIVERY_PRESETS, DeliverySettingsResponse, DeliverySettingsUpdate
from app.services import delivery_settings_service

router = APIRouter()

MODULE = "driver_delivery"


@router.get("/delivery", response_model=DeliverySettingsResponse)
def get_delivery_settings(
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("delivery.view")),
):
    return delivery_settings_service.get_settings(db, current_user.company_id)


@router.put("/delivery", response_model=DeliverySettingsResponse)
def update_delivery_settings(
    data: DeliverySettingsUpdate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("delivery.edit")),
):
    return delivery_settings_service.update_settings(
        db, current_user.company_id, data.model_dump(exclude_none=True)
    )


@router.post("/delivery/preset/{preset_name}", response_model=DeliverySettingsResponse)
def apply_preset(
    preset_name: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("delivery.edit")),
):
    if preset_name not in DELIVERY_PRESETS:
        raise HTTPException(status_code=400, detail=f"Unknown preset: {preset_name}")
    return delivery_settings_service.apply_preset(db, current_user.company_id, preset_name)


@router.get("/delivery/presets")
def list_presets(
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("delivery.view")),
):
    return {"presets": list(DELIVERY_PRESETS.keys())}
