"""Phase 6 — narrative + structured-section generation via Intelligence.

Fires `briefing.morning` or `briefing.evening` managed prompts with a
flat variable payload distilled from `BriefingDataContext`. Haiku-backed
per the cost estimate in the Phase 6 audit.

The prompt output shape (enforced via force_json):
  {
    "narrative_text": "Good morning, James. ...",
    "structured_sections": {
      "greeting": "...",
      "overnight_summary": {...},
      ...
    }
  }

Missing / failed generation falls back to a stub narrative + empty
sections — callers (API + sweep) surface the failure but do NOT crash.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.user import User
from app.services.briefings.types import (
    BriefingDataContext,
    BriefingType,
    GeneratedBriefing,
    StructuredSections,
)

logger = logging.getLogger(__name__)


class GenerationError(Exception):
    """Raised on unrecoverable generation failure.

    Most call sites catch this and return a stub briefing instead so the
    user always sees something — but unit tests need a loud signal when
    the Intelligence layer is down.
    """


# ── Public entry points ─────────────────────────────────────────────


def generate_morning_briefing(
    db: Session,
    user: User,
    data_context: BriefingDataContext,
    *,
    raise_on_failure: bool = False,
) -> GeneratedBriefing:
    return _generate(
        db,
        user,
        data_context,
        briefing_type="morning",
        prompt_key="briefing.morning",
        raise_on_failure=raise_on_failure,
    )


def generate_evening_briefing(
    db: Session,
    user: User,
    data_context: BriefingDataContext,
    *,
    raise_on_failure: bool = False,
) -> GeneratedBriefing:
    return _generate(
        db,
        user,
        data_context,
        briefing_type="evening",
        prompt_key="briefing.evening",
        raise_on_failure=raise_on_failure,
    )


# ── Implementation ──────────────────────────────────────────────────


def _generate(
    db: Session,
    user: User,
    ctx: BriefingDataContext,
    *,
    briefing_type: BriefingType,
    prompt_key: str,
    raise_on_failure: bool,
) -> GeneratedBriefing:
    start = time.monotonic()

    variables = _build_variables(ctx)

    # Call Intelligence. The prompt's force_json=True forces structured
    # output; we parse into StructuredSections via Pydantic.
    result = None
    error_message: str | None = None
    try:
        from app.services.intelligence import intelligence_service

        result = intelligence_service.execute(
            db,
            prompt_key=prompt_key,
            variables=variables,
            company_id=user.company_id,
            caller_module="briefings",
            caller_entity_type="user",
            caller_entity_id=user.id,
        )
    except Exception as exc:  # pragma: no cover — defensive
        error_message = f"intelligence call raised: {exc}"
        logger.exception("Briefing generation (%s) raised", briefing_type)

    duration_ms = int((time.monotonic() - start) * 1000)

    narrative_text: str = ""
    sections: StructuredSections
    input_tokens = output_tokens = 0
    cost: Decimal | None = None

    if result is None or getattr(result, "status", None) != "success":
        status = getattr(result, "status", "no_result") if result else "no_result"
        error_message = error_message or f"intelligence status={status}"
        if raise_on_failure:
            raise GenerationError(error_message)
        # Fallback content so the user sees something.
        narrative_text, sections = _fallback_content(ctx, briefing_type)
    else:
        parsed = result.response_parsed or {}
        narrative_text, sections = _parse_generation_response(
            parsed, ctx, briefing_type
        )
        input_tokens = result.input_tokens or 0
        output_tokens = result.output_tokens or 0
        cost = result.cost_usd

    return GeneratedBriefing(
        briefing_type=briefing_type,
        narrative_text=narrative_text,
        structured_sections=sections,
        active_space_id=ctx.active_space_id,
        active_space_name=ctx.active_space_name,
        role_slug=ctx.role_slug,
        generation_context={
            "requested_sections": list(ctx.requested_sections),
            "vertical": ctx.vertical,
            "narrative_tone": ctx.narrative_tone,
            "queue_count_total": sum(
                int(q.get("pending_count") or 0) for q in ctx.queue_summaries
            ),
            "overnight_calls_present": ctx.overnight_calls is not None,
            "event_count_today": len(ctx.today_events),
            "event_count_tomorrow": len(ctx.tomorrow_events),
            "error_message": error_message,
        },
        generation_duration_ms=duration_ms,
        intelligence_cost_usd=cost,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def _build_variables(ctx: BriefingDataContext) -> dict[str, Any]:
    """Flatten BriefingDataContext into a prompt variable payload.

    Kept deliberately flat + JSON-safe. The Jinja template references
    variables by name; nesting discipline belongs in the prompt.
    """
    return {
        "user_first_name": ctx.user_first_name,
        "user_last_name": ctx.user_last_name or "",
        "company_name": ctx.company_name or "",
        "role_slug": ctx.role_slug or "",
        "vertical": ctx.vertical or "manufacturing",
        "today_iso": ctx.today_iso,
        "day_of_week": ctx.day_of_week,
        "now_iso": ctx.now_iso,
        "active_space_id": ctx.active_space_id or "",
        "active_space_name": ctx.active_space_name or "",
        "narrative_tone": ctx.narrative_tone,
        "requested_sections": list(ctx.requested_sections),
        "legacy_context": ctx.legacy_context,
        "queue_summaries": ctx.queue_summaries,
        "overnight_calls": ctx.overnight_calls or {},
        "today_events": ctx.today_events,
        "tomorrow_events": ctx.tomorrow_events,
        "pending_approvals": ctx.pending_approvals,
        "flagged_items": ctx.flagged_items,
        "day_completed_items": ctx.day_completed_items,
    }


def _parse_generation_response(
    parsed: dict | list,
    ctx: BriefingDataContext,
    briefing_type: BriefingType,
) -> tuple[str, StructuredSections]:
    """Pull narrative_text + structured_sections out of the prompt response.

    Accepts a {narrative_text, structured_sections} payload. Unknown-shape
    responses fall back to the stub narrative. StructuredSections validates
    with `extra="forbid"` so unexpected keys in the AI output raise (and
    we catch → stub).
    """
    if not isinstance(parsed, dict):
        return _fallback_content(ctx, briefing_type)
    narrative = parsed.get("narrative_text") or parsed.get("narrative") or ""
    sections_raw = parsed.get("structured_sections") or {}
    if not isinstance(narrative, str) or not narrative.strip():
        return _fallback_content(ctx, briefing_type)
    try:
        sections = StructuredSections.model_validate(sections_raw)
    except Exception as e:
        logger.warning(
            "Briefing AI response failed sections validation: %s", e
        )
        # Narrative stays; sections go empty.
        sections = StructuredSections()
    return narrative.strip(), sections


def _fallback_content(
    ctx: BriefingDataContext, briefing_type: BriefingType
) -> tuple[str, StructuredSections]:
    """Generate a deterministic stub when Intelligence is unavailable.

    Not pretty, but the user sees non-empty content + can retry. Kept
    factual so it never misleads — literally lists raw counts from the
    data context.
    """
    name = ctx.user_first_name or "there"
    time_phrase = "Good morning" if briefing_type == "morning" else "Evening"
    queue_total = sum(
        int(q.get("pending_count") or 0) for q in ctx.queue_summaries
    )
    parts = [f"{time_phrase}, {name}. It's {ctx.day_of_week}."]
    if ctx.today_events:
        parts.append(f"You have {len(ctx.today_events)} events today.")
    if queue_total:
        parts.append(
            f"{queue_total} item{'s' if queue_total != 1 else ''} in your triage queues."
        )
    if ctx.overnight_calls:
        oc = ctx.overnight_calls
        voicemails = int(oc.get("voicemails") or 0)
        if voicemails:
            parts.append(
                f"{voicemails} voicemail{'s' if voicemails != 1 else ''} overnight."
            )
    narrative = " ".join(parts)
    sections = StructuredSections(
        greeting=parts[0],
    )
    return narrative, sections


__all__ = [
    "generate_morning_briefing",
    "generate_evening_briefing",
    "GenerationError",
]
