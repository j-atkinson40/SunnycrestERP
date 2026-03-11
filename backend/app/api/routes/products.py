from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database import get_db
from app.models.product import Product
from app.models.user import User
from app.schemas.product import (
    ProductCategoryCreate,
    ProductCategoryResponse,
    ProductCategoryUpdate,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)
from app.services.product_service import (
    create_category,
    create_product,
    deactivate_category,
    deactivate_product,
    get_categories,
    get_product,
    get_products,
    update_category,
    update_product,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Category endpoints
# ---------------------------------------------------------------------------


def _category_to_response(cat) -> dict:
    return ProductCategoryResponse.model_validate(cat).model_dump()


@router.get("/categories", response_model=list[ProductCategoryResponse])
def list_categories(
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("products.view")),
):
    cats = get_categories(db, current_user.company_id, include_inactive)
    return [_category_to_response(c) for c in cats]


@router.post("/categories", status_code=201)
def create_cat(
    data: ProductCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("products.create")),
):
    cat = create_category(db, data, current_user.company_id, actor_id=current_user.id)
    return _category_to_response(cat)


@router.patch("/categories/{category_id}")
def update_cat(
    category_id: str,
    data: ProductCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("products.edit")),
):
    cat = update_category(
        db, category_id, data, current_user.company_id, actor_id=current_user.id
    )
    return _category_to_response(cat)


@router.delete("/categories/{category_id}")
def delete_cat(
    category_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("products.delete")),
):
    deactivate_category(db, category_id, current_user.company_id, actor_id=current_user.id)
    return {"detail": "Category deactivated"}


# ---------------------------------------------------------------------------
# Product endpoints
# ---------------------------------------------------------------------------


def _product_to_response(product: Product) -> dict:
    data = ProductResponse.model_validate(product).model_dump()
    if product.category:
        data["category_name"] = product.category.name
    return data


@router.get("")
def list_products(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    category_id: str | None = Query(None),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("products.view")),
):
    result = get_products(
        db,
        current_user.company_id,
        page,
        per_page,
        search,
        category_id,
        include_inactive,
    )
    return {
        "items": [_product_to_response(p) for p in result["items"]],
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
    }


@router.get("/{product_id}")
def read_product(
    product_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("products.view")),
):
    product = get_product(db, product_id, current_user.company_id)
    return _product_to_response(product)


@router.post("", status_code=201)
def create(
    data: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("products.create")),
):
    product = create_product(db, data, current_user.company_id, actor_id=current_user.id)
    db.refresh(product)
    return _product_to_response(product)


@router.patch("/{product_id}")
def update(
    product_id: str,
    data: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("products.edit")),
):
    product = update_product(
        db, product_id, data, current_user.company_id, actor_id=current_user.id
    )
    db.refresh(product)
    return _product_to_response(product)


@router.delete("/{product_id}")
def delete(
    product_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("products.delete")),
):
    deactivate_product(db, product_id, current_user.company_id, actor_id=current_user.id)
    return {"detail": "Product deactivated"}
