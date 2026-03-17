from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database import get_db
from app.models.bom import BillOfMaterials, BOMLine
from app.models.user import User
from app.schemas.bom import (
    BOMCloneRequest,
    BOMCreate,
    BOMLineResponse,
    BOMListResponse,
    BOMResponse,
    BOMUpdate,
)
from app.services.bom_service import (
    activate_bom,
    archive_bom,
    calculate_bom_cost,
    clone_bom,
    create_bom,
    delete_bom,
    get_bom,
    list_boms,
    update_bom,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _line_to_response(line: BOMLine) -> dict:
    """Convert a BOMLine ORM object to a response dict with computed fields."""
    data = BOMLineResponse.model_validate(line).model_dump()
    cp = line.component_product
    if cp:
        data["component_product_name"] = cp.name
        data["component_product_sku"] = cp.sku
        data["component_unit_cost"] = cp.cost_price
        if cp.cost_price is not None:
            waste_mult = Decimal("1") + (line.waste_factor_pct / Decimal("100"))
            data["line_cost"] = (
                cp.cost_price * line.quantity * waste_mult
            ).quantize(Decimal("0.01"))
    return data


def _bom_to_response(bom: BillOfMaterials, cost_total: Decimal | None = None) -> dict:
    """Convert a BOM ORM object to a full response dict."""
    data = BOMResponse.model_validate(bom).model_dump()
    if bom.product:
        data["product_name"] = bom.product.name
        data["product_sku"] = bom.product.sku
    if bom.creator:
        data["created_by_name"] = (
            f"{bom.creator.first_name} {bom.creator.last_name}"
        )
    data["lines"] = [_line_to_response(line) for line in bom.lines]
    data["cost_total"] = cost_total
    return data


def _bom_to_list_response(
    bom: BillOfMaterials,
    line_count: int,
    cost_total: Decimal | None,
) -> dict:
    """Convert a BOM ORM object to a summary list response dict."""
    data = BOMListResponse.model_validate(bom).model_dump()
    if bom.product:
        data["product_name"] = bom.product.name
        data["product_sku"] = bom.product.sku
    data["line_count"] = line_count
    data["cost_total"] = cost_total
    return data


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
def list_boms_endpoint(
    product_id: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.view")),
):
    """List BOMs with optional filters by product and status."""
    result = list_boms(
        db,
        current_user.company_id,
        product_id=product_id,
        bom_status=status,
        page=page,
        per_page=per_page,
    )
    return {
        "items": [
            _bom_to_list_response(
                item["bom"], item["line_count"], item["cost_total"]
            )
            for item in result["items"]
        ],
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
    }


@router.get("/{bom_id}")
def get_bom_endpoint(
    bom_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.view")),
):
    """Get a BOM with all lines and calculated cost."""
    bom = get_bom(db, bom_id, current_user.company_id)
    cost = calculate_bom_cost(db, bom_id, current_user.company_id)
    return _bom_to_response(bom, cost_total=cost)


@router.post("", status_code=201)
def create_bom_endpoint(
    data: BOMCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.create")),
):
    """Create a new BOM with lines."""
    bom = create_bom(db, current_user.company_id, data, current_user.id)
    cost = calculate_bom_cost(db, bom.id, current_user.company_id)
    return _bom_to_response(bom, cost_total=cost)


@router.patch("/{bom_id}")
def update_bom_endpoint(
    bom_id: str,
    data: BOMUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.edit")),
):
    """Update a draft BOM."""
    bom = update_bom(db, bom_id, current_user.company_id, data, current_user.id)
    cost = calculate_bom_cost(db, bom.id, current_user.company_id)
    return _bom_to_response(bom, cost_total=cost)


@router.post("/{bom_id}/activate")
def activate_bom_endpoint(
    bom_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.edit")),
):
    """Activate a BOM. Archives other active versions for the same product."""
    bom = activate_bom(db, bom_id, current_user.company_id, current_user.id)
    cost = calculate_bom_cost(db, bom.id, current_user.company_id)
    return _bom_to_response(bom, cost_total=cost)


@router.post("/{bom_id}/archive")
def archive_bom_endpoint(
    bom_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.edit")),
):
    """Archive a BOM."""
    bom = archive_bom(db, bom_id, current_user.company_id, current_user.id)
    cost = calculate_bom_cost(db, bom.id, current_user.company_id)
    return _bom_to_response(bom, cost_total=cost)


@router.post("/{bom_id}/clone")
def clone_bom_endpoint(
    bom_id: str,
    data: BOMCloneRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.create")),
):
    """Clone a BOM to create a new draft version."""
    new_version = data.new_version if data else None
    bom = clone_bom(
        db, bom_id, current_user.company_id, current_user.id, new_version
    )
    cost = calculate_bom_cost(db, bom.id, current_user.company_id)
    return _bom_to_response(bom, cost_total=cost)


@router.delete("/{bom_id}", status_code=204)
def delete_bom_endpoint(
    bom_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.delete")),
):
    """Soft-delete a BOM."""
    delete_bom(db, bom_id, current_user.company_id)
    return None
