"""Ancillary Orders — scheduling board side-panel API (v2).

Ancillary orders are funeral-service-related orders that don't involve a
cemetery burial (drop-offs, pickups, supply deliveries).  They appear on the
scheduling board for dispatcher context but are *not* in the Kanban driver
lanes.

V2 changes:
- Rolling 3-day window for scheduled orders
- Floating orders queue (no hard date)
- Atomic floating-to-scheduled conversion
- Day sub-sections within status groups
"""

from datetime import date, datetime, timedelta, UTC
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
    scheduling_type: str  # 'kanban' | 'ancillary' | 'direct_ship'


class MoveToDateRequest(BaseModel):
    new_date: date


class AssignFloatingRequest(BaseModel):
    """Atomic floating-to-scheduled conversion."""
    driver_id: str
    delivery_date: date


class FloatingMarkPickupRequest(BaseModel):
    """Mark a floating order as awaiting pickup — requires choosing a date."""
    delivery_date: date
    expected_by: datetime | None = None
    contact: str | None = None


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
        "ancillary_is_floating": bool(delivery.ancillary_is_floating),
        "ancillary_soft_target_date": delivery.ancillary_soft_target_date.isoformat() if delivery.ancillary_soft_target_date else None,
        # Phase 4.3.2 (r56) — renamed from assigned_driver_id; value
        # is now users.id (was drivers.id). Frontend consumers compare
        # against DriverDTO.user_id (=drivers.employee_id), not
        # DriverDTO.id.
        "primary_assignee_id": delivery.primary_assignee_id,
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


def _get_available_drivers(db: Session, company_id: str) -> list[dict]:
    """Get active drivers for assignment dropdowns."""
    active_drivers = (
        db.query(Driver)
        .filter(
            Driver.company_id == company_id,
            Driver.active.is_(True),
        )
        .all()
    )
    result = []
    for drv in active_drivers:
        name = f"Driver {drv.id[:8]}"
        if drv.employee:
            name = f"{drv.employee.first_name} {drv.employee.last_name}"
        result.append({"driver_id": drv.id, "name": name})
    result.sort(key=lambda d: d["name"])
    return result


def _resolve_driver_names(db: Session, user_ids: list[str]) -> dict[str, str]:
    """Resolve a list of user IDs to display names.

    Phase 4.3.2 (r56) — now keyed on users.id. Pre-rename, this
    resolved drivers.id via the Driver.employee relationship. Post-
    rename, deliveries.primary_assignee_id directly stores users.id,
    so we query User.first_name + User.last_name.
    """
    if not user_ids:
        return {}
    from app.models.user import User as _User

    users = db.query(_User).filter(_User.id.in_(user_ids)).all()
    names: dict[str, str] = {}
    for u in users:
        name = f"{u.first_name or ''} {u.last_name or ''}".strip()
        if not name:
            name = u.email or f"User {u.id[:8]}"
        names[u.id] = name
    return names


