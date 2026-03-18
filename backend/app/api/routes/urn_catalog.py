"""Urn Catalog routes — Wilbert import + management."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.urn_catalog import (
    UrnBulkImportRequest,
    UrnCatalogStats,
    UrnCreateRequest,
    UrnImportResponse,
    UrnProductResponse,
)
from app.services.urn_catalog_service import (
    activate_urn,
    bulk_import_urns,
    create_urn,
    deactivate_urn,
    get_urn_stats,
    list_urns,
)

router = APIRouter()


def _product_to_response(p) -> dict:
    return UrnProductResponse(
        id=p.id,
        name=p.name,
        wilbert_sku=p.wilbert_sku,
        wholesale_cost=float(p.wholesale_cost) if p.wholesale_cost is not None else None,
        price=float(p.price) if p.price is not None else None,
        markup_percent=float(p.markup_percent) if p.markup_percent is not None else None,
        category=p.category.name if p.category else None,
        source=p.source,
        is_active=p.is_active,
        created_at=p.created_at,
    ).model_dump()


@router.get("/urns", response_model=list[UrnProductResponse])
def list_urn_products(
    active_only: bool = Query(True),
    limit: int = Query(500, le=2000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("products.view")),
):
    """List urn products with optional active/inactive filter."""
    products = list_urns(
        db, current_user.company_id, active_only=active_only, limit=limit, offset=offset
    )
    return [_product_to_response(p) for p in products]


@router.get("/urns/stats", response_model=UrnCatalogStats)
def urn_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("products.view")),
):
    """Stats for the urn catalog."""
    return get_urn_stats(db, current_user.company_id)


@router.post("/urns/import", response_model=UrnImportResponse)
def import_urns(
    body: UrnBulkImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("products.manage")),
):
    """Bulk import from Wilbert price list."""
    result = bulk_import_urns(
        db,
        current_user.company_id,
        current_user.id,
        body.urns,
        markup_percent=body.markup_percent,
        rounding=body.rounding,
    )
    db.commit()
    return result


@router.post("/urns/{product_id}/deactivate")
def deactivate_urn_product(
    product_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("products.manage")),
):
    """Deactivate an urn."""
    if not deactivate_urn(db, current_user.company_id, product_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )
    db.commit()
    return {"status": "deactivated"}


@router.post("/urns/{product_id}/activate")
def activate_urn_product(
    product_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("products.manage")),
):
    """Activate an urn."""
    if not activate_urn(db, current_user.company_id, product_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )
    db.commit()
    return {"status": "activated"}


@router.post("/urns", response_model=UrnProductResponse)
def create_urn_product(
    body: UrnCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("products.manage")),
):
    """Create a single urn manually."""
    product = create_urn(
        db,
        current_user.company_id,
        current_user.id,
        name=body.name,
        wilbert_sku=body.wilbert_sku,
        wholesale_cost=body.wholesale_cost,
        price=body.price,
        markup_percent=body.markup_percent,
        category=body.category,
        description=body.description,
    )
    db.commit()
    db.refresh(product)
    return _product_to_response(product)
