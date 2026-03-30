"""Funeral home preference service.

Handles auto-adding a vault placer line item when:
  - The customer (funeral home) has prefers_placer = True
  - The order/quote contains a line item whose product has is_lowering_device = True
  - The order/quote does not already have a placer line item

Also detects placer preferences from historical order import data.
"""

import logging
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.product import Product

logger = logging.getLogger(__name__)

# Reason tag stored on is_auto_added lines
PLACER_REASON = "funeral_home_placer_preference"


# ---------------------------------------------------------------------------
# Core helper: find or don't
# ---------------------------------------------------------------------------


def _get_placer_product(db: Session, company_id: str) -> Product | None:
    """Return the active placer product for the tenant, or None."""
    return (
        db.query(Product)
        .filter(
            Product.company_id == company_id,
            Product.is_placer.is_(True),
            Product.is_active.is_(True),
        )
        .first()
    )


def _lines_have_lowering_device(db: Session, lines) -> bool:
    """Return True if any line in the list references a product with is_lowering_device."""
    for line in lines:
        if not line.product_id:
            continue
        product = db.query(Product).filter(Product.id == line.product_id).first()
        if product and product.is_lowering_device:
            return True
    return False


def _lines_have_placer(db: Session, lines) -> bool:
    """Return True if any line already references a placer product."""
    for line in lines:
        if not line.product_id:
            continue
        product = db.query(Product).filter(Product.id == line.product_id).first()
        if product and product.is_placer:
            return True
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_placer_to_quote_lines(
    db: Session,
    company_id: str,
    customer_id: str | None,
    quote,
    line_class,
) -> bool:
    """Add a vault placer QuoteLine if the funeral home prefers it and has a lowering device.

    Args:
        db: SQLAlchemy session
        company_id: tenant company ID
        customer_id: customer ID (may be None for anonymous orders)
        quote: Quote ORM object with .id and .lines
        line_class: QuoteLine class to instantiate

    Returns:
        True if a placer was added
    """
    if not customer_id:
        return False

    try:
        customer = (
            db.query(Customer)
            .filter(Customer.id == customer_id, Customer.company_id == company_id)
            .first()
        )
        if not customer or not customer.prefers_placer:
            return False

        lines = list(quote.lines or [])
        if not _lines_have_lowering_device(db, lines):
            return False
        if _lines_have_placer(db, lines):
            return False  # Already present

        placer = _get_placer_product(db, company_id)
        if not placer:
            logger.warning(
                "prefers_placer=True for customer %s but no is_placer product found for company %s",
                customer_id,
                company_id,
            )
            return False

        import uuid

        placer_line = line_class(
            id=str(uuid.uuid4()),
            quote_id=quote.id,
            product_id=placer.id,
            description=placer.name,
            quantity=Decimal("1"),
            unit_price=Decimal("0.00"),
            line_total=Decimal("0.00"),
            sort_order=len(lines) + 1,
            is_auto_added=True,
            auto_add_reason=PLACER_REASON,
        )
        db.add(placer_line)
        db.flush()
        logger.info(
            "Auto-added placer line to quote %s for customer %s",
            quote.id,
            customer_id,
        )
        return True

    except Exception as exc:
        logger.warning("apply_placer_to_quote_lines failed: %s", exc)
        return False


def apply_placer_to_order_lines(
    db: Session,
    company_id: str,
    customer_id: str | None,
    order,
    line_class,
) -> bool:
    """Add a vault placer SalesOrderLine if the funeral home prefers it.

    Args:
        db: SQLAlchemy session
        company_id: tenant company ID
        customer_id: customer ID (may be None)
        order: SalesOrder ORM object with .id and .lines
        line_class: SalesOrderLine class to instantiate

    Returns:
        True if a placer was added
    """
    if not customer_id:
        return False

    try:
        customer = (
            db.query(Customer)
            .filter(Customer.id == customer_id, Customer.company_id == company_id)
            .first()
        )
        if not customer or not customer.prefers_placer:
            return False

        lines = list(order.lines or [])
        if not _lines_have_lowering_device(db, lines):
            return False
        if _lines_have_placer(db, lines):
            return False

        placer = _get_placer_product(db, company_id)
        if not placer:
            logger.warning(
                "prefers_placer=True for customer %s but no is_placer product found for company %s",
                customer_id,
                company_id,
            )
            return False

        import uuid

        placer_line = line_class(
            id=str(uuid.uuid4()),
            sales_order_id=order.id,
            product_id=placer.id,
            description=placer.name,
            quantity=Decimal("1"),
            unit_price=Decimal("0.00"),
            line_total=Decimal("0.00"),
            sort_order=len(lines) + 1,
            is_auto_added=True,
            auto_add_reason=PLACER_REASON,
        )
        db.add(placer_line)
        db.flush()
        logger.info(
            "Auto-added placer line to order %s for customer %s",
            order.id,
            customer_id,
        )
        return True

    except Exception as exc:
        logger.warning("apply_placer_to_order_lines failed: %s", exc)
        return False


