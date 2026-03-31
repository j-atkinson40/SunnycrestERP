"""Service layer for Purchase Orders — CRUD, receiving, status transitions."""

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import and_, func
from sqlalchemy.orm import Session, joinedload

logger = logging.getLogger(__name__)

from app.models.inventory_item import InventoryItem
from app.models.inventory_transaction import InventoryTransaction
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_line import PurchaseOrderLine
from app.services import audit_service


# ---------------------------------------------------------------------------
# PO number generation (PO-YYYY-####)
# ---------------------------------------------------------------------------

def _next_po_number(db: Session, company_id: str) -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"PO-{year}-"

    last = (
        db.query(PurchaseOrder.number)
        .filter(
            PurchaseOrder.company_id == company_id,
            PurchaseOrder.number.like(f"{prefix}%"),
        )
        .order_by(PurchaseOrder.number.desc())
        .first()
    )
    if last and last[0]:
        try:
            seq = int(last[0].replace(prefix, "")) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _active_filter():
    return PurchaseOrder.deleted_at.is_(None)


def _calc_line_total(qty: Decimal, cost: Decimal) -> Decimal:
    return (qty * cost).quantize(Decimal("0.01"))


def _recalc_totals(po: PurchaseOrder) -> None:
    """Recalculate subtotal & total from non-deleted lines."""
    subtotal = Decimal("0.00")
    for line in po.lines:
        if line.deleted_at is None:
            subtotal += line.line_total
    po.subtotal = subtotal
    po.total = subtotal + (po.tax_amount or Decimal("0.00"))


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def get_purchase_orders(
    db: Session,
    company_id: str,
    page: int = 1,
    per_page: int = 20,
    search: str | None = None,
    status: str | None = None,
    vendor_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    query = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.company_id == company_id, _active_filter())
    )

    if search:
        term = f"%{search}%"
        query = query.filter(PurchaseOrder.number.ilike(term))

    if status:
        query = query.filter(PurchaseOrder.status == status)

    if vendor_id:
        query = query.filter(PurchaseOrder.vendor_id == vendor_id)

    if date_from:
        query = query.filter(PurchaseOrder.order_date >= date_from)
    if date_to:
        query = query.filter(PurchaseOrder.order_date <= date_to)

    total = query.count()
    items = (
        query.options(joinedload(PurchaseOrder.vendor))
        .order_by(PurchaseOrder.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {"items": items, "total": total, "page": page, "per_page": per_page}


def get_purchase_order(db: Session, po_id: str, company_id: str) -> PurchaseOrder:
    po = (
        db.query(PurchaseOrder)
        .options(
            joinedload(PurchaseOrder.vendor),
            joinedload(PurchaseOrder.lines).joinedload(PurchaseOrderLine.product),
            joinedload(PurchaseOrder.creator),
        )
        .filter(
            PurchaseOrder.id == po_id,
            PurchaseOrder.company_id == company_id,
            _active_filter(),
        )
        .first()
    )
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return po


def create_purchase_order(
    db: Session, data, company_id: str, actor_id: str
) -> PurchaseOrder:
    from datetime import date as date_type

    po = PurchaseOrder(
        id=str(uuid.uuid4()),
        company_id=company_id,
        number=_next_po_number(db, company_id),
        vendor_id=data.vendor_id,
        status="draft",
        order_date=data.order_date or datetime.now(timezone.utc),
        expected_date=data.expected_date,
        shipping_address=data.shipping_address,
        tax_amount=data.tax_amount or Decimal("0.00"),
        notes=data.notes,
        created_by=actor_id,
    )
    db.add(po)
    db.flush()

    # Add lines
    for idx, line_data in enumerate(data.lines):
        line_total = _calc_line_total(line_data.quantity_ordered, line_data.unit_cost)
        line = PurchaseOrderLine(
            id=str(uuid.uuid4()),
            po_id=po.id,
            product_id=line_data.product_id,
            description=line_data.description,
            quantity_ordered=line_data.quantity_ordered,
            unit_cost=line_data.unit_cost,
            line_total=line_total,
            sort_order=line_data.sort_order or idx,
        )
        db.add(line)

    db.flush()
    db.refresh(po)
    _recalc_totals(po)
    db.flush()

    audit_service.log_action(
        db, company_id, "created", "purchase_order", po.id,
        user_id=actor_id,
        changes={"number": po.number, "vendor_id": po.vendor_id},
    )
    db.commit()
    return po


def update_purchase_order(
    db: Session, po_id: str, data, company_id: str, actor_id: str
) -> PurchaseOrder:
    po = get_purchase_order(db, po_id, company_id)

    if po.status not in ("draft", "sent"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot edit PO in '{po.status}' status",
        )

    # Update header fields
    for field in ("vendor_id", "order_date", "expected_date", "shipping_address",
                  "tax_amount", "notes"):
        val = getattr(data, field, None)
        if val is not None:
            setattr(po, field, val)

    po.modified_by = actor_id
    po.modified_at = datetime.now(timezone.utc)

    # Replace lines if provided
    if data.lines is not None:
        # Soft-delete old lines
        for old_line in po.lines:
            if old_line.deleted_at is None:
                old_line.deleted_at = datetime.now(timezone.utc)

        # Create new lines
        for idx, ld in enumerate(data.lines):
            line_total = _calc_line_total(
                ld.quantity_ordered or Decimal("0"),
                ld.unit_cost or Decimal("0"),
            )
            line = PurchaseOrderLine(
                id=str(uuid.uuid4()),
                po_id=po.id,
                product_id=ld.product_id,
                description=ld.description or "",
                quantity_ordered=ld.quantity_ordered or Decimal("0"),
                unit_cost=ld.unit_cost or Decimal("0"),
                line_total=line_total,
                sort_order=ld.sort_order if ld.sort_order is not None else idx,
            )
            db.add(line)

    db.flush()
    db.refresh(po)
    _recalc_totals(po)

    audit_service.log_action(
        db, company_id, "updated", "purchase_order", po.id,
        user_id=actor_id,
    )
    db.commit()
    return po


def send_purchase_order(
    db: Session, po_id: str, company_id: str, actor_id: str
) -> PurchaseOrder:
    po = get_purchase_order(db, po_id, company_id)
    if po.status != "draft":
        raise HTTPException(
            status_code=400, detail="Only draft POs can be sent"
        )
    po.status = "sent"
    po.sent_at = datetime.now(timezone.utc)
    po.modified_by = actor_id
    po.modified_at = datetime.now(timezone.utc)

    audit_service.log_action(
        db, company_id, "sent", "purchase_order", po.id, user_id=actor_id,
    )
    db.commit()
    return po


def receive_purchase_order(
    db: Session, po_id: str, receive_data, company_id: str, actor_id: str
) -> PurchaseOrder:
    """Record receiving against PO lines. Updates inventory if product_id is set."""
    po = get_purchase_order(db, po_id, company_id)

    if po.status not in ("sent", "partial"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot receive against PO in '{po.status}' status",
        )

    # Build lookup of active lines
    line_map = {
        line.id: line for line in po.lines if line.deleted_at is None
    }

    for item in receive_data.lines:
        line = line_map.get(item.po_line_id)
        if not line:
            raise HTTPException(
                status_code=400,
                detail=f"PO line {item.po_line_id} not found",
            )
        if item.quantity_received <= 0:
            raise HTTPException(
                status_code=400,
                detail="Quantity received must be positive",
            )
        new_qty = line.quantity_received + item.quantity_received
        if new_qty > line.quantity_ordered:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot receive {item.quantity_received} for line "
                    f"'{line.description}' — would exceed ordered qty "
                    f"({line.quantity_ordered})"
                ),
            )
        line.quantity_received = new_qty

        # Update inventory if product_id is set
        if line.product_id:
            _update_inventory(
                db, company_id, line.product_id,
                int(item.quantity_received), po.number, actor_id,
            )
            _check_and_queue_reorder(db, company_id, line.product_id)

    # Auto-update PO status
    all_received = all(
        line.quantity_received >= line.quantity_ordered
        for line in po.lines
        if line.deleted_at is None
    )
    any_received = any(
        line.quantity_received > 0
        for line in po.lines
        if line.deleted_at is None
    )

    if all_received:
        po.status = "received"
    elif any_received:
        po.status = "partial"

    po.modified_by = actor_id
    po.modified_at = datetime.now(timezone.utc)

    audit_service.log_action(
        db, company_id, "received", "purchase_order", po.id,
        user_id=actor_id,
        changes={"status": po.status},
    )
    db.commit()
    return po


