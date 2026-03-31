"""Quote management service for the Order Entry Station.

Handles wastewater and other product-line quotes created via the
quick-quote slide-over.  Separate from the general-purpose sales_service
which manages the full Sales → Invoice pipeline.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException, status
from sqlalchemy import and_, func
from sqlalchemy.orm import Session, joinedload

from app.models.quote import Quote, QuoteLine
from app.models.sales_order import SalesOrder, SalesOrderLine
from app.services import audit_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _next_quote_number(db: Session, company_id: str) -> str:
    """Generate next Q-YYYY-NNNN number."""
    year = datetime.now(timezone.utc).year
    prefix = f"Q-{year}-"
    last = (
        db.query(Quote.number)
        .filter(
            Quote.company_id == company_id,
            Quote.number.like(f"{prefix}%"),
        )
        .order_by(Quote.number.desc())
        .first()
    )
    if last and last[0]:
        try:
            seq = int(last[0].replace(prefix, "")) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


def _next_order_number(db: Session, company_id: str) -> str:
    """Generate next SO-YYYY-NNNN number."""
    year = datetime.now(timezone.utc).year
    prefix = f"SO-{year}-"
    last = (
        db.query(SalesOrder.number)
        .filter(
            SalesOrder.company_id == company_id,
            SalesOrder.number.like(f"{prefix}%"),
        )
        .order_by(SalesOrder.number.desc())
        .first()
    )
    if last and last[0]:
        try:
            seq = int(last[0].replace(prefix, "")) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


def _compute_line_total(quantity, unit_price) -> Decimal:
    qty = Decimal(str(quantity))
    price = Decimal(str(unit_price))
    return (qty * price).quantize(Decimal("0.01"))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_quote(
    db: Session,
    tenant_id: str,
    user_id: str,
    *,
    customer_name: str,
    product_line: str,
    line_items: list[dict],
    customer_id: str | None = None,
    template_id: str | None = None,
    permit_number: str | None = None,
    permit_jurisdiction: str | None = None,
    installation_address: str | None = None,
    installation_city: str | None = None,
    installation_state: str | None = None,
    contact_name: str | None = None,
    contact_phone: str | None = None,
    notes: str | None = None,
    delivery_charge: float | None = None,
    cemetery_id: str | None = None,
    cemetery_name: str | None = None,
    deceased_name: str | None = None,
) -> dict:
    """Create a quote record. Returns the quote with generated quote number."""
    now = datetime.now(timezone.utc)
    quote_number = _next_quote_number(db, tenant_id)

    # Compute totals from line items
    subtotal = Decimal("0.00")
    quote_lines: list[QuoteLine] = []
    for idx, item in enumerate(line_items):
        qty = Decimal(str(item.get("quantity", 1)))
        price = Decimal(str(item.get("unit_price", 0)))
        line_total = _compute_line_total(qty, price)
        subtotal += line_total
        quote_lines.append(
            QuoteLine(
                id=str(uuid.uuid4()),
                description=item.get("description", ""),
                product_id=item.get("product_id"),
                quantity=qty,
                unit_price=price,
                line_total=line_total,
                sort_order=idx,
            )
        )

    # Add delivery charge as a separate line if provided
    if delivery_charge and delivery_charge > 0:
        dc = Decimal(str(delivery_charge))
        subtotal += dc
        quote_lines.append(
            QuoteLine(
                id=str(uuid.uuid4()),
                description="Delivery",
                quantity=Decimal("1"),
                unit_price=dc,
                line_total=dc,
                sort_order=len(quote_lines),
            )
        )

    total = subtotal  # No tax for now; can be extended

    quote = Quote(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        number=quote_number,
        customer_id=customer_id,
        customer_name=customer_name,
        status="draft",
        quote_date=now,
        expiry_date=now + timedelta(days=30),
        subtotal=subtotal,
        tax_rate=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        total=total,
        notes=notes,
        product_line=product_line,
        template_id=template_id,
        permit_number=permit_number,
        permit_jurisdiction=permit_jurisdiction,
        installation_address=installation_address,
        installation_city=installation_city,
        installation_state=installation_state,
        contact_name=contact_name,
        contact_phone=contact_phone,
        delivery_charge=Decimal(str(delivery_charge)) if delivery_charge else None,
        deceased_name=deceased_name,
        created_by=user_id,
        created_at=now,
    )

    db.add(quote)
    for ql in quote_lines:
        ql.quote_id = quote.id
        db.add(ql)

    db.flush()

    # --- Cemetery ---
    if cemetery_id:
        from app.models.cemetery import Cemetery
        cem = db.query(Cemetery).filter(
            Cemetery.id == cemetery_id,
            Cemetery.company_id == tenant_id,
        ).first()
        if cem:
            quote.cemetery_id = cem.id
            quote.cemetery_name = cem.name
            # Record funeral home → cemetery usage history
            if customer_id:
                try:
                    from app.services import cemetery_service
                    cemetery_service.record_funeral_home_cemetery_usage(
                        db, tenant_id, customer_id, cemetery_id
                    )
                except Exception:
                    pass  # Non-critical

    # --- Tax ---
    if cemetery_id or customer_id:
        try:
            from app.services.tax_service import get_jurisdiction_for_order, compute_tax
            from app.models.customer import Customer as CustomerModel
            jur, rate_obj = get_jurisdiction_for_order(db, tenant_id, cemetery_id, customer_id)
            if jur and rate_obj:
                cust = db.query(CustomerModel).filter(CustomerModel.id == customer_id).first() if customer_id else None
                tax_exempt = bool(cust and cust.tax_exempt) if cust else False
                tax_amount, effective_rate = compute_tax(quote.subtotal, rate_obj.rate_percentage, tax_exempt)
                quote.tax_amount = tax_amount
                quote.tax_rate = effective_rate
                quote.total = quote.subtotal + tax_amount + (quote.delivery_charge or Decimal("0.00"))
        except Exception as exc:
            logger.warning("Tax calculation failed: %s", exc)

    # --- Funeral home preferences (placer auto-add) ---
    if customer_id:
        try:
            from app.services.funeral_home_preference_service import apply_placer_to_quote_lines
            from app.models.quote import QuoteLine as QuoteLineModel
            # Reload lines after flush so the list is current
            db.refresh(quote)
            apply_placer_to_quote_lines(db, tenant_id, customer_id, quote, QuoteLineModel)
        except Exception as exc:
            logger.warning("Placer auto-add failed for quote: %s", exc)

    db.commit()
    db.refresh(quote)

    audit_service.log(
        db,
        company_id=tenant_id,
        user_id=user_id,
        action="create",
        entity_type="quote",
        entity_id=quote.id,
        details={"number": quote_number, "product_line": product_line},
    )

    return _quote_to_dict(quote)


def convert_quote_to_order(
    db: Session, tenant_id: str, user_id: str, quote_id: str
) -> dict:
    """Convert an existing quote to a sales order."""
    quote = _get_quote_or_404(db, tenant_id, quote_id)

    if quote.status == "converted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quote has already been converted to an order",
        )

    now = datetime.now(timezone.utc)
    order_number = _next_order_number(db, tenant_id)

    order = SalesOrder(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        number=order_number,
        customer_id=quote.customer_id,
        quote_id=quote.id,
        status="confirmed",
        order_date=now,
        subtotal=quote.subtotal,
        tax_rate=quote.tax_rate,
        tax_amount=quote.tax_amount,
        total=quote.total,
        notes=quote.notes,
        ship_to_name=quote.contact_name or quote.customer_name,
        ship_to_address=quote.installation_address,
        deceased_name=getattr(quote, "deceased_name", None),
        created_by=user_id,
        created_at=now,
    )
    db.add(order)

    # Copy lines (preserve auto-add tracking from quote)
    for ql in quote.lines or []:
        order_line = SalesOrderLine(
            id=str(uuid.uuid4()),
            sales_order_id=order.id,
            product_id=ql.product_id,
            description=ql.description,
            quantity=ql.quantity,
            unit_price=ql.unit_price,
            line_total=ql.line_total,
            sort_order=ql.sort_order,
            is_auto_added=getattr(ql, "is_auto_added", False),
            auto_add_reason=getattr(ql, "auto_add_reason", None),
        )
        db.add(order_line)

    # Update quote status
    quote.status = "converted"
    quote.converted_to_order_id = order.id
    quote.modified_by = user_id
    quote.modified_at = now

    db.commit()
    db.refresh(order)

    audit_service.log(
        db,
        company_id=tenant_id,
        user_id=user_id,
        action="convert",
        entity_type="quote",
        entity_id=quote.id,
        details={"order_id": order.id, "order_number": order_number},
    )

    return {
        "id": order.id,
        "order_number": order.number,
        "customer_name": quote.customer_name,
        "total": float(order.total),
        "status": order.status,
        "created_at": order.created_at,
    }


def list_pending_quotes(
    db: Session, tenant_id: str, *, days: int = 14
) -> list[dict]:
    """List quotes not yet converted or declined, within the given timeframe."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    quotes = (
        db.query(Quote)
        .options(joinedload(Quote.lines))
        .filter(
            Quote.company_id == tenant_id,
            Quote.status.in_(["draft", "sent"]),
            Quote.created_at >= cutoff,
        )
        .order_by(Quote.created_at.desc())
        .all()
    )
    return [_quote_to_dict(q) for q in quotes]


