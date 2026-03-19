"""Bundle pricing service — conditional pricing based on order composition."""

import logging
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.product_bundle import ProductBundle
from app.models.product import Product

logger = logging.getLogger(__name__)


@dataclass
class BundlePriceResult:
    price: Decimal
    tier: str  # "with_vault" or "standalone"
    qualifying_product: str | None = None


def get_bundle_price(
    db: Session,
    bundle_id: str,
    order_line_items: list[dict],
) -> BundlePriceResult:
    """Determine the correct bundle price based on order line items.

    order_line_items: [{"product_id": str, "product_name": str, "category": str, ...}]
    """
    bundle = db.query(ProductBundle).filter(ProductBundle.id == bundle_id).first()
    if not bundle:
        raise ValueError(f"Bundle {bundle_id} not found")

    if not bundle.has_conditional_pricing:
        return BundlePriceResult(
            price=bundle.price or Decimal("0"),
            tier="standalone",
            qualifying_product=None,
        )

    # Check if any line item qualifies for vault pricing
    qualifier_cats = bundle.vault_qualifier_list
    for item in order_line_items:
        category = item.get("category", "")
        if category in qualifier_cats:
            return BundlePriceResult(
                price=bundle.with_vault_price or Decimal("0"),
                tier="with_vault",
                qualifying_product=item.get("product_name"),
            )

    return BundlePriceResult(
        price=bundle.standalone_price or Decimal("0"),
        tier="standalone",
        qualifying_product=None,
    )


def reevaluate_order_bundles(
    db: Session,
    tenant_id: str,
    order_line_items: list[dict],
) -> list[dict]:
    """Re-evaluate pricing for all bundles on an order.

    Called when line items change. Returns list of price changes.
    Non-blocking — logs errors but does not raise.

    order_line_items: [{"id": str, "product_id": str, "product_name": str,
                        "category": str, "line_item_type": str,
                        "bundle_id": str | None, "charge_id": str | None,
                        "unit_price": Decimal, ...}]
    """
    price_changes: list[dict] = []

    try:
        # Re-evaluate bundle line items
        bundle_items = [i for i in order_line_items if i.get("bundle_id")]
        for item in bundle_items:
            try:
                result = get_bundle_price(db, item["bundle_id"], order_line_items)
                current_price = Decimal(str(item.get("unit_price", 0)))
                if result.price != current_price:
                    price_changes.append({
                        "line_item_id": item["id"],
                        "item_name": item.get("product_name", ""),
                        "old_price": float(current_price),
                        "new_price": float(result.price),
                        "tier": result.tier,
                        "qualifying_product": result.qualifying_product,
                        "direction": "down" if result.price < current_price else "up",
                    })
            except Exception:
                logger.exception("Failed to re-evaluate bundle %s", item.get("bundle_id"))

        # Re-evaluate overage charges with conditional pricing
        from app.models.charge_library_item import ChargeLibraryItem

        overage_items = [
            i for i in order_line_items
            if i.get("line_item_type") == "overage_charge" and i.get("charge_id")
        ]

        # Check if order has a qualifying vault
        has_qualifying_vault = any(
            i.get("category") in ("burial_vault", "urn_vault")
            for i in order_line_items
        )

        for item in overage_items:
            try:
                charge = db.query(ChargeLibraryItem).filter(
                    ChargeLibraryItem.id == item["charge_id"]
                ).first()
                if not charge or not charge.has_conditional_pricing:
                    continue

                new_price = (
                    charge.with_vault_price if has_qualifying_vault
                    else charge.standalone_price
                ) or Decimal("0")

                current_price = Decimal(str(item.get("unit_price", 0)))
                if new_price != current_price:
                    price_changes.append({
                        "line_item_id": item["id"],
                        "item_name": item.get("product_name", charge.charge_name),
                        "old_price": float(current_price),
                        "new_price": float(new_price),
                        "tier": "with_vault" if has_qualifying_vault else "standalone",
                        "qualifying_product": None,
                        "direction": "down" if new_price < current_price else "up",
                    })
            except Exception:
                logger.exception("Failed to re-evaluate overage charge %s", item.get("charge_id"))

    except Exception:
        logger.exception("reevaluate_order_bundles failed")

    return price_changes
