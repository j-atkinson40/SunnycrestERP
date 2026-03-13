import csv
import io
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.product_category import ProductCategory
from app.models.product_price_tier import ProductPriceTier
from app.schemas.product import (
    PriceTierCreate,
    PriceTierUpdate,
    ProductCategoryCreate,
    ProductCategoryUpdate,
    ProductCreate,
    ProductUpdate,
)
from app.services import audit_service
from app.services.inventory_service import create_inventory_item
from app.services.sync_log_service import complete_sync_log, create_sync_log


# ---------------------------------------------------------------------------
# Category helpers
# ---------------------------------------------------------------------------


def get_categories(
    db: Session,
    company_id: str,
    include_inactive: bool = False,
    parent_id: str | None = "__unset__",
) -> list[ProductCategory]:
    query = db.query(ProductCategory).filter(
        ProductCategory.company_id == company_id
    )
    if not include_inactive:
        query = query.filter(ProductCategory.is_active == True)  # noqa: E712
    # Filter by parent_id only if explicitly passed (not the default sentinel)
    if parent_id != "__unset__":
        query = query.filter(ProductCategory.parent_id == parent_id)
    return query.order_by(ProductCategory.parent_id.nulls_first(), ProductCategory.name).all()


def get_category(
    db: Session, category_id: str, company_id: str
) -> ProductCategory:
    cat = (
        db.query(ProductCategory)
        .filter(
            ProductCategory.id == category_id,
            ProductCategory.company_id == company_id,
        )
        .first()
    )
    if not cat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        )
    return cat


def create_category(
    db: Session,
    data: ProductCategoryCreate,
    company_id: str,
    actor_id: str | None = None,
) -> ProductCategory:
    # Validate parent if provided
    if data.parent_id:
        parent = get_category(db, data.parent_id, company_id)
        # Only allow two levels — parent must be a root category
        if parent.parent_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subcategories can only be one level deep",
            )

    # Check uniqueness scoped to same parent
    existing = (
        db.query(ProductCategory)
        .filter(
            ProductCategory.name == data.name,
            ProductCategory.company_id == company_id,
            ProductCategory.parent_id == data.parent_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A category with this name already exists",
        )

    cat = ProductCategory(
        company_id=company_id,
        name=data.name,
        description=data.description,
        parent_id=data.parent_id,
        created_by=actor_id,
    )
    db.add(cat)
    db.flush()

    audit_service.log_action(
        db,
        company_id,
        "created",
        "product_category",
        cat.id,
        user_id=actor_id,
        changes={"name": data.name, "parent_id": data.parent_id},
    )

    db.commit()
    db.refresh(cat)
    return cat


def update_category(
    db: Session,
    category_id: str,
    data: ProductCategoryUpdate,
    company_id: str,
    actor_id: str | None = None,
) -> ProductCategory:
    cat = get_category(db, category_id, company_id)

    old_data = {"name": cat.name, "description": cat.description, "is_active": cat.is_active}

    update_data = data.model_dump(exclude_unset=True)

    # Check uniqueness if name is changing (scoped to same parent)
    if "name" in update_data and update_data["name"] != cat.name:
        existing = (
            db.query(ProductCategory)
            .filter(
                ProductCategory.name == update_data["name"],
                ProductCategory.company_id == company_id,
                ProductCategory.parent_id == cat.parent_id,
                ProductCategory.id != category_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A category with this name already exists",
            )

    for field, value in update_data.items():
        setattr(cat, field, value)
    cat.modified_by = actor_id

    new_data = {"name": cat.name, "description": cat.description, "is_active": cat.is_active}
    changes = audit_service.compute_changes(old_data, new_data)
    if changes:
        audit_service.log_action(
            db,
            company_id,
            "updated",
            "product_category",
            cat.id,
            user_id=actor_id,
            changes=changes,
        )

    db.commit()
    db.refresh(cat)
    return cat


def deactivate_category(
    db: Session,
    category_id: str,
    company_id: str,
    actor_id: str | None = None,
) -> ProductCategory:
    cat = get_category(db, category_id, company_id)
    cat.is_active = False

    audit_service.log_action(
        db,
        company_id,
        "deactivated",
        "product_category",
        cat.id,
        user_id=actor_id,
        changes={"is_active": {"old": True, "new": False}},
    )

    db.commit()
    db.refresh(cat)
    return cat


# ---------------------------------------------------------------------------
# Product helpers
# ---------------------------------------------------------------------------


def _validate_category_id(
    db: Session, category_id: str, company_id: str
) -> None:
    """Ensure the category belongs to the same company and is active."""
    cat = (
        db.query(ProductCategory)
        .filter(
            ProductCategory.id == category_id,
            ProductCategory.company_id == company_id,
        )
        .first()
    )
    if not cat:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid category for this company",
        )


def get_products(
    db: Session,
    company_id: str,
    page: int = 1,
    per_page: int = 20,
    search: str | None = None,
    category_id: str | None = None,
    include_inactive: bool = False,
) -> dict:
    query = db.query(Product).filter(Product.company_id == company_id)

    if not include_inactive:
        query = query.filter(Product.is_active == True)  # noqa: E712

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            Product.name.ilike(pattern) | Product.sku.ilike(pattern)
        )

    if category_id:
        query = query.filter(Product.category_id == category_id)

    total = query.count()
    products = (
        query.order_by(Product.name)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {"items": products, "total": total, "page": page, "per_page": per_page}


def get_product(db: Session, product_id: str, company_id: str) -> Product:
    product = (
        db.query(Product)
        .filter(Product.id == product_id, Product.company_id == company_id)
        .first()
    )
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )
    return product


