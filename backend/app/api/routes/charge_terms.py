"""Charge account terms — onboarding + settings endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.company import Company
from app.models.customer import Customer
from app.models.user import User
from app.utils.company_name_resolver import resolve_customer_name

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class DefaultTermsBody(BaseModel):
    net_days: int = 30
    finance_charge_rate: float = 1.5
    finance_charge_after_days: int = 30
    no_finance_charge: bool = False
    credit_limit: float | None = None  # None = no limit


class ExceptionBody(BaseModel):
    customer_id: str
    net_days: int = 30
    finance_charge_rate: float = 1.5
    finance_charge_after_days: int = 30
    no_finance_charge: bool = False
    credit_limit: float | None = None


class ExceptionUpdateBody(BaseModel):
    net_days: int | None = None
    finance_charge_rate: float | None = None
    finance_charge_after_days: int | None = None
    no_finance_charge: bool | None = None
    credit_limit: float | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FH_TYPES = {"funeral_home"}

# Exclude these customer_type values explicitly
_EXCLUDE_TYPES = {
    "contractor", "cemetery", "crematory", "church", "government",
    "school", "fire_department", "utility", "cod_precast", "aggregate",
}


def _funeral_home_filter(query, company_id: str):
    """Filter to funeral-home-ish customers only."""
    return query.filter(
        Customer.company_id == company_id,
        Customer.is_active == True,
        ~Customer.customer_type.in_(_EXCLUDE_TYPES),
    ).filter(
        (Customer.customer_type.in_(_FH_TYPES))
        | (Customer.customer_type.is_(None))
    )


def _get_defaults(company: Company) -> dict:
    """Read charge account defaults from company settings_json."""
    s = company.settings or {}
    return {
        "net_days": s.get("charge_default_net_days", 30),
        "finance_charge_rate": s.get("charge_default_fc_rate", 1.5),
        "finance_charge_after_days": s.get("charge_default_fc_after_days", 30),
        "no_finance_charge": s.get("charge_default_no_fc", False),
        "credit_limit": s.get("charge_default_credit_limit"),  # None = no limit
        "applied": s.get("charge_defaults_applied", False),
    }


def _save_defaults(company: Company, data: DefaultTermsBody, db: Session):
    """Write charge account defaults to company settings_json."""
    company.set_setting("charge_default_net_days", data.net_days)
    company.set_setting("charge_default_fc_rate", data.finance_charge_rate)
    company.set_setting("charge_default_fc_after_days", data.finance_charge_after_days)
    company.set_setting("charge_default_no_fc", data.no_finance_charge)
    company.set_setting("charge_default_credit_limit", data.credit_limit)
    company.set_setting("charge_defaults_applied", True)


def _net_days_to_terms(net_days: int) -> str:
    if net_days == 0:
        return "Due on receipt"
    return f"Net {net_days}"


def _terms_to_net_days(terms: str | None) -> int:
    if not terms:
        return 30
    t = terms.strip().lower()
    if t in ("due on receipt", "due upon receipt", "cod"):
        return 0
    # "Net 30" → 30
    if t.startswith("net"):
        try:
            return int(t.replace("net", "").strip())
        except ValueError:
            return 30
    try:
        return int(t)
    except ValueError:
        return 30


def _serialize_exception(c: Customer, defaults: dict) -> dict:
    """Serialize a customer that has an override (differs from defaults)."""
    net_days = _terms_to_net_days(c.payment_terms)
    return {
        "id": c.id,
        "customer_id": c.id,
        "customer_name": resolve_customer_name(c),
        "net_days": net_days,
        "finance_charge_rate": defaults["finance_charge_rate"],
        "finance_charge_after_days": defaults["finance_charge_after_days"],
        "no_finance_charge": defaults["no_finance_charge"],
        "credit_limit": float(c.credit_limit) if c.credit_limit is not None else None,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
def get_charge_terms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get charge terms overview: defaults + exceptions + FH count."""
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    defaults = _get_defaults(company)

    # Count funeral homes
    fh_count = _funeral_home_filter(
        db.query(func.count(Customer.id)), current_user.company_id
    ).scalar() or 0

    # Find customers with individual overrides (payment_terms or credit_limit differs)
    default_terms_str = _net_days_to_terms(defaults["net_days"])
    exceptions = []

    fh_query = _funeral_home_filter(
        db.query(Customer), current_user.company_id
    )
    # Only include those where payment_terms or credit_limit differs from default
    if defaults["applied"]:
        for c in fh_query.all():
            has_terms_override = (
                c.payment_terms is not None
                and c.payment_terms != default_terms_str
            )
            default_cl = defaults["credit_limit"]
            has_limit_override = False
            if default_cl is None:
                has_limit_override = c.credit_limit is not None
            else:
                has_limit_override = (
                    c.credit_limit is not None
                    and float(c.credit_limit) != default_cl
                ) or c.credit_limit is None

            if has_terms_override or has_limit_override:
                exceptions.append(_serialize_exception(c, defaults))

    return {
        "default": defaults,
        "exceptions": exceptions,
        "funeral_home_count": fh_count,
    }


