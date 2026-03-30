"""Order Entry Station routes — templates, quotes, activity feed, voice parsing."""

import json
import re
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_module
from app.database import get_db
from app.models.quick_quote_template import QuickQuoteTemplate
from app.models.quote import Quote
from app.models.sales_order import SalesOrder
from app.models.user import User
from app.schemas.order_station import (
    CreateQuoteRequest,
    OrderStationActivityResponse,
    QuickQuoteTemplateResponse,
    QuoteResponse,
    UpdateQuoteStatusRequest,
)
from app.services import quote_service
from app.services import cemetery_service
from app.services import template_season_service

router = APIRouter()

# ---------------------------------------------------------------------------
# Voice-to-order parsing — system prompt for Claude
# ---------------------------------------------------------------------------

_PARSE_ORDER_SYSTEM_PROMPT = """You are parsing a natural language funeral order entry for a burial vault manufacturer.

Extract these fields from the input:
{
  "vault_product": string or null,
  "equipment": string or null,
  "cemetery_name": string or null,
  "service_date": string or null,
  "confidence": float
}

vault_product — match to known vault names (use exact casing):
Monticello, Venetian, Continental, Salute, Tribute, Monarch, Graveliner,
Graveliner SS, Bronze Triune, Copper Triune, SST Triune, Cameo Rose,
Veteran Triune, Wilbert Bronze, Loved & Cherished 19", Loved & Cherished 24",
Loved & Cherished 31", Continental 34, Graveliner 34, Graveliner 38, Pine Box,
Urn Vault (append line name if specified, e.g. "Urn Vault Monticello")

equipment — one of: full_equipment, lowering_device_grass, lowering_device_only, tent_only, no_equipment, null

cemetery_name — extract and expand shorthand:
  "Oak Hill" → "Oak Hill Cemetery", "St Mary's" → "St. Mary's Cemetery",
  "Lakeview" → "Lakeview Cemetery". If already a full name, return as-is.

service_date — always YYYY-MM-DD. Resolve relative dates using today's date:
  "tomorrow" → tomorrow, "Thursday" → next Thursday,
  "March 31" → current or next year's March 31.
  Current date: {today}

confidence — 0.0 to 1.0, how confident you are in the overall parse.

Return JSON only, no markdown. If a field cannot be determined, return null."""


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


