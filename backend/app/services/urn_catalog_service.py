"""Service layer for the Urn Catalog Manager."""

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func as sa_func, or_
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.product_category import ProductCategory

logger = logging.getLogger(__name__)


def list_urns(
    db: Session,
    tenant_id: str,
    active_only: bool = True,
    limit: int = 500,
    offset: int = 0,
) -> list[Product]:
    """List urn products for the tenant."""
    query = db.query(Product).filter(Product.company_id == tenant_id)

    # Urns are products imported via wilbert_import, or with an urn-related category
    query = query.filter(
        or_(
            Product.source == "wilbert_import",
            Product.wilbert_sku.isnot(None),
        )
    )

    if active_only:
        query = query.filter(Product.is_active == True)  # noqa: E712

    return query.order_by(Product.name).offset(offset).limit(limit).all()


def get_urn_stats(db: Session, tenant_id: str) -> dict:
    """Active count, inactive count, imported count, last import timestamp."""
    base = db.query(Product).filter(
        Product.company_id == tenant_id,
        or_(
            Product.source == "wilbert_import",
            Product.wilbert_sku.isnot(None),
        ),
    )

    active_count = base.filter(Product.is_active == True).count()  # noqa: E712
    inactive_count = base.filter(Product.is_active == False).count()  # noqa: E712
    imported_count = base.filter(Product.source == "wilbert_import").count()

    last_import_at = (
        base.filter(Product.source == "wilbert_import")
        .with_entities(sa_func.max(Product.created_at))
        .scalar()
    )

    return {
        "active_count": active_count,
        "inactive_count": inactive_count,
        "imported_count": imported_count,
        "last_import_at": last_import_at,
    }


def bulk_import_urns(
    db: Session,
    tenant_id: str,
    user_id: str,
    urns: list,
    markup_percent: float | None = None,
    rounding: str = "1.00",
) -> dict:
    """Import urns from Wilbert price list.

    - Match existing by wilbert_sku (exact, trimmed)
    - Existing: update wholesale_cost only (preserve selling price)
    - New: create product with wholesale_cost and calculated selling price
    - Single transaction
    - Returns {created, updated, total, errors}
    """
    created = 0
    updated = 0
    errors: list[dict] = []

    for idx, urn in enumerate(urns):
        try:
            sku = urn.wilbert_sku.strip()
            if not sku:
                errors.append({"index": idx, "error": "Empty wilbert_sku"})
                continue

            existing = (
                db.query(Product)
                .filter(
                    Product.company_id == tenant_id,
                    Product.wilbert_sku == sku,
                )
                .first()
            )

            if existing:
                existing.wholesale_cost = Decimal(str(urn.wholesale_cost))
                existing.modified_by = user_id
                existing.updated_at = datetime.now(timezone.utc)
                updated += 1
            else:
                # Calculate selling price
                selling_price = urn.selling_price
                if selling_price is None and markup_percent is not None:
                    selling_price = calculate_selling_price(
                        urn.wholesale_cost, markup_percent, rounding
                    )

                product = Product(
                    company_id=tenant_id,
                    name=urn.name.strip(),
                    wilbert_sku=sku,
                    wholesale_cost=Decimal(str(urn.wholesale_cost)),
                    price=Decimal(str(selling_price)) if selling_price else None,
                    markup_percent=(
                        Decimal(str(markup_percent)) if markup_percent else None
                    ),
                    source="wilbert_import",
                    is_active=True,
                    created_by=user_id,
                    modified_by=user_id,
                    description=urn.size or None,
                )
                db.add(product)
                created += 1

        except Exception as exc:
            logger.warning("Error importing urn index %d: %s", idx, exc)
            errors.append({"index": idx, "error": str(exc)})

    db.flush()

    return {
        "created": created,
        "updated": updated,
        "total": created + updated,
        "errors": errors,
    }


def calculate_selling_price(
    wholesale: float, markup_pct: float, rounding: str = "1.00"
) -> float:
    """Calculate selling price with markup and rounding."""
    raw = wholesale * (1 + markup_pct / 100)
    r = float(rounding)
    if r >= 1:
        return round(raw / r) * r
    return round(raw, 2)


def deactivate_urn(db: Session, tenant_id: str, product_id: str) -> bool:
    """Set is_active = False on a product."""
    product = (
        db.query(Product)
        .filter(
            Product.id == product_id,
            Product.company_id == tenant_id,
        )
        .first()
    )
    if not product:
        return False
    product.is_active = False
    product.updated_at = datetime.now(timezone.utc)
    db.flush()
    return True


def activate_urn(db: Session, tenant_id: str, product_id: str) -> bool:
    """Set is_active = True on a product."""
    product = (
        db.query(Product)
        .filter(
            Product.id == product_id,
            Product.company_id == tenant_id,
        )
        .first()
    )
    if not product:
        return False
    product.is_active = True
    product.updated_at = datetime.now(timezone.utc)
    db.flush()
    return True


def create_urn(
    db: Session,
    tenant_id: str,
    user_id: str,
    *,
    name: str,
    wilbert_sku: str | None = None,
    wholesale_cost: float | None = None,
    price: float | None = None,
    markup_percent: float | None = None,
    category: str | None = None,
    description: str | None = None,
) -> Product:
    """Create a single urn product manually."""
    product = Product(
        company_id=tenant_id,
        name=name.strip(),
        wilbert_sku=wilbert_sku.strip() if wilbert_sku else None,
        wholesale_cost=Decimal(str(wholesale_cost)) if wholesale_cost else None,
        price=Decimal(str(price)) if price else None,
        markup_percent=Decimal(str(markup_percent)) if markup_percent else None,
        source="wilbert_import" if wilbert_sku else "manual",
        description=description,
        is_active=True,
        created_by=user_id,
        modified_by=user_id,
    )
    db.add(product)
    db.flush()
    return product