def _group_by_date(cards: list[dict], dates: list[date]) -> list[dict]:
    """Group cards into day sub-sections ordered by the 3-day window dates."""
    date_strs = [d.isoformat() for d in dates]
    groups = []
    for ds in date_strs:
        day_cards = [c for c in cards if c.get("requested_date") == ds]
        if day_cards:
            groups.append({"date": ds, "cards": day_cards})
    return groups


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/ancillary")
def list_ancillary_orders(
    anchor_date: date = Query(..., alias="date"),
    day1: date | None = Query(None),
    day2: date | None = Query(None),
    day3: date | None = Query(None),
    include_completed: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get ancillary orders for the 3-day window + all floating orders.

    The frontend passes the 3 delivery dates (day1, day2, day3) computed from
    getNextDeliveryDay().  Falls back to anchor_date + next 2 days if not provided.
    """
    # Build the 3-day window dates
    if day1 and day2 and day3:
        window_dates = [day1, day2, day3]
    else:
        window_dates = [
            anchor_date,
            anchor_date + timedelta(days=1),
            anchor_date + timedelta(days=2),
        ]

    # --- Scheduled orders (within 3-day window) ---
    scheduled_filters = [
        Delivery.company_id == current_user.company_id,
        Delivery.scheduling_type == "ancillary",
        or_(Delivery.ancillary_is_floating.is_(False), Delivery.ancillary_is_floating.is_(None)),
        Delivery.requested_date.in_(window_dates),
        Delivery.status != "cancelled",
    ]

    if not include_completed:
        scheduled_filters.append(
            or_(
                Delivery.ancillary_fulfillment_status != "completed",
                Delivery.ancillary_fulfillment_status.is_(None),
            )
        )

    scheduled_deliveries = (
        db.query(Delivery)
        .filter(*scheduled_filters)
        .order_by(Delivery.requested_date, Delivery.created_at)
        .all()
    )

    # --- Floating orders (all unresolved, not date-scoped) ---
    floating_filters = [
        Delivery.company_id == current_user.company_id,
        Delivery.scheduling_type == "ancillary",
        Delivery.ancillary_is_floating.is_(True),
        Delivery.status != "cancelled",
    ]

    if not include_completed:
        floating_filters.append(
            or_(
                Delivery.ancillary_fulfillment_status != "completed",
                Delivery.ancillary_fulfillment_status.is_(None),
            )
        )

    floating_deliveries = (
        db.query(Delivery)
        .filter(*floating_filters)
        .order_by(Delivery.ancillary_soft_target_date.asc().nullslast(), Delivery.created_at)
        .all()
    )

    # Classify scheduled into status groups with day sub-sections
    needs_action: list[dict] = []
    awaiting_pickup: list[dict] = []
    assigned_items: list[dict] = []
    completed: list[dict] = []

    for d in scheduled_deliveries:
        card = _serialize_ancillary_card(d)
        status = d.ancillary_fulfillment_status or "unassigned"
        if status == "completed":
            completed.append(card)
        elif status == "awaiting_pickup":
            awaiting_pickup.append(card)
        elif status == "assigned_to_driver":
            assigned_items.append(card)
        else:
            needs_action.append(card)

    # Group each status by date
    needs_action_by_day = _group_by_date(needs_action, window_dates)
    awaiting_pickup_by_day = _group_by_date(awaiting_pickup, window_dates)

    # Assigned — group by driver, then by date within each driver
    assigned_by_driver: dict[str, list[dict]] = {}
    for card in assigned_items:
        # Phase 4.3.2 — value now a users.id (was drivers.id). The
        # grouping key is the assignee identity; driver_names below
        # resolves via users.id directly.
        driver_id = card.get("primary_assignee_id") or "unknown"
        if driver_id not in assigned_by_driver:
            assigned_by_driver[driver_id] = []
        assigned_by_driver[driver_id].append(card)

    driver_ids = list(assigned_by_driver.keys())
    driver_names = _resolve_driver_names(db, driver_ids)

    assigned_groups = []
    for driver_id, cards in assigned_by_driver.items():
        by_day = _group_by_date(cards, window_dates)
        assigned_groups.append({
            "driver_id": driver_id,
            "driver_name": driver_names.get(driver_id, f"Driver {driver_id[:8]}"),
            "items": cards,
            "items_by_day": by_day,
            "item_count": len(cards),
        })
    assigned_groups.sort(key=lambda g: g["driver_name"])

    # Serialize floating
    floating_cards = [_serialize_ancillary_card(d) for d in floating_deliveries]
    floating_completed = [c for c in floating_cards if c["ancillary_fulfillment_status"] == "completed"]
    floating_unresolved = [c for c in floating_cards if c["ancillary_fulfillment_status"] != "completed"]

    # Stats
    total_scheduled = len(scheduled_deliveries)
    total_floating = len(floating_deliveries)
    scheduled_unresolved = len(needs_action) + len(awaiting_pickup) + len(assigned_items)
    floating_unresolved_count = len(floating_unresolved)

    available_drivers = _get_available_drivers(db, current_user.company_id)

    return {
        "anchor_date": anchor_date.isoformat(),
        "window_dates": [d.isoformat() for d in window_dates],
        # Scheduled groups with day sub-sections
        "needs_action": needs_action,
        "needs_action_by_day": needs_action_by_day,
        "awaiting_pickup": awaiting_pickup,
        "awaiting_pickup_by_day": awaiting_pickup_by_day,
        "assigned_groups": assigned_groups,
        "completed": completed,
        # Floating orders
        "floating": floating_unresolved,
        "floating_completed": floating_completed,
        # Drivers
        "available_drivers": available_drivers,
        # Stats
        "stats": {
            "total": total_scheduled + total_floating,
            "scheduled_total": total_scheduled,
            "floating_total": total_floating,
            "needs_action": len(needs_action),
            "awaiting_pickup": len(awaiting_pickup),
            "assigned": len(assigned_items),
            "completed": len(completed) + len(floating_completed),
            "unresolved": scheduled_unresolved + floating_unresolved_count,
            "floating_unresolved": floating_unresolved_count,
        },
    }


@router.post("/ancillary/{delivery_id}/assign")
def assign_ancillary_to_driver(
    delivery_id: str,
    data: AssignDriverRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Assign a scheduled ancillary order to a driver."""
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

    # Phase 4.3.2 — translate drivers.id → users.id via employee_id.
    # Portal-only drivers (employee_id=None) return 400; kanban-side
    # portal-driver assignment is a post-September follow-up.
    if driver.employee_id is None:
        raise HTTPException(
            status_code=400,
            detail="Driver has no linked user account (portal-only driver).",
        )

    delivery.ancillary_fulfillment_status = "assigned_to_driver"
    delivery.primary_assignee_id = driver.employee_id
    delivery.modified_at = datetime.now(UTC)
    db.commit()

    return {"status": "assigned", "delivery_id": delivery_id, "driver_id": data.driver_id}


@router.post("/ancillary/{delivery_id}/assign-floating")
def assign_floating_order(
    delivery_id: str,
    data: AssignFloatingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Atomic floating-to-scheduled conversion.

    Sets delivery_date, primary_assignee_id, ancillary_is_floating=false,
    and ancillary_fulfillment_status='assigned_to_driver' in one transaction.
    """
    delivery = db.query(Delivery).filter(
        Delivery.id == delivery_id,
        Delivery.company_id == current_user.company_id,
        Delivery.scheduling_type == "ancillary",
        Delivery.ancillary_is_floating.is_(True),
    ).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Floating ancillary order not found")

    driver = db.query(Driver).filter(
        Driver.id == data.driver_id,
        Driver.company_id == current_user.company_id,
    ).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    if driver.employee_id is None:
        raise HTTPException(
            status_code=400,
            detail="Driver has no linked user account (portal-only driver).",
        )

    # Atomic update. primary_assignee_id is users.id, not drivers.id.
    delivery.requested_date = data.delivery_date
    delivery.primary_assignee_id = driver.employee_id
    delivery.ancillary_is_floating = False
    delivery.ancillary_fulfillment_status = "assigned_to_driver"
    delivery.ancillary_soft_target_date = None
    delivery.modified_at = datetime.now(UTC)
    db.commit()

    return {
        "status": "assigned",
        "delivery_id": delivery_id,
        "driver_id": data.driver_id,
        "delivery_date": data.delivery_date.isoformat(),
    }


@router.post("/ancillary/{delivery_id}/floating-mark-pickup")
def floating_mark_pickup(
    delivery_id: str,
    data: FloatingMarkPickupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a floating order as awaiting pickup — converts to scheduled with a date."""
    delivery = db.query(Delivery).filter(
        Delivery.id == delivery_id,
        Delivery.company_id == current_user.company_id,
        Delivery.scheduling_type == "ancillary",
        Delivery.ancillary_is_floating.is_(True),
    ).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Floating ancillary order not found")

    delivery.requested_date = data.delivery_date
    delivery.ancillary_is_floating = False
    delivery.ancillary_fulfillment_status = "awaiting_pickup"
    delivery.pickup_expected_by = data.expected_by
    if data.contact:
        delivery.pickup_confirmed_by = data.contact
    delivery.ancillary_soft_target_date = None
    delivery.modified_at = datetime.now(UTC)
    db.commit()

    return {"status": "awaiting_pickup", "delivery_id": delivery_id, "delivery_date": data.delivery_date.isoformat()}


@router.post("/ancillary/{delivery_id}/mark-pickup")
def mark_as_pickup(
    delivery_id: str,
    data: MarkPickupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a scheduled ancillary order as awaiting funeral home pickup."""
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
    """Confirm an assigned ancillary order has been delivered."""
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


@router.post("/ancillary/{delivery_id}/move")
def move_to_date(
    delivery_id: str,
    data: MoveToDateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Move a scheduled ancillary order to a different date within the window."""
    delivery = db.query(Delivery).filter(
        Delivery.id == delivery_id,
        Delivery.company_id == current_user.company_id,
        Delivery.scheduling_type == "ancillary",
    ).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Ancillary order not found")

    delivery.requested_date = data.new_date
    delivery.modified_at = datetime.now(UTC)
    db.commit()

    return {"status": "moved", "delivery_id": delivery_id, "new_date": data.new_date.isoformat()}


@router.patch("/ancillary/{delivery_id}/scheduling-type")
def update_scheduling_type(
    delivery_id: str,
    data: UpdateSchedulingTypeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toggle a delivery between kanban, ancillary, and direct_ship scheduling."""
    if data.scheduling_type not in ("kanban", "ancillary", "direct_ship"):
        raise HTTPException(status_code=400, detail="scheduling_type must be 'kanban', 'ancillary', or 'direct_ship'")

    delivery = db.query(Delivery).filter(
        Delivery.id == delivery_id,
        Delivery.company_id == current_user.company_id,
    ).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    delivery.scheduling_type = data.scheduling_type
    if data.scheduling_type == "ancillary" and not delivery.ancillary_fulfillment_status:
        delivery.ancillary_fulfillment_status = "unassigned"
    elif data.scheduling_type == "direct_ship":
        delivery.ancillary_fulfillment_status = None
        delivery.primary_assignee_id = None
        delivery.ancillary_is_floating = False
        delivery.ancillary_soft_target_date = None
        if not delivery.direct_ship_status:
            delivery.direct_ship_status = "pending"
    elif data.scheduling_type == "kanban":
        delivery.ancillary_fulfillment_status = None
        delivery.primary_assignee_id = None
        delivery.ancillary_is_floating = False
        delivery.ancillary_soft_target_date = None
        delivery.direct_ship_status = None
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
    return assign_ancillary_to_driver(delivery_id, data, db, current_user)
