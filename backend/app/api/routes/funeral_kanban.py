"""Funeral Kanban Scheduling — extension API endpoints."""

from datetime import date, datetime, UTC
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_module
from app.database import get_db
from app.models.delivery import Delivery
from app.models.delivery_route import DeliveryRoute
from app.models.delivery_stop import DeliveryStop
from app.models.driver import Driver
from app.models.user import User
from app.services import extension_service

router = APIRouter(
    dependencies=[Depends(require_module("driver_delivery"))],
)


def _require_funeral_kanban(db: Session, tenant_id: str) -> dict:
    """Check extension is enabled and return its config."""
    if not extension_service.is_extension_enabled(db, tenant_id, "funeral_kanban_scheduling"):
        raise HTTPException(status_code=403, detail="Funeral Kanban Scheduling extension is not enabled")
    return extension_service.get_extension_config(db, tenant_id, "funeral_kanban_scheduling")


def _serialize_delivery_card(delivery: Delivery, config: dict, sequence: int | None = None) -> dict:
    """Convert a delivery to a Kanban card."""
    tc = delivery.type_config or {}
    service_time_raw = tc.get("service_time", "")

    # Parse service time for display
    service_time_display = service_time_raw
    if service_time_raw and ":" in service_time_raw:
        try:
            parts = service_time_raw.split(":")
            hour = int(parts[0])
            minute = parts[1] if len(parts) > 1 else "00"
            ampm = "AM" if hour < 12 else "PM"
            display_hour = hour if hour <= 12 else hour - 12
            if display_hour == 0:
                display_hour = 12
            service_time_display = f"{display_hour}:{minute} {ampm}"
        except (ValueError, IndexError):
            pass

    # Calculate hours until service
    hours_until_service = None
    is_critical = False
    is_warning = False
    critical_hours = config.get("critical_window_hours", 4)

    if service_time_raw and delivery.requested_date:
        try:
            parts = service_time_raw.split(":")
            service_dt = datetime(
                delivery.requested_date.year,
                delivery.requested_date.month,
                delivery.requested_date.day,
                int(parts[0]),
                int(parts[1]) if len(parts) > 1 else 0,
                tzinfo=UTC,
            )
            now = datetime.now(UTC)
            delta = (service_dt - now).total_seconds() / 3600
            hours_until_service = round(delta, 1)
            is_critical = delta < critical_hours
            is_warning = not is_critical and delta < critical_hours * 2
        except (ValueError, IndexError):
            pass

    # Format delivery window
    window_start = None
    window_end = None
    if delivery.required_window_start:
        window_start = delivery.required_window_start.strftime("%I:%M %p").lstrip("0")
    if delivery.required_window_end:
        window_end = delivery.required_window_end.strftime("%I:%M %p").lstrip("0")

    card = {
        "delivery_id": delivery.id,
        "family_name": tc.get("family_name", ""),
        "cemetery_name": tc.get("cemetery_name", ""),
        "funeral_home_name": tc.get("funeral_home_name", ""),
        "service_time": service_time_raw,
        "service_time_display": service_time_display,
        "vault_type": tc.get("vault_type", ""),
        "vault_personalization": tc.get("vault_personalization", ""),
        "requested_date": delivery.requested_date.isoformat() if delivery.requested_date else None,
        "required_window_start": window_start,
        "required_window_end": window_end,
        "hours_until_service": hours_until_service,
        "is_critical": is_critical,
        "is_warning": is_warning,
        "order_id": delivery.order_id,
        "notes": delivery.special_instructions,
        "status": delivery.status,
        "delivery_address": delivery.delivery_address,
    }

    if sequence is not None:
        card["scheduled_sequence"] = sequence

    return card


class AssignRequest(BaseModel):
    delivery_id: str
    driver_id: str | None = None
    date: date
    sequence: int | None = None


