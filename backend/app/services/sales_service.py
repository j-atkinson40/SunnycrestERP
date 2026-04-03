"""Service layer for Sales / Accounts Receivable — Quotes, Sales Orders,
Invoices, Customer Payments, AR Aging, and sales statistics."""

import csv
import io
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException, status
from sqlalchemy import and_, func
from sqlalchemy.orm import Session, joinedload

from app.models.customer import Customer
from app.models.customer_payment import CustomerPayment, CustomerPaymentApplication
from app.models.invoice import Invoice, InvoiceLine
from app.models.quote import Quote, QuoteLine
from app.models.sales_order import SalesOrder, SalesOrderLine
from app.schemas.sales import (
    ARAgingBucket,
    ARAgingCustomer,
    ARAgingReport,
    SalesStats,
)
from app.services import audit_service
from app.services.sync_log_service import complete_sync_log, create_sync_log

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _next_number(db: Session, company_id: str, model_class, prefix: str) -> str:
    """Generate the next auto-number for a given prefix (e.g. QTE, SO, INV).

    Format: ``{PREFIX}-{YYYY}-{####}``
    """
    year = datetime.now(timezone.utc).year
    full_prefix = f"{prefix}-{year}-"
    last = (
        db.query(model_class.number)
        .filter(
            model_class.company_id == company_id,
            model_class.number.like(f"{full_prefix}%"),
        )
        .order_by(model_class.number.desc())
        .first()
    )
    if last and last[0]:
        try:
            seq = int(last[0].replace(full_prefix, "")) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1
    return f"{full_prefix}{seq:04d}"


def _parse_payment_terms_days(terms: str | None) -> int:
    """Extract number of days from payment terms string.

    ``"Net 30"`` -> 30, ``"Net 15"`` -> 15, ``"COD"`` -> 0, default -> 30.
    """
    if not terms:
        return 30
    upper = terms.strip().upper()
    if upper == "COD":
        return 0
    match = re.search(r"(\d+)", terms)
    return int(match.group(1)) if match else 30


def _compute_line_total(quantity: Decimal, unit_price: Decimal) -> Decimal:
    """Round line total to two decimal places."""
    return (quantity * unit_price).quantize(Decimal("0.01"))


def _compute_totals(
    lines_data: list, tax_rate: Decimal
) -> tuple[Decimal, Decimal, Decimal]:
    """Return (subtotal, tax_amount, total) computed from line data."""
    subtotal = Decimal("0.00")
    for line in lines_data:
        subtotal += _compute_line_total(line.quantity, line.unit_price)
    tax_amount = (subtotal * tax_rate).quantize(Decimal("0.01"))
    total = subtotal + tax_amount
    return subtotal, tax_amount, total


def _get_customer_or_404(db: Session, company_id: str, customer_id: str) -> Customer:
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.company_id == company_id)
        .first()
    )
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found"
        )
    return customer


# ---------------------------------------------------------------------------
# Quotes
# ---------------------------------------------------------------------------


def get_quotes(
    db: Session,
    company_id: str,
    page: int = 1,
    per_page: int = 20,
    status_filter: str | None = None,
    customer_id: str | None = None,
) -> dict:
    query = db.query(Quote).filter(Quote.company_id == company_id)
    if status_filter:
        query = query.filter(Quote.status == status_filter)
    if customer_id:
        query = query.filter(Quote.customer_id == customer_id)

    total = query.count()
    items = (
        query.options(joinedload(Quote.customer))
        .order_by(Quote.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {"items": items, "total": total, "page": page, "per_page": per_page}


def get_quote(db: Session, company_id: str, quote_id: str) -> Quote:
    quote = (
        db.query(Quote)
        .options(
            joinedload(Quote.customer),
            joinedload(Quote.lines),
            joinedload(Quote.creator),
        )
        .filter(Quote.id == quote_id, Quote.company_id == company_id)
        .first()
    )
    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found"
        )
    return quote


def create_quote(db: Session, company_id: str, user_id: str, data) -> Quote:
    _get_customer_or_404(db, company_id, data.customer_id)

    subtotal, tax_amount, total = _compute_totals(data.lines, data.tax_rate)
    number = _next_number(db, company_id, Quote, "QTE")

    quote = Quote(
        id=str(uuid.uuid4()),
        company_id=company_id,
        number=number,
        customer_id=data.customer_id,
        status="draft",
        quote_date=data.quote_date,
        expiry_date=data.expiry_date,
        payment_terms=data.payment_terms,
        tax_rate=data.tax_rate,
        subtotal=subtotal,
        tax_amount=tax_amount,
        total=total,
        notes=data.notes,
        created_by=user_id,
    )
    db.add(quote)
    db.flush()

    for idx, ld in enumerate(data.lines):
        line = QuoteLine(
            id=str(uuid.uuid4()),
            quote_id=quote.id,
            product_id=ld.product_id,
            description=ld.description,
            quantity=ld.quantity,
            unit_price=ld.unit_price,
            line_total=_compute_line_total(ld.quantity, ld.unit_price),
            sort_order=ld.sort_order if ld.sort_order else idx,
        )
        db.add(line)

    db.flush()

    audit_service.log_action(
        db,
        company_id,
        "created",
        "quote",
        quote.id,
        user_id=user_id,
        changes={"number": quote.number, "total": str(total)},
    )
    db.commit()
    db.refresh(quote)
    return quote


def update_quote(
    db: Session, company_id: str, user_id: str, quote_id: str, data
) -> Quote:
    quote = get_quote(db, company_id, quote_id)

    if quote.status in ("converted",):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify a converted quote",
        )

    for field in ("status", "expiry_date", "payment_terms", "notes"):
        val = getattr(data, field, None)
        if val is not None:
            setattr(quote, field, val)

    quote.modified_by = user_id
    quote.modified_at = datetime.now(timezone.utc)

    audit_service.log_action(
        db,
        company_id,
        "updated",
        "quote",
        quote.id,
        user_id=user_id,
    )
    db.commit()
    db.refresh(quote)
    return quote


def convert_quote_to_order(
    db: Session, company_id: str, user_id: str, quote_id: str
) -> SalesOrder:
    quote = get_quote(db, company_id, quote_id)

    if quote.status == "converted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quote has already been converted",
        )
    if quote.status not in ("draft", "sent", "accepted"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot convert quote in '{quote.status}' status",
        )

    order_number = _next_number(db, company_id, SalesOrder, "SO")
    now = datetime.now(timezone.utc)

    order = SalesOrder(
        id=str(uuid.uuid4()),
        company_id=company_id,
        number=order_number,
        customer_id=quote.customer_id,
        quote_id=quote.id,
        status="draft",
        order_date=now,
        payment_terms=quote.payment_terms,
        subtotal=quote.subtotal,
        tax_rate=quote.tax_rate,
        tax_amount=quote.tax_amount,
        total=quote.total,
        notes=quote.notes,
        created_by=user_id,
    )
    db.add(order)
    db.flush()

    for ql in quote.lines:
        sol = SalesOrderLine(
            id=str(uuid.uuid4()),
            sales_order_id=order.id,
            product_id=ql.product_id,
            description=ql.description,
            quantity=ql.quantity,
            unit_price=ql.unit_price,
            line_total=ql.line_total,
            sort_order=ql.sort_order,
        )
        db.add(sol)

    quote.status = "converted"
    quote.converted_to_order_id = order.id
    quote.modified_by = user_id
    quote.modified_at = now

    audit_service.log_action(
        db,
        company_id,
        "converted",
        "quote",
        quote.id,
        user_id=user_id,
        changes={"sales_order_id": order.id, "sales_order_number": order.number},
    )
    db.commit()
    db.refresh(order)
    return order


