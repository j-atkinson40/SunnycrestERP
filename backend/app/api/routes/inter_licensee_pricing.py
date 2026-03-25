"""Inter-licensee pricing API routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.inter_licensee_pricing_service import (
    add_price_list_item,
    create_or_update_price_list,
    delete_price_list_item,
    get_area_price_list,
    get_own_price_list,
    lookup_transfer_pricing,
    make_price_visible_to_fh,
    respond_to_price_request,
    review_and_approve_pricing,
    update_price_list_item,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class PriceListSettings(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    visible_to_all_licensees: bool | None = None
    pricing_method: str | None = None
    retail_adjustment_percentage: float | None = None
    notes: str | None = None


class PriceListItemCreate(BaseModel):
    product_name: str
    product_code: str | None = None
    unit_price: float | None = None
    unit: str = "each"
    notes: str | None = None


class PriceListItemUpdate(BaseModel):
    product_name: str | None = None
    product_code: str | None = None
    unit_price: float | None = None
    unit: str | None = None
    is_active: bool | None = None
    notes: str | None = None


class PriceResponseSubmit(BaseModel):
    response_items: list[dict]
    response_notes: str | None = None


class PricingApproval(BaseModel):
    markup_percentage: float = 0
    review_notes: str | None = None


# ── Own price list management ──


@router.get("")
def get_price_list(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = get_own_price_list(db, current_user.company_id)
    return result or {"exists": False}


@router.post("")
def save_price_list(
    body: PriceListSettings,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return create_or_update_price_list(db, current_user.company_id, body.model_dump(exclude_none=True), current_user.id)


@router.post("/items")
def add_item(
    body: PriceListItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pl = get_own_price_list(db, current_user.company_id)
    if not pl or not pl.get("id"):
        raise HTTPException(status_code=400, detail="Create a price list first")
    return add_price_list_item(db, current_user.company_id, pl["id"], body.model_dump())


@router.patch("/items/{item_id}")
def update_item(
    item_id: str,
    body: PriceListItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    success = update_price_list_item(db, item_id, current_user.company_id, body.model_dump(exclude_none=True))
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "ok"}


@router.delete("/items/{item_id}")
def remove_item(
    item_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    success = delete_price_list_item(db, item_id, current_user.company_id)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "ok"}


# ── Lookup area licensee pricing ──


@router.get("/lookup/{area_tenant_id}")
def lookup_area_pricing(
    area_tenant_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = get_area_price_list(db, area_tenant_id)
    return result or {"exists": False}


# ── Transfer pricing flow ──


@router.post("/transfers/{transfer_id}/lookup")
def lookup_pricing(
    transfer_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return lookup_transfer_pricing(db, transfer_id)


@router.post("/transfers/{transfer_id}/submit-response")
def submit_price_response(
    transfer_id: str,
    body: PriceResponseSubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = respond_to_price_request(db, transfer_id, body.response_items, body.response_notes, current_user.id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/transfers/{transfer_id}/approve")
def approve_pricing(
    transfer_id: str,
    body: PricingApproval,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = review_and_approve_pricing(db, transfer_id, body.markup_percentage, body.review_notes, current_user.id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/transfers/{transfer_id}/make-visible")
def make_visible(
    transfer_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = make_price_visible_to_fh(db, transfer_id, current_user.id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
