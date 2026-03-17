"""Funeral Home Price List & GPL Management API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_module, require_permission
from app.database import get_db
from app.models.user import User
from app.services import ftc_compliance_service

router = APIRouter(
    dependencies=[Depends(require_module("funeral_home"))],
)


# ---------------------------------------------------------------------------
# Request / Response schemas (inline)
# ---------------------------------------------------------------------------


class PriceListItemCreate(BaseModel):
    item_code: str
    category: str
    item_name: str
    description: str | None = None
    unit_price: float
    price_type: str | None = "flat"
    is_ftc_required_disclosure: bool | None = None
    ftc_disclosure_text: str | None = None
    is_required_by_law: bool | None = None
    sort_order: int | None = None


class PriceListItemUpdate(BaseModel):
    item_code: str | None = None
    category: str | None = None
    item_name: str | None = None
    description: str | None = None
    unit_price: float | None = None
    price_type: str | None = None
    is_ftc_required_disclosure: bool | None = None
    ftc_disclosure_text: str | None = None
    is_required_by_law: bool | None = None
    sort_order: int | None = None


class GPLVersionCreate(BaseModel):
    notes: str


# ---------------------------------------------------------------------------
# Literal paths first (before /{item_id})
# ---------------------------------------------------------------------------


@router.get("/")
def list_price_list_items(
    category: str | None = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_price_list.view")),
):
    """List price list items with optional category filter."""
    return ftc_compliance_service.get_price_list(
        db, current_user.company_id, category=category, active_only=active_only
    )


@router.post("/", status_code=201)
def create_price_list_item(
    data: PriceListItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_price_list.create")),
):
    """Create a new price list item."""
    return ftc_compliance_service.create_price_list_item(
        db, current_user.company_id, data.model_dump(exclude_none=True)
    )


@router.get("/compliance")
def get_compliance_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_compliance.view")),
):
    """Get FTC compliance validation report."""
    return ftc_compliance_service.validate_gpl(db, current_user.company_id)


@router.get("/gpl-versions")
def list_gpl_versions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_price_list.view")),
):
    """Get GPL version history."""
    return ftc_compliance_service.get_gpl_versions(db, current_user.company_id)


@router.post("/gpl-versions", status_code=201)
def create_gpl_version(
    data: GPLVersionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_price_list.edit")),
):
    """Create a new GPL version snapshot."""
    return ftc_compliance_service.create_gpl_version(
        db, current_user.company_id, data.notes, current_user.id
    )


@router.post("/seed-ftc", status_code=201)
def seed_ftc_items(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_price_list.create")),
):
    """Seed FTC required disclosure items into price list."""
    ftc_compliance_service.seed_ftc_price_list(db, current_user.company_id)
    return {"detail": "FTC required items seeded"}


# ---------------------------------------------------------------------------
# Parameterized routes (after literal paths)
# ---------------------------------------------------------------------------


@router.put("/{item_id}")
def update_price_list_item(
    item_id: str,
    data: PriceListItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("fh_price_list.edit")),
):
    """Update a price list item."""
    result = ftc_compliance_service.update_price_list_item(
        db,
        current_user.company_id,
        item_id,
        data.model_dump(exclude_none=True),
    )
    if not result:
        raise HTTPException(status_code=404, detail="Price list item not found")
    return result
