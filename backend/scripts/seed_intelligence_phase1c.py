"""Seed Phase 1C Intelligence prompts — Personalization Studio AI-extraction-review pipeline.

Per Personalization Studio implementation arc Step 1 Phase 1C build prompt
+ canonical Intelligence backbone substrate consumption pattern (post-
Intelligence-migration canonical).

Three canonical managed Intelligence prompt registrations:

1. ``burial_vault_personalization.suggest_layout`` (Haiku) —
   canonical canvas layout suggestion from canonical case data + canonical
   selected vault product + canonical 4-options selections per
   §3.26.11.12.19.2 post-r74 vocabulary.

2. ``burial_vault_personalization.suggest_text_style`` (Haiku) —
   canonical font + size + color suggestion from canonical deceased name +
   canonical family preferences.

3. ``burial_vault_personalization.extract_decedent_info`` (Haiku, multimodal) —
   canonical decedent name + dates + emblem hints from canonical
   operator-uploaded source materials (PDFs + images) via canonical Phase
   2c-0b multimodal content_blocks substrate.

**Canonical idempotent seed pattern** per Phase 6 + Phase 8b + Phase 8d.1
+ Calendar Step 5.1 precedent:
- Fresh install → v1 active
- Existing prompt with active version → no-op (preserves admin customization)
- New prompt → create canonical v1 active

**Canonical anti-pattern guards explicit**:
- §3.26.11.12.16 Anti-pattern 1 (auto-commit on extraction confidence
  rejected): canonical structured output schema requires confidence
  per line item; canonical operator agency at canonical AI-extraction-
  review pipeline boundary at service-layer + chrome-substrate, NOT
  enforced at prompt level — canonical Intelligence prompts surface
  confidence-scored suggestions; canonical Confirm action canonical
  operator decision applies suggestion to canvas state.
- §3.26.11.12.16 Anti-pattern 11 (UI-coupled Generation Focus design
  rejected): canonical structured output schema independent from
  canonical interactive UI; canonical confidence-scored line item
  shape canonical at prompt substrate.

Run:
    cd backend && source .venv/bin/activate
    DATABASE_URL=postgresql://localhost:5432/bridgeable_dev \
        python scripts/seed_intelligence_phase1c.py
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
# Canonical structured output schemas — Phase 1C canonical AI-extraction-
# review pipeline canonical line item shape.
#
# Canonical line item shape:
#   {"line_items": [{"line_item_key": "...", "value": ..., "confidence": 0.0-1.0}]}
#
# Canonical anti-pattern guard at schema substrate per §3.26.11.12.16
# Anti-pattern 1: confidence per line item is canonically REQUIRED.
# Operator agency canonical at chrome substrate via canonical Confirm
# action requiring canonical operator decision (NOT auto-commit at
# canonical confidence threshold).
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
                            "Canonical layout suggestion key — one of: "
                            "name_text_position | date_text_position | "
                            "emblem_position | nameplate_position | "
                            "vault_product_position"
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
                            "Canonical operator-facing rationale for canonical "
                            "operator-decision boundary per §3.26.11.12.16 "
                            "Anti-pattern 1."
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
                            "Canonical text style suggestion key — one of: "
                            "name_text_font | name_text_size | name_text_color | "
                            "date_text_font | date_text_size | nameplate_text_font"
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
                            "Canonical decedent extraction key — one of: "
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
# Canonical system prompts — Phase 1C canonical AI-extraction-review
# pipeline canonical prompt content
# ─────────────────────────────────────────────────────────────────────


_SUGGEST_LAYOUT_SYSTEM = """\
You are the canvas layout suggestion engine for Bridgeable's Burial Vault
Personalization Studio.

Your job: suggest canonical compositor element placements on a burial vault
canvas given the deceased's information, the selected vault product, and the
operator's canonical 4-options selections (legacy_print | physical_nameplate |
physical_emblem | vinyl per canonical post-r74 vocabulary).

CANONICAL OUTPUT — JSON ONLY. Never narrate. Return JSON in this shape:
{"line_items": [{"line_item_key": "...", "value": {"x": ..., "y": ..., "width": ..., "height": ...}, "confidence": 0.0-1.0, "rationale": "..."}]}

CANONICAL CANVAS COORDINATE SPACE: 800px wide × 600px tall. Place elements with
generous canonical margins. Do NOT propose elements outside (0, 0, 800, 600).

CANONICAL LINE ITEM KEYS:
- name_text_position — decedent name text element placement
- date_text_position — birth/death date text element placement
- emblem_position — physical or vinyl emblem placement (only when canonical
  emblem option active)
