"""Delivery intelligence — demand prediction, conflict detection, capacity management."""

import logging
import math
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.delivery_intelligence import (
    DeliveryCapacityBlock,
    DeliveryConflictLog,
    DeliveryDemandForecast,
    DriverProfile,
)

logger = logging.getLogger(__name__)

SEASONAL_MULTIPLIERS = {1: 0.7, 2: 0.8, 3: 1.2, 4: 1.4, 5: 1.3, 6: 1.0, 7: 0.9, 8: 0.9, 9: 0.9, 10: 0.8, 11: 0.7, 12: 0.6}

DEFAULT_CONFIG = {
    "enabled": True,
    "show_operations_board_zone": True,
    "scheduling_warnings_enabled": True,
    "conflict_alerts_enabled": True,
    "block_suggestions_enabled": True,
    "blanket_block_reassessment_enabled": True,
    "weekly_review_alerts_enabled": True,
    "minimum_days_to_flag": 14,
    "flag_at_risk_level": "moderate",
}


def get_config(db: Session, tenant_id: str) -> dict:
    """Load delivery intelligence config with defaults."""
    from app.models.company import Company
    company = db.query(Company).filter(Company.id == tenant_id).first()
    if not company:
        return {**DEFAULT_CONFIG, "enabled": False}
    settings = getattr(company, "settings", None) or {}
    config = settings.get("delivery_intelligence_config") or {}
    # Merge with defaults — config keys override defaults
    return {**DEFAULT_CONFIG, **config}


def is_enabled(db: Session, tenant_id: str) -> bool:
    """Quick check if delivery intelligence is enabled for this tenant."""
    return get_config(db, tenant_id).get("enabled", False)


# ---------------------------------------------------------------------------
# Driver & Block Management
# ---------------------------------------------------------------------------


def get_drivers(db: Session, tenant_id: str) -> list[dict]:
    drivers = db.query(DriverProfile).filter(DriverProfile.tenant_id == tenant_id, DriverProfile.is_active.is_(True)).all()
    return [
        {
            "id": d.id, "name": d.name, "employee_id": d.employee_id,
            "funeral_certified": d.funeral_certified, "funeral_daily_rough_capacity": d.funeral_daily_rough_capacity,
            "can_deliver_wastewater": d.can_deliver_wastewater, "can_deliver_redi_rock": d.can_deliver_redi_rock,
            "can_deliver_rosetta": d.can_deliver_rosetta, "can_deliver_vault": d.can_deliver_vault,
            "default_working_days": d.default_working_days,
        }
        for d in drivers
    ]


def get_funeral_driver_count(db: Session, tenant_id: str, target_date: date) -> int:
    """Count funeral-capable drivers working on a given date."""
    dow = target_date.isoweekday()  # 1=Mon, 7=Sun
    drivers = (
        db.query(DriverProfile)
        .filter(
            DriverProfile.tenant_id == tenant_id,
            DriverProfile.is_active.is_(True),
            DriverProfile.funeral_certified.is_(True),
        )
        .all()
    )
    # Filter by working days
    count = 0
    for d in drivers:
        working = d.default_working_days or [1, 2, 3, 4, 5]
        if dow in working:
            # Check for driver-specific blocks
            blocked = (
                db.query(DeliveryCapacityBlock)
                .filter(
                    DeliveryCapacityBlock.tenant_id == tenant_id,
                    DeliveryCapacityBlock.driver_id == d.id,
                    DeliveryCapacityBlock.block_start <= target_date,
                    DeliveryCapacityBlock.block_end >= target_date,
                    DeliveryCapacityBlock.is_active.is_(True),
                    DeliveryCapacityBlock.overridden.is_(False),
                )
                .first()
            )
            if not blocked:
                count += 1
    return count


def get_blocks(db: Session, tenant_id: str, start: date | None = None, end: date | None = None) -> list[dict]:
    query = db.query(DeliveryCapacityBlock).filter(
        DeliveryCapacityBlock.tenant_id == tenant_id,
        DeliveryCapacityBlock.is_active.is_(True),
    )
    if start:
        query = query.filter(DeliveryCapacityBlock.block_end >= start)
    if end:
        query = query.filter(DeliveryCapacityBlock.block_start <= end)
    blocks = query.order_by(DeliveryCapacityBlock.block_start).all()
    return [
        {
            "id": b.id, "block_type": b.block_type, "blocked_product_types": b.blocked_product_types,
            "block_start": str(b.block_start), "block_end": str(b.block_end),
            "applies_to_days": b.applies_to_days, "reason": b.reason,
            "suggested_by_agent": b.suggested_by_agent, "overridden": b.overridden,
        }
        for b in blocks
    ]


