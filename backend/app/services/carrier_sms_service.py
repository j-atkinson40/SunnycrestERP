"""Inbound SMS processing for third-party carrier status updates.

Handles Twilio webhook payloads: matches carrier by phone, finds most
recent pending delivery, and processes keyword commands.

Keywords:
  PICKED    → marks delivery as in_transit
  DELIVERED → marks delivery as completed
  ISSUE     → creates issue event, notifies dispatch
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.carrier import Carrier
from app.models.delivery import Delivery
from app.models.delivery_event import DeliveryEvent
from app.models.tenant_notification import TenantNotification

logger = logging.getLogger(__name__)

_HELP_TEXT = (
    "Reply with one of: PICKED (when loaded), DELIVERED (when complete), "
    "ISSUE (if there is a problem)."
)


def _normalise_phone(phone: str) -> str:
    """Strip non-digit characters for comparison."""
    return "".join(c for c in phone if c.isdigit())


def _find_carrier_by_phone(db: Session, from_phone: str) -> Carrier | None:
    """Match a carrier by contact_phone (fuzzy on digits)."""
    normalised = _normalise_phone(from_phone)
    carriers = (
        db.query(Carrier)
        .filter(Carrier.active.is_(True), Carrier.carrier_type == "third_party")
        .all()
    )
    for c in carriers:
        if c.contact_phone and _normalise_phone(c.contact_phone) == normalised:
            return c
    return None


def _find_pending_delivery(db: Session, carrier: Carrier) -> Delivery | None:
    """Find the most recent non-completed delivery for this carrier."""
    return (
        db.query(Delivery)
        .filter(
            Delivery.carrier_id == carrier.id,
            Delivery.company_id == carrier.company_id,
            Delivery.status.notin_(["completed", "cancelled", "failed"]),
        )
        .order_by(Delivery.created_at.desc())
        .first()
    )


def _create_event(
    db: Session,
    delivery: Delivery,
    event_type: str,
    notes: str | None = None,
) -> DeliveryEvent:
    event = DeliveryEvent(
        id=str(uuid.uuid4()),
        company_id=delivery.company_id,
        delivery_id=delivery.id,
        event_type=event_type,
        source="carrier_sms",
        notes=notes,
    )
    db.add(event)
    return event


def process_inbound_sms(db: Session, from_phone: str, body: str) -> str:
    """Process an inbound SMS from a carrier.

    Returns the reply message to send back.
    """
    carrier = _find_carrier_by_phone(db, from_phone)
    if not carrier:
        logger.warning("Inbound SMS from unknown phone: %s", from_phone)
        return "Unknown sender. Contact dispatch for assistance."

    delivery = _find_pending_delivery(db, carrier)
    if not delivery:
        return "No pending delivery found for your carrier. Contact dispatch."

    keyword = body.strip().upper().split()[0] if body.strip() else ""
    now = datetime.now(timezone.utc)

    if keyword == "PICKED":
        delivery.status = "in_transit"
        delivery.modified_at = now
        _create_event(db, delivery, "picked_up", notes="Carrier confirmed pickup via SMS")
        db.commit()
        return "Confirmed: delivery marked as in transit. Reply DELIVERED when complete."

    elif keyword == "DELIVERED":
        delivery.status = "completed"
        delivery.completed_at = now
        delivery.modified_at = now
        _create_event(db, delivery, "completed", notes="Carrier confirmed delivery via SMS")
        db.commit()
        return "Confirmed: delivery marked as completed. Thank you!"

    elif keyword == "ISSUE":
        _create_event(
            db,
            delivery,
            "issue",
            notes=f"Carrier reported issue via SMS: {body.strip()}",
        )
        # Notify dispatch
        notif = TenantNotification(
            id=str(uuid.uuid4()),
            company_id=delivery.company_id,
            source_tenant_id=None,
            notification_type="carrier_issue",
            title=f"Carrier Issue: {carrier.name}",
            message=f"Carrier {carrier.name} reported an issue for delivery {delivery.id}: {body.strip()}",
            data={
                "delivery_id": delivery.id,
                "carrier_id": carrier.id,
                "carrier_name": carrier.name,
                "sms_body": body.strip(),
            },
        )
        db.add(notif)
        db.commit()
        return "Issue reported. Dispatch has been notified and will contact you shortly."

    else:
        return _HELP_TEXT
