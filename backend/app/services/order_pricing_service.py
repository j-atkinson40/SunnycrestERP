"""Order Pricing Service — conditional pricing logic for vault-based pricing."""

from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session

from app.models.sales_order import SalesOrder, SalesOrderLine
from app.models.product import Product
from app.models.product_category import ProductCategory


# Known vault product lines (used as fallback if category lookup fails)
VAULT_PRODUCT_LINES = {
    "wilbert bronze", "triune", "bronze triune", "copper triune", "sst triune",
    "venetian", "continental", "graveliner", "salute", "monticello", "monarch",
    "tribute", "cameo rose", "loved & cherished", "pine box", "veteran triune",
    "veteran", "universal",
}


def has_vault_on_order(order_lines: list, db: Session) -> bool:
    """Return True if any line item on the order is a burial vault or urn vault product."""
    for line in order_lines:
        if not line.product_id:
            continue
        product = db.query(Product).filter(Product.id == line.product_id).first()
        if not product:
            continue

        # Primary signal: category name contains 'vault'
        if product.category_id:
            category = db.query(ProductCategory).filter(ProductCategory.id == product.category_id).first()
            if category and "vault" in (category.name or "").lower():
                return True

        # Secondary signal: variant_type is set (vaults have STD-1P, STD-2P, etc.)
        if product.variant_type:
            return True

        # Tertiary signal: product_line matches known vault lines
        if product.product_line and product.product_line.lower().strip() in VAULT_PRODUCT_LINES:
            return True

    return False


def get_effective_price(product: Product, order_lines: list, db: Session) -> Optional[Decimal]:
    """Return the effective price for a product given the current order lines.

    - Call office products: returns None (price on request)
    - Single-price products: returns product.price
    - Conditional pricing: returns with-vault price if vault on order, else without-vault price
    """
    if product.is_call_office:
        return None

    if not product.has_conditional_pricing:
        return product.price

    if has_vault_on_order(order_lines, db):
        return product.price  # lower "with our product" price
    else:
        return product.price_without_our_product  # higher standalone price


def recalculate_order_line_prices(order_id: str, db: Session) -> bool:
    """Recalculate prices for all conditional-pricing lines on an order.

    Called after any line item is added, removed, or changed.
    Returns True if any prices were updated.
    """
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not order:
        return False

    lines = db.query(SalesOrderLine).filter(SalesOrderLine.sales_order_id == order_id).all()
    any_updated = False

    for line in lines:
        if not line.product_id:
            continue
        product = db.query(Product).filter(Product.id == line.product_id).first()
        if not product:
            continue
        if not product.has_conditional_pricing and not product.is_call_office:
            continue

        new_price = get_effective_price(product, lines, db)
        if new_price is None:
            continue  # call office — manual entry required, don't overwrite

        if line.unit_price != new_price:
            line.unit_price = new_price
            # Update line total
            if line.quantity:
                line.line_total = new_price * Decimal(str(line.quantity))
            any_updated = True

    if any_updated:
        # Recalculate order totals from all lines (reload to get current values)
        all_lines = db.query(SalesOrderLine).filter(SalesOrderLine.sales_order_id == order_id).all()
        subtotal = sum((line.line_total or Decimal("0")) for line in all_lines)
        order.subtotal = subtotal
        # Preserve existing tax
        tax_amount = order.tax_amount or Decimal("0")
        order.total = subtotal + tax_amount
        db.flush()

    return any_updated
