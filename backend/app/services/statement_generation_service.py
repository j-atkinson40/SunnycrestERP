"""Statement generation service — monthly statement runs with agent flagging."""

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.statement import CustomerStatement, StatementRun

logger = logging.getLogger(__name__)

PAYMENT_TERMS_DAYS = {
    "net_15": 15, "net_30": 30, "net_60": 60, "net_90": 90,
    "due_on_receipt": 0, "cod": 0,
}


def get_eligible_customers(db: Session, tenant_id: str, period_end: date) -> list[Customer]:
    """Get all customers with receives_monthly_statement = true and activity in period."""
    return (
        db.query(Customer)
        .filter(
            Customer.company_id == tenant_id,
            Customer.receives_monthly_statement == True,
            Customer.is_active == True,
        )
        .all()
    )


def calculate_statement_data(
    db: Session, tenant_id: str, customer_id: str,
    period_start: date, period_end: date,
) -> dict:
    """Calculate all statement figures for a customer."""
    # Opening balance — unpaid invoices before period start
    opening = db.query(func.coalesce(func.sum(Invoice.total - Invoice.amount_paid), 0)).filter(
        Invoice.company_id == tenant_id, Invoice.customer_id == customer_id,
        Invoice.invoice_date < period_start,
        Invoice.status.in_(["sent", "partial", "overdue"]),
    ).scalar() or Decimal(0)

    # Invoices in period
    invoices = db.query(Invoice).filter(
        Invoice.company_id == tenant_id, Invoice.customer_id == customer_id,
        Invoice.invoice_date >= period_start, Invoice.invoice_date <= period_end,
    ).all()
    invoices_total = sum(Decimal(str(i.total)) for i in invoices)

    # Payments in period
    try:
        from app.models.payment import Payment
        payments_total = db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(
            Payment.company_id == tenant_id, Payment.customer_id == customer_id,
            Payment.payment_date >= period_start, Payment.payment_date <= period_end,
        ).scalar() or Decimal(0)
    except Exception:
        payments_total = Decimal(0)

    closing = opening + invoices_total - payments_total

    return {
        "opening_balance": float(opening),
        "invoices_total": float(invoices_total),
        "payments_total": float(payments_total),
        "credits_total": 0,
        "closing_balance": float(closing),
        "invoice_count": len(invoices),
    }


def detect_flags(
    db: Session, tenant_id: str, customer: Customer,
    statement_data: dict, period_end: date,
) -> list[dict]:
    """Detect flag conditions on a statement."""
    flags = []
    closing = statement_data["closing_balance"]

    # High balance variance — compare to 3-month average
    prev_items = (
        db.query(CustomerStatement)
        .filter(
            CustomerStatement.tenant_id == tenant_id,
            CustomerStatement.customer_id == customer.id,
        )
        .order_by(CustomerStatement.created_at.desc())
        .limit(3)
        .all()
    )
    if prev_items:
        avg_balance = sum(float(i.balance_due) for i in prev_items) / len(prev_items)
        if avg_balance > 0 and closing > avg_balance * 1.5:
            pct = int((closing / avg_balance - 1) * 100)
            flags.append({
                "code": "high_balance_variance",
                "message": f"Balance is {pct}% above 3-month average of ${avg_balance:,.2f}.",
            })

    # Payment after cutoff
    try:
        from app.models.payment import Payment
        post_cutoff = db.query(Payment).filter(
            Payment.company_id == tenant_id, Payment.customer_id == customer.id,
            Payment.payment_date > period_end,
            Payment.payment_date <= date.today(),
        ).first()
        if post_cutoff:
            flags.append({
                "code": "payment_after_cutoff",
                "message": f"Payment of ${float(post_cutoff.amount):,.2f} received on {post_cutoff.payment_date} after cutoff.",
            })
    except Exception:
        pass

    # Open dispute
    disputed = db.query(Invoice).filter(
        Invoice.company_id == tenant_id, Invoice.customer_id == customer.id,
        Invoice.status == "disputed",
    ).first()
    if disputed:
        flags.append({
            "code": "open_dispute",
            "message": f"Invoice #{disputed.invoice_number or disputed.id[:8]} is in dispute.",
        })

    # Credit balance
    if closing < 0:
        flags.append({
            "code": "credit_balance",
            "message": f"Customer has a credit balance of ${abs(closing):,.2f}.",
        })

    # First statement (check if any previous statements exist beyond the current batch)
    prev_any = db.query(CustomerStatement).filter(
        CustomerStatement.tenant_id == tenant_id,
        CustomerStatement.customer_id == customer.id,
        CustomerStatement.status != "pending",
    ).first()
    if not prev_any:
        flags.append({
            "code": "first_statement",
            "message": "First statement for this customer. Verify contact and delivery details.",
        })

    # Large balance (near credit limit)
    if customer.credit_limit and customer.credit_limit > 0 and closing > 0:
        pct = closing / float(customer.credit_limit) * 100
        if pct >= 90:
            flags.append({
                "code": "large_balance",
                "message": f"Balance is at {pct:.0f}% of credit limit.",
            })

    return flags


