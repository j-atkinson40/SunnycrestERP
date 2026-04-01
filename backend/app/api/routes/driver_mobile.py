"""Driver mobile endpoints — today's route, events, media, console."""

from datetime import date, datetime, UTC
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_module
from app.database import get_db
from app.models.delivery import Delivery
from app.models.delivery_route import DeliveryRoute
from app.models.delivery_stop import DeliveryStop
from app.models.user import User
from app.schemas.delivery import EventCreate, EventResponse, MediaResponse, RouteResponse, StopResponse
from app.services import delivery_service, driver_mobile_service

router = APIRouter()

MODULE = "driver_delivery"


class StartRouteRequest(BaseModel):
    pass


class CompleteRouteRequest(BaseModel):
    total_mileage: Decimal | None = None


class UpdateStopStatusRequest(BaseModel):
    status: str
    driver_notes: str | None = None


@router.get("/route/today", response_model=RouteResponse | None)
def get_today_route(
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(get_current_user),
):
    driver = delivery_service.get_driver_by_employee(db, current_user.id, current_user.company_id)
    if not driver:
        raise HTTPException(status_code=404, detail="No driver profile found for this user")
    route = driver_mobile_service.get_today_route(db, driver.id, current_user.company_id)
    if not route:
        return None
    resp = RouteResponse.model_validate(route)
    if route.driver and route.driver.employee:
        resp.driver_name = f"{route.driver.employee.first_name} {route.driver.employee.last_name}"
    if route.vehicle:
        resp.vehicle_name = route.vehicle.name
    return resp


@router.post("/route/today/start", response_model=RouteResponse)
def start_route(
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(get_current_user),
):
    driver = delivery_service.get_driver_by_employee(db, current_user.id, current_user.company_id)
    if not driver:
        raise HTTPException(status_code=404, detail="No driver profile found")
    route = driver_mobile_service.get_today_route(db, driver.id, current_user.company_id)
    if not route:
        raise HTTPException(status_code=404, detail="No route scheduled for today")
    return driver_mobile_service.start_route(db, route)


@router.post("/route/today/complete", response_model=RouteResponse)
def complete_route(
    data: CompleteRouteRequest,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(get_current_user),
):
    driver = delivery_service.get_driver_by_employee(db, current_user.id, current_user.company_id)
    if not driver:
        raise HTTPException(status_code=404, detail="No driver profile found")
    route = driver_mobile_service.get_today_route(db, driver.id, current_user.company_id)
    if not route:
        raise HTTPException(status_code=404, detail="No route scheduled for today")
    return driver_mobile_service.complete_route(
        db, route, total_mileage=float(data.total_mileage) if data.total_mileage else None
    )


@router.patch("/stops/{stop_id}/status", response_model=StopResponse)
def update_stop_status(
    stop_id: str,
    data: UpdateStopStatusRequest,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(get_current_user),
):
    from app.models.delivery_stop import DeliveryStop

    stop = db.query(DeliveryStop).filter(DeliveryStop.id == stop_id).first()
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")
    return delivery_service.update_stop_status(db, stop, data.status, data.driver_notes)


class ExceptionItem(BaseModel):
    item_description: str
    reason: str  # weather, access_issue, family_request, equipment_failure, other
    notes: str | None = None


class ExceptionReport(BaseModel):
    exceptions: list[ExceptionItem]


@router.post("/stops/{stop_id}/exception")
def report_stop_exception(
    stop_id: str,
    data: ExceptionReport,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(get_current_user),
):
    """Report delivery exceptions for a stop. Annotates the SalesOrder for invoice review."""
    from app.models.sales_order import SalesOrder
    from app.models.agent import AgentAlert
    import uuid

    stop = db.query(DeliveryStop).filter(DeliveryStop.id == stop_id).first()
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")

    # Navigate: stop → delivery → sales order
    delivery = db.query(Delivery).filter(Delivery.id == stop.delivery_id).first()
    order_id = None
    if delivery and delivery.order_id:
        order = db.query(SalesOrder).filter(SalesOrder.id == delivery.order_id).first()
        if order:
            order_id = order.id
            order.driver_exceptions = [e.model_dump() for e in data.exceptions]
            order.has_driver_exception = True

            # Create alert for morning review
            customer_name = getattr(order, "ship_to_name", None) or "Customer"
            alert = AgentAlert(
                id=str(uuid.uuid4()),
                tenant_id=current_user.company_id,
                alert_type="driver_exception",
                severity="warning",
                title=f"Delivery exception — {customer_name}",
                message=(
                    f"Driver reported {len(data.exceptions)} exception(s) on delivery "
                    f"to {customer_name}. Review before approving tonight's draft invoice."
                ),
                action_label="Review Invoices",
                action_url="/ar/invoices/review",
            )
            db.add(alert)

    db.commit()
    return {"success": True, "order_id": order_id}