def get_quote(db: Session, tenant_id: str, quote_id: str) -> dict:
    """Get a single quote by ID."""
    quote = _get_quote_or_404(db, tenant_id, quote_id)
    return _quote_to_dict(quote)


def update_quote_status(
    db: Session, tenant_id: str, user_id: str, quote_id: str, new_status: str
) -> dict:
    """Update quote status (sent, declined, expired)."""
    valid_statuses = {"sent", "declined", "expired"}
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
        )

    quote = _get_quote_or_404(db, tenant_id, quote_id)

    if quote.status == "converted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change status of a converted quote",
        )

    now = datetime.now(timezone.utc)
    old_status = quote.status
    quote.status = new_status
    quote.modified_by = user_id
    quote.modified_at = now

    db.commit()
    db.refresh(quote)

    audit_service.log(
        db,
        company_id=tenant_id,
        user_id=user_id,
        action="update_status",
        entity_type="quote",
        entity_id=quote.id,
        details={"old_status": old_status, "new_status": new_status},
    )

    return _quote_to_dict(quote)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_quote_or_404(db: Session, tenant_id: str, quote_id: str) -> Quote:
    quote = (
        db.query(Quote)
        .options(joinedload(Quote.lines))
        .filter(Quote.id == quote_id, Quote.company_id == tenant_id)
        .first()
    )
    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quote not found",
        )
    return quote


