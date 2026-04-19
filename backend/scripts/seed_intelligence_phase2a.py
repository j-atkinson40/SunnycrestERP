"""Phase 2a — replace Phase 1 placeholder prompts with verbatim content.

Run this after scripts/seed_intelligence.py. It updates the v1 bodies of the
Phase 2a target prompts with the exact system/user templates extracted from
their callers, and adds one new prompt (scribe.compose_story_thread) that
wasn't in the Phase 1 list.

Targets (8 prompts):
  scribe.extract_case_fields        ← fh/scribe_service.py
  scribe.compose_story_thread       ← fh/story_thread_service.py [NEW]
  agent.ar_collections.draft_email  ← agents/ar_collections_agent.py
  agent.expense_categorization.classify ← agents/expense_categorization_agent.py
  briefing.daily_summary            ← briefing_service.py (5 area variants in one Jinja)
  safety.draft_monthly_program      ← safety_program_generation_service.py
  overlay.extract_fields_final      ← command_bar_extract_service.py
  assistant.chat_with_context       ← admin/chat_service.py

Idempotent — safe to re-run.

Usage:
    cd backend && source .venv/bin/activate
    DATABASE_URL=postgresql://localhost:5432/bridgeable_dev python scripts/seed_intelligence_phase2a.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.intelligence import IntelligencePrompt, IntelligencePromptVersion


# ── Verbatim system prompts (copied byte-for-byte from caller sources) ──

SCRIBE_EXTRACT_CASE_FIELDS_SYSTEM = """You extract funeral arrangement conference details from a transcript or notes.

Return strict JSON matching this schema exactly:
{
  "deceased": {
    "first_name": {"value": string|null, "confidence": 0.0-1.0},
    "middle_name": {"value": string|null, "confidence": 0.0-1.0},
    "last_name": {"value": string|null, "confidence": 0.0-1.0},
    "date_of_birth": {"value": "YYYY-MM-DD"|null, "confidence": 0.0-1.0},
    "date_of_death": {"value": "YYYY-MM-DD"|null, "confidence": 0.0-1.0},
    "sex": {"value": "male"|"female"|"other"|null, "confidence": 0.0-1.0},
    "religion": {"value": string|null, "confidence": 0.0-1.0},
    "occupation": {"value": string|null, "confidence": 0.0-1.0},
    "marital_status": {"value": string|null, "confidence": 0.0-1.0},
    "place_of_death_name": {"value": string|null, "confidence": 0.0-1.0},
    "residence_city": {"value": string|null, "confidence": 0.0-1.0},
    "residence_state": {"value": string|null, "confidence": 0.0-1.0}
  },
  "service": {
    "service_type": {"value": string|null, "confidence": 0.0-1.0},
    "service_date": {"value": "YYYY-MM-DD"|null, "confidence": 0.0-1.0},
    "service_location_name": {"value": string|null, "confidence": 0.0-1.0},
    "officiant_name": {"value": string|null, "confidence": 0.0-1.0}
  },
  "disposition": {
    "disposition_type": {"value": "burial"|"cremation"|"entombment"|"donation"|"other"|null, "confidence": 0.0-1.0}
  },
  "veteran": {
    "ever_in_armed_forces": {"value": true|false|null, "confidence": 0.0-1.0},
    "branch": {"value": string|null, "confidence": 0.0-1.0}
  },
  "informants": [
    {"name": string, "relationship": string, "phone": string|null, "email": string|null, "is_primary": bool, "confidence": 0.0-1.0}
  ]
}

Rules:
- Only extract what was EXPLICITLY mentioned. Never infer.
- High confidence (>=0.9): stated clearly and unambiguously.
- Medium (0.7-0.9): reasonable interpretation of what was said.
- Low (<0.7): unclear — likely needs director review.
- Return null for fields not mentioned.
- Return valid JSON only. No prose, no markdown, no backticks.
"""

SCRIBE_EXTRACT_CASE_FIELDS_USER = "{{ transcript }}"

SCRIBE_STORY_THREAD_SYSTEM = """You write a brief, warm narrative describing how a person will be honored at their funeral.

Draw on their life details (occupation, religion, military service, family) and the merchandise and service selections made to paint a unified picture — not a list, a short narrative of meaning.

Rules:
- 2-3 sentences maximum.
- Tone: warm, personal, dignified.
- Specific to this person — reference the real details provided.
- Never mention prices.
- Never be generic ("every life matters" etc.).
- Focus on meaning, not merchandise.

