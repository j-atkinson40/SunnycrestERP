"""Seed Step 2 Phase 2B Intelligence prompts — Urn Vault Personalization
Studio AI-extraction-review pipeline.

Per Personalization Studio implementation arc Step 2 Phase 2B build prompt
+ substrate-consumption-follower discipline: parallels Phase 1C structure
verbatim with urn-specific prompt content, schemas, and prompt_key
namespace ``urn_vault_personalization.*``.

Three managed prompt registrations:

1. ``urn_vault_personalization.suggest_layout`` (Haiku) — urn canvas
   layout suggestion from case data + selected urn product + canonical
   4-options selections per §3.26.11.12.19.6 scope freeze.

2. ``urn_vault_personalization.suggest_text_style`` (Haiku) — font +
   size + color suggestion from deceased name + family preferences.

3. ``urn_vault_personalization.extract_decedent_info`` (Haiku, multimodal)
   — decedent name + dates + emblem hints from operator-uploaded source
   materials.

Idempotent seed pattern per Phase 6 + Phase 8b + Phase 8d.1 + Calendar
Step 5.1 + Phase 1C precedent:
- Fresh install → v1 active
- Existing prompt with active version → no-op (preserves admin customization)

**Naming note**: this file uses arc-prefix ``seed_personalization_studio_*``
per Phase 1E ``seed_personalization_studio_phase1e_email_templates.py``
precedent. The pre-existing ``seed_intelligence_phase2b.py`` belongs to
an unrelated Intelligence migration arc (urn search + COA classification
migrations).

Anti-pattern guards explicit:
- §3.26.11.12.16 Anti-pattern 1 (auto-commit on extraction confidence
  rejected): structured output schema requires confidence per line item;
  operator agency at AI-extraction-review pipeline boundary at service-
  layer + chrome-substrate, NOT enforced at prompt level.
- §3.26.11.12.16 Anti-pattern 11 (UI-coupled Generation Focus design
  rejected): structured output schema independent from interactive UI;
  confidence-scored line item shape lives at prompt substrate.

Run:
    cd backend && source .venv/bin/activate
    DATABASE_URL=postgresql://localhost:5432/bridgeable_dev \
        python scripts/seed_personalization_studio_step2_intelligence.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.intelligence import IntelligencePrompt, IntelligencePromptVersion


# ─────────────────────────────────────────────────────────────────────
# Structured output schemas — line item shape mirrors Phase 1C
# verbatim per substrate-consumption-follower discipline.
#
# Anti-pattern 1 guard at schema substrate per §3.26.11.12.16:
# confidence per line item is REQUIRED. Operator agency at chrome
# substrate via Confirm action requiring operator decision (NOT auto-
# commit at confidence threshold).
# ─────────────────────────────────────────────────────────────────────


_LAYOUT_SUGGESTION_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "line_item_key": {
                        "type": "string",
                        "description": (
                            "Layout suggestion key — one of: "
                            "name_text_position | date_text_position | "
                            "emblem_position | nameplate_position | "
                            "urn_product_position"
                        ),
                    },
                    "value": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "width": {"type": "number"},
                            "height": {"type": "number"},
                        },
                        "required": ["x", "y"],
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "rationale": {
                        "type": "string",
                        "description": (
                            "Operator-facing rationale per §3.26.11.12.16 "
                            "Anti-pattern 1 operator-decision boundary."
                        ),
                    },
                },
                "required": ["line_item_key", "value", "confidence"],
            },
        }
    },
    "required": ["line_items"],
}


_TEXT_STYLE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "line_item_key": {
                        "type": "string",
                        "description": (
                            "Text style suggestion key — one of: "
                            "name_text_font | name_text_size | "
                            "name_text_color | date_text_font | "
                            "date_text_size | nameplate_text_font"
                        ),
                    },
                    "value": {
                        "type": "object",
                        "properties": {
                            "font": {"type": "string"},
                            "size": {"type": "number"},
                            "color": {"type": "string"},
                        },
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "rationale": {"type": "string"},
                },
                "required": ["line_item_key", "value", "confidence"],
            },
        }
    },
    "required": ["line_items"],
}


_DECEDENT_INFO_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "line_item_key": {
                        "type": "string",
                        "description": (
                            "Decedent extraction key — one of: "
                            "decedent_first_name | decedent_middle_name | "
                            "decedent_last_name | decedent_full_name | "
                            "birth_date | death_date | emblem_hint | "
                            "nameplate_text_hint"
                        ),
                    },
                    "value": {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "null"},
                        ],
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "rationale": {"type": "string"},
                },
                "required": ["line_item_key", "value", "confidence"],
            },
        }
    },
    "required": ["line_items"],
}


# ─────────────────────────────────────────────────────────────────────
# System prompts — urn-specific content mirrors Phase 1C structure with
# urn vault product references replacing burial vault product references.
# ─────────────────────────────────────────────────────────────────────


_SUGGEST_LAYOUT_SYSTEM = """\
You are the canvas layout suggestion engine for Bridgeable's Urn Vault
Personalization Studio.