# ---------------------------------------------------------------------------
# Sales Orders
# ---------------------------------------------------------------------------


def get_sales_orders(
    db: Session,
    company_id: str,
    page: int = 1,
    per_page: int = 20,
    status_filter: str | None = None,
    customer_id: str | None = None,
) -> dict:
    query = db.query(SalesOrder).filter(SalesOrder.company_id == company_id)
    if status_filter:
        query = query.filter(SalesOrder.status == status_filter)
    if customer_id:
        query = query.filter(SalesOrder.customer_id == customer_id)

    total = query.count()
    items = (
        query.options(joinedload(SalesOrder.customer))
        .order_by(SalesOrder.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {"items": items, "total": total, "page": page, "per_page": per_page}


def get_sales_order(db: Session, company_id: str, order_id: str) -> SalesOrder:
    order = (
        db.query(SalesOrder)
        .options(
            joinedload(SalesOrder.customer),
            joinedload(SalesOrder.lines),
            joinedload(SalesOrder.creator),
        )
        .filter(SalesOrder.id == order_id, SalesOrder.company_id == company_id)
        .first()
    )
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sales order not found"
        )
    return order


def create_sales_order(
    db: Session, company_id: str, user_id: str, data
) -> SalesOrder:
    _get_customer_or_404(db, company_id, data.customer_id)

    subtotal, tax_amount, total = _compute_totals(data.lines, data.tax_rate)
    number = _next_number(db, company_id, SalesOrder, "SO")

    order = SalesOrder(
        id=str(uuid.uuid4()),
        company_id=company_id,
        number=number,
        customer_id=data.customer_id,
        quote_id=data.quote_id,
        status="draft",
        order_date=data.order_date,
        required_date=data.required_date,
        payment_terms=data.payment_terms,
        tax_rate=data.tax_rate,
        subtotal=subtotal,
        tax_amount=tax_amount,
        total=total,
        ship_to_name=data.ship_to_name,
        ship_to_address=data.ship_to_address,
        notes=data.notes,
        created_by=user_id,
    )
    db.add(order)
    db.flush()

    for idx, ld in enumerate(data.lines):
        line = SalesOrderLine(
            id=str(uuid.uuid4()),
            sales_order_id=order.id,
            product_id=ld.product_id,
            description=ld.description,
            quantity=ld.quantity,
            unit_price=ld.unit_price,
            line_total=_compute_line_total(ld.quantity, ld.unit_price),
            sort_order=ld.sort_order if ld.sort_order else idx,
        )
        db.add(line)

    db.flush()

    # Apply conditional pricing after all lines are created
    try:
        from app.services.order_pricing_service import recalculate_order_line_prices
        recalculate_order_line_prices(order.id, db)
    except Exception as _exc:
        logger.warning("Conditional pricing recalc failed for order %s: %s", order.id, _exc)

    # Apply funeral home preferences (placer auto-add + confirmation method)
    try:
        from app.services.funeral_home_preference_service import (
            apply_placer_to_order_lines,
            set_order_confirmation_method,
        )
        db.refresh(order)
        apply_placer_to_order_lines(db, company_id, data.customer_id, order, SalesOrderLine)
        set_order_confirmation_method(db, company_id, data.customer_id, order)
    except Exception as _exc:
        logger.warning("Funeral home preferences failed for order %s: %s", order.id, _exc)

    # Credit hold check — soft warning, does not block order
    _check_credit_on_order(db, company_id, data.customer_id, order)

    # Soft inventory check — flags low stock, does not block
    _check_inventory_on_order(db, company_id, order)

    audit_service.log_action(
        db,
        company_id,
        "created",
        "sales_order",
        order.id,
        user_id=user_id,
        changes={"number": order.number, "total": str(total)},
    )
    db.commit()
    db.refresh(order)
    return order


def update_sales_order(
    db: Session, company_id: str, user_id: str, order_id: str, data
) -> SalesOrder:
    order = get_sales_order(db, company_id, order_id)

    if order.status in ("completed", "canceled"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot modify order in '{order.status}' status",
        )

    for field in ("status", "required_date", "shipped_date", "notes",
                   "deceased_name", "service_location", "service_location_other",
                   "service_time", "eta"):
        val = getattr(data, field, None)
        if val is not None:
            setattr(order, field, val)

    order.modified_by = user_id
    order.modified_at = datetime.now(timezone.utc)

    new_status = getattr(data, "status", None)

    audit_service.log_action(
        db,
        company_id,
        "updated",
        "sales_order",
        order.id,
        user_id=user_id,
    )
    db.commit()
    db.refresh(order)

    # Hook: auto-create delivery when order is confirmed
    if new_status == "confirmed":
        try:
            from app.services import order_integration_service

            order_integration_service.on_order_confirmed(db, order)
        except Exception as exc:
            logger.error("Order integration hook failed for %s: %s", order.id, exc)

    return order


def create_invoice_from_order(
    db: Session, company_id: str, user_id: str, order_id: str
) -> Invoice:
    order = get_sales_order(db, company_id, order_id)

    if order.status in ("canceled",):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot invoice a canceled order",
        )

    inv_number = _next_number(db, company_id, Invoice, "INV")
    now = datetime.now(timezone.utc)
    days = _parse_payment_terms_days(order.payment_terms)
    due_date = now + timedelta(days=days)

    invoice = Invoice(
        id=str(uuid.uuid4()),
        company_id=company_id,
        number=inv_number,
        customer_id=order.customer_id,
        sales_order_id=order.id,
        status="draft",
        invoice_date=now,
        due_date=due_date,
        payment_terms=order.payment_terms,
        tax_rate=order.tax_rate,
        subtotal=order.subtotal,
        tax_amount=order.tax_amount,
        total=order.total,
        notes=order.notes,
        deceased_name=order.deceased_name,
        created_by=user_id,
    )
    db.add(invoice)
    db.flush()

    for sol in order.lines:
        il = InvoiceLine(
            id=str(uuid.uuid4()),
            invoice_id=invoice.id,
            product_id=sol.product_id,
            description=sol.description,
            quantity=sol.quantity,
            unit_price=sol.unit_price,
            line_total=sol.line_total,
            sort_order=sol.sort_order,
        )
        db.add(il)

    # Update customer balance
    customer = _get_customer_or_404(db, company_id, order.customer_id)
    customer.current_balance += invoice.total

    audit_service.log_action(
        db,
        company_id,
        "created",
        "invoice",
        invoice.id,
        user_id=user_id,
        changes={
            "number": invoice.number,
            "from_order": order.number,
            "total": str(invoice.total),
        },
    )
    db.commit()
    db.refresh(invoice)
    return invoice


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------


