"""Phase 6 — typed models for briefings.

All shapes are Pydantic with `extra="forbid"` (Phase 5 discipline) so
unknown fields in persisted preferences trigger loud errors rather than
silent drift. Shapes round-trip via `model_dump(mode="json")` /
`model_validate()`.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ── Literal sets ─────────────────────────────────────────────────────

BriefingType = Literal["morning", "evening"]

# The full universe of section keys. Prompts + frontend use these keys as
# a stable contract. Adding a new section = add here + update prompt +
# update UI renderer.
BriefingSectionKey = Literal[
    # Morning
    "greeting",
    "overnight_summary",
    "overnight_calls",
    "today_calendar",
    "pending_decisions",
    "queue_summaries",
    "flags",
    # Evening
    "day_summary",
    "pending_decisions_remaining",
    "tomorrow_preview",
    "flagged_for_tomorrow",
    "loose_threads",
]

DeliveryChannel = Literal["in_app", "email"]

MORNING_DEFAULT_SECTIONS: list[str] = [
    "greeting",
    "overnight_summary",
    "overnight_calls",
    "today_calendar",
    "pending_decisions",
    "queue_summaries",
    "flags",
]
EVENING_DEFAULT_SECTIONS: list[str] = [
    "day_summary",
    "pending_decisions_remaining",
    "tomorrow_preview",
    "flagged_for_tomorrow",
    "loose_threads",
]

DEFAULT_MORNING_TIME = "07:00"
DEFAULT_EVENING_TIME = "17:00"


# ── User preferences ─────────────────────────────────────────────────


class BriefingPreferences(BaseModel):
    """Stored at `User.preferences.briefing_preferences`.

    Phase 6 preferences layer on top of the existing tenant-level
    `briefings_enabled_tenant_wide` + `briefing_delivery_time` settings
    and the existing `ai_settings_service.briefing_narrative_tone` value.
    We do NOT duplicate tone here — it's read at generation time from
    `ai_settings_service`.
    """

    model_config = ConfigDict(extra="forbid")

    morning_enabled: bool = True
    morning_delivery_time: str = DEFAULT_MORNING_TIME  # HH:MM in tenant TZ
    morning_channels: list[str] = Field(
        default_factory=lambda: ["in_app", "email"]
    )
    morning_sections: list[str] = Field(
        default_factory=lambda: list(MORNING_DEFAULT_SECTIONS)
    )

    evening_enabled: bool = True
    evening_delivery_time: str = DEFAULT_EVENING_TIME
    evening_channels: list[str] = Field(default_factory=lambda: ["in_app"])
    evening_sections: list[str] = Field(
        default_factory=lambda: list(EVENING_DEFAULT_SECTIONS)
    )


# ── Structured sections (prompt output) ──────────────────────────────


class StructuredSections(BaseModel):
    """Machine-readable decomposition of the narrative.

    Stored at `briefings.structured_sections` JSONB. Every section is
    optional — the prompt emits only those requested by the user's
    preferences AND supported by the data context. UI renders sections
    as expandable cards below the prose.
    """

    model_config = ConfigDict(extra="forbid")

    greeting: str | None = None

    # Morning sections
    overnight_summary: dict[str, Any] | None = None
    overnight_calls: dict[str, Any] | None = None
    today_calendar: dict[str, Any] | None = None
    pending_decisions: list[dict[str, Any]] | None = None
    queue_summaries: list[dict[str, Any]] | None = None
    flags: list[dict[str, Any]] | None = None

    # Evening sections
    day_summary: dict[str, Any] | None = None
    pending_decisions_remaining: list[dict[str, Any]] | None = None
    tomorrow_preview: dict[str, Any] | None = None
    flagged_for_tomorrow: list[dict[str, Any]] | None = None
    loose_threads: list[dict[str, Any]] | None = None


# ── Generator return shape ──────────────────────────────────────────


class GeneratedBriefing(BaseModel):
    """Returned by `generator.generate_morning_briefing` / `_evening_briefing`.

    The caller (API handler or scheduler sweep) persists this as a
    Briefing row + dispatches delivery per preferences.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    briefing_type: BriefingType
    narrative_text: str
    structured_sections: StructuredSections
    active_space_id: str | None = None
    active_space_name: str | None = None
    role_slug: str | None = None
    generation_context: dict[str, Any] | None = None
    generation_duration_ms: int | None = None
    intelligence_cost_usd: Decimal | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


# ── Data context (assembled by data_sources.py, fed into prompt) ────


class BriefingDataContext(BaseModel):
    """Raw material collected by `data_sources` + fed into the prompt.

    Everything here is derived from READS — this context struct never
    mutates state. `generator.py` turns it into prompt variables.

    Fields are intentionally wide (Any/dict) because the legacy context
    builders return heterogeneous shapes we intentionally don't retype
    — they're already production-proven.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    # Identity + scope
    user_id: str
    user_first_name: str
    user_last_name: str | None = None
    company_id: str
    company_name: str | None = None
    role_slug: str | None = None
    vertical: str | None = None

    # Time context (ISO timestamps; prompt converts to human phrasing)
    today_iso: str
    day_of_week: str  # "Monday", "Tuesday", ...
    now_iso: str
    since_last_briefing_iso: str | None = None

    # Active space (Phase 3 integration)
    active_space_id: str | None = None
    active_space_name: str | None = None

    # Legacy context builder output (reused verbatim)
    legacy_context: dict[str, Any] = Field(default_factory=dict)

    # Phase 5 triage integration
    queue_summaries: list[dict[str, Any]] = Field(default_factory=list)
    # Each: {queue_id, queue_name, pending_count, estimated_time_minutes}

    # Phase 2 saved-view integration (on-demand)
    saved_view_results: dict[str, Any] = Field(default_factory=dict)

    # Call Intelligence (Phase 6 — preserves legacy _build_call_summary)
    overnight_calls: dict[str, Any] | None = None

    # Calendar + pending items
    today_events: list[dict[str, Any]] = Field(default_factory=list)
    pending_approvals: list[dict[str, Any]] = Field(default_factory=list)
    flagged_items: list[dict[str, Any]] = Field(default_factory=list)

    # Evening-specific
    day_completed_items: list[dict[str, Any]] = Field(default_factory=list)
    tomorrow_events: list[dict[str, Any]] = Field(default_factory=list)

    # Preference-driven section list (prompt emits only these)
    requested_sections: list[str] = Field(default_factory=list)

    # Tone + other AI settings (read from ai_settings_service)
    narrative_tone: str = "concise"  # "concise" | "detailed"


__all__ = [
    "BriefingType",
    "BriefingSectionKey",
    "DeliveryChannel",
    "MORNING_DEFAULT_SECTIONS",
    "EVENING_DEFAULT_SECTIONS",
    "DEFAULT_MORNING_TIME",
    "DEFAULT_EVENING_TIME",
    "BriefingPreferences",
    "StructuredSections",
    "GeneratedBriefing",
    "BriefingDataContext",
]
