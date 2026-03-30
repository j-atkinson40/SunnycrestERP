"""End-of-day draft invoice generation for funeral service orders.

Runs at 6 PM daily.  For each manufacturing tenant with
invoice_generation_mode = 'end_of_day', finds all completed sales orders
for today that have no invoice yet and creates a draft invoice that requires
morning review before being posted to AR.
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

# Statuses that indicate a funeral service order was fulfilled today
COMPLETED_STATUSES = {"completed", "shipped", "delivered"}


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

    today = date.today()
    tomorrow = today + timedelta(days=1)

    # Find qualifying orders:
    #   - completed/shipped today (scheduled_date = today OR required_date::date = today)
    #   - order_type = 'funeral' OR order_type IS NULL (manufacturing vertical: all are funeral)
    #   - no invoice yet
    #   - not cancelled
    already_invoiced_order_ids = set(
        row[0]
        for row in db.query(Invoice.sales_order_id)
        .filter(
            Invoice.company_id == tenant_id,
            Invoice.sales_order_id.isnot(None),
        )
        .all()
    )

    orders_query = (
        db.query(SalesOrder)
        .filter(
            SalesOrder.company_id == tenant_id,
            SalesOrder.status.in_(COMPLETED_STATUSES),
            SalesOrder.status != "canceled",
        )
        .filter(
            # Scheduled_date populated → filter by it; otherwise fall back to required_date
            (SalesOrder.scheduled_date == today)
            | (
                SalesOrder.scheduled_date.is_(None)
                & (func.date(SalesOrder.required_date) == today)
            )
        )
    )

    # Funeral-type filter: include explicit 'funeral' orders OR untyped orders
    # (all orders in manufacturing vertical are implicitly funeral-related)
    orders_query = orders_query.filter(
        (SalesOrder.order_type == "funeral") | (SalesOrder.order_type.is_(None))
    )

    all_orders = orders_query.all()
    qualifying = [o for o in all_orders if o.id not in already_invoiced_order_ids]

    if not qualifying:
        logger.info(
            "[DRAFT_INVOICE_GENERATOR] Tenant %s: no qualifying orders for %s",
            tenant_id,
            today,
        )
        return

    from app.services import sales_service
    from app.services.agent_service import create_alert, log_activity

    created_invoices: list[Invoice] = []
    exception_count = 0

    for order in qualifying:
        try:
            invoice = sales_service.create_invoice_from_order(
                db, tenant_id, "system", order.id
            )

            # Mark as draft review invoice
            invoice.status = "draft"
            invoice.requires_review = True
            invoice.review_due_date = tomorrow
            invoice.auto_generated = True
            invoice.generation_reason = "end_of_day_batch"

            # Carry over driver exceptions if any
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

            # Log activity
            customer_name = order.customer.name if order.customer else order.customer_id
            log_activity(
                db,
                tenant_id,
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
                order.id,
                exc,
            )

    if not created_invoices:
        return

    db.commit()

    # Build customer list for alert message
    customer_names: list[str] = []
    for inv in created_invoices:
        try:
            order = next((o for o in qualifying if o.id == inv.sales_order_id), None)
            name = order.customer.name if (order and order.customer) else "Unknown"
            customer_names.append(name)
        except Exception:
            customer_names.append("Unknown")

    count = len(created_invoices)
    total_amount = sum(inv.total for inv in created_invoices)

    severity = "warning" if exception_count > 0 else "info"
    title = f"{count} draft invoice{'s' if count != 1 else ''} ready for morning review"
    lines = [
        f"End-of-day batch created {count} draft invoice{'s' if count != 1 else ''} "
        f"for {today} services totaling ${total_amount:,.2f}.",
        "",
        "Services:",
    ] + [f"  • {name}" for name in customer_names]

    if exception_count > 0:
        lines.append(
            f"\n⚠ {exception_count} invoice{'s have' if exception_count != 1 else ' has'} "
            "driver exceptions flagged — review before approving."
        )

    create_alert(
        db,
        tenant_id,
        alert_type="draft_invoices_ready",
        severity=severity,
        title=title,
        message="\n".join(lines),
        action_label="Review invoices",
        action_url="/ar/invoices/review",
    )

    logger.info(
        "[DRAFT_INVOICE_GENERATOR] Tenant %s: created %d draft invoices (%d with exceptions)",
        tenant_id,
        count,
        exception_count,
    )


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

        customer_name = None
        ship_to = None
        if inv.customer:
            customer_name = inv.customer.name
        elif order and order.customer:
            customer_name = order.customer.name

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
            "lines": [
                {
                    "id": ln.id,
                    "description": ln.description,
                    "quantity": ln.quantity,
                    "unit_price": ln.unit_price,
                    "line_total": ln.line_total,
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
    inv.status = "sent"
    inv.requires_review = False
    inv.reviewed_by = user_id
    inv.reviewed_at = now
    inv.approved_by = user_id
    inv.approved_at = now
    inv.modified_at = now

    # Post to AR — update customer balance
    if inv.customer:
        inv.customer.current_balance = (inv.customer.current_balance or Decimal("0")) + inv.total

    db.commit()
    db.refresh(inv)

    logger.info("Invoice %s approved by user %s", inv.number, user_id)
    return inv


# ---------------------------------------------------------------------------
# Bulk approve — all no-exception drafts
# ---------------------------------------------------------------------------


def approve_all_no_exceptions(
    db: Session, company_id: str, user_id: str
) -> dict:
    """Approve all draft review invoices that have no driver exceptions.

    Returns summary with count approved.
    """
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

    for inv in pending:
        inv.status = "sent"
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
        approved_count += 1
        total_amount += inv.total

    db.commit()

    logger.info(
        "Bulk approved %d invoices ($%.2f) for tenant %s by user %s",
        approved_count,
        total_amount,
        company_id,
        user_id,
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
