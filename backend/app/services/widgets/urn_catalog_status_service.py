"""Urn Catalog Status widget — extension-gated catalog health.

Phase W-3d cluster widget. **First widget exercising the
`required_extension` axis of the 5-axis filter end-to-end** —
visible only to tenants with the `urn_sales` extension activated.

Per [DESIGN_LANGUAGE.md §12.10 reference](../../../DESIGN_LANGUAGE.md):
  • Glance variant: single-line summary
    ("23 SKUs · 3 low-stock · 5 recent orders")
  • Brief variant: 3-5 row breakdown with low-stock items
    highlighted

Catalog health metrics:
  • Total active SKUs (where is_active=True AND discontinued=False)
  • Stocked SKUs (source_type='stocked')
  • Drop-ship SKUs (source_type='drop_ship')
  • Low-stock count (stocked SKUs where qty_on_hand <= reorder_point
    AND reorder_point > 0; reorder_point=0 means "no monitoring")
  • Recent orders (UrnOrders created in last 7 days, is_active=true)

Tenant isolation: explicit `tenant_id == user.company_id` filter at
every entry point. The widget never sees other tenants' catalog
data.

Per [§12.6a Widget Interactivity Discipline](../../../DESIGN_LANGUAGE.md):
view-only with click-through to `/urns/catalog` for the full catalog
view. No in-place edits — adjusting stock levels, reorder points, or
SKU status happens on the catalog page.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.urn_inventory import UrnInventory
from app.models.urn_order import UrnOrder
from app.models.urn_product import UrnProduct
from app.models.user import User


def get_urn_catalog_status(
    db: Session,
    *,
    user: User,
    tenant_id: Optional[str] = None,
) -> dict:
    """Return urn catalog health summary for the user's tenant.

    Response shape:
        {
          "total_skus": 23,
          "stocked_skus": 8,
          "drop_ship_skus": 15,
          "low_stock_count": 3,
          "low_stock_items": [
            { "sku": "P2013", "name": "Cloisonne Opal",
              "qty_on_hand": 2, "reorder_point": 5 }, ...
          ],
          "recent_order_count": 5,
          "navigation_target": "/urns/catalog"
        }

    Empty state: tenant with urn_sales extension but no products —
    counts return 0; widget renders empty-state copy with CTA to
    catalog setup.
    """
    tid = tenant_id or user.company_id
    if not tid:
        return {
            "total_skus": 0,
            "stocked_skus": 0,
            "drop_ship_skus": 0,
            "low_stock_count": 0,
            "low_stock_items": [],
            "recent_order_count": 0,
            "navigation_target": "/urns/catalog",
        }

    # Active SKU counts
    base_q = db.query(UrnProduct).filter(
        UrnProduct.tenant_id == tid,
        UrnProduct.is_active.is_(True),
        UrnProduct.discontinued.is_(False),
    )
    total_skus = base_q.count()
    stocked_skus = base_q.filter(UrnProduct.source_type == "stocked").count()
    drop_ship_skus = base_q.filter(
        UrnProduct.source_type == "drop_ship"
    ).count()

    # Low-stock identification: stocked SKUs whose inventory is at or
    # below reorder_point (and reorder_point is monitored, > 0).
    low_stock_query = (
        db.query(UrnProduct, UrnInventory)
        .join(
            UrnInventory,
            UrnInventory.urn_product_id == UrnProduct.id,
        )
        .filter(
            UrnProduct.tenant_id == tid,
            UrnProduct.is_active.is_(True),
            UrnProduct.discontinued.is_(False),
            UrnProduct.source_type == "stocked",
            UrnInventory.reorder_point > 0,
            UrnInventory.qty_on_hand <= UrnInventory.reorder_point,
        )
        .order_by(UrnInventory.qty_on_hand.asc())
    )
    low_stock_rows = low_stock_query.all()

    low_stock_items: list[dict] = []
    for prod, inv in low_stock_rows[:10]:  # Brief variant shows top 10
        low_stock_items.append(
            {
                "product_id": prod.id,
                "sku": prod.sku,
                "name": prod.name,
                "qty_on_hand": inv.qty_on_hand,
                "qty_reserved": inv.qty_reserved,
                "reorder_point": inv.reorder_point,
            }
        )

    # Recent orders in last 7 days
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent_order_count = (
        db.query(func.count(UrnOrder.id))
        .filter(
            UrnOrder.tenant_id == tid,
            UrnOrder.is_active.is_(True),
            UrnOrder.created_at >= seven_days_ago,
        )
        .scalar()
        or 0
    )

    return {
        "total_skus": total_skus,
        "stocked_skus": stocked_skus,
        "drop_ship_skus": drop_ship_skus,
        "low_stock_count": len(low_stock_rows),
        "low_stock_items": low_stock_items,
        "recent_order_count": recent_order_count,
        "navigation_target": "/urns/catalog",
    }
