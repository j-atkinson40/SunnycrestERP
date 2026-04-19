"""Core command service — NLP command processing with Claude API + fallback."""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_action import UserAction

logger = logging.getLogger(__name__)


# The system prompt formerly defined here lives in the managed
# `commandbar.classify_intent` prompt (Phase 2c-3 migration). See
# backend/scripts/update_commandbar_classify_intent.py for the verbatim content
# and variable schema.


def process_command(
    db: Session,
    raw_input: str,
    user: User,
    context: dict,
) -> dict:
    """Process a command bar input. Tries Claude API, falls back to local search."""
    # Pre-resolve entities
    resolved = _resolve_entities(db, raw_input, user.company_id)

    # Try Claude API
    try:
        result = _call_claude(db, raw_input, resolved, context, user)
        if result and result.get("results"):
            # Assign shortcut numbers
            for i, r in enumerate(result["results"][:5]):
                r["shortcut"] = i + 1
            return result
    except Exception as e:
        logger.warning(f"Claude command API failed, falling back to search: {e}")

    # Fallback to local search
    return _local_search(db, raw_input, user.company_id)


def _resolve_entities(db: Session, raw_input: str, company_id: str) -> dict:
    """Pre-resolve entity references from input text."""
    resolved = {"companies": [], "orders": [], "products": []}
    input_lower = raw_input.lower()

    # Search company entities
    try:
        from app.models.company_entity import CompanyEntity
        companies = (
            db.query(CompanyEntity)
            .filter(
                CompanyEntity.company_id == company_id,
                func.lower(CompanyEntity.name).contains(input_lower.split()[-1] if input_lower.split() else "")
            )
            .limit(5)
            .all()
        )
        resolved["companies"] = [
            {"id": c.id, "name": c.name, "type": getattr(c, "customer_type", None)}
            for c in companies
        ]
    except Exception:
        pass

    # Search orders
    try:
        from app.models.sales_order import SalesOrder
        orders = (
            db.query(SalesOrder)
            .filter(
                SalesOrder.company_id == company_id,
                or_(
                    SalesOrder.order_number.ilike(f"%{raw_input}%"),
                )
            )
            .limit(5)
            .all()
        )
        resolved["orders"] = [
            {"id": o.id, "order_number": o.order_number, "status": o.status}
            for o in orders
        ]
    except Exception:
        pass

    # Search products
    try:
        from app.models.product import Product
        products = (
            db.query(Product)
            .filter(
                Product.company_id == company_id,
                or_(
                    Product.name.ilike(f"%{raw_input}%"),
                    Product.sku.ilike(f"%{raw_input}%"),
                )
            )
            .limit(5)
            .all()
        )
        resolved["products"] = [
            {"id": p.id, "name": p.name, "sku": getattr(p, "sku", None)}
            for p in products
        ]
    except Exception:
        pass

    return resolved


def _call_claude(
    db: Session, raw_input: str, resolved: dict, context: dict, user: User
) -> Optional[dict]:
    """Classify the command via the managed `commandbar.classify_intent` prompt.

    Phase 2c-3 migration — prompt content now lives in the Intelligence layer.
    On failure (API down, parse error, etc.), returns None so the caller falls
    through to the local_search Postgres path.
    """
    prompt_data = {
        "input": raw_input,
        "resolved_entities": resolved,
        "user_context": context,
        "instruction": "Return JSON only. No preamble.",
    }

    try:
        from app.services.intelligence import intelligence_service

        result = intelligence_service.execute(
            db,
            prompt_key="commandbar.classify_intent",
            variables={"payload": json.dumps(prompt_data)},
            company_id=user.company_id,
            caller_module="core_command_service.process_command",
            caller_entity_type=None,  # universal classifier — no single entity
            caller_entity_id=None,
        )
        if result.status == "success":
            # force_json=true → response_parsed is the dict we want
            if isinstance(result.response_parsed, dict):
                return result.response_parsed
            # Defensive fallback: some models occasionally return valid JSON text
            # without us parsing; try one more json.loads.
            if isinstance(result.response_text, str) and result.response_text.strip():
                return json.loads(result.response_text)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Claude command parse error: {e}")

    return None