@router.post("/events", response_model=EventResponse)
def post_event(
    data: EventCreate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(get_current_user),
):
    driver = delivery_service.get_driver_by_employee(db, current_user.id, current_user.company_id)
    if not driver:
        raise HTTPException(status_code=404, detail="No driver profile found")
    return driver_mobile_service.post_event(
        db,
        current_user.company_id,
        driver.id,
        data.model_dump(exclude_none=True),
    )


@router.post("/media", response_model=MediaResponse, status_code=201)
async def upload_media(
    delivery_id: str,
    media_type: str,
    file: UploadFile,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(get_current_user),
):
    # In production, upload to S3/GCS. For now, store locally.
    import os
    import uuid

    upload_dir = "/tmp/delivery_media"
    os.makedirs(upload_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or "file")[1] or ".bin"
    file_name = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(upload_dir, file_name)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    return delivery_service.create_media(
        db,
        current_user.company_id,
        delivery_id=delivery_id,
        media_type=media_type,
        file_url=f"/media/{file_name}",
    )


# ---------------------------------------------------------------------------
# Milestone settings for the driver console
# ---------------------------------------------------------------------------


@router.get("/console/milestone-settings")
def get_milestone_settings(
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(get_current_user),
):
    """Get milestone button visibility settings for the driver console."""
    from app.models.company import Company

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if not company:
        return {
            "milestone_on_my_way_enabled": True,
            "milestone_arrived_enabled": True,
            "milestone_delivered_enabled": True,
        }

    return {
        "milestone_on_my_way_enabled": company.get_setting("milestone_on_my_way_enabled", True),
        "milestone_arrived_enabled": company.get_setting("milestone_arrived_enabled", True),
        "milestone_delivered_enabled": company.get_setting("milestone_delivered_enabled", True),
    }


# ---------------------------------------------------------------------------
# Console — rich delivery cards for the driver console view
# ---------------------------------------------------------------------------


def _serialize_console_card(delivery: Delivery, stop: DeliveryStop | None, config: dict | None = None) -> dict:
    """Build a rich card payload for the driver console."""
    tc = delivery.type_config or {}
    config = config or {}

    # Parse service time for display
    service_time_raw = tc.get("service_time", "")
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

    # Hours until service
    hours_until_service = None
    is_critical = False
    is_warning = False
    critical_hours = config.get("critical_window_hours", 4) if config else 4

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

    # Format delivery windows
    window_start = None
    window_end = None
    if delivery.required_window_start:
        window_start = delivery.required_window_start.strftime("%I:%M %p").lstrip("0")
    if delivery.required_window_end:
        window_end = delivery.required_window_end.strftime("%I:%M %p").lstrip("0")

    # Customer name from relationship
    customer_name = None
    if delivery.customer:
        customer_name = delivery.customer.name if hasattr(delivery.customer, "name") else None

    card = {
        "delivery_id": delivery.id,
        "delivery_type": delivery.delivery_type,
        "status": delivery.status,
        "priority": delivery.priority,
        "delivery_address": delivery.delivery_address,
        "delivery_lat": str(delivery.delivery_lat) if delivery.delivery_lat else None,
        "delivery_lng": str(delivery.delivery_lng) if delivery.delivery_lng else None,
        "requested_date": delivery.requested_date.isoformat() if delivery.requested_date else None,
        "required_window_start": window_start,
        "required_window_end": window_end,
        "special_instructions": delivery.special_instructions,
        "customer_name": customer_name,
        "order_id": delivery.order_id,
        "completed_at": delivery.completed_at.isoformat() if delivery.completed_at else None,
        # Funeral-specific fields from type_config
        "family_name": tc.get("family_name", ""),
        "cemetery_name": tc.get("cemetery_name", ""),
        "funeral_home_name": tc.get("funeral_home_name", ""),
        "service_time": service_time_raw,
        "service_time_display": service_time_display,
        "vault_type": tc.get("vault_type", ""),
        "vault_personalization": tc.get("vault_personalization", ""),
        "hours_until_service": hours_until_service,
        "is_critical": is_critical,
        "is_warning": is_warning,
        # Stop info
        "stop_id": stop.id if stop else None,
        "stop_status": stop.status if stop else None,
        "sequence_number": stop.sequence_number if stop else None,
        "actual_arrival": stop.actual_arrival.isoformat() if stop and stop.actual_arrival else None,
        "actual_departure": stop.actual_departure.isoformat() if stop and stop.actual_departure else None,
        "driver_notes": stop.driver_notes if stop else None,
    }

    return card


