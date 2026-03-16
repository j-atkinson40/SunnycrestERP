"""Order ↔ Delivery integration hooks.

Auto-create a delivery when a sales order is confirmed.
Auto-invoice when a delivery is completed.

Both hooks are gated by per-tenant delivery settings:
  - auto_create_delivery_from_order
  - auto_invoice_on_complete
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.delivery import Delivery
from app.models.sales_order import SalesOrder

logger = logging.getLogger(__name__)


def on_order_confirmed(db: Session, order: SalesOrder) -> Delivery | None:
    """Auto-create a pending delivery when a sales order is confirmed.

    Only fires if the tenant has ``auto_create_delivery_from_order`` enabled.
    Returns the new Delivery or None if skipped.
    """
    from app.services.delivery_settings_service import get_settings

    settings = get_settings(db, order.company_id)
    if not settings.auto_create_delivery_from_order:
        return None

    # Avoid duplicate — check if a delivery already references this order
    existing = (
        db.query(Delivery)
        .filter(
            Delivery.company_id == order.company_id,
            Delivery.order_id == order.id,
        )
        .first()
    )
    if existing:
        logger.info(
            "Delivery already exists for order %s (delivery %s) — skipping",
            order.id,
            existing.id,
        )
        return existing

    # Build delivery address from the order's ship-to info
    address_parts = [
        p for p in [order.ship_to_name, order.ship_to_address] if p
    ]
    delivery_address = ", ".join(address_parts) if address_parts else None

    # Default delivery type to "precast" — can be overridden by dispatch later
    delivery = Delivery(
        id=str(uuid.uuid4()),
        company_id=order.company_id,
        delivery_type="precast",
        order_id=order.id,
        customer_id=order.customer_id,
        delivery_address=delivery_address,
        requested_date=order.required_date.date() if order.required_date else None,
        status="pending",
        priority="normal",
        special_instructions=order.notes,
        created_by=order.created_by,
    )
    db.add(delivery)
    db.commit()
    db.refresh(delivery)

    logger.info(
        "Auto-created delivery %s for confirmed order %s (company %s)",
        delivery.id,
        order.number,
        order.company_id,
    )
    return delivery


def on_delivery_completed(db: Session, delivery: Delivery) -> None:
    """Auto-create an invoice when a delivery is completed.

    Only fires if:
      1. The tenant has ``auto_invoice_on_complete`` enabled.
      2. The delivery is linked to a sales order (order_id is set).
    """
    from app.services.delivery_settings_service import get_settings

    settings = get_settings(db, delivery.company_id)
    if not settings.auto_invoice_on_complete:
        return

    if not delivery.order_id:
        logger.debug(
            "Delivery %s has no linked order — skipping auto-invoice",
            delivery.id,
        )
        return

    # Check if the order already has an invoice
    from app.models.invoice import Invoice

    existing_invoice = (
        db.query(Invoice)
        .filter(
            Invoice.company_id == delivery.company_id,
            Invoice.sales_order_id == delivery.order_id,
        )
        .first()
    )
    if existing_invoice:
        logger.info(
            "Invoice %s already exists for order %s — skipping auto-invoice",
            existing_invoice.number,
            delivery.order_id,
        )
        return

    # Use the sales_service to create the invoice (reuses existing logic)
    try:
        from app.services import sales_service

        invoice = sales_service.create_invoice_from_order(
            db,
            delivery.company_id,
            delivery.created_by or "system",
            delivery.order_id,
        )
        logger.info(
            "Auto-created invoice %s for delivery %s (order %s)",
            invoice.number,
            delivery.id,
            delivery.order_id,
        )
    except Exception as exc:
        logger.error(
            "Failed to auto-create invoice for delivery %s: %s",
            delivery.id,
            exc,
        )
