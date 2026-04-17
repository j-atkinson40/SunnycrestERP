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
        price_str = _format_price(p.price)
        parts = [price_str] if price_str else []
        if p.sku:
            parts.append(p.sku)
        out.append({
            "result_type": "record",
            "record_type": "product",
            "id": f"product:{p.id}",
            "record_id": p.id,
            "title": p.name,
            "subtitle": " · ".join(parts) or "Product",
            "price": float(p.price) if p.price is not None else None,
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
    for p in products:
        ps = _format_price(p.price)
        lines.append(f"{p.name}: {ps}" if ps else f"{p.name}: price not set")

    return {
        "result_type": "answer",
        "id": f"answer:price:{product_name}",
        "icon": "💡",
        "headline": " · ".join(lines),
        "source_title": "Price list",
        "source_section": None,
        "source_label": "From your active price list",
        "route": "/products",
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


def try_answer(db: Session, query: str, company_id: str) -> dict | None:
    """Attempt to answer a question from platform data.
    Runs price then inventory patterns. Returns None if nothing matches."""
    for fn in (_try_answer_price, _try_answer_inventory):
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

    answer = None
    if intent == QueryIntent.QUESTION:
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
