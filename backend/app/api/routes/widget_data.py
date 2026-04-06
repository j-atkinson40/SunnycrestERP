"""Widget data summary endpoints — lightweight endpoints used by dashboard widgets.

These return pre-aggregated data suitable for widget display. Each is designed
to be fast and independent so one widget failing doesn't affect others.
"""

from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, case, and_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User

router = APIRouter()


@router.get("/orders/today")
def orders_today(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Today's orders for the TodaysServicesWidget."""
    from app.models.sales_order import SalesOrder

    today = date.today()
    orders = (
        db.query(SalesOrder)
        .filter(
            SalesOrder.company_id == current_user.company_id,
            SalesOrder.is_active == True,
            func.date(SalesOrder.service_date) == today,
        )
        .order_by(SalesOrder.service_date)
        .all()
    )

    return {
        "date": today.isoformat(),
        "count": len(orders),
        "orders": [
            {
                "id": o.id,
                "order_number": getattr(o, "order_number", None),
                "customer_name": getattr(o, "customer_name", None) or getattr(o, "bill_to_name", "Unknown"),
                "cemetery_name": getattr(o, "cemetery_name", None) or getattr(o, "ship_to_name", None),
                "service_time": o.service_date.isoformat() if o.service_date else None,
                "status": getattr(o, "status", "pending"),
            }
            for o in orders
        ],
    }


@router.get("/orders/pending-summary")
def orders_pending_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pending order counts for the OpenOrdersWidget."""
    from app.models.sales_order import SalesOrder

    orders = (
        db.query(SalesOrder.status, func.count(SalesOrder.id))
        .filter(
            SalesOrder.company_id == current_user.company_id,
            SalesOrder.is_active == True,
            SalesOrder.status.in_(["pending", "scheduled", "in_production", "confirmed", "draft"]),
        )
        .group_by(SalesOrder.status)
        .all()
    )

    counts = {status: count for status, count in orders}
    return {
        "unscheduled": counts.get("pending", 0) + counts.get("draft", 0),
        "scheduled": counts.get("scheduled", 0) + counts.get("confirmed", 0),
        "in_production": counts.get("in_production", 0),
        "total": sum(counts.values()),
    }


@router.get("/drivers/status-summary")
def drivers_status_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Driver status for the DriverStatusWidget."""
    from app.models.driver import Driver

    drivers = (
        db.query(Driver)
        .filter(
            Driver.company_id == current_user.company_id,
            Driver.is_active == True,
        )
        .all()
    )

    return {
        "count": len(drivers),
        "drivers": [
            {
                "id": d.id,
                "name": getattr(d, "name", None) or f"{getattr(d, 'first_name', '')} {getattr(d, 'last_name', '')}".strip(),
                "status": getattr(d, "current_status", "available"),
                "current_stop": getattr(d, "current_stop", None),
                "next_stop": getattr(d, "next_stop", None),
                "phone": getattr(d, "phone", None),
            }
            for d in drivers
        ],
    }


@router.get("/production/daily-summary")
def production_daily_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Production summary for the ProductionStatusWidget."""
    from app.models.production_log import ProductionLogEntry

    today = date.today()
    entries = (
        db.query(ProductionLogEntry)
        .filter(
            ProductionLogEntry.company_id == current_user.company_id,
            func.date(ProductionLogEntry.created_at) == today,
        )
        .all()
    )

    total_units = sum(getattr(e, "quantity", 0) or 0 for e in entries)

    # Group by product
    by_product: dict[str, int] = {}
    for e in entries:
        name = getattr(e, "product_name", None) or getattr(e, "product_name_raw", "Unknown")
        by_product[name] = by_product.get(name, 0) + (getattr(e, "quantity", 0) or 0)

    return {
        "date": today.isoformat(),
        "total_units": total_units,
        "target": None,  # Target not yet configured in settings
        "by_product": [
            {"product": name, "units": count}
            for name, count in sorted(by_product.items(), key=lambda x: -x[1])
        ],
    }


@router.get("/inventory/key-items")
def inventory_key_items(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Key inventory levels for the InventoryWidget."""
    from app.models.inventory import InventoryItem

    items = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.company_id == current_user.company_id,
            InventoryItem.is_active == True,
        )
        .order_by(InventoryItem.quantity_on_hand.asc())
        .limit(limit)
        .all()
    )

    return {
        "items": [
            {
                "id": i.id,
                "product_name": getattr(i, "product_name", None) or getattr(i, "name", "Unknown"),
                "product_id": getattr(i, "product_id", None),
                "quantity": getattr(i, "quantity_on_hand", 0) or 0,
                "min_level": getattr(i, "reorder_point", None) or getattr(i, "minimum_quantity", 0),
                "status": _inventory_status(
                    getattr(i, "quantity_on_hand", 0) or 0,
                    getattr(i, "reorder_point", None) or getattr(i, "minimum_quantity", 0) or 0,
                ),
            }
            for i in items
        ],
    }


