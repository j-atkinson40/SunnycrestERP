"""Delivery dispatch management routes — deliveries, routes, stops,
vehicles, drivers, carriers, and stats."""

from datetime import date, datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_module, require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.delivery import (
    CarrierCreate,
    CarrierResponse,
    CarrierUpdate,
    DeliveryCreate,
    DeliveryListItem,
    DeliveryResponse,
    DeliveryStats,
    DeliveryUpdate,
    DriverCreate,
    DriverResponse,
    DriverUpdate,
    EventCreate,
    EventResponse,
    MediaResponse,
    PaginatedCarriers,
    PaginatedDeliveries,
    PaginatedDrivers,
    PaginatedRoutes,
    PaginatedVehicles,
    RouteCreate,
    RouteResponse,
    RouteUpdate,
    StopCreate,
    StopResequence,
    StopResponse,
    VehicleCreate,
    VehicleResponse,
    VehicleUpdate,
)
from app.services import delivery_service, delivery_notification_service

router = APIRouter()

MODULE = "driver_delivery"


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=DeliveryStats)
def get_stats(
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("delivery.view")),
):
    return delivery_service.get_delivery_stats(db, current_user.company_id)


# ---------------------------------------------------------------------------
# Vehicles
# ---------------------------------------------------------------------------


@router.get("/vehicles", response_model=PaginatedVehicles)
def list_vehicles(
    active_only: bool = True,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("vehicles.view")),
):
    items, total = delivery_service.list_vehicles(
        db, current_user.company_id, active_only=active_only, page=page, per_page=per_page
    )
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.post("/vehicles", response_model=VehicleResponse, status_code=201)
def create_vehicle(
    data: VehicleCreate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("vehicles.create")),
):
    return delivery_service.create_vehicle(
        db, current_user.company_id, data.model_dump(exclude_none=True)
    )


@router.get("/vehicles/{vehicle_id}", response_model=VehicleResponse)
def get_vehicle(
    vehicle_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("vehicles.view")),
):
    vehicle = delivery_service.get_vehicle(db, vehicle_id, current_user.company_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle


@router.patch("/vehicles/{vehicle_id}", response_model=VehicleResponse)
def update_vehicle(
    vehicle_id: str,
    data: VehicleUpdate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("vehicles.edit")),
):
    vehicle = delivery_service.get_vehicle(db, vehicle_id, current_user.company_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return delivery_service.update_vehicle(db, vehicle, data.model_dump(exclude_none=True))


# ---------------------------------------------------------------------------
# Drivers
# ---------------------------------------------------------------------------


@router.get("/drivers", response_model=PaginatedDrivers)
def list_drivers(
    active_only: bool = True,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("drivers.view")),
):
    items, total = delivery_service.list_drivers(
        db, current_user.company_id, active_only=active_only, page=page, per_page=per_page
    )
    # Enrich with employee name
    result_items = []
    for d in items:
        resp = DriverResponse.model_validate(d)
        if d.employee:
            resp.employee_name = f"{d.employee.first_name} {d.employee.last_name}"
        result_items.append(resp)
    return {"items": result_items, "total": total, "page": page, "per_page": per_page}


@router.post("/drivers", response_model=DriverResponse, status_code=201)
def create_driver(
    data: DriverCreate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("drivers.create")),
):
    return delivery_service.create_driver(
        db, current_user.company_id, data.model_dump(exclude_none=True)
    )


@router.get("/drivers/{driver_id}", response_model=DriverResponse)
def get_driver(
    driver_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("drivers.view")),
):
    driver = delivery_service.get_driver(db, driver_id, current_user.company_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    return driver


@router.patch("/drivers/{driver_id}", response_model=DriverResponse)
def update_driver(
    driver_id: str,
    data: DriverUpdate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("drivers.edit")),
):
    driver = delivery_service.get_driver(db, driver_id, current_user.company_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    return delivery_service.update_driver(db, driver, data.model_dump(exclude_none=True))


# ---------------------------------------------------------------------------
# Carriers
# ---------------------------------------------------------------------------


@router.get("/carriers", response_model=PaginatedCarriers)
def list_carriers(
    active_only: bool = True,
    carrier_type: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("carriers.view")),
):
    items, total = delivery_service.list_carriers(
        db, current_user.company_id,
        active_only=active_only, carrier_type=carrier_type,
        page=page, per_page=per_page,
    )
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.post("/carriers", response_model=CarrierResponse, status_code=201)
def create_carrier(
    data: CarrierCreate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("carriers.create")),
):
    return delivery_service.create_carrier(
        db, current_user.company_id, data.model_dump(exclude_none=True)
    )


