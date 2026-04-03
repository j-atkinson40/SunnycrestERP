"""Order Entry Station routes — templates, quotes, activity feed, voice parsing."""

import json
import re
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Query
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
# Personalization task spawning helper
# ---------------------------------------------------------------------------

def _spawn_personalization_tasks(
    db: Session,
    company_id: str,
    order: SalesOrder,
    fields: dict,
    background_tasks: BackgroundTasks,
) -> None:
    """Parse _pers_* fields from the order station form and create
    OrderPersonalizationTask records.  For legacy tasks, enqueue
    background proof generation."""
    import uuid as _uuid

    from app.models.order_personalization_task import OrderPersonalizationTask
    from app.services.legacy_service import generate_legacy_proof_async
    from app.services.personalization_config import LEGACY_PRINT_IMAGE_URLS

    pers_types = [t.strip() for t in (fields.get("_pers_types") or "").split(",") if t.strip()]
    if not pers_types:
        return

    pers_name = fields.get("_pers_name") or ""
    pers_dates = fields.get("_pers_dates") or ""
    pers_additional = fields.get("_pers_additional") or ""
    pers_symbol = fields.get("_pers_symbol") or ""
    pers_legacy_type = fields.get("_pers_legacy_type") or "standard"
    pers_print_name = fields.get("_pers_print_name") or ""
    pers_custom_desc = fields.get("_pers_custom_desc") or ""

    # Determine is_urn from order line items (check product personalization_tier)
    is_urn = False
    for line in (order.lines or []):
        product = line.product
        if product and getattr(product, "personalization_tier", None) == "urn_vault":
            is_urn = True
            break

    for ptype in pers_types:
        # Map frontend type to task_type
        if ptype == "legacy_print":
            task_type = "legacy_custom" if pers_legacy_type == "custom" else "legacy_standard"
        elif ptype == "lifes_reflections":
            task_type = "lifes_reflections"
        elif ptype == "nameplate":
            task_type = "nameplate"
        elif ptype == "cover_emblem":
            task_type = "cover_emblem"
        else:
            continue

        task = OrderPersonalizationTask(
            id=str(_uuid.uuid4()),
            company_id=company_id,
            order_id=order.id,
            task_type=task_type,
            inscription_name=pers_name or None,
            inscription_dates=pers_dates or None,
            inscription_additional=pers_additional or None,
            print_name=pers_print_name or None,
            print_image_url=LEGACY_PRINT_IMAGE_URLS.get(pers_print_name) if pers_print_name else None,
            symbol=pers_symbol or None,
            is_custom_legacy=(pers_legacy_type == "custom"),
            status="pending",
            notes=pers_custom_desc if (task_type in ("legacy_custom",) and pers_custom_desc) else None,
        )
        db.add(task)
        db.flush()

        # Enqueue background proof generation for legacy tasks
        if task_type in ("legacy_standard", "legacy_custom"):
            background_tasks.add_task(
                generate_legacy_proof_async,
                task_id=task.id,
                order_id=order.id,
                print_name=pers_print_name,
                is_urn=is_urn,
                name=pers_name or None,
                dates=pers_dates or None,
                additional=pers_additional or None,
            )

    db.commit()

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
    from app.utils.company_name_resolver import resolve_customer_name, resolve_cemetery_name
    todays_orders = [
        {
            "id": o.id,
            "number": o.number,
            "customer_name": o.ship_to_name or resolve_customer_name(o.customer),
            "cemetery_name": resolve_cemetery_name(o.cemetery) if o.cemetery_id else None,
            "cemetery_id": o.cemetery_id,
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

    # Recent funeral homes — last 10 distinct FHs that had funeral orders
    from app.models.customer import Customer

    recent_fh_subq = (
        db.query(SalesOrder.customer_id)
        .filter(
            SalesOrder.company_id == tenant_id,
            SalesOrder.order_type == "funeral",
            SalesOrder.customer_id.isnot(None),
        )
        .order_by(SalesOrder.created_at.desc())
        .limit(50)
        .subquery()
    )
    recent_fh_ids = db.query(recent_fh_subq.c.customer_id).distinct().limit(10).all()
    recent_fh_ids = [r[0] for r in recent_fh_ids]

    recent_funeral_homes = []
    if recent_fh_ids:
        customers = (
            db.query(Customer)
            .filter(Customer.id.in_(recent_fh_ids))
            .all()
        )
        id_to_cust = {c.id: c for c in customers}
        # Preserve order from query
        for fh_id in recent_fh_ids:
            c = id_to_cust.get(fh_id)
            if c:
                recent_funeral_homes.append({"id": c.id, "name": c.name})

    return OrderStationActivityResponse(
        todays_orders=todays_orders,
        pending_quotes=pending_quotes,
        recent_orders=recent_orders,
        recent_funeral_homes=recent_funeral_homes,
        spring_burial_count=spring_burial_count,
        pending_quote_count=pending_quote_count,
        pending_quote_value=pending_quote_value,
        flags=flags,
    )


# ---------------------------------------------------------------------------
# Quotes
# ---------------------------------------------------------------------------


@router.get("/cemetery-tax-preview")
def cemetery_tax_preview(
    cemetery_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get tax rate preview for a cemetery — used in order station UI."""
    from app.services.tax_service import get_tax_preview
    return get_tax_preview(db, current_user.company_id, cemetery_id)


@router.post("/quotes", response_model=QuoteResponse, status_code=201)
def create_quote(
    data: CreateQuoteRequest,
    background_tasks: BackgroundTasks,
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
        cemetery_id=data.cemetery_id,
        cemetery_name=data.cemetery_name,
        deceased_name=data.deceased_name,
    )

    # For mode="order", auto-convert to SalesOrder and apply service fields
    if data.mode == "order" and result.get("id"):
        try:
            from datetime import time as _time

            order_result = quote_service.convert_quote_to_order(
                db, current_user.company_id, current_user.id, result["id"]
            )
            # Apply service fields to the new SalesOrder
            order = db.query(SalesOrder).filter(SalesOrder.id == order_result["id"]).first()
            if order:
                if data.service_location:
                    order.service_location = data.service_location
                if data.service_location_other:
                    order.service_location_other = data.service_location_other
                if data.service_time:
                    try:
                        parts = data.service_time.split(":")
                        order.service_time = _time(int(parts[0]), int(parts[1]))
                    except (ValueError, IndexError):
                        pass
                if data.eta:
                    try:
                        parts = data.eta.split(":")
                        order.eta = _time(int(parts[0]), int(parts[1]))
                    except (ValueError, IndexError):
                        pass
                db.commit()

                # Spawn personalization tasks if _pers_* fields present
                if data.fields and data.fields.get("_pers_types"):
                    try:
                        _spawn_personalization_tasks(
                            db, current_user.company_id, order, data.fields, background_tasks,
                        )
                    except Exception:
                        pass  # Non-fatal — order still created

                # Log CRM activity
                try:
                    from app.services.crm.activity_log_service import log_system_event
                    log_system_event(
                        db, current_user.company_id, None,
                        activity_type="order",
                        title=f"Order #{order_result.get('order_number', '')} created — {data.customer_name}",
                        related_order_id=order_result["id"],
                        customer_id=order.customer_id if order else None,
                    )
                    db.commit()
                except Exception:
                    pass
        except Exception:
            pass  # Quote was created; conversion failure is not fatal

    return QuoteResponse(
        id=result["id"],
        quote_number=result["quote_number"],
        customer_name=result["customer_name"],
        product_line=result["product_line"],
        total=result["total"],
        status=result["status"],
        created_at=result["created_at"],
        cemetery_id=result.get("cemetery_id"),
        cemetery_name=result.get("cemetery_name"),
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