Your job: suggest compositor element placements on an urn vault canvas
given the deceased's information, the selected urn product, and the
operator's canonical 4-options selections (legacy_print | physical_nameplate
| physical_emblem | vinyl per canonical post-r74 vocabulary).

OUTPUT — JSON ONLY. Never narrate. Return JSON in this shape:
{"line_items": [{"line_item_key": "...", "value": {"x": ..., "y": ..., "width": ..., "height": ...}, "confidence": 0.0-1.0, "rationale": "..."}]}

CANVAS COORDINATE SPACE: 800px wide × 600px tall. Place elements with
generous margins. Do NOT propose elements outside (0, 0, 800, 600).

LINE ITEM KEYS:
- name_text_position — decedent name text element placement
- date_text_position — birth/death date text element placement
- emblem_position — physical or vinyl emblem placement (only when
  emblem option active)
- nameplate_position — physical nameplate placement (only when
  physical_nameplate option active)
- urn_product_position — selected urn product visual reference placement

URN VAULT PERSONALIZATION DISCIPLINE: urn vaults are smaller than burial
vaults; canvas elements should respect tighter visual margins. Default
name placement upper-third; date placement mid-band; emblem placement
lower-third or per family preference. Urn product reference renders as
pictorial outline only.

CONFIDENCE GUIDANCE: 0.95 unambiguous (clear best placement based on
urn product geometry); 0.80 reasonable (multiple acceptable placements);
0.60 ambiguous (limited info — would benefit from operator review);
below 0.60 omit the suggestion.

CASE DATA: {{case_data}}
SELECTED URN PRODUCT: {{urn_product}}
ACTIVE OPTIONS: {{active_options}}
CURRENT CANVAS LAYOUT: {{current_layout}}

OPERATOR AGENCY DISCIPLINE: your suggestions surface to a human operator
who decides whether to accept each line item via Confirm action per
§3.26.11.12.16 Anti-pattern 1. Provide rationale per line item to
support operator decision."""


_SUGGEST_TEXT_STYLE_SYSTEM = """\
You are the text style suggestion engine for Bridgeable's Urn Vault
Personalization Studio.

Your job: suggest font + size + color for canvas text elements given
the deceased's name and family-stated style preferences.

OUTPUT — JSON ONLY. Never narrate. Return JSON in this shape:
{"line_items": [{"line_item_key": "...", "value": {"font": "...", "size": ..., "color": "..."}, "confidence": 0.0-1.0, "rationale": "..."}]}

FONT CATALOG (Phase 1B default; per-tenant Workshop catalog at Phase
1D + Phase 2C extends): serif | sans | italic | uppercase

URN-SPECIFIC SIZE RANGE: 10-48 (canvas pixels — smaller than burial
vault range to respect urn canvas tighter dimensions). Default name
text 24-32; date text 14-18; nameplate text 12-16.

