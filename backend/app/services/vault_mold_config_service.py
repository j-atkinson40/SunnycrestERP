"""Vault mold configuration service — tracks per-product daily production capacity."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.inventory_item import InventoryItem
from app.models.product import Product
from app.models.vault_mold_config import VaultMoldConfig

logger = logging.getLogger(__name__)


def get_mold_configs(db: Session, company_id: str) -> list[dict]:
    """Return all active mold configs for a tenant, joined with product and inventory data."""
    configs = (
        db.query(VaultMoldConfig, Product, InventoryItem)
        .join(Product, VaultMoldConfig.product_id == Product.id)
        .outerjoin(
            InventoryItem,
            (InventoryItem.product_id == Product.id)
            & (InventoryItem.company_id == VaultMoldConfig.company_id),
        )
        .filter(
            VaultMoldConfig.company_id == company_id,
            VaultMoldConfig.is_active.is_(True),
            Product.is_active.is_(True),
        )
        .all()
    )

    return [
        {
            "id": cfg.id,
            "product_id": cfg.product_id,
            "product_name": prod.name,
            "product_category": prod.product_line or "",
            "daily_capacity": cfg.daily_capacity,
            "is_active": cfg.is_active,
            "notes": cfg.notes,
            "current_stock": inv.quantity_on_hand if inv else 0,
            "spare_covers": inv.spare_covers if inv else 0,
            "spare_bases": inv.spare_bases if inv else 0,
        }
        for cfg, prod, inv in configs
    ]


def upsert_mold_configs(
    db: Session, company_id: str, configs: list[dict]
) -> list[VaultMoldConfig]:
    """Batch upsert mold configs. Each dict: {product_id, daily_capacity, is_active, notes}."""
    results = []
    for item in configs:
        existing = (
            db.query(VaultMoldConfig)
            .filter(
                VaultMoldConfig.company_id == company_id,
                VaultMoldConfig.product_id == item["product_id"],
            )
            .first()
        )
        if existing:
            existing.daily_capacity = item.get("daily_capacity", existing.daily_capacity)
            existing.is_active = item.get("is_active", existing.is_active)
            existing.notes = item.get("notes", existing.notes)
            existing.updated_at = datetime.now(timezone.utc)
            results.append(existing)
        else:
            new_cfg = VaultMoldConfig(
                id=str(uuid.uuid4()),
                company_id=company_id,
                product_id=item["product_id"],
                daily_capacity=item.get("daily_capacity", 1),
                is_active=item.get("is_active", True),
                notes=item.get("notes"),
            )
            db.add(new_cfg)
            results.append(new_cfg)

    db.commit()
    for r in results:
        db.refresh(r)
    return results


def get_daily_capacity_summary(db: Session, company_id: str) -> list[dict]:
    """Return per-product daily capacity for the production log UI."""
    configs = (
        db.query(VaultMoldConfig, Product, InventoryItem)
        .join(Product, VaultMoldConfig.product_id == Product.id)
        .outerjoin(
            InventoryItem,
            (InventoryItem.product_id == Product.id)
            & (InventoryItem.company_id == VaultMoldConfig.company_id),
        )
        .filter(
            VaultMoldConfig.company_id == company_id,
            VaultMoldConfig.is_active.is_(True),
            Product.is_active.is_(True),
        )
        .order_by(Product.name)
        .all()
    )

    return [
        {
            "product_id": prod.id,
            "product_name": prod.name,
            "daily_capacity": cfg.daily_capacity,
            "current_stock": inv.quantity_on_hand if inv else 0,
            "spare_covers": inv.spare_covers if inv else 0,
            "spare_bases": inv.spare_bases if inv else 0,
        }
        for cfg, prod, inv in configs
    ]


def validate_production_entry(
    db: Session, company_id: str, entries: list[dict]
) -> dict:
    """Validate production entries against mold capacity.

    Only validates complete pours — partial pours (cover/base) are exceptions
    and are not subject to capacity limits.

    entries: [{product_id, quantity, component_type}]
    Returns: {valid: bool, errors: [str]}
    """
    errors = []
    for entry in entries:
        if entry.get("component_type", "complete") != "complete":
            continue

        product_id = entry.get("product_id")
        quantity = entry.get("quantity", 0)
        if not product_id or quantity <= 0:
            continue

        config = (
            db.query(VaultMoldConfig)
            .filter(
                VaultMoldConfig.company_id == company_id,
                VaultMoldConfig.product_id == product_id,
                VaultMoldConfig.is_active.is_(True),
            )
            .first()
        )
        if config and quantity > config.daily_capacity:
            product = db.query(Product).filter(Product.id == product_id).first()
            name = product.name if product else product_id
            errors.append(
                f"{name}: quantity {quantity} exceeds daily capacity of {config.daily_capacity}"
            )

    return {"valid": len(errors) == 0, "errors": errors}