def set_order_confirmation_method(
    db: Session, company_id: str, customer_id: str | None, order
) -> None:
    """Copy preferred_confirmation_method from customer onto the order (if not already set)."""
    if not customer_id or getattr(order, "confirmation_method", None):
        return
    try:
        customer = (
            db.query(Customer)
            .filter(Customer.id == customer_id, Customer.company_id == company_id)
            .first()
        )
        if customer and customer.preferred_confirmation_method:
            order.confirmation_method = customer.preferred_confirmation_method
    except Exception as exc:
        logger.warning("set_order_confirmation_method failed: %s", exc)


# ---------------------------------------------------------------------------
# Historical import placer detection
# ---------------------------------------------------------------------------


def detect_placer_preferences_from_history(
    db: Session, company_id: str, import_id: str
) -> dict:
    """After a historical import, detect funeral homes that consistently used a placer.

    Rules:
      - If placer_rate > 0.80  → set customer.prefers_placer = True (auto)
      - If 0.30 < placer_rate <= 0.80 → add to warnings (suggest manual review)

    Returns a dict with:
      auto_set: list of {customer_id, name, placer_rate}
      suggested: list of {customer_id, name, placer_rate}
    """
    from sqlalchemy import func
    from app.models.historical_order_import import HistoricalOrder

    auto_set = []
    suggested = []

    try:
        # Get all funeral home customers that appear in this import
        customer_rows = (
            db.query(
                HistoricalOrder.customer_id,
                func.count().label("total_orders"),
            )
            .filter(
                HistoricalOrder.import_id == import_id,
                HistoricalOrder.customer_id.isnot(None),
            )
            .group_by(HistoricalOrder.customer_id)
            .all()
        )

        for customer_id, total_orders in customer_rows:
            if not total_orders:
                continue

            # Count orders with lowering device in equipment_mapped
            lowering_orders = (
                db.query(func.count())
                .filter(
                    HistoricalOrder.import_id == import_id,
                    HistoricalOrder.customer_id == customer_id,
                    HistoricalOrder.equipment_mapped.ilike("%lowering%")
                    | HistoricalOrder.equipment_mapped.ilike("%device%")
                    | HistoricalOrder.equipment_mapped.ilike("%full%"),
                )
                .scalar()
                or 0
            )

            if lowering_orders == 0:
                continue

            # Count orders with placer in raw_equipment
            placer_orders = (
                db.query(func.count())
                .filter(
                    HistoricalOrder.import_id == import_id,
                    HistoricalOrder.customer_id == customer_id,
                    HistoricalOrder.raw_equipment.ilike("%placer%"),
                )
                .scalar()
                or 0
            )

            placer_rate = placer_orders / lowering_orders

            customer = (
                db.query(Customer)
                .filter(Customer.id == customer_id, Customer.company_id == company_id)
                .first()
            )
            if not customer:
                continue

            customer_name = customer.name

            if placer_rate > 0.80:
                customer.prefers_placer = True
                auto_set.append(
                    {
                        "customer_id": customer_id,
                        "name": customer_name,
                        "placer_rate": round(placer_rate * 100, 1),
                        "placer_orders": placer_orders,
                        "lowering_orders": lowering_orders,
                    }
                )
            elif placer_rate > 0.30:
                suggested.append(
                    {
                        "customer_id": customer_id,
                        "name": customer_name,
                        "placer_rate": round(placer_rate * 100, 1),
                        "placer_orders": placer_orders,
                        "lowering_orders": lowering_orders,
                    }
                )

        if auto_set:
            db.flush()

    except Exception as exc:
        logger.warning("detect_placer_preferences_from_history failed: %s", exc)

    return {"auto_set": auto_set, "suggested": suggested}
