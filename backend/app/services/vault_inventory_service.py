"""
Vault inventory projection and replenishment intelligence.

Handles delivery-aware inventory projections for tenants that purchase
vaults from a supplier (vault_fulfillment_mode = 'purchase' or 'hybrid').
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def get_next_delivery_date(supplier, from_date: date | None = None) -> date:
    """Return the next delivery date given the supplier's schedule and lead time."""
    if from_date is None:
        from_date = date.today()

    earliest_delivery = from_date + timedelta(days=supplier.lead_time_days)

    if supplier.delivery_schedule == "on_demand" or not supplier.delivery_days:
        return earliest_delivery

    # Fixed delivery days — find next qualifying day >= earliest_delivery
    for day_offset in range(14):
        candidate = earliest_delivery + timedelta(days=day_offset)
        candidate_day_name = DAY_NAMES[candidate.weekday()]
        if candidate_day_name in (supplier.delivery_days or []):
            return candidate

    # Fallback
    return earliest_delivery


def get_order_deadline(supplier, delivery_date: date) -> date:
    """When must we place the order to receive it by delivery_date?"""
    return delivery_date - timedelta(days=supplier.lead_time_days)


def project_inventory(
    db: Session,
    company_id: str,
    product_id: str,
    days_ahead: int = 14,
) -> dict[str, Any]:
    """Build a day-by-day inventory projection for a product."""
    from app.models import InventoryItem, SalesOrder, PurchaseOrder, PurchaseOrderLine

    today = date.today()

    # Current stock
    inv_item = db.query(InventoryItem).filter(
        InventoryItem.company_id == company_id,
        InventoryItem.product_id == product_id,
        InventoryItem.is_active == True,
    ).first()
    current_stock = int(inv_item.quantity_on_hand) if inv_item else 0
    reorder_point = int(inv_item.reorder_point) if inv_item and inv_item.reorder_point else 0

    # Build day maps
    outbound_by_date: dict[date, int] = {}
    inbound_by_date: dict[date, int] = {}

    horizon = today + timedelta(days=days_ahead)

    # Scheduled outbound orders (sales orders with this product)
    try:
        orders = db.query(SalesOrder).filter(
            SalesOrder.company_id == company_id,
            SalesOrder.scheduled_date >= today,
            SalesOrder.scheduled_date <= horizon,
            SalesOrder.status.notin_(["cancelled", "delivered", "invoiced"]),
        ).all()
        for order in orders:
            if not order.scheduled_date:
                continue
            order_date = order.scheduled_date if isinstance(order.scheduled_date, date) else order.scheduled_date.date()
            for line in (order.lines or []):
                if str(line.product_id) == str(product_id):
                    qty = int(line.quantity or 0)
                    outbound_by_date[order_date] = outbound_by_date.get(order_date, 0) + qty
    except Exception as e:
        logger.debug("Could not load scheduled orders for projection: %s", e)

    # Expected inbound from POs
    try:
        po_lines = db.query(PurchaseOrderLine).join(
            PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.purchase_order_id
        ).filter(
            PurchaseOrder.company_id == company_id,
            PurchaseOrder.status.in_(["sent", "partial"]),
            PurchaseOrderLine.product_id == product_id,
            PurchaseOrderLine.deleted_at.is_(None),
        ).all()
        for line in po_lines:
            po = db.query(PurchaseOrder).filter(PurchaseOrder.id == line.purchase_order_id).first()
            if po and po.expected_date:
                exp_date = po.expected_date if isinstance(po.expected_date, date) else po.expected_date.date()
                if today <= exp_date <= horizon:
                    remaining = float(line.quantity_ordered or 0) - float(line.quantity_received or 0)
                    inbound_by_date[exp_date] = inbound_by_date.get(exp_date, 0) + int(remaining)
    except Exception as e:
        logger.debug("Could not load PO lines for projection: %s", e)

    # Build projection
    projection = []
    running_qty = current_stock
    for day_offset in range(days_ahead):
        d = today + timedelta(days=day_offset)
        outbound = outbound_by_date.get(d, 0)
        inbound = inbound_by_date.get(d, 0)
        running_qty = running_qty + inbound - outbound
        projection.append({
            "date": d.isoformat(),
            "quantity": running_qty,
            "outbound": outbound,
            "inbound": inbound,
        })

    lowest = min((p["quantity"] for p in projection), default=current_stock)
    lowest_date = next((p["date"] for p in projection if p["quantity"] == lowest), None)

    return {
        "current_stock": current_stock,
        "projected_14_days": projection,
        "lowest_projected": lowest,
        "lowest_projected_date": lowest_date,
        "reorder_point": reorder_point,
    }


def check_reorder_needed(
    db: Session,
    company_id: str,
    product_id: str,
) -> dict[str, Any] | None:
    """Check if a reorder is needed for a product given the supplier's delivery schedule."""
    from app.models import VaultSupplier, InventoryItem

    supplier = db.query(VaultSupplier).filter(
        VaultSupplier.company_id == company_id,
        VaultSupplier.is_primary == True,
        VaultSupplier.is_active == True,
    ).first()

    if not supplier:
        return None

    inv_item = db.query(InventoryItem).filter(
        InventoryItem.company_id == company_id,
        InventoryItem.product_id == product_id,
    ).first()

    reorder_point = int(inv_item.reorder_point) if inv_item and inv_item.reorder_point else 3
    today = date.today()
    next_delivery = get_next_delivery_date(supplier, today)
    order_deadline = get_order_deadline(supplier, next_delivery)
    days_until_deadline = (order_deadline - today).days

    proj = project_inventory(db, company_id, product_id, days_ahead=21)

    # Stock level at next delivery date
    delivery_day_offset = (next_delivery - today).days
    if 0 <= delivery_day_offset < len(proj["projected_14_days"]):
        stock_at_delivery = proj["projected_14_days"][min(delivery_day_offset, len(proj["projected_14_days"]) - 1)]["quantity"]
    else:
        stock_at_delivery = proj["current_stock"]

    needs_reorder = (
        proj["lowest_projected"] <= reorder_point or
        stock_at_delivery <= reorder_point
    )
    urgent = days_until_deadline <= 0

    return {
        "needs_reorder": needs_reorder,
        "urgent": urgent,
        "next_delivery": next_delivery.isoformat(),
        "order_deadline": order_deadline.isoformat(),
        "current_stock": proj["current_stock"],
        "projected_at_delivery": stock_at_delivery,
        "reorder_point": reorder_point,
        "days_until_deadline": days_until_deadline,
        "lowest_projected": proj["lowest_projected"],
        "lowest_projected_date": proj["lowest_projected_date"],
    }


