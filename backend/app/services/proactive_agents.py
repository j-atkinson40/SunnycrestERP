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
    """Daily: check vault replenishment needs for buyer/hybrid tenants."""
    from app.models import Company, VaultSupplier, PurchaseOrder, AgentAlert
    from app.services.vault_inventory_service import build_suggested_order

    company = db.query(Company).filter(Company.id == tenant_id).first()
    if not company:
        return {"suggestions": 0}

    mode = company.vault_fulfillment_mode or "produce"

    # Producers handle replenishment through production scheduling
    if mode == "produce":
        return {"suggestions": 0, "mode": "produce"}

    supplier = db.query(VaultSupplier).filter(
        VaultSupplier.company_id == tenant_id,
        VaultSupplier.is_primary == True,
        VaultSupplier.is_active == True,
    ).first()

    if not supplier:
        try:
            alert = AgentAlert(
                tenant_id=tenant_id,
                alert_type="vault_supplier_missing",
                severity="warning",
                title="No vault supplier configured",
                message=(
                    "Your vault fulfillment mode is set to purchase or hybrid, "
                    "but no vault supplier has been configured. "
                    "Set up your supplier in Settings → Vault Supplier."
                ),
            )
            db.add(alert)
            db.commit()
        except Exception as e:
            logger.warning("Could not create supplier missing alert: %s", e)
        return {"suggestions": 0, "error": "no_supplier"}

    suggestion = build_suggested_order(db, tenant_id)
    if not suggestion:
        return {"suggestions": 0}

    any_needs_reorder = any(item["reason"] in ("below_reorder_point", "urgent") for item in suggestion["suggested_items"])
    if not any_needs_reorder and not suggestion.get("urgent"):
        return {"suggestions": 0, "status": "stock_ok"}

    # Check if PO already exists for this delivery window
    existing_po = db.query(PurchaseOrder).filter(
        PurchaseOrder.company_id == tenant_id,
        PurchaseOrder.vendor_id == supplier.vendor_id,
        PurchaseOrder.status.in_(["draft", "sent"]),
    ).first()
    if existing_po:
        return {"suggestions": 0, "status": "po_exists"}

    # Build message
    import json
    items_text = ", ".join(f"{item['quantity']}x {item['product_name']}" for item in suggestion["suggested_items"])
    stock_lines = "\n".join(
        f"  {item['product_name']}: {item['current_stock']} on hand, reorder point {item['reorder_point']}"
        for item in suggestion["suggested_items"]
    )
    severity = "action_required" if suggestion["urgent"] else "warning"
    title = (
        f"Vault order needed TODAY — delivery {suggestion['next_delivery']}"
        if suggestion["urgent"]
        else f"Vault reorder needed by {suggestion['order_deadline']}"
    )
    message = (
        f"Suggested order: {items_text}\n"
        f"Total: {suggestion['total_units']} vaults\n\n"
        f"Next delivery: {suggestion['next_delivery']}\n"
        f"Order deadline: {suggestion['order_deadline']}\n\n"
        f"Stock levels:\n{stock_lines}"
    )
    suggested_json = json.dumps({"items": suggestion["suggested_items"], "vendor_id": supplier.vendor_id})

    try:
        alert = AgentAlert(
            tenant_id=tenant_id,
            alert_type="vault_reorder_needed",
            severity=severity,
            title=title,
            message=message,
            action_label="Create Purchase Order",
            action_url=f"/purchasing/po/new?vendor={supplier.vendor_id}&suggested={suggested_json}",
        )
        db.add(alert)
        db.commit()
    except Exception as e:
        logger.warning("Could not create reorder alert: %s", e)
        return {"suggestions": 0, "error": str(e)}

    return {"suggestions": 1, "urgent": suggestion["urgent"]}


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
# AR Balance Reconciliation
# ---------------------------------------------------------------------------