def _quote_to_dict(q: Quote) -> dict:
    """Convert a Quote ORM instance to a plain dict."""
    return {
        "id": q.id,
        "quote_number": q.number,
        "customer_name": q.customer_name,
        "customer_id": q.customer_id,
        "product_line": q.product_line,
        "status": q.status,
        "subtotal": float(q.subtotal),
        "total": float(q.total),
        "permit_number": q.permit_number,
        "permit_jurisdiction": q.permit_jurisdiction,
        "installation_address": q.installation_address,
        "installation_city": q.installation_city,
        "installation_state": q.installation_state,
        "contact_name": q.contact_name,
        "contact_phone": q.contact_phone,
        "delivery_charge": float(q.delivery_charge) if q.delivery_charge else None,
        "notes": q.notes,
        "created_at": q.created_at,
        "expiry_date": q.expiry_date,
        "cemetery_id": q.cemetery_id if hasattr(q, "cemetery_id") else None,
        "cemetery_name": q.cemetery_name if hasattr(q, "cemetery_name") else None,
        "lines": [
            {
                "id": ln.id,
                "description": ln.description,
                "quantity": float(ln.quantity),
                "unit_price": float(ln.unit_price),
                "line_total": float(ln.line_total),
            }
            for ln in (q.lines or [])
        ],
    }
