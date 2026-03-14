"""Platform fee configuration and management routes — admin-only."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.platform_fee import (
    FeeRateConfigCreate,
    FeeRateConfigResponse,
    FeeRateConfigUpdate,
    FeeStats,
    PaginatedFees,
    PlatformFeeResponse,
    WaiveFeeRequest,
)
from app.services import platform_fee_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Fee Rate Configs
# ---------------------------------------------------------------------------


@router.get("/configs", response_model=list[FeeRateConfigResponse])
def list_fee_configs(
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all fee rate configurations."""
    return platform_fee_service.get_fee_configs(db)


@router.post("/configs", response_model=FeeRateConfigResponse)
def create_fee_config(
    body: FeeRateConfigCreate,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new fee rate configuration."""
    config = platform_fee_service.create_fee_config(db, body)
    return FeeRateConfigResponse.model_validate(config)


@router.patch("/configs/{config_id}", response_model=FeeRateConfigResponse)
def update_fee_config(
    config_id: str,
    body: FeeRateConfigUpdate,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update a fee rate configuration."""
    config = platform_fee_service.update_fee_config(db, config_id, body)
    return FeeRateConfigResponse.model_validate(config)


@router.delete("/configs/{config_id}", status_code=204)
def delete_fee_config(
    config_id: str,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete a fee rate configuration."""
    platform_fee_service.delete_fee_config(db, config_id)


# ---------------------------------------------------------------------------
# Platform Fees
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=FeeStats)
def get_fee_stats(
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get aggregated fee statistics."""
    return platform_fee_service.get_fee_stats(db)


@router.get("", response_model=PaginatedFees)
def list_fees(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    status: str | None = None,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List platform fees with optional status filter."""
    items, total = platform_fee_service.get_fees(db, page, per_page, status)
    return PaginatedFees(items=items, total=total, page=page, per_page=per_page)


@router.post("/{fee_id}/collect", response_model=PlatformFeeResponse)
def collect_fee(
    fee_id: str,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Mark a pending fee as collected."""
    fee = platform_fee_service.collect_fee(db, fee_id)
    return PlatformFeeResponse.model_validate(fee)


@router.post("/{fee_id}/waive", response_model=PlatformFeeResponse)
def waive_fee(
    fee_id: str,
    body: WaiveFeeRequest,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Waive a pending fee."""
    fee = platform_fee_service.waive_fee(db, fee_id, user.id, body.reason)
    return PlatformFeeResponse.model_validate(fee)
