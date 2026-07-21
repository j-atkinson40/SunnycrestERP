"""Sales-tax accumulation & filing — the period accumulator and the return.

THE PERIOD RULE (stated at the site, per NY practice): sales-tax
periods follow the New York quarterly sales-tax calendar — Q1 Mar 1–May
31, Q2 Jun 1–Aug 31, Q3 Sep 1–Nov 30, Q4 Dec 1–Feb 28/29 — assignment
BY INVOICE DATE. Returns are due the 20th of the month after the
period ends (the ST-100 rhythm). Monthly filers (company setting
`tax_filing_frequency = "monthly"`) accumulate calendar months instead.
Filing law is the operator's and his CPA's — this module implements the
statutory NY calendar and flags gaps; it never improvises exemptions.

ACCUMULATION IS RECOMPUTE-AND-REPLACE: a period's rows are deleted and
rebuilt from the invoices' stored truth, so re-running is drift-free by
construction (idempotency pinned). The accumulator NEVER writes back to
invoices — history accumulates as stored, classified honestly
(forward invoices carry structured tax facts from birth; historical
NULL-source rows land in the unclassified bucket with a gap note).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.tax_filing import TaxPeriod

logger = logging.getLogger(__name__)

# Reason-class vocabulary for exempt/zero-tax sales. The return reports
# exempt sales BY CLASS; certificates are citable from their records.
EXEMPT_CLASSES = (
    "product_exempt",
    "job_certificate",
    "customer_certificate",
    "override_zero",
    "unresolved",
    "zero_tax_unclassified",
)

# Invoice statuses that represent real sales for filing. Write-offs
# stay included: the sale (and its tax) happened — a collection loss is
# not a tax reversal (bad-debt credits are the CPA's call, not ours).
FILING_STATUSES = ("posted", "sent", "partial", "paid", "overdue", "write_off")


# ---------------------------------------------------------------------------
# Periods — the NY sales-tax calendar
# ---------------------------------------------------------------------------


def period_for_date(d: date, frequency: str = "quarterly") -> dict:
    """Assign a date to its filing period BY INVOICE DATE (NY practice)."""
    if frequency == "monthly":
        start = date(d.year, d.month, 1)
        end = (date(d.year + 1, 1, 1) if d.month == 12
               else date(d.year, d.month + 1, 1))
        from datetime import timedelta
        end = end - timedelta(days=1)
        return {"key": f"{d.year}-{d.month:02d}", "start": start, "end": end,
                "label": start.strftime("%B %Y")}

    # NY quarterly sales-tax calendar (Q1 = Mar–May of the labeled year).
    if 3 <= d.month <= 5:
        year, q, start, end = d.year, 1, date(d.year, 3, 1), date(d.year, 5, 31)
    elif 6 <= d.month <= 8:
        year, q, start, end = d.year, 2, date(d.year, 6, 1), date(d.year, 8, 31)
    elif 9 <= d.month <= 11:
        year, q, start, end = d.year, 3, date(d.year, 9, 1), date(d.year, 11, 30)
    elif d.month == 12:
        year, q = d.year, 4
        start = date(d.year, 12, 1)
        end = _feb_end(d.year + 1)
    else:  # Jan/Feb belong to the prior year's Q4
        year, q = d.year - 1, 4
        start = date(d.year - 1, 12, 1)
        end = _feb_end(d.year)
    return {"key": f"{year}-Q{q}", "start": start, "end": end,
            "label": f"Q{q} {year} ({start.strftime('%b %-d')} – {end.strftime('%b %-d, %Y')})"}


def _feb_end(year: int) -> date:
    return date(year, 2, 29) if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else date(year, 2, 28)


def due_date_for_period(period_end: date) -> date:
    """Returns are due the 20th of the month after the period ends."""
    if period_end.month == 12:
        return date(period_end.year + 1, 1, 20)
    return date(period_end.year, period_end.month + 1, 20)


def _company_frequency(db: Session, company_id: str) -> str:
    from app.models.company import Company
    company = db.query(Company).filter(Company.id == company_id).first()
    settings = (company.settings or {}) if company else {}
    freq = settings.get("tax_filing_frequency", "quarterly")
    return freq if freq in ("monthly", "quarterly") else "quarterly"


# ---------------------------------------------------------------------------
# Classification — the invoices' stored truth, honestly bucketed
# ---------------------------------------------------------------------------


def classify_invoice(db: Session, inv: Invoice) -> dict:
    """Classify ONE invoice's tax facts from stored truth (read-only).

    Forward invoices carry tax_source/tax_jurisdiction from birth.
    Historical rows (NULL source) classify from amounts alone: taxed →
    taxable under a derived-or-unassigned jurisdiction; zero-tax →
    the unclassified bucket with a gap note. Never writes back.
    """
    taxable = (inv.subtotal or Decimal("0.00")) - (inv.exempt_amount or Decimal("0.00"))
    exempt = inv.exempt_amount or Decimal("0.00")
    tax = inv.tax_amount or Decimal("0.00")
    gap = None

    if inv.tax_jurisdiction:
        jurisdiction = inv.tax_jurisdiction
    elif tax > 0:
        jurisdiction = _derive_jurisdiction(db, inv) or f"rate {(inv.tax_rate or 0) * 100:.2f}% (jurisdiction unassigned)"
        if "unassigned" in jurisdiction:
            gap = f"{inv.number}: taxed but no jurisdiction on record or derivable"
    else:
        jurisdiction = "(no jurisdiction — zero tax)"

    if tax > 0:
        cls = "taxable"
    elif inv.tax_source in EXEMPT_CLASSES:
        cls = inv.tax_source
        exempt = exempt if exempt > 0 else (inv.subtotal or Decimal("0.00"))
        taxable = (inv.subtotal or Decimal("0.00")) - exempt
    elif inv.tax_source == "override" and tax == 0:
        cls = "override_zero"
        exempt = inv.subtotal or Decimal("0.00")
        taxable = Decimal("0.00")
    else:
        cls = "zero_tax_unclassified"
        exempt = inv.subtotal or Decimal("0.00")
        taxable = Decimal("0.00")
        if (inv.subtotal or 0) > 0:
            gap = (f"{inv.number}: zero tax with no recorded exemption "
                   "source — classify before filing")

    return {"jurisdiction": jurisdiction, "class": cls,
            "taxable": taxable, "exempt": exempt, "tax": tax, "gap": gap}


def _derive_jurisdiction(db: Session, inv: Invoice) -> str | None:
    """Best-available jurisdiction for a historical invoice: the
    customer's county via the same U-1 chain. Marked derived — the
    stored column is authoritative when present."""
    try:
        from app.services.tax_service import get_jurisdiction_for_order
        jur, _rate = get_jurisdiction_for_order(db, inv.company_id, None, inv.customer_id)
        if jur:
            return f"{jur.county} County, {jur.state} (derived)"
    except Exception:
        pass
    return None


def stamp_invoice_tax_facts(db: Session, invoice: Invoice, order=None) -> None:
    """Populate the structured tax facts on a NEWBORN invoice (forward
    only — the accumulator never rewrites history). Reason carries from
    the source quote when one exists (carry-not-recompute); jurisdiction
    derives from the customer at birth and is stored as charged."""
    reason = None
    if order is not None and getattr(order, "quote_id", None):
        from app.models.quote import Quote
        q = db.query(Quote).filter(Quote.id == order.quote_id).first()
        if q is not None:
            reason = q.tax_reason
    if reason:
        invoice.tax_reason = reason
        if reason.startswith("resolved:"):
            invoice.tax_source = "jurisdiction"
        elif reason.startswith("override:"):
            invoice.tax_source = "override"
        elif "job certificate" in reason:
            invoice.tax_source = "job_certificate"
        elif "customer certificate" in reason:
            invoice.tax_source = "customer_certificate"
        elif "product-exempt" in reason:
            invoice.tax_source = "product_exempt"
        elif reason.startswith("exempt:"):
            invoice.tax_source = "customer_certificate"
        elif reason.startswith("unresolved:"):
            invoice.tax_source = "unresolved"
    elif (invoice.tax_amount or 0) > 0:
        invoice.tax_source = "jurisdiction"
        invoice.tax_reason = f"carried from order at {(invoice.tax_rate or 0) * 100:.2f}%"
    # else: zero tax, no reason — stays NULL, lands unclassified honestly.

    if invoice.tax_jurisdiction is None:
        derived = _derive_jurisdiction(db, invoice)
        if derived:
            invoice.tax_jurisdiction = derived.replace(" (derived)", "")


# ---------------------------------------------------------------------------
# The accumulator — recompute-and-replace, drift-free by construction
# ---------------------------------------------------------------------------


def accumulate_period(db: Session, company_id: str, period_key: str | None = None,
                      on: date | None = None) -> dict:
    """Rebuild the accumulator rows for one period (default: the period
    containing `on`/today) from the invoices' stored truth. Idempotent:
    delete-and-rebuild — re-running produces byte-identical rows."""
    freq = _company_frequency(db, company_id)
    if period_key is None:
        p = period_for_date(on or date.today(), freq)
    else:
        p = _period_from_key(period_key, freq)

    invoices = (
        db.query(Invoice)
        .filter(
            Invoice.company_id == company_id,
            Invoice.status.in_(FILING_STATUSES),
            Invoice.is_finance_charge.is_(False),
            Invoice.invoice_date >= datetime.combine(p["start"], datetime.min.time(), timezone.utc),
            Invoice.invoice_date <= datetime.combine(p["end"], datetime.max.time(), timezone.utc),
        )
        .all()
    )

    buckets: dict[str, dict] = {}
    gaps: list[str] = []
    for inv in invoices:
        c = classify_invoice(db, inv)
        b = buckets.setdefault(c["jurisdiction"], {
            "gross": Decimal("0.00"), "taxable": Decimal("0.00"),
            "exempt": Decimal("0.00"), "tax": Decimal("0.00"),
            "count": 0, "by_class": {},
        })
        b["gross"] += (inv.subtotal or Decimal("0.00"))
        b["taxable"] += c["taxable"]
        b["exempt"] += c["exempt"]
        b["tax"] += c["tax"]
        b["count"] += 1
        if c["exempt"] > 0:
            key = c["class"] if c["class"] != "taxable" else "partial_product_exempt"
            b["by_class"][key] = float(Decimal(str(b["by_class"].get(key, 0))) + c["exempt"])
        if c["gap"]:
            gaps.append(c["gap"])

    # Certificate-gap sweep: exemption flags without valid certificates
    # among this period's customers (the return that tells you what to
    # fix before filing).
    gaps.extend(_certificate_gaps(db, company_id, {i.customer_id for i in invoices}, p["end"]))

    db.query(TaxPeriod).filter(
        TaxPeriod.company_id == company_id,
        TaxPeriod.period_key == p["key"],
    ).delete()
    now = datetime.now(timezone.utc)
    for jname, b in sorted(buckets.items()):
        db.add(TaxPeriod(
            company_id=company_id, period_key=p["key"],
            period_start=p["start"], period_end=p["end"],
            jurisdiction_name=jname,
            gross_sales=b["gross"], taxable_sales=b["taxable"],
            exempt_sales=b["exempt"], exempt_by_class=b["by_class"],
            tax_computed=b["tax"], invoice_count=b["count"],
            gaps=gaps if jname == sorted(buckets)[0] else None,
            last_accumulated_at=now,
        ))
    if not buckets:
        db.add(TaxPeriod(
            company_id=company_id, period_key=p["key"],
            period_start=p["start"], period_end=p["end"],
            jurisdiction_name="(no sales)", gaps=gaps or None,
            last_accumulated_at=now,
        ))
    db.commit()
    return {"period_key": p["key"], "jurisdictions": len(buckets),
            "invoices": len(invoices), "gaps": len(gaps)}


def _period_from_key(key: str, frequency: str) -> dict:
    if "-Q" in key:
        year, q = key.split("-Q")
        month = {1: 3, 2: 6, 3: 9, 4: 12}[int(q)]
        return period_for_date(date(int(year), month, 1), "quarterly")
    year, month = key.split("-")
    return period_for_date(date(int(year), int(month), 1), "monthly")


def _certificate_gaps(db: Session, company_id: str, customer_ids: set, on: date) -> list[str]:
    from app.models.customer import Customer
    from app.services.tax_service import _find_valid_certificate
    from app.models.tax_filing import TaxCertificate

    out = []
    if not customer_ids:
        return out
    flagged = (
        db.query(Customer)
        .filter(Customer.company_id == company_id,
                Customer.id.in_(customer_ids),
                Customer.tax_exempt.is_(True))
        .all()
    )
    for cust in flagged:
        cert, _scope = _find_valid_certificate(db, company_id, cust.id, None, on)
        if cert is None:
            out.append(f"{cust.name}: exemption flag without a valid certificate on file")
        elif cert.vault_document_id is None:
            out.append(f"{cust.name}: certificate {cert.cert_number or cert.cert_type} has no attached scan")
    return out


# ---------------------------------------------------------------------------
# The return — the ST-100's feeding shape
# ---------------------------------------------------------------------------


def get_return(db: Session, company_id: str, period_key: str | None = None) -> dict:
    """The by-jurisdiction filing report for a period: gross · exempt
    (by reason class) · taxable · tax computed, plus THE GAPS LIST —
    the return that tells you what to fix before filing."""
    freq = _company_frequency(db, company_id)
    if period_key is None:
        period_key = period_for_date(date.today(), freq)["key"]
    p = _period_from_key(period_key, freq)

    rows = (
        db.query(TaxPeriod)
        .filter(TaxPeriod.company_id == company_id,
                TaxPeriod.period_key == period_key)
        .order_by(TaxPeriod.jurisdiction_name)
        .all()
    )
    gaps: list[str] = []
    for r in rows:
        if r.gaps:
            gaps.extend(r.gaps)
    jurisdictions = [
        {
            "jurisdiction": r.jurisdiction_name,
            "gross_sales": float(r.gross_sales),
            "taxable_sales": float(r.taxable_sales),
            "exempt_sales": float(r.exempt_sales),
            "exempt_by_class": r.exempt_by_class or {},
            "tax_computed": float(r.tax_computed),
            "invoice_count": r.invoice_count,
        }
        for r in rows if r.jurisdiction_name != "(no sales)"
    ]
    accumulated = rows[0].last_accumulated_at.isoformat() if rows else None
    return {
        "period_key": period_key,
        "period_label": p["label"],
        "period_start": str(p["start"]),
        "period_end": str(p["end"]),
        "due_date": str(due_date_for_period(p["end"])),
        "frequency": freq,
        "period_rule": ("NY quarterly sales-tax calendar (Mar–May / Jun–Aug / "
                        "Sep–Nov / Dec–Feb), assigned by invoice date; due the "
                        "20th after period end" if freq == "quarterly"
                        else "calendar months, assigned by invoice date"),
        "jurisdictions": jurisdictions,
        "totals": {
            "gross_sales": sum(j["gross_sales"] for j in jurisdictions),
            "taxable_sales": sum(j["taxable_sales"] for j in jurisdictions),
            "exempt_sales": sum(j["exempt_sales"] for j in jurisdictions),
            "tax_computed": sum(j["tax_computed"] for j in jurisdictions),
        },
        "gaps": gaps,
        "accumulated_at": accumulated,
    }


def available_periods(db: Session, company_id: str) -> list[dict]:
    """Periods with accumulator rows, newest first, plus the current one."""
    freq = _company_frequency(db, company_id)
    current = period_for_date(date.today(), freq)
    keys = [k for (k,) in (
        db.query(TaxPeriod.period_key)
        .filter(TaxPeriod.company_id == company_id)
        .distinct().all()
    )]
    if current["key"] not in keys:
        keys.append(current["key"])
    out = []
    for k in sorted(keys, reverse=True):
        p = _period_from_key(k, freq)
        out.append({"key": k, "label": p["label"],
                    "due_date": str(due_date_for_period(p["end"]))})
    return out
