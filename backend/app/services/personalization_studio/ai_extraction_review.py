"""Canonical AI-extraction-review pipeline service — Phase 1C of
Personalization Studio implementation arc Step 1.

Per §3.26.11.12.20 Generation Focus extraction adapter category +
§3.26.11.12.21 operational modes (review-by-default + reviewer paths
canonical) + §3.26.11.12.16 Anti-pattern 1 (auto-commit on extraction
confidence rejected) + DESIGN_LANGUAGE §14.14.3 visual canon.

**Three canonical service functions** mirroring canonical Phase 1C
managed Intelligence prompt registrations:

1. ``suggest_layout(db, instance_id, ...)`` — invokes canonical
   ``intelligence_service.execute()`` with canonical case data +
   selected vault product + canonical 4-options selections per
   §3.26.11.12.19.2 post-r74 vocabulary; returns canonical confidence-
   scored canvas layout suggestion line items.

2. ``suggest_text_style(db, instance_id, ...)`` — invokes canonical
   ``intelligence_service.execute()`` with canonical deceased name +
   family preferences; returns canonical confidence-scored font + size
   + color suggestion line items.

3. ``extract_decedent_info(db, instance_id, content_blocks, ...)`` —
   invokes canonical ``intelligence_service.execute()`` with canonical
   multimodal content_blocks (PDFs + images) per Phase 2c-0b multimodal
   substrate; returns canonical confidence-scored decedent extraction
   line items.

**Canonical anti-pattern guards explicit at service substrate**:

- §3.26.11.12.16 Anti-pattern 1 (auto-commit on extraction confidence
  rejected): service returns canonical confidence-scored line items;
  service does NOT mutate canvas state. Canonical operator agency at
  canonical Confirm action canonical at chrome substrate applies
  canonical line item to canvas state.
- §3.26.11.12.16 Anti-pattern 11 (UI-coupled Generation Focus design
  rejected): canonical structured output schema independent from
  canonical interactive UI; canonical line items canonical at
  canonical Intelligence prompt substrate; canonical chrome substrate
  consumes canonical line items via canonical Pattern 2 sub-cards
  per §14.14.3.
- §3.26.11.12.16 Anti-pattern 12 (parallel architectures for differently-
  sourced Generation Focus inputs rejected): canonical AI-extraction-
  review pipeline single canonical architecture across canonical
  adapter source categories. Canonical multimodal content_blocks
  substrate canonical at canonical extraction adapter category per
  §3.26.11.12.20.
- §2.4.4 Anti-pattern 8 (vertical-specific code creep): service is
  canonical Generation Focus AI-extraction-review substrate; canonical
  template_type discriminator dispatches to per-template canonical
  prompt key. Step 2 (Urn Vault Personalization Studio) inherits
  canonical service via canonical prompt key extension
  (``urn_vault_personalization.suggest_layout`` etc.).

**Canonical-pattern-establisher discipline at Phase 1C**: Step 2
(Urn Vault Personalization Studio) inherits canonical AI-extraction-
review pipeline via canonical Intelligence prompt naming convention
extension. Canonical service signature is canonical-template-type-
parameterized; canonical prompt key dispatches per template_type at
canonical service substrate.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.fh_case import FHCase
from app.models.funeral_case import CaseDeceased, FuneralCase
from app.models.generation_focus_instance import GenerationFocusInstance
from app.models.urn_product import UrnProduct
from app.services.intelligence import intelligence_service
from app.services.personalization_studio.instance_service import (
    PersonalizationStudioError,
    PersonalizationStudioNotFound,
    get_canvas_state,
    get_instance,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Canonical confidence tier vocabulary per §14.14.3 visual canon
# ─────────────────────────────────────────────────────────────────────


CONFIDENCE_TIER_HIGH = "high"      # ≥0.85 — canonical success chrome
CONFIDENCE_TIER_MEDIUM = "medium"  # 0.70-0.85 — canonical warning chrome
CONFIDENCE_TIER_LOW = "low"        # <0.70 — canonical error chrome

# Canonical thresholds per DESIGN_LANGUAGE §14.14.3.
CONFIDENCE_THRESHOLD_HIGH = 0.85
CONFIDENCE_THRESHOLD_MEDIUM = 0.70


def confidence_tier(confidence: float) -> str:
    """Canonical confidence tier per §14.14.3 thresholds.

    Read-side helper for chrome substrate consumers + canonical anti-
    pattern guard surfaces (canonical confidence threshold does NOT
    trigger canonical auto-commit per §3.26.11.12.16 Anti-pattern 1
    — canonical chrome substrate uses tier for visual treatment ONLY).
    """
    if confidence >= CONFIDENCE_THRESHOLD_HIGH:
        return CONFIDENCE_TIER_HIGH
    if confidence >= CONFIDENCE_THRESHOLD_MEDIUM:
        return CONFIDENCE_TIER_MEDIUM
    return CONFIDENCE_TIER_LOW


# ─────────────────────────────────────────────────────────────────────
# Canonical prompt key dispatch per template_type discriminator
# (canonical-pattern-establisher: Step 2 extends via prompt key
# naming convention)
# ─────────────────────────────────────────────────────────────────────


_PROMPT_KEY_DISPATCH: dict[str, dict[str, str]] = {
    "burial_vault_personalization_studio": {
        "suggest_layout": "burial_vault_personalization.suggest_layout",
        "suggest_text_style": "burial_vault_personalization.suggest_text_style",
        "extract_decedent_info": "burial_vault_personalization.extract_decedent_info",
    },
    # Step 2 substrate-consumption-follower extension per Phase 2B.
    # Urn-specific prompt keys at urn_vault_personalization.* namespace
    # (parallel to burial_vault_personalization.* namespace at canonical
    # Phase 1C).
    "urn_vault_personalization_studio": {
        "suggest_layout": "urn_vault_personalization.suggest_layout",
        "suggest_text_style": "urn_vault_personalization.suggest_text_style",
        "extract_decedent_info": "urn_vault_personalization.extract_decedent_info",
    },
}


def _resolve_prompt_key(template_type: str, suggestion_type: str) -> str:
    """Canonical prompt key dispatch per template_type discriminator."""
    template_dispatch = _PROMPT_KEY_DISPATCH.get(template_type)
    if template_dispatch is None:
        raise PersonalizationStudioError(
            f"No canonical Intelligence prompt dispatch for template_type "
            f"{template_type!r}; canonical Phase 1C canonical-pattern-"
            f"establisher value is 'burial_vault_personalization_studio'. "
            f"Step 2 extends."
        )
    prompt_key = template_dispatch.get(suggestion_type)
    if prompt_key is None:
        raise PersonalizationStudioError(
            f"No canonical Intelligence prompt for suggestion_type "
            f"{suggestion_type!r} on template_type {template_type!r}."
        )
    return prompt_key


# ─────────────────────────────────────────────────────────────────────
# Canonical canvas data marshalling helpers
# ─────────────────────────────────────────────────────────────────────


def _build_case_data_summary(
    db: Session, instance: GenerationFocusInstance
) -> str:
    """Build canonical case data summary string for canonical Intelligence
    prompt variable consumption.

    Per Q3 canonical authoring_context ↔ linked_entity_type pairing per
    §3.26.11.12.19.3 baked: ``funeral_home_with_family`` → fh_case;
    ``manufacturer_without_family`` → sales_order; ``manufacturer_from_fh_share``
    → document_share. This helper marshals canonical case data per
    authoring_context.
    """
    if instance.authoring_context == "funeral_home_with_family":
        # Canonical FH-vertical: fh_case linked. Pull deceased + service
        # info from canonical FuneralCase satellite tables.
        fh_case = (
            db.query(FuneralCase)
            .filter(FuneralCase.id == instance.linked_entity_id)
            .first()
        )
        if fh_case is None:
            return "(canonical FH case not found)"
        deceased = (
            db.query(CaseDeceased)
            .filter(CaseDeceased.case_id == fh_case.id)
            .first()
        )
        parts = [f"Case number: {fh_case.case_number}"]
        if deceased:
            parts.append(
                f"Deceased: {deceased.first_name or ''} "
                f"{deceased.middle_name or ''} {deceased.last_name or ''}".strip()
            )
            if deceased.date_of_birth:
                parts.append(f"Birth date: {deceased.date_of_birth.isoformat()}")
            if deceased.date_of_death:
                parts.append(f"Death date: {deceased.date_of_death.isoformat()}")
        return "; ".join(parts)
    elif instance.authoring_context == "manufacturer_without_family":
        # Canonical Mfg-vertical: sales_order linked. Phase 1C canonical
        # surfaces order metadata if available; full sales-order
        # marshalling is per-sales-order canonical at canonical service
        # consumer (Phase 1F integration). Phase 1C ships canonical
        # placeholder summary.
        return f"Sales order id: {instance.linked_entity_id}"
    elif instance.authoring_context == "manufacturer_from_fh_share":
        # Canonical read-only consume mode per §14.14.5. Phase 1C
        # canonical surfaces shared-document context placeholder.
        return f"Shared document id: {instance.linked_entity_id}"
    return "(canonical case data unavailable)"


def _build_vault_product_summary(canvas_state: dict | None) -> str:
    """Build canonical vault product summary from canonical canvas state."""
    if canvas_state is None:
        return "(no canvas state — pre-first-commit)"
    vault_product = canvas_state.get("vault_product") or {}
    name = vault_product.get("vault_product_name") or "(no product selected)"
    return f"Selected vault product: {name}"


def _build_active_options_summary(canvas_state: dict | None) -> str:
    """Build canonical 4-options canonical post-r74 summary."""
    if canvas_state is None:
        return "(no canvas state)"
    options = canvas_state.get("options") or {}
    active = [k for k, v in options.items() if v is not None]
    if not active:
        return "(no canonical options active)"
    return f"Active canonical options: {', '.join(active)}"


def _build_current_layout_summary(canvas_state: dict | None) -> str:
    """Build canonical current layout summary."""
    if canvas_state is None:
        return "(no canvas state — empty layout)"
    elements = (canvas_state.get("canvas_layout") or {}).get("elements") or []
    if not elements:
        return "(empty canvas — no elements placed)"
    parts = []
    for el in elements:
        el_type = el.get("element_type", "?")
        x = el.get("x", 0)
        y = el.get("y", 0)
        parts.append(f"{el_type} at ({x}, {y})")
    return "; ".join(parts)


def _build_deceased_name(canvas_state: dict | None) -> str:
    """Build canonical deceased name string from canonical canvas state."""
    if canvas_state is None:
        return "(no name — pre-first-commit)"
    return canvas_state.get("name_display") or "(no name set)"


# ─────────────────────────────────────────────────────────────────────
# Canonical service functions
# ─────────────────────────────────────────────────────────────────────


def _execute_intelligence_and_unwrap(
    db: Session,
    *,
    prompt_key: str,
    variables: dict[str, Any],
    company_id: str,
    caller_module: str,
    caller_entity_id: str,
    content_blocks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Canonical Intelligence backbone consumption helper.

    Invokes canonical ``intelligence_service.execute()`` with canonical
    caller linkage + canonical multimodal content_blocks (when provided);
    unwraps canonical line items from canonical structured output schema.

    Returns canonical payload shape:
      {
        "line_items": [
          {"line_item_key": str, "value": ..., "confidence": float,
           "rationale": str, "confidence_tier": str},
          ...
        ],
        "execution_id": str,
        "model_used": str,
        "latency_ms": int,
      }

    Per §3.26.11.12.16 Anti-pattern 11: canonical chrome substrate consumes
    canonical line items via canonical Pattern 2 sub-cards per §14.14.3.
    """
    result = intelligence_service.execute(
        db,
        prompt_key=prompt_key,
        variables=variables,
        company_id=company_id,
        caller_module=caller_module,
        caller_entity_type="generation_focus_instance",
        caller_entity_id=caller_entity_id,
        content_blocks=content_blocks,
    )

    parsed = result.response_parsed or {}
    raw_line_items = parsed.get("line_items") if isinstance(parsed, dict) else None
    if not isinstance(raw_line_items, list):
        raise PersonalizationStudioError(
            f"Intelligence response for {prompt_key!r} missing 'line_items' "
            f"array. Phase 1C Anti-pattern 1 schema substrate guard violated: "
            f"backbone returned response that does not satisfy declared "
            f"response_schema."
        )

    # Phase 1C strict line-item validation per §3.26.11.12.16 Anti-pattern 1
    # schema substrate guard. The backbone validator at
    # prompt_renderer.validate_response_against_schema is permissive by
    # design (top-level required only; nested items.required NOT
    # enforced). This loop surfaces malformed line items as service-layer
    # error rather than silently dropping them — preserves operator
    # visibility into canonical Intelligence response failures.
    line_items: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_line_items):
        if not isinstance(item, dict):
            raise PersonalizationStudioError(
                f"Intelligence response for {prompt_key!r} line_items[{idx}] "
                f"is not a dict; Anti-pattern 1 guard violated."
            )
        # Schema-declared required: ["line_item_key", "value", "confidence"].
        for required_field in ("line_item_key", "value", "confidence"):
            if required_field not in item:
                raise PersonalizationStudioError(
                    f"Intelligence response for {prompt_key!r} line_items[{idx}] "
                    f"missing required '{required_field}' field; Anti-pattern 1 "
                    f"schema substrate guard violated."
                )
        confidence = item["confidence"]
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            raise PersonalizationStudioError(
                f"Intelligence response for {prompt_key!r} line_items[{idx}] "
                f"confidence is not a number (got {type(confidence).__name__}); "
                f"Anti-pattern 1 schema substrate guard violated."
            )
        confidence_value = float(confidence)
        if not (0.0 <= confidence_value <= 1.0):
            raise PersonalizationStudioError(
                f"Intelligence response for {prompt_key!r} line_items[{idx}] "
                f"confidence {confidence_value} outside [0.0, 1.0] range; "
                f"Anti-pattern 1 schema substrate guard violated."
            )
        line_items.append(
            {
                "line_item_key": item.get("line_item_key"),
                "value": item.get("value"),
                "confidence": confidence_value,
                "rationale": item.get("rationale"),
                "confidence_tier": confidence_tier(confidence_value),
            }
        )

    return {
        "line_items": line_items,
        "execution_id": result.execution_id,
        "model_used": result.model_used,
        "latency_ms": result.latency_ms,
    }


