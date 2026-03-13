"""Service layer for Vendor Payments — create, list, soft-delete with reversal."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.vendor_bill import VendorBill
from app.models.vendor_payment import VendorPayment
from app.models.vendor_payment_application import VendorPaymentApplication
from app.services import audit_service


def _active_filter():
    return VendorPayment.deleted_at.is_(None)


def _update_bill_status(bill: VendorBill) -> None:
    """Set bill status based on amount_paid vs total."""
    if bill.amount_paid >= bill.total:
        bill.status = "paid"
    elif bill.amount_paid > 0:
        bill.status = "partial"
    elif bill.status == "paid":
        bill.status = "approved"  # reverted


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def get_vendor_payments(
    db: Session,
    company_id: str,
    page: int = 1,
    per_page: int = 20,
    vendor_id: str | None = None,
) -> dict:
    query = db.query(VendorPayment).filter(
        VendorPayment.company_id == company_id, _active_filter()
    )
    if vendor_id:
        query = query.filter(VendorPayment.vendor_id == vendor_id)

    total = query.count()
    items = (
        query.options(joinedload(VendorPayment.vendor))
        .order_by(VendorPayment.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {"items": items, "total": total, "page": page, "per_page": per_page}


def get_vendor_payment(
    db: Session, payment_id: str, company_id: str
) -> VendorPayment:
    payment = (
        db.query(VendorPayment)
        .options(
            joinedload(VendorPayment.vendor),
            joinedload(VendorPayment.applications).joinedload(
                VendorPaymentApplication.bill
            ),
            joinedload(VendorPayment.creator),
        )
        .filter(
            VendorPayment.id == payment_id,
            VendorPayment.company_id == company_id,
            _active_filter(),
        )
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment


def create_vendor_payment(
    db: Session, data, company_id: str, actor_id: str
) -> VendorPayment:
    # Validate sum of applications equals total
    app_total = sum(a.amount_applied for a in data.applications)
    if app_total != data.total_amount:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Sum of applications ({app_total}) does not match "
                f"total amount ({data.total_amount})"
            ),
        )

    # Validate each application against bill balance
    for app in data.applications:
        bill = (
            db.query(VendorBill)
            .filter(
                VendorBill.id == app.bill_id,
                VendorBill.company_id == company_id,
                VendorBill.deleted_at.is_(None),
            )
            .first()
        )
        if not bill:
            raise HTTPException(
                status_code=400,
                detail=f"Bill {app.bill_id} not found",
            )
        if bill.status not in ("approved", "partial"):
            raise HTTPException(
                status_code=400,
                detail=f"Bill {bill.number} must be approved before payment",
            )
        if app.amount_applied > bill.balance_remaining:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Amount {app.amount_applied} exceeds balance "
                    f"({bill.balance_remaining}) on bill {bill.number}"
                ),
            )

    # Create payment
    payment = VendorPayment(
        id=str(uuid.uuid4()),
        company_id=company_id,
        vendor_id=data.vendor_id,
        payment_date=data.payment_date,
        total_amount=data.total_amount,
        payment_method=data.payment_method,
        reference_number=data.reference_number,
        notes=data.notes,
        created_by=actor_id,
    )
    db.add(payment)
    db.flush()

    # Create applications and update bills
    for app_data in data.applications:
        pa = VendorPaymentApplication(
            id=str(uuid.uuid4()),
            payment_id=payment.id,
            bill_id=app_data.bill_id,
            amount_applied=app_data.amount_applied,
        )
        db.add(pa)

        bill = db.query(VendorBill).filter(VendorBill.id == app_data.bill_id).first()
        bill.amount_paid += app_data.amount_applied
        bill.modified_by = actor_id
        bill.modified_at = datetime.now(timezone.utc)
        _update_bill_status(bill)

    db.flush()

    audit_service.log_action(
        db, company_id, "created", "vendor_payment", payment.id,
        user_id=actor_id,
        changes={
            "total_amount": str(data.total_amount),
            "vendor_id": data.vendor_id,
            "method": data.payment_method,
        },
    )
    db.commit()
    return payment


def soft_delete_vendor_payment(
    db: Session, payment_id: str, company_id: str, actor_id: str
) -> None:
    """Soft-delete a payment and reverse all bill amount_paid updates."""
    payment = get_vendor_payment(db, payment_id, company_id)
    now = datetime.now(timezone.utc)

    # Reverse each application
    for app in payment.applications:
        bill = db.query(VendorBill).filter(VendorBill.id == app.bill_id).first()
        if bill:
            bill.amount_paid -= app.amount_applied
            if bill.amount_paid < Decimal("0.00"):
                bill.amount_paid = Decimal("0.00")
            bill.modified_by = actor_id
            bill.modified_at = now
            _update_bill_status(bill)

    payment.deleted_at = now
    payment.modified_by = actor_id
    payment.modified_at = now

    audit_service.log_action(
        db, company_id, "deleted", "vendor_payment", payment.id,
        user_id=actor_id,
        changes={"reversed_amount": str(payment.total_amount)},
    )
    db.commit()
