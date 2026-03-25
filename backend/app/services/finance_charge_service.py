"""Finance charge service — calculation, review, and posting."""

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.customer import Customer
from app.models.finance_charge import FinanceChargeItem, FinanceChargeRun
from app.models.invoice import Invoice

logger = logging.getLogger(__name__)


def get_settings(db: Session, tenant_id: str) -> dict:
    """Get tenant finance charge configuration."""
    company = db.query(Company).filter(Company.id == tenant_id).first()
    if not company:
        return {"enabled": False}
    s = company.settings or {}
    return {
        "enabled": s.get("finance_charges_enabled", False),
        "rate_monthly": float(s.get("finance_charge_rate_monthly", 1.5)),
        "minimum_amount": float(s.get("finance_charge_minimum_amount", 2.0)),
        "minimum_balance": float(s.get("finance_charge_minimum_balance", 10.0)),
        "balance_basis": s.get("finance_charge_balance_basis", "past_due_only"),
        "compound": s.get("finance_charge_compound", False),
        "grace_days": int(s.get("finance_charge_grace_days", 0)),
        "calculation_day": int(s.get("finance_charge_calculation_day", 27)),
        "gl_account_id": s.get("finance_charge_gl_account_id"),
        "ar_account_id": s.get("finance_charge_ar_account_id"),
    }


def calculate_eligible_balance(
    db: Session, customer_id: str, tenant_id: str, calc_date: date, settings: dict,
) -> dict:
    """Determine the balance finance charges apply to."""
    grace_days = settings.get("grace_days", 0)
    basis = settings.get("balance_basis", "past_due_only")
    compound = settings.get("compound", False)

    # All open invoices excluding current-period finance charges
    query = db.query(Invoice).filter(
        Invoice.company_id == tenant_id,
        Invoice.customer_id == customer_id,
        Invoice.status.in_(["posted", "sent", "partial", "overdue"]),
    )

    invoices = query.all()

    # Build aging snapshot
    aging = {"current": 0, "days_1_30": 0, "days_31_60": 0, "days_61_90": 0, "days_over_90": 0}
    eligible_balance = Decimal("0")

    for inv in invoices:
        balance = Decimal(str(getattr(inv, "balance_due", 0) or getattr(inv, "total", 0) or 0))
        if balance <= 0:
            continue

        # Skip current-month invoices for full_outstanding basis
        if inv.invoice_date and inv.invoice_date.month == calc_date.month and inv.invoice_date.year == calc_date.year:
            if basis == "full_outstanding":
                continue

        effective_due = inv.due_date
        if effective_due and grace_days > 0:
            effective_due = effective_due + timedelta(days=grace_days)

        if not effective_due:
            effective_due = inv.invoice_date or calc_date

        days_past = (calc_date - effective_due).days if effective_due else 0

        # Aging bucket
        if days_past <= 0:
            aging["current"] += float(balance)
        elif days_past <= 30:
            aging["days_1_30"] += float(balance)
        elif days_past <= 60:
            aging["days_31_60"] += float(balance)
        elif days_past <= 90:
            aging["days_61_90"] += float(balance)
        else:
            aging["days_over_90"] += float(balance)

        # Determine if this invoice is eligible based on basis
        is_fc = getattr(inv, "is_finance_charge", False)
        if is_fc and not compound:
            continue  # Skip prior finance charges if not compounding

        include = False
        if basis == "full_outstanding":
            include = True
        elif basis == "past_due_only":
            include = days_past > 0
        elif basis == "aging_30_plus":
            include = days_past > 30
        elif basis == "aging_60_plus":
            include = days_past > 60
        elif basis == "aging_90_plus":
            include = days_past > 90

        if include:
            eligible_balance += balance

    # Prior finance charge balance (for compounding display)
    prior_fc = Decimal("0")
    if compound:
        fc_invoices = [i for i in invoices if getattr(i, "is_finance_charge", False)]
        for fci in fc_invoices:
            bal = Decimal(str(getattr(fci, "balance_due", 0) or 0))
            if bal > 0:
                prior_fc += bal

    aging["eligible_for_charge"] = float(eligible_balance)

    return {
        "eligible_balance": float(eligible_balance),
        "prior_finance_charge_balance": float(prior_fc),
        "aging_snapshot": aging,
    }