def suggest_layout(
    db: Session,
    *,
    instance_id: str,
    company_id: str,
) -> dict[str, Any]:
    """Canonical canvas layout suggestion per Phase 1C canonical AI-
    extraction-review pipeline.

    Invokes canonical ``intelligence_service.execute()`` with canonical
    case data + canonical selected vault product + canonical 4-options
    selections; returns canonical confidence-scored canvas layout
    suggestion line items.

    Canonical anti-pattern guard: service returns canonical line items;
    service does NOT mutate canvas state per §3.26.11.12.16 Anti-pattern 1.
    Canonical Confirm action canonical at chrome substrate applies
    canonical line item to canvas state via canonical operator agency.

    Raises:
        PersonalizationStudioNotFound: instance_id not found or cross-tenant.
    """
    instance = get_instance(db, instance_id=instance_id, company_id=company_id)
    canvas_state = get_canvas_state(db, instance_id=instance_id)

    prompt_key = _resolve_prompt_key(instance.template_type, "suggest_layout")

    variables = {
        "case_data": _build_case_data_summary(db, instance),
        "vault_product": _build_vault_product_summary(canvas_state),
        "active_options": _build_active_options_summary(canvas_state),
        "current_layout": _build_current_layout_summary(canvas_state),
    }

    payload = _execute_intelligence_and_unwrap(
        db,
        prompt_key=prompt_key,
        variables=variables,
        company_id=company_id,
        caller_module="personalization_studio.ai_extraction_review.suggest_layout",
        caller_entity_id=instance_id,
    )

    logger.info(
        "personalization_studio.suggest_layout: instance=%s template=%s "
        "line_items=%d execution_id=%s",
        instance_id,
        instance.template_type,
        len(payload["line_items"]),
        payload["execution_id"],
    )
    return payload