def run_ar_balance_reconciliation(db: Session, tenant_id: str) -> dict:
    """Reconcile stored customer AR balances against actual invoice totals.

    Detects and corrects balance drift caused by failed transactions,
    import edge cases, or manual adjustments that bypassed the normal flow.
    """
    from app.models import Customer, Invoice
    from app.services.behavioral_analytics_service import generate_insight

    customers = (
        db.query(Customer)
        .filter(
            Customer.company_id == tenant_id,
            Customer.is_active == True,
        )
        .all()
    )

    corrected = 0
    for customer in customers:
        calculated = (
            db.query(func.sum(Invoice.total - Invoice.amount_paid))
            .filter(
                Invoice.company_id == tenant_id,
                Invoice.customer_id == customer.id,
                Invoice.status.notin_(["paid", "void", "draft"]),
            )
            .scalar()
            or Decimal("0.00")
        )

        stored = customer.current_balance or Decimal("0.00")
        diff = abs(float(calculated) - float(stored))

        if diff > 0.01:
            logger.warning(
                "AR balance drift for customer %s (%s): stored=%.2f calculated=%.2f diff=%.2f",
                customer.id,
                customer.name,
                float(stored),
                float(calculated),
                diff,
            )
            customer.current_balance = calculated
            corrected += 1

            try:
                generate_insight(
                    db=db,
                    company_id=tenant_id,
                    insight_type="agent_alert",
                    title=f"AR balance corrected for {customer.name}",
                    description=(
                        f"Stored balance was ${float(stored):.2f} but open invoice total was "
                        f"${float(calculated):.2f} (difference: ${diff:.2f}). "
                        "Automatically corrected. If this recurs, investigate recent "
                        "payment imports or manual adjustments for this account."
                    ),
                    action_url=f"/customers/{customer.id}",
                    severity="warning",
                    metadata={
                        "customer_id": customer.id,
                        "stored_balance": float(stored),
                        "calculated_balance": float(calculated),
                        "difference": diff,
                    },
                )
            except Exception:
                pass

    if corrected > 0:
        db.commit()

    return {"customers_checked": len(customers), "balances_corrected": corrected}


# ---------------------------------------------------------------------------
# Payment pattern learning
# ---------------------------------------------------------------------------


def enrich_payment_patterns(db: Session, company_id: str) -> dict:
    """Calculate and store payment behavioral patterns per customer."""
    import statistics
    from datetime import date as _date
    from decimal import Decimal as _Decimal

    from app.models.behavioral_analytics import EntityBehavioralProfile
    from app.models.customer import Customer
    from app.models.customer_payment import CustomerPayment, CustomerPaymentApplication
    from app.models.invoice import Invoice

    customers = (
        db.query(Customer)
        .filter(
            Customer.company_id == company_id,
            Customer.is_active.is_(True),
        )
        .all()
    )

    updated = 0
    for customer in customers:
        payments = (
            db.query(CustomerPayment)
            .filter(
                CustomerPayment.company_id == company_id,
                CustomerPayment.customer_id == customer.id,
                CustomerPayment.deleted_at.is_(None),
            )
            .all()
        )

        if not payments:
            continue

        # Calculate avg days to pay
        days_to_pay = []
        for p in payments:
            for app in p.applications:
                inv = db.query(Invoice).filter(Invoice.id == app.invoice_id).first()
                if inv and inv.invoice_date and p.payment_date:
                    pay_date = p.payment_date if isinstance(p.payment_date, _date) else p.payment_date.date()
                    inv_date = inv.invoice_date if isinstance(inv.invoice_date, _date) else inv.invoice_date.date()
                    delta = (pay_date - inv_date).days
                    if 0 <= delta <= 120:
                        days_to_pay.append(delta)

        avg_days = statistics.mean(days_to_pay) if days_to_pay else None

        methods = [p.payment_method for p in payments if p.payment_method]
        typical_method = max(set(methods), key=methods.count) if methods else None

        payment_days = [p.payment_date.day for p in payments if p.payment_date]
        typical_day = max(set(payment_days), key=payment_days.count) if payment_days else None

        last_payment = max(payments, key=lambda p: p.payment_date) if payments else None

        try:
            profile = (
                db.query(EntityBehavioralProfile)
                .filter(
                    EntityBehavioralProfile.tenant_id == company_id,
                    EntityBehavioralProfile.entity_type == "customer",
                    EntityBehavioralProfile.entity_id == customer.id,
                )
                .first()
            )

            if not profile:
                profile = EntityBehavioralProfile(
                    tenant_id=company_id,
                    entity_type="customer",
                    entity_id=customer.id,
                )
                db.add(profile)

            if avg_days is not None:
                profile.avg_days_to_pay = _Decimal(str(round(avg_days, 1)))

            existing = profile.profile_data or {}
            existing.update(
                {
                    "typical_payment_method": typical_method,
                    "typical_payment_day": typical_day,
                    "last_payment_date": (
                        last_payment.payment_date.isoformat()
                        if last_payment and last_payment.payment_date
                        else None
                    ),
                    "last_payment_amount": (
                        float(last_payment.total_amount) if last_payment else None
                    ),
                }
            )
            profile.profile_data = existing
            updated += 1
        except Exception as e:
            logger.warning(
                "Could not update behavioral profile for customer %s: %s", customer.id, e
            )

    if updated > 0:
        db.commit()

    return {"customers_updated": updated}