@router.get("/templates", response_model=list[QuickQuoteTemplateResponse])
def list_templates(
    product_line: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all quick-order / quick-quote templates for the tenant.

    Returns system templates (tenant_id IS NULL) and tenant-specific
    templates, filtered by product_line if provided.
    """
    query = db.query(QuickQuoteTemplate).filter(
        QuickQuoteTemplate.is_active.is_(True),
        (
            (QuickQuoteTemplate.tenant_id == current_user.company_id)
            | (QuickQuoteTemplate.tenant_id.is_(None))
        ),
    )

    if product_line:
        query = query.filter(QuickQuoteTemplate.product_line == product_line)

    templates = query.order_by(
        QuickQuoteTemplate.sort_order, QuickQuoteTemplate.display_label
    ).all()

    # Seasonal filtering
    active_season = template_season_service.get_active_season(db, current_user.company_id)
    if active_season:
        season_ids = set(active_season.active_template_ids or [])
        templates = [t for t in templates if not t.seasonal_only or t.id in season_ids]
    else:
        templates = [t for t in templates if not t.seasonal_only]

    results = []
    for t in templates:
        results.append(
            QuickQuoteTemplateResponse(
                id=t.id,
                template_name=t.template_name,
                display_label=t.display_label,
                display_description=t.display_description,
                icon=t.icon,
                product_line=t.product_line,
                sort_order=t.sort_order,
                is_active=t.is_active,
                is_system_template=t.is_system_template,
                line_items=t.line_items_parsed,
                variable_fields=t.variable_fields_parsed,
                slide_over_width=t.slide_over_width,
                primary_action=t.primary_action,
                quote_template_key=t.quote_template_key,
                seasonal_only=t.seasonal_only,
            )
        )
    return results


# ---------------------------------------------------------------------------
# Activity feed
# ---------------------------------------------------------------------------


@router.get("/activity", response_model=OrderStationActivityResponse)
def order_station_activity(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Activity feed: today's orders, pending quotes, recent orders, flags."""
    tenant_id = current_user.company_id
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Today's orders
    todays_orders_q = (
        db.query(SalesOrder)
        .filter(
            SalesOrder.company_id == tenant_id,
            SalesOrder.created_at >= today_start,
        )
        .order_by(SalesOrder.created_at.desc())
        .limit(50)
        .all()
    )
    todays_orders = [
        {
            "id": o.id,
            "number": o.number,
            "customer_name": o.ship_to_name or (o.customer.name if o.customer else ""),
            "total": float(o.total),
            "status": o.status,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }
        for o in todays_orders_q
    ]

    # Pending quotes (last 14 days)
    cutoff = now - timedelta(days=14)
    pending_quotes_q = (
        db.query(Quote)
        .filter(
            Quote.company_id == tenant_id,
            Quote.status.in_(["draft", "sent"]),
            Quote.created_at >= cutoff,
        )
        .order_by(Quote.created_at.desc())
        .limit(50)
        .all()
    )
    pending_quotes = [
        {
            "id": q.id,
            "number": q.number,
            "customer_name": q.customer_name or (q.customer.name if q.customer else ""),
            "total": float(q.total),
            "status": q.status,
            "product_line": q.product_line,
            "created_at": q.created_at.isoformat() if q.created_at else None,
        }
        for q in pending_quotes_q
    ]

    # Recent orders (last 7 days)
    recent_cutoff = now - timedelta(days=7)
    recent_orders_q = (
        db.query(SalesOrder)
        .filter(
            SalesOrder.company_id == tenant_id,
            SalesOrder.created_at >= recent_cutoff,
        )
        .order_by(SalesOrder.created_at.desc())
        .limit(20)
        .all()
    )
    recent_orders = [
        {
            "id": o.id,
            "number": o.number,
            "customer_name": o.ship_to_name or (o.customer.name if o.customer else ""),
            "total": float(o.total),
            "status": o.status,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }
        for o in recent_orders_q
    ]

    # Spring burial count
    spring_burial_count = (
        db.query(func.count(SalesOrder.id))
        .filter(
            SalesOrder.company_id == tenant_id,
            SalesOrder.is_spring_burial.is_(True),
            SalesOrder.status.notin_(["canceled", "completed"]),
        )
        .scalar()
        or 0
    )

    # Pending quote aggregates
    pending_quote_count = len(pending_quotes)
    pending_quote_value = sum(q["total"] for q in pending_quotes)

    # Flags — quotes expiring within 3 days
    expiry_cutoff = now + timedelta(days=3)
    expiring_quotes = (
        db.query(Quote)
        .filter(
            Quote.company_id == tenant_id,
            Quote.status.in_(["draft", "sent"]),
            Quote.expiry_date.isnot(None),
            Quote.expiry_date <= expiry_cutoff,
            Quote.expiry_date >= now,
        )
        .all()
    )
    flags = [
        {
            "type": "quote_expiring",
            "message": f"Quote {q.number} expires on {q.expiry_date.strftime('%m/%d') if q.expiry_date else 'N/A'}",
            "entity_id": q.id,
            "entity_type": "quote",
        }
        for q in expiring_quotes
    ]

    return OrderStationActivityResponse(
        todays_orders=todays_orders,
        pending_quotes=pending_quotes,
        recent_orders=recent_orders,
        spring_burial_count=spring_burial_count,
        pending_quote_count=pending_quote_count,
        pending_quote_value=pending_quote_value,
        flags=flags,
    )


# ---------------------------------------------------------------------------
# Quotes
# ---------------------------------------------------------------------------


@router.post("/quotes", response_model=QuoteResponse, status_code=201)
def create_quote(
    data: CreateQuoteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a quote from the order station slide-over."""
    result = quote_service.create_quote(
        db,
        current_user.company_id,
        current_user.id,
        customer_name=data.customer_name,
        customer_id=data.customer_id,
        product_line=data.product_line,
        line_items=data.line_items,
        template_id=data.template_id,
        permit_number=data.permit_number,
        permit_jurisdiction=data.permit_jurisdiction,
        installation_address=data.installation_address,
        installation_city=data.installation_city,
        installation_state=data.installation_state,
        contact_name=data.contact_name,
        contact_phone=data.contact_phone,
        notes=data.notes,
        delivery_charge=data.delivery_charge,
    )
    return QuoteResponse(
        id=result["id"],
        quote_number=result["quote_number"],
        customer_name=result["customer_name"],
        product_line=result["product_line"],
        total=result["total"],
        status=result["status"],
        created_at=result["created_at"],
    )


@router.get("/quotes", response_model=list[QuoteResponse])
def list_quotes(
    days: int = Query(14, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List pending quotes for the order station."""
    results = quote_service.list_pending_quotes(
        db, current_user.company_id, days=days
    )
    return [
        QuoteResponse(
            id=r["id"],
            quote_number=r["quote_number"],
            customer_name=r["customer_name"],
            product_line=r["product_line"],
            total=r["total"],
            status=r["status"],
            created_at=r["created_at"],
        )
        for r in results
    ]


@router.get("/quotes/{quote_id}")
def get_quote(
    quote_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single quote with full details."""
    return quote_service.get_quote(db, current_user.company_id, quote_id)


@router.post("/quotes/{quote_id}/convert")
def convert_quote(
    quote_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Convert a quote to a sales order."""
    return quote_service.convert_quote_to_order(
        db, current_user.company_id, current_user.id, quote_id
    )


@router.post("/record-cemetery-history")
def record_cemetery_history(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record that a funeral home used a cemetery on an order."""
    customer_id = data.get("customer_id")
    cemetery_id = data.get("cemetery_id")
    order_date_str = data.get("order_date")

    if not customer_id or not cemetery_id:
        return {"detail": "customer_id and cemetery_id required"}

    from datetime import date
    order_date = None
    if order_date_str:
        try:
            order_date = date.fromisoformat(order_date_str)
        except ValueError:
            pass

    cemetery_service.record_funeral_home_cemetery_usage(
        db,
        company_id=current_user.company_id,
        customer_id=customer_id,
        cemetery_id=cemetery_id,
        order_date=order_date,
    )
    return {"detail": "recorded"}


@router.patch("/quotes/{quote_id}")
def update_quote_status(
    quote_id: str,
    data: UpdateQuoteStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update quote status (send, decline, expire)."""
    return quote_service.update_quote_status(
        db, current_user.company_id, current_user.id, quote_id, data.status
    )


# ---------------------------------------------------------------------------
# Voice-to-order parsing
# ---------------------------------------------------------------------------


@router.post("/parse-order")
def parse_order(
    data: dict,
    current_user: User = Depends(get_current_user),
):
    """Parse a natural language funeral order entry via Claude API.

    Returns structured fields: vault_product, equipment, cemetery_name,
    service_date, confidence (0-1).
    """
    import anthropic

    from app.config import settings

    input_text = (data.get("input") or "").strip()
    if not input_text:
        return {"vault_product": None, "equipment": None, "cemetery_name": None, "service_date": None, "confidence": 0.0}

    if not settings.ANTHROPIC_API_KEY:
        return {"error": "AI not configured", "confidence": 0.0}

    today_str = date.today().isoformat()
    system_prompt = _PARSE_ORDER_SYSTEM_PROMPT.replace("{today}", today_str)

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system=system_prompt,
            messages=[{"role": "user", "content": input_text}],
        )
        text = message.content[0].text.strip()
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        return json.loads(text)
    except json.JSONDecodeError as exc:
        return {"error": f"Parse error: {exc}", "confidence": 0.0}
    except Exception as exc:
        return {"error": str(exc), "confidence": 0.0}


# ---------------------------------------------------------------------------
# Template season active check
# ---------------------------------------------------------------------------


@router.get("/active-season")
def get_active_season(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the currently active season for today's date, or null."""
    season = template_season_service.get_active_season(db, current_user.company_id)
    if not season:
        return None
    from app.services.template_season_service import _to_dict
    return _to_dict(season)
