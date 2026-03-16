"""Customer-facing delivery portal — feature-flagged."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_feature, require_module
from app.database import get_db
from app.models.user import User
from app.schemas.delivery import DeliveryResponse, EventResponse
from app.services import delivery_service

router = APIRouter()

MODULE = "driver_delivery"
FLAG = "delivery_portal"


@router.get("/deliveries/{delivery_id}/status")
def get_delivery_status(
    delivery_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module(MODULE)),
    current_user: User = Depends(require_feature(FLAG)),
):
    delivery = delivery_service.get_delivery(db, delivery_id, current_user.company_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    events = delivery_service.list_events(db, delivery_id, current_user.company_id)
    return {
        "delivery_id": delivery.id,
        "status": delivery.status,
        "delivery_type": delivery.delivery_type,
        "delivery_address": delivery.delivery_address,
        "requested_date": str(delivery.requested_date) if delivery.requested_date else None,
        "scheduled_at": delivery.scheduled_at.isoformat() if delivery.scheduled_at else None,
        "completed_at": delivery.completed_at.isoformat() if delivery.completed_at else None,
        "events": [
            {
                "event_type": e.event_type,
                "created_at": e.created_at.isoformat(),
                "notes": e.notes,
            }
            for e in events
        ],
    }
