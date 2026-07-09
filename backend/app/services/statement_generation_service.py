"""Statement generation service — monthly statement runs with agent flagging."""

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.customer_payment import CustomerPayment, CustomerPaymentApplication
from app.models.invoice import Invoice
from app.models.statement import CustomerStatement, StatementRun

logger = logging.getLogger(__name__)

PAYMENT_TERMS_DAYS = {
    "net_15": 15, "net_30": 30, "net_60": 60, "net_90": 90,
    "due_on_receipt": 0, "cod": 0,
}

# Invoice statuses that never appear in customer-facing statement math —
# applied to both the opening-balance reconstruction and in-period charges.
EXCLUDED_INVOICE_STATUSES = ("draft", "void", "write_off")

# StatementRun statuses that may be superseded by a re-generation for the
# same period. Anything past review (approved / sending / sent) is refused.
_SUPERSEDABLE_RUN_STATUSES = ("draft", "in_review", "failed")


def sum_customer_payments_in_period(
    db: Session, tenant_id: str, customer_id: str,
    period_start: date, period_end: date,
) -> Decimal:
    """Payments RECEIVED in the period — Σ CustomerPayment.total_amount by
    payment_date (end-inclusive at day granularity), soft-deletes excluded.

    Payment-date attribution is the customer-facing reading ("the check I
    sent this month") and the only representable one: applications carry no
    date of their own. This is the canonical CustomerPayment period read —
    D-3 (reconciliation matching) reuses this pattern.

    No fallback: if this raises, statement generation must fail loudly —
    a statement that can't include payments must not generate.
    """
    end_exclusive = period_end + timedelta(days=1)
    total = db.query(
        func.coalesce(func.sum(CustomerPayment.total_amount), 0)
    ).filter(
        CustomerPayment.company_id == tenant_id,
        CustomerPayment.customer_id == customer_id,
        CustomerPayment.deleted_at.is_(None),
        CustomerPayment.payment_date >= period_start,
        CustomerPayment.payment_date < end_exclusive,
    ).scalar()
    return Decimal(str(total or 0))


def _opening_balance_as_of(
    db: Session, tenant_id: str, customer_id: str, period_start: date,
) -> Decimal:
    """Outstanding balance as of period start, reconstructed from history:
    pre-period invoice totals minus applications from pre-period payments.

    Deliberately NOT the live `Invoice.total - amount_paid` residual — that
    is as-of-now, and an in-period payment applied to a pre-period invoice
    would be double-counted (opening already shrunk by it AND subtracted
    again in payments_total).
    """
    invoiced = db.query(
        func.coalesce(func.sum(Invoice.total), 0)
    ).filter(
        Invoice.company_id == tenant_id,
        Invoice.customer_id == customer_id,
        Invoice.invoice_date < period_start,
        Invoice.status.notin_(EXCLUDED_INVOICE_STATUSES),
    ).scalar()

    applied = db.query(
        func.coalesce(func.sum(CustomerPaymentApplication.amount_applied), 0)
    ).join(
        CustomerPayment,
        CustomerPaymentApplication.payment_id == CustomerPayment.id,
    ).join(
        Invoice,
        CustomerPaymentApplication.invoice_id == Invoice.id,
    ).filter(
        Invoice.company_id == tenant_id,
        Invoice.customer_id == customer_id,
        Invoice.invoice_date < period_start,
        Invoice.status.notin_(EXCLUDED_INVOICE_STATUSES),
        CustomerPayment.deleted_at.is_(None),
        CustomerPayment.payment_date < period_start,
    ).scalar()

    return Decimal(str(invoiced or 0)) - Decimal(str(applied or 0))


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
    """Calculate all statement figures for a customer.

    LOUD-FAILURE CONTRACT: no component of the money math falls back to a
    default. If any read raises, the exception propagates and the statement
    does not generate — a wrong money number is worse than no statement.
    (The pre-rework version swallowed a dead `app.models.payment` import
    into payments_total = 0 on every statement; see audit C-1.)
    """
    # Opening balance — reconstructed as of period start (see helper).
    opening = _opening_balance_as_of(db, tenant_id, customer_id, period_start)

    # Invoices in period. invoice_date is a timestamp; period_end is a date —
    # compare end-exclusive so intraday period-end invoices count.
    end_exclusive = period_end + timedelta(days=1)
    invoices = db.query(Invoice).filter(
        Invoice.company_id == tenant_id, Invoice.customer_id == customer_id,
        Invoice.invoice_date >= period_start,
        Invoice.invoice_date < end_exclusive,
        Invoice.status.notin_(EXCLUDED_INVOICE_STATUSES),
    ).all()
    invoices_total = sum((Decimal(str(i.total)) for i in invoices), Decimal(0))

    # Payments received in period (payment-date attribution — Phase 0 §2).
    payments_total = sum_customer_payments_in_period(
        db, tenant_id, customer_id, period_start, period_end
    )

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

    # Payment after cutoff. Strictly AFTER the period-end day (the old
    # `> period_end` datetime-cast mis-flagged an intraday period-end
    # payment as post-cutoff). No swallow — a failed read raises.
    cutoff_exclusive = period_end + timedelta(days=1)
    post_cutoff = db.query(CustomerPayment).filter(
        CustomerPayment.company_id == tenant_id,
        CustomerPayment.customer_id == customer.id,
        CustomerPayment.deleted_at.is_(None),
        CustomerPayment.payment_date >= cutoff_exclusive,
    ).order_by(CustomerPayment.payment_date).first()
    if post_cutoff:
        pc_date = post_cutoff.payment_date.date() if hasattr(post_cutoff.payment_date, "date") else post_cutoff.payment_date
        flags.append({
            "code": "payment_after_cutoff",
            "message": f"Payment of ${float(post_cutoff.total_amount):,.2f} received on {pc_date} after cutoff.",
        })

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


