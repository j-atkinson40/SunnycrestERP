"""AI extraction fallback via Intelligence layer.

When structured parsers + entity resolver leave required fields
unfilled, call Claude to extract the remainder. The Intelligence
layer handles prompt rendering, model routing (Haiku via
`simple` route), cost/latency audit rows, and force-JSON output.

This module builds the prompt variable blocks and parses the
returned JSON into `FieldExtraction` objects. The prompt template
itself lives in the managed Intelligence prompts (seeded by
`scripts/seed_intelligence.py` under keys
`nl_creation.extract.{entity_type}`).

Latency: the Intelligence call dominates p50 (~300-500ms on Haiku).
Structured parse + resolver is <100ms combined.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.user import User
from app.services.intelligence import intelligence_service
from app.services.nl_creation.types import (
    ExtractionSource,
    FieldExtraction,
    FieldExtractor,
    NLEntityConfig,
)

logger = logging.getLogger(__name__)


# ── Prompt variable rendering ────────────────────────────────────────


def _render_field_descriptions(
    config: NLEntityConfig,
    skip_fields: set[str],
) -> str:
    """Render the `field_descriptions` block the AI prompt consumes.

    Skips fields already extracted by structured parsers / resolver
    so the model focuses on genuine gaps.
    """
    lines: list[str] = []
    for fx in config.field_extractors:
        if fx.field_key in skip_fields:
            continue
        parts = [f"- {fx.field_key} ({fx.field_type}): {fx.field_label}"]
        if fx.required:
            parts.append("[required]")
        if fx.enum_values:
            parts.append("allowed=" + "|".join(fx.enum_values))
        if fx.ai_hint:
            parts.append(f"hint: {fx.ai_hint}")
        lines.append(" ".join(parts))
    return "\n".join(lines) or "(no remaining fields)"


def _render_structured_extractions(
    extractions: list[FieldExtraction],
) -> str:
    """Render the `structured_extractions` block: what we already
    captured before calling AI. Model preserves these verbatim."""
    if not extractions:
        return "(none)"
    lines = []
    for e in extractions:
        lines.append(
            f"- {e.field_key}: {e.display_value} "
            f"(source={e.source}, confidence={e.confidence:.2f})"
        )
    return "\n".join(lines)


def _render_tenant_context(user: User) -> str:
    co = getattr(user, "company", None)
    if co is None:
        return "tenant: (unknown)"
    parts = [f"tenant: {co.name}"]
    vertical = getattr(co, "vertical", None)
    if vertical:
        parts.append(f"vertical: {vertical}")
    return " · ".join(parts)


def _render_space_context(active_space_name: str | None) -> str:
    if not active_space_name:
        return "(no active space)"
    return f"active space: {active_space_name}"


# ── Parsing the AI response ──────────────────────────────────────────


def _coerce_extraction(
    config: NLEntityConfig,
    field_key: str,
    raw_value: Any,
    confidence: float,
    source: ExtractionSource = "ai_extraction",
) -> FieldExtraction | None:
    """Build a FieldExtraction from a single AI-returned payload.

    Drops fields not in the entity config; coerces empty/null values
    to None (returns None to signal skip). Display value falls back
    to str(raw_value) — structured_parsers already formatted theirs.
    """
    fx = config.field_by_key(field_key)
    if fx is None:
        return None
    if raw_value is None:
        return None
    if isinstance(raw_value, str) and not raw_value.strip():
        return None
    display = str(raw_value)
    if isinstance(raw_value, dict):
        # For "name"-type fields the parser returns a dict; mirror.
        # The AI may return nested dicts; stringify deterministically.
        display = ", ".join(f"{k}={v}" for k, v in raw_value.items() if v)
    return FieldExtraction(
        field_key=field_key,
        field_label=fx.field_label,
        extracted_value=raw_value,
        display_value=display,
        confidence=float(max(0.0, min(1.0, confidence))),
        source=source,
    )


# ── Entry point ──────────────────────────────────────────────────────


def run_ai_extraction(
    db: Session,
    *,
    config: NLEntityConfig,
    natural_language: str,
    user: User,
    active_space_name: str | None,
    structured_extractions: list[FieldExtraction],
    active_space_id: str | None = None,
) -> tuple[list[FieldExtraction], str | None, int | None]:
    """Run the Intelligence prompt for this entity type.

    Returns (new_ai_extractions, execution_id, latency_ms).
    `new_ai_extractions` only includes fields NOT already in
    `structured_extractions` — the orchestrator merges.

    Errors return ([], None, None) — caller continues with what it
    has. Failures are logged via Intelligence's own audit row.
    """
    if not natural_language or not natural_language.strip():
        return ([], None, None)

    already_keys = {e.field_key for e in structured_extractions}
    variables = {
        "entity_type": config.entity_type,
        "natural_language": natural_language,
        "tenant_context": _render_tenant_context(user),
        "space_context": _render_space_context(active_space_name),
        "field_descriptions": _render_field_descriptions(config, already_keys),
        "structured_extractions": _render_structured_extractions(
            structured_extractions
        ),
    }

    try:
        result = intelligence_service.execute(
            db,
            prompt_key=config.ai_prompt_key,
            variables=variables,
            company_id=user.company_id,
            caller_module="nl_creation.ai_extraction",
            caller_entity_type=config.entity_type,
            caller_entity_id=None,
        )
    except Exception:
        logger.exception(
            "AI extraction failed for entity_type=%s prompt_key=%s",
            config.entity_type, config.ai_prompt_key,
        )
        return ([], None, None)

    if result.status != "success" or not isinstance(result.response_parsed, dict):
        logger.warning(
            "AI extraction non-success: status=%s error=%s",
            result.status, result.error_message,
        )
        return ([], result.execution_id, result.latency_ms)

    payload = result.response_parsed
    # Accepted shapes from the prompt:
    #   {"extractions": [{"field_key": "...", "value": ..., "confidence": 0-1}]}
    #   OR legacy: {"<field_key>": {"value": ..., "confidence": 0-1}}
    ai_extractions: list[FieldExtraction] = []
    raw_list = payload.get("extractions")
    if isinstance(raw_list, list):
        for entry in raw_list:
            if not isinstance(entry, dict):
                continue
            fk = entry.get("field_key")
            if not fk or fk in already_keys:
                continue
            conf = _coerce_float(entry.get("confidence"), default=0.7)
            ext = _coerce_extraction(config, fk, entry.get("value"), conf)
            if ext:
                ai_extractions.append(ext)
    else:
        # Legacy shape support.
        for fk, entry in payload.items():
            if fk == "extractions":
                continue
            if fk in already_keys:
                continue
            if not isinstance(entry, dict):
                continue
            conf = _coerce_float(entry.get("confidence"), default=0.7)
            ext = _coerce_extraction(config, fk, entry.get("value"), conf)
            if ext:
                ai_extractions.append(ext)

    # Use `active_space_id` kwarg below only for debugging — the prompt
    # already sees space_name in the variables block. We accept the
    # id kwarg to keep the call signature uniform with the extractor
    # orchestrator's call site.
    _ = active_space_id

    return (ai_extractions, result.execution_id, result.latency_ms)


def _coerce_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


__all__ = ["run_ai_extraction"]
