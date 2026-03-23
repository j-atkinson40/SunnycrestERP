"""Statement service — run creation, generation, sending, balance calculation."""

import logging
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.statement import CustomerStatement, StatementRun, StatementTemplate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


def get_templates(db: Session, tenant_id: str) -> list[dict]:
    templates = (
        db.query(StatementTemplate)
        .filter(
            (StatementTemplate.tenant_id == tenant_id)
            | (StatementTemplate.tenant_id.is_(None))
        )
        .order_by(StatementTemplate.template_name)
        .all()
    )
    return [
        {
            "id": t.id,
            "template_key": t.template_key,
            "template_name": t.template_name,
            "customer_type": t.customer_type,
            "is_default_for_type": t.is_default_for_type,
            "sections": t.sections,
            "logo_enabled": t.logo_enabled,
            "show_aging_summary": t.show_aging_summary,
            "show_account_number": t.show_account_number,
            "show_payment_instructions": t.show_payment_instructions,
        }
        for t in templates
    ]


# ---------------------------------------------------------------------------
# Eligible customers
# ---------------------------------------------------------------------------


def get_eligible_customers(db: Session, tenant_id: str) -> list[dict]:
    customers = (
        db.query(Customer)
        .filter(
            Customer.company_id == tenant_id,
            Customer.is_active.is_(True),
            Customer.receives_statements.is_(True),
        )
        .order_by(Customer.name)
        .all()
    )
    return [
        {
            "id": c.id,
            "name": c.name,
            "account_number": c.account_number,
            "billing_email": c.billing_email or c.email,
            "delivery_method": c.statement_delivery_method or "digital",
            "template_key": c.statement_template_key,
        }
        for c in customers
    ]


# ---------------------------------------------------------------------------
# Statement runs
# ---------------------------------------------------------------------------


def initiate_run(
    db: Session,
    tenant_id: str,
    user_id: str,
    month: int,
    year: int,
    custom_message: str | None = None,
) -> StatementRun:
    # Check for existing run
    existing = (
        db.query(StatementRun)
        .filter(
            StatementRun.tenant_id == tenant_id,
            StatementRun.statement_period_month == month,
            StatementRun.statement_period_year == year,
        )
        .first()
    )
    if existing:
        return existing

    customers = get_eligible_customers(db, tenant_id)
    digital = sum(1 for c in customers if c["delivery_method"] == "digital")
    mail = sum(1 for c in customers if c["delivery_method"] == "mail")
    none_count = sum(1 for c in customers if c["delivery_method"] == "none")

    run = StatementRun(
        tenant_id=tenant_id,
        statement_period_month=month,
        statement_period_year=year,
        status="generating",
        total_customers=len(customers),
        digital_count=digital,
        mail_count=mail,
        none_count=none_count,
        initiated_by=user_id,
        custom_message=custom_message,
    )
    db.add(run)
    db.flush()

    # Create customer statement records
    for cust in customers:
        if cust["delivery_method"] == "none":
            continue
        stmt = CustomerStatement(
            tenant_id=tenant_id,
            run_id=run.id,
            customer_id=cust["id"],
            statement_period_month=month,
            statement_period_year=year,
            delivery_method=cust["delivery_method"],
            template_key=cust["template_key"] or "general_standard",
            status="pending",
        )
        db.add(stmt)

    db.commit()
    db.refresh(run)
    return run


def get_run_status(db: Session, run_id: str, tenant_id: str) -> dict | None:
    run = (
        db.query(StatementRun)
        .filter(StatementRun.id == run_id, StatementRun.tenant_id == tenant_id)
        .first()
    )
    if not run:
        return None

    stmts = (
        db.query(CustomerStatement)
        .filter(CustomerStatement.run_id == run_id)
        .all()
    )
    cust_ids = [s.customer_id for s in stmts]
    customers = {
        c.id: c
        for c in db.query(Customer).filter(Customer.id.in_(cust_ids)).all()
    } if cust_ids else {}

    completed = sum(1 for s in stmts if s.status in ("ready", "sent"))
    failed = sum(1 for s in stmts if s.status == "failed")

    return {
        "id": run.id,
        "status": run.status,
        "month": run.statement_period_month,
        "year": run.statement_period_year,
        "total": run.total_customers,
        "digital_count": run.digital_count,
        "mail_count": run.mail_count,
        "completed": completed,
        "failed": failed,
        "custom_message": run.custom_message,
        "generated_at": run.generated_at.isoformat() if run.generated_at else None,
        "sent_at": run.sent_at.isoformat() if run.sent_at else None,
        "zip_file_url": run.zip_file_url,
        "customers": [
            {
                "id": s.id,
                "customer_id": s.customer_id,
                "customer_name": customers[s.customer_id].name if s.customer_id in customers else "Unknown",
                "delivery_method": s.delivery_method,
                "status": s.status,
                "balance_due": str(s.balance_due),
                "invoice_count": s.invoice_count,
                "email_sent_to": s.email_sent_to,
                "send_error": s.send_error,
                "statement_pdf_url": s.statement_pdf_url,
            }
            for s in stmts
        ],
    }


