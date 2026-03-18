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

from app.services.ai_service import call_anthropic

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
) -> dict:
    """
    Parse a natural-language manufacturing command into a structured intent.

    Args:
        user_input: The user's free-text command.
        product_catalog: List of dicts with keys: id, name, sku.
        customer_catalog: List of dicts with keys: id, name.
        employee_names: List of employee first names.

    Returns:
        Parsed intent dict.
    """
    today = date.today().isoformat()
    system_prompt = _MANUFACTURING_COMMAND_PROMPT.format(today=today)

    context: dict = {}
    if product_catalog:
        context["product_catalog"] = product_catalog
    if customer_catalog:
        context["customer_catalog"] = customer_catalog
    if employee_names:
        context["employee_names"] = employee_names

    return call_anthropic(
        system_prompt=system_prompt,
        user_message=user_input,
        context_data=context if context else None,
    )
