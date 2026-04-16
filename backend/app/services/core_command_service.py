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


# --- Claude system prompt ---
COMMAND_SYSTEM_PROMPT = """You are the intent classification engine for Bridgeable — a physical economy operating platform for the death care industry. Parse natural language input from users (precast manufacturers, funeral home directors, cemetery managers) and return structured JSON.

Current user context will be provided. Resolve entity references against the provided data. Return confidence scores.

ALWAYS return valid JSON matching the schema below. NEVER return markdown, explanation, or preamble — only the JSON object.

Response schema:
{
  "results": [
    {
      "id": "string",
      "type": "ACTION" | "VIEW" | "RECORD" | "NAV" | "ASK",
      "icon": "string (lucide icon name)",
      "title": "string",
      "subtitle": "string",
      "shortcut": 1-5,
      "action": {
        "type": "navigate" | "navigate_with_prefill" | "open_timeline" | "execute_action" | "vault_query" | "open_modal",
        "route": "string",
        "prefill": {}
      },
      "confidence": 0.0-1.0
    }
  ],
  "intent": "string",
  "needs_confirmation": false
}

Available intents: search, create_order, schedule_delivery, log_production, view_compliance, create_reminder, find_record, navigate, log_pour, log_strip, create_employee, find_employee, view_briefing, call_customer, create_invoice, run_statements, view_ar_aging, view_ap_aging, view_revenue_report, create_disinterment, view_disinterments, log_incident, run_audit_prep, view_safety, view_training, view_ss_certificates, settings_programs, settings_locations, settings_team, settings_product_lines, settings_tax, settings_email, view_invoices, view_bills, view_purchase_orders, view_products, view_knowledge_base, view_team, create_urn_order, view_urns, view_transfers, view_spring_burials, view_calls, view_agents

Known navigable routes (use the canonical path when intent=navigate):
  /dashboard /orders /orders/new /scheduling /scheduling/new
  /crm /crm/companies /crm/funeral-homes /crm/pipeline
  /compliance /compliance/disinterments /compliance/disinterments/new
  /ar/invoices /ar/invoices/review /ar/aging /ar/payments /ar/quotes /ar/statements
  /ap/bills /ap/aging /ap/payments /ap/purchase-orders
  /products /products/urns /urns/catalog /urns/orders /urns/orders/new
  /safety /safety/programs /safety/incidents /safety/incidents/new
  /safety/training /safety/osha-300 /safety/toolbox-talks
  /social-service-certificates /spring-burials /transfers /calls /agents /team
  /reports /knowledge-base
  /settings/programs /settings/locations /settings/product-lines
  /settings/tax /settings/invoice /settings/call-intelligence
  /settings/compliance
  /production /production/pour-events/new /production-log
"""


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
        result = _call_claude(raw_input, resolved, context, user)
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


def _call_claude(raw_input: str, resolved: dict, context: dict, user: User) -> Optional[dict]:
    """Call Claude API for intent classification with 800ms timeout."""
    try:
        from app.services.ai_service import call_anthropic
    except ImportError:
        return None

    prompt_data = {
        "input": raw_input,
        "resolved_entities": resolved,
        "user_context": context,
        "instruction": "Return JSON only. No preamble."
    }

    try:
        response = call_anthropic(
            system_prompt=COMMAND_SYSTEM_PROMPT,
            user_message=json.dumps(prompt_data),
            max_tokens=1000,
        )
        if response:
            # Parse JSON from response
            parsed = json.loads(response) if isinstance(response, str) else response
            return parsed
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