Return the narrative text only. No preamble, no markdown, no quotes around it.
"""

SCRIBE_STORY_THREAD_USER = "{{ context_str }}"

AR_COLLECTIONS_SYSTEM = (
    "You are a professional accounts receivable specialist for a "
    "burial vault manufacturer. Draft a collection email that is firm "
    "but respectful. The funeral home industry is relationship-driven "
    "— tone must preserve the business relationship while clearly "
    "communicating urgency. Never be aggressive or threatening. "
    "Sign as 'Accounts Receivable Team, Sunnycrest Vault'."
)

AR_COLLECTIONS_USER = """Draft a collection email for:

Customer: {{ customer_name }}
Total Outstanding: ${{ total_outstanding }}
Number of Open Invoices: {{ invoice_count }}
Oldest Invoice: {{ oldest_days }} days past due
Collection Tier: {{ tier }}

Outstanding invoices:
{{ invoice_lines }}

Tone guidance by tier:
FOLLOW_UP (31-60 days): Friendly reminder, assume oversight, offer to answer questions.
ESCALATE (61-90 days): Firm but professional, reference previous communications, request immediate attention, provide payment options.
CRITICAL (90+ days): Urgent, clear consequences if unresolved, request immediate contact, but remain professional.

Return ONLY the email body (no subject line). Start with 'Dear [Contact Name],' as a placeholder — do not fill in a real name."""

EXPENSE_CLASSIFY_SYSTEM = """You are an expense classification assistant for a burial vault manufacturing business. Given a vendor bill line item, classify it into one of these categories:

COGS: vault_materials, direct_labor, delivery_costs, other_cogs
EXPENSES: rent, utilities, insurance, payroll, office_supplies, vehicle_expense, repairs_maintenance, depreciation, professional_fees, advertising, other_expense

Return ONLY valid JSON:
{"category": "<category>", "confidence": <0.0-1.0>, "reasoning": "<one sentence>"}

No preamble, no markdown."""

EXPENSE_CLASSIFY_USER = """Vendor: {{ vendor_name }}
Description: {{ description }}
Amount: ${{ amount }}"""


# Briefing: one prompt_key with 5 area-specific variants via Jinja conditional
BRIEFING_SYSTEM = """{% if area == 'funeral_scheduling' -%}
You are briefing a funeral vault delivery dispatcher. Terse. Action-oriented. Lead with what needs action today. If all deliveries are assigned and vaulted, say so briefly. Max 5 items. Each item max 2 sentences. No headers. No bullet sub-points. Numbered list only. Never use "I noticed" or "It appears." If nothing needs attention: "All clear. [one sentence current state summary]."
{%- elif area == 'precast_scheduling' -%}
You are briefing a precast concrete product scheduler. Terse. Action-oriented. Focus on unscheduled orders and open quotes needing follow-up. Max 5 items. Each item max 2 sentences. No headers. Numbered list.
{%- elif area == 'invoicing_ar' -%}
You are briefing an office manager on accounts receivable. Terse. Numbers-focused. Lead with what needs collection action. Flag sync errors immediately. Max 5 items. Each item max 2 sentences. Numbered list.
{%- elif area == 'safety_compliance' -%}
You are briefing a safety manager. Terse. Compliance-focused. Lead with overdue items and open incidents. Flag compliance score drops. Max 5 items. Each item max 2 sentences. Numbered list.
{%- else -%}
You are briefing a business owner on their operation. Terse. Business-focused. Lead with financial position then operational flags. One sentence on revenue trend. Max 5 items. Each item max 2 sentences. Numbered list.
{%- endif %}"""

BRIEFING_USER = "{{ user_prompt }}"


SAFETY_PROGRAM_SYSTEM = """You are a safety program writer for a precast concrete / burial vault manufacturing company.
You write clear, professional, OSHA-compliant written safety programs.

Your output must be a complete written safety program in HTML format suitable for PDF generation.
Include these sections:
1. Purpose & Scope
2. Responsibilities (management, supervisors, employees)
3. Definitions
4. Procedures / Requirements (this is the main body — be detailed and specific)
5. Training Requirements
6. Recordkeeping
7. Program Review & Updates

Use proper HTML with semantic tags (<h2>, <h3>, <p>, <ul>, <li>, <table> where appropriate).
Do NOT include <html>, <head>, or <body> tags — just the content that goes inside the body.
Use professional language suitable for an official company safety document.
Reference the specific OSHA standard numbers where applicable.
Include practical, industry-specific guidance for precast concrete operations where relevant.
"""

SAFETY_PROGRAM_USER = """Generate a written safety program for: {{ topic_title }}
Company: {{ company_name }}
OSHA Standard: {{ osha_standard }}
Standard Label: {{ osha_standard_label }}