def _clear_presend_run_for_period(
    db: Session, tenant_id: str, period_start: date,
) -> None:
    """Delete an existing run (+ its items) for the same period if it never
    went out; refuse loudly if it did.

    uq_statement_run_period means the first run for a period owns it forever
    — without this, a wrong-numbered draft (e.g. any pre-D-1 statement with
    silently-zeroed payments) could never be regenerated, and re-generation
    would die on a raw unique violation.
    """
    prior = db.query(StatementRun).filter(
        StatementRun.tenant_id == tenant_id,
        StatementRun.statement_period_month == period_start.month,
        StatementRun.statement_period_year == period_start.year,
    ).first()
    if prior is None:
        return
    if prior.status in _SUPERSEDABLE_RUN_STATUSES and (prior.sent_count or 0) == 0:
        db.query(CustomerStatement).filter(
            CustomerStatement.run_id == prior.id
        ).delete(synchronize_session=False)
        db.delete(prior)
        db.flush()
        logger.info(
            "Superseded pre-send statement run %s (%s) for period %s/%s",
            prior.id, prior.status,
            period_start.month, period_start.year,
        )
        return
    raise ValueError(
        f"A statement run for {period_start.month}/{period_start.year} "
        f"already exists with status '{prior.status}' — refusing to "
        f"regenerate a run that is approved or already went out."
    )


def generate_statement_run(
    db: Session, tenant_id: str, user_id: str,
    period_start: date, period_end: date,
) -> StatementRun:
    """Generate a full statement run for all eligible customers.

    LOUD-FAILURE CONTRACT: if the statement math raises for any customer,
    the whole run rolls back (no partial statements), a status="failed"
    StatementRun row is recorded for operator visibility, and the exception
    re-raises to the caller. Never emits a statement with defaulted numbers.
    """
    customers = get_eligible_customers(db, tenant_id, period_end)

    _clear_presend_run_for_period(db, tenant_id, period_start)

    run = StatementRun(
        tenant_id=tenant_id,
        period_start=period_start,
        period_end=period_end,
        statement_period_month=period_start.month,
        statement_period_year=period_start.year,
        status="draft",
        total_customers=len(customers),
        initiated_by=user_id,
    )
    db.add(run)
    db.flush()

    try:
        return _generate_statements_for_run(
            db, run, tenant_id, customers, period_start, period_end
        )
    except Exception:
        # Roll back the partial run, then record the failure loudly in a
        # fresh transaction. Recording must never mask the original error.
        db.rollback()
        try:
            _clear_presend_run_for_period(db, tenant_id, period_start)
            db.add(StatementRun(
                tenant_id=tenant_id,
                period_start=period_start,
                period_end=period_end,
                statement_period_month=period_start.month,
                statement_period_year=period_start.year,
                status="failed",
                total_customers=len(customers),
                initiated_by=user_id,
            ))
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Could not record failed statement run")
        raise


def _generate_statements_for_run(
    db: Session, run: StatementRun, tenant_id: str,
    customers: list[Customer], period_start: date, period_end: date,
) -> StatementRun:
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
