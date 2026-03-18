"""Daily production log service — CRUD for production entries with inventory integration."""

import json
import logging
from datetime import date, datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.production_log_entry import ProductionLogEntry
from app.models.production_log_summary import ProductionLogSummary
from app.models.product import Product

logger = logging.getLogger(__name__)


def list_entries(
    db: Session,
    tenant_id: str,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    product_id: str | None = None,
    entered_by: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[ProductionLogEntry]:
    """List production log entries with optional filters. Default: current month."""
    q = db.query(ProductionLogEntry).filter(ProductionLogEntry.tenant_id == tenant_id)

    if start_date:
        q = q.filter(ProductionLogEntry.log_date >= start_date)
    elif not end_date:
        # Default to current month
        today = date.today()
        q = q.filter(ProductionLogEntry.log_date >= today.replace(day=1))

    if end_date:
        q = q.filter(ProductionLogEntry.log_date <= end_date)
    if product_id:
        q = q.filter(ProductionLogEntry.product_id == product_id)
    if entered_by:
        q = q.filter(ProductionLogEntry.entered_by == entered_by)

    return (
        q.order_by(ProductionLogEntry.log_date.desc(), ProductionLogEntry.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_today_entries(db: Session, tenant_id: str) -> list[ProductionLogEntry]:
    """Get all entries for today."""
    today = date.today()
    return (
        db.query(ProductionLogEntry)
        .filter(
            ProductionLogEntry.tenant_id == tenant_id,
            ProductionLogEntry.log_date == today,
        )
        .order_by(ProductionLogEntry.created_at.desc())
        .all()
    )


def get_today_total(db: Session, tenant_id: str) -> int:
    """Get total units produced today."""
    today = date.today()
    result = (
        db.query(func.coalesce(func.sum(ProductionLogEntry.quantity_produced), 0))
        .filter(
            ProductionLogEntry.tenant_id == tenant_id,
            ProductionLogEntry.log_date == today,
        )
        .scalar()
    )
    return int(result)


def create_entry(
    db: Session,
    tenant_id: str,
    entered_by: str,
    *,
    product_id: str,
    quantity_produced: int,
    log_date: date | None = None,
    mix_design_id: str | None = None,
    batch_count: int | None = None,
    notes: str | None = None,
    entry_method: str = "manual",
) -> ProductionLogEntry:
    """Create a production log entry and update inventory.

    Inventory update is synchronous -- if it fails, the entry is not saved.
    """
    # Look up product for denormalized name
    product = (
        db.query(Product)
        .filter(Product.id == product_id, Product.company_id == tenant_id)
        .first()
    )
    if not product:
        raise ValueError(f"Product {product_id} not found")

    # Look up mix design name if provided
    mix_design_name = None
    if mix_design_id:
        try:
            from app.models.mix_design import MixDesign

            md = db.query(MixDesign).filter(MixDesign.id == mix_design_id).first()
            if md:
                mix_design_name = md.name
        except ImportError:
            pass  # MixDesign model may not exist

    entry = ProductionLogEntry(
        tenant_id=tenant_id,
        log_date=log_date or date.today(),
        product_id=product_id,
        product_name=product.name,
        quantity_produced=quantity_produced,
        mix_design_id=mix_design_id,
        mix_design_name=mix_design_name,
        batch_count=batch_count,
        notes=notes,
        entered_by=entered_by,
        entry_method=entry_method,
    )
    db.add(entry)

    # Update inventory -- synchronous, same transaction
    _adjust_inventory(db, tenant_id, product_id, quantity_produced, entry.id, "add")

    db.flush()

    # Update daily summary
    _update_summary(db, tenant_id, entry.log_date)

    # Fire onboarding hook
    try:
        from app.services.onboarding_hooks import on_product_created
        # Check completion for production log scenario if applicable
    except Exception:
        pass

    db.commit()
    db.refresh(entry)
    return entry


def update_entry(
    db: Session,
    tenant_id: str,
    entry_id: str,
    **kwargs,
) -> ProductionLogEntry:
    """Update a production log entry. Adjusts inventory by the delta if quantity changed."""
    entry = (
        db.query(ProductionLogEntry)
        .filter(
            ProductionLogEntry.id == entry_id,
            ProductionLogEntry.tenant_id == tenant_id,
        )
        .first()
    )
    if not entry:
        raise ValueError("Entry not found")

    old_quantity = entry.quantity_produced

    if "quantity_produced" in kwargs and kwargs["quantity_produced"] is not None:
        new_quantity = kwargs["quantity_produced"]
        delta = new_quantity - old_quantity
        if delta != 0:
            action = "add" if delta > 0 else "subtract"
            _adjust_inventory(db, tenant_id, entry.product_id, abs(delta), entry.id, action)
        entry.quantity_produced = new_quantity

    if "mix_design_id" in kwargs:
        entry.mix_design_id = kwargs["mix_design_id"]
        # Look up name
        if kwargs["mix_design_id"]:
            try:
                from app.models.mix_design import MixDesign

                md = db.query(MixDesign).filter(MixDesign.id == kwargs["mix_design_id"]).first()
                entry.mix_design_name = md.name if md else None
            except ImportError:
                pass
        else:
            entry.mix_design_name = kwargs.get("mix_design_name")

    if "batch_count" in kwargs:
        entry.batch_count = kwargs["batch_count"]
    if "notes" in kwargs:
        entry.notes = kwargs["notes"]

    entry.updated_at = datetime.now(timezone.utc)

    _update_summary(db, tenant_id, entry.log_date)

    db.commit()
    db.refresh(entry)
    return entry


def delete_entry(db: Session, tenant_id: str, entry_id: str) -> bool:
    """Delete a production log entry and reverse inventory adjustment."""
    entry = (
        db.query(ProductionLogEntry)
        .filter(
            ProductionLogEntry.id == entry_id,
            ProductionLogEntry.tenant_id == tenant_id,
        )
        .first()
    )
    if not entry:
        return False

    # Reverse inventory
    _adjust_inventory(db, tenant_id, entry.product_id, entry.quantity_produced, entry.id, "subtract")

    log_date = entry.log_date
    db.delete(entry)

    _update_summary(db, tenant_id, log_date)

    db.commit()
    return True


def get_summaries(
    db: Session,
    tenant_id: str,
    start_date: date,
    end_date: date,
) -> list[ProductionLogSummary]:
    """Get daily summaries for a date range."""
    return (
        db.query(ProductionLogSummary)
        .filter(
            ProductionLogSummary.tenant_id == tenant_id,
            ProductionLogSummary.summary_date >= start_date,
            ProductionLogSummary.summary_date <= end_date,
        )
        .order_by(ProductionLogSummary.summary_date.desc())
        .all()
    )


def _adjust_inventory(
    db: Session,
    tenant_id: str,
    product_id: str,
    quantity: int,
    reference_id: str,
    action: str,  # "add" or "subtract"
) -> None:
    """Adjust inventory for a product. Synchronous, in the same transaction.

    Uses the InventoryItem model if it exists, otherwise updates product.stock_quantity directly.
    """
    try:
        from app.models.inventory_item import InventoryItem

        inv = (
            db.query(InventoryItem)
            .filter(
                InventoryItem.company_id == tenant_id,
                InventoryItem.product_id == product_id,
            )
            .first()
        )
        if inv:
            if action == "add":
                inv.quantity_on_hand = (inv.quantity_on_hand or 0) + quantity
            else:
                inv.quantity_on_hand = max(0, (inv.quantity_on_hand or 0) - quantity)
            inv.updated_at = datetime.now(timezone.utc)
        else:
            # Create inventory record
            if action == "add":
                new_inv = InventoryItem(
                    company_id=tenant_id,
                    product_id=product_id,
                    quantity_on_hand=quantity,
                )
                db.add(new_inv)
    except ImportError:
        # Fallback: try updating product directly
        product = db.query(Product).filter(Product.id == product_id).first()
        if product and hasattr(product, "stock_quantity"):
            if action == "add":
                product.stock_quantity = (product.stock_quantity or 0) + quantity
            else:
                product.stock_quantity = max(0, (product.stock_quantity or 0) - quantity)

    # Log the adjustment
    try:
        from app.services import audit_service

        audit_service.log_action(
            db,
            tenant_id,
            "inventory_adjusted" if action == "add" else "inventory_reduced",
            "production_log_entry",
            reference_id,
            changes={"product_id": product_id, "quantity": quantity, "action": action, "source": "production_log"},
        )
    except Exception:
        logger.warning("Failed to log inventory adjustment audit")


def _update_summary(db: Session, tenant_id: str, summary_date: date) -> None:
    """Recalculate the daily summary for a given date."""
    entries = (
        db.query(ProductionLogEntry)
        .filter(
            ProductionLogEntry.tenant_id == tenant_id,
            ProductionLogEntry.log_date == summary_date,
        )
        .all()
    )

    total = sum(e.quantity_produced for e in entries)
    products = {}
    for e in entries:
        if e.product_id in products:
            products[e.product_id]["quantity"] += e.quantity_produced
        else:
            products[e.product_id] = {
                "product_id": e.product_id,
                "product_name": e.product_name,
                "quantity": e.quantity_produced,
            }

    summary = (
        db.query(ProductionLogSummary)
        .filter(
            ProductionLogSummary.tenant_id == tenant_id,
            ProductionLogSummary.summary_date == summary_date,
        )
        .first()
    )

    if summary:
        summary.total_units_produced = total
        summary.products_produced = json.dumps(list(products.values()))
        summary.recalculated_at = datetime.now(timezone.utc)
    else:
        if total > 0:
            summary = ProductionLogSummary(
                tenant_id=tenant_id,
                summary_date=summary_date,
                total_units_produced=total,
                products_produced=json.dumps(list(products.values())),
                recalculated_at=datetime.now(timezone.utc),
            )
            db.add(summary)