@router.get("/carriers/{carrier_id}", response_model=CarrierResponse)
def get_carrier(
    carrier_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("carriers.view")),
):
    carrier = delivery_service.get_carrier(db, carrier_id, current_user.company_id)
    if not carrier:
        raise HTTPException(status_code=404, detail="Carrier not found")
    return carrier


@router.patch("/carriers/{carrier_id}", response_model=CarrierResponse)
def update_carrier(
    carrier_id: str,
    data: CarrierUpdate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("carriers.edit")),
):
    carrier = delivery_service.get_carrier(db, carrier_id, current_user.company_id)
    if not carrier:
        raise HTTPException(status_code=404, detail="Carrier not found")
    return delivery_service.update_carrier(db, carrier, data.model_dump(exclude_none=True))


# ---------------------------------------------------------------------------
# Deliveries
# ---------------------------------------------------------------------------


@router.get("/deliveries", response_model=PaginatedDeliveries)
def list_deliveries(
    status: str | None = None,
    delivery_type: str | None = None,
    customer_id: str | None = None,
    carrier_id: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    unscheduled_only: bool = False,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("delivery.view")),
):
    items, total = delivery_service.list_deliveries(
        db, current_user.company_id,
        status=status, delivery_type=delivery_type,
        customer_id=customer_id, carrier_id=carrier_id,
        date_from=date_from, date_to=date_to,
        unscheduled_only=unscheduled_only,
        page=page, per_page=per_page,
    )
    result_items = []
    for d in items:
        item = DeliveryListItem.model_validate(d)
        if d.customer:
            item.customer_name = getattr(d.customer, "name", None) or getattr(d.customer, "company_name", None)
        if d.carrier:
            item.carrier_name = d.carrier.name
        result_items.append(item)
    return {"items": result_items, "total": total, "page": page, "per_page": per_page}


@router.post("/deliveries", response_model=DeliveryResponse, status_code=201)
def create_delivery(
    data: DeliveryCreate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("delivery.create")),
):
    delivery = delivery_service.create_delivery(
        db, current_user.company_id,
        data.model_dump(exclude_none=True),
        actor_id=current_user.id,
    )
    # If assigned to a third-party carrier, trigger carrier notification
    if delivery.carrier_id and delivery.carrier and delivery.carrier.carrier_type == "third_party":
        delivery_notification_service.on_carrier_assigned(db, delivery)
    return delivery