def generate_statement(
    db: Session, customer_statement_id: str, tenant_id: str,
) -> bool:
    """Generate a single customer statement — calculates balances, marks ready."""
    stmt = (
        db.query(CustomerStatement)
        .filter(
            CustomerStatement.id == customer_statement_id,
            CustomerStatement.tenant_id == tenant_id,
        )
        .first()
    )
    if not stmt:
        return False

    stmt.status = "generating"
    db.flush()

    try:
        balances = calculate_balances(
            db, stmt.customer_id, stmt.statement_period_month, stmt.statement_period_year,
        )
        invoices = get_period_invoices(
            db, stmt.customer_id, stmt.statement_period_month, stmt.statement_period_year,
        )

        stmt.previous_balance = balances["previous_balance"]
        stmt.new_charges = balances["new_charges"]
        stmt.payments_received = balances["payments_received"]
        stmt.balance_due = balances["balance_due"]
        stmt.invoice_ids = [i["id"] for i in invoices]
        stmt.invoice_count = len(invoices)
        stmt.statement_pdf_generated_at = datetime.now(timezone.utc)
        stmt.status = "ready"
        db.commit()
        return True
    except Exception as e:
        logger.error("Failed to generate statement %s: %s", customer_statement_id, e)
        stmt.status = "failed"
        stmt.send_error = str(e)[:500]
        db.commit()
        return False


def generate_all_for_run(db: Session, run_id: str, tenant_id: str) -> None:
    """Generate all pending statements for a run."""
    stmts = (
        db.query(CustomerStatement)
        .filter(
            CustomerStatement.run_id == run_id,
            CustomerStatement.status == "pending",
        )
        .all()
    )
    for stmt in stmts:
        generate_statement(db, stmt.id, tenant_id)

    run = db.query(StatementRun).filter(StatementRun.id == run_id).first()
    if run:
        all_stmts = db.query(CustomerStatement).filter(CustomerStatement.run_id == run_id).all()
        has_failures = any(s.status == "failed" for s in all_stmts)
        run.status = "partial" if has_failures else "ready"
        run.generated_at = datetime.now(timezone.utc)
        db.commit()


def mark_sent(
    db: Session, customer_statement_id: str, tenant_id: str, email: str,
) -> bool:
    stmt = (
        db.query(CustomerStatement)
        .filter(
            CustomerStatement.id == customer_statement_id,
            CustomerStatement.tenant_id == tenant_id,
        )
        .first()
    )
    if not stmt:
        return False
    stmt.status = "sent"
    stmt.sent_at = datetime.now(timezone.utc)
    stmt.email_sent_to = email
    db.commit()
    return True


def send_all_digital(db: Session, run_id: str, tenant_id: str) -> dict:
    """Mark all digital statements in a run as sent."""
    stmts = (
        db.query(CustomerStatement)
        .filter(
            CustomerStatement.run_id == run_id,
            CustomerStatement.delivery_method == "digital",
            CustomerStatement.status == "ready",
        )
        .all()
    )
    cust_ids = [s.customer_id for s in stmts]
    customers = {
        c.id: c for c in db.query(Customer).filter(Customer.id.in_(cust_ids)).all()
    } if cust_ids else {}

    sent = 0
    failed = 0
    for stmt in stmts:
        cust = customers.get(stmt.customer_id)
        email = cust.billing_email or cust.email if cust else None
        if not email:
            stmt.status = "failed"
            stmt.send_error = "No email address on file"
            failed += 1
            continue
        stmt.status = "sent"
        stmt.sent_at = datetime.now(timezone.utc)
        stmt.email_sent_to = email
        sent += 1

    # Update run
    run = db.query(StatementRun).filter(StatementRun.id == run_id).first()
    if run:
        run.sent_at = datetime.now(timezone.utc)
        all_stmts = db.query(CustomerStatement).filter(CustomerStatement.run_id == run_id).all()
        all_done = all(s.status in ("sent", "skipped", "failed") or s.delivery_method == "mail" for s in all_stmts)
        if all_done:
            run.status = "complete"

    db.commit()
    return {"sent": sent, "failed": failed}


