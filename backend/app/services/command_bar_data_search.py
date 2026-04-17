"""Command-bar data search — intent classification, live record search,
and pattern-based question answering from platform data.

Entry point: answer_or_search(db, query, company_id) returns a dict
with keys `answer`, `records`, `intent`, `answered`.

Scope: pricing-for-product and generic record search (products,
contacts, orders). Inventory / contact-info / compliance patterns are
stubbed — adding them is mechanical once the schema hooks are known.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.company_entity import CompanyEntity
from app.models.product import Product
from app.models import PriceListItem, PriceListVersion

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Intent classification
# ─────────────────────────────────────────────────────────────────────

class QueryIntent:
    QUESTION = "question"
    SEARCH = "search"
    ACTION = "action"
    NAVIGATE = "navigate"


_QUESTION_STARTERS = [
    "what is our ", "what's our ", "what are our ",
    "what is the ", "what's the ",
    "what is ", "what's ", "whats ",
    "how much is ", "how much does ", "how much for ",
    "how many ", "how do ",
    "where is ", "where are ", "where's ",
    "who is ", "who's ",
    "when is ", "when's ", "when does ",
    "which ", "why ",
    "can i ", "do we ", "does ", "is there ",
    "show me ", "tell me ", "find me ", "look up ",
    "price for ", "price of ",
    "cost of ", "cost for ",
]

_ACTION_STARTERS = {"create", "new", "add", "start", "schedule", "send",
                    "run", "generate", "log"}
_NAV_PREFIXES = ("go to ", "open ", "navigate ", "view ")


def classify_query(query: str) -> str:
    q = (query or "").lower().strip()
    if not q:
        return QueryIntent.SEARCH
    for starter in _QUESTION_STARTERS:
        if q.startswith(starter):
            return QueryIntent.QUESTION
    first = q.split()[0]
    if first in _ACTION_STARTERS:
        return QueryIntent.ACTION
    for p in _NAV_PREFIXES:
        if q.startswith(p):
            return QueryIntent.NAVIGATE
    return QueryIntent.SEARCH


# ─────────────────────────────────────────────────────────────────────
# Search-term extraction — strip question phrasing
# ─────────────────────────────────────────────────────────────────────

_STRIP_PREFIXES = [
    # Longest first so "what is our price for a " wins over "what is "
    "what is our price for a ", "what is our price for ",
    "what is the price of a ", "what is the price of ",
    "what's our price for a ", "what's our price for ",
    "what is our ", "what's our ",
    "price for a ", "price for ", "price of a ", "price of ",
    "how much is a ", "how much is ", "how much for a ", "how much for ",
    "cost of a ", "cost of ", "cost for a ", "cost for ",
    "show me ", "find me ", "look up ", "tell me about ",
    "what is the ", "what's the ",
    "what is ", "what's ", "whats ",
    "where is ", "who is ", "when is ",
    "search for ",
]


def extract_search_term(query: str) -> str:
    q = (query or "").lower().strip()
    for pre in sorted(_STRIP_PREFIXES, key=len, reverse=True):
        if q.startswith(pre):
            q = q[len(pre):]
            break
    q = q.rstrip("?.,!")
    q = re.sub(r"^(a |an |the )", "", q)
    return q.strip()


# ─────────────────────────────────────────────────────────────────────
# Live record search
# ─────────────────────────────────────────────────────────────────────

def _format_price(value: float | int | None) -> str | None:
    if value is None:
        return None
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return None


def _active_price_version_id(db: Session, company_id: str) -> str | None:
    """Return the active PriceListVersion id for the tenant, or None.
    Prefers `status == 'active'`; falls back to most-recently activated."""
    row = (
        db.query(PriceListVersion.id)
        .filter(
            PriceListVersion.tenant_id == company_id,
            PriceListVersion.status == "active",
        )
        .order_by(PriceListVersion.activated_at.desc())
        .first()
    )
    if row:
        return row[0]
    # Fallback: most recent version regardless of status
    row = (
        db.query(PriceListVersion.id)
        .filter(PriceListVersion.tenant_id == company_id)
        .order_by(PriceListVersion.activated_at.desc().nullslast())
        .first()
    )
    return row[0] if row else None


def _tiered_price_for_product(
    db: Session, product: Product, company_id: str
) -> dict[str, float | None]:
    """Look up {standard, contractor, homeowner, source} for a Product
    using the active PriceListVersion; falls back to Product.price.

    Matches PriceListItem by product_code == product.sku first, then by
    product_name == product.name. Returns a dict so the caller can format
    however it wants.
    """
    result: dict[str, float | None] = {
        "standard": None,
        "contractor": None,
        "homeowner": None,
        "source": None,
    }

    version_id = _active_price_version_id(db, company_id)
    item = None
    if version_id:
        q = db.query(PriceListItem).filter(
            PriceListItem.tenant_id == company_id,
            PriceListItem.version_id == version_id,
            PriceListItem.is_active == True,  # noqa: E712
        )
        if product.sku:
            item = q.filter(PriceListItem.product_code == product.sku).first()
        if not item and product.name:
            item = q.filter(PriceListItem.product_name == product.name).first()

    if item is not None:
        result["standard"] = float(item.standard_price) if item.standard_price is not None else None
        result["contractor"] = float(item.contractor_price) if item.contractor_price is not None else None
        result["homeowner"] = float(item.homeowner_price) if item.homeowner_price is not None else None
        result["source"] = "price_list"
        return result

    if product.price is not None:
        result["standard"] = float(product.price)
        result["source"] = "product"
    return result


def _format_tiered_price_line(name: str, tiers: dict[str, float | None]) -> str:
    """Build "{name}: $X · Contractor $Y · Homeowner $Z" when tiers exist,
    or fall back to just the standard price."""
    std = _format_price(tiers["standard"])
    c = _format_price(tiers["contractor"])
    h = _format_price(tiers["homeowner"])
    if not std and not c and not h:
        return f"{name}: price not set"
    parts = [std] if std else []
    if c:
        parts.append(f"Contractor {c}")
    if h:
        parts.append(f"Homeowner {h}")
    return f"{name}: " + " · ".join(parts)


def search_products(
    db: Session, query: str, company_id: str, limit: int = 5
) -> list[dict]:
    if not query:
        return []
    pattern = f"%{query}%"
    products = (
        db.query(Product)
        .filter(
            Product.company_id == company_id,
            Product.is_active == True,  # noqa: E712
            or_(Product.name.ilike(pattern), Product.sku.ilike(pattern)),
        )
        .order_by(Product.name.asc())
        .limit(limit)
        .all()
    )
    out = []
    for p in products:
        tiers = _tiered_price_for_product(db, p, company_id)
        # Subtitle prefers active-price-list standard; falls back to Product.price
        price_str = _format_price(tiers["standard"])
        parts: list[str] = []
        if price_str:
            parts.append(price_str)
        if p.sku:
            parts.append(p.sku)
        out.append({
            "result_type": "record",
            "record_type": "product",
            "id": f"product:{p.id}",
            "record_id": p.id,
            "title": p.name,
            "subtitle": " · ".join(parts) or "Product",
            "price": tiers["standard"],
            "price_source": tiers["source"],
            "icon": "package",
            "route": "/products",
        })
    return out


def search_contacts(
    db: Session, query: str, company_id: str, limit: int = 3
) -> list[dict]:
    if not query:
        return []
    pattern = f"%{query}%"
    rows = (
        db.query(CompanyEntity)
        .filter(
            CompanyEntity.company_id == company_id,
            CompanyEntity.name.ilike(pattern),
        )
        .order_by(CompanyEntity.name.asc())
        .limit(limit)
        .all()
    )
    out = []
    for c in rows:
        flags = []
        if c.is_customer:
            flags.append("Customer")
        if c.is_vendor:
            flags.append("Vendor")
        subtitle_parts = []
        if flags:
            subtitle_parts.append(" / ".join(flags))
        if c.city and c.state:
            subtitle_parts.append(f"{c.city}, {c.state}")
        out.append({
            "result_type": "record",
            "record_type": "contact",
            "id": f"contact:{c.id}",
            "record_id": c.id,
            "title": c.name,
            "subtitle": " · ".join(subtitle_parts) or "Contact",
            "icon": "users",
            "route": f"/crm/companies/{c.id}",
        })
    return out


# Optional order search (guarded — sales_orders model name may differ)
def search_orders(db: Session, query: str, company_id: str, limit: int = 3) -> list[dict]:
    try:
        from app.models.sales_order import SalesOrder  # type: ignore
    except Exception:
        return []
    if not query:
        return []
    pattern = f"%{query}%"
    try:
        # Try common column names without assuming schema
        rows = (
            db.query(SalesOrder)
            .filter(
                SalesOrder.company_id == company_id,
                or_(
                    getattr(SalesOrder, "order_number", SalesOrder.id).ilike(pattern),
                    getattr(SalesOrder, "customer_name", SalesOrder.id).ilike(pattern),
                ),
            )
            .order_by(getattr(SalesOrder, "created_at").desc())
            .limit(limit)
            .all()
        )
    except Exception:
        return []
    out = []
    for o in rows:
        num = getattr(o, "order_number", o.id)
        customer = getattr(o, "customer_name", None) or ""
        out.append({
            "result_type": "record",
            "record_type": "order",
            "id": f"order:{o.id}",
            "record_id": o.id,
            "title": f"Order {num}",
            "subtitle": customer or "Order",
            "icon": "clipboard-list",
            "route": f"/orders/{o.id}",
        })
    return out


# ─────────────────────────────────────────────────────────────────────
# Pattern-based answer engine
# ─────────────────────────────────────────────────────────────────────

_PRICE_PATTERNS = [
    r"price (?:for|of) (?:a |an |the )?(.+)",
    r"how much (?:is|for|does) (?:a |an |the )?(.+?)(?: cost)?$",
    r"cost (?:for|of) (?:a |an |the )?(.+)",
    r"what(?:'s| is) (?:our |the )?price (?:for|of) (?:a |an |the )?(.+)",
]

_INVENTORY_PATTERNS = [
    r"how many (.+?) do we have",
    r"inventory (?:for|of) (.+)",
    r"stock (?:for|of) (.+)",
    r"how much (.+?) (?:in stock|on hand)",
]

_CONTACT_INFO_PATTERNS = {
    "phone": [
        r"(?:phone|phone number|number|call) (?:for|of) (.+)",
        r"what(?:'s| is) (?:the )?(?:phone|phone number|number) (?:for|of) (.+)",
    ],
    "email": [
        r"(?:email|email address) (?:for|of) (.+)",
        r"what(?:'s| is) (?:the )?email (?:for|of) (.+)",
    ],
    "address": [
        r"(?:address|where is) (.+)",
        r"where(?:'s| is) (.+) located",
    ],
}

_RECENT_ORDER_PATTERNS = [
    r"(?:last|latest|most recent) order (?:from|for) (.+)",
    r"(?:last|most recent) order (?:by )?(.+)",
]


def _try_answer_price(
    db: Session, query: str, company_id: str
) -> dict | None:
    q = query.lower().strip().rstrip("?.,!")
    product_name: str | None = None
    for pat in _PRICE_PATTERNS:
        m = re.search(pat, q)
        if m:
            product_name = m.group(1).strip()
            break
    if not product_name:
        return None

    pattern = f"%{product_name}%"
    products = (
        db.query(Product)
        .filter(
            Product.company_id == company_id,
            Product.is_active == True,  # noqa: E712
            Product.name.ilike(pattern),
        )
        .order_by(Product.name.asc())
        .limit(4)
        .all()
    )
    if not products:
        return None

    lines: list[str] = []
    used_price_list = False
    for p in products:
        tiers = _tiered_price_for_product(db, p, company_id)
        if tiers["source"] == "price_list":
            used_price_list = True
        lines.append(_format_tiered_price_line(p.name, tiers))

    return {
        "result_type": "answer",
        "id": f"answer:price:{product_name}",
        "icon": "💡",
        "headline": " · ".join(lines),
        "source_title": "Price list",
        "source_section": None,
        "source_label": (
            "From your active price list" if used_price_list else "From product catalog"
        ),
        "route": "/pricing" if used_price_list else "/products",
        "related_record_ids": [p.id for p in products],
    }


def _try_answer_inventory(
    db: Session, query: str, company_id: str
) -> dict | None:
    q = query.lower().strip().rstrip("?.,!")
    product_name: str | None = None
    for pat in _INVENTORY_PATTERNS:
        m = re.search(pat, q)
        if m:
            product_name = m.group(1).strip()
            break
    if not product_name:
        return None

    # Try InventoryItem model — may not exist in all environments
    try:
        from app.models.inventory import InventoryItem  # type: ignore
    except Exception:
        return None

    pattern = f"%{product_name}%"
    products = (
        db.query(Product)
        .filter(
            Product.company_id == company_id,
            Product.is_active == True,  # noqa: E712
            Product.name.ilike(pattern),
        )
        .order_by(Product.name.asc())
        .limit(4)
        .all()
    )
    if not products:
        return None

    lines: list[str] = []
    for p in products:
        try:
            item = (
                db.query(InventoryItem)
                .filter(
                    InventoryItem.company_id == company_id,
                    InventoryItem.product_id == p.id,
                )
                .first()
            )
            qty = getattr(item, "quantity_on_hand", None) if item else None
        except Exception:
            qty = None
        if qty is not None:
            lines.append(f"{p.name}: {qty} in stock")
        else:
            lines.append(f"{p.name}: inventory not tracked")

    return {
        "result_type": "answer",
        "id": f"answer:inventory:{product_name}",
        "icon": "💡",
        "headline": " · ".join(lines),
        "source_title": "Inventory",
        "source_section": None,
        "source_label": "Current inventory",
        "route": "/inventory",
        "related_record_ids": [p.id for p in products],
    }


def _try_answer_contact_info(
    db: Session, query: str, company_id: str
) -> dict | None:
    """Answer 'phone/email/address for {company}' questions."""
    q = query.lower().strip().rstrip("?.,!")
    field: str | None = None
    contact_name: str | None = None
    for fname, patterns in _CONTACT_INFO_PATTERNS.items():
        for pat in patterns:
            m = re.search(pat, q)
            if m:
                field = fname
                contact_name = m.group(1).strip()
                break
        if field:
            break
    if not contact_name:
        return None

    contact = (
        db.query(CompanyEntity)
        .filter(
            CompanyEntity.company_id == company_id,
            CompanyEntity.name.ilike(f"%{contact_name}%"),
        )
        .order_by(CompanyEntity.name.asc())
        .first()
    )
    if not contact:
        return None

    if field == "phone":
        value = contact.phone or "No phone on file"
        headline = f"{contact.name}: {value}"
        label = "From CRM contact"
    elif field == "email":
        value = contact.email or "No email on file"
        headline = f"{contact.name}: {value}"
        label = "From CRM contact"
    else:  # address
        parts = [contact.address_line1, contact.address_line2, contact.city, contact.state, contact.zip]
        addr = ", ".join([p for p in parts if p])
        headline = f"{contact.name}: {addr}" if addr else f"{contact.name}: no address on file"
        label = "From CRM contact"

    return {
        "result_type": "answer",
        "id": f"answer:contact:{field}:{contact.id}",
        "icon": "💡",
        "headline": headline,
        "source_title": "CRM",
        "source_section": None,
        "source_label": label,
        "route": f"/crm/companies/{contact.id}",
        "related_record_ids": [contact.id],
    }


def _try_answer_recent_order(
    db: Session, query: str, company_id: str
) -> dict | None:
    """Answer 'last order from {company}' questions."""
    q = query.lower().strip().rstrip("?.,!")
    customer_name: str | None = None
    for pat in _RECENT_ORDER_PATTERNS:
        m = re.search(pat, q)
        if m:
            customer_name = m.group(1).strip()
            break
    if not customer_name:
        return None

    try:
        from app.models.sales_order import SalesOrder  # type: ignore
    except Exception:
        return None

    # Find candidate customers by name
    customer = (
        db.query(CompanyEntity)
        .filter(
            CompanyEntity.company_id == company_id,
            CompanyEntity.name.ilike(f"%{customer_name}%"),
        )
        .order_by(CompanyEntity.name.asc())
        .first()
    )
    if not customer:
        return None

    try:
        order = (
            db.query(SalesOrder)
            .filter(
                SalesOrder.company_id == company_id,
                SalesOrder.customer_id == customer.id,
            )
            .order_by(SalesOrder.order_date.desc().nullslast())
            .first()
        )
    except Exception:
        return None

    if not order:
        return {
            "result_type": "answer",
            "id": f"answer:recent_order:{customer.id}",
            "icon": "💡",
            "headline": f"{customer.name}: no orders on file",
            "source_title": "Orders",
            "source_section": None,
            "source_label": "From sales orders",
            "route": f"/crm/companies/{customer.id}",
            "related_record_ids": [customer.id],
        }

    date_str = order.order_date.strftime("%b %-d, %Y") if order.order_date else "unknown date"
    total_str = _format_price(float(order.total)) if getattr(order, "total", None) is not None else None
    num = getattr(order, "number", None) or order.id
    status = getattr(order, "status", None) or ""
    bits = [f"Order {num}", date_str]
    if total_str:
        bits.append(total_str)
    if status:
        bits.append(status)
    headline = f"{customer.name} · " + " · ".join(bits)

    return {
        "result_type": "answer",
        "id": f"answer:recent_order:{order.id}",
        "icon": "💡",
        "headline": headline,
        "source_title": "Orders",
        "source_section": None,
        "source_label": "Most recent sales order",
        "route": f"/orders/{order.id}",
        "related_record_ids": [order.id],
    }


def try_answer(db: Session, query: str, company_id: str) -> dict | None:
    """Attempt to answer a question from platform data. Runs handlers in
    priority order. Returns None if nothing matches."""
    handlers = (
        _try_answer_price,
        _try_answer_inventory,
        _try_answer_recent_order,
        _try_answer_contact_info,
    )
    for fn in handlers:
        try:
            ans = fn(db, query, company_id)
        except Exception as e:  # pragma: no cover — defensive
            logger.debug("Answer engine error in %s: %s", fn.__name__, e)
            ans = None
        if ans:
            return ans
    return None


# ─────────────────────────────────────────────────────────────────────
# Top-level orchestrator
# ─────────────────────────────────────────────────────────────────────

def answer_or_search(
    db: Session, query: str, company_id: str
) -> dict[str, Any]:
    """Full command-bar data search.

    Returns:
        {
          intent: str,
          answered: bool,
          answer: dict | None,
          records: list[dict],
        }
    """
    q = (query or "").strip()
    if not q:
        return {"intent": "empty", "answered": False, "answer": None, "records": []}

    intent = classify_query(q)
    term = extract_search_term(q)

    # Run the pattern-based answer engine on QUESTION *and* SEARCH intents.
    # Many implicit lookups don't start with a question word — e.g.
    # "phone number for Hopkins" or "last order from Murphy" classify
    # as SEARCH but still have clean patterns. try_answer returns None
    # when nothing matches, so it's cheap to always run.
    answer = None
    if intent in (QueryIntent.QUESTION, QueryIntent.SEARCH):
        answer = try_answer(db, q, company_id)

    # Always search live records when we have a meaningful search term
    records: list[dict] = []
    if term and len(term) >= 2:
        records.extend(search_products(db, term, company_id, limit=5))
        records.extend(search_contacts(db, term, company_id, limit=3))
        records.extend(search_orders(db, term, company_id, limit=3))

    return {
        "intent": intent,
        "answered": bool(answer),
        "answer": answer,
        "records": records[:8],
    }
