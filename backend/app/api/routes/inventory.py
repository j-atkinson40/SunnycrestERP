from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database import get_db
from app.models.inventory_item import InventoryItem
from app.models.inventory_transaction import InventoryTransaction
from app.models.user import User
from app.schemas.inventory import (
    AdjustStockRequest,
    InventoryItemResponse,
    InventorySettingsUpdate,
    InventoryTransactionResponse,
    ReceiveStockRequest,
)
from app.services.inventory_service import (
    adjust_stock,
    get_inventory_item,
    get_inventory_items,
    get_transactions,
    receive_stock,
    update_inventory_settings,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _item_to_response(item: InventoryItem) -> dict:
    data = InventoryItemResponse.model_validate(item).model_dump()
    if item.product:
        data["product_name"] = item.product.name
        data["product_sku"] = item.product.sku
        if item.product.category:
            data["category_name"] = item.product.category.name
    if item.reorder_point is not None:
        data["is_low_stock"] = item.quantity_on_hand <= item.reorder_point
    return data


def _tx_to_response(tx: InventoryTransaction) -> dict:
    data = InventoryTransactionResponse.model_validate(tx).model_dump()
    if tx.product:
        data["product_name"] = tx.product.name
    if tx.user:
        data["created_by_name"] = f"{tx.user.first_name} {tx.user.last_name}"
    return data


# ---------------------------------------------------------------------------
# Inventory item endpoints
# ---------------------------------------------------------------------------


@router.get("")
def list_inventory(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    low_stock_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.view")),
):
    result = get_inventory_items(
        db, current_user.company_id, page, per_page, search, low_stock_only
    )
    return {
        "items": [_item_to_response(i) for i in result["items"]],
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
    }


# NOTE: /transactions must be before /{product_id} to avoid FastAPI matching
# "transactions" as a product_id path parameter.
@router.get("/transactions")
def list_all_transactions(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.view")),
):
    result = get_transactions(
        db, current_user.company_id, page=page, per_page=per_page
    )
    return {
        "items": [_tx_to_response(tx) for tx in result["items"]],
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
    }


@router.get("/{product_id}")
def read_inventory_item(
    product_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.view")),
):
    item = get_inventory_item(db, product_id, current_user.company_id)
    return _item_to_response(item)


@router.post("/{product_id}/receive", status_code=201)
def receive_stock_endpoint(
    product_id: str,
    data: ReceiveStockRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.create")),
):
    item = receive_stock(
        db,
        product_id,
        data.quantity,
        current_user.company_id,
        actor_id=current_user.id,
        reference=data.reference,
        notes=data.notes,
    )
    return _item_to_response(item)


@router.post("/{product_id}/adjust")
def adjust_stock_endpoint(
    product_id: str,
    data: AdjustStockRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.edit")),
):
    item = adjust_stock(
        db,
        product_id,
        data.new_quantity,
        current_user.company_id,
        actor_id=current_user.id,
        reference=data.reference,
        notes=data.notes,
    )
    return _item_to_response(item)


@router.patch("/{product_id}/settings")
def update_settings(
    product_id: str,
    data: InventorySettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.edit")),
):
    item = update_inventory_settings(
        db,
        product_id,
        current_user.company_id,
        reorder_point=data.reorder_point,
        reorder_quantity=data.reorder_quantity,
        location=data.location,
        actor_id=current_user.id,
    )
    return _item_to_response(item)


@router.get("/{product_id}/transactions")
def list_product_transactions(
    product_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.view")),
):
    result = get_transactions(
        db,
        current_user.company_id,
        product_id=product_id,
        page=page,
        per_page=per_page,
    )
    return {
        "items": [_tx_to_response(tx) for tx in result["items"]],
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
    }
