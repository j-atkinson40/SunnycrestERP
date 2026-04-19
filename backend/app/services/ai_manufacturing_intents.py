"""
Manufacturing-specific AI intent parsing.

Provides a single system prompt and parser for the AI command bar
to handle natural-language manufacturing commands such as:
  - log production
  - check inventory
  - create order
  - record payment
  - log training
  - log incident
"""

import logging
from datetime import date


logger = logging.getLogger(__name__)

_MANUFACTURING_COMMAND_PROMPT = """\
You are a manufacturing ERP assistant for a precast-concrete / vault production company.
Your job is to classify the user's natural-language command into exactly ONE intent
and extract structured data.

Today's date: {today}

INTENTS (pick exactly one):

1. log_production
   Triggers: "we made", "we poured", "produced today", "made this morning", "finished [qty] [product]"
   Extract: product names and quantities.
   Return:
   {{
     "intent": "log_production",
     "entries": [{{"product_name": "Standard Vault", "quantity": 6}}, ...],
     "message": "Ready to log 6 Standard Vaults and 4 Grave Boxes"
   }}

2. check_inventory
   Triggers: "how many", "do we have", "inventory", "stock", "in stock"
   Extract: product name.
   Return:
   {{
     "intent": "check_inventory",
     "product_name": "<matched product name>",
     "product_id": "<id from catalog or null>",
     "message": "Looking up inventory for <product>..."
   }}

3. create_order
   Triggers: customer name + product mention, "order", "to [customer]", "for [customer]"
   Extract: customer name, products, quantities, delivery date hints.
   Return:
   {{
     "intent": "create_order",
     "customer": "Johnson Funeral Home",
     "items": [{{"product_name": "Standard Vault", "quantity": 2}}],
     "delivery_date_hint": "Friday" or null,
     "message": "Draft order: 2 Standard Vaults to Johnson Funeral Home"
   }}

4. record_payment
   Triggers: "paid", "received payment", "check from", "payment from"
   Extract: customer name, optional amount, optional invoice reference.
   Return:
   {{
     "intent": "record_payment",
     "customer": "...",
     "amount": 1500.00 or null,
     "invoice_reference": "INV-1042" or null,
     "payment_method": "check" or "cash" or "ach" or null,
     "message": "Record payment from <customer>..."
   }}

5. log_training
   Triggers: "did training", "safety training", "trained the crew", "completed certification"
   Extract: training topic, employee names or "whole crew".
   Return:
   {{
     "intent": "log_training",
     "topic": "Forklift Safety",
     "employees": ["John", "Mike"] or ["whole_crew"],
     "date": "{today}",
     "message": "Log forklift safety training for the whole crew"
   }}

6. log_incident
   Triggers: "incident", "accident", "injury", "near miss", "slipped", "hurt"
   Extract: employee name, description, severity hint.
   Return:
   {{
     "intent": "log_incident",
     "employee": "Mike",
     "description": "Slipped on wet concrete near pour area",
     "severity_hint": "first_aid" or "near_miss" or "medical" or "serious",
     "message": "We've started an incident report. Please review before submitting."
   }}

CONTEXT DATA you will receive:
- product_catalog: list of {{id, name, sku}}
- customer_catalog: list of {{id, name}}
- employee_names: list of employee first names

RULES:
- Always return exactly one JSON object with an "intent" field.
- Match products / customers by fuzzy name against the catalogs provided.
- If the command doesn't match any intent, return:
  {{"intent": "unknown", "message": "I'm not sure what you'd like to do. Try something like: 'we made 6 standard vaults today'"}}
- confidence field is optional but encouraged: "high", "medium", or "low".
"""


def parse_manufacturing_command(
    user_input: str,
    product_catalog: list[dict] | None = None,
    customer_catalog: list[dict] | None = None,
    employee_names: list[str] | None = None,
    *,
    db=None,
    company_id: str | None = None,
) -> dict:
    """
    Parse a natural-language manufacturing command into a structured intent.

    Phase 2c-4 migration: routes through the managed
    `commandbar.classify_manufacturing_intent` prompt. Catalogs are bundled
    into a single context_data_json variable the seed's user_template expects.
    """
    import json as _json

    from app.services.intelligence import intelligence_service

    if db is None:
        from app.database import SessionLocal
        local_db = SessionLocal()
        try:
            return parse_manufacturing_command(
                user_input,
                product_catalog,
                customer_catalog,
                employee_names,
                db=local_db,
                company_id=company_id,
            )
        finally:
            local_db.close()

    context: dict = {}
    if product_catalog:
        context["product_catalog"] = product_catalog
    if customer_catalog:
        context["customer_catalog"] = customer_catalog
    if employee_names:
        context["employee_names"] = employee_names

    today = date.today().isoformat()
    result = intelligence_service.execute(
        db,
        prompt_key="commandbar.classify_manufacturing_intent",
        variables={
            "today": today,
            "user_input": user_input,
            "context_data_json": _json.dumps(context) if context else "",
        },
        company_id=company_id,
        caller_module="ai_manufacturing_intents.parse_manufacturing_command",
        caller_entity_type=None,
    )
    if result.status == "success" and isinstance(result.response_parsed, dict):
        return result.response_parsed
    # Fallback mirrors the legacy "unknown intent" shape
    return {"intent": "unknown", "message": result.error_message or "Classification failed."}
