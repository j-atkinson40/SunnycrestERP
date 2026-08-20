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
            # ⚠️ THE OPERATOR'S ANSWER BEATS EVERY DERIVED ONE (r172). It exists
            # because 22 ZIPs in Sunnycrest's twelve counties span a rate
            # boundary and cannot be resolved from a ZIP at all. Checked before
            # the ZIP so that setting it actually ends the ambiguity.
            if (cust.tax_county or "").strip():
                county = cust.tax_county.strip()
                state = (cust.state or cust.billing_state or "NY").strip().upper()
            else:
                # ⚠️ WAS `_load_zip_mapping()` — 107 COUNTY CENTROIDS USED AS A
                # COVERAGE TABLE. One ZIP per county, so 14580 (Webster, Monroe)
                # resolved to nothing while 14604 (Rochester) resolved fine, and
                # every real customer outside those 107 silently charged zero.
                # Now the state's own cross-reference, and — the point of the
                # change — a ZIP that spans counties DOES NOT RESOLVE.
                from app.services.county_geographic_service import counties_for_zip

                zip_code = (cust.zip_code or cust.billing_zip or "").strip()[:5]
                if zip_code:
                    cand = counties_for_zip(zip_code, "NY")
                    if len(cand) == 1:
                        county, state = cand[0], "NY"
                    elif len(cand) > 1:
                        # ⚠️ A STRADDLE IS ONLY AMBIGUOUS IF THE ANSWER DIFFERS.
                        # 57 ZIPs span two or more of Sunnycrest's twelve
                        # counties; only 22 touch Oneida (8.75%) or Ontario
                        # (7.5%). For the other 35 every candidate is at 8%, so
                        # the rate is the same whichever county the customer is
                        # actually in — refusing those would be theatre.
                        #
                        # ⚠️ AND THEY ARE HARMLESS ONLY BECAUSE THOSE RATES
                        # MATCH TODAY. If one of those counties changes rate, 35
                        # ZIPs become ambiguous with nothing announcing it — the
                        # condition is checked here at resolution time rather
                        # than assumed, so a rate change flips them to
                        # unresolved instead of silently mispricing.
                        agreed = _one_rate_across(db, company_id, cand)
                        if agreed is not None:
                            county, state = agreed, "NY"
                        # else: leave unresolved. The reason names the counties.
                    if not county:
                        state = state or ""

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


def _one_rate_across(db: Session, company_id: str, counties: list[str]) -> str | None:
    """Return a county to use when EVERY candidate would charge the same rate.

    A ZIP spanning several counties is only a problem when the counties disagree
    about the rate. This returns the first candidate when all of them are
    configured for this tenant AND carry one rate; None otherwise.

    ⚠️ EVERY CANDIDATE MUST BE CONFIGURED, not just one. If a ZIP spans Cortland
    and Broome and the tenant has only Cortland, the customer may genuinely be
    in Broome — and resolving to Cortland because it is the only row we have is
    a guess wearing a lookup's clothes.
    """
    from app.models.tax import TaxJurisdiction, TaxRate

    rows = (
        db.query(TaxJurisdiction, TaxRate)
        .join(TaxRate, TaxRate.id == TaxJurisdiction.tax_rate_id)
        .filter(
            TaxJurisdiction.tenant_id == company_id,
            TaxJurisdiction.is_active == True,  # noqa: E712
            TaxJurisdiction.state == "NY",
        )
        .all()
    )
    by_county = {j.county.lower(): r.rate_percentage for j, r in rows}
    rates = {by_county.get(c.lower()) for c in counties}
    if None in rates or len(rates) != 1:
        return None
    return counties[0]


def unresolved_reason_for_customer(db: Session, customer_id: str | None,
                                   cemetery_id: str | None = None) -> str:
    """Why resolution failed, in terms an operator can act on.

    ⚠️ "CANNOT RESOLVE" SENDS SOMEONE HUNTING. The three failures below need
    three different actions, and a single message for all of them is the same
    defect as a health check that cannot distinguish "did not run" from "found
    nothing":

      - no ZIP at all            → put an address on the customer
      - ZIP spans counties       → set `tax_county`, and here are the choices
      - resolved but no rate row → configure that county in tax settings

    The ambiguous case names the counties for the same reason a migration
    pre-flight names the rows it will touch: the specific fact is what makes it
    actionable.
    """
    from app.models.customer import Customer
    from app.services.county_geographic_service import counties_for_zip

    if not (customer_id or cemetery_id):
        return "no customer or cemetery to resolve against"
    cust = (
        db.query(Customer).filter(Customer.id == customer_id).first()
        if customer_id else None
    )
    if cust is None:
        return "no cemetery county and no customer record to resolve against"
    if (cust.tax_county or "").strip():
        return (
            f"{cust.name} is set to {cust.tax_county.strip()} County, but no tax "
            f"jurisdiction is configured for it — add it in tax settings"
        )
    zip_code = (cust.zip_code or cust.billing_zip or "").strip()[:5]
    if not zip_code:
        return (
            f"{cust.name} has no ZIP code on file — sales tax resolves from the "
            "ZIP, and without one this customer's orders charge no tax, which "
            "is not the same as being exempt"
        )
    cand = counties_for_zip(zip_code, "NY")
    if len(cand) > 1:
        # Reached only when the candidates DISAGREE — a straddle whose counties
        # share a rate resolves and never gets here. Two ways to disagree, and
        # they want different actions.
        from app.models.tax import TaxJurisdiction, TaxRate

        rows = (
            db.query(TaxJurisdiction, TaxRate)
            .join(TaxRate, TaxRate.id == TaxJurisdiction.tax_rate_id)
            .filter(
                TaxJurisdiction.tenant_id == cust.company_id,
                TaxJurisdiction.is_active == True,  # noqa: E712
            )
            .all()
        )
        by_county = {j.county.lower(): r.rate_percentage for j, r in rows}
        unconfigured = [c for c in cand if c.lower() not in by_county]
        if unconfigured:
            return (
                f"ZIP {zip_code} spans {', '.join(cand)}, and "
                f"{', '.join(unconfigured)} {'is' if len(unconfigured) == 1 else 'are'} "
                f"not configured — the customer may be in a county this tenant "
                f"has no rate for. Set the county on {cust.name}, or add the "
                f"missing jurisdiction."
            )
        spread = ", ".join(
            f"{c} {by_county[c.lower()].normalize()}%" for c in cand
        )
        return (
            f"ZIP {zip_code} spans counties charging different rates "
            f"({spread}) — a ZIP cannot decide between them. Set the county on "
            f"{cust.name} to resolve this."
        )
    if not cand:
        return (
            f"ZIP {zip_code} is not in the New York ZIP→county reference — set "
            f"the county on {cust.name} directly"
        )
    return (
        f"{cust.name} resolves to {cand[0]} County, but no tax jurisdiction is "
        f"configured for it — add it in tax settings"
    )


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

    # ⚠️ WAS ONE SENTENCE FOR EVERY FAILURE — "no cemetery county and the
    # customer's zip matched no jurisdiction" — which is true of a customer with
    # no address, a customer whose ZIP spans two counties, and a county nobody
    # configured. Three different actions, one message. Now the specific one.
    missing = unresolved_reason_for_customer(db, customer_id, cemetery_id)
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