@router.get("/deliveries/{delivery_id}", response_model=DeliveryResponse)
def get_delivery(
    delivery_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("delivery.view")),
):
    delivery = delivery_service.get_delivery(db, delivery_id, current_user.company_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    resp = DeliveryResponse.model_validate(delivery)
    if delivery.customer:
        resp.customer_name = getattr(delivery.customer, "name", None) or getattr(delivery.customer, "company_name", None)
    if delivery.carrier:
        resp.carrier_name = delivery.carrier.name
    return resp


@router.patch("/deliveries/{delivery_id}", response_model=DeliveryResponse)
def update_delivery(
    delivery_id: str,
    data: DeliveryUpdate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("delivery.edit")),
):
    delivery = delivery_service.get_delivery(db, delivery_id, current_user.company_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    old_carrier_id = delivery.carrier_id
    updated = delivery_service.update_delivery(db, delivery, data.model_dump(exclude_none=True))
    # If carrier was newly assigned, trigger notification
    if updated.carrier_id and updated.carrier_id != old_carrier_id:
        if updated.carrier and updated.carrier.carrier_type == "third_party":
            delivery_notification_service.on_carrier_assigned(db, updated)
    return updated


@router.patch("/deliveries/{delivery_id}/carrier-status")
def manual_carrier_status_update(
    delivery_id: str,
    new_status: str = Query(...),
    carrier_notes: str | None = None,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("delivery.dispatch")),
):
    """Manually update the status of a third-party carrier delivery."""
    delivery = delivery_service.get_delivery(db, delivery_id, current_user.company_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    if not delivery.carrier_id:
        raise HTTPException(status_code=400, detail="Delivery is not assigned to a carrier")

    delivery_service.update_delivery(db, delivery, {"status": new_status})
    delivery_service.create_event(
        db,
        current_user.company_id,
        {
            "delivery_id": delivery_id,
            "event_type": f"status_change_{new_status}",
            "source": "dispatch_manual",
            "notes": carrier_notes,
        },
    )
    return {"status": "ok", "new_status": new_status}


# ---------------------------------------------------------------------------
# Delivery Events
# ---------------------------------------------------------------------------


@router.get("/deliveries/{delivery_id}/events", response_model=list[EventResponse])
def list_delivery_events(
    delivery_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("delivery.view")),
):
    return delivery_service.list_events(db, delivery_id, current_user.company_id)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/routes", response_model=PaginatedRoutes)
def list_routes(
    route_date: date | None = None,
    driver_id: str | None = None,
    route_status: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("routes.view")),
):
    items, total = delivery_service.list_routes(
        db, current_user.company_id,
        route_date=route_date, driver_id=driver_id, status=route_status,
        page=page, per_page=per_page,
    )
    result_items = []
    for r in items:
        resp = RouteResponse.model_validate(r)
        if r.driver and r.driver.employee:
            resp.driver_name = f"{r.driver.employee.first_name} {r.driver.employee.last_name}"
        if r.vehicle:
            resp.vehicle_name = r.vehicle.name
        result_items.append(resp)
    return {"items": result_items, "total": total, "page": page, "per_page": per_page}


@router.post("/routes", response_model=RouteResponse, status_code=201)
def create_route(
    data: RouteCreate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("routes.create")),
):
    return delivery_service.create_route(
        db, current_user.company_id,
        data.model_dump(exclude_none=True),
        actor_id=current_user.id,
    )