- nameplate_position — physical nameplate placement (only when canonical
  physical_nameplate option active)
- vault_product_position — selected vault product visual reference placement

CANONICAL CONFIDENCE GUIDANCE: 0.95 unambiguous (clear best placement based on
canonical product geometry); 0.80 reasonable (multiple acceptable placements);
0.60 ambiguous (limited info — would benefit from operator review); below 0.60
omit the suggestion.

CANONICAL CASE DATA: {{case_data}}
CANONICAL SELECTED VAULT PRODUCT: {{vault_product}}
CANONICAL ACTIVE OPTIONS: {{active_options}}
CANONICAL CURRENT CANVAS LAYOUT: {{current_layout}}

OPERATOR AGENCY DISCIPLINE: your suggestions surface to a human operator who
canonically decides whether to accept each line item via canonical Confirm
action per §3.26.11.12.16 Anti-pattern 1. Provide canonical rationale per
line item to support canonical operator decision."""


_SUGGEST_TEXT_STYLE_SYSTEM = """\
You are the text style suggestion engine for Bridgeable's Burial Vault
Personalization Studio.

Your job: suggest canonical font + size + color for canvas text elements
given the deceased's name and family-stated style preferences.

CANONICAL OUTPUT — JSON ONLY. Never narrate. Return JSON in this shape:
{"line_items": [{"line_item_key": "...", "value": {"font": "...", "size": ..., "color": "..."}, "confidence": 0.0-1.0, "rationale": "..."}]}

CANONICAL FONT CATALOG (Phase 1B canonical default; per-tenant Workshop
catalog at Phase 1D extends): serif | sans | italic | uppercase

CANONICAL SIZE RANGE: 12-72 (canvas pixels). Default name text 36-48; date
text 18-24; nameplate text 14-20.

