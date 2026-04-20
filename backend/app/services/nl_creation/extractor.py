"""NL extractor — orchestration.

Pipeline for `/api/v1/nl-creation/extract`:
  1. Load entity config from registry (404 if unknown).
  2. Run structured parsers on the NL input (all parallel in spirit,
     but Python GIL + tiny CPU cost makes serial fine).
  3. Run entity resolvers for fields whose structured_parser didn't
     hit AND whose field_type is "entity" or whose config declares
     an `entity_resolver_config`. Parallel via asyncio.gather would
     help at scale; Phase 4 runs serial (still well under budget).
  4. If any required field is still missing, call the Intelligence
     prompt for AI fallback.
  5. Merge prior_extractions (preserving user edits) with new
     extractions; last-write-wins only for fields with higher
     confidence OR matching source (user manual edits override).
  6. Apply space_defaults for fields the user didn't mention.
  7. Compute missing_required.

Performance targets (BLOCKING CI gate):
  p50 < 600ms, p99 < 1200ms. Dominated by Intelligence call (~400ms).
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.user import User
from app.services.nl_creation import entity_resolver as resolver_mod
from app.services.nl_creation.ai_extraction import run_ai_extraction
from app.services.nl_creation.entity_registry import get_entity_config
from app.services.nl_creation.types import (
    ExtractionRequest,
    ExtractionResult,
    ExtractionSource,
    FieldExtraction,
    FieldExtractor,
    NLEntityConfig,
    UnknownEntityType,
)

logger = logging.getLogger(__name__)


# ── Candidate extraction for entity-typed fields ─────────────────────
# We scan the NL input for a few likely "name-shaped" substrings per
# entity field (e.g. " Hopkins FH " in the middle of a longer
# sentence). Heuristic: the structured parser didn't hit, so try
# resolver-candidate substrings of 1-5 tokens starting at capitalized
# tokens OR known vocabulary markers ("at", "FH", "funeral home").
# Worst case: ~20 candidate substrings × 30ms resolve = 600ms. We
# cap at 5 candidates and dedup. For most real inputs this resolves
# to 1-2 actual DB lookups.


_CANDIDATE_TOKEN_RX = re.compile(r"\b([A-Z][A-Za-z0-9&.'-]*(?:\s+[A-Z][A-Za-z0-9&.'-]*)*)\b")
_MAX_CANDIDATES_PER_FIELD: int = 5


def _candidate_substrings(text: str) -> list[str]:
    """Return up to _MAX_CANDIDATES_PER_FIELD capitalized substrings
    to try resolving. Deduped, preserving order."""
    if not text:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for m in _CANDIDATE_TOKEN_RX.finditer(text):
        cand = m.group(1).strip()
        if cand.lower() in seen:
            continue
        seen.add(cand.lower())
        out.append(cand)
        if len(out) >= _MAX_CANDIDATES_PER_FIELD:
            break
    return out


# ── Structured pass ──────────────────────────────────────────────────


def _run_structured(
    natural_language: str, config: NLEntityConfig
) -> list[FieldExtraction]:
    """Run every field extractor's structured_parser on the full input.

    Each parser scans the whole text and returns None or a hit.
    Returns the list of FieldExtraction objects for hits.
    """
    out: list[FieldExtraction] = []
    for fx in config.field_extractors:
        if fx.structured_parser is None:
            continue
        try:
            result = fx.structured_parser(natural_language)
        except Exception:
            logger.exception("structured parser for %s raised", fx.field_key)
            continue
        if not result:
            continue
        out.append(
            FieldExtraction(
                field_key=fx.field_key,
                field_label=fx.field_label,
                extracted_value=result.get("value"),
                display_value=result.get("display") or str(result.get("value")),
                confidence=float(result.get("confidence", 0.85)),
                source="structured_parser",
            )
        )
    return out


# ── Entity-resolver pass ─────────────────────────────────────────────


def _run_entity_resolvers(
    db: Session,
    user: User,
    natural_language: str,
    config: NLEntityConfig,
    already_keys: set[str],
) -> list[FieldExtraction]:
    """Resolve candidate substrings against vault entities for each
    entity-typed field not already extracted. Top-1 per field."""
    out: list[FieldExtraction] = []
    candidates = _candidate_substrings(natural_language)
    if not candidates:
        return out

    for fx in config.field_extractors:
        if fx.field_key in already_keys:
            continue
        cfg = fx.entity_resolver_config
        if cfg is None:
            continue
        target = cfg.get("target")
        if not target:
            continue
        filters = cfg.get("filters") or {}
        threshold = float(cfg.get("similarity_threshold") or 0.35)

        best_hit = None
        for cand in candidates:
            try:
                hit = resolver_mod.resolve(
                    db,
                    target=target,
                    query=cand,
                    user=user,
                    filters=filters,
                    similarity_threshold=threshold,
                )
            except Exception:
                logger.exception("entity resolver raised for %s", fx.field_key)
                continue
            if hit is None:
                continue
            if best_hit is None or hit.similarity > best_hit[1].similarity:
                best_hit = (cand, hit)

        if best_hit is None:
            continue

        cand_text, hit = best_hit
        out.append(
            FieldExtraction(
                field_key=fx.field_key,
                field_label=fx.field_label,
                extracted_value=hit.entity_id,
                display_value=hit.display_name,
                confidence=min(0.98, max(0.6, hit.similarity + 0.3)),
                source="entity_resolver",
                resolved_entity_id=hit.entity_id,
                resolved_entity_type=hit.entity_type,
            )
        )
    return out


# ── Space defaults ──────────────────────────────────────────────────


def _apply_space_defaults(
    config: NLEntityConfig,
    extractions: list[FieldExtraction],
    active_space_name_lower: str | None,
) -> list[str]:
    """Mutate `extractions` in place with space-default entries for
    fields the user didn't mention. Returns the list of field_keys
    sourced from a space default."""
    if not active_space_name_lower:
        return []
    defaults = config.space_defaults.get(active_space_name_lower)
    if not defaults:
        return []
    existing = {e.field_key for e in extractions}
    applied: list[str] = []
    for field_key, value in defaults.items():
        # Sentinel keys starting with "_" are telemetry only, not real
        # field defaults.
        if field_key.startswith("_") or field_key in existing:
            continue
        fx = config.field_by_key(field_key)
        if fx is None:
            continue
        extractions.append(
            FieldExtraction(
                field_key=field_key,
                field_label=fx.field_label,
                extracted_value=value,
                display_value=str(value),
                confidence=0.85,
                source="space_default",
            )
        )
        applied.append(field_key)
    return applied


# ── Merge prior + new ───────────────────────────────────────────────


def _merge_prior(
    prior: list[FieldExtraction], new: list[FieldExtraction]
) -> list[FieldExtraction]:
    """Combine prior extractions (from the client) with fresh
    extractions. Rule set:
      - New wins by default — fresh structured/resolver/AI output
        reflects the current input.
      - Prior wins IF the prior was a manual user edit (source
        still counts as its original source but confidence was
        bumped to 1.0 by the client) AND the prior confidence is >=
        the new's.

    Implementation: prefer higher confidence; tie break to new.
    """
    by_key: dict[str, FieldExtraction] = {}
    for e in prior:
        by_key[e.field_key] = e
    for e in new:
        existing = by_key.get(e.field_key)
        if existing is None or e.confidence >= existing.confidence:
            by_key[e.field_key] = e
    return list(by_key.values())


# ── Missing required ────────────────────────────────────────────────


def _missing_required(
    config: NLEntityConfig, extractions: list[FieldExtraction]
) -> list[str]:
    extracted_keys = {e.field_key for e in extractions}
    return [fk for fk in config.required_fields if fk not in extracted_keys]


# ── Space name lookup ────────────────────────────────────────────────


def _resolve_active_space_name(
    user: User, active_space_id: str | None
) -> str | None:
    if not active_space_id:
        return None
    prefs = user.preferences or {}
    for sp in prefs.get("spaces") or []:
        if sp.get("space_id") == active_space_id:
            name = sp.get("name")
            if name:
                return str(name).lower()
    return None


# ── Entry point ──────────────────────────────────────────────────────


def extract(
    db: Session,
    *,
    request: ExtractionRequest,
    user: User,
) -> ExtractionResult:
    """Run the NL extraction pipeline and return a typed result.

    `request.natural_language` is the user's live input. The caller
    (API layer) passes `user` for tenant + preference access; the
    request's tenant_id/user_id are validated equal to the caller
    upstream.
    """
    config = get_entity_config(request.entity_type)
    if config is None:
        raise UnknownEntityType(
            f"Unknown entity_type: {request.entity_type}"
        )

    t0 = time.perf_counter()
    natural_language = (request.natural_language or "").strip()

    # Empty input → return empty result (overlay renders nothing).
    if not natural_language:
        return ExtractionResult(
            entity_type=request.entity_type,
            extractions=[],
            missing_required=config.required_fields,
            raw_input=natural_language,
            extraction_ms=int((time.perf_counter() - t0) * 1000),
        )

    # 1. Structured parsers
    structured = _run_structured(natural_language, config)

    # 2. Entity resolvers on fields the parsers missed
    already_keys = {e.field_key for e in structured}
    resolved = _run_entity_resolvers(
        db, user, natural_language, config, already_keys
    )

    combined = structured + resolved

    # 3. AI fallback — call if ANY required field still missing OR
    # no extractions at all yet. Always call if missing; skip only
    # when all fields captured (optimization for when the structured
    # pass is fully sufficient).
    missing_after_structured = set(config.required_fields) - {
        e.field_key for e in combined
    }
    ai_exec_id: str | None = None
    ai_latency_ms: int | None = None
    if missing_after_structured or not combined:
        active_space_name = _resolve_active_space_name(
            user, request.active_space_id
        )
        ai_extractions, ai_exec_id, ai_latency_ms = run_ai_extraction(
            db,
            config=config,
            natural_language=natural_language,
            user=user,
            active_space_name=active_space_name,
            structured_extractions=combined,
            active_space_id=request.active_space_id,
        )
        combined = combined + ai_extractions

    # 4. Merge with prior extractions (preserve user edits)
    merged = _merge_prior(request.prior_extractions, combined)

    # 5. Space defaults (applied last so they never override user input)
    space_name_lower = _resolve_active_space_name(user, request.active_space_id)
    space_defaulted = _apply_space_defaults(config, merged, space_name_lower)

    # 6. Missing required (post-merge, post-defaults)
    missing = _missing_required(config, merged)

    return ExtractionResult(
        entity_type=request.entity_type,
        extractions=merged,
        missing_required=missing,
        raw_input=natural_language,
        extraction_ms=int((time.perf_counter() - t0) * 1000),
        ai_execution_id=ai_exec_id,
        ai_latency_ms=ai_latency_ms,
        space_default_fields=space_defaulted,
    )


# ── Creation entry point ─────────────────────────────────────────────


def create(
    db: Session,
    *,
    user: User,
    entity_type: str,
    extractions: list[FieldExtraction],
    raw_input: str,
) -> dict[str, Any]:
    """Materialize the entity via the config's creator_callable.

    The creator handles tenant scoping + required-field validation
    at the model-shape level (e.g. Contact requires master_company_id).
    Re-raises `CreationValidationError` on missing required fields —
    the API layer translates to 400.
    """
    config = get_entity_config(entity_type)
    if config is None:
        raise UnknownEntityType(f"Unknown entity_type: {entity_type}")
    return config.creator_callable(db, user, extractions, raw_input)


# Suppress unused-import warnings for types referenced only by
# re-export / annotation (mypy-strict loves to complain).
_ = (Company, date, FieldExtractor, ExtractionSource)


__all__ = ["extract", "create"]