@router.get("/console/deliveries")
def get_console_deliveries(
    delivery_date: date = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(get_current_user),
):
    """Get all deliveries assigned to the current driver for a given date.

    Returns enriched cards with funeral-specific data, stop status, and
    time urgency calculations for the driver console view.
    """
    driver = delivery_service.get_driver_by_employee(db, current_user.id, current_user.company_id)
    if not driver:
        raise HTTPException(status_code=404, detail="No driver profile found for this user")

    target_date = delivery_date or date.today()

    # Find routes for this driver on this date
    routes = (
        db.query(DeliveryRoute)
        .filter(
            DeliveryRoute.driver_id == driver.id,
            DeliveryRoute.company_id == current_user.company_id,
            DeliveryRoute.route_date == target_date,
            DeliveryRoute.status.notin_(["cancelled"]),
        )
        .all()
    )

    if not routes:
        return {
            "date": target_date.isoformat(),
            "driver_id": driver.id,
            "driver_name": f"{current_user.first_name} {current_user.last_name}",
            "route_id": None,
            "route_status": None,
            "deliveries": [],
            "stats": {"total": 0, "completed": 0, "remaining": 0, "in_progress": 0},
        }

    # Use first active route (typically one per day)
    route = routes[0]

    # Get stops with deliveries eagerly loaded
    stops = (
        db.query(DeliveryStop)
        .filter(DeliveryStop.route_id == route.id)
        .order_by(DeliveryStop.sequence_number)
        .all()
    )

    # Load kanban config if available
    from app.services import extension_service
    kanban_config = None
    try:
        if extension_service.is_extension_enabled(db, current_user.company_id, "funeral_kanban_scheduling"):
            kanban_config = extension_service.get_extension_config(
                db, current_user.company_id, "funeral_kanban_scheduling"
            )
    except Exception:
        pass

    # Build cards
    cards = []
    completed_count = 0
    in_progress_count = 0

    for stop in stops:
        delivery = (
            db.query(Delivery)
            .filter(Delivery.id == stop.delivery_id)
            .first()
        )
        if not delivery:
            continue

        card = _serialize_console_card(delivery, stop, kanban_config)
        cards.append(card)

        if stop.status == "completed" or delivery.status == "completed":
            completed_count += 1
        elif stop.status in ("en_route", "arrived") or delivery.status in ("in_transit", "arrived", "setup"):
            in_progress_count += 1

    total = len(cards)

    # Fetch ancillary items assigned to this driver for this date (exclude floating)
    ancillary_items = (
        db.query(Delivery)
        .filter(
            Delivery.company_id == current_user.company_id,
            Delivery.scheduling_type == "ancillary",
            Delivery.assigned_driver_id == driver.id,
            Delivery.requested_date == target_date,
            or_(Delivery.ancillary_is_floating.is_(False), Delivery.ancillary_is_floating.is_(None)),
            Delivery.status != "cancelled",
        )
        .order_by(Delivery.created_at)
        .all()
    )

    ancillary_cards = []
    for ad in ancillary_items:
        tc = ad.type_config or {}
        ancillary_cards.append({
            "delivery_id": ad.id,
            "delivery_type": ad.delivery_type,
            "order_type_label": {
                "funeral_home_dropoff": "Drop-off",
                "funeral_home_pickup": "Pickup",
                "supply_delivery": "Supply",
            }.get(ad.delivery_type, ad.delivery_type),
            "funeral_home_name": tc.get("funeral_home_name", ""),
            "product_summary": tc.get("product_summary", tc.get("vault_type", "")),
            "deceased_name": tc.get("family_name", tc.get("deceased_name", "")),
            "ancillary_fulfillment_status": ad.ancillary_fulfillment_status or "unassigned",
            "special_instructions": ad.special_instructions,
        })

    return {
        "date": target_date.isoformat(),
        "driver_id": driver.id,
        "driver_name": f"{current_user.first_name} {current_user.last_name}",
        "route_id": route.id,
        "route_status": route.status,
        "deliveries": cards,
        "ancillary_items": ancillary_cards,
        "stats": {
            "total": total,
            "completed": completed_count,
            "remaining": total - completed_count,
            "in_progress": in_progress_count,
        },
    }


