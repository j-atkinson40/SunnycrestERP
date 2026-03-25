"""Early payment discount API routes."""

import logging
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.early_payment_discount_service import (
    apply_discounted_payment,
    calculate_discount,
    calculate_statement_discount,
    get_discount_settings,
    is_discount_eligible,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ──


class DiscountSettingsUpdate(BaseModel):
    early_payment_discount_enabled: bool | None = None
    early_payment_discount_percentage: float | None = None
    early_payment_discount_cutoff_day: int | None = None
    early_payment_discount_gl_account_id: str | None = None


class CalculateDiscountRequest(BaseModel):
    payment_amount: float
    customer_id: str
    invoice_ids: list[str] | None = None


class ApplyDiscountRequest(BaseModel):
    discount_data: dict
    discount_type: str  # 'early_payment' or 'manager_override'
    override_reason: str | None = None


class OverrideRequest(BaseModel):
    request_reason: str


class OverrideApproval(BaseModel):
    override_reason: str


# ── Settings ──


@router.get("/settings")
def get_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_discount_settings(db, current_user.company_id)


@router.patch("/settings")
def update_settings(
    body: DiscountSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.company import Company

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    updates = body.model_dump(exclude_none=True)

    # Validate: can't enable without GL account
    if updates.get("early_payment_discount_enabled") and not updates.get("early_payment_discount_gl_account_id"):
        current_gl = (company.settings or {}).get("early_payment_discount_gl_account_id")
        if not current_gl:
            raise HTTPException(status_code=400, detail="GL account required before enabling discount")

    for key, value in updates.items():
        company.set_setting(key, value)

    db.commit()
    return {"status": "ok"}


# ── Eligibility ──


@router.get("/eligibility")
def check_eligibility(
    customer_id: str,
    payment_date: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pd = date.fromisoformat(payment_date)
    return is_discount_eligible(db, current_user.company_id, customer_id, pd)


# ── Calculation ──


@router.post("/calculate")
def calc_discount(
    body: CalculateDiscountRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return calculate_discount(db, current_user.company_id, body.payment_amount, body.invoice_ids)


# ── Application ──


@router.post("/payments/{payment_id}/apply-discount")
def apply_discount(
    payment_id: str,
    body: ApplyDiscountRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    override_by = current_user.id if body.discount_type == "manager_override" else None
    result = apply_discounted_payment(
        db=db,
        payment_id=payment_id,
        tenant_id=current_user.company_id,
        discount_data=body.discount_data,
        discount_type=body.discount_type,
        user_id=current_user.id,
        override_by=override_by,
        override_reason=body.override_reason,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ── Override ──


@router.post("/payments/{payment_id}/request-override")
def request_override(
    payment_id: str,
    body: OverrideRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Create agent alert for managers
    try:
        from app.models.agent import AgentAlert

        alert = AgentAlert(
            tenant_id=current_user.company_id,
            alert_type="discount_override_request",
            severity="action_required",
            title="Discount override requested",
            message=f"{current_user.first_name} {current_user.last_name} requested early payment discount override. Reason: {body.request_reason}",
            action_label="Review Override",
            action_url=f"/ar/payments/{payment_id}/override",
        )
        db.add(alert)
        db.commit()
    except Exception as e:
        logger.warning(f"Could not create override alert: {e}")

    return {"status": "override_requested", "payment_id": payment_id}


@router.post("/payments/{payment_id}/approve-override")
def approve_override(
    payment_id: str,
    body: OverrideApproval,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Calculate and apply discount
    from app.models.customer_payment import CustomerPayment

    payment = db.query(CustomerPayment).filter(CustomerPayment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    discount_data = calculate_discount(db, current_user.company_id, float(payment.amount))
    result = apply_discounted_payment(
        db=db,
        payment_id=payment_id,
        tenant_id=current_user.company_id,
        discount_data=discount_data,
        discount_type="manager_override",
        user_id=current_user.id,
        override_by=current_user.id,
        override_reason=body.override_reason,
    )
    return result


@router.post("/payments/{payment_id}/deny-override")
def deny_override(
    payment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"status": "override_denied", "payment_id": payment_id}


# ── Statement discount preview ──


@router.get("/statement-preview/{customer_id}")
def get_statement_discount_preview(
    customer_id: str,
    closing_balance: float = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = calculate_statement_discount(db, current_user.company_id, customer_id, closing_balance)
    return result or {"eligible": False}