def get_invoices(
    db: Session,
    company_id: str,
    page: int = 1,
    per_page: int = 20,
    status_filter: str | None = None,
    customer_id: str | None = None,
) -> dict:
    query = db.query(Invoice).filter(Invoice.company_id == company_id)
    if status_filter:
        query = query.filter(Invoice.status == status_filter)
    if customer_id:
        query = query.filter(Invoice.customer_id == customer_id)

    total = query.count()
    items = (
        query.options(joinedload(Invoice.customer))
        .order_by(Invoice.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {"items": items, "total": total, "page": page, "per_page": per_page}


def get_invoice(db: Session, company_id: str, invoice_id: str) -> Invoice:
    invoice = (
        db.query(Invoice)
        .options(
            joinedload(Invoice.customer),
            joinedload(Invoice.lines),
            joinedload(Invoice.payment_applications),
            joinedload(Invoice.creator),
        )
        .filter(Invoice.id == invoice_id, Invoice.company_id == company_id)
        .first()
    )
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found"
        )
    return invoice


def create_invoice(db: Session, company_id: str, user_id: str, data) -> Invoice:
    customer = _get_customer_or_404(db, company_id, data.customer_id)

    subtotal, tax_amount, total = _compute_totals(data.lines, data.tax_rate)
    number = _next_number(db, company_id, Invoice, "INV")

    invoice = Invoice(
        id=str(uuid.uuid4()),
        company_id=company_id,
        number=number,
        customer_id=data.customer_id,
        sales_order_id=data.sales_order_id,
        status="draft",
        invoice_date=data.invoice_date,
        due_date=data.due_date,
        payment_terms=data.payment_terms,
        tax_rate=data.tax_rate,
        subtotal=subtotal,
        tax_amount=tax_amount,
        total=total,
        notes=data.notes,
        created_by=user_id,
    )
    db.add(invoice)
    db.flush()

    for idx, ld in enumerate(data.lines):
        line = InvoiceLine(
            id=str(uuid.uuid4()),
            invoice_id=invoice.id,
            product_id=ld.product_id,
            description=ld.description,
            quantity=ld.quantity,
            unit_price=ld.unit_price,
            line_total=_compute_line_total(ld.quantity, ld.unit_price),
            sort_order=ld.sort_order if ld.sort_order else idx,
        )
        db.add(line)

    # Update customer balance
    customer.current_balance += total

    db.flush()

    audit_service.log_action(
        db,
        company_id,
        "created",
        "invoice",
        invoice.id,
        user_id=user_id,
        changes={"number": invoice.number, "total": str(total)},
    )
    db.commit()
    db.refresh(invoice)
    return invoice


def update_invoice(
    db: Session, company_id: str, user_id: str, invoice_id: str, data
) -> Invoice:
    invoice = get_invoice(db, company_id, invoice_id)

    if invoice.status in ("void", "paid"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot modify invoice in '{invoice.status}' status",
        )

    for field in ("status", "notes"):
        val = getattr(data, field, None)
        if val is not None:
            setattr(invoice, field, val)

    invoice.modified_by = user_id
    invoice.modified_at = datetime.now(timezone.utc)

    audit_service.log_action(
        db,
        company_id,
        "updated",
        "invoice",
        invoice.id,
        user_id=user_id,
    )
    db.commit()
    db.refresh(invoice)
    return invoice


def void_invoice(
    db: Session, company_id: str, user_id: str, invoice_id: str
) -> Invoice:
    invoice = get_invoice(db, company_id, invoice_id)

    if invoice.status == "void":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice is already void",
        )
    if invoice.amount_paid > Decimal("0.00"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot void an invoice with payments applied",
        )

    invoice.status = "void"
    invoice.modified_by = user_id
    invoice.modified_at = datetime.now(timezone.utc)

    # Reverse the remaining balance from the customer's current_balance
    customer = _get_customer_or_404(db, company_id, invoice.customer_id)
    customer.current_balance -= invoice.balance_remaining

    audit_service.log_action(
        db,
        company_id,
        "voided",
        "invoice",
        invoice.id,
        user_id=user_id,
        changes={"reversed_balance": str(invoice.balance_remaining)},
    )
    db.commit()
    db.refresh(invoice)
    return invoice


# ---------------------------------------------------------------------------
# Customer Payments — helper functions
# ---------------------------------------------------------------------------


def _create_short_pay_alert(db, company_id, customer, invoice, amount_paid, difference, days_late):
    """Create an agent alert for a short pay that looks like a late discount attempt."""
    try:
        from app.models.agent import AgentAlert
        alert = AgentAlert(
            tenant_id=company_id,
            alert_type="short_pay_late_discount",
            severity="warning",
            title=f"Short pay — late discount: {customer.name}",
            message=(
                f"{customer.name} paid ${float(amount_paid):.2f} on invoice "
                f"#{invoice.number} but the 5% early payment window expired "
                f"{days_late} day{'s' if days_late != 1 else ''} ago. "
                f"Balance remaining: ${difference:.2f}. "
                f"Decide whether to honor the discount."
            ),
            action_label="Honor discount",
            action_url=f"/api/v1/sales/invoices/{invoice.id}/honor-discount",
        )
        db.add(alert)
    except Exception as e:
        logger.warning("Could not create short pay alert: %s", e)


def _check_credit_on_order(db, company_id, customer_id, order):
    """Create agent alert if customer is on credit hold or order exceeds limit."""
    try:
        from app.models.customer import Customer
        from app.models.agent import AgentAlert

        customer = db.query(Customer).filter(
            Customer.id == customer_id, Customer.company_id == company_id
        ).first()
        if not customer or not customer.credit_limit or customer.credit_limit <= 0:
            return

        current = float(customer.current_balance or 0)
        limit = float(customer.credit_limit)
        order_total = float(order.total or 0)

        if current >= limit:
            # Already on hold
            alert = AgentAlert(
                tenant_id=company_id,
                alert_type="order_credit_hold",
                severity="warning",
                title=f"Order for customer on credit hold: {customer.name}",
                message=(
                    f"{customer.name} is on credit hold with balance ${current:,.2f} "
                    f"(limit ${limit:,.2f}). Order {order.number} was created "
                    f"but should be reviewed before fulfillment."
                ),
                action_label="View Customer",
                action_url=f"/customers/{customer_id}",
            )
            db.add(alert)
        elif (current + order_total) > limit:
            # Would exceed
            projected = current + order_total
            alert = AgentAlert(
                tenant_id=company_id,
                alert_type="order_exceeds_credit",
                severity="info",
                title=f"Order exceeds credit limit: {customer.name}",
                message=(
                    f"This order of ${order_total:,.2f} would bring {customer.name}'s "
                    f"balance to ${projected:,.2f}, exceeding their ${limit:,.2f} limit."
                ),
                action_label="View Customer",
                action_url=f"/customers/{customer_id}",
            )
            db.add(alert)
    except Exception as e:
        logger.warning("Credit check on order failed: %s", e)


