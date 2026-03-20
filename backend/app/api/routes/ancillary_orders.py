"""Ancillary Orders — scheduling board side-panel API.

Ancillary orders are funeral-service-related orders that don't involve a
cemetery burial (drop-offs, pickups, supply deliveries).  They appear on the
scheduling board for dispatcher context but are *not* in the Kanban driver
lanes.
"""

from datetime import date, datetime, UTC
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_module
from app.database import get_db
from app.models.delivery import Delivery
from app.models.driver import Driver
from app.models.user import User

router = APIRouter(
    dependencies=[Depends(require_module("driver_delivery"))],
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ANCILLARY_ORDER_TYPES = frozenset({
    "funeral_home_dropoff",
    "funeral_home_pickup",
    "supply_delivery",
})

ORDER_TYPE_LABELS = {
    "funeral_home_dropoff": "Drop-off",
    "funeral_home_pickup": "Pickup",
    "supply_delivery": "Supply",
}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class AssignDriverRequest(BaseModel):
    driver_id: str


class MarkPickupRequest(BaseModel):
    expected_by: datetime | None = None
    contact: str | None = None
    notify_funeral_home: bool = False


class ConfirmPickupRequest(BaseModel):
    confirmed_by: str | None = None


class UpdateSchedulingTypeRequest(BaseModel):
    scheduling_type: str  # 'kanban' | 'ancillary'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize_ancillary_card(delivery: Delivery) -> dict:
    """Serialize a delivery into an ancillary panel card."""
    tc = delivery.type_config or {}
    return {
        "delivery_id": delivery.id,
        "delivery_type": delivery.delivery_type,
        "order_type_label": ORDER_TYPE_LABELS.get(delivery.delivery_type, delivery.delivery_type),
        "funeral_home_name": tc.get("funeral_home_name", ""),
        "product_summary": tc.get("product_summary", tc.get("vault_type", "")),
        "deceased_name": tc.get("family_name", tc.get("deceased_name", "")),
        "status": delivery.status,
        "ancillary_fulfillment_status": delivery.ancillary_fulfillment_status or "unassigned",
        "assigned_driver_id": delivery.assigned_driver_id,
        "pickup_expected_by": delivery.pickup_expected_by.isoformat() if delivery.pickup_expected_by else None,
        "pickup_confirmed_at": delivery.pickup_confirmed_at.isoformat() if delivery.pickup_confirmed_at else None,
        "pickup_confirmed_by": delivery.pickup_confirmed_by,
        "requested_date": delivery.requested_date.isoformat() if delivery.requested_date else None,
        "completed_at": delivery.completed_at.isoformat() if delivery.completed_at else None,
        "special_instructions": delivery.special_instructions,
        "created_at": delivery.created_at.isoformat() if delivery.created_at else None,
    }


def _classify_scheduling_type(delivery_type: str, type_config: dict | None) -> str:
    """Auto-classify an order as kanban or ancillary based on its type/config."""
    if delivery_type in ANCILLARY_ORDER_TYPES:
        return "ancillary"
    tc = type_config or {}
    # If funeral_vault but no cemetery → ancillary
    if delivery_type == "funeral_vault":
        has_cemetery = bool(tc.get("cemetery_name", "").strip())
        is_customer_pickup = bool(tc.get("customer_pickup", False))
        if not has_cemetery or is_customer_pickup:
            return "ancillary"
    return "kanban"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/ancillary")
def list_ancillary_orders(
    order_date: date = Query(..., alias="date"),
    include_completed: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all ancillary orders for a specific date.

    Returns orders grouped by fulfillment status with driver info for
    assigned orders.
    """
    filters = [
        Delivery.company_id == current_user.company_id,
        Delivery.scheduling_type == "ancillary",
        Delivery.requested_date == order_date,
        Delivery.status != "cancelled",
    ]

    if not include_completed:
        filters.append(
            or_(
                Delivery.ancillary_fulfillment_status != "completed",
                Delivery.ancillary_fulfillment_status.is_(None),
            )
        )

    deliveries = (
        db.query(Delivery)
        .filter(*filters)
        .order_by(Delivery.created_at)
        .all()
    )

    # Build cards grouped by status
    needs_action = []
    awaiting_pickup = []
    assigned_to_driver: dict[str, list] = {}
    completed = []

    for d in deliveries:
        card = _serialize_ancillary_card(d)
        status = d.ancillary_fulfillment_status or "unassigned"

        if status == "completed":
            completed.append(card)
        elif status == "awaiting_pickup":
            awaiting_pickup.append(card)
        elif status == "assigned_to_driver":
            driver_id = d.assigned_driver_id or "unknown"
            if driver_id not in assigned_to_driver:
                assigned_to_driver[driver_id] = []
            assigned_to_driver[driver_id].append(card)
        else:
            needs_action.append(card)

    # Resolve driver names for the assigned group
    driver_ids = list(assigned_to_driver.keys())
    driver_names: dict[str, str] = {}
    if driver_ids:
        drivers = (
            db.query(Driver)
            .filter(Driver.id.in_(driver_ids))
            .all()
        )
        for drv in drivers:
            name = f"Driver {drv.id[:8]}"
            if drv.employee:
                name = f"{drv.employee.first_name} {drv.employee.last_name}"
            driver_names[drv.id] = name

    assigned_groups = []
    for driver_id, cards in assigned_to_driver.items():
        assigned_groups.append({
            "driver_id": driver_id,
            "driver_name": driver_names.get(driver_id, f"Driver {driver_id[:8]}"),
            "items": cards,
            "item_count": len(cards),
        })
    assigned_groups.sort(key=lambda g: g["driver_name"])

    # Get available drivers for "Assign to Driver" dropdown
    active_drivers = (
        db.query(Driver)
        .filter(
            Driver.company_id == current_user.company_id,
            Driver.active.is_(True),
        )
        .all()
    )
    available_drivers = []
    for drv in active_drivers:
        name = f"Driver {drv.id[:8]}"
        if drv.employee:
            name = f"{drv.employee.first_name} {drv.employee.last_name}"
        available_drivers.append({"driver_id": drv.id, "name": name})
    available_drivers.sort(key=lambda d: d["name"])

    total_unresolved = len(needs_action) + len(awaiting_pickup) + sum(
        len(g["items"]) for g in assigned_groups
    )

    return {
        "date": order_date.isoformat(),
        "needs_action": needs_action,
        "awaiting_pickup": awaiting_pickup,
        "assigned_groups": assigned_groups,
        "completed": completed,
        "available_drivers": available_drivers,
        "stats": {
            "total": len(deliveries),
            "needs_action": len(needs_action),
            "awaiting_pickup": len(awaiting_pickup),
            "assigned": sum(len(g["items"]) for g in assigned_groups),
            "completed": len(completed),
            "unresolved": total_unresolved,
        },
    }


@router.post("/ancillary/{delivery_id}/assign")
def assign_ancillary_to_driver(
    delivery_id: str,
    data: AssignDriverRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Assign an ancillary order to a driver."""
    delivery = db.query(Delivery).filter(
        Delivery.id == delivery_id,
        Delivery.company_id == current_user.company_id,
        Delivery.scheduling_type == "ancillary",
    ).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Ancillary order not found")

    driver = db.query(Driver).filter(
        Driver.id == data.driver_id,
        Driver.company_id == current_user.company_id,
    ).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    delivery.ancillary_fulfillment_status = "assigned_to_driver"
    delivery.assigned_driver_id = data.driver_id
    delivery.modified_at = datetime.now(UTC)
    db.commit()

    return {"status": "assigned", "delivery_id": delivery_id, "driver_id": data.driver_id}


@router.post("/ancillary/{delivery_id}/mark-pickup")
def mark_as_pickup(
    delivery_id: str,
    data: MarkPickupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark an ancillary order as awaiting funeral home pickup."""
    delivery = db.query(Delivery).filter(
        Delivery.id == delivery_id,
        Delivery.company_id == current_user.company_id,
        Delivery.scheduling_type == "ancillary",
    ).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Ancillary order not found")

    delivery.ancillary_fulfillment_status = "awaiting_pickup"
    delivery.pickup_expected_by = data.expected_by
    if data.contact:
        delivery.pickup_confirmed_by = data.contact
    delivery.modified_at = datetime.now(UTC)
    db.commit()

    # TODO: If data.notify_funeral_home and tenant has delivery_notifications_enabled
    # and funeral home is a connected tenant, send notification

    return {"status": "awaiting_pickup", "delivery_id": delivery_id}


@router.post("/ancillary/{delivery_id}/confirm-pickup")
def confirm_pickup(
    delivery_id: str,
    data: ConfirmPickupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Confirm that the funeral home has picked up their order."""
    delivery = db.query(Delivery).filter(
        Delivery.id == delivery_id,
        Delivery.company_id == current_user.company_id,
        Delivery.scheduling_type == "ancillary",
    ).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Ancillary order not found")

    now = datetime.now(UTC)
    delivery.ancillary_fulfillment_status = "completed"
    delivery.pickup_confirmed_at = now
    delivery.pickup_confirmed_by = data.confirmed_by or f"{current_user.first_name} {current_user.last_name}"
    delivery.status = "completed"
    delivery.completed_at = now
    delivery.modified_at = now
    db.commit()

    return {"status": "completed", "delivery_id": delivery_id}


@router.post("/ancillary/{delivery_id}/confirm-delivered")
def confirm_delivered(
    delivery_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Confirm an assigned ancillary order has been delivered (dispatcher or driver)."""
    delivery = db.query(Delivery).filter(
        Delivery.id == delivery_id,
        Delivery.company_id == current_user.company_id,
        Delivery.scheduling_type == "ancillary",
    ).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Ancillary order not found")

    now = datetime.now(UTC)
    delivery.ancillary_fulfillment_status = "completed"
    delivery.status = "completed"
    delivery.completed_at = now
    delivery.modified_at = now
    db.commit()

    return {"status": "completed", "delivery_id": delivery_id}


@router.patch("/ancillary/{delivery_id}/scheduling-type")
def update_scheduling_type(
    delivery_id: str,
    data: UpdateSchedulingTypeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toggle a delivery between kanban and ancillary scheduling."""
    if data.scheduling_type not in ("kanban", "ancillary"):
        raise HTTPException(status_code=400, detail="scheduling_type must be 'kanban' or 'ancillary'")

    delivery = db.query(Delivery).filter(
        Delivery.id == delivery_id,
        Delivery.company_id == current_user.company_id,
    ).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    delivery.scheduling_type = data.scheduling_type
    if data.scheduling_type == "ancillary" and not delivery.ancillary_fulfillment_status:
        delivery.ancillary_fulfillment_status = "unassigned"
    elif data.scheduling_type == "kanban":
        delivery.ancillary_fulfillment_status = None
        delivery.assigned_driver_id = None
    delivery.modified_at = datetime.now(UTC)
    db.commit()

    return {"status": "updated", "delivery_id": delivery_id, "scheduling_type": data.scheduling_type}


@router.post("/ancillary/{delivery_id}/reassign")
def reassign_ancillary(
    delivery_id: str,
    data: AssignDriverRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reassign an ancillary order to a different driver."""
    # Reuse assign logic
    return assign_ancillary_to_driver(delivery_id, data, db, current_user)