def calculate_charge_amount(
    eligible_balance: float, rate: float, minimum_amount: float, minimum_balance: float,
) -> dict:
    """Calculate the finance charge amount."""
    bal = Decimal(str(eligible_balance))
    min_bal = Decimal(str(minimum_balance))
    min_amt = Decimal(str(minimum_amount))

    if bal < min_bal:
        return {
            "calculated_amount": 0,
            "final_amount": 0,
            "below_minimum_balance": True,
            "minimum_applied": False,
        }

    calculated = (bal * Decimal(str(rate)) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if min_amt > 0 and calculated < min_amt:
        return {
            "calculated_amount": float(calculated),
            "final_amount": float(min_amt),
            "below_minimum_balance": False,
            "minimum_applied": True,
        }

    return {
        "calculated_amount": float(calculated),
        "final_amount": float(calculated),
        "below_minimum_balance": False,
        "minimum_applied": False,
    }


def run_calculation(db: Session, tenant_id: str, calc_date: date, triggered_by: str = "manual") -> dict | None:
    """Run monthly finance charge calculation."""
    settings = get_settings(db, tenant_id)
    if not settings["enabled"]:
        return None

    month = calc_date.month
    year = calc_date.year

    # Check for existing run
    existing = (
        db.query(FinanceChargeRun)
        .filter(
            FinanceChargeRun.tenant_id == tenant_id,
            FinanceChargeRun.charge_year == year,
            FinanceChargeRun.charge_month == month,
            FinanceChargeRun.status != "cancelled",
        )
        .first()
    )
    if existing:
        return {"run_id": existing.id, "already_exists": True}

    run_number = f"FC-{year}-{str(month).zfill(2)}"
    rate = Decimal(str(settings["rate_monthly"]))

    run = FinanceChargeRun(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        run_number=run_number,
        status="calculated",
        charge_month=month,
        charge_year=year,
        calculation_date=calc_date,
        rate_applied=rate,
        balance_basis=settings["balance_basis"],
        compound=settings["compound"],
        grace_days=settings["grace_days"],
        minimum_amount=Decimal(str(settings["minimum_amount"])),
        minimum_balance=Decimal(str(settings["minimum_balance"])),
        calculated_by=triggered_by,
    )
    db.add(run)
    db.flush()

    # Get eligible customers
    customers = (
        db.query(Customer)
        .filter(
            Customer.company_id == tenant_id,
            Customer.is_active.is_(True),
            Customer.finance_charge_eligible.is_(True),
        )
        .all()
    )
    # Filter to monthly_statement billing profile
    eligible = [c for c in customers if getattr(c, "billing_profile", "cod") == "monthly_statement"]

    total_evaluated = len(eligible)
    total_charged = 0
    total_below_min = 0
    total_calculated = Decimal("0")

    for customer in eligible:
        bal_data = calculate_eligible_balance(db, customer.id, tenant_id, calc_date, settings)

        if bal_data["eligible_balance"] <= 0:
            continue

        # Customer-specific rate
        custom_rate = getattr(customer, "finance_charge_custom_rate", None)
        cust_rate = Decimal(str(custom_rate)) if custom_rate else rate

        charge = calculate_charge_amount(
            bal_data["eligible_balance"],
            float(cust_rate),
            settings["minimum_amount"],
            settings["minimum_balance"],
        )

        if charge["below_minimum_balance"]:
            total_below_min += 1
            continue

        item = FinanceChargeItem(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            run_id=run.id,
            customer_id=customer.id,
            eligible_balance=Decimal(str(bal_data["eligible_balance"])),
            rate_applied=cust_rate,
            calculated_amount=Decimal(str(charge["calculated_amount"])),
            minimum_applied=charge["minimum_applied"],
            final_amount=Decimal(str(charge["final_amount"])),
            prior_finance_charge_balance=Decimal(str(bal_data["prior_finance_charge_balance"])),
            aging_snapshot=bal_data["aging_snapshot"],
            review_status="pending",
        )
        db.add(item)
        total_charged += 1
        total_calculated += Decimal(str(charge["final_amount"]))

    run.total_customers_evaluated = total_evaluated
    run.total_customers_charged = total_charged
    run.total_customers_below_minimum = total_below_min
    run.total_amount_calculated = total_calculated
    db.commit()

    return {"run_id": run.id, "already_exists": False, "customers_charged": total_charged, "total": float(total_calculated)}


def approve_item(db: Session, item_id: str, user_id: str) -> bool:
    item = db.query(FinanceChargeItem).filter(FinanceChargeItem.id == item_id).first()
    if not item or item.review_status != "pending":
        return False
    item.review_status = "approved"
    item.reviewed_by = user_id
    item.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    return True


def forgive_item(db: Session, item_id: str, user_id: str, note: str | None = None) -> bool:
    item = db.query(FinanceChargeItem).filter(FinanceChargeItem.id == item_id).first()
    if not item or item.review_status != "pending":
        return False
    item.review_status = "forgiven"
    item.reviewed_by = user_id
    item.reviewed_at = datetime.now(timezone.utc)
    item.forgiveness_note = note
    db.commit()
    return True


def approve_all_pending(db: Session, run_id: str, user_id: str) -> int:
    now = datetime.now(timezone.utc)
    count = (
        db.query(FinanceChargeItem)
        .filter(FinanceChargeItem.run_id == run_id, FinanceChargeItem.review_status == "pending")
        .update({"review_status": "approved", "reviewed_by": user_id, "reviewed_at": now})
    )
    db.commit()
    return count


def post_approved_charges(db: Session, run_id: str, tenant_id: str, user_id: str) -> dict:
    """Post all approved finance charges — creates invoices and JEs."""
    run = db.query(FinanceChargeRun).filter(FinanceChargeRun.id == run_id).first()
    if not run:
        return {"error": "Run not found"}

    # Check no pending items
    pending = (
        db.query(FinanceChargeItem)
        .filter(FinanceChargeItem.run_id == run_id, FinanceChargeItem.review_status == "pending")
        .count()
    )
    if pending > 0:
        return {"error": f"{pending} items still pending review"}

    approved_items = (
        db.query(FinanceChargeItem)
        .filter(FinanceChargeItem.run_id == run_id, FinanceChargeItem.review_status == "approved")
        .all()
    )

    settings = get_settings(db, tenant_id)
    posted_total = Decimal("0")
    forgiven_total = Decimal("0")

    for item in approved_items:
        # Create finance charge invoice
        invoice = Invoice(
            id=str(uuid.uuid4()),
            company_id=tenant_id,
            customer_id=item.customer_id,
            invoice_date=date.today(),
            status="posted",
            is_finance_charge=True,
            total=item.final_amount,
            notes=f"Finance charge — {run.charge_month}/{run.charge_year} ({float(item.rate_applied)}% on ${float(item.eligible_balance):,.2f})",
        )
        db.add(invoice)
        db.flush()

        item.posted = True
        item.invoice_id = invoice.id
        posted_total += item.final_amount

    # Sum forgiven
    forgiven_items = (
        db.query(FinanceChargeItem)
        .filter(FinanceChargeItem.run_id == run_id, FinanceChargeItem.review_status == "forgiven")
        .all()
    )
    for fi in forgiven_items:
        forgiven_total += fi.final_amount

    run.status = "posted"
    run.posted_by = user_id
    run.posted_at = datetime.now(timezone.utc)
    run.total_amount_posted = posted_total
    run.total_amount_forgiven = forgiven_total
    run.total_customers_forgiven = len(forgiven_items)
    db.commit()

    return {
        "posted": len(approved_items),
        "forgiven": len(forgiven_items),
        "total_posted": float(posted_total),
        "total_forgiven": float(forgiven_total),
    }


def get_runs(db: Session, tenant_id: str) -> list[dict]:
    runs = (
        db.query(FinanceChargeRun)
        .filter(FinanceChargeRun.tenant_id == tenant_id)
        .order_by(FinanceChargeRun.charge_year.desc(), FinanceChargeRun.charge_month.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "run_number": r.run_number,
            "status": r.status,
            "charge_month": r.charge_month,
            "charge_year": r.charge_year,
            "total_customers_charged": r.total_customers_charged,
            "total_customers_forgiven": r.total_customers_forgiven,
            "total_amount_calculated": float(r.total_amount_calculated),
            "total_amount_posted": float(r.total_amount_posted),
            "total_amount_forgiven": float(r.total_amount_forgiven),
            "posted_at": r.posted_at.isoformat() if r.posted_at else None,
        }
        for r in runs
    ]


def get_run_items(db: Session, run_id: str) -> list[dict]:
    items = (
        db.query(FinanceChargeItem)
        .filter(FinanceChargeItem.run_id == run_id)
        .order_by(FinanceChargeItem.final_amount.desc())
        .all()
    )
    customer_ids = [i.customer_id for i in items]
    from app.models.user import User
    customers = {c.id: c for c in db.query(Customer).filter(Customer.id.in_(customer_ids)).all()} if customer_ids else {}

    return [
        {
            "id": i.id,
            "customer_id": i.customer_id,
            "customer_name": customers[i.customer_id].name if i.customer_id in customers else "Unknown",
            "eligible_balance": float(i.eligible_balance),
            "rate_applied": float(i.rate_applied),
            "calculated_amount": float(i.calculated_amount),
            "minimum_applied": i.minimum_applied,
            "final_amount": float(i.final_amount),
            "prior_finance_charge_balance": float(i.prior_finance_charge_balance),
            "aging_snapshot": i.aging_snapshot,
            "review_status": i.review_status,
            "forgiveness_note": i.forgiveness_note,
            "posted": i.posted,
        }
        for i in items
    ]