def suggest_text_style(
    db: Session,
    *,
    instance_id: str,
    company_id: str,
    family_preferences: str | None = None,
) -> dict[str, Any]:
    """Canonical text style suggestion per Phase 1C canonical AI-
    extraction-review pipeline.

    Invokes canonical ``intelligence_service.execute()`` with canonical
    deceased name + family preferences; returns canonical confidence-
    scored font + size + color suggestion line items.

    Canonical anti-pattern guard: service returns canonical line items;
    canonical operator decides via canonical Confirm action at chrome
    substrate per §3.26.11.12.16 Anti-pattern 1.

    Raises:
        PersonalizationStudioNotFound: instance_id not found or cross-tenant.
    """
    instance = get_instance(db, instance_id=instance_id, company_id=company_id)
    canvas_state = get_canvas_state(db, instance_id=instance_id)

    prompt_key = _resolve_prompt_key(instance.template_type, "suggest_text_style")

    variables = {
        "deceased_name": _build_deceased_name(canvas_state),
        "family_preferences": (
            family_preferences or "(no family preferences provided)"
        ),
    }

    payload = _execute_intelligence_and_unwrap(
        db,
        prompt_key=prompt_key,
        variables=variables,
        company_id=company_id,
        caller_module=(
            "personalization_studio.ai_extraction_review.suggest_text_style"
        ),
        caller_entity_id=instance_id,
    )

    logger.info(
        "personalization_studio.suggest_text_style: instance=%s template=%s "
        "line_items=%d execution_id=%s",
        instance_id,
        instance.template_type,
        len(payload["line_items"]),
        payload["execution_id"],
    )
    return payload