def _check_inventory_on_order(db, company_id, order):
    """Create agent alerts for low-stock products on this order."""
    try:
        from app.models.inventory_item import InventoryItem
        from app.models.sales_order import SalesOrderLine
        from app.models.product import Product
        from app.models.agent import AgentAlert

        lines = db.query(SalesOrderLine).filter(
            SalesOrderLine.sales_order_id == order.id
        ).all()

        warnings = []
        for line in lines:
            if not line.product_id:
                continue
            inv = db.query(InventoryItem).filter(
                InventoryItem.company_id == company_id,
                InventoryItem.product_id == line.product_id,
            ).first()
            if not inv:
                continue

            qty_on_hand = inv.quantity_on_hand or 0
            reorder_point = inv.reorder_point or 2
            line_qty = int(line.quantity or 0)
            remaining_after = qty_on_hand - line_qty

            if remaining_after < 0:
                product = db.query(Product).filter(Product.id == line.product_id).first()
                name = product.name if product else "Product"
                warnings.append(
                    f"Only {qty_on_hand} {name} in stock — this order requires {line_qty}."
                )
            elif qty_on_hand <= reorder_point:
                product = db.query(Product).filter(Product.id == line.product_id).first()
                name = product.name if product else "Product"
                warnings.append(
                    f"After this order, only {remaining_after} {name} will remain in stock."
                )

        if warnings:
            order.has_inventory_warning = True
            order.inventory_warning_notes = "; ".join(warnings)
            alert = AgentAlert(
                tenant_id=company_id,
                alert_type="low_stock_on_order",
                severity="warning" if any("requires" in w for w in warnings) else "info",
                title=f"Low stock on order {order.number}",
                message="; ".join(warnings),
                action_label="View Inventory",
                action_url="/inventory",
            )
            db.add(alert)
    except Exception as e:
        logger.warning("Inventory check on order failed: %s", e)


def _auto_complete_order_on_payment(db, invoice, company_id):
    """Mark the associated SalesOrder as completed when its invoice is fully paid."""
    try:
        from app.models.sales_order import SalesOrder

        if not getattr(invoice, "sales_order_id", None):
            return
        order = db.query(SalesOrder).filter(SalesOrder.id == invoice.sales_order_id).first()
        if not order:
            return
        if order.status in ("cancelled", "completed"):
            return
        order.status = "completed"
        order.completed_at = datetime.now(timezone.utc)
    except Exception as e:
        logger.warning("Could not auto-complete order on payment: %s", e)


def _create_overpayment_alert(db, company_id, customer, total_amount, applied, overpayment):
    """Create an agent alert for an overpayment."""
    try:
        from app.models.agent import AgentAlert
        alert = AgentAlert(
            tenant_id=company_id,
            alert_type="overpayment",
            severity="info",
            title=f"Overpayment: {customer.name}",
            message=(
                f"{customer.name} paid ${float(total_amount):.2f} but only "
                f"${applied:.2f} was applied to open invoices. "
                f"${overpayment:.2f} credit added to their account."
            ),
        )
        db.add(alert)
    except Exception as e:
        logger.warning("Could not create overpayment alert: %s", e)


# ---------------------------------------------------------------------------
# Customer Payments
# ---------------------------------------------------------------------------


def get_customer_payments(
    db: Session,
    company_id: str,
    page: int = 1,
    per_page: int = 20,
    customer_id: str | None = None,
) -> dict:
    query = db.query(CustomerPayment).filter(
        CustomerPayment.company_id == company_id,
        CustomerPayment.deleted_at.is_(None),
    )
    if customer_id:
        query = query.filter(CustomerPayment.customer_id == customer_id)

    total = query.count()
    items = (
        query.options(joinedload(CustomerPayment.customer))
        .order_by(CustomerPayment.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {"items": items, "total": total, "page": page, "per_page": per_page}


def create_customer_payment(
    db: Session, company_id: str, user_id: str, data
) -> CustomerPayment:
    customer = _get_customer_or_404(db, company_id, data.customer_id)

    # Validate sum of applications matches total_amount
    app_total = sum(a.amount_applied for a in data.applications)
    if app_total != data.total_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Sum of applications ({app_total}) does not match "
                f"total amount ({data.total_amount})"
            ),
        )

    # Validate each application against invoice balance
    for app in data.applications:
        invoice = (
            db.query(Invoice)
            .filter(
                Invoice.id == app.invoice_id,
                Invoice.company_id == company_id,
            )
            .first()
        )
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invoice {app.invoice_id} not found",
            )
        if invoice.status in ("void", "draft"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invoice {invoice.number} is in '{invoice.status}' status and cannot receive payment",
            )
        if app.amount_applied > invoice.balance_remaining:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Amount {app.amount_applied} exceeds balance "
                    f"({invoice.balance_remaining}) on invoice {invoice.number}"
                ),
            )

    # Create payment
    payment = CustomerPayment(
        id=str(uuid.uuid4()),
        company_id=company_id,
        customer_id=data.customer_id,
        payment_date=data.payment_date,
        total_amount=data.total_amount,
        payment_method=data.payment_method,
        reference_number=data.reference_number,
        notes=data.notes,
        created_by=user_id,
    )
    db.add(payment)
    db.flush()

    # Create applications and update invoices
    payment_date_only = (
        data.payment_date.date()
        if hasattr(data.payment_date, "date")
        else data.payment_date
    )
    for app_data in data.applications:
        pa = CustomerPaymentApplication(
            id=str(uuid.uuid4()),
            payment_id=payment.id,
            invoice_id=app_data.invoice_id,
            amount_applied=app_data.amount_applied,
        )
        db.add(pa)

        invoice = db.query(Invoice).filter(Invoice.id == app_data.invoice_id).first()
        invoice.amount_paid += app_data.amount_applied
        invoice.modified_by = user_id
        invoice.modified_at = datetime.now(timezone.utc)

        # Update invoice status
        if invoice.amount_paid >= invoice.total:
            invoice.status = "paid"
            invoice.paid_at = datetime.now(timezone.utc)
            # Auto-complete associated sales order
            _auto_complete_order_on_payment(db, invoice, company_id)
        elif invoice.amount_paid > Decimal("0.00"):
            invoice.status = "partial"

        # Short pay late discount detection
        if (
            invoice.discount_deadline
            and invoice.discounted_total
            and payment_date_only > invoice.discount_deadline
            and float(app_data.amount_applied) >= float(invoice.discounted_total) * 0.99
            and float(app_data.amount_applied) < float(invoice.total)
        ):
            difference = float(invoice.total) - float(app_data.amount_applied)
            days_late = (payment_date_only - invoice.discount_deadline).days
            _create_short_pay_alert(
                db, company_id, customer, invoice, app_data.amount_applied, difference, days_late
            )

    # Subtract payment from customer balance
    customer.current_balance -= data.total_amount

    # Overpayment detection — any unmatched amount becomes customer credit
    total_applied = sum(
        float(app_data.amount_applied) for app_data in data.applications
    )
    if total_applied < float(data.total_amount) - 0.01:
        overpayment = float(data.total_amount) - total_applied
        customer.credit_balance = (customer.credit_balance or Decimal("0.00")) + Decimal(
            str(round(overpayment, 2))
        )
        _create_overpayment_alert(
            db, company_id, customer, data.total_amount, total_applied, overpayment
        )

    db.flush()

    audit_service.log_action(
        db,
        company_id,
        "created",
        "customer_payment",
        payment.id,
        user_id=user_id,
        changes={
            "total_amount": str(data.total_amount),
            "customer_id": data.customer_id,
            "method": data.payment_method,
        },
    )
    db.commit()
    db.refresh(payment)

    # CRM activity log
    try:
        from app.services.crm.activity_log_service import log_system_event
        log_system_event(
            db, company_id, None,
            activity_type="payment",
            title=f"Payment received — ${data.total_amount:,.2f} ({data.payment_method or 'check'})",
            customer_id=data.customer_id,
        )
        db.commit()
    except Exception:
        pass

    return payment


