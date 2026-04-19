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
            SalesOrder.scheduled_date == today,
        )
        .order_by(SalesOrder.scheduled_date)
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
                "service_time": o.scheduled_date.isoformat() if o.scheduled_date else None,
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
            CompanyEntity.company_id == current_user.company_id,
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


# ---------------------------------------------------------------------------
# Team Dashboard Endpoints
# ---------------------------------------------------------------------------


@router.get("/team/roster")
def team_roster(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Team roster — who's on the team, grouped by department/track."""
    from app.models.employee_profile import EmployeeProfile
    from app.models.department import Department
    from app.models.driver import Driver

    users = (
        db.query(User)
        .outerjoin(EmployeeProfile, EmployeeProfile.user_id == User.id)
        .outerjoin(Department, Department.id == EmployeeProfile.department_id)
        .filter(
            User.company_id == current_user.company_id,
            User.is_active == True,
        )
        .all()
    )

    # Get driver IDs so we can tag drivers
    driver_user_ids = set(
        row[0]
        for row in db.query(Driver.employee_id)
        .filter(Driver.company_id == current_user.company_id, Driver.active == True)
        .all()
    )

    roster = []
    for u in users:
        profile = u.profile
        dept = profile.department_obj if profile and profile.department_id else None
        roster.append({
            "id": u.id,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "email": u.email,
            "track": u.track,
            "is_driver": u.id in driver_user_ids,
            "position": profile.position if profile else None,
            "department": dept.name if dept else None,
            "department_id": dept.id if dept else None,
            "hire_date": profile.hire_date.isoformat() if profile and profile.hire_date else None,
            "phone": profile.phone if profile else None,
        })

    # Group counts
    by_track = {}
    by_dept: dict[str, int] = {}
    for r in roster:
        by_track[r["track"]] = by_track.get(r["track"], 0) + 1
        d = r["department"] or "Unassigned"
        by_dept[d] = by_dept.get(d, 0) + 1

    return {
        "total": len(roster),
        "by_track": by_track,
        "by_department": by_dept,
        "employees": roster,
    }


@router.get("/team/training-status")
def team_training_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Training completion and upcoming expirations."""
    from app.models.safety_training import (
        EmployeeTrainingRecord,
        SafetyTrainingEvent,
        SafetyTrainingRequirement,
    )

    today = date.today()

    # All active requirements
    requirements = (
        db.query(SafetyTrainingRequirement)
        .filter(SafetyTrainingRequirement.company_id == current_user.company_id)
        .all()
    )

    # All training records for active employees
    records = (
        db.query(EmployeeTrainingRecord)
        .join(User, User.id == EmployeeTrainingRecord.employee_id)
        .filter(
            EmployeeTrainingRecord.company_id == current_user.company_id,
            User.is_active == True,
        )
        .all()
    )

    # Active employee count
    active_count = (
        db.query(func.count(User.id))
        .filter(User.company_id == current_user.company_id, User.is_active == True)
        .scalar()
    ) or 0

    # Records expiring within 30 days
    expiring_soon = []
    expired = []
    for r in records:
        if r.expiry_date:
            exp = r.expiry_date if isinstance(r.expiry_date, date) else r.expiry_date.date() if hasattr(r.expiry_date, "date") else r.expiry_date
            if exp < today:
                expired.append(r)
            elif (exp - today).days <= 30:
                expiring_soon.append(r)

    # Build per-employee summary
    employee_records: dict[str, list] = {}
    for r in records:
        employee_records.setdefault(r.employee_id, []).append(r)

    completed_count = len([
        r for r in records
        if r.completion_status in ("completed", "passed")
    ])

    return {
        "total_requirements": len(requirements),
        "total_employees": active_count,
        "total_records": len(records),
        "completed": completed_count,
        "expired": len(expired),
        "expiring_soon": len(expiring_soon),
        "completion_rate": round(completed_count / len(records) * 100) if records else 0,
        "expiring_items": [
            {
                "employee_id": r.employee_id,
                "training_event_id": r.training_event_id,
                "expiry_date": r.expiry_date.isoformat() if r.expiry_date else None,
                "completion_status": r.completion_status,
            }
            for r in expiring_soon[:10]
        ],
        "expired_items": [
            {
                "employee_id": r.employee_id,
                "training_event_id": r.training_event_id,
                "expiry_date": r.expiry_date.isoformat() if r.expiry_date else None,
                "completion_status": r.completion_status,
            }
            for r in expired[:10]
        ],
    }


@router.get("/team/safety-certs-due")
def team_safety_certs_due(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Safety certifications expiring within 60 days."""
    from app.models.safety_training import EmployeeTrainingRecord

    today = date.today()
    from datetime import timedelta

    horizon = today + timedelta(days=60)

    records = (
        db.query(EmployeeTrainingRecord)
        .join(User, User.id == EmployeeTrainingRecord.employee_id)
        .filter(
            EmployeeTrainingRecord.company_id == current_user.company_id,
            User.is_active == True,
            EmployeeTrainingRecord.expiry_date != None,
            EmployeeTrainingRecord.expiry_date <= horizon,
        )
        .order_by(EmployeeTrainingRecord.expiry_date.asc())
        .limit(20)
        .all()
    )

    # Enrich with employee names
    employee_ids = list(set(r.employee_id for r in records))
    employees = {
        u.id: u
        for u in db.query(User).filter(User.id.in_(employee_ids)).all()
    } if employee_ids else {}

    items = []
    for r in records:
        emp = employees.get(r.employee_id)
        exp = r.expiry_date
        is_expired = exp < today if exp else False
        items.append({
            "id": r.id,
            "employee_id": r.employee_id,
            "employee_name": f"{emp.first_name} {emp.last_name}" if emp else "Unknown",
            "training_event_id": r.training_event_id,
            "expiry_date": exp.isoformat() if exp else None,
            "days_remaining": (exp - today).days if exp and not is_expired else 0,
            "is_expired": is_expired,
            "completion_status": r.completion_status,
        })

    return {
        "total": len(items),
        "expired_count": sum(1 for i in items if i["is_expired"]),
        "items": items,
    }


@router.get("/team/driver-performance")
def team_driver_performance(
    days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Driver delivery performance metrics over the last N days."""
    from app.models.driver import Driver
    from app.models.delivery import Delivery
    from app.models.delivery_route import DeliveryRoute
    from datetime import timedelta

    today = date.today()
    start_date = today - timedelta(days=days)

    drivers = (
        db.query(Driver)
        .join(User, User.id == Driver.employee_id)
        .filter(
            Driver.company_id == current_user.company_id,
            Driver.active == True,
            User.is_active == True,
        )
        .all()
    )

    driver_ids = [d.id for d in drivers]
    driver_employee_map = {d.id: d.employee_id for d in drivers}

    # Get completed routes in date range
    routes = (
        db.query(DeliveryRoute)
        .filter(
            DeliveryRoute.company_id == current_user.company_id,
            DeliveryRoute.driver_id.in_(driver_ids) if driver_ids else False,
            DeliveryRoute.route_date >= start_date,
        )
        .all()
    ) if driver_ids else []

    # Aggregate per driver
    driver_stats: dict[str, dict] = {d.id: {
        "routes_total": 0,
        "routes_completed": 0,
        "total_stops": 0,
        "total_mileage": 0.0,
    } for d in drivers}

    for r in routes:
        stats = driver_stats.get(r.driver_id)
        if not stats:
            continue
        stats["routes_total"] += 1
        if r.status == "completed":
            stats["routes_completed"] += 1
        stats["total_stops"] += r.total_stops or 0
        stats["total_mileage"] += float(r.total_mileage or 0)

    # Get employee names
    emp_ids = list(set(driver_employee_map.values()))
    employees = {
        u.id: u
        for u in db.query(User).filter(User.id.in_(emp_ids)).all()
    } if emp_ids else {}

    result = []
    for d in drivers:
        emp = employees.get(d.employee_id)
        stats = driver_stats[d.id]
        completion_rate = (
            round(stats["routes_completed"] / stats["routes_total"] * 100)
            if stats["routes_total"] > 0
            else 0
        )
        result.append({
            "driver_id": d.id,
            "employee_id": d.employee_id,
            "name": f"{emp.first_name} {emp.last_name}" if emp else "Unknown",
            "license_expiry": d.license_expiry.isoformat() if d.license_expiry else None,
            "routes_total": stats["routes_total"],
            "routes_completed": stats["routes_completed"],
            "completion_rate": completion_rate,
            "total_stops": stats["total_stops"],
            "total_mileage": round(stats["total_mileage"], 1),
        })

    # Sort by completion rate desc, then total routes desc
    result.sort(key=lambda x: (-x["completion_rate"], -x["routes_total"]))

    return {
        "period_days": days,
        "total_drivers": len(result),
        "drivers": result,
    }


@router.get("/team/announcements")
def team_announcements(
    limit: int = Query(10, ge=1, le=30),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Recent company-wide announcements and notifications."""
    from app.models.notification import Notification

    # Get recent notifications for this user, prioritizing unread
    notifications = (
        db.query(Notification)
        .filter(
            Notification.company_id == current_user.company_id,
            Notification.user_id == current_user.id,
        )
        .order_by(Notification.is_read.asc(), Notification.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "total": len(notifications),
        "unread": sum(1 for n in notifications if not n.is_read),
        "items": [
            {
                "id": n.id,
                "title": n.title,
                "message": n.message,
                "type": n.type,
                "category": n.category,
                "link": n.link,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in notifications
        ],
    }
