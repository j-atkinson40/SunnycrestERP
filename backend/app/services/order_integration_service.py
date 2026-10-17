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


def _requested_date_for(order: SalesOrder):
    """The day this delivery is wanted: the service date, zone-proof.

    ⚠️ THE WHOLE POINT IS THAT A `Date` CANNOT SHIFT AND A `DateTime` CAN. See the
    comment at the call site for the day-early delivery this prevents.
    """
    scheduled = getattr(order, "scheduled_date", None)
    if scheduled is not None:
        return scheduled
    required = getattr(order, "required_date", None)
    return required.date() if required is not None else None


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

    # Default delivery type to "standard" — can be overridden by dispatch later
    delivery = Delivery(
        id=str(uuid.uuid4()),
        company_id=order.company_id,
        delivery_type="standard",
        order_id=order.id,
        customer_id=order.customer_id,
        delivery_address=delivery_address,
        # ⚠️ `scheduled_date` FIRST, AND THAT ORDER IS A BUG FIX (2026-10-16). This read
        # `order.required_date.date()` alone, and `.date()` on a `DateTime(timezone=True)`
        # is evaluated in WHATEVER ZONE THE SESSION READS IT IN. Opas writes
        # `required_date` as midnight UTC on the service day, and midnight UTC is the
        # PREVIOUS EVENING in every negative-offset zone — so with a session on
        # `America/New_York` (which is what `SHOW TimeZone` returns on a dev box, and
        # what any Eastern-configured server returns) a service on the 23rd produced a
        # delivery requested for the 22nd. A stop on the board the day before the
        # funeral.
        #
        # ⚠️ AND A COMMENT OF MINE IN `capture/session_service.approve` ASSERTED THIS WAS
        # SAFE — "a date-only value with a UTC midnight stamp round-trips to the same day
        # for every zone from UTC-11 to UTC+13". That is false for every negative offset,
        # which is most of the Americas. It is corrected there.
        #
        # `scheduled_date` is a plain `Date`. It has no zone and cannot shift. It is also
        # the field that MEANS the service day, so preferring it is both safer and more
        # honest; `required_date` stays as the fallback for pre-Opas and hand-entered
        # orders that carry only it.
        requested_date=_requested_date_for(order),
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

    Behaviour depends on ``invoice_generation_mode``:
      - 'immediate': create an open invoice right now (original behaviour)
      - 'end_of_day': skip — the nightly batch job handles it
      - 'manual': skip entirely
      - Legacy fallback: if ``auto_invoice_on_complete`` is True and mode
        hasn't been set, treat as 'immediate'.
    """
    from app.services.delivery_settings_service import get_settings

    settings = get_settings(db, delivery.company_id)

    mode = getattr(settings, "invoice_generation_mode", None)
    # Legacy: if mode not set, fall back to the old boolean
    if not mode:
        mode = "immediate" if settings.auto_invoice_on_complete else "manual"

    if mode != "immediate":
        return  # 'end_of_day' handled by batch job; 'manual' never auto-invoices

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