# ---------------------------------------------------------------------------
# AR Aging
# ---------------------------------------------------------------------------


def get_ar_aging(
    db: Session, company_id: str, as_of_date: datetime | None = None
) -> ARAgingReport:
    """Build AR aging report from open invoices, grouped by customer with
    buckets for current, 1-30, 31-60, 61-90, and 90+ days past due."""

    if as_of_date is None:
        as_of_date = datetime.now(timezone.utc)

    from app.utils.company_name_resolver import resolve_customer_name

    invoices = (
        db.query(Invoice)
        .options(joinedload(Invoice.customer).joinedload(Customer.company_entity))
        .filter(
            Invoice.company_id == company_id,
            Invoice.status.in_(["sent", "partial", "overdue"]),
        )
        .all()
    )

    zero = Decimal("0.00")
    customer_buckets: dict[str, dict] = {}

    for inv in invoices:
        balance = inv.balance_remaining
        if balance <= zero:
            continue

        cid = inv.customer_id
        if cid not in customer_buckets:
            customer_buckets[cid] = {
                "customer_id": cid,
                "customer_name": resolve_customer_name(inv.customer),
                "account_number": (
                    inv.customer.account_number if inv.customer else None
                ),
                "current": zero,
                "days_1_30": zero,
                "days_31_60": zero,
                "days_61_90": zero,
                "days_over_90": zero,
                "total": zero,
            }

        days_past = (as_of_date - inv.due_date).days if inv.due_date else 0

        bucket = customer_buckets[cid]
        if days_past <= 0:
            bucket["current"] += balance
        elif days_past <= 30:
            bucket["days_1_30"] += balance
        elif days_past <= 60:
            bucket["days_31_60"] += balance
        elif days_past <= 90:
            bucket["days_61_90"] += balance
        else:
            bucket["days_over_90"] += balance

        bucket["total"] += balance

    # Build per-customer response objects
    customers_sorted = sorted(
        customer_buckets.values(), key=lambda c: c["total"], reverse=True
    )

    customer_results = []
    summary = ARAgingBucket()

    for c in customers_sorted:
        b = ARAgingBucket(
            current=c["current"],
            days_1_30=c["days_1_30"],
            days_31_60=c["days_31_60"],
            days_61_90=c["days_61_90"],
            days_over_90=c["days_over_90"],
            total=c["total"],
        )
        customer_results.append(
            ARAgingCustomer(
                customer_id=c["customer_id"],
                customer_name=c["customer_name"],
                account_number=c["account_number"],
                buckets=b,
            )
        )
        summary.current += c["current"]
        summary.days_1_30 += c["days_1_30"]
        summary.days_31_60 += c["days_31_60"]
        summary.days_61_90 += c["days_61_90"]
        summary.days_over_90 += c["days_over_90"]
        summary.total += c["total"]

    return ARAgingReport(company_summary=summary, customers=customer_results)


# ---------------------------------------------------------------------------
# Sales Stats
# ---------------------------------------------------------------------------


def get_sales_stats(db: Session, company_id: str) -> SalesStats:
    total_quotes = (
        db.query(func.count(Quote.id))
        .filter(Quote.company_id == company_id)
        .scalar()
        or 0
    )
    open_quotes = (
        db.query(func.count(Quote.id))
        .filter(
            Quote.company_id == company_id,
            Quote.status.in_(["draft", "sent"]),
        )
        .scalar()
        or 0
    )

    total_orders = (
        db.query(func.count(SalesOrder.id))
        .filter(SalesOrder.company_id == company_id)
        .scalar()
        or 0
    )
    open_orders = (
        db.query(func.count(SalesOrder.id))
        .filter(
            SalesOrder.company_id == company_id,
            SalesOrder.status.in_(["draft", "confirmed", "processing", "shipped"]),
        )
        .scalar()
        or 0
    )

    total_invoices = (
        db.query(func.count(Invoice.id))
        .filter(Invoice.company_id == company_id)
        .scalar()
        or 0
    )
    outstanding_invoices = (
        db.query(func.count(Invoice.id))
        .filter(
            Invoice.company_id == company_id,
            Invoice.status.in_(["sent", "partial", "overdue"]),
        )
        .scalar()
        or 0
    )

    total_ar = (
        db.query(func.sum(Invoice.total - Invoice.amount_paid))
        .filter(
            Invoice.company_id == company_id,
            Invoice.status.in_(["sent", "partial", "overdue"]),
        )
        .scalar()
        or Decimal("0.00")
    )

    return SalesStats(
        total_quotes=total_quotes,
        open_quotes=open_quotes,
        total_orders=total_orders,
        open_orders=open_orders,
        total_invoices=total_invoices,
        outstanding_invoices=outstanding_invoices,
        total_ar_outstanding=total_ar,
    )


# ---------------------------------------------------------------------------
# Sage Payment CSV Import
# ---------------------------------------------------------------------------

_PAYMENT_HEADER_MAP: dict[str, str] = {
    # payment_date
    "payment date": "payment_date",
    "payment_date": "payment_date",
    "date": "payment_date",
    "posting date": "payment_date",
    "posting_date": "payment_date",
    # customer_account
    "customer id": "customer_account",
    "customer_id": "customer_account",
    "customer account": "customer_account",
    "account number": "customer_account",
    "account_number": "customer_account",
    "account #": "customer_account",
    "acct #": "customer_account",
    "acct": "customer_account",
    # sage_customer_id
    "sage customer id": "sage_customer_id",
    "sage_customer_id": "sage_customer_id",
    # invoice_number
    "invoice number": "invoice_number",
    "invoice_number": "invoice_number",
    "invoice #": "invoice_number",
    "invoice no": "invoice_number",
    "invoice": "invoice_number",
    # sage_invoice_id
    "sage invoice id": "sage_invoice_id",
    "sage_invoice_id": "sage_invoice_id",
    # amount_applied
    "amount applied": "amount_applied",
    "amount_applied": "amount_applied",
    "amount": "amount_applied",
    "applied amount": "amount_applied",
    # total_amount
    "total amount": "total_amount",
    "total_amount": "total_amount",
    "payment amount": "total_amount",
    "payment_amount": "total_amount",
    "total": "total_amount",
    # payment_method
    "payment method": "payment_method",
    "payment_method": "payment_method",
    "method": "payment_method",
    "type": "payment_method",
    # reference_number
    "reference": "reference_number",
    "reference number": "reference_number",
    "reference_number": "reference_number",
    "check number": "reference_number",
    "check_number": "reference_number",
    "check #": "reference_number",
    "ref #": "reference_number",
    # notes
    "notes": "notes",
    "memo": "notes",
    "description": "notes",
}