# ---------------------------------------------------------------------------
# Discount expiry monitor
# ---------------------------------------------------------------------------


def run_discount_expiry_monitor(db: Session, company_id: str) -> dict:
    """Alert on early payment discounts expiring within 3 days."""
    from collections import defaultdict
    from datetime import date, timedelta

    from app.models.agent import AgentAlert
    from app.models.customer import Customer
    from app.models.invoice import Invoice

    today = date.today()
    cutoff = today + timedelta(days=3)

    expiring = (
        db.query(Invoice)
        .filter(
            Invoice.company_id == company_id,
            Invoice.discount_deadline.isnot(None),
            Invoice.discount_deadline >= today,
            Invoice.discount_deadline <= cutoff,
            Invoice.status.notin_(["paid", "void"]),
        )
        .all()
    )

    if not expiring:
        return {"alerts_created": 0}

    by_date = defaultdict(list)
    for inv in expiring:
        by_date[inv.discount_deadline].append(inv)

    alerts_created = 0
    for expiry_date, invoices in by_date.items():
        days_until = (expiry_date - today).days
        urgency = (
            "TODAY" if days_until == 0 else ("tomorrow" if days_until == 1 else f"in {days_until} days")
        )

        total_discount = sum(float(inv.total) * 0.05 for inv in invoices if inv.total)

        if len(invoices) == 1:
            inv = invoices[0]
            customer = db.query(Customer).filter(Customer.id == inv.customer_id).first()
            cust_name = customer.name if customer else "Unknown"
            discount_val = float(inv.total) * 0.05
            title = f"Discount expires {urgency}: {cust_name}"
            message = (
                f"Invoice #{inv.number} for ${float(inv.total):.2f} has an early payment "
                f"discount of ${discount_val:.2f} expiring {urgency}. "
                f"If {cust_name} pays ${float(inv.discounted_total or inv.total * 0.95):.2f} "
                f"by {expiry_date.strftime('%B %d')}, they save ${discount_val:.2f}."
            )
        else:
            customer_names = []
            for inv in invoices[:3]:
                c = db.query(Customer).filter(Customer.id == inv.customer_id).first()
                if c:
                    customer_names.append(c.name)
            title = f"{len(invoices)} discounts expire {urgency}"
            message = (
                f"{len(invoices)} early payment discounts expire {urgency} "
                f"totaling ${total_discount:.2f} in savings for customers. "
                f"Customers: {', '.join(customer_names)}{'...' if len(invoices) > 3 else ''}."
            )

        try:
            alert = AgentAlert(
                tenant_id=company_id,
                alert_type="discount_expiring",
                severity="warning" if days_until == 0 else "info",
                title=title,
                message=message,
            )
            db.add(alert)
            alerts_created += 1
        except Exception as e:
            logger.warning("Could not create discount expiry alert: %s", e)

    if alerts_created > 0:
        db.commit()
    return {"alerts_created": alerts_created, "invoices_expiring": len(expiring)}


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
    "ar_balance_reconciliation": run_ar_balance_reconciliation,
}
