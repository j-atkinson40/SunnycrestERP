from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.inventory_item import InventoryItem
from app.models.inventory_transaction import InventoryTransaction
from app.models.product import Product
from app.models.user import User
from app.services import audit_service, notification_service
from app.services.permission_service import user_has_permission


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _check_low_stock_and_notify(
    db: Session,
    item: InventoryItem,
    actor_id: str | None,
) -> None:
    """After any stock change, notify users if stock is at or below reorder point."""
    if item.reorder_point is None:
        return
    if item.quantity_on_hand > item.reorder_point:
        return

    product = db.query(Product).filter(Product.id == item.product_id).first()
    product_name = product.name if product else "Unknown product"

    users = (
        db.query(User)
        .filter(User.company_id == item.company_id, User.is_active == True)  # noqa: E712
        .all()
    )
    for user in users:
        if user_has_permission(user, db, "inventory.view"):
            notification_service.create_notification(
                db,
                item.company_id,
                user.id,
                title="Low Stock Alert",
                message=(
                    f"{product_name} is at {item.quantity_on_hand} units "
                    f"(reorder point: {item.reorder_point})."
                ),
                type="warning",
                category="inventory",
                link=f"/inventory/{item.product_id}",
                actor_id=actor_id,
            )


# ---------------------------------------------------------------------------
# Inventory item CRUD
# ---------------------------------------------------------------------------


def get_inventory_items(
    db: Session,
    company_id: str,
    page: int = 1,
    per_page: int = 20,
    search: str | None = None,
    low_stock_only: bool = False,
) -> dict:
    query = (
        db.query(InventoryItem)
        .join(Product, InventoryItem.product_id == Product.id)
        .filter(
            InventoryItem.company_id == company_id,
            Product.is_active == True,  # noqa: E712
        )
    )

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            Product.name.ilike(pattern) | Product.sku.ilike(pattern)
        )

    if low_stock_only:
        query = query.filter(
            InventoryItem.reorder_point.isnot(None),
            InventoryItem.quantity_on_hand <= InventoryItem.reorder_point,
        )

    total = query.count()
    items = (
        query.order_by(Product.name)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {"items": items, "total": total, "page": page, "per_page": per_page}


def get_inventory_item(
    db: Session, product_id: str, company_id: str
) -> InventoryItem:
    item = (
        db.query(InventoryItem)
        .filter(
            InventoryItem.product_id == product_id,
            InventoryItem.company_id == company_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found for this product",
        )
    return item


def create_inventory_item(
    db: Session, product_id: str, company_id: str
) -> InventoryItem:
    """Auto-create inventory item for a new product. Called from product_service."""
    item = InventoryItem(
        company_id=company_id,
        product_id=product_id,
        quantity_on_hand=0,
    )
    db.add(item)
    db.flush()
    return item


# ---------------------------------------------------------------------------
# Stock operations
# ---------------------------------------------------------------------------


def receive_stock(
    db: Session,
    product_id: str,
    quantity: int,
    company_id: str,
    actor_id: str | None = None,
    reference: str | None = None,
    notes: str | None = None,
) -> InventoryItem:
    item = get_inventory_item(db, product_id, company_id)
    old_qty = item.quantity_on_hand
    item.quantity_on_hand += quantity
    item.modified_by = actor_id

    tx = InventoryTransaction(
        company_id=company_id,
        product_id=product_id,
        transaction_type="receive",
        quantity_change=quantity,
        quantity_after=item.quantity_on_hand,
        reference=reference,
        notes=notes,
        created_by=actor_id,
    )
    db.add(tx)
    db.flush()

    audit_service.log_action(
        db,
        company_id,
        "stock_received",
        "inventory",
        product_id,
        user_id=actor_id,
        changes={"quantity_on_hand": {"old": old_qty, "new": item.quantity_on_hand}},
    )

    _check_low_stock_and_notify(db, item, actor_id)

    db.commit()
    db.refresh(item)
    return item


def adjust_stock(
    db: Session,
    product_id: str,
    new_quantity: int,
    company_id: str,
    actor_id: str | None = None,
    reference: str | None = None,
    notes: str | None = None,
) -> InventoryItem:
    item = get_inventory_item(db, product_id, company_id)
    old_qty = item.quantity_on_hand
    delta = new_quantity - old_qty
    item.quantity_on_hand = new_quantity
    item.modified_by = actor_id

    tx = InventoryTransaction(
        company_id=company_id,
        product_id=product_id,
        transaction_type="adjust",
        quantity_change=delta,
        quantity_after=new_quantity,
        reference=reference,
        notes=notes,
        created_by=actor_id,
    )
    db.add(tx)
    db.flush()

    audit_service.log_action(
        db,
        company_id,
        "stock_adjusted",
        "inventory",
        product_id,
        user_id=actor_id,
        changes={"quantity_on_hand": {"old": old_qty, "new": new_quantity}},
    )

    _check_low_stock_and_notify(db, item, actor_id)

    db.commit()
    db.refresh(item)
    return item


def record_production(
    db: Session,
    product_id: str,
    quantity: int,
    company_id: str,
    actor_id: str | None = None,
    reference: str | None = None,
    notes: str | None = None,
) -> InventoryItem:
    """Record production output — increases stock."""
    item = get_inventory_item(db, product_id, company_id)
    old_qty = item.quantity_on_hand
    item.quantity_on_hand += quantity
    item.modified_by = actor_id

    tx = InventoryTransaction(
        company_id=company_id,
        product_id=product_id,
        transaction_type="production",
        quantity_change=quantity,
        quantity_after=item.quantity_on_hand,
        reference=reference,
        notes=notes,
        created_by=actor_id,
    )
    db.add(tx)
    db.flush()

    audit_service.log_action(
        db,
        company_id,
        "production_recorded",
        "inventory",
        product_id,
        user_id=actor_id,
        changes={"quantity_on_hand": {"old": old_qty, "new": item.quantity_on_hand}},
    )

    _check_low_stock_and_notify(db, item, actor_id)

    db.commit()
    db.refresh(item)
    return item


def write_off_stock(
    db: Session,
    product_id: str,
    quantity: int,
    company_id: str,
    actor_id: str | None = None,
    reason: str = "",
    reference: str | None = None,
    notes: str | None = None,
) -> InventoryItem:
    """Write off damaged, expired, or lost stock — decreases quantity."""
    item = get_inventory_item(db, product_id, company_id)
    if item.quantity_on_hand < quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Insufficient stock to write off. Available: {item.quantity_on_hand}, "
                f"requested: {quantity}"
            ),
        )
    old_qty = item.quantity_on_hand
    item.quantity_on_hand -= quantity
    item.modified_by = actor_id

    full_notes = f"Reason: {reason}"
    if notes:
        full_notes += f". {notes}"

    tx = InventoryTransaction(
        company_id=company_id,
        product_id=product_id,
        transaction_type="write_off",
        quantity_change=-quantity,
        quantity_after=item.quantity_on_hand,
        reference=reference,
        notes=full_notes,
        created_by=actor_id,
    )
    db.add(tx)
    db.flush()

    audit_service.log_action(
        db,
        company_id,
        "stock_written_off",
        "inventory",
        product_id,
        user_id=actor_id,
        changes={"quantity_on_hand": {"old": old_qty, "new": item.quantity_on_hand}},
    )

    _check_low_stock_and_notify(db, item, actor_id)

    db.commit()
    db.refresh(item)
    return item


