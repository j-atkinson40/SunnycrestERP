"""Event-driven notification service for deliveries.

Handles customer SMS notifications, connected tenant alerts,
and carrier assignment SMS.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.delivery import Delivery
from app.models.tenant_notification import TenantNotification

logger = logging.getLogger(__name__)


def _send_sms(to_phone: str, body: str) -> bool:
    """Send SMS via Twilio. Returns True on success."""
    try:
        from app.config import settings

        if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
            logger.warning("Twilio not configured — skipping SMS to %s", to_phone)
            return False

        from twilio.rest import Client

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=body,
            from_=settings.TWILIO_FROM_NUMBER,
            to=to_phone,
        )
        return True
    except Exception as exc:
        logger.error("Failed to send SMS to %s: %s", to_phone, exc)
        return False


def _create_tenant_notification(
    db: Session,
    company_id: str,
    source_tenant_id: str | None,
    notification_type: str,
    title: str,
    message: str | None = None,
    data: dict | None = None,
) -> TenantNotification:
    notif = TenantNotification(
        id=str(uuid.uuid4()),
        company_id=company_id,
        source_tenant_id=source_tenant_id,
        notification_type=notification_type,
        title=title,
        message=message,
        data=data,
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


def on_driver_arrived(db: Session, delivery: Delivery) -> None:
    """Called when a driver arrives at a delivery stop."""
    from app.services.delivery_settings_service import get_settings

    settings = get_settings(db, delivery.company_id)

    # Notify customer
    if settings.notify_customer_on_arrival and delivery.customer:
        phone = getattr(delivery.customer, "phone", None)
        if phone:
            _send_sms(
                phone,
                f"Your delivery driver has arrived at {delivery.delivery_address or 'the delivery location'}.",
            )

    # Notify connected tenants
    if settings.notify_connected_tenant_on_arrival:
        _notify_connected_tenants(
            db,
            delivery,
            "driver_arrived",
            f"Driver arrived for delivery to {delivery.delivery_address or 'unknown'}",
        )


def on_setup_complete(db: Session, delivery: Delivery) -> None:
    """Called when setup is confirmed (critical for funeral vault)."""
    from app.services.delivery_settings_service import get_settings

    settings = get_settings(db, delivery.company_id)

    if settings.notify_connected_tenant_on_setup:
        _notify_connected_tenants(
            db,
            delivery,
            "setup_complete",
            f"Setup complete for delivery at {delivery.delivery_address or 'unknown'}",
        )


def on_driver_departed(db: Session, delivery: Delivery) -> None:
    """Called when driver departs from a stop."""
    pass  # Placeholder for future dispatch-board real-time updates


def on_delivery_complete(db: Session, delivery: Delivery) -> None:
    """Called when a delivery is marked completed."""
    from app.services.delivery_settings_service import get_settings

    settings = get_settings(db, delivery.company_id)

    delivery.status = "completed"
    delivery.completed_at = datetime.now(timezone.utc)
    delivery.modified_at = datetime.now(timezone.utc)
    db.commit()

    # Notify customer
    if settings.notify_customer_on_complete and delivery.customer:
        phone = getattr(delivery.customer, "phone", None)
        if phone:
            _send_sms(phone, "Your delivery has been completed. Thank you!")

    # Auto-invoice if the delivery is linked to a sales order
    try:
        from app.services import order_integration_service

        order_integration_service.on_delivery_completed(db, delivery)
    except Exception as exc:
        logger.error("Auto-invoice hook failed for delivery %s: %s", delivery.id, exc)


def on_carrier_assigned(db: Session, delivery: Delivery) -> None:
    """Called when a delivery is assigned to a third-party carrier.

    If sms_carrier_updates is enabled and the carrier has a phone number,
    sends an SMS with delivery details and keyword reply instructions.
    """
    from app.services.delivery_settings_service import get_settings

    settings = get_settings(db, delivery.company_id)

    if not settings.sms_carrier_updates:
        return
    if not delivery.carrier:
        return
    phone = delivery.carrier.contact_phone
    if not phone:
        return

    customer_name = "N/A"
    if delivery.customer:
        customer_name = getattr(delivery.customer, "name", None) or getattr(
            delivery.customer, "company_name", "N/A"
        )

    from app.config import settings as app_settings

    company_name = delivery.company.name if delivery.company else app_settings.APP_NAME

    body = (
        f"You have a delivery scheduled. "
        f"Customer: {customer_name}. "
        f"Address: {delivery.delivery_address or 'TBD'}. "
        f"Date: {delivery.requested_date or 'TBD'}. "
        f"Reply PICKED when loaded, DELIVERED when complete, ISSUE if problem. "
        f"{company_name}"
    )
    _send_sms(phone, body)


def _notify_connected_tenants(
    db: Session,
    delivery: Delivery,
    notification_type: str,
    message: str,
) -> None:
    """Send in-app notification to connected tenants."""
    from app.models.network_relationship import NetworkRelationship

    relationships = (
        db.query(NetworkRelationship)
        .filter(
            NetworkRelationship.status == "active",
            (
                (NetworkRelationship.requester_id == delivery.company_id)
                | (NetworkRelationship.responder_id == delivery.company_id)
            ),
        )
        .all()
    )

    for rel in relationships:
        target_id = (
            rel.responder_id
            if rel.requester_id == delivery.company_id
            else rel.requester_id
        )
        _create_tenant_notification(
            db,
            company_id=target_id,
            source_tenant_id=delivery.company_id,
            notification_type=notification_type,
            title=f"Delivery Update: {notification_type.replace('_', ' ').title()}",
            message=message,
            data={
                "delivery_id": delivery.id,
                "delivery_type": delivery.delivery_type,
                "address": delivery.delivery_address,
            },
        )