def extract_decedent_info(
    db: Session,
    *,
    instance_id: str,
    company_id: str,
    content_blocks: list[dict[str, Any]],
    context_summary: str | None = None,
) -> dict[str, Any]:
    """Canonical multimodal decedent info extraction per Phase 1C
    canonical AI-extraction-review pipeline + canonical Phase 2c-0b
    multimodal content_blocks substrate.

    Invokes canonical ``intelligence_service.execute()`` with canonical
    multimodal content_blocks (PDFs + images); returns canonical
    confidence-scored decedent extraction line items (name parts,
    dates, emblem hints, nameplate text hints).

    Canonical anti-pattern guard: service returns canonical line items;
    canonical operator decides via canonical Confirm action at chrome
    substrate per §3.26.11.12.16 Anti-pattern 1.

    Args:
        instance_id: canonical Generation Focus instance UUID
        company_id: canonical tenant scoping
        content_blocks: canonical Phase 2c-0b multimodal content_blocks
            list (each block: ``{"type": "image"|"document",
            "source": {"type": "base64", "media_type": ..., "data": ...}}``)
        context_summary: optional canonical text context (e.g., "Death
            certificate from County clerk; obituary from local newspaper")

    Raises:
        PersonalizationStudioNotFound: instance_id not found or cross-tenant.
        PersonalizationStudioError: content_blocks empty or malformed.
    """
    if not content_blocks:
        raise PersonalizationStudioError(
            "Canonical extract_decedent_info requires at least one canonical "
            "content_block (PDF or image) per Phase 2c-0b multimodal substrate."
        )

    instance = get_instance(db, instance_id=instance_id, company_id=company_id)

    prompt_key = _resolve_prompt_key(
        instance.template_type, "extract_decedent_info"
    )

    variables = {
        "context_summary": (
            context_summary
            or f"Source materials for canonical decedent extraction; "
            f"{len(content_blocks)} canonical content block(s) provided."
        ),
    }

    payload = _execute_intelligence_and_unwrap(
        db,
        prompt_key=prompt_key,
        variables=variables,
        company_id=company_id,
        caller_module=(
            "personalization_studio.ai_extraction_review.extract_decedent_info"
        ),
        caller_entity_id=instance_id,
        content_blocks=content_blocks,
    )

    logger.info(
        "personalization_studio.extract_decedent_info: instance=%s template=%s "
        "content_blocks=%d line_items=%d execution_id=%s",
        instance_id,
        instance.template_type,
        len(content_blocks),
        len(payload["line_items"]),
        payload["execution_id"],
    )
    return payload
