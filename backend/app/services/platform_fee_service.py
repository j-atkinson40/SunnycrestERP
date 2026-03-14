"""Platform transaction fee service — calculate, collect, and waive fees."""

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.network_transaction import NetworkTransaction
from app.models.platform_fee import FeeRateConfig, PlatformFee
from app.schemas.platform_fee import (
    FeeRateConfigCreate,
    FeeRateConfigResponse,
    FeeRateConfigUpdate,
    FeeStats,
    PlatformFeeResponse,
)


# ---------------------------------------------------------------------------
# Fee Rate Config CRUD
# ---------------------------------------------------------------------------


def get_fee_configs(db: Session) -> list[FeeRateConfigResponse]:
    """List all fee rate configurations."""
    configs = db.query(FeeRateConfig).order_by(FeeRateConfig.transaction_type).all()
    return [FeeRateConfigResponse.model_validate(c) for c in configs]


def create_fee_config(db: Session, data: FeeRateConfigCreate) -> FeeRateConfig:
    """Create a new fee rate configuration."""
    config = FeeRateConfig(
        transaction_type=data.transaction_type,
        fee_type=data.fee_type,
        rate=data.rate,
        min_fee=data.min_fee,
        max_fee=data.max_fee,
        effective_from=data.effective_from,
        effective_until=data.effective_until,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def update_fee_config(
    db: Session, config_id: str, data: FeeRateConfigUpdate
) -> FeeRateConfig:
    """Update an existing fee rate configuration."""
    config = db.query(FeeRateConfig).filter(FeeRateConfig.id == config_id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fee config not found"
        )
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(config, key, value)
    db.commit()
    db.refresh(config)
    return config


def delete_fee_config(db: Session, config_id: str) -> None:
    """Delete a fee rate configuration."""
    config = db.query(FeeRateConfig).filter(FeeRateConfig.id == config_id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fee config not found"
        )
    db.delete(config)
    db.commit()


# ---------------------------------------------------------------------------
# Fee calculation
# ---------------------------------------------------------------------------


def _get_applicable_config(
    db: Session, transaction_type: str
) -> FeeRateConfig | None:
    """Find the currently active fee config for a transaction type."""
    now = datetime.now(timezone.utc)
    config = (
        db.query(FeeRateConfig)
        .filter(
            FeeRateConfig.transaction_type == transaction_type,
            (FeeRateConfig.effective_from.is_(None)) | (FeeRateConfig.effective_from <= now),
            (FeeRateConfig.effective_until.is_(None)) | (FeeRateConfig.effective_until > now),
        )
        .order_by(FeeRateConfig.created_at.desc())
        .first()
    )
    return config


def calculate_fee(
    db: Session, network_transaction_id: str, base_amount: Decimal
) -> PlatformFee | None:
    """Calculate and attach a platform fee to a network transaction.

    Returns None if no applicable fee config or rate is zero.
    """
    tx = (
        db.query(NetworkTransaction)
        .filter(NetworkTransaction.id == network_transaction_id)
        .first()
    )
    if not tx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Network transaction not found",
        )

    config = _get_applicable_config(db, tx.transaction_type)
    if not config or config.rate == Decimal("0"):
        return None

    # Calculate
    if config.fee_type == "flat_fee":
        calculated = config.rate
    else:  # transaction_percent
        calculated = base_amount * config.rate

    # Apply min/max
    if calculated < config.min_fee:
        calculated = config.min_fee
    if config.max_fee is not None and calculated > config.max_fee:
        calculated = config.max_fee

    fee = PlatformFee(
        network_transaction_id=network_transaction_id,
        fee_rate_config_id=config.id,
        fee_type=config.fee_type,
        rate=config.rate,
        base_amount=base_amount,
        calculated_amount=calculated,
    )
    db.add(fee)
    db.commit()
    db.refresh(fee)
    return fee


# ---------------------------------------------------------------------------
# Fee lifecycle
# ---------------------------------------------------------------------------


def get_fees(
    db: Session,
    page: int = 1,
    per_page: int = 25,
    status_filter: str | None = None,
) -> tuple[list[PlatformFeeResponse], int]:
    """List platform fees with optional status filter."""
    q = db.query(PlatformFee)
    if status_filter:
        q = q.filter(PlatformFee.status == status_filter)
    total = q.count()
    rows = (
        q.order_by(PlatformFee.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    items = [PlatformFeeResponse.model_validate(r) for r in rows]
    return items, total


def collect_fee(db: Session, fee_id: str) -> PlatformFee:
    """Mark a fee as collected."""
    fee = db.query(PlatformFee).filter(PlatformFee.id == fee_id).first()
    if not fee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fee not found")
    if fee.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot collect a fee with status '{fee.status}'",
        )
    fee.status = "collected"
    fee.collected_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(fee)
    return fee


def waive_fee(
    db: Session, fee_id: str, actor_id: str, reason: str
) -> PlatformFee:
    """Waive a pending fee."""
    fee = db.query(PlatformFee).filter(PlatformFee.id == fee_id).first()
    if not fee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fee not found")
    if fee.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot waive a fee with status '{fee.status}'",
        )
    fee.status = "waived"
    fee.waived_by = actor_id
    fee.waived_reason = reason
    db.commit()
    db.refresh(fee)
    return fee


def get_fee_stats(db: Session) -> FeeStats:
    """Aggregate fee statistics."""
    total = db.query(PlatformFee).count()

    def _sum_by_status(s: str) -> Decimal:
        result = (
            db.query(func.coalesce(func.sum(PlatformFee.calculated_amount), 0))
            .filter(PlatformFee.status == s)
            .scalar()
        )
        return Decimal(str(result))

    pending = _sum_by_status("pending")
    collected = _sum_by_status("collected")
    waived = _sum_by_status("waived")

    return FeeStats(
        total_fees=total,
        pending_amount=pending,
        collected_amount=collected,
        waived_amount=waived,
        total_revenue=collected,
    )
