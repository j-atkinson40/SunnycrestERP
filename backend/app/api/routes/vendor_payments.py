"""API routes for Vendor Payments."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_module, require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.vendor_payment import (
    PaginatedVendorPayments,
    PaymentApplicationResponse,
    VendorPaymentCreate,
    VendorPaymentListItem,
    VendorPaymentResponse,
)
from app.services import vendor_payment_service as pay_svc

router = APIRouter()


def _app_to_response(app) -> dict:
    data = PaymentApplicationResponse.model_validate(app).model_dump()
    data["bill_number"] = app.bill.number if app.bill else None
    return data


def _payment_to_list_item(p) -> dict:
    data = VendorPaymentListItem.model_validate(p).model_dump()
    data["vendor_name"] = p.vendor.name if p.vendor else None
    return data


def _payment_to_response(p) -> dict:
    data = VendorPaymentResponse.model_validate(p).model_dump()
    data["vendor_name"] = p.vendor.name if p.vendor else None
    if p.creator:
        data["created_by_name"] = (
            f"{p.creator.first_name or ''} {p.creator.last_name or ''}".strip()
            or p.creator.email
        )
    else:
        data["created_by_name"] = None
    data["applications"] = [_app_to_response(a) for a in (p.applications or [])]
    return data


@router.get("", response_model=PaginatedVendorPayments)
def list_vendor_payments(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    vendor_id: str | None = Query(None),
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("ap.view")),
):
    result = pay_svc.get_vendor_payments(
        db, current_user.company_id, page, per_page, vendor_id,
    )
    return {
        "items": [_payment_to_list_item(p) for p in result["items"]],
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
    }


@router.post("", status_code=201)
def create_vendor_payment(
    data: VendorPaymentCreate,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("ap.record_payment")),
):
    payment = pay_svc.create_vendor_payment(
        db, data, current_user.company_id, actor_id=current_user.id,
    )
    db.refresh(payment)
    return _payment_to_response(payment)


@router.get("/{payment_id}")
def read_vendor_payment(
    payment_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("ap.view")),
):
    payment = pay_svc.get_vendor_payment(
        db, payment_id, current_user.company_id,
    )
    return _payment_to_response(payment)


@router.delete("/{payment_id}")
def delete_vendor_payment(
    payment_id: str,
    db: Session = Depends(get_db),
    _module: User = Depends(require_module("purchasing")),
    current_user: User = Depends(require_permission("ap.record_payment")),
):
    pay_svc.soft_delete_vendor_payment(
        db, payment_id, current_user.company_id, actor_id=current_user.id,
    )
    return {"detail": "Payment deleted and bill amounts reversed"}