_PAYMENT_METHOD_MAP: dict[str, str] = {
    "check": "check",
    "chk": "check",
    "ach": "ach",
    "wire": "wire",
    "wir": "wire",
    "credit card": "credit_card",
    "credit_card": "credit_card",
    "cc": "credit_card",
    "cash": "cash",
    "csh": "cash",
}


def _normalise_payment_headers(fieldnames: list[str]) -> dict[str, str]:
    """Map raw CSV header names to canonical field names."""
    mapping: dict[str, str] = {}
    for raw in fieldnames:
        key = raw.strip().lower()
        canonical = _PAYMENT_HEADER_MAP.get(key)
        if canonical:
            mapping[raw] = canonical
    return mapping


def _parse_amount(raw: str) -> Decimal | None:
    """Parse a currency string like '$1,234.56' into a Decimal."""
    cleaned = raw.strip().replace(",", "").replace("$", "")
    if not cleaned:
        return None
    try:
        return Decimal(cleaned).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def _parse_date(raw: str) -> str | None:
    """Try common date formats and return ISO date string (YYYY-MM-DD)."""
    raw = raw.strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def import_sage_payments_from_csv(
    db: Session,
    file_content: bytes,
    company_id: str,
    actor_id: str | None = None,
) -> dict:
    """Parse a Sage payment CSV and create customer payments.

    Rows are grouped by (reference_number, customer, payment_date) into single
    CustomerPayment records, each with one or more invoice applications.

    Returns ``{"created": int, "skipped": int, "errors": [{"row": int, "message": str}]}``
    """
    sync_log = create_sync_log(
        db,
        company_id,
        sync_type="csv_import",
        source="sage_csv",
        destination="customer_payments",
    )

    # --- Decode CSV ---
    try:
        text = file_content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = file_content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file is empty or has no headers",
        )

    header_map = _normalise_payment_headers(list(reader.fieldnames))
    mapped_fields = set(header_map.values())

    # Validate required columns
    has_customer = "customer_account" in mapped_fields or "sage_customer_id" in mapped_fields
    has_invoice = "invoice_number" in mapped_fields or "sage_invoice_id" in mapped_fields
    has_amount = "amount_applied" in mapped_fields

    if not has_customer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV must contain a customer identifier column (e.g. 'Account Number', 'Customer ID')",
        )
    if not has_invoice:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV must contain an invoice identifier column (e.g. 'Invoice Number', 'Invoice #')",
        )
    if not has_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV must contain an amount column (e.g. 'Amount Applied', 'Amount')",
        )

    # --- Pre-load lookup indexes ---
    customers_by_account: dict[str, Customer] = {}
    for c in db.query(Customer).filter(Customer.company_id == company_id).all():
        if c.account_number:
            customers_by_account[c.account_number.upper()] = c
        if c.sage_customer_id:
            customers_by_account[f"SAGE:{c.sage_customer_id}"] = c

    invoices_by_number: dict[str, Invoice] = {}
    for inv in db.query(Invoice).filter(Invoice.company_id == company_id).all():
        if inv.number:
            invoices_by_number[inv.number.upper()] = inv
        if inv.sage_invoice_id:
            invoices_by_number[f"SAGE:{inv.sage_invoice_id}"] = inv

    existing_sage_ids: set[str] = {
        pid[0]
        for pid in db.query(CustomerPayment.sage_payment_id)
        .filter(
            CustomerPayment.company_id == company_id,
            CustomerPayment.sage_payment_id.isnot(None),
        )
        .all()
    }

    # --- First pass: parse rows and group into payments ---
    errors: list[dict[str, object]] = []
    # Key: (ref, customer_id, date_str) -> list of (invoice, amount, row_num, notes)
    groups: dict[tuple[str, str, str], dict] = {}

    for row_num, raw_row in enumerate(reader, start=2):
        row: dict[str, str] = {}
        for raw_key, value in raw_row.items():
            canonical = header_map.get(raw_key)
            if canonical:
                row[canonical] = (value or "").strip()

        # Find customer
        customer: Customer | None = None
        acct_raw = row.get("customer_account", "")
        sage_cid = row.get("sage_customer_id", "")

        if acct_raw:
            customer = customers_by_account.get(acct_raw.upper())
        if not customer and sage_cid:
            customer = customers_by_account.get(f"SAGE:{sage_cid}")

        if not customer:
            errors.append({"row": row_num, "message": f"Customer not found: {acct_raw or sage_cid}"})
            continue

        # Find invoice
        invoice: Invoice | None = None
        inv_num = row.get("invoice_number", "")
        sage_inv = row.get("sage_invoice_id", "")

        if inv_num:
            invoice = invoices_by_number.get(inv_num.upper())
        if not invoice and sage_inv:
            invoice = invoices_by_number.get(f"SAGE:{sage_inv}")

        if not invoice:
            errors.append({"row": row_num, "message": f"Invoice not found: {inv_num or sage_inv}"})
            continue

        # Validate invoice belongs to this customer
        if invoice.customer_id != customer.id:
            errors.append({
                "row": row_num,
                "message": f"Invoice {invoice.number} does not belong to customer {customer.name}",
            })
            continue

        # Parse amount
        amount = _parse_amount(row.get("amount_applied", ""))
        if not amount or amount <= Decimal("0"):
            errors.append({"row": row_num, "message": f"Invalid amount: {row.get('amount_applied', '')}"})
            continue

        # Parse date
        date_str = _parse_date(row.get("payment_date", ""))
        if not date_str:
            errors.append({"row": row_num, "message": f"Invalid or missing payment date: {row.get('payment_date', '')}"})
            continue

        # Payment method
        raw_method = row.get("payment_method", "").strip().lower()
        method = _PAYMENT_METHOD_MAP.get(raw_method, "check")

        ref = row.get("reference_number", "").strip() or f"IMPORT-{row_num}"
        notes = row.get("notes", "").strip() or None

        # Group key
        group_key = (ref, customer.id, date_str)
        if group_key not in groups:
            groups[group_key] = {
                "customer": customer,
                "payment_date": date_str,
                "payment_method": method,
                "reference_number": ref,
                "notes": notes,
                "applications": [],
            }
        groups[group_key]["applications"].append({
            "invoice": invoice,
            "amount_applied": amount,
            "row_num": row_num,
        })

    # --- Second pass: create payments ---
    created = 0
    skipped = 0

    for group_key, group in groups.items():
        ref, customer_id, date_str = group_key
        customer = group["customer"]
        acct_display = customer.account_number or customer.id

        # Derive sage_payment_id for duplicate detection
        sage_payment_id = f"SAGE-{ref}-{acct_display}-{date_str}"
        if sage_payment_id in existing_sage_ids:
            skipped += 1
            continue

        # Validate each application
        total_amount = Decimal("0.00")
        valid = True

        for app in group["applications"]:
            inv = app["invoice"]
            amt = app["amount_applied"]

            if inv.status in ("void", "draft"):
                errors.append({
                    "row": app["row_num"],
                    "message": f"Invoice {inv.number} is '{inv.status}' and cannot receive payment",
                })
                valid = False
                break

            if amt > inv.balance_remaining:
                errors.append({
                    "row": app["row_num"],
                    "message": (
                        f"Amount {amt} exceeds balance {inv.balance_remaining} "
                        f"on invoice {inv.number}"
                    ),
                })
                valid = False
                break

            total_amount += amt

        if not valid:
            skipped += 1
            continue

        # Create payment
        payment = CustomerPayment(
            id=str(uuid.uuid4()),
            company_id=company_id,
            customer_id=customer.id,
            payment_date=datetime.strptime(date_str, "%Y-%m-%d"),
            total_amount=total_amount,
            payment_method=group["payment_method"],
            reference_number=group["reference_number"],
            notes=group["notes"],
            sage_payment_id=sage_payment_id,
            created_by=actor_id,
        )
        db.add(payment)
        db.flush()

        # Create applications and update invoices
        for app in group["applications"]:
            inv = app["invoice"]
            amt = app["amount_applied"]

            pa = CustomerPaymentApplication(
                id=str(uuid.uuid4()),
                payment_id=payment.id,
                invoice_id=inv.id,
                amount_applied=amt,
            )
            db.add(pa)

            inv.amount_paid += amt
            inv.modified_by = actor_id
            inv.modified_at = datetime.now(timezone.utc)

            if inv.amount_paid >= inv.total:
                inv.status = "paid"
            elif inv.amount_paid > Decimal("0.00"):
                inv.status = "partial"

        # Update customer balance
        customer.current_balance -= total_amount

        existing_sage_ids.add(sage_payment_id)
        created += 1

    if created > 0:
        audit_service.log_action(
            db,
            company_id,
            "bulk_imported",
            "customer_payment",
            None,
            user_id=actor_id,
            changes={"count": created, "source": "sage_csv"},
        )

    error_summary = (
        "; ".join(f"Row {e['row']}: {e['message']}" for e in errors[:10])
        if errors
        else None
    )
    complete_sync_log(db, sync_log, created, skipped, error_summary)
    db.commit()

    return {"created": created, "skipped": skipped, "errors": errors}