@router.patch("/console/deliveries/{delivery_id}/status")
def update_console_delivery_status(
    delivery_id: str,
    data: UpdateStopStatusRequest,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(get_current_user),
):
    """Update a delivery's status from the driver console.

    Handles the full lifecycle: en_route → arrived → completed.
    Also updates the parent Delivery status to keep Kanban boards in sync.
    """
    driver = delivery_service.get_driver_by_employee(db, current_user.id, current_user.company_id)
    if not driver:
        raise HTTPException(status_code=404, detail="No driver profile found")

    # Find the delivery
    delivery = db.query(Delivery).filter(
        Delivery.id == delivery_id,
        Delivery.company_id == current_user.company_id,
    ).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    # Find the stop for this delivery in a current route
    stop = (
        db.query(DeliveryStop)
        .join(DeliveryRoute, DeliveryRoute.id == DeliveryStop.route_id)
        .filter(
            DeliveryStop.delivery_id == delivery_id,
            DeliveryRoute.driver_id == driver.id,
            DeliveryRoute.status.notin_(["cancelled", "completed"]),
        )
        .first()
    )
    if not stop:
        raise HTTPException(status_code=404, detail="No active stop found for this delivery")

    now = datetime.now(UTC)
    new_status = data.status

    # Update stop
    stop.status = new_status
    if data.driver_notes is not None:
        stop.driver_notes = data.driver_notes
    if new_status == "en_route":
        pass  # No timestamp needed
    elif new_status == "arrived" and not stop.actual_arrival:
        stop.actual_arrival = now
    elif new_status == "completed" and not stop.actual_departure:
        stop.actual_departure = now

    # Map stop status to delivery status
    delivery_status_map = {
        "en_route": "in_transit",
        "arrived": "arrived",
        "completed": "completed",
    }
    new_delivery_status = delivery_status_map.get(new_status)
    if new_delivery_status:
        delivery.status = new_delivery_status
        if new_delivery_status == "completed":
            delivery.completed_at = now

    delivery.modified_at = now
    db.commit()

    # Post a delivery event for tracking
    try:
        event_type_map = {
            "en_route": "departed",
            "arrived": "arrived",
            "completed": "completed",
        }
        event_type = event_type_map.get(new_status)
        if event_type:
            driver_mobile_service.post_event(
                db,
                current_user.company_id,
                driver.id,
                {
                    "delivery_id": delivery_id,
                    "event_type": event_type,
                    "source": "driver",
                    "notes": data.driver_notes,
                },
            )
    except Exception:
        pass  # Don't fail the status update if event posting fails

    return {
        "delivery_id": delivery_id,
        "status": new_status,
        "delivery_status": delivery.status,
        "completed_at": delivery.completed_at.isoformat() if delivery.completed_at else None,
    }


@router.post("/console/ancillary/{delivery_id}/confirm")
def confirm_ancillary_delivery(
    delivery_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(get_current_user),
):
    """Driver confirms an ancillary delivery (drop-off/supply) from the console."""
    driver = delivery_service.get_driver_by_employee(db, current_user.id, current_user.company_id)
    if not driver:
        raise HTTPException(status_code=404, detail="No driver profile found")

    delivery = db.query(Delivery).filter(
        Delivery.id == delivery_id,
        Delivery.company_id == current_user.company_id,
        Delivery.scheduling_type == "ancillary",
        Delivery.assigned_driver_id == driver.id,
    ).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Ancillary delivery not found or not assigned to you")

    now = datetime.now(UTC)
    delivery.ancillary_fulfillment_status = "completed"
    delivery.status = "completed"
    delivery.completed_at = now
    delivery.modified_at = now
    db.commit()

    return {"status": "completed", "delivery_id": delivery_id}