def build_suggested_order(db: Session, company_id: str) -> dict[str, Any] | None:
    """Build a suggested vault order using FIFO deficit + velocity fill."""
    from app.models import VaultSupplier, Product, InventoryItem, InventoryTransaction
    from sqlalchemy import func as sqlfunc

    supplier = db.query(VaultSupplier).filter(
        VaultSupplier.company_id == company_id,
        VaultSupplier.is_primary == True,
        VaultSupplier.is_active == True,
    ).first()
    if not supplier:
        return None

    order_quantity = supplier.order_quantity
    today = date.today()
    next_delivery = get_next_delivery_date(supplier, today)
    order_deadline = get_order_deadline(supplier, next_delivery)

    # Get vault products
    products = db.query(Product).filter(
        Product.company_id == company_id,
        Product.is_active == True,
    ).all()

    # Filter to vault/burial products
    vault_products = [p for p in products if any(
        kw in (p.name or "").lower() or kw in (getattr(p, "category_name", "") or "").lower()
        for kw in ["vault", "urn", "graveliner", "monticello", "venetian"]
    )]
    if not vault_products:
        vault_products = products[:10]  # fallback

    product_checks = []
    for product in vault_products:
        inv = db.query(InventoryItem).filter(
            InventoryItem.company_id == company_id,
            InventoryItem.product_id == product.id,
        ).first()
        if not inv:
            continue

        reorder_point = int(inv.reorder_point or 3)
        check = check_reorder_needed(db, company_id, product.id) or {}
        projected = check.get("projected_at_delivery", int(inv.quantity_on_hand or 0))
        deficit = max(0, reorder_point - projected)

        # Calculate velocity: sells in last 30 days
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        sell_qty = db.query(sqlfunc.sum(InventoryTransaction.quantity_change)).filter(
            InventoryTransaction.company_id == company_id,
            InventoryTransaction.product_id == product.id,
            InventoryTransaction.transaction_type == "sell",
            InventoryTransaction.created_at >= thirty_days_ago,
        ).scalar() or 0
        velocity = abs(float(sell_qty)) / 30.0  # units per day

        product_checks.append({
            "product_id": product.id,
            "product_name": product.name,
            "current_stock": int(inv.quantity_on_hand or 0),
            "reorder_point": reorder_point,
            "needs_reorder": check.get("needs_reorder", False),
            "urgent": check.get("urgent", False),
            "projected_at_delivery": projected,
            "deficit": deficit,
            "velocity": velocity,
        })

    # Sort by urgency
    product_checks.sort(key=lambda x: (not x["urgent"], not x["needs_reorder"], -x["deficit"], -x["velocity"]))

    allocated: dict[str, int] = {}
    slots_remaining = order_quantity

    # Pass 1: Allocate deficit
    for pc in product_checks:
        if pc["needs_reorder"] and pc["deficit"] > 0 and slots_remaining > 0:
            qty = min(pc["deficit"], slots_remaining)
            allocated[pc["product_id"]] = qty
            slots_remaining -= qty

    # Pass 2: Velocity fill
    if slots_remaining > 0:
        total_velocity = sum(pc["velocity"] for pc in product_checks) or 1.0
        for pc in sorted(product_checks, key=lambda x: -x["velocity"]):
            if slots_remaining <= 0:
                break
            share = max(1, round(slots_remaining * (pc["velocity"] / total_velocity)))
            share = min(share, slots_remaining)
            allocated[pc["product_id"]] = allocated.get(pc["product_id"], 0) + share
            slots_remaining -= share

    # Assign leftover to highest-deficit product
    if slots_remaining > 0 and product_checks:
        top = max(product_checks, key=lambda x: x["deficit"])
        allocated[top["product_id"]] = allocated.get(top["product_id"], 0) + slots_remaining

    suggested_items = []
    for pc in product_checks:
        qty = allocated.get(pc["product_id"], 0)
        if qty > 0:
            reason = "urgent" if pc["urgent"] else ("below_reorder_point" if pc["needs_reorder"] else "velocity_fill")
            suggested_items.append({
                "product_id": pc["product_id"],
                "product_name": pc["product_name"],
                "quantity": qty,
                "reason": reason,
                "current_stock": pc["current_stock"],
                "reorder_point": pc["reorder_point"],
            })

    return {
        "supplier_id": supplier.id,
        "vendor_id": supplier.vendor_id,
        "order_quantity": order_quantity,
        "suggested_items": suggested_items,
        "next_delivery": next_delivery.isoformat(),
        "order_deadline": order_deadline.isoformat(),
        "urgent": any(pc["urgent"] for pc in product_checks if pc["needs_reorder"]),
        "total_units": sum(item["quantity"] for item in suggested_items),
    }
