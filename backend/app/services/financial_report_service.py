"""Financial report service — 13 report types + audit health checks.

Each method returns structured data consumed by the UI and PDF generator.
All monetary calculations use Decimal, never float.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.journal_entry import JournalEntry, JournalEntryLine
from app.models.report import AuditHealthCheck, AuditPackage, ReportRun
from app.models.vendor_bill import VendorBill
from app.models.vendor_bill_line import VendorBillLine

logger = logging.getLogger(__name__)


def _log_run(db: Session, tenant_id: str, report_type: str, params: dict, user_id: str | None, row_count: int = 0) -> ReportRun:
    run = ReportRun(tenant_id=tenant_id, report_type=report_type, parameters=params, status="complete",
                    row_count=row_count, generated_by=user_id, completed_at=datetime.now(timezone.utc))
    db.add(run)
    db.commit()
    return run


# ---------------------------------------------------------------------------
# REPORT 1: Income Statement
# ---------------------------------------------------------------------------

# The income statement, in the ruled order. `delivery_cost` sits BELOW gross
# profit deliberately: it is a cost of getting product to the customer, not a
# cost of producing it, and burying it in COGS makes gross margin
# incomparable across licensees who deliver differently.
#
# Sign conventions. Revenue-natured categories carry a CREDIT balance, so their
# figure is credits - debits. Everything else is debit-natured. `contra_revenue`
# is debit-natured AND subtracted from revenue, which is why it is listed with
# revenue rather than with the costs.
_PL_SECTIONS: tuple[tuple[str, str, str], ...] = (
    ("revenue",        "Revenue",              "credit"),
    ("contra_revenue", "Less: contra revenue", "debit"),
    ("cogs",           "Cost of goods sold",   "debit"),
    ("delivery_cost",  "Delivery costs",       "debit"),
    ("expense",        "Operating expenses",   "debit"),
    ("tax_expense",    "Tax expense",          "debit"),
    ("other_income",   "Other income",         "credit"),
    ("other_expense",  "Other expense",        "debit"),
)

# Categories that belong on the BALANCE SHEET. Their lines are excluded from the
# P&L rather than swept into a bucket.
_BALANCE_SHEET_CATEGORIES = frozenset({
    "current_asset", "fixed_asset", "current_liability",
    "long_term_liability", "equity",
})

# Genuinely miscellaneous or not yet classified. These CANNOT be honestly placed
# on an income statement — `other` may be either an income or a balance-sheet
# account — so they are reported separately and excluded from net income, with
# the amount stated so nobody has to guess how much was set aside.
_UNPLACEABLE_CATEGORIES = frozenset({"other", "unclassified"})


def get_income_statement(db: Session, tenant_id: str, period_start: date, period_end: date,
                         comparison_start: date | None = None, comparison_end: date | None = None,
                         user_id: str | None = None) -> dict:
    """Revenue - contra revenue - COGS = gross profit; then costs below it.

    Reads the LEDGER. Before A-3 this read invoices and vendor bills, so a
    posted journal entry was invisible to the P&L, and revenue was a single
    fabricated `4000 Sales Revenue` row holding every invoice total, summed in
    binary float in a module whose docstring says "never float".

    Lines whose `gl_account_id` does not resolve to one of this tenant's GL
    mappings are counted in `unplaceable`, never dropped. The low-level
    `create_journal_entry` does no GL lookup (the API-level `create_entry`
    does), so unresolvable lines are possible, and an income statement that
    silently omits them would be wrong in exactly the way that is hardest to
    notice.
    """
    sections, unplaceable, totals = _pl_sections(db, tenant_id, period_start, period_end)

    def t(cat: str) -> Decimal:
        return totals.get(cat, Decimal("0"))

    gross_profit = t("revenue") - t("contra_revenue") - t("cogs")
    operating_income = gross_profit - t("delivery_cost") - t("expense")
    net_income = (operating_income - t("tax_expense")
                  + t("other_income") - t("other_expense"))

    result = {
        "period": {"start": str(period_start), "end": str(period_end)},
        "sections": sections,
        "gross_profit": gross_profit,
        "gross_margin_percent": (
            (gross_profit / t("revenue") * 100).quantize(Decimal("0.1"))
            if t("revenue") else Decimal("0.0")
        ),
        "operating_income": operating_income,
        "net_income": net_income,
        "has_postings": any(sec["accounts"] for sec in sections) or bool(unplaceable["accounts"]),
        "unplaceable": unplaceable,
        "reconciliation": _reconcile_revenue_to_ar(db, tenant_id, period_start,
                                                   period_end, t("revenue")),
        "expense_reconciliation": _reconcile_expense_to_ap(
            db, tenant_id, period_start, period_end,
            t("cogs") + t("delivery_cost") + t("expense")),
        # Retained for existing callers. `revenue`/`cogs`/`expenses` are the
        # section rows; the flat totals keep the old key names.
        "revenue": next(s["accounts"] for s in sections if s["category"] == "revenue"),
        "total_revenue": t("revenue"),
        "cogs": next(s["accounts"] for s in sections if s["category"] == "cogs"),
        "total_cogs": t("cogs"),
        "expenses": next(s["accounts"] for s in sections if s["category"] == "expense"),
        "total_expenses": t("expense"),
    }

    if comparison_start and comparison_end:
        _, _, comp_totals = _pl_sections(db, tenant_id, comparison_start, comparison_end)

        def ct(cat: str) -> Decimal:
            return comp_totals.get(cat, Decimal("0"))

        comp_gross = ct("revenue") - ct("contra_revenue") - ct("cogs")
        result["comparison_period"] = {"start": str(comparison_start), "end": str(comparison_end)}
        result["comparison_net_income"] = (
            comp_gross - ct("delivery_cost") - ct("expense") - ct("tax_expense")
            + ct("other_income") - ct("other_expense")
        )

    _log_run(db, tenant_id, "income_statement",
             {"period_start": str(period_start), "period_end": str(period_end)},
             user_id, sum(len(s["accounts"]) for s in sections))
    return result


def _pl_sections(db: Session, tenant_id: str, start: date, end: date):
    """Ledger lines for the period, grouped into P&L sections by GL category."""
    from app.models.accounting_analysis import TenantGLMapping

    rows = (
        db.query(
            TenantGLMapping.platform_category.label("category"),
            JournalEntryLine.gl_account_number.label("number"),
            JournalEntryLine.gl_account_name.label("name"),
            func.coalesce(func.sum(JournalEntryLine.debit_amount), 0).label("debits"),
            func.coalesce(func.sum(JournalEntryLine.credit_amount), 0).label("credits"),
        )
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .outerjoin(TenantGLMapping, TenantGLMapping.id == JournalEntryLine.gl_account_id)
        .filter(
            JournalEntryLine.tenant_id == tenant_id,
            JournalEntry.status.in_(_LEDGER_STATUSES),
            JournalEntry.entry_date >= start,
            JournalEntry.entry_date <= end,
        )
        .group_by(TenantGLMapping.platform_category,
                  JournalEntryLine.gl_account_number,
                  JournalEntryLine.gl_account_name)
        .all()
    )

    by_category: dict[str, list[dict]] = {}
    totals: dict[str, Decimal] = {}
    unplaceable_accounts: list[dict] = []
    unplaceable_total = Decimal("0")

    natural = {cat: sign for cat, _, sign in _PL_SECTIONS}

    for r in rows:
        debits = Decimal(str(r.debits))
        credits = Decimal(str(r.credits))
        cat = r.category

        if cat in _BALANCE_SHEET_CATEGORIES:
            continue

        if cat is None or cat in _UNPLACEABLE_CATEGORIES:
            unplaceable_accounts.append({
                "account_number": r.number, "account_name": r.name,
                "category": cat, "debits": debits, "credits": credits,
                "reason": ("no GL mapping for this line's gl_account_id"
                           if cat is None else f"category {cat!r} is not a P&L section"),
            })
            unplaceable_total += (debits - credits)
            continue

        amount = credits - debits if natural[cat] == "credit" else debits - credits
        by_category.setdefault(cat, []).append({
            "account_number": r.number, "account_name": r.name, "amount": amount,
        })
        totals[cat] = totals.get(cat, Decimal("0")) + amount

    sections = [
        {"category": cat, "label": label,
         "accounts": sorted(by_category.get(cat, []),
                            key=lambda a: a["account_number"] or ""),
         "total": totals.get(cat, Decimal("0"))}
        for cat, label, _ in _PL_SECTIONS
    ]
    unplaceable = {
        "accounts": sorted(unplaceable_accounts, key=lambda a: a["account_number"] or ""),
        "net_amount": unplaceable_total,
        "excluded_from_net_income": True,
    }
    return sections, unplaceable, totals


def _reconcile_revenue_to_ar(db: Session, tenant_id: str, start: date, end: date,
                             gl_revenue: Decimal) -> dict:
    """GL revenue against the AR subledger for the same period.

    Live from A-3 onward, and it could not have been meaningful before: until
    revenue came from the GL there was nothing to reconcile it TO — the old
    figure WAS the invoice total, so the two sides were the same number and
    agreement was tautological.

    A difference is not automatically an error. Revenue recognised by journal
    entry without an invoice, or an invoice raised for something that is not
    revenue, both show up here legitimately. It is a prompt to look, which is
    why it reports the figures rather than a pass/fail.
    """
    invoiced = (
        db.query(func.coalesce(func.sum(Invoice.total), 0))
        .filter(Invoice.company_id == tenant_id,
                Invoice.invoice_date >= start,
                Invoice.invoice_date <= end,
                Invoice.status.in_(["posted", "sent", "paid", "partial", "overdue"]))
        .scalar()
    )
    ar_revenue = Decimal(str(invoiced or 0))
    difference = gl_revenue - ar_revenue
    return {
        "gl_revenue": gl_revenue,
        "ar_subledger_revenue": ar_revenue,
        "difference": difference,
        "agrees": difference == 0,
    }


def _reconcile_expense_to_ap(db: Session, tenant_id: str, start: date, end: date,
                             gl_expense: Decimal) -> dict:
    """GL expenses against the AP subledger, symmetric to the AR side.

    THIS ONE MATTERS MORE THAN ITS TWIN, and the reason should not be buried.
    `ar_invoice_posting` exists, so an invoice CAN reach the ledger. There is no
    equivalent for vendor bills — nothing anywhere posts AP to the GL. So ledger
    expenses are structurally empty, not merely empty today, until an AP posting
    path is built.

    Before A-3 the P&L showed vendor-bill expenses via `_sum_by_gl_type`, which
    D-2 did real work to make honest. Reading the ledger instead is correct — it
    is the source of truth — but it means those expenses stop appearing, and
    without this the disappearance would be SILENT. That is the defect shape
    this arc keeps closing, so it is not being introduced here.
    """
    from app.models.vendor_bill import VendorBill

    billed = (
        db.query(func.coalesce(func.sum(VendorBill.total), 0))
        .filter(VendorBill.company_id == tenant_id,
                VendorBill.deleted_at.is_(None),
                VendorBill.status.notin_(("draft", "void")),
                VendorBill.bill_date >= start,
                # END-EXCLUSIVE. `bill_date` is a DATETIME, not a date, so
                # `<= end` silently drops every bill timestamped after midnight
                # on the closing day. Same boundary discipline as D-1/D-2.
                VendorBill.bill_date < end + timedelta(days=1))
        .scalar()
    )
    ap_expense = Decimal(str(billed or 0))
    difference = gl_expense - ap_expense
    return {
        "gl_expense": gl_expense,
        "ap_subledger_expense": ap_expense,
        "difference": difference,
        "agrees": difference == 0,
        "note": ("No AP-to-GL posting path exists, so a non-zero AP subledger "
                 "with zero GL expense is expected rather than anomalous."),
    }


# ---------------------------------------------------------------------------
# REPORT 5: AR Aging
# ---------------------------------------------------------------------------

def get_ar_aging_report(db: Session, tenant_id: str, as_of: date | None = None, user_id: str | None = None) -> dict:
    """AR aging by customer with buckets."""
    as_of = as_of or date.today()
    invoices = db.query(Invoice).filter(
        Invoice.company_id == tenant_id,
        Invoice.status.in_(["sent", "partial", "overdue"]),
    ).all()

    customer_map: dict[str, dict] = {}
    for inv in invoices:
        cid = inv.customer_id
        if cid not in customer_map:
            cust = db.query(Customer).filter(Customer.id == cid).first()
            customer_map[cid] = {
                "customer_id": cid, "customer_name": cust.name if cust else "Unknown",
                "current": 0, "days_1_30": 0, "days_31_60": 0, "days_61_90": 0, "days_over_90": 0, "total": 0,
            }
        balance = float(inv.total - (inv.amount_paid or 0))
        days = (as_of - inv.due_date).days if inv.due_date else 0
        bucket = "current" if days <= 0 else "days_1_30" if days <= 30 else "days_31_60" if days <= 60 else "days_61_90" if days <= 90 else "days_over_90"
        customer_map[cid][bucket] += balance
        customer_map[cid]["total"] += balance

    customers = sorted(customer_map.values(), key=lambda x: x["total"], reverse=True)
    totals = {k: sum(c[k] for c in customers) for k in ["current", "days_1_30", "days_31_60", "days_61_90", "days_over_90", "total"]}

    _log_run(db, tenant_id, "ar_aging", {"as_of": str(as_of)}, user_id, len(customers))
    return {"as_of_date": str(as_of), "customers": customers, "totals": totals, "customer_count": len(customers)}


# ---------------------------------------------------------------------------
# REPORT 6: AP Aging
# ---------------------------------------------------------------------------

def get_ap_aging_report(db: Session, tenant_id: str, as_of: date | None = None, user_id: str | None = None) -> dict:
    """AP aging by vendor — DELEGATES to the canonical ap_aging_service (D-2).

    Pre-rework this site imported the dead `app.models.bill` inside a
    try/except and confidently returned an EMPTY vendor list on every call
    (audit C-3). The real aging engine already existed; this report is now a
    shape adapter over it: due-date buckets, balance_remaining (partials
    reduce the amount aged), statuses pending/approved/partial, soft-deletes
    excluded. LOUD-FAILURE CONTRACT: no fallback — if aging cannot compute,
    this raises (a missing report gets investigated; a wrong one gets read).
    """
    from app.services.ap_aging_service import get_ap_aging

    as_of = as_of or date.today()
    # Midnight-UTC of as_of: a bill due ON as_of ages 0 days → current.
    as_of_dt = datetime(as_of.year, as_of.month, as_of.day, tzinfo=timezone.utc)

    rows = get_ap_aging(db, tenant_id, as_of_dt)
    vendors = [
        {
            "vendor_id": r["vendor_id"],
            "vendor_name": r["vendor_name"],
            "current": float(r["current"]),
            "days_1_30": float(r["d1_30"]),
            "days_31_60": float(r["d31_60"]),
            "days_61_90": float(r["d61_90"]),
            "days_over_90": float(r["d90_plus"]),
            "total": float(r["total"]),
        }
        for r in rows
    ]
    totals = {k: round(sum(v[k] for v in vendors), 2) for k in ["current", "days_1_30", "days_31_60", "days_61_90", "days_over_90", "total"]}

    _log_run(db, tenant_id, "ap_aging", {"as_of": str(as_of)}, user_id, len(vendors))
    return {"as_of_date": str(as_of), "vendors": vendors, "totals": totals, "vendor_count": len(vendors)}


# ---------------------------------------------------------------------------
# REPORT 7: Sales by Customer
# ---------------------------------------------------------------------------

def get_sales_by_customer(db: Session, tenant_id: str, period_start: date, period_end: date, user_id: str | None = None) -> dict:
    invoices = db.query(Invoice).filter(
        Invoice.company_id == tenant_id,
        Invoice.invoice_date >= period_start, Invoice.invoice_date <= period_end,
    ).all()

    customer_map: dict[str, dict] = {}
    for inv in invoices:
        cid = inv.customer_id
        if cid not in customer_map:
            cust = db.query(Customer).filter(Customer.id == cid).first()
            customer_map[cid] = {"customer_id": cid, "customer_name": cust.name if cust else "Unknown",
                                  "invoice_count": 0, "total_invoiced": 0, "total_paid": 0}
        customer_map[cid]["invoice_count"] += 1
        customer_map[cid]["total_invoiced"] += float(inv.total)
        customer_map[cid]["total_paid"] += float(inv.amount_paid or 0)

    for c in customer_map.values():
        c["total_outstanding"] = c["total_invoiced"] - c["total_paid"]
        c["average_invoice"] = round(c["total_invoiced"] / c["invoice_count"], 2) if c["invoice_count"] else 0

    customers = sorted(customer_map.values(), key=lambda x: x["total_invoiced"], reverse=True)
    _log_run(db, tenant_id, "sales_by_customer", {"period_start": str(period_start), "period_end": str(period_end)}, user_id, len(customers))
    return {"period": {"start": str(period_start), "end": str(period_end)}, "customers": customers}


# ---------------------------------------------------------------------------
# REPORT 9: Invoice Register
# ---------------------------------------------------------------------------

def get_invoice_register(db: Session, tenant_id: str, period_start: date, period_end: date, user_id: str | None = None) -> dict:
    invoices = db.query(Invoice).filter(
        Invoice.company_id == tenant_id,
        Invoice.invoice_date >= period_start, Invoice.invoice_date <= period_end,
    ).order_by(Invoice.invoice_date).all()

    rows = []
    for inv in invoices:
        cust = db.query(Customer).filter(Customer.id == inv.customer_id).first()
        rows.append({
            "invoice_number": inv.invoice_number, "date": str(inv.invoice_date),
            "customer_name": cust.name if cust else "Unknown",
            "due_date": str(inv.due_date) if inv.due_date else None,
            "total": float(inv.total), "amount_paid": float(inv.amount_paid or 0),
            "balance_due": float(inv.total - (inv.amount_paid or 0)),
            "status": inv.status,
        })

    _log_run(db, tenant_id, "invoice_register", {"period_start": str(period_start), "period_end": str(period_end)}, user_id, len(rows))
    return {"period": {"start": str(period_start), "end": str(period_end)}, "invoices": rows,
            "totals": {"total": sum(r["total"] for r in rows), "paid": sum(r["amount_paid"] for r in rows), "balance": sum(r["balance_due"] for r in rows)}}


# ---------------------------------------------------------------------------
# REPORT 13: Tax Summary
# ---------------------------------------------------------------------------

def get_tax_summary(db: Session, tenant_id: str, period_start: date, period_end: date, user_id: str | None = None) -> dict:
    """Tax by jurisdiction for filing — reads the invoices' stored truth
    through the sales-tax arc's classifier (the hardcoded-zero stub died
    by replacement). Arbitrary ranges classify live; the period
    accumulator at /tax/returns is the filing-shaped surface."""
    from datetime import datetime as _dt, timezone as _tz
    from decimal import Decimal as _D

    from app.models.invoice import Invoice
    from app.services.tax_filing_service import FILING_STATUSES, classify_invoice

    invoices = (
        db.query(Invoice)
        .filter(
            Invoice.company_id == tenant_id,
            Invoice.status.in_(FILING_STATUSES),
            Invoice.is_finance_charge.is_(False),
            Invoice.invoice_date >= _dt.combine(period_start, _dt.min.time(), _tz.utc),
            Invoice.invoice_date <= _dt.combine(period_end, _dt.max.time(), _tz.utc),
        )
        .all()
    )
    buckets: dict[str, dict] = {}
    for inv in invoices:
        c = classify_invoice(db, inv)
        b = buckets.setdefault(c["jurisdiction"], {"taxable": _D("0"), "exempt": _D("0"), "tax": _D("0")})
        b["taxable"] += c["taxable"]
        b["exempt"] += c["exempt"]
        b["tax"] += c["tax"]

    jurisdictions = [
        {"jurisdiction": name, "taxable_sales": float(b["taxable"]),
         "exempt_sales": float(b["exempt"]), "tax_collected": float(b["tax"])}
        for name, b in sorted(buckets.items())
    ]
    result = {
        "period": {"start": str(period_start), "end": str(period_end)},
        "jurisdictions": jurisdictions,
        "total_tax": sum(j["tax_collected"] for j in jurisdictions),
        "total_taxable": sum(j["taxable_sales"] for j in jurisdictions),
        "exempt_total": sum(j["exempt_sales"] for j in jurisdictions),
    }
    _log_run(db, tenant_id, "tax_summary", {"period_start": str(period_start), "period_end": str(period_end)}, user_id, len(jurisdictions))
    return result


# ---------------------------------------------------------------------------
# Audit Health Check
# ---------------------------------------------------------------------------

def run_health_check(db: Session, tenant_id: str) -> dict:
    """Run all audit health checks and return findings."""
    today = date.today()
    findings = []

    # Check: reconciliation overdue
    try:
        from app.models.financial_account import FinancialAccount
        overdue_accounts = db.query(FinancialAccount).filter(
            FinancialAccount.tenant_id == tenant_id, FinancialAccount.is_active == True,
        ).all()
        for acct in overdue_accounts:
            if acct.last_reconciled_date and (today - acct.last_reconciled_date).days > 35:
                findings.append({"severity": "amber", "category": "reconciliation", "code": "recon_overdue",
                                  "message": f"{acct.account_name} is {(today - acct.last_reconciled_date).days} days since last reconciliation",
                                  "action_label": "Reconcile", "action_url": f"/settings/accounts"})
            elif not acct.last_reconciled_date:
                findings.append({"severity": "amber", "category": "reconciliation", "code": "never_reconciled",
                                  "message": f"{acct.account_name} has never been reconciled", "action_label": "Reconcile", "action_url": "/settings/accounts"})
    except Exception:
        logger.warning("health check 'reconciliation' failed — finding silently absent", exc_info=True)

    # Check: stale draft journal entries
    try:
        from app.models.journal_entry import JournalEntry
        stale_count = db.query(func.count(JournalEntry.id)).filter(
            JournalEntry.tenant_id == tenant_id, JournalEntry.status == "draft",
            JournalEntry.created_at < datetime.now(timezone.utc) - timedelta(days=7),
        ).scalar() or 0
        if stale_count > 0:
            findings.append({"severity": "amber", "category": "journal_entries", "code": "stale_drafts",
                              "message": f"{stale_count} journal entries in draft for over 7 days",
                              "action_label": "Review Drafts", "action_url": "/journal-entries?status=draft"})
    except Exception:
        logger.warning("health check 'stale_drafts' failed — finding silently absent", exc_info=True)

    # ⚠️ BOTH TAX CHECKS BELOW QUERIED `customers.tax_status` AND RAISED
    # AttributeError ON EVERY CALL, ON EVERY TENANT, SINCE THEY WERE WRITTEN.
    # Those columns are in the database and were never mapped onto the
    # `Customer` model. Each check caught the error into a bare
    # `except Exception` whose own comment read "finding silently absent" — so a
    # RED compliance finding and an amber one have never been able to fire, and
    # the report rendered exactly as it would if both had run and found nothing.
    #
    # Measured when this was found: no customer on any tenant was exempt, so
    # both would legitimately have reported zero. That is luck, not correctness.
    # The first customer marked exempt is the one nobody would have heard about.
    #
    # Repointed at `TaxCertificate` — the model that holds this data and dates
    # it — and the swallow is replaced by `_tax_check`, which reports a check
    # that COULD NOT RUN as its own visible finding. "Did not run" and "found
    # nothing" are different answers and this report used to render them
    # identically.
    from app.models.tax_filing import TaxCertificate

    def _tax_check(code: str, severity: str, action_label: str, count_query, message):
        """Run a compliance count; surface a failure instead of hiding it."""
        try:
            n = count_query() or 0
        except Exception:
            logger.warning("health check %r failed", code, exc_info=True)
            findings.append({
                "severity": "amber", "category": "tax", "code": f"{code}_check_failed",
                "message": (
                    f"The '{action_label.lower()}' tax check could not run — this is "
                    "NOT a clean result; the condition is unknown."
                ),
                "action_label": "Investigate", "action_url": "/settings/tax?tab=exemptions",
            })
            return
        if n:
            findings.append({
                "severity": severity, "category": "tax", "code": code,
                "message": message(n),
                "action_label": action_label, "action_url": "/settings/tax?tab=exemptions",
            })

    # Check: active certificates with no certificate number recorded
    _tax_check(
        "missing_cert", "amber", "Review",
        lambda: db.query(func.count(TaxCertificate.id)).filter(
            TaxCertificate.company_id == tenant_id,
            TaxCertificate.is_active == True,  # noqa: E712
            TaxCertificate.cert_number.is_(None),
        ).scalar(),
        lambda n: f"{n} exemption certificate{'s' if n != 1 else ''} without a certificate number",
    )

    # Check: certificates past their valid_through date. Open-dated
    # certificates (valid_through NULL) never expire and are excluded by the
    # comparison rather than by an assumption.
    _tax_check(
        "expired_exemptions", "red", "Update",
        lambda: db.query(func.count(TaxCertificate.id)).filter(
            TaxCertificate.company_id == tenant_id,
            TaxCertificate.is_active == True,  # noqa: E712
            TaxCertificate.valid_through < today,
        ).scalar(),
        lambda n: f"{n} tax exemption certificate{'s have' if n != 1 else ' has'} expired",
    )

    # Check: overdue AR over 90 days
    overdue_90 = db.query(func.count(Invoice.id)).filter(
        Invoice.company_id == tenant_id, Invoice.status.in_(["sent", "partial", "overdue"]),
        Invoice.due_date < today - timedelta(days=90),
    ).scalar() or 0
    if overdue_90:
        findings.append({"severity": "red" if overdue_90 > 5 else "amber", "category": "ar", "code": "overdue_90",
                          "message": f"{overdue_90} invoices are over 90 days past due",
                          "action_label": "Review AR", "action_url": "/financials?zone=ar&tab=overdue"})

    # Green checks
    if not any(f["code"] == "recon_overdue" for f in findings) and not any(f["code"] == "never_reconciled" for f in findings):
        findings.append({"severity": "green", "category": "reconciliation", "code": "recon_current", "message": "All accounts reconciled within 35 days"})
    if not any(f["code"] == "expired_exemptions" for f in findings) and not any(f["code"] == "missing_cert" for f in findings):
        findings.append({"severity": "green", "category": "tax", "code": "exemptions_valid", "message": "All exemption certificates are valid"})
    if overdue_90 == 0:
        findings.append({"severity": "green", "category": "ar", "code": "ar_current", "message": "No invoices over 90 days past due"})

    red = sum(1 for f in findings if f["severity"] == "red")
    amber = sum(1 for f in findings if f["severity"] == "amber")
    green = sum(1 for f in findings if f["severity"] == "green")
    overall = "red" if red else "amber" if amber else "green"

    # Upsert health check
    existing = db.query(AuditHealthCheck).filter(
        AuditHealthCheck.tenant_id == tenant_id, AuditHealthCheck.check_date == today,
    ).first()
    if existing:
        existing.overall_score = overall
        existing.green_count = green
        existing.amber_count = amber
        existing.red_count = red
        existing.findings = findings
    else:
        db.add(AuditHealthCheck(
            tenant_id=tenant_id, check_date=today, overall_score=overall,
            green_count=green, amber_count=amber, red_count=red, findings=findings,
        ))
    db.commit()

    return {"overall_score": overall, "green": green, "amber": amber, "red": red, "findings": findings, "check_date": str(today)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sum_by_gl_type(db: Session, tenant_id: str, start: date, end: date, gl_type: str) -> list[dict]:
    """Vendor-bill expenses for the period, categorized honestly (D-2).

    NOT DEAD, BUT NO LONGER CALLED BY THE INCOME STATEMENT (A-3). Read this
    before deciding it is a gap. `get_income_statement` now reads the LEDGER, so
    it no longer routes expenses through here, and nothing else in `app/` calls
    this either. It is kept rather than deleted for two reasons:

      * `tests/test_vendor_bill_reports_rework.py` pins its behaviour, and that
        suite encodes the D-2 vendor-bill categorization work — the honest
        `expense_category` rollup, the end-exclusive boundary, and the
        tax/uncategorized remainder that makes the total tie to bill totals.
        Deleting the function discards that knowledge with it.
      * There is no AP-to-GL posting path anywhere in the codebase, so this is
        currently the ONLY place vendor-bill expenses are aggregated honestly.
        If an AP posting service is built, that changes; until then this is the
        subledger view, and `_reconcile_expense_to_ap` is what tells a reader of
        the P&L that the ledger side is structurally zero rather than genuinely
        zero.

    The `gl_type == "cogs"` branch below was NOT completed in A-3. r174 created
    a COGS dimension, so it could be — but completing a branch inside a function
    nothing invokes is dead code. The income statement gets cogs from the ledger.

    Original docstring follows.


    Pre-rework this imported the dead `app.models.bill` inside a swallow and
    returned [] on every call — the P&L overstated profit by ALL vendor-bill
    expenses (audit C-3). Now: VendorBillLine.amount grouped by
    expense_category (the REAL category dimension the categorization agent
    writes; uncategorized → "General Expenses"), bills status ∉ (draft,
    void), soft-deletes excluded, bill_date in-period END-EXCLUSIVE (the D-1
    boundary discipline). The tax/uncategorized remainder (Σ bill.total −
    Σ lines) lands as an honestly-labeled row so the rollup TIES TO BILL
    TOTALS exactly.

    gl_type == "cogs" returns [] honestly: no COGS dimension exists in the
    model. (The old `total * 0.6` heuristic was DEAD CODE — the swallow
    fired before it ever ran — so this changes nothing observed while
    removing a fabricated ratio.) LOUD-FAILURE: no fallback; errors raise.
    """
    if gl_type != "expense":
        return []

    end_exclusive = end + timedelta(days=1)
    bill_filters = (
        VendorBill.company_id == tenant_id,
        VendorBill.deleted_at.is_(None),
        VendorBill.status.notin_(("draft", "void")),
        VendorBill.bill_date >= start,
        VendorBill.bill_date < end_exclusive,
    )

    line_rows = (
        db.query(VendorBillLine.expense_category, func.sum(VendorBillLine.amount))
        .join(VendorBill, VendorBillLine.bill_id == VendorBill.id)
        .filter(*bill_filters)
        .group_by(VendorBillLine.expense_category)
        .all()
    )
    bill_total = db.query(func.coalesce(func.sum(VendorBill.total), 0)).filter(*bill_filters).scalar() or Decimal("0")

    out: list[dict] = []
    lines_total = Decimal("0")
    for category, amount in sorted(line_rows, key=lambda r: (r[0] or "")):
        amt = Decimal(str(amount or 0))
        lines_total += amt
        if amt == 0:
            continue
        out.append({
            "account_number": "6000",
            "account_name": category or "General Expenses",
            "amount": float(amt),
        })

    remainder = Decimal(str(bill_total)) - lines_total
    if remainder > Decimal("0.005"):
        out.append({
            "account_number": "6999",
            "account_name": "Tax & uncategorized remainder",
            "amount": float(remainder),
        })
    return out


# ---------------------------------------------------------------------------
# REPORT 14: Trial Balance  (LEDGER-1 A-2)
# ---------------------------------------------------------------------------

# Statuses whose lines have actually hit the ledger.
#
# THE REVERSAL TRAP, and the reason this is not `status == "posted"`. Reversing
# an entry (journal_entry_service, ~line 113) creates a NEW entry with
# status="posted" holding the mirrored lines, then sets the ORIGINAL to
# "reversed". The original's lines stay in the table. So a posted-only filter
# keeps the reversal and drops what it reverses, and every account in that pair
# reports the negation of a figure that should be zero. Totals still balance —
# the reversal is internally balanced — so the error is invisible to the one
# check a trial balance is for.
#
# The codebase has not settled this: `== "posted"`, `!= "reversed"` and
# `!= "voided"` all appear, and nothing anywhere sets "voided". Both members of
# a reversed pair belong in the ledger; only drafts do not.
_LEDGER_STATUSES: tuple[str, ...] = ("posted", "reversed")


def get_trial_balance(db: Session, tenant_id: str, as_of: date | None = None,
                      user_id: str | None = None) -> dict:
    """Debits and credits per GL account, cumulative through `as_of`.

    Reads the LEDGER — `journal_entry_lines` — not invoices and vendor bills.
    That is the difference between this and `get_income_statement`, which
    derives figures from source documents and cannot see a manual journal entry
    at all.

    `has_postings` is the field that matters and the reason this returns it
    separately from `balanced`. An empty ledger balances trivially: 0 == 0. A
    caller that reads only `balanced` cannot tell a clean set of books from no
    books, and for most tenants today the honest answer is that there is
    nothing here. `balanced is True and has_postings is False` is not a passing
    trial balance; it is the absence of one.

    Anything with a status this function does not recognise is reported in
    `excluded_statuses` rather than silently dropped — a trial balance that
    quietly omits rows is worse than one that refuses.
    """
    as_of = as_of or date.today()

    rows = (
        db.query(
            JournalEntryLine.gl_account_number.label("number"),
            JournalEntryLine.gl_account_name.label("name"),
            func.coalesce(func.sum(JournalEntryLine.debit_amount), 0).label("debits"),
            func.coalesce(func.sum(JournalEntryLine.credit_amount), 0).label("credits"),
            func.count(JournalEntryLine.id).label("lines"),
        )
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .filter(
            JournalEntryLine.tenant_id == tenant_id,
            JournalEntry.status.in_(_LEDGER_STATUSES),
            JournalEntry.entry_date <= as_of,
        )
        .group_by(JournalEntryLine.gl_account_number, JournalEntryLine.gl_account_name)
        .order_by(JournalEntryLine.gl_account_number)
        .all()
    )

    accounts = []
    total_debits = Decimal("0")
    total_credits = Decimal("0")
    for r in rows:
        debits = Decimal(str(r.debits))
        credits = Decimal(str(r.credits))
        total_debits += debits
        total_credits += credits
        accounts.append({
            "account_number": r.number,
            "account_name": r.name,
            "debits": debits,
            "credits": credits,
            # Debit-positive. An account with more credits than debits reports a
            # negative balance rather than being flipped into a credit column —
            # the caller decides presentation; this reports arithmetic.
            "balance": debits - credits,
            "line_count": r.lines,
        })

    excluded = dict(
        db.query(JournalEntry.status, func.count(JournalEntryLine.id))
        .join(JournalEntryLine, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .filter(
            JournalEntryLine.tenant_id == tenant_id,
            JournalEntry.status.notin_(_LEDGER_STATUSES),
            JournalEntry.entry_date <= as_of,
        )
        .group_by(JournalEntry.status)
        .all()
    )

    result = {
        "as_of": str(as_of),
        "accounts": accounts,
        "total_debits": total_debits,
        "total_credits": total_credits,
        "difference": total_debits - total_credits,
        "balanced": total_debits == total_credits,
        "has_postings": bool(accounts),
        "account_count": len(accounts),
        "excluded_statuses": excluded,
    }
    _log_run(db, tenant_id, "trial_balance", {"as_of": str(as_of)}, user_id, len(accounts))
    return result
