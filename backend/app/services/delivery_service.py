"""Core CRUD service for the delivery module — vehicles, drivers, carriers,
deliveries, routes, stops, events, and media."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.carrier import Carrier
from app.models.delivery import Delivery
from app.models.delivery_event import DeliveryEvent
from app.models.delivery_media import DeliveryMedia
from app.models.delivery_route import DeliveryRoute
from app.models.delivery_stop import DeliveryStop
from app.models.driver import Driver
from app.models.vehicle import Vehicle


# ---------------------------------------------------------------------------
# Vehicles
# ---------------------------------------------------------------------------


def list_vehicles(
    db: Session,
    company_id: str,
    *,
    active_only: bool = True,
    page: int = 1,
    per_page: int = 50,
) -> tuple[list[Vehicle], int]:
    q = db.query(Vehicle).filter(Vehicle.company_id == company_id)
    if active_only:
        q = q.filter(Vehicle.active.is_(True))
    total = q.count()
    items = q.order_by(Vehicle.name).offset((page - 1) * per_page).limit(per_page).all()
    return items, total


def get_vehicle(db: Session, vehicle_id: str, company_id: str) -> Vehicle | None:
    return (
        db.query(Vehicle)
        .filter(Vehicle.id == vehicle_id, Vehicle.company_id == company_id)
        .first()
    )


def create_vehicle(db: Session, company_id: str, data: dict) -> Vehicle:
    vehicle = Vehicle(id=str(uuid.uuid4()), company_id=company_id, **data)
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


def update_vehicle(db: Session, vehicle: Vehicle, data: dict) -> Vehicle:
    for k, v in data.items():
        if v is not None:
            setattr(vehicle, k, v)
    vehicle.modified_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(vehicle)
    return vehicle


# ---------------------------------------------------------------------------
# Drivers
# ---------------------------------------------------------------------------


def list_drivers(
    db: Session,
    company_id: str,
    *,
    active_only: bool = True,
    page: int = 1,
    per_page: int = 50,
) -> tuple[list[Driver], int]:
    q = db.query(Driver).filter(Driver.company_id == company_id)
    if active_only:
        q = q.filter(Driver.active.is_(True))
    total = q.count()
    items = q.order_by(Driver.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return items, total


def get_driver(db: Session, driver_id: str, company_id: str) -> Driver | None:
    return (
        db.query(Driver)
        .filter(Driver.id == driver_id, Driver.company_id == company_id)
        .first()
    )


def get_driver_by_employee(db: Session, employee_id: str, company_id: str) -> Driver | None:
    return (
        db.query(Driver)
        .filter(Driver.employee_id == employee_id, Driver.company_id == company_id)
        .first()
    )


def create_driver(db: Session, company_id: str, data: dict) -> Driver:
    driver = Driver(id=str(uuid.uuid4()), company_id=company_id, **data)
    db.add(driver)
    db.commit()
    db.refresh(driver)
    return driver


def update_driver(db: Session, driver: Driver, data: dict) -> Driver:
    for k, v in data.items():
        if v is not None:
            setattr(driver, k, v)
    driver.modified_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(driver)
    return driver


# ---------------------------------------------------------------------------
# Carriers
# ---------------------------------------------------------------------------


def list_carriers(
    db: Session,
    company_id: str,
    *,
    active_only: bool = True,
    carrier_type: str | None = None,
    page: int = 1,
    per_page: int = 50,
) -> tuple[list[Carrier], int]:
    q = db.query(Carrier).filter(Carrier.company_id == company_id)
    if active_only:
        q = q.filter(Carrier.active.is_(True))
    if carrier_type:
        q = q.filter(Carrier.carrier_type == carrier_type)
    total = q.count()
    items = q.order_by(Carrier.name).offset((page - 1) * per_page).limit(per_page).all()
    return items, total


def get_carrier(db: Session, carrier_id: str, company_id: str) -> Carrier | None:
    return (
        db.query(Carrier)
        .filter(Carrier.id == carrier_id, Carrier.company_id == company_id)
        .first()
    )


def create_carrier(db: Session, company_id: str, data: dict) -> Carrier:
    carrier = Carrier(id=str(uuid.uuid4()), company_id=company_id, **data)
    db.add(carrier)
    db.commit()
    db.refresh(carrier)
    return carrier


def update_carrier(db: Session, carrier: Carrier, data: dict) -> Carrier:
    for k, v in data.items():
        if v is not None:
            setattr(carrier, k, v)
    carrier.modified_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(carrier)
    return carrier


# ---------------------------------------------------------------------------
# Deliveries
# ---------------------------------------------------------------------------


def list_deliveries(
    db: Session,
    company_id: str,
    *,
    status: str | None = None,
    delivery_type: str | None = None,
    customer_id: str | None = None,
    carrier_id: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    unscheduled_only: bool = False,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Delivery], int]:
    q = db.query(Delivery).filter(Delivery.company_id == company_id)
    if status:
        q = q.filter(Delivery.status == status)
    if delivery_type:
        q = q.filter(Delivery.delivery_type == delivery_type)
    if customer_id:
        q = q.filter(Delivery.customer_id == customer_id)
    if carrier_id:
        q = q.filter(Delivery.carrier_id == carrier_id)
    if date_from:
        q = q.filter(Delivery.requested_date >= date_from)
    if date_to:
        q = q.filter(Delivery.requested_date <= date_to)
    if unscheduled_only:
        q = q.filter(Delivery.status == "pending")
    total = q.count()
    items = (
        q.order_by(Delivery.requested_date.asc().nullslast(), Delivery.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return items, total


def get_delivery(db: Session, delivery_id: str, company_id: str) -> Delivery | None:
    return (
        db.query(Delivery)
        .filter(Delivery.id == delivery_id, Delivery.company_id == company_id)
        .first()
    )


def create_delivery(db: Session, company_id: str, data: dict, actor_id: str | None = None) -> Delivery:
    delivery = Delivery(
        id=str(uuid.uuid4()),
        company_id=company_id,
        created_by=actor_id,
        **data,
    )
    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    return delivery


def update_delivery(db: Session, delivery: Delivery, data: dict) -> Delivery:
    for k, v in data.items():
        if v is not None:
            setattr(delivery, k, v)
    delivery.modified_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(delivery)
    return delivery


def get_delivery_stats(db: Session, company_id: str) -> dict:
    today = date.today()
    base = db.query(Delivery).filter(Delivery.company_id == company_id)

    total = base.count()
    pending = base.filter(Delivery.status == "pending").count()
    scheduled = base.filter(Delivery.status == "scheduled").count()
    in_transit = base.filter(Delivery.status == "in_transit").count()
    completed_today = (
        base.filter(
            Delivery.status == "completed",
            func.date(Delivery.completed_at) == today,
        ).count()
    )
    active_routes = (
        db.query(DeliveryRoute)
        .filter(
            DeliveryRoute.company_id == company_id,
            DeliveryRoute.route_date == today,
            DeliveryRoute.status.in_(["dispatched", "in_progress"]),
        )
        .count()
    )
    available_drivers = (
        db.query(Driver)
        .filter(Driver.company_id == company_id, Driver.active.is_(True))
        .count()
    )
    available_vehicles = (
        db.query(Vehicle)
        .filter(Vehicle.company_id == company_id, Vehicle.active.is_(True))
        .count()
    )

    return {
        "total_deliveries": total,
        "pending": pending,
        "scheduled": scheduled,
        "in_transit": in_transit,
        "completed_today": completed_today,
        "active_routes": active_routes,
        "available_drivers": available_drivers,
        "available_vehicles": available_vehicles,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def list_routes(
    db: Session,
    company_id: str,
    *,
    route_date: date | None = None,
    driver_id: str | None = None,
    status: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[DeliveryRoute], int]:
    q = db.query(DeliveryRoute).filter(DeliveryRoute.company_id == company_id)
    if route_date:
        q = q.filter(DeliveryRoute.route_date == route_date)
    if driver_id:
        q = q.filter(DeliveryRoute.driver_id == driver_id)
    if status:
        q = q.filter(DeliveryRoute.status == status)
    total = q.count()
    items = (
        q.order_by(DeliveryRoute.route_date.desc(), DeliveryRoute.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return items, total


def get_route(db: Session, route_id: str, company_id: str) -> DeliveryRoute | None:
    return (
        db.query(DeliveryRoute)
        .filter(DeliveryRoute.id == route_id, DeliveryRoute.company_id == company_id)
        .first()
    )


def create_route(db: Session, company_id: str, data: dict, actor_id: str | None = None) -> DeliveryRoute:
    route = DeliveryRoute(
        id=str(uuid.uuid4()),
        company_id=company_id,
        created_by=actor_id,
        **data,
    )
    db.add(route)
    db.commit()
    db.refresh(route)
    return route


def update_route(db: Session, route: DeliveryRoute, data: dict) -> DeliveryRoute:
    for k, v in data.items():
        if v is not None:
            setattr(route, k, v)
    route.modified_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(route)
    return route


# ---------------------------------------------------------------------------
# Stops
# ---------------------------------------------------------------------------


def add_stop(db: Session, route: DeliveryRoute, delivery_id: str, sequence_number: int) -> DeliveryStop:
    stop = DeliveryStop(
        id=str(uuid.uuid4()),
        route_id=route.id,
        delivery_id=delivery_id,
        sequence_number=sequence_number,
    )
    db.add(stop)
    route.total_stops = (
        db.query(func.count(DeliveryStop.id))
        .filter(DeliveryStop.route_id == route.id)
        .scalar()
        or 0
    ) + 1
    route.modified_at = datetime.now(timezone.utc)

    # Mark delivery as scheduled
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()
    if delivery and delivery.status == "pending":
        delivery.status = "scheduled"
        delivery.scheduled_at = datetime.now(timezone.utc)
        delivery.modified_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(stop)
    return stop


def remove_stop(db: Session, route: DeliveryRoute, stop_id: str) -> bool:
    stop = (
        db.query(DeliveryStop)
        .filter(DeliveryStop.id == stop_id, DeliveryStop.route_id == route.id)
        .first()
    )
    if not stop:
        return False
    db.delete(stop)
    route.total_stops = max(0, route.total_stops - 1)
    route.modified_at = datetime.now(timezone.utc)
    db.commit()
    return True


def resequence_stops(db: Session, route: DeliveryRoute, stop_ids: list[str]) -> list[DeliveryStop]:
    stops = (
        db.query(DeliveryStop)
        .filter(DeliveryStop.route_id == route.id)
        .all()
    )
    stop_map = {s.id: s for s in stops}
    for idx, sid in enumerate(stop_ids):
        if sid in stop_map:
            stop_map[sid].sequence_number = idx + 1
    route.modified_at = datetime.now(timezone.utc)
    db.commit()
    return sorted(stops, key=lambda s: s.sequence_number)


def update_stop_status(db: Session, stop: DeliveryStop, status: str, driver_notes: str | None = None) -> DeliveryStop:
    now = datetime.now(timezone.utc)
    stop.status = status
    if driver_notes is not None:
        stop.driver_notes = driver_notes
    if status == "arrived" and not stop.actual_arrival:
        stop.actual_arrival = now
    elif status == "completed" and not stop.actual_departure:
        stop.actual_departure = now
    stop.modified_at = now
    db.commit()
    db.refresh(stop)
    return stop


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


def create_event(
    db: Session,
    company_id: str,
    data: dict,
    driver_id: str | None = None,
) -> DeliveryEvent:
    event = DeliveryEvent(
        id=str(uuid.uuid4()),
        company_id=company_id,
        driver_id=driver_id,
        **data,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_events(db: Session, delivery_id: str, company_id: str) -> list[DeliveryEvent]:
    return (
        db.query(DeliveryEvent)
        .filter(
            DeliveryEvent.delivery_id == delivery_id,
            DeliveryEvent.company_id == company_id,
        )
        .order_by(DeliveryEvent.created_at.asc())
        .all()
    )


# ---------------------------------------------------------------------------
# Media
# ---------------------------------------------------------------------------


def create_media(
    db: Session,
    company_id: str,
    delivery_id: str,
    media_type: str,
    file_url: str,
    event_id: str | None = None,
    captured_at: datetime | None = None,
) -> DeliveryMedia:
    media = DeliveryMedia(
        id=str(uuid.uuid4()),
        company_id=company_id,
        delivery_id=delivery_id,
        event_id=event_id,
        media_type=media_type,
        file_url=file_url,
        captured_at=captured_at,
    )
    db.add(media)
    db.commit()
    db.refresh(media)
    return media
