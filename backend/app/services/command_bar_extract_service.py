"""Natural-language field extraction for command-bar workflow overlays.

Given a workflow and free-text input, Claude extracts structured values
for each of the workflow's input steps. Values are then resolved against
real platform data (CRM contacts, select options, dates) so what the
user sees matches records that actually exist.

This service is called for both live debounced extraction and the final
extraction before submit; callers pass `is_final=True` to opt into the
higher-fidelity Sonnet model. Haiku is used for the hot path.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.company_entity import CompanyEntity
from app.models.workflow import Workflow, WorkflowStep

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────

def build_field_schema(workflow: Workflow, steps: list[WorkflowStep]) -> list[dict]:
    """Describe the workflow's input steps so Claude knows what to extract."""
    schema = []
    for step in sorted(steps, key=lambda s: s.step_order):
        if step.step_type != "input":
            continue
        cfg = step.config or {}
        schema.append({
            "field_key": step.step_key,
            "prompt": cfg.get("prompt", step.step_key),
            "input_type": cfg.get("input_type", "text"),
            "required": cfg.get("required", True),
            "record_type": cfg.get("record_type"),
            "options": cfg.get("options", []),
        })
    return schema


# Workflow-specific vocabulary that Claude should understand when
# extracting. Keep these short and high-signal — long hints cost
# tokens on every debounce tick.
# Quote signals — detected independently of product type so the
# overlay can render a quote-flavored badge + submit label for any
# product. Detection happens in addition to product_type, not
# instead of it.
_QUOTE_SIGNALS: list[str] = [
    "quote for", "quote on", "quoting ", "quoted ", "quote ",
    "price out", "pricing for",
    "estimate for", "estimate on",
    "put together a quote", "get a quote", "draft a quote",
    "what would it cost", "how much would",
]


def detect_entry_intent(input_text: str) -> str:
    """Return 'quote' or 'order'. Quotes override the default."""
    text = (input_text or "").lower()
    if not text:
        return "order"
    for signal in _QUOTE_SIGNALS:
        if signal in text:
            return "quote"
    return "order"


# Purchase-order signals are checked BEFORE anything else — they
# explicitly invert direction ("buy" / "from supplier" / "reorder"
# means we're buying, not selling).
_PURCHASE_ORDER_SIGNALS: list[str] = [
    "po for", "purchase order",
    "buy ", "buying ", "purchase ", "purchasing ",
    "from supplier", "from vendor",
    "reorder", "re-order", "order more",
    "stock up", "replenish", "we need more",
    "vendor order", "supplier order",
]

# Product-type fingerprints for the universal Create Order workflow.
# Scanned in priority order (most specific first) so "disinterment"
# wins over "vault" even if both appear in input.
_PRODUCT_TYPE_FINGERPRINTS: list[tuple[str, list[str]]] = [
    ("disinterment", ["disinterment", "disinter", "exhumation", "exhume"]),
    ("redi_rock", ["redi-rock", "redi rock", "redirock", "retaining wall"]),
    (
        "wastewater",
        ["infiltrator", "eljen", "ezflow", "pipe", "fittings", "septic", "leach field"],
    ),
    ("urn", ["urn", "cremation urn", "companion urn"]),
    (
        "equipment",
        [
            "full equipment", "full setup", "equipment only", "equipment bundle",
            "lowering device", "lowering", "tent only", "just tent", "grass only",
        ],
    ),
    (
        "vault",
        [
            "continental", "monticello", "presidential", "triune",
            "flat top", "flattop", "burial vault", "vault",
        ],
    ),
]

PRODUCT_TYPE_DISPLAY: dict[str, str] = {
    "vault": "Vault Order",
    "disinterment": "Disinterment",
    "redi_rock": "Redi-Rock Order",
    "wastewater": "Wastewater Order",
    "urn": "Urn Order",
    "equipment": "Equipment Order",
    "purchase_order": "Purchase Order",
}

