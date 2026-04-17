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


# ─────────────────────────────────────────────────────────────────────
# PDF rendering — used by the Compose slide-over review mode and the
# "Send to customer" action. Lazy-imports WeasyPrint so environments
# without the C deps don't break on service import.
# ─────────────────────────────────────────────────────────────────────


_PDF_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body{font-family:'Helvetica Neue',Arial,sans-serif;font-size:12px;color:#1a1a1a;margin:0;padding:40px;}
.header{display:flex;justify-content:space-between;margin-bottom:40px;border-bottom:2px solid #1a1a1a;padding-bottom:20px;}
.company-name{font-size:22px;font-weight:700;letter-spacing:-.5px;}
.quote-label{font-size:28px;font-weight:300;color:#666;text-align:right;}
.quote-number{font-size:13px;color:#666;text-align:right;margin-top:4px;}
.details{display:flex;gap:60px;margin-bottom:36px;}
.detail-block label{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.8px;color:#888;display:block;margin-bottom:4px;}
.detail-block p{margin:0;font-size:13px;font-weight:500;}
table{width:100%;border-collapse:collapse;margin-bottom:24px;}
th{background:#f5f5f5;padding:10px 12px;text-align:left;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.6px;color:#666;}
td{padding:12px;border-bottom:1px solid #f0f0f0;font-size:13px;}
td.right{text-align:right;}
.total-row td{font-weight:700;font-size:14px;border-bottom:none;border-top:2px solid #1a1a1a;}
.footer{margin-top:40px;padding-top:20px;border-top:1px solid #eee;font-size:11px;color:#888;}
.expiry-note{background:#fffbeb;border:1px solid #fde68a;border-radius:6px;padding:10px 14px;margin-bottom:24px;font-size:12px;color:#92400e;}
</style></head><body>
<div class="header"><div><div class="company-name">{company_name}</div></div>
<div><div class="quote-label">QUOTE</div><div class="quote-number">#{quote_number}</div><div class="quote-number">{quote_date}</div></div></div>
<div class="details">
{customer_block}
<div class="detail-block"><label>Prepared by</label><p>{company_name}</p></div>
{expiry_block}
</div>
{expiry_note}
<table><thead><tr><th>Description</th><th style="text-align:right">Qty</th><th style="text-align:right">Unit Price</th><th style="text-align:right">Total</th></tr></thead><tbody>
{line_rows}
{total_row}
</tbody></table>
{notes_block}
<div class="footer"><p>Thank you for your business. To accept this quote, please reply or contact us directly.</p>
<p style="margin-top:8px;">{company_name}</p></div>
</body></html>"""


def _money(v) -> str:
    try:
        return f"${float(v):,.2f}"
    except (TypeError, ValueError):
        return "—"


def generate_quote_pdf(db: Session, tenant_id: str, quote_id: str) -> bytes:
    """Render a quote as a PDF via WeasyPrint. Raises ValueError if the
    quote doesn't belong to this tenant, RuntimeError if WeasyPrint isn't
    available in the environment."""
    try:
        from weasyprint import HTML  # type: ignore
    except Exception as e:  # pragma: no cover — missing system dep
        raise RuntimeError(f"WeasyPrint unavailable: {e}")

    from app.models.company import Company  # local import to avoid cycles

    quote = _get_quote_or_404(db, tenant_id, quote_id)
    company = db.query(Company).filter(Company.id == tenant_id).first()
    lines = sorted(quote.lines or [], key=lambda ln: ln.sort_order or 0)

    company_name = (company.name if company else "Bridgeable") or "Bridgeable"
    quote_number = quote.number or quote.id[:8].upper()
    quote_date_str = (
        quote.quote_date.strftime("%B %-d, %Y") if quote.quote_date else ""
    )

    customer_block = (
        f'<div class="detail-block"><label>Prepared for</label>'
        f"<p>{quote.customer_name}</p></div>"
        if quote.customer_name
        else ""
    )

    expiry_block = ""
    expiry_note = ""
    if quote.expiry_date:
        expiry_str = quote.expiry_date.strftime("%B %-d, %Y")
        expiry_block = (
            '<div class="detail-block"><label>Valid until</label>'
            f"<p>{expiry_str}</p></div>"
        )
        expiry_note = (
            '<div class="expiry-note">This quote is valid until '
            f"{expiry_str}. Prices subject to change after expiry.</div>"
        )

    line_rows = "".join(
        (
            f"<tr><td>{ln.description or ''}</td>"
            f'<td class="right">{float(ln.quantity or 0):g}</td>'
            f'<td class="right">{_money(ln.unit_price)}</td>'
            f'<td class="right">{_money(ln.line_total)}</td></tr>'
        )
        for ln in lines
    ) or (
        '<tr><td colspan="4" style="color:#999;text-align:center;">'
        "No line items.</td></tr>"
    )
    total_row = (
        '<tr class="total-row"><td colspan="3">Total</td>'
        f'<td class="right">{_money(quote.total)}</td></tr>'
        if quote.total
        else ""
    )
    notes_block = (
        '<div style="margin-bottom:24px;"><div style="font-size:10px;'
        "font-weight:600;text-transform:uppercase;color:#888;"
        'letter-spacing:.6px;margin-bottom:6px;">Notes</div>'
        f'<div style="font-size:13px;">{quote.notes}</div></div>'
        if quote.notes
        else ""
    )

    html = _PDF_TEMPLATE.format(
        company_name=company_name,
        quote_number=quote_number,
        quote_date=quote_date_str,
        customer_block=customer_block,
        expiry_block=expiry_block,
        expiry_note=expiry_note,
        line_rows=line_rows,
        total_row=total_row,
        notes_block=notes_block,
    )
    return HTML(string=html).write_pdf()
