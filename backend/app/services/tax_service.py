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


@dataclass
class LineTaxResolution:
    """The three-axis chain's full answer (sales-tax arc).

    Extends the U-1 shape with line-level detail: which lines went out
    product-exempt, which certificate backed a customer/job exemption,
    and any GAPS (an exemption flag without a backing certificate — the
    honest strictness: exemption is backed or it's a listed gap, never
    assumed).
    """
    tax_amount: Decimal
    tax_rate: Decimal
    reason: str
    resolved: bool
    source: str                      # override | product_exempt | job_certificate |
                                     # customer_certificate | jurisdiction | unresolved
    taxable_subtotal: Decimal
    exempt_subtotal: Decimal
    exempt_lines: list
    gaps: list


def _find_valid_certificate(db, company_id: str, customer_id: str,
                            sales_order_id: str | None, on):
    """Job cert first (order-scoped), then the customer's blanket.
    Dated validity does the work — an expired cert is simply absent."""
    from app.models.tax_filing import TaxCertificate

    if sales_order_id:
        for cert in (
            db.query(TaxCertificate)
            .filter(TaxCertificate.company_id == company_id,
                    TaxCertificate.sales_order_id == sales_order_id,
                    TaxCertificate.is_active.is_(True))
            .all()
        ):
            if cert.is_valid_on(on):
                return cert, "job"
    for cert in (
        db.query(TaxCertificate)
        .filter(TaxCertificate.company_id == company_id,
                TaxCertificate.customer_id == customer_id,
                TaxCertificate.sales_order_id.is_(None),
                TaxCertificate.is_active.is_(True))
        .all()
    ):
        if cert.is_valid_on(on):
            return cert, "customer"
    return None, None