@router.get("/schedule")
def get_schedule(
    schedule_date: date = Query(..., alias="date"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the funeral vault Kanban schedule for a specific date."""
    config = _require_funeral_kanban(db, current_user.company_id)

    # Get all funeral_vault deliveries for this date that are unscheduled
    unscheduled_deliveries = (
        db.query(Delivery)
        .filter(
            Delivery.company_id == current_user.company_id,
            Delivery.delivery_type == "funeral_vault",
            Delivery.requested_date == schedule_date,
            Delivery.status.in_(["pending"]),
        )
        .order_by(Delivery.required_window_start, Delivery.created_at)
        .all()
    )

    # Filter to only truly unscheduled (no active stop assignment)
    # A delivery is unscheduled if it has no stop in any non-cancelled route for this date
    scheduled_delivery_ids = set()
    routes_for_date = (
        db.query(DeliveryRoute)
        .filter(
            DeliveryRoute.company_id == current_user.company_id,
            DeliveryRoute.route_date == schedule_date,
            DeliveryRoute.status.notin_(["cancelled"]),
        )
        .all()
    )
    route_ids = [r.id for r in routes_for_date]

    if route_ids:
        stops = (
            db.query(DeliveryStop)
            .filter(DeliveryStop.route_id.in_(route_ids))
            .all()
        )
        scheduled_delivery_ids = {s.delivery_id for s in stops}

    truly_unscheduled = [
        d for d in unscheduled_deliveries if d.id not in scheduled_delivery_ids
    ]

    # Also check for scheduled funeral_vault deliveries that aren't in the pending query
    # (status might have been updated to "scheduled")
    additional_scheduled = (
        db.query(Delivery)
        .filter(
            Delivery.company_id == current_user.company_id,
            Delivery.delivery_type == "funeral_vault",
            Delivery.requested_date == schedule_date,
            Delivery.id.in_(scheduled_delivery_ids) if scheduled_delivery_ids else False,
        )
        .all()
    ) if scheduled_delivery_ids else []

    all_scheduled_map = {d.id: d for d in additional_scheduled}
    # Also include from original query those that ARE scheduled
    for d in unscheduled_deliveries:
        if d.id in scheduled_delivery_ids:
            all_scheduled_map[d.id] = d

    # Get all active drivers
    drivers = (
        db.query(Driver)
        .filter(
            Driver.company_id == current_user.company_id,
            Driver.active.is_(True),
        )
        .all()
    )

    # Build driver lanes
    driver_lanes = []
    # Map: driver_id -> list of (stop, delivery)
    driver_deliveries: dict[str, list[tuple]] = {d.id: [] for d in drivers}

    for route in routes_for_date:
        if route.driver_id not in driver_deliveries:
            continue
        route_stops = (
            db.query(DeliveryStop)
            .filter(DeliveryStop.route_id == route.id)
            .order_by(DeliveryStop.sequence_number)
            .all()
        )
        for stop in route_stops:
            # Only include funeral_vault deliveries
            delivery = all_scheduled_map.get(stop.delivery_id)
            if not delivery:
                # Fetch it
                delivery = db.query(Delivery).filter(
                    Delivery.id == stop.delivery_id,
                    Delivery.delivery_type == "funeral_vault",
                ).first()
            if delivery and delivery.delivery_type == "funeral_vault":
                driver_deliveries[route.driver_id].append(
                    (stop, delivery)
                )

    # Get driver names via employee relationship
    for driver in drivers:
        items = driver_deliveries.get(driver.id, [])
        cards = []
        for stop, delivery in items:
            cards.append(_serialize_delivery_card(delivery, config, sequence=stop.sequence_number))

        # Get driver display name from employee
        driver_name = f"Driver {driver.id[:8]}"
        if driver.employee:
            driver_name = f"{driver.employee.first_name} {driver.employee.last_name}"

        driver_lanes.append({
            "driver_id": driver.id,
            "name": driver_name,
            "deliveries": cards,
            "delivery_count": len(cards),
        })

    # Sort: drivers with deliveries first, then alphabetical
    driver_lanes.sort(key=lambda d: (-d["delivery_count"], d["name"]))

    return {
        "date": schedule_date.isoformat(),
        "config": config,
        "unscheduled": [_serialize_delivery_card(d, config) for d in truly_unscheduled],
        "drivers": driver_lanes,
    }


@router.post("/assign")
def assign_delivery(
    data: AssignRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Assign or unassign a funeral vault delivery to/from a driver."""
    _require_funeral_kanban(db, current_user.company_id)

    delivery = db.query(Delivery).filter(
        Delivery.id == data.delivery_id,
        Delivery.company_id == current_user.company_id,
    ).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    # Remove from any existing route on this date
    existing_routes = (
        db.query(DeliveryRoute)
        .filter(
            DeliveryRoute.company_id == current_user.company_id,
            DeliveryRoute.route_date == data.date,
            DeliveryRoute.status.notin_(["cancelled"]),
        )
        .all()
    )
    for route in existing_routes:
        stop = (
            db.query(DeliveryStop)
            .filter(
                DeliveryStop.route_id == route.id,
                DeliveryStop.delivery_id == data.delivery_id,
            )
            .first()
        )
        if stop:
            db.delete(stop)
            # Resequence remaining stops
            remaining = (
                db.query(DeliveryStop)
                .filter(
                    DeliveryStop.route_id == route.id,
                    DeliveryStop.id != stop.id,
                )
                .order_by(DeliveryStop.sequence_number)
                .all()
            )
            for i, s in enumerate(remaining):
                s.sequence_number = i + 1
            # Update route total_stops
            route.total_stops = len(remaining)

    if data.driver_id is None:
        # Unassign — set back to pending
        delivery.status = "pending"
        delivery.scheduled_at = None
        db.commit()
        return {"status": "unassigned", "delivery_id": data.delivery_id}

    # Find or create a route for this driver on this date
    route = (
        db.query(DeliveryRoute)
        .filter(
            DeliveryRoute.company_id == current_user.company_id,
            DeliveryRoute.driver_id == data.driver_id,
            DeliveryRoute.route_date == data.date,
            DeliveryRoute.status.notin_(["cancelled", "completed"]),
        )
        .first()
    )

    if not route:
        route = DeliveryRoute(
            company_id=current_user.company_id,
            driver_id=data.driver_id,
            route_date=data.date,
            status="draft",
            total_stops=0,
            created_by=current_user.id,
        )
        db.add(route)
        db.flush()

    # Determine sequence
    if data.sequence is not None:
        target_seq = data.sequence
    else:
        max_seq = (
            db.query(DeliveryStop.sequence_number)
            .filter(DeliveryStop.route_id == route.id)
            .order_by(DeliveryStop.sequence_number.desc())
            .first()
        )
        target_seq = (max_seq[0] + 1) if max_seq else 1

    # Shift existing stops if needed
    if data.sequence is not None:
        existing_stops = (
            db.query(DeliveryStop)
            .filter(
                DeliveryStop.route_id == route.id,
                DeliveryStop.sequence_number >= target_seq,
            )
            .order_by(DeliveryStop.sequence_number.desc())
            .all()
        )
        for s in existing_stops:
            s.sequence_number += 1

    # Create the stop
    new_stop = DeliveryStop(
        route_id=route.id,
        delivery_id=data.delivery_id,
        sequence_number=target_seq,
        status="pending",
    )
    db.add(new_stop)

    # Update delivery status
    delivery.status = "scheduled"
    delivery.scheduled_at = datetime.now(UTC)

    # Update route total
    total = db.query(DeliveryStop).filter(DeliveryStop.route_id == route.id).count()
    route.total_stops = total + 1  # +1 for the new one not yet flushed

    db.commit()

    return {
        "status": "assigned",
        "delivery_id": data.delivery_id,
        "driver_id": data.driver_id,
        "route_id": route.id,
        "sequence": target_seq,
    }


@router.get("/config")
def get_kanban_config(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the funeral kanban extension config for the current tenant."""
    config = _require_funeral_kanban(db, current_user.company_id)
    return config