# ---------------------------------------------------------------------------
# Payment detail and void
# ---------------------------------------------------------------------------


def get_payment_detail(db: Session, payment_id: str, company_id: str) -> dict:
    """Return a single payment with its applications."""
    payment = (
        db.query(CustomerPayment)
        .filter(
            CustomerPayment.id == payment_id,
            CustomerPayment.company_id == company_id,
            CustomerPayment.deleted_at.is_(None),
        )
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    apps = []
    for app in payment.applications:
        inv = db.query(Invoice).filter(Invoice.id == app.invoice_id).first()
        apps.append(
            {
                "invoice_id": app.invoice_id,
                "invoice_number": inv.number if inv else "",
                "invoice_date": (
                    inv.invoice_date.isoformat()
                    if inv and inv.invoice_date
                    else None
                ),
                "amount_applied": float(app.amount_applied),
                "notes": app.notes,
            }
        )

    return {
        "id": payment.id,
        "customer_id": payment.customer_id,
        "payment_date": (
            payment.payment_date.isoformat() if payment.payment_date else None
        ),
        "total_amount": float(payment.total_amount),
        "payment_method": payment.payment_method,
        "reference_number": payment.reference_number,
        "notes": payment.notes,
        "applications": apps,
        "created_by": payment.created_by,
        "created_at": (
            payment.created_at.isoformat() if payment.created_at else None
        ),
    }


def void_payment(
    db: Session, payment_id: str, company_id: str, voided_by: str
) -> dict:
    """Void a payment and reverse all invoice applications."""
    payment = (
        db.query(CustomerPayment)
        .filter(
            CustomerPayment.id == payment_id,
            CustomerPayment.company_id == company_id,
            CustomerPayment.deleted_at.is_(None),
        )
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    customer = (
        db.query(Customer).filter(Customer.id == payment.customer_id).first()
    )

    # Reverse each application
    for app in payment.applications:
        inv = db.query(Invoice).filter(Invoice.id == app.invoice_id).first()
        if inv:
            inv.amount_paid = max(
                Decimal("0.00"), inv.amount_paid - app.amount_applied
            )
            inv.discount_amount = Decimal("0.00")
            inv.paid_at = None
            # Recalculate status
            if inv.amount_paid <= Decimal("0.00"):
                inv.status = "sent"
            elif inv.amount_paid < inv.total:
                inv.status = "partial"

    # Restore customer balance
    if customer:
        customer.current_balance += payment.total_amount

    # Soft delete the payment
    payment.deleted_at = datetime.now(timezone.utc)

    audit_service.log_action(
        db,
        company_id,
        "voided",
        "customer_payment",
        payment.id,
        user_id=voided_by,
        changes={"total_amount": str(payment.total_amount)},
    )

    db.commit()
    return {"message": "Payment voided", "payment_id": payment_id}


def get_invoice_payment_history(
    db: Session, invoice_id: str, company_id: str
) -> list[dict]:
    """Return all payments applied to an invoice."""
    inv = (
        db.query(Invoice)
        .filter(
            Invoice.id == invoice_id,
            Invoice.company_id == company_id,
        )
        .first()
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    apps = (
        db.query(CustomerPaymentApplication)
        .filter(CustomerPaymentApplication.invoice_id == invoice_id)
        .all()
    )

    result = []
    for app in apps:
        pmt = (
            db.query(CustomerPayment)
            .filter(
                CustomerPayment.id == app.payment_id,
                CustomerPayment.deleted_at.is_(None),
            )
            .first()
        )
        if pmt:
            result.append(
                {
                    "payment_id": pmt.id,
                    "payment_date": (
                        pmt.payment_date.isoformat()
                        if pmt.payment_date
                        else None
                    ),
                    "payment_method": pmt.payment_method,
                    "reference_number": pmt.reference_number,
                    "amount_applied": float(app.amount_applied),
                    "notes": app.notes,
                }
            )
    return result


def honor_early_payment_discount(db: Session, invoice_id: str, company_id: str) -> dict:
    """Apply early payment discount retroactively."""
    inv = (
        db.query(Invoice)
        .filter(
            Invoice.id == invoice_id,
            Invoice.company_id == company_id,
        )
        .first()
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.status == "paid":
        raise HTTPException(status_code=400, detail="Invoice already paid")

    discount = float(inv.total) - float(inv.amount_paid)
    inv.discount_amount = Decimal(str(round(discount, 2)))
    inv.amount_paid = inv.total
    inv.status = "paid"
    inv.paid_at = datetime.now(timezone.utc)

    # Adjust customer balance
    customer = db.query(Customer).filter(Customer.id == inv.customer_id).first()
    if customer:
        customer.current_balance -= Decimal(str(round(discount, 2)))

    db.commit()
    db.refresh(inv)
    return {
        "message": "Discount honored",
        "invoice_id": invoice_id,
        "discount_applied": round(discount, 2),
    }


def suggest_payment_application(
    db: Session, customer_id: str, amount, payment_date, company_id: str
) -> dict:
    """Intelligently suggest how to apply a payment to open invoices."""
    from itertools import combinations

    amount = Decimal(str(amount))

    open_invoices = (
        db.query(Invoice)
        .filter(
            Invoice.company_id == company_id,
            Invoice.customer_id == customer_id,
            Invoice.status.in_(["sent", "partial", "overdue"]),
        )
        .order_by(Invoice.invoice_date.asc())
        .all()
    )

    if not open_invoices:
        return {
            "scenario": "no_open_invoices",
            "message": "No open invoices found",
            "applications": [],
        }

    total_open = sum(float(inv.total) - float(inv.amount_paid) for inv in open_invoices)
    amt = float(amount)

    def make_app(inv, amount_to_apply):
        return {
            "invoice_id": inv.id,
            "invoice_number": inv.number,
            "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
            "balance_remaining": float(inv.total) - float(inv.amount_paid),
            "amount_to_apply": round(amount_to_apply, 2),
            "covers_fully": amount_to_apply >= (float(inv.total) - float(inv.amount_paid)) - 0.01,
        }

    # Exact match — covers all open invoices
    if abs(amt - total_open) < 0.02:
        return {
            "scenario": "exact_match",
            "message": "This payment covers the full open balance",
            "confidence": 0.99,
            "applications": [
                make_app(inv, float(inv.total) - float(inv.amount_paid))
                for inv in open_invoices
            ],
        }

    # Overpayment
    if amt > total_open + 0.01:
        return {
            "scenario": "overpayment",
            "message": (
                f"This payment is ${amt - total_open:.2f} more than the open balance. "
                "The excess will be held as customer credit."
            ),
            "confidence": 0.95,
            "applications": [
                make_app(inv, float(inv.total) - float(inv.amount_paid))
                for inv in open_invoices
            ],
        }

    # Check for early payment discount match on single invoice
    for inv in open_invoices:
        if inv.discounted_total and abs(amt - float(inv.discounted_total)) < 0.02:
            return {
                "scenario": "early_pay_discount",
                "message": f"This matches the early payment discount amount for invoice #{inv.number}",
                "confidence": 0.97,
                "applications": [make_app(inv, float(inv.discounted_total))],
            }

    # Check subset match (up to 5 invoices)
    for r in range(1, min(6, len(open_invoices) + 1)):
        for combo in combinations(open_invoices, r):
            combo_total = sum(float(inv.total) - float(inv.amount_paid) for inv in combo)
            if abs(combo_total - amt) < 0.02:
                nums = ", ".join(f"#{inv.number}" for inv in combo)
                return {
                    "scenario": "invoice_subset",
                    "message": (
                        f"This covers invoice{'s' if len(combo) > 1 else ''} {nums} exactly"
                    ),
                    "confidence": 0.95,
                    "applications": [
                        make_app(inv, float(inv.total) - float(inv.amount_paid))
                        for inv in combo
                    ],
                }

    # FIFO partial
    remaining = amt
    applications = []
    for inv in open_invoices:
        if remaining <= 0:
            break
        bal = float(inv.total) - float(inv.amount_paid)
        apply = min(remaining, bal)
        applications.append(make_app(inv, apply))
        remaining -= apply

    return {
        "scenario": "fifo_partial",
        "message": "Applied oldest-first until payment is exhausted",
        "confidence": 0.8,
        "applications": applications,
    }


async def scan_check_image(db: Session, file, company_id: str) -> dict:
    """Use Claude Vision to extract payment info from a check image."""
    import base64
    import json as _json

    # Read image
    content = await file.read()
    b64_image = base64.b64encode(content).decode()
    content_type = file.content_type or "image/jpeg"

    prompt = """Extract payment information from this check image. Return JSON only:
{
  "payer_name": "string or null",
  "amount": "decimal number or null",
  "check_number": "string or null",
  "check_date": "YYYY-MM-DD or null",
  "memo": "string or null",
  "bank_name": "string or null",
  "confidence": {
    "payer_name": 0.0,
    "amount": 0.0,
    "check_number": 0.0,
    "check_date": 0.0
  }
}
Return only valid JSON. If a field is not clearly visible, return null."""

    extracted = {}
    try:
        import anthropic
        from app.config import settings
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": content_type,
                                "data": b64_image,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        extracted = _json.loads(response.content[0].text)
    except Exception as e:
        logger.error("Check scan failed: %s", e)
        return {
            "extracted": {},
            "matched_customer": None,
            "suggested_applications": [],
            "error": str(e),
        }

    # Fuzzy match payer_name against customers
    matched_customer = None
    suggested_applications = []

    if extracted.get("payer_name"):
        customers = (
            db.query(Customer)
            .filter(
                Customer.company_id == company_id,
                Customer.is_active.is_(True),
            )
            .all()
        )

        payer = extracted["payer_name"].lower().strip()
        best_match = None
        best_score = 0.0

        for cust in customers:
            name = cust.name.lower().strip()
            payer_tokens = set(payer.split())
            name_tokens = set(name.split())
            stop = {"funeral", "home", "homes", "chapel", "memorial", "inc", "llc", "the", "and", "&"}
            payer_tokens -= stop
            name_tokens -= stop
            if not payer_tokens or not name_tokens:
                continue
            overlap = len(payer_tokens & name_tokens)
            union = len(payer_tokens | name_tokens)
            score = overlap / union if union else 0.0
            if score > best_score:
                best_score = score
                best_match = cust

        if best_match and best_score >= 0.6:
            matched_customer = {
                "customer_id": best_match.id,
                "name": best_match.name,
                "match_confidence": best_score,
                "match_method": "payer_name",
            }

            open_invoices = (
                db.query(Invoice)
                .filter(
                    Invoice.company_id == company_id,
                    Invoice.customer_id == best_match.id,
                    Invoice.status.in_(["sent", "partial", "overdue"]),
                )
                .order_by(Invoice.invoice_date.asc())
                .all()
            )

            remaining = float(extracted.get("amount") or 0)
            for inv in open_invoices:
                bal = float(inv.total) - float(inv.amount_paid)
                if remaining <= 0:
                    break
                apply = min(remaining, bal)
                suggested_applications.append(
                    {
                        "invoice_id": inv.id,
                        "invoice_number": inv.number,
                        "invoice_date": (
                            inv.invoice_date.isoformat() if inv.invoice_date else None
                        ),
                        "balance_remaining": bal,
                        "amount_to_apply": apply,
                        "covers_fully": apply >= bal - 0.01,
                    }
                )
                remaining -= apply

    return {
        "extracted": extracted,
        "matched_customer": matched_customer,
        "suggested_applications": suggested_applications,
    }
