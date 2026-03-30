"""Tax service — county-based tax resolution for funeral orders.

Uses cemetery.county + cemetery.state to look up TaxJurisdiction,
then applies TaxRate to taxable order amounts.
"""

import logging
from decimal import Decimal

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def get_jurisdiction_for_order(
    db: Session,
    company_id: str,
    cemetery_id: str | None = None,
    customer_id: str | None = None,
) -> tuple:
    """Find (TaxJurisdiction, TaxRate) for an order.

    Priority: cemetery county > customer county.
    Returns (None, None) if no matching jurisdiction configured.
    """
    from app.models.cemetery import Cemetery
    from app.models.customer import Customer
    from app.models.tax import TaxJurisdiction, TaxRate

    state = county = None

    if cemetery_id:
        cem = db.query(Cemetery).filter(Cemetery.id == cemetery_id).first()
        if cem and cem.county:
            county = cem.county.strip()
            state = (cem.state or "").strip().upper()

    if not county and customer_id:
        cust = db.query(Customer).filter(Customer.id == customer_id).first()
        if cust:
            # customers don't have a county field directly; skip
            pass

    if not county or not state:
        return None, None

    jur = (
        db.query(TaxJurisdiction)
        .filter(
            TaxJurisdiction.tenant_id == company_id,
            TaxJurisdiction.state == state,
            TaxJurisdiction.is_active == True,  # noqa: E712
        )
        .filter(TaxJurisdiction.county.ilike(county))
        .first()
    )

    if not jur:
        return None, None

    rate = db.query(TaxRate).filter(TaxRate.id == jur.tax_rate_id).first()
    return jur, rate


def compute_tax(
    subtotal: Decimal,
    rate_percentage: Decimal,
    tax_exempt: bool = False,
) -> tuple[Decimal, Decimal]:
    """Return (tax_amount, effective_rate) given subtotal and rate_percentage.

    rate_percentage is stored as e.g. 8.0 meaning 8.0%.
    Returns (Decimal tax_amount, Decimal rate_percentage).
    """
    if tax_exempt or rate_percentage == Decimal("0"):
        return Decimal("0.00"), Decimal("0.0000")
    tax = (subtotal * rate_percentage / Decimal("100")).quantize(Decimal("0.01"))
    return tax, rate_percentage


def get_tax_preview(
    db: Session,
    company_id: str,
    cemetery_id: str,
) -> dict:
    """Return a tax preview dict for the order station UI.

    Returns:
        {
            "configured": bool,
            "rate_percentage": float | None,
            "rate_name": str | None,
            "county": str | None,
            "state": str | None,
            "jurisdiction_name": str | None,
        }
    """
    from app.models.cemetery import Cemetery

    cem = db.query(Cemetery).filter(Cemetery.id == cemetery_id).first()
    if not cem:
        return {"configured": False, "rate_percentage": None, "rate_name": None,
                "county": None, "state": None, "jurisdiction_name": None}

    county = (cem.county or "").strip()
    state = (cem.state or "").strip().upper()

    if not county:
        return {"configured": False, "rate_percentage": None, "rate_name": None,
                "county": None, "state": state or None, "jurisdiction_name": None}

    jur, rate = get_jurisdiction_for_order(db, company_id, cemetery_id=cemetery_id)

    if jur and rate:
        return {
            "configured": True,
            "rate_percentage": float(rate.rate_percentage),
            "rate_name": rate.rate_name,
            "county": county,
            "state": state,
            "jurisdiction_name": jur.jurisdiction_name,
        }

    return {
        "configured": False,
        "rate_percentage": None,
        "rate_name": None,
        "county": county,
        "state": state,
        "jurisdiction_name": None,
    }