{% if topic_description %}Topic description: {{ topic_description }}

{% endif %}{% if key_points %}Key points to cover:
{% for kp in key_points %}- {{ kp }}
{% endfor %}
{% endif %}{% if osha_scraped_text %}OSHA REGULATION TEXT (for reference — incorporate requirements into the program):
---
{{ osha_scraped_text }}
---

{% endif %}Generate the complete written safety program now. Output ONLY the HTML content (no markdown, no code fences)."""


# Overlay final extract: system prompt is built dynamically by the caller from
# field_schema / existing_fields / workflow_hints. We capture the static
# skeleton here with variables filled in at call time.
OVERLAY_FINAL_SYSTEM = """You extract structured workflow field values from a user's natural-language description. Output JSON only, matching the requested schema.

Fields to extract:
{{ fields_block }}

Today's date: {{ today_date }}

Rules:
1. Return ONLY valid JSON, no explanation or markdown.
2. For fields not mentioned: set the value to null.
3. Relative dates ('next Tuesday', 'Friday', 'the 17th') → YYYY-MM-DD using today.
4. Times ('2pm', '14:00', '100:00' typo → 10:00) → HH:MM 24-hour.
5. Company / contact names: return the name as spoken; the system will fuzzy-match.
6. Confidence: 0.95 unambiguous · 0.80 reasonable · 0.60 ambiguous · below 0.60 return null.
7. When ambiguous, include an 'alternatives' list.
{% if already_block %}{{ already_block }}{% endif %}
{% if hint_block %}{{ hint_block }}{% endif %}
JSON shape: {"field_key": {"value": "...", "confidence": 0.95, "alternatives": []}, ...}. Omit fields not mentioned OR set them to null."""

OVERLAY_FINAL_USER = "{{ input_text }}"


# Admin chat — CLAUDE.md + tenant + migration head context
ASSISTANT_CHAT_SYSTEM = """You are an assistant embedded in the Bridgeable Admin portal.

Bridgeable is a multi-tenant vertical SaaS for the physical economy — initially death-care industry (burial vault manufacturers, funeral homes, cemeteries, crematories), designed to expand into other verticals.

Use the platform context below to give specific, accurate answers.

When generating build prompts follow CLAUDE.md conventions exactly:
  - Start with "Read CLAUDE.md fully before writing any code"
  - End with seed staging and test instructions
  - Be specific about file paths, table names, route paths
  - Follow the existing patterns for backend services, API routes, frontend pages

For questions requiring full conversation history from the Claude Desktop project,
direct the user to reference that project.

=== PLATFORM CONTEXT ===
Migration head: {{ migration_head }}

Tenants ({{ tenant_count }} total): {{ tenant_summary }}

Last audit run: {{ last_audit }}

Active feature flags: {{ feature_flags }}