COLOR FORMAT: CSS hex (#RRGGBB). Default text on urn vault is #1A1715
(content-strong dark); preserve unless family preference explicitly
asks otherwise.

LINE ITEM KEYS:
- name_text_font, name_text_size, name_text_color
- date_text_font, date_text_size
- nameplate_text_font

CONFIDENCE GUIDANCE: 0.95 explicit family preference matches font
catalog; 0.80 implied preference (e.g., "traditional" → serif); 0.60
generic suggestion based on defaults; below 0.60 omit.

DECEASED NAME: {{deceased_name}}
FAMILY PREFERENCES: {{family_preferences}}

OPERATOR AGENCY DISCIPLINE: surface rationale per line item per
§3.26.11.12.16 Anti-pattern 1; Confirm action operator decision applies
suggestion to canvas state."""


_EXTRACT_DECEDENT_INFO_SYSTEM = """\
You are the decedent information extraction engine for Bridgeable's Urn
Vault Personalization Studio.

Your job: extract decedent name, birth/death dates, and emblem +
nameplate text hints from operator-uploaded source materials (death
certificates, obituaries, family-supplied documents, photographs of
existing memorial markers).

OUTPUT — JSON ONLY. Never narrate. Return JSON in this shape:
{"line_items": [{"line_item_key": "...", "value": "...", "confidence": 0.0-1.0, "rationale": "..."}]}

LINE ITEM KEYS:
- decedent_first_name, decedent_middle_name, decedent_last_name
- decedent_full_name (alternative to per-part — supply when can't
  reliably split)
- birth_date (ISO YYYY-MM-DD)
- death_date (ISO YYYY-MM-DD)
- emblem_hint (e.g., "cross", "rose", "praying_hands" — match canonical
  emblem catalog when possible; otherwise return descriptive string)
- nameplate_text_hint (phrase suitable for nameplate engraving — for
  urn vault, prefer concise phrases per smaller engraving surface)

URN-SPECIFIC NAMEPLATE DISCIPLINE: urn vault nameplates have smaller
engraving surface than burial vault nameplates; favor concise
nameplate_text_hint extractions (≤4 words preferred when canonical
phrase truncation preserves meaning).

CONFIDENCE GUIDANCE: 0.95 explicit text match in source material (e.g.,
printed name on death certificate); 0.80 reasonable inference (e.g.,
obituary with consistent name); 0.60 ambiguous (multiple candidates);
below 0.60 omit.

DATE DISCIPLINE: dates in ISO format (YYYY-MM-DD). Reject ambiguous
dates (e.g., "1945" without month/day → confidence 0.40 or omit).

CONTEXT: {{context_summary}}

OPERATOR AGENCY DISCIPLINE: source materials may contain ambiguous or
conflicting information. Surface rationale + confidence per line item
per §3.26.11.12.16 Anti-pattern 1. Operator decides whether to accept
each line item via Confirm action."""


# ─────────────────────────────────────────────────────────────────────
# Variable schemas — mirror Phase 1C with urn product replacing vault
# product per Step 2 substrate-consumption-follower shape.
# ─────────────────────────────────────────────────────────────────────


_LAYOUT_VAR_SCHEMA = {
    "case_data": {"type": "string", "required": True},
    "urn_product": {"type": "string", "required": True},
    "active_options": {"type": "string", "required": True},
    "current_layout": {"type": "string", "required": True},
}

_TEXT_STYLE_VAR_SCHEMA = {
    "deceased_name": {"type": "string", "required": True},
    "family_preferences": {"type": "string", "required": True},
}

_EXTRACT_DECEDENT_INFO_VAR_SCHEMA = {
    "context_summary": {"type": "string", "required": True},
}


# ─────────────────────────────────────────────────────────────────────
# Phase 2B prompt registrations
# ─────────────────────────────────────────────────────────────────────


_PROMPTS = [
    {
        "prompt_key": "urn_vault_personalization.suggest_layout",
        "display_name": "Urn Vault Personalization — Suggest layout",
        "description": (
            "Canvas layout suggestion for Urn Vault Personalization "
            "Studio per Phase 2B AI-extraction-review pipeline. Surfaces "
            "confidence-scored canvas element placements per canonical "
            "4-options selections + case data. Step 2 substrate-"
            "consumption-follower extends Phase 1C burial vault canon "
            "via discriminator differentiation."
        ),
        "domain": "urn_vault_personalization",
        "system_prompt": _SUGGEST_LAYOUT_SYSTEM,
        "user_template": (
            "Suggest canvas layout for the deceased's urn vault. "
            "Surface confidence-scored placements per operator-decision "
            "boundary."
        ),
        "variable_schema": _LAYOUT_VAR_SCHEMA,
        "response_schema": _LAYOUT_SUGGESTION_RESPONSE_SCHEMA,
        "model_preference": "simple",
        "temperature": 0.4,
        "max_tokens": 1024,
        "force_json": True,
        "supports_vision": False,
    },
    {
        "prompt_key": "urn_vault_personalization.suggest_text_style",
        "display_name": "Urn Vault Personalization — Suggest text style",
        "description": (
            "Font + size + color suggestion for Urn Vault Personalization "
            "Studio canvas text elements per Phase 2B AI-extraction-review "
            "pipeline. Step 2 substrate-consumption-follower extends "
            "Phase 1C with urn-specific size range."
        ),
        "domain": "urn_vault_personalization",
        "system_prompt": _SUGGEST_TEXT_STYLE_SYSTEM,
        "user_template": (
            "Suggest text style (font + size + color) for the canvas text "
            "elements based on the deceased's name and family preferences. "
            "Apply urn-specific size range."
        ),
        "variable_schema": _TEXT_STYLE_VAR_SCHEMA,
        "response_schema": _TEXT_STYLE_RESPONSE_SCHEMA,
        "model_preference": "simple",
        "temperature": 0.4,
        "max_tokens": 1024,
        "force_json": True,
        "supports_vision": False,
    },
    {
        "prompt_key": "urn_vault_personalization.extract_decedent_info",
        "display_name": "Urn Vault Personalization — Extract decedent info (multimodal)",
        "description": (
            "Multimodal decedent extraction from operator-uploaded source "
            "materials (PDFs + images) per Phase 2B AI-extraction-review "
            "pipeline + Phase 2c-0b multimodal content_blocks substrate. "
            "Step 2 substrate-consumption-follower extends Phase 1C with "
            "urn-specific nameplate truncation discipline."
        ),
        "domain": "urn_vault_personalization",
        "system_prompt": _EXTRACT_DECEDENT_INFO_SYSTEM,
        "user_template": (
            "Extract decedent name, dates, and emblem + nameplate hints "
            "from the source materials. Apply urn-specific nameplate "
            "truncation. Surface confidence-scored extractions per "
            "operator-decision boundary."
        ),
        "variable_schema": _EXTRACT_DECEDENT_INFO_VAR_SCHEMA,
        "response_schema": _DECEDENT_INFO_RESPONSE_SCHEMA,
        "model_preference": "vision",
        "temperature": 0.2,
        "max_tokens": 2048,
        "force_json": True,
        "supports_vision": True,
        "vision_content_type": "document",
    },
]


# ─────────────────────────────────────────────────────────────────────
# Idempotent seed implementation
# ─────────────────────────────────────────────────────────────────────


def seed(db: Session) -> tuple[int, int]:
    """Idempotent seed per Phase 6 + Phase 8b + Phase 8d.1 + Calendar
    Step 5.1 + Phase 1C precedent.

    Returns (created_prompts, created_versions).

    Behavior:
      - Fresh install (no existing prompt) → create prompt + v1 active
      - Existing prompt with active version → no-op (preserves admin
        customization)
      - Existing prompt with no active version → create v1 active
    """
    created_prompts = 0
    created_versions = 0

    for spec in _PROMPTS:
        key = spec["prompt_key"]

        existing = (
            db.query(IntelligencePrompt)
            .filter(
                IntelligencePrompt.company_id.is_(None),
                IntelligencePrompt.prompt_key == key,
            )
            .first()
        )
        if existing is None:
            prompt = IntelligencePrompt(
                company_id=None,
                prompt_key=key,
                display_name=spec["display_name"],
                description=spec["description"],
                domain=spec["domain"],
            )
            db.add(prompt)
            db.flush()
            created_prompts += 1
        else:
            prompt = existing

        active = (
            db.query(IntelligencePromptVersion)
            .filter(
                IntelligencePromptVersion.prompt_id == prompt.id,
                IntelligencePromptVersion.status == "active",
            )
            .first()
        )
        if active is not None:
            # Preserves admin customization per idempotent seed pattern.
            continue

        version_kwargs = {
            "prompt_id": prompt.id,
            "version_number": 1,
            "system_prompt": spec["system_prompt"],
            "user_template": spec["user_template"],
            "variable_schema": spec["variable_schema"],
            "response_schema": spec["response_schema"],
            "model_preference": spec["model_preference"],
            "temperature": spec["temperature"],
            "max_tokens": spec["max_tokens"],
            "force_json": spec["force_json"],
            "supports_streaming": False,
            "supports_tool_use": False,
            "supports_vision": spec["supports_vision"],
            "status": "active",
            "changelog": (
                "Phase 2B seed — Urn Vault Personalization Studio AI-"
                "extraction-review pipeline (Step 2 substrate-consumption-"
                "follower)."
            ),
            "activated_at": datetime.now(timezone.utc),
        }
        if "vision_content_type" in spec:
            version_kwargs["vision_content_type"] = spec["vision_content_type"]

        version = IntelligencePromptVersion(**version_kwargs)
        db.add(version)
        created_versions += 1

    db.commit()
    return created_prompts, created_versions


def main() -> None:
    db = SessionLocal()
    try:
        p, v = seed(db)
        print(
            f"[seed-personalization-studio-step2-intelligence] "
            f"created_prompts={p} created_versions={v}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