def resolve_line_tax(
    db: Session,
    company_id: str,
    *,
    lines: list,
    customer_id: str | None = None,
    sales_order_id: str | None = None,
    cemetery_id: str | None = None,
    override_rate: Decimal | None = None,
    require_resolution: bool = False,
    on_date=None,
) -> LineTaxResolution:
    """THE RESOLUTION ORDER, extended at the line level (sales-tax arc):

        explicit override → PRODUCT-EXEMPT (per line) → JOB CERT →
        CUSTOMER CERT → jurisdiction engine → unresolved

    Each answer carries its SPECIFIC reason. A customer's tax_exempt
    flag WITHOUT a valid certificate resolves TAXABLE with the gap
    surfaced — exemption is backed or it's a listed gap, never assumed.

    `lines` items: {"product_id": str|None, "amount": Decimal-ish,
    "description": str|None}.
    """
    from datetime import date as _date
    from app.models.customer import Customer
    from app.models.product import Product
    from app.services.money import round_money

    on = on_date or _date.today()
    amounts = [Decimal(str(l.get("amount") or 0)) for l in lines]
    subtotal = sum(amounts, Decimal("0.00"))

    if override_rate is not None:
        rate = Decimal(str(override_rate))
        pct = (rate * 100).normalize()
        return LineTaxResolution(
            tax_amount=round_money(subtotal * rate), tax_rate=rate,
            reason=f"override: {pct}% (explicit)", resolved=True,
            source="override", taxable_subtotal=subtotal,
            exempt_subtotal=Decimal("0.00"), exempt_lines=[], gaps=[],
        )

    # AXIS 1 — product taxability. 'inherit' resolves TAXABLE (the
    # default law); only the operator's explicit 'exempt' mark exempts.
    product_ids = [l.get("product_id") for l in lines if l.get("product_id")]
    products = {
        p.id: p for p in db.query(Product).filter(
            Product.id.in_(product_ids), Product.company_id == company_id
        ).all()
    } if product_ids else {}
    exempt_lines, taxable_subtotal, exempt_subtotal = [], Decimal("0.00"), Decimal("0.00")
    for l, amt in zip(lines, amounts):
        p = products.get(l.get("product_id"))
        if p is not None and p.tax_class == "exempt":
            exempt_lines.append({
                "description": l.get("description") or p.name,
                "amount": float(amt),
                "reason": f"product: {p.name} — exempt class",
            })
            exempt_subtotal += amt
        else:
            taxable_subtotal += amt

    gaps: list = []
    cust = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.company_id == company_id)
        .first()
        if customer_id else None
    )

    def _all_exempt(reason: str, source: str) -> LineTaxResolution:
        return LineTaxResolution(
            tax_amount=Decimal("0.00"), tax_rate=Decimal("0.0000"),
            reason=reason, resolved=True, source=source,
            taxable_subtotal=Decimal("0.00"),
            exempt_subtotal=subtotal, exempt_lines=exempt_lines, gaps=gaps,
        )

    if taxable_subtotal <= Decimal("0.00") and exempt_subtotal > 0:
        return _all_exempt(
            f"exempt: all {len(exempt_lines)} line(s) product-exempt", "product_exempt")

    # AXES 2+3 — certificates (job first, then blanket).
    if cust:
        cert, scope = _find_valid_certificate(db, company_id, cust.id, sales_order_id, on)
        if cert:
            num = cert.cert_number or "no number on record"
            if scope == "job":
                reason = f"exempt: job certificate {cert.cert_type} ({num})"
                source = "job_certificate"
            else:
                through = (f"valid through {cert.valid_through.isoformat()}"
                           if cert.valid_through else "open-dated")
                reason = f"exempt: customer certificate {cert.cert_type} ({num}), {through}"
                source = "customer_certificate"
            if exempt_lines:
                reason += f" · {len(exempt_lines)} line(s) also product-exempt"
            gaps_note = list(gaps)
            return LineTaxResolution(
                tax_amount=Decimal("0.00"), tax_rate=Decimal("0.0000"),
                reason=reason, resolved=True, source=source,
                taxable_subtotal=Decimal("0.00"), exempt_subtotal=subtotal,
                exempt_lines=exempt_lines, gaps=gaps_note,
            )
        if cust.tax_exempt:
            # THE HONEST STRICTNESS: the flag without a backing
            # certificate does NOT exempt — taxable, with the gap listed.
            gaps.append(
                f"{cust.name} carries an exemption flag but no valid "
                "certificate on file — resolved TAXABLE; attach the "
                "certificate to exempt."
            )

    # Jurisdiction engine on what remains taxable.
    jur, rate_obj = get_jurisdiction_for_order(db, company_id, cemetery_id, customer_id)
    if jur and rate_obj:
        tax_amount, _pct = compute_tax(taxable_subtotal, rate_obj.rate_percentage, False)
        effective = (rate_obj.rate_percentage / Decimal("100")).quantize(Decimal("0.0001"))
        reason = (
            f"resolved: {rate_obj.rate_percentage.normalize()}% — "
            f"{jur.county} County, {jur.state}"
        )
        if exempt_lines:
            reason += (f" · {len(exempt_lines)} line(s) product-exempt "
                       f"(${float(exempt_subtotal):,.2f})")
        if gaps:
            reason += " · GAP: exemption flag without certificate"
        return LineTaxResolution(
            tax_amount=tax_amount, tax_rate=effective, reason=reason,
            resolved=True, source="jurisdiction",
            taxable_subtotal=taxable_subtotal, exempt_subtotal=exempt_subtotal,
            exempt_lines=exempt_lines, gaps=gaps,
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
    return LineTaxResolution(
        tax_amount=Decimal("0.00"), tax_rate=Decimal("0.0000"),
        reason=f"unresolved: {missing}", resolved=False, source="unresolved",
        taxable_subtotal=taxable_subtotal, exempt_subtotal=exempt_subtotal,
        exempt_lines=exempt_lines, gaps=gaps,
    )


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
    """The shared money core's tax step — the U-1 shape, now a thin
    wrapper over the three-axis line-level chain (one law, one path).

    NOTE (sales-tax arc): the bare tax_exempt flag no longer exempts —
    a valid certificate does. Flag-without-cert resolves TAXABLE with
    the gap in the reason. Product exemption needs line detail; callers
    with lines use resolve_line_tax directly.
    """
    out = resolve_line_tax(
        db, company_id,
        lines=[{"product_id": None, "amount": subtotal, "description": None}],
        customer_id=customer_id, cemetery_id=cemetery_id,
        override_rate=override_rate, require_resolution=require_resolution,
    )
    return TaxResolution(
        tax_amount=out.tax_amount, tax_rate=out.tax_rate,
        reason=out.reason, resolved=out.resolved,
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