@router.get("/legacy-studio/queue-summary")
def legacy_queue_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Legacy proof queue for the LegacyQueueWidget."""
    from app.models.legacy_proof import LegacyProof

    proofs = (
        db.query(LegacyProof)
        .filter(
            LegacyProof.company_id == current_user.company_id,
            LegacyProof.is_active == True,
        )
        .order_by(LegacyProof.created_at.desc())
        .limit(20)
        .all()
    )

    pending = [p for p in proofs if getattr(p, "status", "") in ("pending", "draft", "needs_review")]
    approved_today = [
        p for p in proofs
        if getattr(p, "status", "") == "approved"
        and getattr(p, "updated_at", None)
        and getattr(p, "updated_at").date() == date.today()
    ]

    return {
        "pending_count": len(pending),
        "approved_today_count": len(approved_today),
        "pending": [
            {
                "id": p.id,
                "customer_name": getattr(p, "customer_name", None) or getattr(p, "funeral_home_name", "Unknown"),
                "print_name": getattr(p, "deceased_name", None) or getattr(p, "print_name", None),
                "service_date": getattr(p, "service_date", None).isoformat() if getattr(p, "service_date", None) else None,
                "status": getattr(p, "status", "pending"),
            }
            for p in pending[:10]
        ],
    }


@router.get("/briefing/today")
def briefing_today(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Today's briefing summary for the BriefingSummaryWidget."""
    from app.models.employee_briefing import EmployeeBriefing

    today = date.today()
    briefing = (
        db.query(EmployeeBriefing)
        .filter(
            EmployeeBriefing.company_id == current_user.company_id,
            func.date(EmployeeBriefing.created_at) == today,
        )
        .order_by(EmployeeBriefing.created_at.desc())
        .first()
    )

    if not briefing:
        return {"available": False, "narrative": None, "action_items": 0}

    return {
        "available": True,
        "narrative": getattr(briefing, "narrative", None) or getattr(briefing, "summary", None),
        "action_items": getattr(briefing, "action_item_count", 0) or 0,
        "created_at": briefing.created_at.isoformat() if briefing.created_at else None,
    }


@router.get("/safety/dashboard-summary")
def safety_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Safety dashboard for the SafetyWidget."""
    from app.models.safety import SafetyIncident, SafetyInspection

    open_incidents = (
        db.query(func.count(SafetyIncident.id))
        .filter(
            SafetyIncident.company_id == current_user.company_id,
            SafetyIncident.status.in_(["open", "investigating"]),
        )
        .scalar()
    ) or 0

    overdue_inspections = (
        db.query(func.count(SafetyInspection.id))
        .filter(
            SafetyInspection.company_id == current_user.company_id,
            SafetyInspection.status == "overdue",
        )
        .scalar()
    ) or 0

    return {
        "open_incidents": open_incidents,
        "overdue_inspections": overdue_inspections,
        "training_overdue": 0,  # TODO: query training requirements
    }


@router.get("/qc/daily-summary")
def qc_daily_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """QC summary for the QCStatusWidget."""
    from app.models.qc import QCInspection

    today = date.today()
    inspections = (
        db.query(QCInspection)
        .filter(
            QCInspection.company_id == current_user.company_id,
            func.date(QCInspection.created_at) == today,
        )
        .all()
    )

    completed = [i for i in inspections if getattr(i, "status", "") in ("completed", "passed")]
    failed = [i for i in inspections if getattr(i, "status", "") == "failed"]

    return {
        "total": len(inspections),
        "completed": len(completed),
        "failed": len(failed),
        "pass_rate": round(len(completed) / len(inspections) * 100) if inspections else 0,
    }


@router.get("/activity/recent")
def activity_recent(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Recent activity for the ActivityFeedWidget."""
    from app.models.activity_log import ActivityLog

    logs = (
        db.query(ActivityLog)
        .filter(ActivityLog.company_id == current_user.company_id)
        .order_by(ActivityLog.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "events": [
            {
                "id": log.id,
                "action": getattr(log, "action", None),
                "description": getattr(log, "description", None) or getattr(log, "message", None),
                "entity_type": getattr(log, "entity_type", None),
                "entity_id": getattr(log, "entity_id", None),
                "user_name": getattr(log, "user_name", None),
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
    }


@router.get("/crm/at-risk-summary")
def at_risk_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """At-risk accounts for the AtRiskAccountsWidget."""
    # Use financial health scores if available, else simple overdue check
    from app.models.company_entity import CompanyEntity

    # Return basic list — full implementation uses financial health service
    at_risk = (
        db.query(CompanyEntity)
        .filter(
            CompanyEntity.tenant_id == current_user.company_id,
            CompanyEntity.is_active == True,
            CompanyEntity.customer_type.in_(["funeral_home", "cemetery"]),
        )
        .limit(5)
        .all()
    )

    return {
        "count": 0,  # placeholder until financial health scores implemented
        "accounts": [],
    }


def _inventory_status(qty: int, min_level: int) -> str:
    if qty <= 0:
        return "out"
    if min_level > 0 and qty <= min_level:
        return "low"
    return "ok"
