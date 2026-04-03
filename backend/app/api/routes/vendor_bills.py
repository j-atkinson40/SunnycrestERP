"""API routes for Vendor Bills."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_module, require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.vendor_bill import (
    BillLineResponse,
    PaginatedVendorBills,
    VendorBillCreate,
    VendorBillListItem,
    VendorBillResponse,
    VendorBillUpdate,
)
from app.services import vendor_bill_service as bill_svc

router = APIRouter()


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _bill_to_list_item(bill) -> dict:
    from app.utils.company_name_resolver import resolve_vendor_name
    data = VendorBillListItem.model_validate(bill).model_dump()
    data["vendor_name"] = resolve_vendor_name(bill.vendor)
    data["balance_remaining"] = bill.balance_remaining
    return data


def _bill_to_response(bill) -> dict:
    from app.utils.company_name_resolver import resolve_vendor_name
    data = VendorBillResponse.model_validate(bill).model_dump()
    data["vendor_name"] = resolve_vendor_name(bill.vendor)
    data["po_number"] = bill.purchase_order.number if bill.purchase_order else None
    data["balance_remaining"] = bill.balance_remaining
    if bill.approver:
        data["approved_by_name"] = (
            f"{bill.approver.first_name or ''} {bill.approver.last_name or ''}".strip()
            or bill.approver.email
        )
    else:
        data["approved_by_name"] = None
    if bill.creator:
        data["created_by_name"] = (
            f"{bill.creator.first_name or ''} {bill.creator.last_name or ''}".strip()
            or bill.creator.email
        )
    else:
        data["created_by_name"] = None
    data["lines"] = [
        BillLineResponse.model_validate(l).model_dump()
        for l in (bill.lines or [])
        if l.deleted_at is None
    ]
    return data


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/due")
def bills_due(
    days: int = Query(30, ge=1),
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("ap.view")),
):
    bills = bill_svc.get_bills_due(db, current_user.company_id, days)
    return [_bill_to_list_item(b) for b in bills]


@router.get("/overdue")
def bills_overdue(
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("ap.view")),
):
    bills = bill_svc.get_bills_overdue(db, current_user.company_id)
    return [_bill_to_list_item(b) for b in bills]


@router.get("", response_model=PaginatedVendorBills)
def list_vendor_bills(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    status: str | None = Query(None),
    vendor_id: str | None = Query(None),
    due_from: str | None = Query(None),
    due_to: str | None = Query(None),
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("ap.view")),
):
    result = bill_svc.get_vendor_bills(
        db, current_user.company_id, page, per_page,
        search, status, vendor_id, due_from, due_to,
    )
    return {
        "items": [_bill_to_list_item(b) for b in result["items"]],
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
    }


@router.post("", status_code=201)
def create_vendor_bill(
    data: VendorBillCreate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("ap.create_bill")),
):
    bill = bill_svc.create_vendor_bill(
        db, data, current_user.company_id, actor_id=current_user.id,
    )
    db.refresh(bill)
    return _bill_to_response(bill)


@router.get("/{bill_id}")
def read_vendor_bill(
    bill_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("ap.view")),
):
    bill = bill_svc.get_vendor_bill(db, bill_id, current_user.company_id)
    return _bill_to_response(bill)


@router.put("/{bill_id}")
def update_vendor_bill(
    bill_id: str,
    data: VendorBillUpdate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("ap.create_bill")),
):
    bill = bill_svc.update_vendor_bill(
        db, bill_id, data, current_user.company_id, actor_id=current_user.id,
    )
    db.refresh(bill)
    return _bill_to_response(bill)


@router.post("/{bill_id}/approve")
def approve_vendor_bill(
    bill_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("ap.approve_bill")),
):
    bill = bill_svc.approve_vendor_bill(
        db, bill_id, current_user.company_id, actor_id=current_user.id,
    )
    return _bill_to_response(bill)


@router.post("/{bill_id}/void")
def void_vendor_bill(
    bill_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("ap.void")),
):
    bill = bill_svc.void_vendor_bill(
        db, bill_id, current_user.company_id, actor_id=current_user.id,
    )
    return _bill_to_response(bill)


@router.delete("/{bill_id}")
def delete_vendor_bill(
    bill_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("ap.create_bill")),
):
    bill_svc.soft_delete_vendor_bill(
        db, bill_id, current_user.company_id, actor_id=current_user.id,
    )
    return {"detail": "Vendor bill deleted"}