def cancel_purchase_order(
    db: Session, po_id: str, company_id: str, actor_id: str
) -> PurchaseOrder:
    po = get_purchase_order(db, po_id, company_id)
    # Soft-delete all lines
    now = datetime.now(timezone.utc)
    for line in po.lines:
        if line.deleted_at is None:
            line.deleted_at = now
    po.status = "cancelled"
    po.modified_by = actor_id
    po.modified_at = now

    audit_service.log_action(
        db, company_id, "cancelled", "purchase_order", po.id,
        user_id=actor_id,
    )
    db.commit()
    return po


def soft_delete_purchase_order(
    db: Session, po_id: str, company_id: str, actor_id: str
) -> None:
    po = get_purchase_order(db, po_id, company_id)
    if po.status != "draft":
        raise HTTPException(
            status_code=400,
            detail="Only draft POs can be deleted",
        )
    now = datetime.now(timezone.utc)
    po.deleted_at = now
    for line in po.lines:
        if line.deleted_at is None:
            line.deleted_at = now
    po.modified_by = actor_id
    po.modified_at = now

    audit_service.log_action(
        db, company_id, "deleted", "purchase_order", po.id,
        user_id=actor_id,
    )
    db.commit()


def get_po_stats(db: Session, company_id: str) -> dict:
    rows = (
        db.query(PurchaseOrder.status, func.count(PurchaseOrder.id))
        .filter(PurchaseOrder.company_id == company_id, _active_filter())
        .group_by(PurchaseOrder.status)
        .all()
    )
    counts = {r[0]: r[1] for r in rows}
    total = sum(counts.values())
    return {
        "total_pos": total,
        "draft": counts.get("draft", 0),
        "sent": counts.get("sent", 0),
        "partial": counts.get("partial", 0),
        "received": counts.get("received", 0),
        "closed": counts.get("closed", 0),
    }