def batch_record_production(
    db: Session,
    entries: list[dict],
    company_id: str,
    actor_id: str | None = None,
    batch_reference: str | None = None,
) -> dict:
    """Record production for multiple products in one batch."""
    results = []
    success_count = 0
    failure_count = 0

    for entry in entries:
        ref = entry.get("reference") or batch_reference
        try:
            record_production(
                db,
                entry["product_id"],
                entry["quantity"],
                company_id,
                actor_id=actor_id,
                reference=ref,
                notes=entry.get("notes"),
            )
            results.append({
                "product_id": entry["product_id"],
                "success": True,
                "error": None,
            })
            success_count += 1
        except Exception as exc:
            results.append({
                "product_id": entry["product_id"],
                "success": False,
                "error": str(exc),
            })
            failure_count += 1

    return {
        "success_count": success_count,
        "failure_count": failure_count,
        "results": results,
    }


def record_sale(
    db: Session,
    product_id: str,
    quantity: int,
    company_id: str,
    actor_id: str | None = None,
    reference: str | None = None,
) -> InventoryItem:
    """Reduce stock for a sale. Used by the future sales module."""
    item = get_inventory_item(db, product_id, company_id)
    if item.quantity_on_hand < quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Insufficient stock. Available: {item.quantity_on_hand}, "
                f"requested: {quantity}"
            ),
        )
    old_qty = item.quantity_on_hand
    item.quantity_on_hand -= quantity
    item.modified_by = actor_id

    tx = InventoryTransaction(
        company_id=company_id,
        product_id=product_id,
        transaction_type="sell",
        quantity_change=-quantity,
        quantity_after=item.quantity_on_hand,
        reference=reference,
        created_by=actor_id,
    )
    db.add(tx)
    db.flush()

    audit_service.log_action(
        db,
        company_id,
        "stock_sold",
        "inventory",
        product_id,
        user_id=actor_id,
        changes={"quantity_on_hand": {"old": old_qty, "new": item.quantity_on_hand}},
    )

    _check_low_stock_and_notify(db, item, actor_id)

    db.commit()
    db.refresh(item)
    return item


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def update_inventory_settings(
    db: Session,
    product_id: str,
    company_id: str,
    reorder_point: int | None = None,
    reorder_quantity: int | None = None,
    location: str | None = None,
    actor_id: str | None = None,
) -> InventoryItem:
    item = get_inventory_item(db, product_id, company_id)

    old_data = {
        "reorder_point": item.reorder_point,
        "reorder_quantity": item.reorder_quantity,
        "location": item.location,
    }

    if reorder_point is not None:
        item.reorder_point = reorder_point
    if reorder_quantity is not None:
        item.reorder_quantity = reorder_quantity
    if location is not None:
        item.location = location
    item.modified_by = actor_id

    new_data = {
        "reorder_point": item.reorder_point,
        "reorder_quantity": item.reorder_quantity,
        "location": item.location,
    }
    changes = audit_service.compute_changes(old_data, new_data)
    if changes:
        audit_service.log_action(
            db,
            company_id,
            "updated",
            "inventory_settings",
            product_id,
            user_id=actor_id,
            changes=changes,
        )

    db.commit()
    db.refresh(item)
    return item


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------


def get_transactions(
    db: Session,
    company_id: str,
    product_id: str | None = None,
    transaction_type: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    query = db.query(InventoryTransaction).filter(
        InventoryTransaction.company_id == company_id
    )
    if product_id:
        query = query.filter(InventoryTransaction.product_id == product_id)
    if transaction_type:
        query = query.filter(InventoryTransaction.transaction_type == transaction_type)

    total = query.count()
    items = (
        query.order_by(InventoryTransaction.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {"items": items, "total": total, "page": page, "per_page": per_page}
