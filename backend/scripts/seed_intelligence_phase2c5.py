"""Phase 2c-5 — final cleanup seeds.

Adds three prompts that unblock deletion of ai_service.py:

1. extraction.inventory_command   (parse-inventory route)
2. extraction.ap_command          (parse-ap route)
3. legacy.arbitrary_prompt        (/ai/prompt deprecation endpoint backing)

After this seed runs and the three routes migrate, `ai_service.py` has zero
callers in production code and can be deleted outright.

Idempotent — safe to re-run.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models.intelligence import IntelligencePrompt, IntelligencePromptVersion


# Verbatim from ai_service._INVENTORY_SYSTEM_PROMPT
INVENTORY_SYSTEM_PROMPT = """You are an inventory management assistant for a food production company.
Your job is to parse natural-language inventory commands into structured JSON.

You will receive:
1. A user command (e.g. "Add 500 units of SKU-1042 to bin 4B")
2. A product catalog with id, name, and sku for each product

Return a JSON object with these fields:
{
  "action": one of "receive", "production", "write_off", "adjust",
  "product_id": the matched product's id (string) or null if unmatched,
  "product_name": the matched product's name or the name from user input,
  "product_sku": the matched product's SKU or the SKU from user input,
  "quantity": integer quantity parsed from the command (null if unclear),
  "location": storage location if mentioned (string or null),
  "reference": reference number if mentioned (string or null),
  "reason": reason for write-off if applicable (string or null),
  "notes": any additional notes (string or null),
  "confidence": "high", "medium", or "low",
  "ambiguous": true if the command is unclear or could be interpreted multiple ways,
  "clarification_message": a short message asking for clarification if ambiguous (null otherwise)
}

Rules:
- Match products by SKU first (exact or partial match), then by name (fuzzy).
- Keywords: "produce", "produced", "made", "manufacture" → action "production"
- Keywords: "receive", "received", "incoming", "delivery" → action "receive"
- Keywords: "write off", "writeoff", "damaged", "expired", "lost", "spoiled", "discard" → action "write_off"
- Keywords: "adjust", "set", "correct", "count" → action "adjust"
- If the user mentions adding/increasing stock without a specific keyword, default to "receive".
- For write_off, extract the reason from context (e.g. "damaged", "expired").
- If you cannot match a product from the catalog, set product_id to null and confidence to "low".
- If quantity is not specified, set it to null and set ambiguous to true.
- If the command mentions multiple products, return a JSON object with a "commands" array instead,
  where each element follows the same structure above.
"""

INVENTORY_USER_TEMPLATE = """{{ user_input }}

Context data:
{{ context_data_json }}"""


# Verbatim from ai_service._AP_SYSTEM_PROMPT
AP_SYSTEM_PROMPT = """You are an accounts payable assistant for a business ERP system.
Your job is to parse natural-language AP and purchasing commands into structured JSON.

You will receive:
1. A user command (e.g. "Create a PO to Acme Supply for 100 widgets at $5 each")
2. A vendor catalog with id and name for each active vendor

Return a JSON object with these fields:
{
  "intent": one of "create_po", "create_bill", "query_aging", "record_payment",
  "vendor_name": matched vendor name or the name from user input,
  "vendor_id": matched vendor's id (string) or null if unmatched,
  "items": array of line items [{description, quantity, unit_cost}] or null,
  "invoice_number": vendor invoice number if mentioned (string or null),
  "amount": total amount if mentioned (number or null),
  "payment_method": one of "check", "ach", "wire", "credit_card", "cash" or null,
  "reference_number": check number or reference if mentioned (string or null),
  "date": date if mentioned in ISO format (string or null),
  "notes": any additional notes (string or null),
  "confidence": "high", "medium", or "low",
  "ambiguous": true if the command is unclear,
  "clarification_message": a short message asking for clarification if ambiguous (null otherwise)
}

Rules:
- Match vendors by name (fuzzy match against the catalog).
- Keywords: "PO", "purchase order", "order from", "buy" → intent "create_po"
- Keywords: "bill", "invoice", "received bill" → intent "create_bill"
- Keywords: "aging", "outstanding", "overdue", "how much do we owe" → intent "query_aging"
- Keywords: "pay", "payment", "paid", "send check" → intent "record_payment"
- For create_po, extract line items (description, quantity, unit_cost) if mentioned.
- For create_bill, extract invoice_number and amount if mentioned.
- For record_payment, extract amount, payment_method, and reference_number if mentioned.
- If you cannot determine the intent, set confidence to "low" and ambiguous to true.
- If you cannot match a vendor, set vendor_id to null and confidence to "medium" at best.
"""

AP_USER_TEMPLATE = """{{ user_input }}