def _local_search(db: Session, raw_input: str, company_id: str) -> dict:
    """Fallback local search against vault items, companies, orders, products."""
    results = []
    pattern = f"%{raw_input}%"

    # Search vault items
    try:
        from app.models.vault_item import VaultItem
        vault_items = (
            db.query(VaultItem)
            .filter(
                VaultItem.company_id == company_id,
                or_(
                    VaultItem.title.ilike(pattern),
                    VaultItem.description.ilike(pattern),
                ),
                VaultItem.status == "active",
            )
            .order_by(VaultItem.created_at.desc())
            .limit(3)
            .all()
        )
        for item in vault_items:
            results.append({
                "id": f"vault_{item.id}",
                "type": "RECORD",
                "icon": _vault_icon(item.item_type),
                "title": item.title,
                "subtitle": f"{item.item_type} · {item.created_at.strftime('%b %d') if item.created_at else ''}",
                "action": {"type": "navigate", "route": f"/vault/items/{item.id}"},
                "confidence": 0.5,
            })
    except Exception:
        pass

    # Search company entities
    try:
        from app.models.company_entity import CompanyEntity
        companies = (
            db.query(CompanyEntity)
            .filter(
                CompanyEntity.company_id == company_id,
                CompanyEntity.name.ilike(pattern),
            )
            .limit(3)
            .all()
        )
        for c in companies:
            results.append({
                "id": f"company_{c.id}",
                "type": "RECORD",
                "icon": "building",
                "title": c.name,
                "subtitle": getattr(c, "customer_type", "") or "Company",
                "action": {"type": "navigate", "route": f"/crm/companies/{c.id}"},
                "confidence": 0.6,
            })
    except Exception:
        pass

    # Search orders
    try:
        from app.models.sales_order import SalesOrder
        from app.models.customer import Customer
        orders = (
            db.query(SalesOrder)
            .outerjoin(Customer, SalesOrder.customer_id == Customer.id)
            .filter(
                SalesOrder.company_id == company_id,
                or_(
                    SalesOrder.order_number.ilike(pattern),
                    Customer.name.ilike(pattern),
                ),
            )
            .limit(3)
            .all()
        )
        for o in orders:
            results.append({
                "id": f"order_{o.id}",
                "type": "RECORD",
                "icon": "package",
                "title": f"Order {o.order_number}",
                "subtitle": f"{o.status or 'unknown'}",
                "action": {"type": "navigate", "route": f"/orders/{o.id}"},
                "confidence": 0.55,
            })
    except Exception:
        pass

    # Sort by confidence, assign shortcuts
    results.sort(key=lambda r: r["confidence"], reverse=True)
    for i, r in enumerate(results[:5]):
        r["shortcut"] = i + 1

    return {
        "results": results[:5],
        "intent": "search",
        "raw_input": raw_input,
        "needs_confirmation": False,
        "search_only": True,
    }


def _vault_icon(item_type: str) -> str:
    """Map vault item type to icon."""
    icons = {
        "event": "calendar",
        "document": "file-text",
        "communication": "message-square",
        "reminder": "bell",
        "asset": "box",
        "compliance": "shield",
        "production": "layers",
    }
    return icons.get(item_type, "file")


def log_action(
    db: Session,
    user_id: str,
    company_id: str,
    action_id: str,
    raw_input: str,
    result_title: str,
    result_type: str,
    action_data: dict,
    input_method: str = "keyboard",
) -> UserAction:
    """Log a command bar action to the database."""
    action = UserAction(
        id=str(uuid.uuid4()),
        user_id=user_id,
        company_id=company_id,
        action_id=action_id,
        raw_input=raw_input,
        result_title=result_title,
        result_type=result_type,
        action_data=action_data,
        input_method=input_method,
    )
    db.add(action)
    db.commit()
    return action


def get_recent_actions(db: Session, user_id: str, limit: int = 10) -> list[dict]:
    """Get the user's most recent command bar actions."""
    actions = (
        db.query(UserAction)
        .filter(
            UserAction.user_id == user_id,
            UserAction.is_active == True,
        )
        .order_by(UserAction.executed_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": a.action_id,
            "title": a.result_title,
            "type": a.result_type,
            "action": a.action_data,
            "input_method": a.input_method,
            "timestamp": a.executed_at.isoformat() if a.executed_at else None,
        }
        for a in actions
    ]