# Which types are "we are buying" vs "we are selling". Used by the
# frontend to color the overlay badge (blue vs green) and to route
# the create_record action to the right table in the future.
PRODUCT_TYPE_DIRECTION: dict[str, str] = {
    "vault": "sales",
    "disinterment": "sales",
    "redi_rock": "sales",
    "wastewater": "sales",
    "urn": "sales",
    "equipment": "sales",
    "purchase_order": "purchase",
}


def detect_product_type(input_text: str) -> str | None:
    """Scan input for product-type keywords. Returns the type key or
    None. Purchase-order signals win first (explicit direction flip);
    more specific sales types then beat more generic ones."""
    text = (input_text or "").lower()
    if not text:
        return None
    # Purchase-order signals checked FIRST — override everything else
    for signal in _PURCHASE_ORDER_SIGNALS:
        if signal in text:
            return "purchase_order"
    for type_key, keywords in _PRODUCT_TYPE_FINGERPRINTS:
        for kw in keywords:
            if kw in text:
                return type_key
    return None


WORKFLOW_EXTRACTION_HINTS: dict[str, str] = {
    # Universal Compose workflow (rebranded from wf_create_order).
    "wf_compose": """
Sunnycrest Precast — product context:

VAULT PRODUCTS (fuzzy match):
  continental → Continental Standard
  monticello → Monticello Standard
  presidential → Presidential
  triune → Triune
  flat top / flattop → Flat Top

EQUIPMENT BUNDLES:
  full equipment / full setup → Full Equipment
  lowering and grass → Lowering Device & Grass
  lowering only → Lowering Device Only
  tent only / just tent → Tent Only
  equipment only → Equipment Only

REDI-ROCK: match block sizes ("60 blocks", "2 ton"); site address often mentioned.
WASTEWATER: Infiltrator, Eljen, EZflow — match product name + quantity.
URN: cremation urns and companion urns — match model name.

CUSTOMERS: partial names like "Hopkins" → "Hopkins Funeral Home".
DATES: resolve relative dates ("Friday", "next week") to YYYY-MM-DD.
DISINTERMENTS: "dis" / "disinterment" → order_type disinterment. Customer is the funeral home requesting it.
QUANTITIES: always whole numbers.

PURCHASE ORDERS — triggered by: buy, po for, purchase, from supplier, from vendor, reorder, order more, stock up, replenish, we need more:
  vendor: the company Sunnycrest is buying FROM (not a funeral home customer).
  item: what is being purchased (cement, rebar, wire, sand, gravel, admixture, forms, hardware, etc.).
  quantity: include units if stated ("50 bags", "2 tons", "100 linear feet").
  unit_price: when a price is mentioned with "per" or "@" (e.g. "$12.50 per bag") → extract the number.

DIRECTION DISAMBIGUATION:
  "for Hopkins" → SALES ORDER (funeral home customer).
  "from Acme Supply" → PURCHASE ORDER (vendor).
  "Continental for Hopkins" → SALES ORDER vault.
  "buy cement from Acme" → PURCHASE ORDER.
  If both a customer and vendor are mentioned and unclear, prefer PURCHASE ORDER when vendor-style language ("from", "buy", "purchase") is present.

QUOTES — triggered by: quote for, quote on, estimate for, estimate on, price out, pricing for, put together a quote, get a quote, draft a quote, what would it cost:
  Same product + customer extraction as orders; only the intent differs.
  "valid for 30 days" / "good for 30 days" → quote_expiry_days: 30.
  Default quote_expiry_days: 30 when not specified.
""",
    "wf_mfg_create_order": """
VAULT PRODUCTS (fuzzy match to full name):
  continental → Continental Standard
  monticello → Monticello Standard
  presidential → Presidential
  triune → Triune
  flat top / flattop → Flat Top

EQUIPMENT BUNDLES:
  full equipment / full setup / full package / complete setup → Full Equipment
  lowering and grass / lowering grass / device and grass → Lowering Device & Grass
  lowering only / just lowering → Lowering Device Only
  tent only / just tent → Tent Only
  equipment only → Equipment Only

CUSTOMERS: partial funeral home names should match CRM contacts.
  Hopkins → Hopkins Funeral Home
  Murphy → Murphy Funeral Home

DELIVERY: resolve "Friday", "next week", "the 17th", "tomorrow" to YYYY-MM-DD.
""",
    "wf_mfg_disinterment": """
CUSTOMERS are funeral homes initiating the disinterment.
LOCATION is the cemetery / current interment address.
Urgency words (ASAP, rush, emergency) belong in the notes field.
Match partial funeral home names to CRM.
""",
    "wf_mfg_schedule_delivery": """
ORDER can be referenced by number ("order 1234", "#1234") or by
  customer name ("the Hopkins order").
DRIVER is a team member — match first names.
DATE: morning defaults to 08:00, afternoon to 13:00 when unspecified.
""",
    "wf_mfg_log_pour": """
PRODUCT names match the vault product catalog.
QUANTITY is always a whole number.
""",
    "wf_mfg_send_statement": """
CUSTOMER is a funeral home or other company in CRM.
Partial names should match (e.g. "Hopkins" → Hopkins Funeral Home).
""",
    "wf_fh_first_call": """
DISPOSITION:
  burial / ground burial / traditional → burial
  cremation / direct cremation / crem → cremation
  cremation with service / memorial → cremation_with_service
DIRECTOR: match first names of funeral home staff.
FAMILY NAME: the surname of the deceased.
""",
    "wf_fh_schedule_arrangement": """
CASE: reference by family name or case number.
DIRECTOR: match first names of funeral home staff.
TIME: morning = AM, afternoon = PM when ambiguous.
""",
}


