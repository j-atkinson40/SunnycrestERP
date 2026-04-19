"""End-of-day draft invoice generation for funeral service orders.

Runs at 6 PM daily.  For each manufacturing tenant with
invoice_generation_mode = 'end_of_day', finds all qualifying sales orders
for today and creates draft invoices that require morning review.

Two modes, controlled by require_driver_status_updates on DeliverySettings:

  False (default — auto-confirm):
    Query every funeral order scheduled today that is not cancelled/postponed
    and not yet invoiced.  Orders that are not already marked delivered are
    automatically confirmed by the system (delivery_auto_confirmed = True,
    delivered_at = now(), status → 'delivered').  A draft invoice is created
    for every such order.

  True (require driver):
    Only create draft invoices for orders that drivers have already marked
    delivered/completed/shipped.  Orders that are still unconfirmed are
    gathered into a warning alert so dispatch staff can follow up.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.sales_order import SalesOrder

logger = logging.getLogger(__name__)


def _try_send_invoice_email(db: Session, inv: Invoice) -> None:
    """Attempt to generate PDF and send invoice email. Logs errors but never raises."""
    try:
        from app.services.pdf_generation_service import generate_invoice_pdf
        from app.services.email_service import email_service
        from app.models.company import Company
        from datetime import datetime, timezone

        customer = inv.customer
        # Try CRM contacts first, fallback to legacy customer email
        to_emails = []
        if customer and customer.master_company_id:
            try:
                from app.services.crm.contact_service import get_invoice_recipients
                to_emails = get_invoice_recipients(db, customer.master_company_id, inv.company_id)
            except Exception:
                pass
        if not to_emails:
            fallback = (customer.billing_email or customer.email) if customer else None
            to_emails = [fallback] if fallback else []
        if not to_emails:
            logger.warning("Invoice %s: no email on customer — skipping email delivery", inv.number)
            return
        to_email = to_emails[0]  # primary recipient for email_service API

        company = db.query(Company).filter(Company.id == inv.company_id).first()
        company_name = company.name if company else "Your supplier"

        pdf_bytes = generate_invoice_pdf(db, inv.id, inv.company_id)
        if pdf_bytes is None:
            logger.warning("Invoice %s: PDF generation unavailable — email not sent", inv.number)
            return

        from app.utils.company_name_resolver import resolve_customer_name
        result = email_service.send_invoice_email(
            to_email=to_email,
            to_name=resolve_customer_name(customer),
            company_name=company_name,
            invoice_number=inv.number,
            invoice_date=inv.invoice_date.strftime("%B %d, %Y") if inv.invoice_date else "",
            due_date=inv.due_date.strftime("%B %d, %Y") if inv.due_date else "",
            total_amount=f"${inv.total:,.2f}",
            balance_due=f"${inv.balance_remaining:,.2f}",
            deceased_name=inv.deceased_name,
            pdf_attachment=pdf_bytes,
            reply_to=company.email if company else None,
            company_id=inv.company_id,
            db=db,
        )

        # Persist PDF to R2 (non-blocking, idempotent)
        if pdf_bytes:
            try:
                from app.services.document_r2_service import save_generated_document
                from app.models.document import Document as DocModel

                filename = f"Invoice-{inv.number}.pdf"
                r2_key = f"tenants/{inv.company_id}/invoices/{inv.id}/invoice/{filename}"
                existing = db.query(DocModel).filter(DocModel.r2_key == r2_key).first()

                if not existing:
                    save_generated_document(
                        db,
                        company_id=inv.company_id,
                        entity_type="invoice",
                        entity_id=str(inv.id),
                        document_type="invoice",
                        file_name=filename,
                        file_bytes=pdf_bytes,
                        mime_type="application/pdf",
                        generated_by=None,
                        metadata={
                            "invoice_id": str(inv.id),
                            "invoice_number": inv.number,
                            "customer_id": str(inv.customer_id),
                            "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
                            "due_date": inv.due_date.isoformat() if inv.due_date else None,
                            "total": str(inv.total),
                            "amount_paid": str(inv.amount_paid),
                            "balance_remaining": str(inv.balance_remaining),
                            "status": inv.status,
                            "deceased_name": inv.deceased_name,
                            "payment_terms": inv.payment_terms,
                        },
                    )
            except Exception as e:
                logger.warning(f"Invoice PDF persistence failed (non-blocking): {e}")

        if result.get("success"):
            now = datetime.now(timezone.utc)
            inv.sent_at = now
            inv.sent_to_email = to_email
            db.commit()
            logger.info("Invoice %s emailed to %s", inv.number, to_email)
            # CRM activity log
            try:
                from app.services.crm.activity_log_service import log_system_event
                log_system_event(
                    db, inv.company_id, None,
                    activity_type="invoice",
                    title=f"Invoice #{inv.number} sent — ${inv.total:,.2f}",
                    related_invoice_id=inv.id,
                    customer_id=inv.customer_id,
                )
                db.commit()
            except Exception:
                pass
        else:
            logger.error("Invoice %s email delivery failed", inv.number)
    except Exception as exc:
        logger.error("Invoice %s email send error: %s", getattr(inv, "number", "?"), exc)


# Statuses that count as driver-confirmed delivery
DRIVER_CONFIRMED_STATUSES = {"completed", "shipped", "delivered"}

# Statuses that mean the order is cancelled / won't be invoiced
SKIP_STATUSES = {"canceled", "cancelled", "postponed"}


# ---------------------------------------------------------------------------
# Batch job — called once per tenant from the scheduler
# ---------------------------------------------------------------------------


def generate_draft_invoices(db: Session, tenant_id: str) -> None:
    """Generate end-of-day draft invoices for a single tenant.

    Idempotent — orders that already have an invoice are skipped.
    """
    from app.services.delivery_settings_service import get_settings

    settings = get_settings(db, tenant_id)

    # Only run if tenant has enabled end-of-day batch mode
    mode = getattr(settings, "invoice_generation_mode", None)
    if mode != "end_of_day":
        return

    require_driver = getattr(settings, "require_driver_status_updates", False)

    today = date.today()
    tomorrow = today + timedelta(days=1)
    now = datetime.now(timezone.utc)

    # IDs of orders that already have an invoice
    already_invoiced_order_ids = set(
        row[0]
        for row in db.query(Invoice.sales_order_id)
        .filter(
            Invoice.company_id == tenant_id,
            Invoice.sales_order_id.isnot(None),
        )
        .all()
    )

    # Base query: funeral orders due today or overdue, not cancelled, not yet invoiced
    # Eligibility: scheduled_date <= today, or if no scheduled_date then required_date <= today
    # Orders with neither date set are never auto-delivered (require explicit scheduling)
    base_q = (
        db.query(SalesOrder)
        .filter(
            SalesOrder.company_id == tenant_id,
            SalesOrder.status.in_(["confirmed", "processing", "shipped", "delivered"]),
            ~SalesOrder.status.in_(SKIP_STATUSES),
        )
        .filter(
            (SalesOrder.scheduled_date <= today)
            | (
                SalesOrder.scheduled_date.is_(None)
                & (func.date(SalesOrder.required_date) <= today)
                & SalesOrder.required_date.isnot(None)
            )
        )
        .filter(
            (SalesOrder.order_type == "funeral") | (SalesOrder.order_type.is_(None))
        )
    )

    all_today = base_q.all()
    uninvoiced = [o for o in all_today if o.id not in already_invoiced_order_ids]

    if not uninvoiced:
        logger.info(
            "[DRAFT_INVOICE_GENERATOR] Tenant %s: no uninvoiced orders for %s",
            tenant_id,
            today,
        )
        return

    from app.services import sales_service
    from app.services.agent_service import create_alert, log_activity

    if require_driver:
        _generate_require_driver_mode(
            db, tenant_id, uninvoiced, today, tomorrow, now,
            sales_service, create_alert, log_activity,
        )
    else:
        _generate_auto_confirm_mode(
            db, tenant_id, uninvoiced, today, tomorrow, now,
            sales_service, create_alert, log_activity,
        )


# ---------------------------------------------------------------------------
# Mode: auto-confirm  (require_driver_status_updates = False)
# ---------------------------------------------------------------------------


def _generate_auto_confirm_mode(
    db, tenant_id, uninvoiced, today, tomorrow, now,
    sales_service, create_alert, log_activity,
):
    """Auto-mark unconfirmed orders as delivered, then generate draft invoices."""
    created_invoices: list[Invoice] = []
    exception_count = 0
    auto_confirmed_count = 0

    for order in uninvoiced:
        # Auto-confirm if driver hasn't marked it delivered
        if order.status not in DRIVER_CONFIRMED_STATUSES:
            order.status = "delivered"
            order.delivered_at = now
            order.delivery_auto_confirmed = True
            auto_confirmed_count += 1
            logger.debug(
                "[DRAFT_INVOICE_GENERATOR] Auto-confirmed order %s for tenant %s",
                order.number, tenant_id,
            )

        try:
            invoice = sales_service.create_invoice_from_order(
                db, tenant_id, "system", order.id
            )

            invoice.status = "draft"
            invoice.requires_review = True
            invoice.review_due_date = tomorrow
            invoice.auto_generated = True
            invoice.generation_reason = "end_of_day_batch"

            if order.has_driver_exception and order.driver_exceptions:
                invoice.has_exceptions = True
                exception_notes = "; ".join(
                    f"{e.get('reason', 'issue')} — {e.get('notes', '')}"
                    for e in order.driver_exceptions
                )
                invoice.review_notes = f"Driver exception(s): {exception_notes}"
                exception_count += 1

            db.add(invoice)
            created_invoices.append(invoice)

            from app.utils.company_name_resolver import resolve_customer_name as _rcn
            customer_name = _rcn(order.customer) if order.customer else order.customer_id
            log_activity(
                db, tenant_id,
                action_type="draft_invoice_created",
                description=(
                    f"Draft invoice auto-created for {customer_name} "
                    f"(order {order.number}, service {today})"
                ),
                record_type="invoice",
                record_id=invoice.id,
                autonomous=True,
            )

        except Exception as exc:
            logger.error(
                "[DRAFT_INVOICE_GENERATOR] Failed to create draft invoice for order %s: %s",
                order.id, exc,
            )

    if not created_invoices:
        return

    db.commit()

    customer_names = _collect_customer_names(db, created_invoices, uninvoiced)
    count = len(created_invoices)
    total_amount = sum(inv.total for inv in created_invoices)

    severity = "warning" if exception_count > 0 else "info"
    title = f"{count} draft invoice{'s' if count != 1 else ''} ready for morning review"

    lines = [
        f"End-of-day batch created {count} draft invoice{'s' if count != 1 else ''} "
        f"for {today} services totaling ${total_amount:,.2f}.",
    ]
    if auto_confirmed_count > 0:
        lines.append(
            f"{auto_confirmed_count} of {count} service{'s were' if auto_confirmed_count != 1 else ' was'} "
            "auto-confirmed (drivers did not update status in the app)."
        )
    lines += ["", "Services:"] + [f"  • {name}" for name in customer_names]

    if exception_count > 0:
        lines.append(
            f"\n⚠ {exception_count} invoice{'s have' if exception_count != 1 else ' has'} "
            "driver exceptions flagged — review before approving."
        )

    create_alert(
        db, tenant_id,
        alert_type="draft_invoices_ready",
        severity=severity,
        title=title,
        message="\n".join(lines),
        action_label="Review invoices",
        action_url="/ar/invoices/review",
    )

    logger.info(
        "[DRAFT_INVOICE_GENERATOR] Tenant %s: created %d draft invoices "
        "(%d auto-confirmed, %d with exceptions)",
        tenant_id, count, auto_confirmed_count, exception_count,
    )


# ---------------------------------------------------------------------------
# Mode: require driver  (require_driver_status_updates = True)
# ---------------------------------------------------------------------------


def _generate_require_driver_mode(
    db, tenant_id, uninvoiced, today, tomorrow, now,
    sales_service, create_alert, log_activity,
):
    """Only invoice driver-confirmed orders; alert on unconfirmed ones."""
    confirmed = [o for o in uninvoiced if o.status in DRIVER_CONFIRMED_STATUSES]
    unconfirmed = [o for o in uninvoiced if o.status not in DRIVER_CONFIRMED_STATUSES]

    created_invoices: list[Invoice] = []
    exception_count = 0

    for order in confirmed:
        try:
            invoice = sales_service.create_invoice_from_order(
                db, tenant_id, "system", order.id
            )

            invoice.status = "draft"
            invoice.requires_review = True
            invoice.review_due_date = tomorrow
            invoice.auto_generated = True
            invoice.generation_reason = "end_of_day_batch"

            if order.has_driver_exception and order.driver_exceptions:
                invoice.has_exceptions = True
                exception_notes = "; ".join(
                    f"{e.get('reason', 'issue')} — {e.get('notes', '')}"
                    for e in order.driver_exceptions
                )
                invoice.review_notes = f"Driver exception(s): {exception_notes}"
                exception_count += 1

            db.add(invoice)
            created_invoices.append(invoice)

            from app.utils.company_name_resolver import resolve_customer_name as _rcn
            customer_name = _rcn(order.customer) if order.customer else order.customer_id
            log_activity(
                db, tenant_id,
                action_type="draft_invoice_created",
                description=(
                    f"Draft invoice auto-created for {customer_name} "
                    f"(order {order.number}, service {today})"
                ),
                record_type="invoice",
                record_id=invoice.id,
                autonomous=True,
            )

        except Exception as exc:
            logger.error(
                "[DRAFT_INVOICE_GENERATOR] Failed to create draft invoice for order %s: %s",
                order.id, exc,
            )

    if created_invoices:
        db.commit()

        customer_names = _collect_customer_names(db, created_invoices, confirmed)
        count = len(created_invoices)
        total_amount = sum(inv.total for inv in created_invoices)

        severity = "warning" if exception_count > 0 else "info"
        title = f"{count} draft invoice{'s' if count != 1 else ''} ready for morning review"
        lines = [
            f"End-of-day batch created {count} draft invoice{'s' if count != 1 else ''} "
            f"for {today} services totaling ${total_amount:,.2f}.",
            "", "Services:",
        ] + [f"  • {name}" for name in customer_names]
        if exception_count > 0:
            lines.append(
                f"\n⚠ {exception_count} invoice{'s have' if exception_count != 1 else ' has'} "
                "driver exceptions flagged — review before approving."
            )

        create_alert(
            db, tenant_id,
            alert_type="draft_invoices_ready",
            severity=severity,
            title=title,
            message="\n".join(lines),
            action_label="Review invoices",
            action_url="/ar/invoices/review",
        )

    # Warn about unconfirmed orders
    if unconfirmed:
        _create_unconfirmed_alert(db, tenant_id, unconfirmed, today, create_alert)

    logger.info(
        "[DRAFT_INVOICE_GENERATOR] Tenant %s: created %d draft invoices, "
        "%d unconfirmed services flagged",
        tenant_id, len(created_invoices), len(unconfirmed),
    )


def _create_unconfirmed_alert(db, tenant_id, unconfirmed, today, create_alert):
    from app.utils.company_name_resolver import resolve_customer_name
    count = len(unconfirmed)
    details = []
    for order in unconfirmed:
        cust = resolve_customer_name(order.customer)
        dest = order.ship_to_name or order.ship_to_address or "—"
        details.append(f"  • {cust} — {dest}")

    create_alert(
        db, tenant_id,
        alert_type="unconfirmed_deliveries",
        severity="warning",
        title=f"{count} service{'s' if count != 1 else ''} today not marked delivered",
        message=(
            f"These funeral services were scheduled for {today} but drivers have "
            "not confirmed delivery. Verify completion before approving draft invoices "
            "tomorrow morning.\n\n"
            + "\n".join(details)
        ),
        action_label="Review orders",
        action_url=f"/orders?date={today}&status=unconfirmed",
    )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _collect_customer_names(db, invoices, orders) -> list[str]:
    from app.utils.company_name_resolver import resolve_customer_name
    names: list[str] = []
    for inv in invoices:
        order = next((o for o in orders if o.id == inv.sales_order_id), None)
        name = resolve_customer_name(order.customer) if (order and order.customer) else "Unknown"
        names.append(name)
    return names


# ---------------------------------------------------------------------------
# Review queue query
# ---------------------------------------------------------------------------


def get_review_queue(db: Session, company_id: str) -> list[dict]:
    """Return all draft invoices pending review, exceptions first."""
    invoices = (
        db.query(Invoice)
        .filter(
            Invoice.company_id == company_id,
            Invoice.status == "draft",
            Invoice.requires_review.is_(True),
        )
        .order_by(Invoice.has_exceptions.desc(), Invoice.review_due_date.asc())
        .all()
    )

    result = []
    for inv in invoices:
        order = None
        if inv.sales_order_id:
            order = db.query(SalesOrder).filter(SalesOrder.id == inv.sales_order_id).first()

        from app.utils.company_name_resolver import resolve_customer_name
        customer_name = None
        ship_to = None
        if inv.customer:
            customer_name = resolve_customer_name(inv.customer)
        elif order and order.customer:
            customer_name = resolve_customer_name(order.customer)

        if order:
            ship_to = order.ship_to_name or order.ship_to_address

        result.append({
            "id": inv.id,
            "number": inv.number,
            "customer_id": inv.customer_id,
            "customer_name": customer_name,
            "ship_to": ship_to,
            "invoice_date": inv.invoice_date,
            "due_date": inv.due_date,
            "subtotal": inv.subtotal,
            "tax_amount": inv.tax_amount,
            "total": inv.total,
            "has_exceptions": inv.has_exceptions,
            "review_notes": inv.review_notes,
            "review_due_date": inv.review_due_date,
            "auto_generated": inv.auto_generated,
            "generation_reason": inv.generation_reason,
            "sales_order_id": inv.sales_order_id,
            "order_number": order.number if order else None,
            "scheduled_date": str(order.scheduled_date) if order and order.scheduled_date else None,
            "driver_exceptions": order.driver_exceptions if order else None,
            # Delivery confirmation
            "delivery_auto_confirmed": order.delivery_auto_confirmed if order else False,
            "delivered_at": order.delivered_at.isoformat() if (order and order.delivered_at) else None,
            "delivered_by_driver_name": order.delivered_by_driver_name if order else None,
            "deceased_name": inv.deceased_name,
            "invoice_delivery_preference": getattr(inv.customer, "invoice_delivery_preference", "statement_only") if inv.customer else "statement_only",
            "lines": [
                {
                    "id": ln.id,
                    "description": ln.description,
                    "quantity": float(ln.quantity),
                    "unit_price": float(ln.unit_price),
                    "line_total": float(ln.line_total),
                    "product_id": ln.product_id,
                }
                for ln in (inv.lines or [])
            ],
        })
    return result


# ---------------------------------------------------------------------------
# Approve single invoice
# ---------------------------------------------------------------------------


def approve_invoice(
    db: Session, company_id: str, invoice_id: str, user_id: str
) -> Invoice:
    """Post a draft review invoice to AR (status → 'sent', updates customer balance)."""
    from fastapi import HTTPException, status as http_status

    inv = (
        db.query(Invoice)
        .filter(Invoice.id == invoice_id, Invoice.company_id == company_id)
        .first()
    )
    if not inv:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if inv.status != "draft":
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invoice is already '{inv.status}' — only drafts can be approved",
        )

    now = datetime.now(timezone.utc)
    inv.requires_review = False
    inv.reviewed_by = user_id
    inv.reviewed_at = now
    inv.approved_by = user_id
    inv.approved_at = now
    inv.modified_at = now

    # Post to AR — update customer balance
    if inv.customer:
        inv.customer.current_balance = (inv.customer.current_balance or Decimal("0")) + inv.total

    # Determine delivery preference and whether to email
    customer = inv.customer
    delivery_pref = getattr(customer, "invoice_delivery_preference", "statement_only") if customer else "statement_only"
    should_email = delivery_pref in ("invoice_immediately", "both")

    if should_email:
        inv.status = "sent"
    else:
        inv.status = "open"

    db.commit()
    db.refresh(inv)

    # Send email after commit so invoice is fully persisted
    if should_email:
        _try_send_invoice_email(db, inv)

    logger.info("Invoice %s approved by user %s (delivery=%s)", inv.number, user_id, delivery_pref)
    return inv


# ---------------------------------------------------------------------------
# Bulk approve — all no-exception drafts
# ---------------------------------------------------------------------------


def approve_all_no_exceptions(
    db: Session, company_id: str, user_id: str
) -> dict:
    """Approve all draft review invoices that have no driver exceptions."""
    pending = (
        db.query(Invoice)
        .filter(
            Invoice.company_id == company_id,
            Invoice.status == "draft",
            Invoice.requires_review.is_(True),
            Invoice.has_exceptions.is_(False),
        )
        .all()
    )

    now = datetime.now(timezone.utc)
    approved_count = 0
    total_amount = Decimal("0")

    to_email_after: list[Invoice] = []

    for inv in pending:
        inv.requires_review = False
        inv.reviewed_by = user_id
        inv.reviewed_at = now
        inv.approved_by = user_id
        inv.approved_at = now
        inv.modified_at = now
        if inv.customer:
            inv.customer.current_balance = (
                inv.customer.current_balance or Decimal("0")
            ) + inv.total
        delivery_pref = getattr(inv.customer, "invoice_delivery_preference", "statement_only") if inv.customer else "statement_only"
        if delivery_pref in ("invoice_immediately", "both"):
            inv.status = "sent"
            to_email_after.append(inv)
        else:
            inv.status = "open"
        approved_count += 1
        total_amount += inv.total

    db.commit()

    for inv in to_email_after:
        _try_send_invoice_email(db, inv)

    logger.info(
        "Bulk approved %d invoices ($%.2f) for tenant %s by user %s",
        approved_count, total_amount, company_id, user_id,
    )
    return {
        "approved_count": approved_count,
        "total_amount": str(total_amount),
    }


# ---------------------------------------------------------------------------
# Overdue review check — used by alert job
# ---------------------------------------------------------------------------


def get_overdue_review_invoices(db: Session, company_id: str) -> list[Invoice]:
    """Return draft review invoices whose review_due_date has passed."""
    today = date.today()
    return (
        db.query(Invoice)
        .filter(
            Invoice.company_id == company_id,
            Invoice.status == "draft",
            Invoice.requires_review.is_(True),
            Invoice.review_due_date < today,
        )
        .all()
    )