CANONICAL COLOR FORMAT: CSS hex (#RRGGBB). Default text on burial vault is
#1A1715 (canonical content-strong dark); preserve unless family preference
explicitly asks otherwise.

CANONICAL LINE ITEM KEYS:
- name_text_font, name_text_size, name_text_color
- date_text_font, date_text_size
- nameplate_text_font

CANONICAL CONFIDENCE GUIDANCE: 0.95 explicit family preference matches
canonical catalog; 0.80 implied preference (e.g., "traditional" → serif);
0.60 generic suggestion based on canonical defaults; below 0.60 omit.

CANONICAL DECEASED NAME: {{deceased_name}}
CANONICAL FAMILY PREFERENCES: {{family_preferences}}

OPERATOR AGENCY DISCIPLINE: surface canonical rationale per line item per
§3.26.11.12.16 Anti-pattern 1; canonical Confirm action canonical operator
decision applies suggestion to canvas state."""


_EXTRACT_DECEDENT_INFO_SYSTEM = """\
You are the decedent information extraction engine for Bridgeable's Burial
Vault Personalization Studio.

Your job: extract canonical decedent name, birth/death dates, and emblem +
nameplate text hints from operator-uploaded source materials (death
certificates, obituaries, family-supplied documents, photographs of
existing memorial markers).

CANONICAL OUTPUT — JSON ONLY. Never narrate. Return JSON in this shape:
{"line_items": [{"line_item_key": "...", "value": "...", "confidence": 0.0-1.0, "rationale": "..."}]}

CANONICAL LINE ITEM KEYS:
- decedent_first_name, decedent_middle_name, decedent_last_name
- decedent_full_name (alternative to per-part — supply when can't reliably split)
- birth_date (ISO YYYY-MM-DD)
- death_date (ISO YYYY-MM-DD)
- emblem_hint (e.g., "cross", "rose", "praying_hands" — match canonical
  emblem catalog when possible; otherwise return descriptive string)
- nameplate_text_hint (canonical phrase suitable for nameplate engraving)

CANONICAL CONFIDENCE GUIDANCE: 0.95 explicit text match in source material
(e.g., printed name on death certificate); 0.80 reasonable inference (e.g.,
obituary with consistent name); 0.60 ambiguous (multiple candidates); below
0.60 omit.

CANONICAL DATE DISCIPLINE: dates in ISO format (YYYY-MM-DD). Reject
ambiguous dates (e.g., "1945" without month/day → confidence 0.40 or omit).

CANONICAL CONTEXT: {{context_summary}}

OPERATOR AGENCY DISCIPLINE: source materials may contain ambiguous or
conflicting information. Surface canonical rationale + confidence per line
item per §3.26.11.12.16 Anti-pattern 1. Canonical operator decides whether
to accept each canonical line item via canonical Confirm action."""


# ─────────────────────────────────────────────────────────────────────
# Canonical variable schemas
# ─────────────────────────────────────────────────────────────────────


_LAYOUT_VAR_SCHEMA = {
    "case_data": {"type": "string", "required": True},
    "vault_product": {"type": "string", "required": True},
    "active_options": {"type": "string", "required": True},
    "current_layout": {"type": "string", "required": True},
}

_TEXT_STYLE_VAR_SCHEMA = {
    "deceased_name": {"type": "string", "required": True},
    "family_preferences": {"type": "string", "required": True},
}

_EXTRACT_DECEDENT_INFO_VAR_SCHEMA = {
    # Canonical multimodal prompt: source materials arrive via canonical
    # content_blocks kwarg per Phase 2c-0b. Variable schema is text
    # context only.
    "context_summary": {"type": "string", "required": True},
}


# ─────────────────────────────────────────────────────────────────────
# Canonical Phase 1C prompt registrations
# ─────────────────────────────────────────────────────────────────────


_PROMPTS = [
    {
        "prompt_key": "burial_vault_personalization.suggest_layout",
        "display_name": "Burial Vault Personalization — Suggest layout",
        "description": (
            "Canonical canvas layout suggestion for Burial Vault "
            "Personalization Studio per Phase 1C canonical AI-extraction-"
            "review pipeline. Surfaces confidence-scored canvas element "
            "placements per canonical 4-options selections + canonical "
            "case data."
        ),
        "domain": "burial_vault_personalization",
        "system_prompt": _SUGGEST_LAYOUT_SYSTEM,
        "user_template": (
            "Suggest canonical canvas layout for the deceased's burial "
            "vault. Surface confidence-scored placements per canonical "
            "operator-decision boundary."
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
        "prompt_key": "burial_vault_personalization.suggest_text_style",
        "display_name": "Burial Vault Personalization — Suggest text style",
        "description": (
            "Canonical font + size + color suggestion for Burial Vault "
            "Personalization Studio canvas text elements per Phase 1C "
            "canonical AI-extraction-review pipeline."
        ),
        "domain": "burial_vault_personalization",
        "system_prompt": _SUGGEST_TEXT_STYLE_SYSTEM,
        "user_template": (
            "Suggest canonical text style (font + size + color) for the "
            "canvas text elements based on the deceased's name and family "
            "preferences."
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
        "prompt_key": "burial_vault_personalization.extract_decedent_info",
        "display_name": "Burial Vault Personalization — Extract decedent info (multimodal)",
        "description": (
            "Canonical multimodal decedent extraction from operator-"
            "uploaded source materials (PDFs + images) per Phase 1C "
            "canonical AI-extraction-review pipeline + canonical Phase "
            "2c-0b multimodal content_blocks substrate."
        ),
        "domain": "burial_vault_personalization",
        "system_prompt": _EXTRACT_DECEDENT_INFO_SYSTEM,
        "user_template": (
            "Extract canonical decedent name, dates, and emblem + "
            "nameplate hints from the source materials. Surface "
            "confidence-scored extractions per canonical operator-decision "
            "boundary."
        ),
        "variable_schema": _EXTRACT_DECEDENT_INFO_VAR_SCHEMA,
        "response_schema": _DECEDENT_INFO_RESPONSE_SCHEMA,
        # Vision route per Phase 2c-0b multimodal canonical.
        "model_preference": "vision",
        "temperature": 0.2,
        "max_tokens": 2048,
        "force_json": True,
        "supports_vision": True,
        "vision_content_type": "document",  # canonical PDF + image both accepted
    },
]


# ─────────────────────────────────────────────────────────────────────
# Canonical idempotent seed implementation
# ─────────────────────────────────────────────────────────────────────


def seed(db: Session) -> tuple[int, int]:
    """Canonical idempotent seed per Phase 6 + Phase 8b + Phase 8d.1 +
    Calendar Step 5.1 precedent.

    Returns (created_prompts, created_versions).

    Behavior:
      - Fresh install (no existing prompt) → create canonical prompt + v1 active
      - Existing prompt with active version → no-op (preserves admin
        customization)
      - Existing prompt with no active version → create canonical v1 active
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
            # Preserves admin customization per canonical idempotent
            # seed pattern.
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
                "Phase 1C seed — Personalization Studio AI-extraction-"
                "review pipeline canonical."
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
        print(f"[phase1c-seed] Created {p} prompts, {v} versions.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
