"""Direct Ship Orders — scheduling board panel API.

Direct ship orders go through the manufacturer for billing but are physically
shipped by Wilbert directly to the funeral home.  Status flow:
pending → ordered_from_wilbert → shipped → done.
"""

from datetime import date, datetime, timedelta, UTC

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_module
from app.database import get_db
from app.models.delivery import Delivery
from app.models.user import User

router = APIRouter(
    dependencies=[Depends(require_module("driver_delivery"))],
)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class MarkOrderedRequest(BaseModel):
    wilbert_order_number: str | None = None
    notes: str | None = None


class MarkShippedRequest(BaseModel):
    pass


class MarkDoneRequest(BaseModel):
    pass


class UpdateSchedulingTypeRequest(BaseModel):
    scheduling_type: str  # 'kanban' | 'ancillary' | 'direct_ship'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize_direct_ship_card(delivery: Delivery) -> dict:
    """Serialize a delivery into a direct ship panel card."""
    tc = delivery.type_config or {}
    return {
        "delivery_id": delivery.id,
        "delivery_type": delivery.delivery_type,
        "funeral_home_name": tc.get("funeral_home_name", ""),
        "product_summary": tc.get("product_summary", tc.get("vault_type", "")),
        "deceased_name": tc.get("family_name", tc.get("deceased_name", "")),
        "status": delivery.status,
        "direct_ship_status": delivery.direct_ship_status or "pending",
        "wilbert_order_number": delivery.wilbert_order_number,
        "direct_ship_notes": delivery.direct_ship_notes,
        "needed_by": delivery.requested_date.isoformat() if delivery.requested_date else None,
        "marked_shipped_at": delivery.marked_shipped_at.isoformat() if delivery.marked_shipped_at else None,
        "marked_shipped_by": delivery.marked_shipped_by,
        "completed_at": delivery.completed_at.isoformat() if delivery.completed_at else None,
        "special_instructions": delivery.special_instructions,
        "created_at": delivery.created_at.isoformat() if delivery.created_at else None,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/direct-ship")
def list_direct_ship_orders(
    include_completed: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all direct ship orders due within the next 7 days.

    Unlike Kanban/ancillary panels, this is not date-scoped to a single day.
    It always shows the 7-day lookahead window plus any overdue orders.
    """
    today = date.today()
    window_end = today + timedelta(days=7)

    filters = [
        Delivery.company_id == current_user.company_id,
        Delivery.scheduling_type == "direct_ship",
        Delivery.status != "cancelled",
    ]

    if not include_completed:
        filters.append(
            or_(
                Delivery.direct_ship_status != "done",
                Delivery.direct_ship_status.is_(None),
            )
        )

    # Include orders with needed_by within 7 days OR with no date set OR overdue
    filters.append(
        or_(
            Delivery.requested_date <= window_end,
            Delivery.requested_date.is_(None),
        )
    )

    deliveries = (
        db.query(Delivery)
        .filter(*filters)
        .order_by(Delivery.requested_date.asc().nulls_last(), Delivery.created_at)
        .all()
    )

    # Group by status
    needs_ordering = []
    ordered = []
    shipped = []
    completed = []

    for d in deliveries:
        card = _serialize_direct_ship_card(d)
        status = d.direct_ship_status or "pending"

        if status == "done":
            completed.append(card)
        elif status == "shipped":
            shipped.append(card)
        elif status == "ordered_from_wilbert":
            ordered.append(card)
        else:
            needs_ordering.append(card)

    return {
        "needs_ordering": needs_ordering,
        "ordered": ordered,
        "shipped": shipped,
        "completed": completed,
        "stats": {
            "total": len(deliveries),
            "needs_ordering": len(needs_ordering),
            "ordered": len(ordered),
            "shipped": len(shipped),
            "completed": len(completed),
            "unresolved": len(needs_ordering) + len(ordered) + len(shipped),
        },
    }


@router.post("/direct-ship/{delivery_id}/mark-ordered")
def mark_as_ordered(
    delivery_id: str,
    data: MarkOrderedRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a direct ship order as ordered from Wilbert."""
    delivery = db.query(Delivery).filter(
        Delivery.id == delivery_id,
        Delivery.company_id == current_user.company_id,
        Delivery.scheduling_type == "direct_ship",
    ).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Direct ship order not found")

    delivery.direct_ship_status = "ordered_from_wilbert"
    if data.wilbert_order_number:
        delivery.wilbert_order_number = data.wilbert_order_number
    if data.notes:
        delivery.direct_ship_notes = data.notes
    delivery.modified_at = datetime.now(UTC)
    db.commit()

    return {"status": "ordered_from_wilbert", "delivery_id": delivery_id}


@router.post("/direct-ship/{delivery_id}/mark-shipped")
def mark_as_shipped(
    delivery_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a direct ship order as shipped by Wilbert."""
    delivery = db.query(Delivery).filter(
        Delivery.id == delivery_id,
        Delivery.company_id == current_user.company_id,
        Delivery.scheduling_type == "direct_ship",
    ).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Direct ship order not found")

    now = datetime.now(UTC)
    delivery.direct_ship_status = "shipped"
    delivery.marked_shipped_at = now
    delivery.marked_shipped_by = current_user.id
    delivery.modified_at = now
    db.commit()

    return {"status": "shipped", "delivery_id": delivery_id}


@router.post("/direct-ship/{delivery_id}/mark-done")
def mark_as_done(
    delivery_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a direct ship order as complete."""
    delivery = db.query(Delivery).filter(
        Delivery.id == delivery_id,
        Delivery.company_id == current_user.company_id,
        Delivery.scheduling_type == "direct_ship",
    ).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Direct ship order not found")

    now = datetime.now(UTC)
    delivery.direct_ship_status = "done"
    delivery.status = "completed"
    delivery.completed_at = now
    delivery.modified_at = now
    db.commit()

    return {"status": "done", "delivery_id": delivery_id}