@router.get("/routes/{route_id}", response_model=RouteResponse)
def get_route(
    route_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("routes.view")),
):
    route = delivery_service.get_route(db, route_id, current_user.company_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    resp = RouteResponse.model_validate(route)
    if route.driver and route.driver.employee:
        resp.driver_name = f"{route.driver.employee.first_name} {route.driver.employee.last_name}"
    if route.vehicle:
        resp.vehicle_name = route.vehicle.name
    return resp


@router.patch("/routes/{route_id}", response_model=RouteResponse)
def update_route(
    route_id: str,
    data: RouteUpdate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("routes.edit")),
):
    route = delivery_service.get_route(db, route_id, current_user.company_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    return delivery_service.update_route(db, route, data.model_dump(exclude_none=True))


# ---------------------------------------------------------------------------
# Route Stops
# ---------------------------------------------------------------------------


@router.post("/routes/{route_id}/stops", response_model=StopResponse, status_code=201)
def add_stop(
    route_id: str,
    data: StopCreate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("routes.edit")),
):
    route = delivery_service.get_route(db, route_id, current_user.company_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    return delivery_service.add_stop(db, route, data.delivery_id, data.sequence_number)


@router.patch("/routes/{route_id}/stops/resequence")
def resequence_stops(
    route_id: str,
    data: StopResequence,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("routes.edit")),
):
    route = delivery_service.get_route(db, route_id, current_user.company_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    stops = delivery_service.resequence_stops(db, route, data.stop_ids)
    return {"status": "ok", "stops": [StopResponse.model_validate(s) for s in stops]}


@router.delete("/routes/{route_id}/stops/{stop_id}", status_code=204)
def remove_stop(
    route_id: str,
    stop_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("routes.edit")),
):
    route = delivery_service.get_route(db, route_id, current_user.company_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    if not delivery_service.remove_stop(db, route, stop_id):
        raise HTTPException(status_code=404, detail="Stop not found")


# ---------------------------------------------------------------------------
# Delivery completion with optional driver exceptions
# ---------------------------------------------------------------------------


class DeliveryExceptionItem(BaseModel):
    product_id: Optional[str] = None
    reason: str  # 'weather' | 'access_issue' | 'family_request' | 'equipment_failure' | 'other'
    notes: Optional[str] = None


class DeliveryCompleteRequest(BaseModel):
    completed_at: Optional[datetime] = None
    exceptions: Optional[list[DeliveryExceptionItem]] = None


@router.post("/{delivery_id}/complete", status_code=200)
def complete_delivery(
    delivery_id: str,
    data: DeliveryCompleteRequest,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_permission("delivery.edit")),
):
    """Mark a delivery as completed.

    Optionally report driver exceptions (items that could not be fulfilled).
    Exceptions are stored on the linked sales order and will be flagged on
    tonight's draft invoice for morning review.
    """
    from app.models.delivery import Delivery
    from app.models.sales_order import SalesOrder

    delivery = (
        db.query(Delivery)
        .filter(
            Delivery.id == delivery_id,
            Delivery.company_id == current_user.company_id,
        )
        .first()
    )
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    if delivery.status in ("cancelled", "failed"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot complete a delivery with status '{delivery.status}'",
        )

    now = data.completed_at or datetime.now(timezone.utc)
    delivery.status = "completed"
    delivery.completed_at = now

    exceptions_data = None
    has_exceptions = False

    if data.exceptions:
        exceptions_data = [e.model_dump() for e in data.exceptions]
        has_exceptions = True

    # Store exceptions on the linked sales order
    # Update the linked sales order with driver confirmation details
    if delivery.order_id:
        order = (
            db.query(SalesOrder)
            .filter(
                SalesOrder.id == delivery.order_id,
                SalesOrder.company_id == current_user.company_id,
            )
            .first()
        )
        if order:
            order.delivered_at = now
            order.delivery_auto_confirmed = False
            driver_name = getattr(current_user, "full_name", None) or current_user.email
            order.delivered_by_driver_name = driver_name
            if has_exceptions:
                order.driver_exceptions = exceptions_data
                order.has_driver_exception = True

    db.commit()
    db.refresh(delivery)

    # Trigger immediate-mode invoice hook (no-op for end_of_day / manual)
    try:
        from app.services.order_integration_service import on_delivery_completed
        on_delivery_completed(db, delivery)
    except Exception as exc:
        # Non-fatal — log and continue
        import logging
        logging.getLogger(__name__).error(
            "on_delivery_completed hook error for delivery %s: %s", delivery_id, exc
        )

    # Create real-time alert if exceptions were reported
    if has_exceptions:
        try:
            from app.models.customer import Customer
            from app.services.agent_service import create_alert

            customer_name = "Unknown"
            if delivery.customer_id:
                cust = db.query(Customer.name).filter(
                    Customer.id == delivery.customer_id
                ).first()
                if cust:
                    customer_name = cust[0]

            reason_list = ", ".join(
                e.get("reason", "issue") for e in (exceptions_data or [])
            )
            create_alert(
                db,
                current_user.company_id,
                alert_type="delivery_exception",
                severity="warning",
                title=f"Delivery exception — {customer_name} service today",
                message=(
                    f"Driver reported exception(s) for {customer_name}: {reason_list}. "
                    "This will be flagged on tonight's draft invoice for review."
                ),
                action_label="View draft invoices",
                action_url="/ar/invoices/review",
            )
        except Exception:
            pass

    return {
        "status": "completed",
        "delivery_id": delivery_id,
        "completed_at": now.isoformat(),
        "exceptions_recorded": len(exceptions_data) if exceptions_data else 0,
    }