def _build_prompt_blocks(
    field_schema: list[dict],
    existing_fields: dict[str, dict],
    workflow_id: str | None = None,
) -> tuple[str, str, str]:
    """Assemble the three variable blocks the managed prompt template expects.

    Returns (fields_block, already_block, hint_block). The managed
    `overlay.extract_fields_final` prompt (see scripts/seed_intelligence_phase2a.py)
    glues these blocks together inside its Jinja template.
    """
    descs: list[str] = []
    for f in field_schema:
        line = f'- {f["field_key"]}: {f["prompt"]}'
        t = f["input_type"]
        if t == "select" and f.get("options"):
            opts = ", ".join(o.get("label", o.get("value", "")) for o in f["options"])
            line += f" (options: {opts})"
        elif t == "crm_search":
            line += " (match against company/contact names)"
        elif t == "record_search":
            line += f" (find an existing {f.get('record_type') or 'record'})"
        elif t == "date_picker":
            line += " (resolve relative dates to YYYY-MM-DD)"
        elif t == "datetime_picker":
            line += " (resolve to YYYY-MM-DDTHH:MM 24-hour)"
        elif t == "number":
            line += " (numeric value only)"
        if not f["required"]:
            line += " [optional]"
        descs.append(line)

    already_lines: list[str] = []
    for key, val in (existing_fields or {}).items():
        if not val:
            continue
        conf = float(val.get("confidence", 0) or 0)
        if conf >= 0.85:
            shown = val.get("display_value") or val.get("value") or ""
            already_lines.append(
                f'- {key}: "{shown}" (keep unless user clearly stated a different value)'
            )

    already_block = (
        "\nAlready extracted (preserve unless clearly overridden):\n"
        + "\n".join(already_lines)
        if already_lines
        else ""
    )
    fields_block = "\n".join(descs) if descs else "(no fields)"

    hint = WORKFLOW_EXTRACTION_HINTS.get(workflow_id or "", "").strip()
    hint_block = f"\n\nWorkflow-specific vocabulary:\n{hint}\n" if hint else ""

    return fields_block, already_block, hint_block


