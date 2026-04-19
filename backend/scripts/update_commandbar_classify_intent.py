"""Phase 2c-3 — update commandbar.classify_intent from placeholder → verbatim.

Phase 1 seeded this prompt with placeholder content. Phase 2c-3 swaps in the
verbatim system prompt + user template from core_command_service._call_claude,
which is the primary caller.

Idempotent: safe to re-run.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models.intelligence import IntelligencePrompt, IntelligencePromptVersion


# Verbatim from app/services/core_command_service.py:COMMAND_SYSTEM_PROMPT
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

# The caller sends a JSON-serialized payload with input, resolved_entities,
# user_context, and instruction. The managed prompt renders this payload via
# three variables so future callers can reuse the same prompt with different
# resolver implementations.
COMMAND_USER_TEMPLATE = """{{ payload }}"""


VARIABLE_SCHEMA = {
    "payload": {
        "type": "string",
        "required": True,
        "description": (
            "JSON-serialized object with keys: input, resolved_entities, user_context, "
            "instruction. Caller assembles this payload before invoke."
        ),
    },
}


RESPONSE_SCHEMA = {"required": ["results", "intent"]}


def apply_update() -> None:
    db = SessionLocal()
    try:
        prompt = (
            db.query(IntelligencePrompt)
            .filter(
                IntelligencePrompt.company_id.is_(None),
                IntelligencePrompt.prompt_key == "commandbar.classify_intent",
            )
            .first()
        )
        if prompt is None:
            print("  SKIP: commandbar.classify_intent prompt not found")
            return

        version = (
            db.query(IntelligencePromptVersion)
            .filter(
                IntelligencePromptVersion.prompt_id == prompt.id,
                IntelligencePromptVersion.status == "active",
            )
            .first()
        )
        if version is None:
            print("  SKIP: no active version")
            return

        version.system_prompt = COMMAND_SYSTEM_PROMPT
        version.user_template = COMMAND_USER_TEMPLATE
        version.variable_schema = VARIABLE_SCHEMA
        version.response_schema = RESPONSE_SCHEMA
        version.model_preference = "simple"
        version.temperature = 0.2
        version.max_tokens = 1000
        version.force_json = True
        version.changelog = (
            "Phase 2c-3 — swapped placeholder for verbatim content from "
            "core_command_service.COMMAND_SYSTEM_PROMPT. Caller migration in "
            "same build routes core_command_service._call_claude through this "
            "prompt."
        )
        version.activated_at = datetime.now(timezone.utc)

        db.commit()
        print(f"  Updated commandbar.classify_intent (version id={version.id})")
    finally:
        db.close()


if __name__ == "__main__":
    apply_update()