# ---------------------------------------------------------------------------
# Balance calculation
# ---------------------------------------------------------------------------


def calculate_balances(
    db: Session, customer_id: str, month: int, year: int,
) -> dict:
    period_start = date(year, month, 1)
    if month == 12:
        period_end = date(year + 1, 1, 1)
    else:
        period_end = date(year, month + 1, 1)

    # Previous balance — invoices before this period with outstanding amounts
    prev_invoices = (
        db.query(func.coalesce(func.sum(Invoice.total - Invoice.amount_paid), 0))
        .filter(
            Invoice.customer_id == customer_id,
            Invoice.invoice_date < period_start,
            Invoice.status.in_(["sent", "partial", "overdue"]),
        )
        .scalar()
    )

    # New charges this period
    new_charges = (
        db.query(func.coalesce(func.sum(Invoice.total), 0))
        .filter(
            Invoice.customer_id == customer_id,
            Invoice.invoice_date >= period_start,
            Invoice.invoice_date < period_end,
        )
        .scalar()
    )

    # Payments this period
    payments = (
        db.query(func.coalesce(func.sum(Invoice.amount_paid), 0))
        .filter(
            Invoice.customer_id == customer_id,
            Invoice.modified_at >= period_start,
            Invoice.modified_at < period_end,
            Invoice.amount_paid > 0,
        )
        .scalar()
    )

    previous_balance = Decimal(str(prev_invoices))
    new_charges_dec = Decimal(str(new_charges))
    payments_dec = Decimal(str(payments))
    balance_due = previous_balance + new_charges_dec - payments_dec

    return {
        "previous_balance": previous_balance,
        "new_charges": new_charges_dec,
        "payments_received": payments_dec,
        "balance_due": balance_due,
    }


def get_period_invoices(
    db: Session, customer_id: str, month: int, year: int,
) -> list[dict]:
    period_start = date(year, month, 1)
    if month == 12:
        period_end = date(year + 1, 1, 1)
    else:
        period_end = date(year, month + 1, 1)

    invoices = (
        db.query(Invoice)
        .filter(
            Invoice.customer_id == customer_id,
            Invoice.invoice_date >= period_start,
            Invoice.invoice_date < period_end,
        )
        .order_by(Invoice.invoice_date)
        .all()
    )
    return [
        {
            "id": i.id,
            "invoice_number": i.invoice_number,
            "invoice_date": str(i.invoice_date) if i.invoice_date else None,
            "total": str(i.total),
            "description": i.description or "",
        }
        for i in invoices
    ]


# ---------------------------------------------------------------------------
# Run history
# ---------------------------------------------------------------------------


def get_run_history(db: Session, tenant_id: str, limit: int = 12) -> list[dict]:
    runs = (
        db.query(StatementRun)
        .filter(StatementRun.tenant_id == tenant_id)
        .order_by(StatementRun.statement_period_year.desc(), StatementRun.statement_period_month.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "month": r.statement_period_month,
            "year": r.statement_period_year,
            "status": r.status,
            "total_customers": r.total_customers,
            "digital_count": r.digital_count,
            "mail_count": r.mail_count,
            "sent_at": r.sent_at.isoformat() if r.sent_at else None,
            "generated_at": r.generated_at.isoformat() if r.generated_at else None,
        }
        for r in runs
    ]


def get_customer_statement_history(
    db: Session, customer_id: str, tenant_id: str, limit: int = 12,
) -> list[dict]:
    stmts = (
        db.query(CustomerStatement)
        .filter(
            CustomerStatement.customer_id == customer_id,
            CustomerStatement.tenant_id == tenant_id,
            CustomerStatement.status.in_(["ready", "sent"]),
        )
        .order_by(CustomerStatement.statement_period_year.desc(), CustomerStatement.statement_period_month.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": s.id,
            "month": s.statement_period_month,
            "year": s.statement_period_year,
            "balance_due": str(s.balance_due),
            "status": s.status,
            "sent_at": s.sent_at.isoformat() if s.sent_at else None,
            "statement_pdf_url": s.statement_pdf_url,
        }
        for s in stmts
    ]
