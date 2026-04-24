"""Core CRUD service for the delivery module — vehicles, drivers, carriers,
deliveries, routes, stops, events, and media."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

import logging

from app.models.carrier import Carrier
from app.models.delivery import Delivery
from app.models.delivery_event import DeliveryEvent
from app.models.delivery_media import DeliveryMedia
from app.models.delivery_route import DeliveryRoute
from app.models.delivery_stop import DeliveryStop
from app.models.driver import Driver
from app.models.user import User
from app.models.vehicle import Vehicle

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Phase 4.3 (r56) transitional assignee-identity helper
# ---------------------------------------------------------------------------


def resolve_primary_assignee_id(
    db: Session, raw_value: str | None, company_id: str
) -> str | None:
    """Translate a raw assignee identifier to a valid ``users.id``.

    Phase 4.3.2 migrated ``deliveries.assigned_driver_id`` (bare
    String, stored ``drivers.id`` values) to
    ``deliveries.primary_assignee_id`` (FK to ``users.id``). Many
    existing call sites — the Monitor drag handler, the ancillary
    assign routes, the Scheduling Focus drag handler — continue to
    pass ``drivers.id`` values because frontend ``MonitorDriverDTO``
    exposes ``driver.id`` as the assignee identity.

    This helper is the transitional glue. It accepts either:

      - a ``users.id`` value (returned unchanged)
      - a ``drivers.id`` value (translated to ``drivers.employee_id``
        = the canonical tenant-user identity for that Driver row)
      - ``None`` (returned as None — valid "clear assignment")

    Raises ``ValueError`` if:
      - the value is neither a User.id nor a Driver.id under the
        caller's tenant
      - the Driver has no ``employee_id`` (portal-only drivers;
        kanban assignment for those is post-September follow-up)

    Callers translate ``ValueError`` into HTTP 400 at the route
    boundary. This helper is intentionally tenant-scoped — the
    ``company_id`` argument prevents cross-tenant resolution even
    against valid-looking ids from other tenants.

    Retired in Phase 4.3.3 once the frontend ``MonitorDriverDTO``
    surfaces ``user_id`` explicitly and every caller passes it.
    """
    if raw_value is None:
        return None
    # Is it already a valid users.id?
    hit_user = (
        db.query(User)
        .filter(User.id == raw_value, User.company_id == company_id)
        .first()
    )
    if hit_user is not None:
        return raw_value
    # Fallback: maybe it's a drivers.id — translate via employee_id.
    hit_driver = (
        db.query(Driver)
        .filter(Driver.id == raw_value, Driver.company_id == company_id)
        .first()
    )
    if hit_driver is not None:
        if hit_driver.employee_id is None:
            raise ValueError(
                "Driver has no linked user account (portal-only "
                "driver). Kanban assignment for portal drivers is a "
                "post-September follow-up."
            )
        return hit_driver.employee_id
    raise ValueError(
        f"primary_assignee_id={raw_value!r} does not resolve to a "
        f"tenant user or driver."
    )


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


# Phase 8e.2.1 — get_driver_by_employee retired. Driver identity
# resolves via portal_user_id going forward (see
# app.services.portal.user_service.resolve_driver_for_portal_user).
# Kept as a deprecation stub only because one caller in
# routes/extensions.py was rewritten to the portal path; removing
# the function entirely would orphan any straggler imports during
# the transition.
def get_driver_by_employee(db: Session, employee_id: str, company_id: str) -> "Driver | None":  # noqa: F821
    import warnings

    warnings.warn(
        "get_driver_by_employee is retired (Phase 8e.2.1). Use "
        "portal.user_service.resolve_driver_for_portal_user.",
        DeprecationWarning,
        stacklevel=2,
    )
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

    # Dual-write: also create vault item
    _sync_delivery_to_vault(db, delivery, actor_id)

    return delivery


def update_delivery(db: Session, delivery: Delivery, data: dict) -> Delivery:
    # Capture the state the revert-hook needs to inspect BEFORE the
    # mutation — the requested_date may itself be one of the edited
    # fields, and we need to revert the schedule for whichever date
    # (old or new) was finalized.
    pre_edit_date = delivery.requested_date

    # Phase 4.2.2 — removed the prior `if v is not None` guard. It was
    # belt-and-suspenders over the route-layer `exclude_none=True` that
    # already stripped nulls before they reached this function. Its
    # effect was to silently discard ANY explicit null in `data`,
    # which broke drag-to-Unassigned (setting `primary_assignee_id` to
    # None is a legitimate "clear the field" operation, not a "skip
    # this field" signal). The route layer now uses
    # `exclude_unset=True` so unset fields are omitted from `data` but
    # explicit nulls reach this loop and set the column to NULL as
    # intended. Callers passing literal dicts (carrier_portal.py,
    # deliveries.py manual carrier-status path) never include None
    # keys, so they're unaffected.
    for k, v in data.items():
        setattr(delivery, k, v)
    delivery.modified_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(delivery)

    # Phase B Session 1 — schedule revert hook. After the delivery
    # commit, if this edit affected a finalized schedule, flip it
    # back to draft. Called at both the pre-edit date (in case the
    # delivery was REMOVED from a finalized day) and the post-edit
    # date (in case it was MOVED INTO a finalized day).
    try:
        from app.services import delivery_schedule_service as _sched
        if pre_edit_date is not None:
            row = _sched.get_schedule_state(db, delivery.company_id, pre_edit_date)
            if row is not None and row.state == "finalized":
                _sched.revert_to_draft(
                    db,
                    delivery.company_id,
                    pre_edit_date,
                    reason=f"Delivery {delivery.id[:8]} edited after finalize",
                )
        if delivery.requested_date is not None and delivery.requested_date != pre_edit_date:
            row = _sched.get_schedule_state(db, delivery.company_id, delivery.requested_date)
            if row is not None and row.state == "finalized":
                _sched.revert_to_draft(
                    db,
                    delivery.company_id,
                    delivery.requested_date,
                    reason=f"Delivery {delivery.id[:8]} moved into finalized day",
                )
    except Exception:
        # Revert-hook failures never block the delivery update itself.
        # Observability: failures log but don't raise.
        import logging as _logging
        _logging.getLogger(__name__).exception(
            "schedule revert hook failed for delivery %s", delivery.id
        )

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

    # Dual-write: also create vault item
    _sync_route_to_vault(db, route, actor_id)

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

    # Sync SalesOrder status when stop is completed
    if status == "completed":
        _sync_sales_order_delivery(db, stop, now)

    db.commit()
    db.refresh(stop)
    return stop


def _sync_sales_order_delivery(db: Session, stop, now) -> None:
    """Mark the associated SalesOrder as delivered when a stop is completed."""
    try:
        from app.models.delivery import Delivery
        from app.models.sales_order import SalesOrder

        delivery = db.query(Delivery).filter(Delivery.id == stop.delivery_id).first()
        if not delivery or not delivery.order_id:
            return

        order = db.query(SalesOrder).filter(SalesOrder.id == delivery.order_id).first()
        if not order:
            return
        if order.status in ("completed", "invoiced", "cancelled"):
            return

        order.status = "delivered"
        order.delivered_at = now
        order.driver_confirmed = True
        order.delivery_auto_confirmed = False
    except Exception:
        pass  # Don't break stop update if sync fails


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


def seed_delivery_types(db: Session, company_id: str) -> int:
    """Seed default delivery types for a new company. Idempotent."""
    from app.models.delivery_type_definition import DeliveryTypeDefinition

    existing = (
        db.query(DeliveryTypeDefinition.key)
        .filter(DeliveryTypeDefinition.company_id == company_id)
        .all()
    )
    existing_keys = {r[0] for r in existing}

    DEFAULTS = [
        {
            "key": "standard",
            "name": "Standard Delivery",
            "color": "gray",
            "description": "Standard delivery with basic confirmation.",
            "driver_instructions": "Deliver to the specified address. Get customer acknowledgment.",
            "requires_signature": False,
            "requires_photo": False,
            "sort_order": 0,
        },
    ]

    count = 0
    for d in DEFAULTS:
        if d["key"] not in existing_keys:
            db.add(DeliveryTypeDefinition(company_id=company_id, **d))
            count += 1

    if count:
        db.flush()
    return count


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

    # Dual-write: delivery photos → vault documents
    _sync_media_to_vault(db, media, delivery_id)

    return media


# ---------------------------------------------------------------------------
# Vault dual-write helpers
# ---------------------------------------------------------------------------


def _sync_delivery_to_vault(db: Session, delivery: Delivery, actor_id: str | None = None) -> None:
    """Create a VaultItem mirror of a delivery record (dual-write pattern)."""
    try:
        from app.services.vault_service import create_vault_item

        # Build title from available data
        customer_name = ""
        if delivery.customer:
            customer_name = getattr(delivery.customer, "name", "")
        title = f"Delivery to {customer_name}" if customer_name else f"Delivery #{delivery.id[:8]}"

        # Determine shared companies for cross-tenant visibility
        shared_ids = None
        if delivery.customer_id:
            try:
                from app.models.customer import Customer
                cust = db.query(Customer).filter(Customer.id == delivery.customer_id).first()
                if cust and getattr(cust, "company_id", None) and cust.company_id != delivery.company_id:
                    shared_ids = [cust.company_id]
            except Exception:
                pass

        create_vault_item(
            db,
            company_id=delivery.company_id,
            item_type="event",
            title=title,
            description=delivery.special_instructions,
            event_start=delivery.scheduled_at or (
                datetime.combine(delivery.requested_date, datetime.min.time()).replace(tzinfo=timezone.utc)
                if delivery.requested_date else None
            ),
            event_end=None,
            event_location=delivery.delivery_address,
            event_type="delivery",
            visibility="shared" if shared_ids else "internal",
            shared_with_company_ids=shared_ids,
            related_entity_type="order",
            related_entity_id=delivery.order_id,
            status="active",
            source="system_generated",
            source_entity_id=delivery.id,
            created_by=actor_id,
            metadata_json={
                "delivery_type": delivery.delivery_type,
                "priority": delivery.priority,
                "customer_id": delivery.customer_id,
                "weight_lbs": str(delivery.weight_lbs) if delivery.weight_lbs else None,
                "scheduling_type": delivery.scheduling_type,
            },
        )
        db.commit()
    except Exception:
        logger.warning("Vault dual-write failed for delivery %s", delivery.id, exc_info=True)
        db.rollback()


def _sync_route_to_vault(db: Session, route: DeliveryRoute, actor_id: str | None = None) -> None:
    """Create a VaultItem mirror of a route record (dual-write pattern)."""
    try:
        from app.services.vault_service import create_vault_item

        driver_name = ""
        if route.driver:
            driver_name = getattr(route.driver, "name", "") or f"Driver {route.driver_id[:8]}"
        title = f"Route: {driver_name} — {route.route_date}" if driver_name else f"Route {route.route_date}"

        create_vault_item(
            db,
            company_id=route.company_id,
            item_type="event",
            title=title,
            description=route.notes,
            event_start=datetime.combine(route.route_date, datetime.min.time()).replace(tzinfo=timezone.utc),
            event_type="route",
            related_entity_type="employee",
            related_entity_id=route.driver_id,
            status="active",
            source="system_generated",
            source_entity_id=route.id,
            created_by=actor_id,
            metadata_json={
                "driver_id": route.driver_id,
                "vehicle_id": route.vehicle_id,
                "total_stops": route.total_stops,
                "route_status": route.status,
            },
        )
        db.commit()
    except Exception:
        logger.warning("Vault dual-write failed for route %s", route.id, exc_info=True)
        db.rollback()


def _sync_media_to_vault(db: Session, media: DeliveryMedia, delivery_id: str) -> None:
    """Create a VaultItem for delivery media (photos, signatures, etc.).

    D-6 also writes a canonical `delivery_confirmation` Document (one
    per delivery, not per media) + DocumentShare to the customer tenant
    when the customer is itself a tenant. This feeds the unified
    cross-tenant inbox alongside statements + legacy vault prints.
    """
    try:
        from app.services.vault_service import create_vault_item

        delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()
        if not delivery:
            return

        # Determine cross-tenant sharing
        shared_ids = None
        customer_tenant_id: str | None = None
        if delivery.customer_id:
            try:
                from app.models.customer import Customer
                cust = db.query(Customer).filter(Customer.id == delivery.customer_id).first()
                if cust and getattr(cust, "company_id", None) and cust.company_id != delivery.company_id:
                    shared_ids = [cust.company_id]
                    customer_tenant_id = cust.company_id
            except Exception:
                pass

        doc_type = "delivery_confirmation" if media.media_type in ("photo", "signature") else "delivery_media"

        create_vault_item(
            db,
            company_id=delivery.company_id,
            item_type="document",
            title=f"Delivery {media.media_type}: {delivery_id[:8]}",
            document_type=doc_type,
            r2_key=media.file_url if media.file_url and media.file_url.startswith("tenants/") else None,
            mime_type="image/jpeg" if media.media_type == "photo" else None,
            visibility="shared" if shared_ids else "internal",
            shared_with_company_ids=shared_ids,
            related_entity_type="order",
            related_entity_id=delivery.order_id,
            source="system_generated",
            source_entity_id=media.id,
            metadata_json={
                "delivery_id": delivery_id,
                "media_type": media.media_type,
                "file_url": media.file_url,
            },
        )

        # Phase D-6: unified cross-tenant Document + Share. Best-effort
        # — failure is logged but doesn't block the VaultItem write.
        if media.media_type in ("photo", "signature") and customer_tenant_id:
            try:
                _ensure_delivery_confirmation_document(
                    db, delivery=delivery, media=media,
                    target_tenant_id=customer_tenant_id,
                )
            except Exception:
                logger.warning(
                    "Delivery confirmation Document+Share failed for media %s",
                    media.id,
                    exc_info=True,
                )

        db.commit()
    except Exception:
        logger.warning("Vault dual-write failed for media %s", media.id, exc_info=True)
        db.rollback()


def _ensure_delivery_confirmation_document(
    db: Session,
    *,
    delivery: Delivery,
    media: DeliveryMedia,
    target_tenant_id: str,
) -> None:
    """Idempotent per-delivery canonical Document + share. First media
    sync for a delivery creates the Document; subsequent media syncs
    reuse it (additional photos don't spawn additional Documents)."""
    from app.models.canonical_document import Document
    from app.services.documents import document_sharing_service
    import uuid as _uuid

    # Look for an existing delivery_confirmation Document for this delivery
    existing = (
        db.query(Document)
        .filter(
            Document.company_id == delivery.company_id,
            Document.document_type == "delivery_confirmation",
            Document.entity_type == "delivery",
            Document.entity_id == delivery.id,
            Document.deleted_at.is_(None),
        )
        .first()
    )
    if existing is None:
        # Create a lightweight Document anchoring this delivery in the
        # canonical layer. storage_key points at the first media file
        # (the "primary" artifact for the delivery); subsequent media
        # remain VaultItems per the existing pattern.
        storage_key = (
            media.file_url
            if media.file_url and media.file_url.startswith("tenants/")
            else f"tenants/{delivery.company_id}/deliveries/{delivery.id}/primary"
        )
        existing = Document(
            id=str(_uuid.uuid4()),
            company_id=delivery.company_id,
            document_type="delivery_confirmation",
            title=f"Delivery confirmation — {delivery.id[:8]}",
            description=(
                f"Proof of delivery for order {delivery.order_id or ''}".strip()
            ),
            storage_key=storage_key,
            mime_type="image/jpeg" if media.media_type == "photo" else "application/octet-stream",
            file_size_bytes=None,
            status="rendered",
            entity_type="delivery",
            entity_id=delivery.id,
            sales_order_id=delivery.order_id,
            caller_module="delivery_service._sync_media_to_vault",
        )
        db.add(existing)
        db.flush()

    document_sharing_service.ensure_share(
        db,
        document=existing,
        target_company_id=target_tenant_id,
        reason=f"Delivery confirmation for order {delivery.order_id or 'unknown'}",
        source_module="delivery_service",
        enforce_relationship=False,
    )
