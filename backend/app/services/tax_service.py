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
            # D-11 U-1: customers carry no county directly — resolve it
            # through the platform's zip→county mapping (the same data the
            # cemetery-suggestion flow uses). Before this, the customer
            # branch silently skipped and customer-only quotes could never
            # resolve tax.
            zip_code = (cust.zip_code or cust.billing_zip or "").strip()[:5]
            if zip_code:
                from app.services.county_geographic_service import _load_zip_mapping
                hit = _load_zip_mapping().get(zip_code)
                if hit:
                    county = hit["county"]
                    state = (hit["state"] or "").strip().upper()

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
    from app.services.money import round_money
    tax = round_money(subtotal * rate_percentage / Decimal("100"))
    return tax, rate_percentage


class TaxResolutionError(ValueError):
    """A quote that can't resolve and carries no override — refused loudly."""


from dataclasses import dataclass  # noqa: E402


@dataclass
class TaxResolution:
    """ONE TAX RESOLUTION, both faces (D-11 U-1).

    Tax is DERIVED (the jurisdiction engine) or EXPLICITLY overridden —
    never a silent default. The result carries its WHY, rendered wherever
    tax shows (the invoice-face honesty precedent):

        "resolved: 7% — Cayuga County, NY"
        "exempt: Hopkins FH is tax-exempt"
        "override: 7% (explicit)"        (0 is allowed, but must be explicit)
        "unresolved: <what was missing>" (tolerated walk-in path only)
    """
    tax_amount: Decimal
    tax_rate: Decimal          # effective fraction, e.g. 0.0700
    reason: str
    resolved: bool             # True unless the "unresolved" reason


def resolve_quote_tax(
    db: Session,
    company_id: str,
    *,
    subtotal: Decimal,
    customer_id: str | None = None,
    cemetery_id: str | None = None,
    override_rate: Decimal | None = None,
    require_resolution: bool = False,
) -> TaxResolution:
    """The shared money core's tax step — the only tax path for quotes.

    Order of authority: explicit override > exemption > jurisdiction
    engine > unresolved. `require_resolution=True` (the Sales/QTE face,
    where a customer is always present) raises TaxResolutionError instead
    of returning an unresolved zero — the confident-zero rule at tax
    altitude.
    """
    from app.models.customer import Customer
    from app.services.money import round_money

    if override_rate is not None:
        rate = Decimal(str(override_rate))
        pct = (rate * 100).normalize()
        return TaxResolution(
            tax_amount=round_money(subtotal * rate),
            tax_rate=rate,
            reason=f"override: {pct}% (explicit)",
            resolved=True,
        )

    cust = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.company_id == company_id)
        .first()
        if customer_id else None
    )
    if cust and cust.tax_exempt:
        return TaxResolution(
            tax_amount=Decimal("0.00"),
            tax_rate=Decimal("0.0000"),
            reason=f"exempt: {cust.name} is tax-exempt",
            resolved=True,
        )

    jur, rate_obj = get_jurisdiction_for_order(db, company_id, cemetery_id, customer_id)
    if jur and rate_obj:
        tax_amount, _pct = compute_tax(subtotal, rate_obj.rate_percentage, False)
        effective = (rate_obj.rate_percentage / Decimal("100")).quantize(Decimal("0.0001"))
        return TaxResolution(
            tax_amount=tax_amount,
            tax_rate=effective,
            reason=(
                f"resolved: {rate_obj.rate_percentage.normalize()}% — "
                f"{jur.county} County, {jur.state}"
            ),
            resolved=True,
        )

    missing = (
        "no cemetery county and the customer's zip matched no jurisdiction"
        if (cemetery_id or customer_id)
        else "no customer or cemetery to resolve against"
    )
    if require_resolution:
        raise TaxResolutionError(
            f"Can't resolve tax ({missing}) and no explicit tax rate was "
            "given — set up a tax jurisdiction for this customer's county, "
            "or pass an explicit tax_rate (0 is allowed, but must be "
            "explicit)."
        )
    return TaxResolution(
        tax_amount=Decimal("0.00"),
        tax_rate=Decimal("0.0000"),
        reason=f"unresolved: {missing}",
        resolved=False,
    )


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