# Backwards-compat alias so existing tests / callers that import
# build_system_prompt continue to work. Returns the concatenated skeleton
# identical to the pre-migration output.
def build_system_prompt(
    field_schema: list[dict],
    existing_fields: dict[str, dict],
    workflow_id: str | None = None,
) -> str:
    fields_block, already_block, hint_block = _build_prompt_blocks(
        field_schema, existing_fields, workflow_id
    )
    today_str = date.today().isoformat()
    return (
        "You extract structured workflow field values from a user's natural-language "
        "description. Output JSON only, matching the requested schema.\n\n"
        f"Fields to extract:\n{fields_block}\n\n"
        f"Today's date: {today_str}\n\n"
        "Rules:\n"
        "1. Return ONLY valid JSON, no explanation or markdown.\n"
        "2. For fields not mentioned: set the value to null.\n"
        "3. Relative dates ('next Tuesday', 'Friday', 'the 17th') → YYYY-MM-DD using today.\n"
        "4. Times ('2pm', '14:00', '100:00' typo → 10:00) → HH:MM 24-hour.\n"
        "5. Company / contact names: return the name as spoken; the system will fuzzy-match.\n"
        "6. Confidence: 0.95 unambiguous · 0.80 reasonable · 0.60 ambiguous · below 0.60 return null.\n"
        "7. When ambiguous, include an 'alternatives' list.\n"
        f"{already_block}"
        f"{hint_block}\n"
        'JSON shape: {"field_key": {"value": "...", "confidence": 0.95, "alternatives": []}, ...}.'
        " Omit fields not mentioned OR set them to null."
    )


def _format_date_display(value: str | None) -> str:
    if not value:
        return ""
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d", "%H:%M", "%I:%M %p"):
        try:
            dt = datetime.strptime(value, fmt)
            if fmt == "%Y-%m-%d":
                return dt.strftime("%A, %b %d")
            if fmt == "%Y-%m-%dT%H:%M":
                return dt.strftime("%A, %b %d at %I:%M %p")
            return dt.strftime("%I:%M %p")
        except ValueError:
            continue
    return value


def _fuzzy_match_company(
    db: Session, name: str, company_id: str
) -> dict | None:
    if not name:
        return None
    # Exact
    exact = (
        db.query(CompanyEntity)
        .filter(
            CompanyEntity.company_id == company_id,
            CompanyEntity.name.ilike(name),
        )
        .first()
    )
    if exact:
        return {"id": exact.id, "name": exact.name, "match_score": 0.99}
    # Contains
    contains = (
        db.query(CompanyEntity)
        .filter(
            CompanyEntity.company_id == company_id,
            CompanyEntity.name.ilike(f"%{name}%"),
        )
        .first()
    )
    if contains:
        ratio = len(name) / max(len(contains.name), 1)
        return {
            "id": contains.id,
            "name": contains.name,
            "match_score": min(0.9, ratio + 0.3),
        }
    # Word-by-word
    for word in (w for w in name.split() if len(w) > 2):
        partial = (
            db.query(CompanyEntity)
            .filter(
                CompanyEntity.company_id == company_id,
                CompanyEntity.name.ilike(f"%{word}%"),
            )
            .first()
        )
        if partial:
            return {"id": partial.id, "name": partial.name, "match_score": 0.75}
    return None


def _fuzzy_match_option(value: str, options: list[dict]) -> dict | None:
    if not value or not options:
        return None
    v = value.lower().strip()
    for o in options:
        if str(o.get("value", "")).lower() == v or str(o.get("label", "")).lower() == v:
            return o
    for o in options:
        lbl = str(o.get("label", "")).lower()
        if lbl and (v in lbl or lbl in v):
            return o
    return None