def create_product(
    db: Session,
    data: ProductCreate,
    company_id: str,
    actor_id: str | None = None,
) -> Product:
    # Validate category if provided
    if data.category_id:
        _validate_category_id(db, data.category_id, company_id)

    # Check SKU uniqueness if provided
    if data.sku:
        existing = (
            db.query(Product)
            .filter(Product.sku == data.sku, Product.company_id == company_id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A product with this SKU already exists",
            )

    product = Product(
        company_id=company_id,
        category_id=data.category_id,
        name=data.name,
        sku=data.sku,
        description=data.description,
        price=data.price,
        cost_price=data.cost_price,
        unit_of_measure=data.unit_of_measure,
        image_url=data.image_url,
        created_by=actor_id,
    )
    db.add(product)
    db.flush()

    audit_service.log_action(
        db,
        company_id,
        "created",
        "product",
        product.id,
        user_id=actor_id,
        changes={"name": data.name, "sku": data.sku},
    )

    # Auto-create inventory item with quantity 0
    create_inventory_item(db, product.id, company_id)

    db.commit()
    db.refresh(product)
    return product


def update_product(
    db: Session,
    product_id: str,
    data: ProductUpdate,
    company_id: str,
    actor_id: str | None = None,
) -> Product:
    product = get_product(db, product_id, company_id)

    old_data = {
        "name": product.name,
        "sku": product.sku,
        "description": product.description,
        "category_id": product.category_id,
        "price": str(product.price) if product.price is not None else None,
        "cost_price": str(product.cost_price) if product.cost_price is not None else None,
        "unit_of_measure": product.unit_of_measure,
        "image_url": product.image_url,
        "is_active": product.is_active,
    }

    update_data = data.model_dump(exclude_unset=True)

    # Validate category if changing
    if "category_id" in update_data and update_data["category_id"]:
        _validate_category_id(db, update_data["category_id"], company_id)

    # Check SKU uniqueness if changing
    if "sku" in update_data and update_data["sku"]:
        existing = (
            db.query(Product)
            .filter(
                Product.sku == update_data["sku"],
                Product.company_id == company_id,
                Product.id != product_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A product with this SKU already exists",
            )

    for field, value in update_data.items():
        setattr(product, field, value)
    product.modified_by = actor_id

    new_data = {
        "name": product.name,
        "sku": product.sku,
        "description": product.description,
        "category_id": product.category_id,
        "price": str(product.price) if product.price is not None else None,
        "cost_price": str(product.cost_price) if product.cost_price is not None else None,
        "unit_of_measure": product.unit_of_measure,
        "image_url": product.image_url,
        "is_active": product.is_active,
    }
    changes = audit_service.compute_changes(old_data, new_data)
    if changes:
        audit_service.log_action(
            db,
            company_id,
            "updated",
            "product",
            product.id,
            user_id=actor_id,
            changes=changes,
        )

    db.commit()
    db.refresh(product)
    return product


def deactivate_product(
    db: Session,
    product_id: str,
    company_id: str,
    actor_id: str | None = None,
) -> Product:
    product = get_product(db, product_id, company_id)
    product.is_active = False

    audit_service.log_action(
        db,
        company_id,
        "deactivated",
        "product",
        product.id,
        user_id=actor_id,
        changes={"is_active": {"old": True, "new": False}},
    )

    db.commit()
    db.refresh(product)
    return product


# ---------------------------------------------------------------------------
# Price Tier helpers
# ---------------------------------------------------------------------------


def get_price_tiers(
    db: Session, product_id: str, company_id: str
) -> list[ProductPriceTier]:
    # Validate product exists
    get_product(db, product_id, company_id)
    return (
        db.query(ProductPriceTier)
        .filter(
            ProductPriceTier.product_id == product_id,
            ProductPriceTier.company_id == company_id,
            ProductPriceTier.is_active == True,  # noqa: E712
        )
        .order_by(ProductPriceTier.min_quantity)
        .all()
    )


def create_price_tier(
    db: Session,
    product_id: str,
    data: PriceTierCreate,
    company_id: str,
    actor_id: str | None = None,
) -> ProductPriceTier:
    # Validate product exists
    get_product(db, product_id, company_id)

    # Check no duplicate min_quantity among active tiers
    existing = (
        db.query(ProductPriceTier)
        .filter(
            ProductPriceTier.product_id == product_id,
            ProductPriceTier.min_quantity == data.min_quantity,
            ProductPriceTier.is_active == True,  # noqa: E712
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A pricing tier for quantity {data.min_quantity}+ already exists",
        )

    tier = ProductPriceTier(
        product_id=product_id,
        company_id=company_id,
        min_quantity=data.min_quantity,
        price=data.price,
        label=data.label,
        created_by=actor_id,
    )
    db.add(tier)
    db.flush()

    audit_service.log_action(
        db,
        company_id,
        "created",
        "product_price_tier",
        tier.id,
        user_id=actor_id,
        changes={
            "product_id": product_id,
            "min_quantity": data.min_quantity,
            "price": str(data.price),
            "label": data.label,
        },
    )

    db.commit()
    db.refresh(tier)
    return tier


def update_price_tier(
    db: Session,
    tier_id: str,
    data: PriceTierUpdate,
    company_id: str,
    actor_id: str | None = None,
) -> ProductPriceTier:
    tier = (
        db.query(ProductPriceTier)
        .filter(
            ProductPriceTier.id == tier_id,
            ProductPriceTier.company_id == company_id,
        )
        .first()
    )
    if not tier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Price tier not found"
        )

    old_data = {
        "min_quantity": tier.min_quantity,
        "price": str(tier.price),
        "label": tier.label,
    }

    update_data = data.model_dump(exclude_unset=True)

    # Check uniqueness if min_quantity is changing
    if "min_quantity" in update_data and update_data["min_quantity"] != tier.min_quantity:
        existing = (
            db.query(ProductPriceTier)
            .filter(
                ProductPriceTier.product_id == tier.product_id,
                ProductPriceTier.min_quantity == update_data["min_quantity"],
                ProductPriceTier.id != tier_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A pricing tier for quantity {update_data['min_quantity']}+ already exists",
            )

    for field, value in update_data.items():
        setattr(tier, field, value)
    tier.modified_by = actor_id

    new_data = {
        "min_quantity": tier.min_quantity,
        "price": str(tier.price),
        "label": tier.label,
    }
    changes = audit_service.compute_changes(old_data, new_data)
    if changes:
        audit_service.log_action(
            db,
            company_id,
            "updated",
            "product_price_tier",
            tier.id,
            user_id=actor_id,
            changes=changes,
        )

    db.commit()
    db.refresh(tier)
    return tier


def delete_price_tier(
    db: Session,
    tier_id: str,
    company_id: str,
    actor_id: str | None = None,
) -> None:
    tier = (
        db.query(ProductPriceTier)
        .filter(
            ProductPriceTier.id == tier_id,
            ProductPriceTier.company_id == company_id,
        )
        .first()
    )
    if not tier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Price tier not found"
        )

    tier.is_active = False
    tier.modified_by = actor_id

    audit_service.log_action(
        db,
        company_id,
        "deactivated",
        "product_price_tier",
        tier.id,
        user_id=actor_id,
        changes={
            "is_active": {"old": True, "new": False},
            "product_id": tier.product_id,
            "min_quantity": tier.min_quantity,
            "price": str(tier.price),
        },
    )

    db.commit()


# ---------------------------------------------------------------------------
# CSV Import
# ---------------------------------------------------------------------------

# Mapping of flexible header names → canonical field names
_HEADER_MAP: dict[str, str] = {
    "name": "name",
    "product name": "name",
    "product_name": "name",
    "sku": "sku",
    "item number": "sku",
    "item_number": "sku",
    "description": "description",
    "category": "category",
    "product category": "category",
    "product_category": "category",
    "price": "price",
    "selling price": "price",
    "selling_price": "price",
    "cost price": "cost_price",
    "cost_price": "cost_price",
    "cost": "cost_price",
    "unit of measure": "unit_of_measure",
    "unit_of_measure": "unit_of_measure",
    "uom": "unit_of_measure",
    "unit": "unit_of_measure",
}


def _normalise_headers(raw_headers: list[str]) -> dict[str, str]:
    """Map raw CSV headers to canonical field names."""
    mapping: dict[str, str] = {}
    for h in raw_headers:
        key = h.strip().lower()
        if key in _HEADER_MAP:
            mapping[h] = _HEADER_MAP[key]
    return mapping


def _resolve_category(
    db: Session, name: str, company_id: str, cache: dict[str, str]
) -> str | None:
    """Look up or auto-create a category by name. Uses a cache to avoid repeat queries."""
    key = name.strip().lower()
    if not key:
        return None
    if key in cache:
        return cache[key]

    cat = (
        db.query(ProductCategory)
        .filter(
            ProductCategory.company_id == company_id,
            ProductCategory.name.ilike(key),
            ProductCategory.parent_id.is_(None),
        )
        .first()
    )
    if not cat:
        # Auto-create as a root category
        cat = ProductCategory(company_id=company_id, name=name.strip())
        db.add(cat)
        db.flush()
    cache[key] = cat.id
    return cat.id


def import_products_from_csv(
    db: Session,
    file_content: bytes,
    company_id: str,
    actor_id: str | None = None,
) -> dict:
    """Parse a CSV file and bulk-create products.

    Returns {"created": int, "skipped": int, "errors": [{"row": int, "message": str}]}
    """
    # Create sync log entry for this import
    sync_log = create_sync_log(
        db,
        company_id,
        sync_type="csv_import",
        source="csv_file",
        destination="products",
    )

    try:
        text = file_content.decode("utf-8-sig")  # handles BOM from Excel
    except UnicodeDecodeError:
        text = file_content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file is empty or has no headers",
        )

    header_map = _normalise_headers(list(reader.fieldnames))
    if "name" not in header_map.values():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV must contain a 'name' or 'Product Name' column",
        )

    errors: list[dict[str, object]] = []
    created = 0
    skipped = 0
    category_cache: dict[str, str] = {}

    # Pre-load existing SKUs for this company for fast duplicate checking
    existing_skus: set[str] = {
        s[0].upper()
        for s in db.query(Product.sku)
        .filter(Product.company_id == company_id, Product.sku.isnot(None))
        .all()
    }

    for row_num, raw_row in enumerate(reader, start=2):  # row 1 = headers
        # Map raw headers to canonical names
        row: dict[str, str] = {}
        for raw_key, value in raw_row.items():
            canonical = header_map.get(raw_key)
            if canonical:
                row[canonical] = (value or "").strip()

        name = row.get("name", "").strip()
        if not name:
            errors.append({"row": row_num, "message": "Missing product name"})
            skipped += 1
            continue

        sku = row.get("sku", "").strip() or None
        if sku and sku.upper() in existing_skus:
            errors.append({"row": row_num, "message": f"Duplicate SKU: {sku}"})
            skipped += 1
            continue

        # Parse prices
        price = None
        cost_price = None
        try:
            if row.get("price"):
                price = Decimal(row["price"].replace(",", "").replace("$", ""))
        except (InvalidOperation, ValueError):
            errors.append({"row": row_num, "message": f"Invalid price value: {row.get('price')}"})
            skipped += 1
            continue

        try:
            if row.get("cost_price"):
                cost_price = Decimal(row["cost_price"].replace(",", "").replace("$", ""))
        except (InvalidOperation, ValueError):
            errors.append({"row": row_num, "message": f"Invalid cost price value: {row.get('cost_price')}"})
            skipped += 1
            continue

        # Resolve category
        category_id = None
        cat_name = row.get("category", "").strip()
        if cat_name:
            category_id = _resolve_category(db, cat_name, company_id, category_cache)

        product = Product(
            company_id=company_id,
            name=name,
            sku=sku,
            description=row.get("description", "").strip() or None,
            category_id=category_id,
            price=price,
            cost_price=cost_price,
            unit_of_measure=row.get("unit_of_measure", "").strip() or None,
            created_by=actor_id,
        )
        db.add(product)
        db.flush()

        # Auto-create inventory item
        create_inventory_item(db, product.id, company_id)

        if sku:
            existing_skus.add(sku.upper())
        created += 1

    if created > 0:
        audit_service.log_action(
            db,
            company_id,
            "bulk_imported",
            "product",
            None,
            user_id=actor_id,
            changes={"count": created},
        )

    # Complete sync log
    error_summary = "; ".join(
        f"Row {e['row']}: {e['message']}" for e in errors[:10]
    ) if errors else None
    complete_sync_log(db, sync_log, created, skipped, error_summary)
    db.commit()

    return {"created": created, "skipped": skipped, "errors": errors}
