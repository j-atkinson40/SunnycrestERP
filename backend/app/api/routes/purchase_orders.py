"""API routes for Purchase Orders."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_module, require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.purchase_order import (
    PaginatedPurchaseOrders,
    POLineResponse,
    POStats,
    PurchaseOrderCreate,
    PurchaseOrderListItem,
    PurchaseOrderResponse,
    PurchaseOrderUpdate,
    ReceivePayload,
)
from app.services import purchase_order_service as po_svc

router = APIRouter()


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _line_to_response(line) -> dict:
    data = POLineResponse.model_validate(line).model_dump()
    data["product_name"] = line.product.name if line.product else None
    return data


def _po_to_response(po) -> dict:
    data = PurchaseOrderResponse.model_validate(po).model_dump()
    data["vendor_name"] = po.vendor.name if po.vendor else None
    if po.creator:
        data["created_by_name"] = (
            f"{po.creator.first_name or ''} {po.creator.last_name or ''}".strip()
            or po.creator.email
        )
    else:
        data["created_by_name"] = None
    data["lines"] = [
        _line_to_response(l) for l in (po.lines or []) if l.deleted_at is None
    ]
    return data


def _po_to_list_item(po) -> dict:
    data = PurchaseOrderListItem.model_validate(po).model_dump()
    data["vendor_name"] = po.vendor.name if po.vendor else None
    return data


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=POStats)
def po_stats(
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("ap.view")),
):
    return po_svc.get_po_stats(db, current_user.company_id)


# ---------------------------------------------------------------------------
# List / CRUD
# ---------------------------------------------------------------------------


@router.get("", response_model=PaginatedPurchaseOrders)
def list_purchase_orders(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    status: str | None = Query(None),
    vendor_id: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("ap.view")),
):
    result = po_svc.get_purchase_orders(
        db, current_user.company_id, page, per_page,
        search, status, vendor_id, date_from, date_to,
    )
    return {
        "items": [_po_to_list_item(po) for po in result["items"]],
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
    }


@router.post("", status_code=201)
def create_purchase_order(
    data: PurchaseOrderCreate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("ap.create_po")),
):
    po = po_svc.create_purchase_order(
        db, data, current_user.company_id, actor_id=current_user.id,
    )
    db.refresh(po)
    return _po_to_response(po)


@router.get("/{po_id}")
def read_purchase_order(
    po_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("ap.view")),
):
    po = po_svc.get_purchase_order(db, po_id, current_user.company_id)
    return _po_to_response(po)


@router.put("/{po_id}")
def update_purchase_order(
    po_id: str,
    data: PurchaseOrderUpdate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("ap.create_po")),
):
    po = po_svc.update_purchase_order(
        db, po_id, data, current_user.company_id, actor_id=current_user.id,
    )
    db.refresh(po)
    return _po_to_response(po)


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------


@router.post("/{po_id}/send")
def send_purchase_order(
    po_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("ap.create_po")),
):
    po = po_svc.send_purchase_order(
        db, po_id, current_user.company_id, actor_id=current_user.id,
    )
    return _po_to_response(po)


@router.post("/{po_id}/receive")
def receive_purchase_order(
    po_id: str,
    payload: ReceivePayload,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("ap.receive")),
):
    po = po_svc.receive_purchase_order(
        db, po_id, payload, current_user.company_id, actor_id=current_user.id,
    )
    return _po_to_response(po)


@router.post("/{po_id}/cancel")
def cancel_purchase_order(
    po_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("ap.create_po")),
):
    po = po_svc.cancel_purchase_order(
        db, po_id, current_user.company_id, actor_id=current_user.id,
    )
    return _po_to_response(po)


@router.delete("/{po_id}")
def delete_purchase_order(
    po_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("ap.create_po")),
):
    po_svc.soft_delete_purchase_order(
        db, po_id, current_user.company_id, actor_id=current_user.id,
    )
    return {"detail": "Purchase order deleted"}
