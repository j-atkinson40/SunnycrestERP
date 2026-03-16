"""Carrier portal — simplified interface for external carriers.

Feature-flagged behind `carrier_portal`. In a full implementation,
the `external_carrier` role would scope access to only deliveries
assigned to their carrier_id. For now, we use standard auth +
carrier_id scoping.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_feature, require_module
from app.database import get_db
from app.models.delivery import Delivery
from app.models.user import User
from app.services import delivery_service

router = APIRouter()

MODULE = "driver_delivery"
FLAG = "carrier_portal"


class CarrierStatusUpdate(BaseModel):
    status: str  # picked_up, in_transit, delivered, issue
    notes: str | None = None


@router.get("/deliveries")
def list_carrier_deliveries(
    carrier_id: str = Query(..., description="The carrier's ID"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_feature(FLAG)),
):
    """List deliveries assigned to a specific carrier."""
    items, total = delivery_service.list_deliveries(
        db, current_user.company_id,
        carrier_id=carrier_id,
        page=page, per_page=per_page,
    )
    result = []
    for d in items:
        result.append({
            "id": d.id,
            "delivery_type": d.delivery_type,
            "delivery_address": d.delivery_address,
            "requested_date": str(d.requested_date) if d.requested_date else None,
            "status": d.status,
            "priority": d.priority,
            "customer_name": (
                getattr(d.customer, "name", None) or getattr(d.customer, "company_name", None)
            ) if d.customer else None,
            "special_instructions": d.special_instructions,
        })
    return {"items": result, "total": total, "page": page, "per_page": per_page}


@router.patch("/deliveries/{delivery_id}/status")
def update_carrier_delivery_status(
    delivery_id: str,
    data: CarrierStatusUpdate,
    carrier_id: str = Query(..., description="The carrier's ID"),
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_feature(FLAG)),
):
    """Update delivery status from the carrier portal."""
    allowed_statuses = {"picked_up", "in_transit", "delivered", "issue"}
    if data.status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Status must be one of: {', '.join(sorted(allowed_statuses))}",
        )

    delivery = delivery_service.get_delivery(db, delivery_id, current_user.company_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    if delivery.carrier_id != carrier_id:
        raise HTTPException(status_code=403, detail="Delivery not assigned to this carrier")

    # Map portal status to internal status
    status_map = {
        "picked_up": "in_transit",
        "in_transit": "in_transit",
        "delivered": "completed",
        "issue": delivery.status,  # keep current status, log event
    }
    new_status = status_map[data.status]
    if new_status != delivery.status:
        delivery_service.update_delivery(db, delivery, {"status": new_status})

    delivery_service.create_event(
        db,
        current_user.company_id,
        {
            "delivery_id": delivery_id,
            "event_type": data.status,
            "source": "carrier_portal",
            "notes": data.notes,
        },
    )
    return {"status": "ok", "new_status": new_status}