# ---------------------------------------------------------------------------
# Inventory helper
# ---------------------------------------------------------------------------


def _update_inventory(
    db: Session,
    company_id: str,
    product_id: str,
    qty: int,
    reference: str,
    actor_id: str,
) -> None:
    """Increase inventory for a product when goods are received."""
    inv = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.company_id == company_id,
            InventoryItem.product_id == product_id,
        )
        .first()
    )
    if inv:
        old_qty = inv.quantity_on_hand
        inv.quantity_on_hand += qty
        inv.updated_at = datetime.now(timezone.utc)
        inv.modified_by = actor_id
    else:
        old_qty = 0
        inv = InventoryItem(
            id=str(uuid.uuid4()),
            company_id=company_id,
            product_id=product_id,
            quantity_on_hand=qty,
            created_by=actor_id,
        )
        db.add(inv)
    db.flush()

    # Record inventory transaction
    txn = InventoryTransaction(
        id=str(uuid.uuid4()),
        company_id=company_id,
        product_id=product_id,
        transaction_type="receive",
        quantity_change=qty,
        quantity_after=inv.quantity_on_hand,
        reference=f"PO Receiving: {reference}",
        created_by=actor_id,
    )
    db.add(txn)
    db.flush()


def _check_and_queue_reorder(db: Session, company_id: str, product_id: str | None) -> None:
    """Check if a reorder is needed after inventory changes. No-op if vault_inventory_service unavailable."""
    if not product_id:
        return
    try:
        from app.services.vault_inventory_service import check_reorder_needed
        check_reorder_needed(db, company_id, product_id)
    except Exception as e:
        logger.debug("Reorder check skipped: %s", e)