@router.post("/default")
def save_default_terms(
    data: DefaultTermsBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save/update tenant-level default charge account terms."""
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    _save_defaults(company, data, db)

    # Also update company.default_payment_terms for use elsewhere
    company.default_payment_terms = _net_days_to_terms(data.net_days)

    # Apply defaults to all funeral homes that don't have explicit overrides
    terms_str = _net_days_to_terms(data.net_days)
    fh_query = _funeral_home_filter(db.query(Customer), current_user.company_id)
    updated = 0
    for c in fh_query.all():
        changed = False
        if c.payment_terms is None or c.payment_terms == "" or c.payment_terms == company.default_payment_terms:
            c.payment_terms = terms_str
            changed = True
        if data.credit_limit is not None and c.credit_limit is None:
            from decimal import Decimal
            c.credit_limit = Decimal(str(data.credit_limit))
            changed = True
        elif data.credit_limit is None and c.credit_limit is None:
            pass  # both no limit, no change needed
        if changed:
            updated += 1

    db.commit()

    # Fire onboarding hook (check_completion commits internally)
    try:
        from app.services.onboarding_service import check_completion
        result = check_completion(db, current_user.company_id, "setup_charge_accounts")
        logger.info("Charge terms onboarding hook result=%s company=%s", result, current_user.company_id)
    except Exception:
        logger.exception("Failed to fire charge terms onboarding hook")

    return {
        "applied_count": updated,
        "default": _get_defaults(company),
    }


@router.post("/exceptions")
def create_exception(
    data: ExceptionBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a per-customer charge terms exception."""
    customer = db.query(Customer).filter(
        Customer.id == data.customer_id,
        Customer.company_id == current_user.company_id,
    ).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    from decimal import Decimal

    customer.payment_terms = _net_days_to_terms(data.net_days)
    if data.credit_limit is not None:
        customer.credit_limit = Decimal(str(data.credit_limit))
    else:
        customer.credit_limit = None

    db.commit()
    db.refresh(customer)

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    defaults = _get_defaults(company) if company else {}

    return _serialize_exception(customer, defaults)


@router.patch("/exceptions/{customer_id}")
def update_exception(
    customer_id: str,
    data: ExceptionUpdateBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a per-customer charge terms exception."""
    customer = db.query(Customer).filter(
        Customer.id == customer_id,
        Customer.company_id == current_user.company_id,
    ).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    from decimal import Decimal

    if data.net_days is not None:
        customer.payment_terms = _net_days_to_terms(data.net_days)
    if data.credit_limit is not None:
        customer.credit_limit = Decimal(str(data.credit_limit))
    elif data.credit_limit is None and "credit_limit" in data.model_fields_set:
        customer.credit_limit = None

    db.commit()
    db.refresh(customer)

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    defaults = _get_defaults(company) if company else {}

    return _serialize_exception(customer, defaults)


@router.delete("/exceptions/{customer_id}")
def delete_exception(
    customer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove per-customer exception — revert to tenant defaults."""
    customer = db.query(Customer).filter(
        Customer.id == customer_id,
        Customer.company_id == current_user.company_id,
    ).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    defaults = _get_defaults(company) if company else {}

    # Reset to defaults
    from decimal import Decimal
    customer.payment_terms = _net_days_to_terms(defaults.get("net_days", 30))
    if defaults.get("credit_limit") is not None:
        customer.credit_limit = Decimal(str(defaults["credit_limit"]))
    else:
        customer.credit_limit = None

    db.commit()
    return {"detail": "Exception removed"}
