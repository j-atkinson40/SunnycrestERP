"""Proactive action agents — pre-problem intelligence layer.

Fire-and-forget jobs that extend existing agent infrastructure with
proactive intelligence. All integrate with the behavioral analytics layer.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PART 1 — PO Intelligence Agent
# ---------------------------------------------------------------------------


def run_reorder_suggestion_job(db: Session, tenant_id: str) -> dict:
    """Detect vendors/products overdue for reorder based on historical PO patterns."""
    from app.models.purchase_order import PurchaseOrder
    from app.services.behavioral_analytics_service import generate_insight, record_event

    now = date.today()
    results = {"suggestions": 0, "alerts": 0}

    # Get all vendors with at least 3 completed POs
    vendor_po_counts = (
        db.query(PurchaseOrder.vendor_id, func.count(PurchaseOrder.id).label("po_count"))
        .filter(
            PurchaseOrder.tenant_id == tenant_id,
            PurchaseOrder.status.in_(["fully_received", "matched", "closed"]),
        )
        .group_by(PurchaseOrder.vendor_id)
        .having(func.count(PurchaseOrder.id) >= 3)
        .all()
    )

    for vendor_id, po_count in vendor_po_counts:
        # Get last 6 POs for this vendor to calculate average interval
        recent_pos = (
            db.query(PurchaseOrder)
            .filter(
                PurchaseOrder.tenant_id == tenant_id,
                PurchaseOrder.vendor_id == vendor_id,
                PurchaseOrder.status.in_(["fully_received", "matched", "closed"]),
            )
            .order_by(PurchaseOrder.order_date.desc())
            .limit(6)
            .all()
        )

        if len(recent_pos) < 3:
            continue

        # Calculate average days between orders
        intervals = []
        for i in range(len(recent_pos) - 1):
            delta = (recent_pos[i].order_date - recent_pos[i + 1].order_date).days
            if delta > 0:
                intervals.append(delta)

        if not intervals:
            continue

        avg_interval = sum(intervals) / len(intervals)
        last_order_date = recent_pos[0].order_date
        days_since = (now - last_order_date).days
        overdue_by = days_since - avg_interval

        if overdue_by <= 7:
            continue

        # Check if open PO already exists for this vendor
        open_po = (
            db.query(PurchaseOrder)
            .filter(
                PurchaseOrder.tenant_id == tenant_id,
                PurchaseOrder.vendor_id == vendor_id,
                PurchaseOrder.status.not_in(["cancelled", "closed", "fully_received", "matched"]),
            )
            .first()
        )
        if open_po:
            continue

        vendor_name = getattr(recent_pos[0], "vendor_name", None) or "vendor"

        insight = generate_insight(
            db=db,
            tenant_id=tenant_id,
            insight_type="reorder_suggestion",
            headline=f"Order from {vendor_name} — {int(overdue_by)} days past your usual cycle",
            detail=f"You typically order from {vendor_name} every {int(avg_interval)} days. Last order was {days_since} days ago with no new PO open.",
            scope="vendor",
            scope_entity_type="vendor",
            scope_entity_id=vendor_id,
            supporting_data={"avg_interval_days": avg_interval, "days_since_last": days_since, "overdue_by": overdue_by, "po_count": po_count},
            confidence=min(0.90, 0.70 + (po_count / 30)),
            action_type="configure",
            action_label="Create PO",
            action_url=f"/orders?tab=purchase-orders&action=new&vendorId={vendor_id}",
            generated_by_job="reorder_suggestion_job",
        )

        if insight:
            results["suggestions"] += 1

    return results


def run_receiving_discrepancy_monitor(db: Session, tenant_id: str) -> dict:
    """Flag unresolved PO receipt discrepancies after 7 days."""
    from app.services.behavioral_analytics_service import record_event

    results = {"flagged": 0}
    # Stub — would query purchase_order_receipts with discrepancy flags
    # and check for credit memos or replacement deliveries
    return results


# ---------------------------------------------------------------------------
# PART 2 — AR Proactive Agent
# ---------------------------------------------------------------------------


def run_balance_reduction_advisor(db: Session, tenant_id: str) -> dict:
    """Pre-collections proactive outreach suggestions."""
    from app.models.customer import Customer
    from app.services.behavioral_analytics_service import generate_insight, get_or_create_profile

    results = {"late_payment_flags": 0, "finance_charge_warnings": 0}

    # Get monthly statement customers with open balances
    customers = (
        db.query(Customer)
        .filter(
            Customer.company_id == tenant_id,
            Customer.is_active.is_(True),
        )
        .all()
    )

    statement_customers = [c for c in customers if getattr(c, "billing_profile", "cod") == "monthly_statement"]

    for customer in statement_customers:
        profile = get_or_create_profile(db, tenant_id, "customer", customer.id)

        # Scenario A: Payment late for this customer's pattern
        avg_days = float(profile.avg_days_to_pay or 0)
        consistency = float(profile.payment_consistency_score or 0)

        if avg_days > 0 and consistency >= 0.60:
            # Would check days since last statement and compare to customer's pattern
            # Simplified: generate insight if profile shows declining health
            if profile.relationship_health_trend == "declining":
                insight = generate_insight(
                    db=db,
                    tenant_id=tenant_id,
                    insight_type="payment_prediction",
                    headline=f"{customer.name}'s payment timing is declining",
                    detail=f"{customer.name} typically pays within {int(avg_days)} days but recent payments have been slower. A courtesy check-in may be worthwhile.",
                    scope="customer",
                    scope_entity_type="customer",
                    scope_entity_id=customer.id,
                    confidence=consistency,
                    action_type="contact",
                    action_label="Log a call or send a note",
                    generated_by_job="balance_reduction_advisor",
                )
                if insight:
                    results["late_payment_flags"] += 1

    return results


# ---------------------------------------------------------------------------
# PART 3 — AP Intelligence Agent
# ---------------------------------------------------------------------------


def check_duplicate_bill(db: Session, tenant_id: str, vendor_id: str, amount: float, bill_date: date) -> dict | None:
    """Pre-save duplicate invoice check. Returns warning if potential duplicate found."""
    from app.models.vendor_bill import VendorBill

    amount_low = amount * 0.95
    amount_high = amount * 1.05
    date_start = bill_date - timedelta(days=30)

    existing = (
        db.query(VendorBill)
        .filter(
            VendorBill.tenant_id == tenant_id,
            VendorBill.vendor_id == vendor_id,
            VendorBill.total_amount.between(Decimal(str(amount_low)), Decimal(str(amount_high))),
            VendorBill.bill_date >= date_start,
            VendorBill.status != "cancelled",
        )
        .first()
    )

    if existing:
        return {
            "warning": True,
            "warning_type": "possible_duplicate",
            "message": f"A bill from this vendor for a similar amount (${float(existing.total_amount):,.2f}) was recorded on {existing.bill_date}. Is this a duplicate?",
            "existing_bill_id": existing.id,
            "existing_bill_number": existing.bill_number,
        }

    return None


# ---------------------------------------------------------------------------
# PART 4 — Tax Compliance Agent
# ---------------------------------------------------------------------------


def run_tax_filing_prep(db: Session, tenant_id: str) -> dict:
    """Generate tax filing preparation package for the prior period."""
    from app.models.company import Company

    company = db.query(Company).filter(Company.id == tenant_id).first()
    settings = company.settings or {} if company else {}

    if not settings.get("tax_filing_reminder_enabled", True):
        return {"skipped": True, "reason": "reminders_disabled"}

    # Determine filing period
    today = date.today()
    frequency = settings.get("tax_filing_frequency", "monthly")

    if frequency == "monthly":
        # Prior month
        if today.month == 1:
            period_month, period_year = 12, today.year - 1
        else:
            period_month, period_year = today.month - 1, today.year
    elif frequency == "quarterly":
        # Prior quarter
        quarter = (today.month - 1) // 3
        if quarter == 0:
            period_month, period_year = 10, today.year - 1  # Q4 of prior year
        else:
            period_month = (quarter - 1) * 3 + 1
            period_year = today.year
    else:
        return {"skipped": True, "reason": "annual_frequency"}

    # Would call FinancialReportService.getTaxSummary() here
    # For now, return the prep structure
    return {
        "period_month": period_month,
        "period_year": period_year,
        "frequency": frequency,
        "status": "ready",
    }


# ---------------------------------------------------------------------------
# PART 5 — Accounting Intelligence Agent
# ---------------------------------------------------------------------------


def run_missing_entry_detector(db: Session, tenant_id: str) -> dict:
    """Detect missing recurring entries and historical pattern entries."""
    from app.models.journal_entry import JournalEntry, JournalEntryTemplate

    results = {"missing_recurring": 0, "historical_suggestions": 0}
    today = date.today()
    current_month = today.month
    current_year = today.year

    # CHECK 1: Expected recurring entries not posted
    templates = (
        db.query(JournalEntryTemplate)
        .filter(JournalEntryTemplate.tenant_id == tenant_id, JournalEntryTemplate.is_active.is_(True))
        .all()
    )

    for template in templates:
        # Check if entry exists for this template this month
        exists = (
            db.query(JournalEntry)
            .filter(
                JournalEntry.tenant_id == tenant_id,
                JournalEntry.recurring_template_id == template.id,
                JournalEntry.period_month == current_month,
                JournalEntry.period_year == current_year,
                JournalEntry.status != "reversed",
            )
            .first()
        )

        next_run = getattr(template, "next_run_date", None)
        if not exists and next_run and next_run <= today:
            results["missing_recurring"] += 1

    # CHECK 2: Historical pattern entries from same month last year
    prior_year_entries = (
        db.query(JournalEntry)
        .filter(
            JournalEntry.tenant_id == tenant_id,
            JournalEntry.period_month == current_month,
            JournalEntry.period_year == current_year - 1,
            JournalEntry.entry_type.in_(["adjusting", "manual"]),
            JournalEntry.recurring_template_id.is_(None),
            JournalEntry.status == "posted",
            JournalEntry.total_debits > 500,
        )
        .all()
    )

    for prior_entry in prior_year_entries:
        # Check for similar entry this year
        similar = (
            db.query(JournalEntry)
            .filter(
                JournalEntry.tenant_id == tenant_id,
                JournalEntry.period_month == current_month,
                JournalEntry.period_year == current_year,
                JournalEntry.status == "posted",
                JournalEntry.total_debits.between(
                    prior_entry.total_debits * Decimal("0.5"),
                    prior_entry.total_debits * Decimal("1.5"),
                ),
            )
            .first()
        )

        if not similar:
            results["historical_suggestions"] += 1

    return results


# ---------------------------------------------------------------------------
# PART 6 — Reconciliation Intelligence
# ---------------------------------------------------------------------------


def run_uncleared_check_monitor(db: Session, tenant_id: str) -> dict:
    """Flag checks outstanding for 45+ days."""
    from app.models.reconciliation import ReconciliationAdjustment

    results = {"flagged": 0}
    cutoff = date.today() - timedelta(days=45)

    stale_checks = (
        db.query(ReconciliationAdjustment)
        .filter(
            ReconciliationAdjustment.tenant_id == tenant_id,
            ReconciliationAdjustment.adjustment_type == "outstanding_check",
            func.date(ReconciliationAdjustment.created_at) < cutoff,
        )
        .all()
    )

    # Would cross-reference against subsequent reconciliations to check if cleared
    results["flagged"] = len(stale_checks)
    return results


# ---------------------------------------------------------------------------
# PART 8 — Year-End Preparation
# ---------------------------------------------------------------------------


def generate_year_end_checklist(db: Session, tenant_id: str) -> list[dict]:
    """Generate personalized year-end closing checklist."""
    items = []

    # Standard items — always included
    items.extend([
        {"category": "reconciliation", "text": "Reconcile all financial accounts through December 31", "priority": "high"},
        {"category": "entries", "text": "Post all December recurring journal entries", "priority": "high"},
        {"category": "entries", "text": "Review and post depreciation for December", "priority": "medium"},
        {"category": "ar", "text": "Review AR aging — write off uncollectible balances", "priority": "high"},
        {"category": "ap", "text": "Verify all December vendor bills are entered", "priority": "high"},
        {"category": "payroll", "text": "Reconcile payroll to W-2 totals", "priority": "high"},
        {"category": "compliance", "text": "Complete 1099 filing (deadline January 31)", "priority": "high"},
        {"category": "periods", "text": "Close December accounting period", "priority": "high"},
        {"category": "reports", "text": "Run year-end financial statements", "priority": "medium"},
    ])

    # Conditional items based on tenant data would be added here
    # e.g. check for prepaid balances, open transfers, finance charge runs

    return items


def run_incomplete_customer_profile_job(db: Session, tenant_id: str) -> dict:
    """Alert when quick-created customers haven't been completed after 7 days."""
    from app.services.customer_service import get_incomplete_customer_count

    count = get_incomplete_customer_count(db, tenant_id, older_than_days=7)
    if count == 0:
        return {"alerted": False}

    try:
        from app.services.behavioral_analytics_service import generate_insight
        generate_insight(
            db=db,
            company_id=tenant_id,
            insight_type="agent_alert",
            title=f"{count} customer{'s' if count != 1 else ''} created during order entry need their profiles completed.",
            description=(
                f"{count} customer{'s' if count != 1 else ''} {'were' if count != 1 else 'was'} "
                "created inline during order entry more than 7 days ago and still "
                f"{'have' if count != 1 else 'has'} "
                "incomplete profiles. Adding contact info, credit limits, and billing settings "
                "ensures accurate statements and credit checking."
            ),
            action_url="/customers?filter=incomplete",
            severity="info",
            metadata={"incomplete_count": count},
        )
    except Exception:
        pass

    return {"alerted": True, "count": count}


# ---------------------------------------------------------------------------
# Job Registry — maps job names to functions
# ---------------------------------------------------------------------------

PROACTIVE_JOBS = {
    "reorder_suggestion_job": run_reorder_suggestion_job,
    "receiving_discrepancy_monitor": run_receiving_discrepancy_monitor,
    "balance_reduction_advisor": run_balance_reduction_advisor,
    "tax_filing_prep": run_tax_filing_prep,
    "missing_entry_detector": run_missing_entry_detector,
    "uncleared_check_monitor": run_uncleared_check_monitor,
    "incomplete_customer_profile_job": run_incomplete_customer_profile_job,
}