def resolve_fields(
    extracted: dict[str, Any],
    field_schema: list[dict],
    db: Session,
    company_id: str,
) -> dict[str, dict]:
    schema_map = {f["field_key"]: f for f in field_schema}
    resolved: dict[str, dict] = {}
    for key, payload in (extracted or {}).items():
        if payload is None:
            continue
        if not isinstance(payload, dict):
            continue
        raw = payload.get("value")
        if raw is None or raw == "":
            continue
        try:
            conf = float(payload.get("confidence", 0.8))
        except (TypeError, ValueError):
            conf = 0.8
        s = schema_map.get(key, {})
        t = s.get("input_type", "text")

        if t == "crm_search" and isinstance(raw, str):
            match = _fuzzy_match_company(db, raw, company_id)
            if match:
                resolved[key] = {
                    "value": match["id"],
                    "display_value": match["name"],
                    "confidence": min(conf, match["match_score"]),
                    "matched_id": match["id"],
                    "matched_type": "company_entity",
                    "alternatives": payload.get("alternatives", []),
                }
            else:
                resolved[key] = {
                    "value": raw,
                    "display_value": raw,
                    "confidence": min(conf, 0.6),
                    "matched_id": None,
                    "unresolved": True,
                }
        elif t in ("date_picker", "datetime_picker"):
            resolved[key] = {
                "value": raw,
                "display_value": _format_date_display(str(raw)),
                "confidence": conf,
                "alternatives": payload.get("alternatives", []),
            }
        elif t == "select":
            opt = _fuzzy_match_option(str(raw), s.get("options", []))
            if opt:
                resolved[key] = {
                    "value": opt.get("value"),
                    "display_value": opt.get("label", opt.get("value")),
                    "confidence": conf,
                }
            else:
                resolved[key] = {
                    "value": raw,
                    "display_value": str(raw),
                    "confidence": min(conf, 0.65),
                }
        else:
            resolved[key] = {
                "value": raw,
                "display_value": str(raw),
                "confidence": conf,
                "alternatives": payload.get("alternatives", []),
            }
    return resolved


def extract(
    db: Session,
    *,
    workflow_id: str,
    input_text: str,
    company_id: str,
    existing_fields: dict | None = None,
    is_final: bool = False,
) -> dict:
    """Main entry point — returns {fields: {...}, raw_input: str}."""
    existing = existing_fields or {}
    if not input_text or not input_text.strip():
        return {"fields": {}, "raw_input": input_text}

    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        return {"fields": {}, "raw_input": input_text}
    steps = (
        db.query(WorkflowStep)
        .filter(WorkflowStep.workflow_id == workflow.id)
        .all()
    )
    schema = build_field_schema(workflow, steps)
    if not schema:
        return {"fields": {}, "raw_input": input_text}

    # Build the fields_block / already_block / hint_block the managed prompt expects.
    fields_block, already_block, hint_block = _build_prompt_blocks(
        schema, existing, workflow_id=workflow.id
    )
    try:
        from app.services.intelligence import extraction_service

        # is_final is a legacy seam; both paths go through final_extract in
        # Phase 2a since the command bar only calls with is_final at submit time.
        _ = is_final
        result = extraction_service.final_extract(
            db,
            workflow_id=workflow.id,
            input_text=input_text,
            company_id=company_id,
            session_id=None,  # TODO Phase 2b: plumb session_id through from the UI
            fields_block=fields_block,
            already_block=already_block,
            hint_block=hint_block,
        )
    except Exception as e:
        logger.debug("Extraction failed: %s", e)
        return {"fields": {}, "raw_input": input_text}

    if not isinstance(result, dict):
        return {"fields": {}, "raw_input": input_text}

    resolved = resolve_fields(result, schema, db, company_id)
    product_type = detect_product_type(input_text)
    entry_intent = detect_entry_intent(input_text)
    return {
        "fields": resolved,
        "raw_input": input_text,
        "product_type": product_type,
        "product_type_label": PRODUCT_TYPE_DISPLAY.get(product_type, "") if product_type else "",
        "direction": PRODUCT_TYPE_DIRECTION.get(product_type or "", "sales"),
        "entry_intent": entry_intent,
    }


# expose re for any caller that needs the same regex helpers
__all__ = ["extract", "build_field_schema", "resolve_fields"]

_ = re  # silence unused-import guards