def is_day_blocked(db: Session, tenant_id: str, target_date: date, product_type: str) -> dict | None:
    """Check if a specific day is blocked for a product type."""
    dow = target_date.isoweekday()
    block = (
        db.query(DeliveryCapacityBlock)
        .filter(
            DeliveryCapacityBlock.tenant_id == tenant_id,
            DeliveryCapacityBlock.block_start <= target_date,
            DeliveryCapacityBlock.block_end >= target_date,
            DeliveryCapacityBlock.is_active.is_(True),
            DeliveryCapacityBlock.overridden.is_(False),
        )
        .all()
    )
    for b in block:
        if product_type in (b.blocked_product_types or []):
            if b.applies_to_days is None or dow in b.applies_to_days:
                return {"blocked": True, "reason": b.reason, "block_type": b.block_type}
    return None


# ---------------------------------------------------------------------------
# Demand Prediction
# ---------------------------------------------------------------------------


def build_day_forecast(db: Session, tenant_id: str, target_date: date) -> dict:
    """Build funeral demand forecast for a single day."""
    from app.models.order import Order

    # Confirmed funerals
    confirmed = 0
    try:
        confirmed = (
            db.query(func.count(Order.id))
            .filter(
                Order.company_id == tenant_id,
                Order.order_area == "funeral",
                func.date(Order.scheduled_delivery_date) == target_date,
                Order.status.notin_(["cancelled"]),
            )
            .scalar() or 0
        )
    except Exception:
        pass  # Order model may not have these fields

    # Seasonal estimate (fallback)
    month = target_date.month
    multiplier = SEASONAL_MULTIPLIERS.get(month, 1.0)
    base = max(confirmed, round(2 * multiplier))
    low = max(confirmed, base - 1)
    high = base + 1
    confidence = Decimal("0.55")

    # Driver capacity
    total_drivers = get_funeral_driver_count(db, tenant_id, target_date)
    available_low = max(0, total_drivers - high)
    available_high = max(0, total_drivers - low)

    # Risk level
    if available_low == 0 and available_high == 0:
        risk = "critical"
    elif available_low == 0:
        risk = "high"
    elif available_low == 1:
        risk = "moderate"
    else:
        risk = "low"

    days_until = (target_date - date.today()).days
    recommend_block = risk in ("high", "critical") and days_until >= 7

    # Upsert forecast
    existing = (
        db.query(DeliveryDemandForecast)
        .filter(DeliveryDemandForecast.tenant_id == tenant_id, DeliveryDemandForecast.forecast_date == target_date)
        .first()
    )
    if existing:
        record = existing
    else:
        record = DeliveryDemandForecast(id=str(uuid.uuid4()), tenant_id=tenant_id, forecast_date=target_date)
        db.add(record)

    record.funeral_demand_low = low
    record.funeral_demand_high = high
    record.funeral_demand_confidence = confidence
    record.confirmed_funerals = confirmed
    record.portal_activity_signal = Decimal("0.50")
    record.total_funeral_drivers = total_drivers
    record.predicted_available_after_funerals_low = available_low
    record.predicted_available_after_funerals_high = available_high
    record.risk_level = risk
    record.recommend_block = recommend_block
    record.recommend_block_reason = f"High funeral demand predicted ({low}-{high})" if recommend_block else None
    record.computed_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "date": str(target_date),
        "funeral_demand_low": low, "funeral_demand_high": high,
        "confirmed_funerals": confirmed, "confidence": float(confidence),
        "total_funeral_drivers": total_drivers,
        "available_low": available_low, "available_high": available_high,
        "risk_level": risk, "recommend_block": recommend_block,
    }


def build_forecast_range(db: Session, tenant_id: str, days: int = 21) -> list[dict]:
    """Build forecasts for the next N days."""
    today = date.today()
    return [build_day_forecast(db, tenant_id, today + timedelta(days=i)) for i in range(days)]


