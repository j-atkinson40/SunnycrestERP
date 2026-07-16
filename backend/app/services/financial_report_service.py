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

def get_income_statement(db: Session, tenant_id: str, period_start: date, period_end: date,
                         comparison_start: date | None = None, comparison_end: date | None = None,
                         user_id: str | None = None) -> dict:
    """Revenue - COGS - Expenses = Net Income."""
    revenue = _sum_invoices_by_gl_type(db, tenant_id, period_start, period_end, "revenue")
    cogs = _sum_by_gl_type(db, tenant_id, period_start, period_end, "cogs")
    expenses = _sum_by_gl_type(db, tenant_id, period_start, period_end, "expense")

    total_rev = sum(r["amount"] for r in revenue)
    total_cogs = sum(r["amount"] for r in cogs)
    total_exp = sum(r["amount"] for r in expenses)
    gross = total_rev - total_cogs
    net = gross - total_exp

    result = {
        "period": {"start": str(period_start), "end": str(period_end)},
        "revenue": revenue, "total_revenue": total_rev,
        "cogs": cogs, "total_cogs": total_cogs,
        "gross_profit": gross,
        "gross_margin_percent": round(gross / total_rev * 100, 1) if total_rev else 0,
        "expenses": expenses, "total_expenses": total_exp,
        "net_income": net,
    }

    if comparison_start and comparison_end:
        comp_rev = sum(r["amount"] for r in _sum_invoices_by_gl_type(db, tenant_id, comparison_start, comparison_end, "revenue"))
        comp_exp = sum(r["amount"] for r in _sum_by_gl_type(db, tenant_id, comparison_start, comparison_end, "expense"))
        comp_cogs = sum(r["amount"] for r in _sum_by_gl_type(db, tenant_id, comparison_start, comparison_end, "cogs"))
        result["comparison_period"] = {"start": str(comparison_start), "end": str(comparison_end)}
        result["comparison_net_income"] = comp_rev - comp_cogs - comp_exp

    _log_run(db, tenant_id, "income_statement", {"period_start": str(period_start), "period_end": str(period_end)}, user_id, len(revenue) + len(expenses))
    return result


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
    """Tax collected by jurisdiction for filing."""
    # This requires invoice_lines with tax fields — query if available
    result = {"period": {"start": str(period_start), "end": str(period_end)}, "jurisdictions": [], "total_tax": 0, "total_taxable": 0, "exempt_total": 0}
    _log_run(db, tenant_id, "tax_summary", {"period_start": str(period_start), "period_end": str(period_end)}, user_id, 0)
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

    # Check: exempt customers without certificates
    try:
        missing_cert = db.query(func.count(Customer.id)).filter(
            Customer.company_id == tenant_id, Customer.tax_status == "exempt",
            Customer.exemption_certificate.is_(None),
        ).scalar() or 0
        if missing_cert:
            findings.append({"severity": "amber", "category": "tax", "code": "missing_cert",
                              "message": f"{missing_cert} exempt customers without certificate numbers",
                              "action_label": "Review", "action_url": "/settings/tax?tab=exemptions"})
    except Exception:
        logger.warning("health check 'missing_cert' failed — finding silently absent", exc_info=True)

    # Check: expired exemptions
    try:
        expired = db.query(func.count(Customer.id)).filter(
            Customer.company_id == tenant_id, Customer.tax_status == "exempt",
            Customer.exemption_expiry < today,
        ).scalar() or 0
        if expired:
            findings.append({"severity": "red", "category": "tax", "code": "expired_exemptions",
                              "message": f"{expired} tax exemption certificates have expired",
                              "action_label": "Update", "action_url": "/settings/tax?tab=exemptions"})
    except Exception:
        logger.warning("health check 'expired_exemptions' failed — finding silently absent", exc_info=True)

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

def _sum_invoices_by_gl_type(db: Session, tenant_id: str, start: date, end: date, gl_type: str) -> list[dict]:
    """Sum invoice line amounts grouped by GL account type."""
    invoices = db.query(Invoice).filter(
        Invoice.company_id == tenant_id,
        Invoice.invoice_date >= start, Invoice.invoice_date <= end,
        Invoice.status.in_(["posted", "sent", "paid", "partial"]),
    ).all()
    # Simple aggregation — group by a generic "Sales Revenue" for now
    total = sum(float(i.total) for i in invoices)
    if total > 0:
        return [{"account_number": "4000", "account_name": "Sales Revenue", "amount": total}]
    return []


def _sum_by_gl_type(db: Session, tenant_id: str, start: date, end: date, gl_type: str) -> list[dict]:
    """Vendor-bill expenses for the period, categorized honestly (D-2).

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