def generate_statement_run(
    db: Session, tenant_id: str, user_id: str,
    period_start: date, period_end: date,
) -> StatementRun:
    """Generate a full statement run for all eligible customers."""
    customers = get_eligible_customers(db, tenant_id, period_end)

    run = StatementRun(
        tenant_id=tenant_id,
        statement_period_month=period_start.month,
        statement_period_year=period_start.year,
        status="draft",
        total_customers=len(customers),
        initiated_by=user_id,
    )
    db.add(run)
    db.flush()

    total_amount = Decimal(0)
    flagged_count = 0

    # Identify customers in consolidated_single_payer groups —
    # their data rolls up into the billing contact's statement.
    consolidated_groups: dict[str, list[str]] = {}  # billing_customer_id → [member customer_ids]
    skip_individual = set()  # customer IDs handled by consolidated statement

    for customer in customers:
        if customer.billing_group_customer_id and customer.billing_group_customer_id != customer.id:
            # This customer's AR is consolidated to another customer
            billing_cid = customer.billing_group_customer_id
            consolidated_groups.setdefault(billing_cid, []).append(customer.id)
            skip_individual.add(customer.id)

    for customer in customers:
        if customer.id in skip_individual:
            continue

        # Calculate data for this customer
        data = calculate_statement_data(db, tenant_id, customer.id, period_start, period_end)

        # If this customer is the billing contact for a consolidated group,
        # roll up member data into their statement
        member_ids = consolidated_groups.get(customer.id, [])
        location_breakdown = None
        if member_ids:
            location_breakdown = [{
                "customer_id": customer.id,
                "customer_name": customer.name,
                "opening_balance": data["opening_balance"],
                "new_charges": data["invoices_total"],
                "payments_received": data["payments_total"],
                "closing_balance": data["closing_balance"],
            }]
            for mid in member_ids:
                member = db.query(Customer).filter(Customer.id == mid).first()
                mdata = calculate_statement_data(db, tenant_id, mid, period_start, period_end)
                data["opening_balance"] += mdata["opening_balance"]
                data["invoices_total"] += mdata["invoices_total"]
                data["payments_total"] += mdata["payments_total"]
                data["closing_balance"] += mdata["closing_balance"]
                data["invoice_count"] += mdata["invoice_count"]
                if member:
                    location_breakdown.append({
                        "customer_id": mid,
                        "customer_name": member.name,
                        "opening_balance": mdata["opening_balance"],
                        "new_charges": mdata["invoices_total"],
                        "payments_received": mdata["payments_total"],
                        "closing_balance": mdata["closing_balance"],
                    })

        # Skip if no activity and zero balance
        if data["closing_balance"] == 0 and data["invoices_total"] == 0 and data["payments_total"] == 0:
            continue

        flags = detect_flags(db, tenant_id, customer, data, period_end)

        # Calculate due date from payment terms
        terms_days = PAYMENT_TERMS_DAYS.get(customer.payment_terms or "net_30", 30)
        due = period_end + timedelta(days=terms_days)

        item = CustomerStatement(
            tenant_id=tenant_id,
            run_id=run.id,
            customer_id=customer.id,
            statement_period_month=period_start.month,
            statement_period_year=period_start.year,
            previous_balance=data["opening_balance"],
            new_charges=data["invoices_total"],
            payments_received=data["payments_total"],
            balance_due=data["closing_balance"],
            invoice_count=data["invoice_count"],
            delivery_method=customer.preferred_delivery_method or "email",
            flagged=len(flags) > 0,
            flag_reasons=flags if flags else (location_breakdown if location_breakdown else []),
            status="pending",
        )
        db.add(item)

        total_amount += Decimal(str(data["closing_balance"]))
        if flags:
            flagged_count += 1

    run.total_amount = float(total_amount)
    run.flagged_count = flagged_count
    run.status = "in_review" if flagged_count > 0 else "draft"

    db.commit()
    db.refresh(run)
    logger.info(f"Generated statement run {run.id}: {run.total_customers} customers, {flagged_count} flagged")
    return run


def get_current_run(db: Session, tenant_id: str) -> StatementRun | None:
    """Get active or most recent statement run."""
    active = (
        db.query(StatementRun)
        .filter(
            StatementRun.tenant_id == tenant_id,
            StatementRun.status.in_(["draft", "in_review", "approved", "sending"]),
        )
        .order_by(StatementRun.created_at.desc())
        .first()
    )
    if active:
        return active
    return (
        db.query(StatementRun)
        .filter(StatementRun.tenant_id == tenant_id)
        .order_by(StatementRun.created_at.desc())
        .first()
    )


def approve_item(db: Session, item_id: str, tenant_id: str, user_id: str, note: str | None = None) -> bool:
    item = db.query(CustomerStatement).filter(
        CustomerStatement.id == item_id, CustomerStatement.tenant_id == tenant_id,
    ).first()
    if not item:
        return False
    item.review_status = "approved"
    item.reviewed_by = user_id
    item.reviewed_at = datetime.now(timezone.utc)
    item.review_note = note
    db.commit()
    return True


def skip_item(db: Session, item_id: str, tenant_id: str, user_id: str, note: str | None = None) -> bool:
    item = db.query(CustomerStatement).filter(
        CustomerStatement.id == item_id, CustomerStatement.tenant_id == tenant_id,
    ).first()
    if not item:
        return False
    item.review_status = "skipped"
    item.reviewed_by = user_id
    item.reviewed_at = datetime.now(timezone.utc)
    item.review_note = note
    db.commit()
    return True


def approve_all_unflagged(db: Session, run_id: str, tenant_id: str, user_id: str) -> int:
    now = datetime.now(timezone.utc)
    count = (
        db.query(CustomerStatement)
        .filter(
            CustomerStatement.run_id == run_id,
            CustomerStatement.tenant_id == tenant_id,
            CustomerStatement.flagged == False,
            CustomerStatement.review_status == "pending",
        )
        .update({
            "review_status": "approved",
            "reviewed_by": user_id,
            "reviewed_at": now,
        })
    )
    db.commit()
    return count