def get_forecasts(db: Session, tenant_id: str, days: int = 21) -> list[dict]:
    """Get cached forecasts for display."""
    today = date.today()
    end = today + timedelta(days=days)
    forecasts = (
        db.query(DeliveryDemandForecast)
        .filter(
            DeliveryDemandForecast.tenant_id == tenant_id,
            DeliveryDemandForecast.forecast_date >= today,
            DeliveryDemandForecast.forecast_date <= end,
        )
        .order_by(DeliveryDemandForecast.forecast_date)
        .all()
    )
    return [
        {
            "date": str(f.forecast_date), "funeral_demand_low": f.funeral_demand_low,
            "funeral_demand_high": f.funeral_demand_high, "confirmed_funerals": f.confirmed_funerals,
            "confidence": float(f.funeral_demand_confidence) if f.funeral_demand_confidence else None,
            "total_funeral_drivers": f.total_funeral_drivers,
            "available_low": f.predicted_available_after_funerals_low,
            "available_high": f.predicted_available_after_funerals_high,
            "risk_level": f.risk_level, "recommend_block": f.recommend_block,
        }
        for f in forecasts
    ]


# ---------------------------------------------------------------------------
# Conflict Detection
# ---------------------------------------------------------------------------


def check_order_conflict(db: Session, tenant_id: str, order_id: str | None, delivery_date: date, product_type: str, customer_name: str | None = None) -> dict | None:
    """Check if a delivery has a conflict. Returns conflict data or None."""
    config = get_config(db, tenant_id)
    if not config.get("enabled", False):
        return None
    if not config.get("scheduling_warnings_enabled", True):
        return None

    # Check blocked
    block = is_day_blocked(db, tenant_id, delivery_date, product_type)
    if block:
        conflict_type = "blocked_day"
    else:
        # Check capacity
        forecast = build_day_forecast(db, tenant_id, delivery_date)
        if forecast["risk_level"] in ("high", "critical"):
            conflict_type = "capacity_risk"
        elif forecast["risk_level"] == "moderate" and forecast["available_high"] <= 1:
            conflict_type = "capacity_risk"
        else:
            return None

    days_until = (delivery_date - date.today()).days
    if days_until < 5:
        conflict_type = "under_5_day_warning"

    forecast_data = build_day_forecast(db, tenant_id, delivery_date)

    # Upsert conflict
    existing = None
    if order_id:
        existing = (
            db.query(DeliveryConflictLog)
            .filter(DeliveryConflictLog.order_id == order_id, DeliveryConflictLog.status == "active")
            .first()
        )

    if existing:
        record = existing
    else:
        record = DeliveryConflictLog(id=str(uuid.uuid4()), tenant_id=tenant_id)
        db.add(record)

    record.order_id = order_id
    record.delivery_date = delivery_date
    record.product_type = product_type
    record.customer_name = customer_name
    record.conflict_type = conflict_type
    record.days_until_delivery = days_until
    record.risk_level = forecast_data["risk_level"]
    record.confirmed_funerals_that_day = forecast_data["confirmed_funerals"]
    record.predicted_funeral_range = f"{forecast_data['funeral_demand_low']}-{forecast_data['funeral_demand_high']}"
    record.available_driver_estimate = f"{forecast_data['available_low']}-{forecast_data['available_high']}"
    record.status = "active"
    db.commit()

    return {
        "conflict_id": record.id,
        "conflict_type": conflict_type,
        "risk_level": forecast_data["risk_level"],
        "days_until": days_until,
        "confirmed_funerals": forecast_data["confirmed_funerals"],
        "predicted_range": record.predicted_funeral_range,
        "available_drivers": record.available_driver_estimate,
        "block_reason": block["reason"] if block else None,
    }


def get_active_conflicts(db: Session, tenant_id: str) -> list[dict]:
    conflicts = (
        db.query(DeliveryConflictLog)
        .filter(DeliveryConflictLog.tenant_id == tenant_id, DeliveryConflictLog.status == "active")
        .order_by(DeliveryConflictLog.days_until_delivery)
        .all()
    )
    return [
        {
            "id": c.id, "order_id": c.order_id, "delivery_date": str(c.delivery_date),
            "product_type": c.product_type, "customer_name": c.customer_name,
            "conflict_type": c.conflict_type, "days_until": c.days_until_delivery,
            "risk_level": c.risk_level, "confirmed_funerals": c.confirmed_funerals_that_day,
            "predicted_range": c.predicted_funeral_range, "available_drivers": c.available_driver_estimate,
        }
        for c in conflicts
    ]


def resolve_conflict(db: Session, conflict_id: str, resolution: str, user_id: str, note: str | None = None) -> bool:
    c = db.query(DeliveryConflictLog).filter(DeliveryConflictLog.id == conflict_id).first()
    if not c:
        return False
    c.status = resolution  # 'resolved' or 'accepted'
    c.resolved_at = datetime.now(timezone.utc)
    c.resolved_by = user_id
    c.resolution_note = note
    db.commit()
    return True