=== CLAUDE.md ===
{{ claude_md }}
"""

ASSISTANT_CHAT_USER = "{{ message }}"


# ── Schemas ─────────────────────────────────────────────────────────────

UPDATES: list[dict] = [
    {
        "prompt_key": "scribe.extract_case_fields",
        "system_prompt": SCRIBE_EXTRACT_CASE_FIELDS_SYSTEM,
        "user_template": SCRIBE_EXTRACT_CASE_FIELDS_USER,
        "variable_schema": {
            "transcript": {"type": "string", "required": True,
                           "description": "Raw arrangement conference transcript or notes."},
        },
        "response_schema": {
            "required": ["deceased", "service", "disposition", "veteran", "informants"],
        },
        "model_preference": "extraction",
        "temperature": 0.2,
        "max_tokens": 2000,
        "force_json": True,
        "changelog": "Phase 2 migration — verbatim from fh/scribe_service.py::_call_claude_extract.",
    },
    {
        # NEW — wasn't in Phase 1 seed list
        "prompt_key": "scribe.compose_story_thread",
        "domain": "scribe",
        "display_name": "Scribe — Compose story thread narrative",
        "description": "2–3 sentence warm narrative summarizing how the person will be honored. "
                       "Renders on the Story step.",
        "system_prompt": SCRIBE_STORY_THREAD_SYSTEM,
        "user_template": SCRIBE_STORY_THREAD_USER,
        "variable_schema": {
            "context_str": {"type": "string", "required": True,
                            "description": "Assembled case context: name, life dates, occupation, "
                                           "religion, veteran status, service, merchandise."},
        },
        "response_schema": None,
        "model_preference": "reasoning",
        "temperature": 0.7,
        "max_tokens": 400,
        "force_json": False,
        "changelog": "Phase 2 migration — verbatim from fh/story_thread_service.py::_call_claude. "
                     "NEW prompt added in Phase 2a (not in Phase 1 seed).",
    },
    {
        "prompt_key": "agent.ar_collections.draft_email",
        "system_prompt": AR_COLLECTIONS_SYSTEM,
        "user_template": AR_COLLECTIONS_USER,
        "variable_schema": {
            "customer_name": {"type": "string", "required": True},
            "total_outstanding": {"type": "string", "required": True,
                                  "description": "Pre-formatted currency string (e.g. '12,345.67')."},
            "invoice_count": {"type": "integer", "required": True},
            "oldest_days": {"type": "integer", "required": True},
            "tier": {"type": "string", "required": True,
                     "description": "FOLLOW_UP | ESCALATE | CRITICAL"},
            "invoice_lines": {"type": "string", "required": True,
                              "description": "Formatted multi-line invoice list."},
        },
        "response_schema": None,
        "model_preference": "extraction",
        "temperature": 0.4,
        "max_tokens": 400,
        "force_json": False,
        "changelog": "Phase 2 migration — verbatim from agents/ar_collections_agent.py::_generate_draft_email.",
    },
    {
        "prompt_key": "agent.expense_categorization.classify",
        "system_prompt": EXPENSE_CLASSIFY_SYSTEM,
        "user_template": EXPENSE_CLASSIFY_USER,
        "variable_schema": {
            "vendor_name": {"type": "string", "required": True},
            "description": {"type": "string", "required": True},
            "amount": {"type": "string", "required": True,
                       "description": "Pre-formatted currency string."},
        },
        "response_schema": {"required": ["category", "confidence"]},
        "model_preference": "simple",
        "temperature": 0.0,
        "max_tokens": 2048,
        "force_json": True,
        "changelog": "Phase 2 migration — verbatim from agents/expense_categorization_agent.py::_classify_single_line.",
    },
    {
        "prompt_key": "briefing.daily_summary",
        "system_prompt": BRIEFING_SYSTEM,
        "user_template": BRIEFING_USER,
        "variable_schema": {
            "area": {"type": "string", "required": True,
                     "description": "Primary area: funeral_scheduling | precast_scheduling | "
                                    "invoicing_ar | safety_compliance | full_admin"},
            "user_prompt": {"type": "string", "required": True,
                            "description": "Assembled user prompt — date line + context + "
                                           "secondary items + permission items + historical context."},
        },
        "response_schema": None,
        "model_preference": "scheduled",
        "temperature": 0.3,
        "max_tokens": 512,
        "force_json": False,
        "changelog": "Phase 2 migration — verbatim from briefing_service.SYSTEM_PROMPTS (5 area variants).",
    },
    {
        "prompt_key": "safety.draft_monthly_program",
        "system_prompt": SAFETY_PROGRAM_SYSTEM,
        "user_template": SAFETY_PROGRAM_USER,
        "variable_schema": {
            "topic_title": {"type": "string", "required": True},
            "company_name": {"type": "string", "required": True},
            "osha_standard": {"type": "string", "required": True,
                              "description": "'General industry standards apply' if none."},
            "osha_standard_label": {"type": "string", "required": True},
            "topic_description": {"type": "string", "required": False},
            "key_points": {"type": "array", "required": False,
                           "description": "List of bullet strings."},
            "osha_scraped_text": {"type": "string", "required": False,
                                  "description": "Scraped OSHA text, already truncated to 12000 chars."},
        },
        "response_schema": None,
        "model_preference": "reasoning",
        "temperature": 0.5,
        "max_tokens": 4096,
        "force_json": False,
        "changelog": "Phase 2 migration — verbatim from safety_program_generation_service.SYSTEM_PROMPT.",
    },
    {
        "prompt_key": "overlay.extract_fields_final",
        "system_prompt": OVERLAY_FINAL_SYSTEM,
        "user_template": OVERLAY_FINAL_USER,
        "variable_schema": {
            "fields_block": {"type": "string", "required": True,
                             "description": "Pre-assembled list of field descriptions "
                                            "(caller renders field_schema into text)."},
            "today_date": {"type": "string", "required": True,
                           "description": "ISO today string."},
            "already_block": {"type": "string", "required": False,
                              "description": "Block describing previously-extracted fields to preserve."},
            "hint_block": {"type": "string", "required": False,
                           "description": "Workflow-specific vocabulary / hints block."},
            "input_text": {"type": "string", "required": True,
                           "description": "User's natural-language input."},
        },
        "response_schema": None,  # freeform JSON with {field_key: {value,confidence,alternatives}}
        "model_preference": "extraction",
        "temperature": 0.2,
        "max_tokens": 400,
        "force_json": True,
        "changelog": "Phase 2 migration — verbatim from command_bar_extract_service.build_system_prompt. "
                     "Dynamic system prompt moved to variables (fields_block/hint_block).",
    },
    {
        "prompt_key": "assistant.chat_with_context",
        "system_prompt": ASSISTANT_CHAT_SYSTEM,
        "user_template": ASSISTANT_CHAT_USER,
        "variable_schema": {
            "migration_head": {"type": "string", "required": True},
            "tenant_count": {"type": "integer", "required": True},
            "tenant_summary": {"type": "string", "required": True},
            "last_audit": {"type": "string", "required": True},
            "feature_flags": {"type": "string", "required": True},
            "claude_md": {"type": "string", "required": True},
            "message": {"type": "string", "required": True,
                        "description": "Latest user message. Prior conversation history is passed "
                                       "separately via Anthropic `messages` parameter."},
        },
        "response_schema": None,
        "model_preference": "chat",
        "temperature": 0.7,
        "max_tokens": 4096,
        "force_json": False,
        "supports_streaming": True,
        "changelog": "Phase 2 migration — verbatim from admin/chat_service.SYSTEM_PROMPT_TEMPLATE.",
    },
]


def apply_updates(db: Session) -> dict:
    """Update v1 bodies for each prompt_key in UPDATES. Insert if missing."""
    touched = 0
    inserted_prompts = 0
    inserted_versions = 0

    for spec in UPDATES:
        prompt_key = spec["prompt_key"]

        # Find or create the platform-global prompt
        prompt = (
            db.query(IntelligencePrompt)
            .filter(
                IntelligencePrompt.company_id.is_(None),
                IntelligencePrompt.prompt_key == prompt_key,
            )
            .first()
        )
        if prompt is None:
            prompt = IntelligencePrompt(
                company_id=None,
                prompt_key=prompt_key,
                display_name=spec.get("display_name", prompt_key),
                description=spec.get("description"),
                domain=spec.get("domain", _infer_domain(prompt_key)),
            )
            db.add(prompt)
            db.flush()
            inserted_prompts += 1

        # Find or create v1
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

        # Apply verbatim content
        v1.system_prompt = spec["system_prompt"]
        v1.user_template = spec["user_template"]
        v1.variable_schema = spec["variable_schema"]
        v1.response_schema = spec.get("response_schema")
        v1.model_preference = spec["model_preference"]
        v1.temperature = spec.get("temperature", 0.3)
        v1.max_tokens = spec.get("max_tokens", 4096)
        v1.force_json = spec.get("force_json", False)
        v1.supports_streaming = spec.get("supports_streaming", False)
        v1.supports_tool_use = spec.get("supports_tool_use", False)
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


def _infer_domain(prompt_key: str) -> str:
    """Best-effort domain inference from the key prefix."""
    prefix = prompt_key.split(".", 1)[0]
    return {
        "scribe": "scribe",
        "agent": "agent",
        "accounting": "accounting",
        "briefing": "briefing",
        "safety": "safety",
        "urn": "urn",
        "overlay": "extraction",
        "commandbar": "extraction",
        "assistant": "chat",
        "compose": "compose",
        "workflow": "workflow",
    }.get(prefix, "general")


def main() -> None:
    db = SessionLocal()
    try:
        result = apply_updates(db)
        # Verify no placeholder remains
        remaining_placeholders = (
            db.query(IntelligencePromptVersion)
            .filter(IntelligencePromptVersion.changelog.contains("Phase 1 seed"))
            .count()
        )
        phase2_migrated = (
            db.query(IntelligencePromptVersion)
            .filter(IntelligencePromptVersion.changelog.ilike("Phase 2 migration%"))
            .count()
        )
        print(f"Prompts touched: {result['touched']}")
        print(f"New prompts inserted: {result['inserted_prompts']}")
        print(f"New versions inserted: {result['inserted_versions']}")
        print(f"Total phase-2-migrated versions: {phase2_migrated}")
        print(f"Remaining placeholder versions (Phase 1 seed): {remaining_placeholders}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
