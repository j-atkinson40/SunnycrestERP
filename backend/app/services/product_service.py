from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.product_category import ProductCategory
from app.schemas.product import (
    ProductCategoryCreate,
    ProductCategoryUpdate,
    ProductCreate,
    ProductUpdate,
)
from app.services import audit_service
from app.services.inventory_service import create_inventory_item


# ---------------------------------------------------------------------------
# Category helpers
# ---------------------------------------------------------------------------


def get_categories(
    db: Session, company_id: str, include_inactive: bool = False
) -> list[ProductCategory]:
    query = db.query(ProductCategory).filter(
        ProductCategory.company_id == company_id
    )
    if not include_inactive:
        query = query.filter(ProductCategory.is_active == True)  # noqa: E712
    return query.order_by(ProductCategory.name).all()


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
    existing = (
        db.query(ProductCategory)
        .filter(
            ProductCategory.name == data.name,
            ProductCategory.company_id == company_id,
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
        changes={"name": data.name},
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

    # Check uniqueness if name is changing
    if "name" in update_data and update_data["name"] != cat.name:
        existing = (
            db.query(ProductCategory)
            .filter(
                ProductCategory.name == update_data["name"],
                ProductCategory.company_id == company_id,
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