Context data:
{{ context_data_json }}"""


# legacy.arbitrary_prompt — the meta-prompt that backs the deprecated
# /ai/prompt endpoint. Callers supply the system_prompt verbatim as a
# variable; Jinja renders it unchanged. This keeps the one remaining
# frontend caller (AICommandBar on pages/products.tsx) working while every
# call now produces a managed-prompt audit row instead of a legacy shim row.
LEGACY_ARBITRARY_SYSTEM = "{{ system_prompt }}"
LEGACY_ARBITRARY_USER = (
    "{{ user_message }}"
    "{% if context_data_json %}\n\nContext data:\n{{ context_data_json }}{% endif %}"
)


SPECS: list[dict] = [
    {
        "prompt_key": "extraction.inventory_command",
        "domain": "extraction",
        "display_name": "Extraction — Parse inventory command",
        "description": "Natural-language inventory command → structured action JSON.",
        "system_prompt": INVENTORY_SYSTEM_PROMPT,
        "user_template": INVENTORY_USER_TEMPLATE,
        "variable_schema": {
            "user_input": {"type": "string", "required": True},
            "context_data_json": {
                "type": "string", "required": False,
                "description": "JSON dict with product_catalog list.",
            },
        },
        "response_schema": {"required": ["action"]},
        "model_preference": "extraction",
        "temperature": 0.2,
        "max_tokens": 1024,
        "force_json": True,
        "changelog": (
            "Phase 2c-5 — migrated from ai_service.parse_inventory_command. "
            "Enables deletion of ai_service.py."
        ),
    },
    {
        "prompt_key": "extraction.ap_command",
        "domain": "extraction",
        "display_name": "Extraction — Parse AP command",
        "description": "Natural-language AP/purchasing command → structured action JSON.",
        "system_prompt": AP_SYSTEM_PROMPT,
        "user_template": AP_USER_TEMPLATE,
        "variable_schema": {
            "user_input": {"type": "string", "required": True},
            "context_data_json": {
                "type": "string", "required": False,
                "description": "JSON dict with vendor_catalog list.",
            },
        },
        "response_schema": {"required": ["intent"]},
        "model_preference": "extraction",
        "temperature": 0.2,
        "max_tokens": 1024,
        "force_json": True,
        "changelog": (
            "Phase 2c-5 — migrated from ai_service.parse_ap_command. "
            "Enables deletion of ai_service.py."
        ),
    },
    {
        "prompt_key": "legacy.arbitrary_prompt",
        "domain": "general",
        "display_name": "Legacy — Arbitrary prompt (deprecated)",
        "description": (
            "Pass-through prompt that backs the deprecated /ai/prompt endpoint. "
            "The caller supplies system_prompt verbatim as a variable; this is "
            "intentionally a weak abstraction. New callers must not use this — "
            "create a dedicated managed prompt instead. Sunset: 2027-04-18."
        ),
        "system_prompt": LEGACY_ARBITRARY_SYSTEM,
        "user_template": LEGACY_ARBITRARY_USER,
        "variable_schema": {
            "system_prompt": {"type": "string", "required": True,
                              "description": "System prompt text supplied by the caller."},
            "user_message": {"type": "string", "required": True,
                             "description": "User message supplied by the caller."},
            "context_data_json": {
                "type": "string", "required": False,
                "description": "Optional JSON-serialized context dict appended to the user message.",
            },
        },
        "response_schema": None,  # callers pass arbitrary shapes
        "model_preference": "extraction",
        "temperature": 0.3,
        "max_tokens": 1024,
        "force_json": True,  # legacy call_anthropic enforced JSON-only; preserve behavior
        "changelog": (
            "Phase 2c-5 — created to back the deprecated /ai/prompt endpoint. "
            "New callers must not use this. Sunset 2027-04-18 along with the endpoint."
        ),
    },
]


def apply_seed() -> dict:
    db = SessionLocal()
    try:
        inserted_prompts = 0
        inserted_versions = 0
        touched = 0
        for spec in SPECS:
            prompt = (
                db.query(IntelligencePrompt)
                .filter(
                    IntelligencePrompt.company_id.is_(None),
                    IntelligencePrompt.prompt_key == spec["prompt_key"],
                )
                .first()
            )
            if prompt is None:
                prompt = IntelligencePrompt(
                    company_id=None,
                    prompt_key=spec["prompt_key"],
                    display_name=spec["display_name"],
                    description=spec.get("description"),
                    domain=spec["domain"],
                )
                db.add(prompt)
                db.flush()
                inserted_prompts += 1

            v1 = (
                db.query(IntelligencePromptVersion)
                .filter(
                    IntelligencePromptVersion.prompt_id == prompt.id,
                    IntelligencePromptVersion.version_number == 1,
                )
                .first()
            )
            if v1 is None:
                v1 = IntelligencePromptVersion(
                    prompt_id=prompt.id,
                    version_number=1,
                    status="active",
                    activated_at=datetime.now(timezone.utc),
                    system_prompt="",
                    user_template="",
                    model_preference=spec["model_preference"],
                )
                db.add(v1)
                db.flush()
                inserted_versions += 1

            v1.system_prompt = spec["system_prompt"]
            v1.user_template = spec["user_template"]
            v1.variable_schema = spec["variable_schema"]
            v1.response_schema = spec.get("response_schema")
            v1.model_preference = spec["model_preference"]
            v1.temperature = spec.get("temperature", 0.3)
            v1.max_tokens = spec.get("max_tokens", 4096)
            v1.force_json = spec.get("force_json", False)
            v1.changelog = spec["changelog"]
            if v1.status != "active":
                v1.status = "active"
                v1.activated_at = datetime.now(timezone.utc)
            touched += 1

        db.commit()
        return {
            "touched": touched,
            "inserted_prompts": inserted_prompts,
            "inserted_versions": inserted_versions,
        }
    finally:
        db.close()


def main() -> None:
    result = apply_seed()
    print(f"Prompts touched: {result['touched']}")
    print(f"New prompts inserted: {result['inserted_prompts']}")
    print(f"New versions inserted: {result['inserted_versions']}")


if __name__ == "__main__":
    main()
