"""Statement service — run creation, generation, sending, balance calculation."""

import logging
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.statement import CustomerStatement, StatementRun, StatementTemplate
from app.services.ar_balance import is_receivable

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
        existing._already_existed = True
        return existing

    customers = get_eligible_customers(db, tenant_id)
    digital = sum(1 for c in customers if c["delivery_method"] == "digital")
    mail = sum(1 for c in customers if c["delivery_method"] == "mail")
    none_count = sum(1 for c in customers if c["delivery_method"] == "none")

    import calendar
    period_start = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    period_end = date(year, month, last_day)

    run = StatementRun(
        tenant_id=tenant_id,
        run_date=date.today(),
        period_start=period_start,
        period_end=period_end,
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
        # BSS-2: `stmt.statement_pdf_generated_at = ...` was here and RENDERED
        # NOTHING. This function computes balances; no PDF is produced anywhere
        # in it, and `statement_pdf_url` was left null — so the column asserted a
        # document that did not exist. The stamp now lives in
        # `statement_pdf_service.generate_statement_document`, beside the URL it
        # belongs with. `ready` still means "balances computed and sendable",
        # unchanged — two live endpoints consume it.
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

    from app.models.company import Company
    from app.services import statement_pdf_service
    from app.services.email_service import email_service
    company = db.query(Company).filter(Company.id == tenant_id).first()
    tenant_name = company.name if company else "Your supplier"

    # ── BSS-2 D-3 — DURABILITY, NOT RESILIENCE ────────────────────────────
    # This loop already continued past a failed item. What it did NOT do was
    # commit per item, and `send_statement_email` has `try:`/`finally:` with NO
    # `except` — the finally only closes a session. So a delivery exception
    # PROPAGATED, aborted the sweep, and the single trailing commit never ran:
    # every statement already marked `sent`, with `sent_at` and `email_sent_to`
    # written, rolled back. THE CUSTOMERS RECEIVED THEIR STATEMENTS AND THE
    # LEDGER SAID NOBODY DID. That is the defect here — not "the run stops" but
    # "the run forgets what it already did".
    #
    # Shape follows `plaid/sync.py`: per-item try, per-item state committed
    # INSIDE the loop, one terminal raise at the end. It is the only in-house
    # pattern whose ledger survives in the database rather than the logs —
    # S-1c's per-pair record is log-only, and STATE carries a worked example of
    # log evidence expiring before anyone read it.
    #
    # SOFT vs HARD, and the line between them: `success: False` is the provider
    # ANSWERING; an exception is the provider or transport NOT answering, which
    # is our problem.
    #
    #   SOFT — recorded per item, does NOT fail the run:
    #     • no email address        → `skipped` (a paper-statement customer)
    #     • delivery returned False → `failed`  (the provider answered: no)
    #   HARD — recorded per item, DOES fail the run after the sweep:
    #     • render raised (template / PDF / R2)
    #     • render returned no document (missing customer/company rows)
    #     • the send raised
    #
    # ⚠️ "NO EMAIL" MUST BE SOFT, and the numbers make it concrete: 6 of 11
    # statement-cohort customers have no address, concentrated at testco 3-of-3.
    # Classified hard, that tenant's statement run fails EVERY MONTH FOREVER on
    # a normal configuration — the arc's own pathology, created by the arc.
    #
    # `skipped` is not a new status. It is consumed by the run-completion check
    # below and was written by NOTHING — a soft slot built and never used.
    sent = 0
    failed = 0        # soft: recorded, not run-fatal
    skipped = 0       # soft: no address — paper statement
    hard_failures: list[str] = []

    def _record_hard(statement_id: str, exc: Exception) -> None:
        """Durably stamp one item's failure, Plaid-style.

        ROLLBACK FIRST, THEN RE-FETCH. The exception may have left the session
        dirty and `stmt` stale, so writing through the existing identity map
        could fail or silently write nothing.
        """
        db.rollback()
        fresh = db.get(CustomerStatement, statement_id)
        if fresh is not None:
            fresh.status = "failed"
            fresh.send_error = f"{type(exc).__name__}: {exc}"[:500]
            db.commit()
        hard_failures.append(f"{statement_id}: {type(exc).__name__}")
        logger.error(
            "Statement dispatch INTERNAL error on %s: %s",
            statement_id, exc, exc_info=True,
        )

    for stmt in stmts:
        cust = customers.get(stmt.customer_id)
        email = cust.billing_email or cust.email if cust else None
        if not email:
            # SOFT. Not an error: this customer gets a paper statement.
            stmt.status = "skipped"
            stmt.send_error = "No email address on file — paper statement"
            skipped += 1
            db.commit()
            continue

        # BSS-2 D-2 — RENDER THE STATEMENT AND ATTACH IT.
        # `statement_pdf_service.generate_statement_document` had ZERO callers.
        # It renders a real Document via the active `statement.professional`
        # template, and its own docstring said "the email-sending path in
        # email_service doesn't call it yet." Until now this function emailed a
        # body with no statement in it.
        #
        # Passing `document_id` is all that is required — `send_statement_email`
        # has accepted it all along and DeliveryService auto-fetches and
        # attaches the PDF from it.
        #
        # ⚠️ THE GUARD IS NOT OPTIONAL. `generate_statement_document` raises
        # DocumentRenderError on template / PDF / R2 failure, and this loop's
        # single `db.commit()` sits AFTER the loop — so an unguarded raise would
        # abort the sweep and roll back the per-item ledger for every customer
        # already processed. That is the failure shape D-3 addresses in full;
        # this narrow guard exists so D-2 does not ship the hazard meanwhile.
        #
        # A render failure SKIPS the send: a statement email carrying no
        # statement is worse than no email.
        # D-3 replaces D-2's narrow render-only guard: the try now spans the
        # whole item — render AND send — because the send was the unguarded
        # half, and its state is what was being lost.
        try:
            doc = statement_pdf_service.generate_statement_document(
                db, stmt.id, tenant_id
            )
            document_id = doc.id if doc is not None else None
            if document_id is None:
                # HARD. A missing customer/company row is a data-integrity
                # problem, not a routine outcome — and a statement email
                # carrying no statement is worse than no email, so never fall
                # through to a body-only send.
                raise RuntimeError(
                    "statement render returned no document "
                    "(missing customer or company row)"
                )

        # BSS-2: was `f"{stmt.period_month}/{stmt.period_year}" if hasattr(stmt,
        # "period_month") else "Monthly"`. The columns are
        # `statement_period_month` / `statement_period_year`, so the hasattr was
        # ALWAYS FALSE and every statement email would have rendered its month
        # as the literal string "Monthly". Both columns are non-nullable ints,
        # so no guard is needed. Never noticed because nothing has ever been
        # sent — the first customer to receive one would have found it.
            statement_month = (
                f"{stmt.statement_period_month}/{stmt.statement_period_year}"
            )
            result = email_service.send_statement_email(
                customer_email=email,
                customer_name=cust.name if cust else "Valued Customer",
                tenant_name=tenant_name,
                statement_month=statement_month,
                company_id=tenant_id,
                document_id=document_id,
                db=db,
            )
            if result["success"]:
                stmt.status = "sent"
                stmt.sent_at = datetime.now(timezone.utc)
                stmt.email_sent_to = email
                sent += 1
            else:
                # SOFT. The provider answered, and the answer was no — a bounce
                # or a rejected address. Per the Plaid precedent this records
                # per-item state and does NOT fail the run: a routine external
                # condition must not turn a monthly run red forever. The item
                # state is the signal.
                stmt.status = "failed"
                stmt.send_error = "Email delivery failed"
                failed += 1
            # THE LEDGER SURVIVES. Committed per item, so a later raise cannot
            # unwrite a statement that was genuinely delivered.
            db.commit()
        except Exception as exc:  # noqa: BLE001 — HARD; classified above
            _record_hard(stmt.id, exc)

    # Update run
    run = db.query(StatementRun).filter(StatementRun.id == run_id).first()
    if run:
        run.sent_at = datetime.now(timezone.utc)
        all_stmts = db.query(CustomerStatement).filter(CustomerStatement.run_id == run_id).all()
        all_done = all(s.status in ("sent", "skipped", "failed") or s.delivery_method == "mail" for s in all_stmts)
        if all_done:
            run.status = "complete"

    db.commit()

    # ⚠️ THE TERMINAL RAISE COMES AFTER THE RUN ROW IS COMMITTED, so the run
    # reflects reality before the failure surfaces. Only HARD failures raise —
    # skipped addresses and provider rejections are recorded outcomes of a
    # working system, and a run that goes red because one mailbox is full
    # trains people to ignore red.
    if hard_failures:
        raise RuntimeError(
            f"Statement dispatch hit {len(hard_failures)} internal error(s) "
            f"of {len(stmts)} statement(s); per-item state is committed. "
            + "; ".join(hard_failures[:5])
            + (" …" if len(hard_failures) > 5 else "")
        )

    return {"sent": sent, "failed": failed, "skipped": skipped}


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
        db.query(func.coalesce(func.sum(Invoice.balance_remaining), 0))
        .filter(
            Invoice.customer_id == customer_id,
            Invoice.invoice_date < period_start,
            is_receivable(),
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
