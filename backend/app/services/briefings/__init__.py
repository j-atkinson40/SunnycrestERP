"""Phase 6 — Morning + evening briefing generation + delivery.

Architectural principle: briefings are narrative synthesis over the
primitives (saved views, triage queues, spaces, Intelligence), not a
new primitive. This package composes; it does NOT reimplement data
collection that already lives in `briefing_service.py` (the legacy
context builders represent months of customer ground-truth tuning —
we import and reuse them verbatim).

Coexist-with-legacy discipline:
  - Legacy `briefing_service.py` stays operational
  - Legacy `/briefings/briefing` endpoint + `MorningBriefingCard`
    component unchanged
  - Phase 6 endpoints under `/briefings/v2/*`
  - Phase 6 is canonical for NEW surfaces; legacy is deprecated but
    not deleted — cleanup deferred to post-arc sweep

Public exports:
  - types        — Pydantic models (BriefingPreferences, SectionKey, etc.)
  - preferences  — load/save user preferences (User.preferences namespace)
  - data_sources — collect data for a briefing (imports legacy builders)
  - generator    — Intelligence-driven narrative + structured sections
  - delivery     — email + in-app channel dispatch
  - scheduler    — per-user sweep logic (global every-15-min job)
"""

from __future__ import annotations

from app.services.briefings.types import (
    BriefingType,
    BriefingSectionKey,
    MORNING_DEFAULT_SECTIONS,
    EVENING_DEFAULT_SECTIONS,
    DEFAULT_MORNING_TIME,
    DEFAULT_EVENING_TIME,
    BriefingPreferences,
    StructuredSections,
    GeneratedBriefing,
    BriefingDataContext,
)

from app.services.briefings.preferences import (
    get_preferences,
    update_preferences,
    seed_preferences_for_user,
)

from app.services.briefings.data_sources import (
    collect_data_for_morning_briefing,
    collect_data_for_evening_briefing,
)

from app.services.briefings.generator import (
    generate_morning_briefing,
    generate_evening_briefing,
    GenerationError,
)

from app.services.briefings.delivery import deliver_briefing

from app.services.briefings.scheduler_integration import (
    sweep_briefings_to_generate,
)


__all__ = [
    # types
    "BriefingType",
    "BriefingSectionKey",
    "MORNING_DEFAULT_SECTIONS",
    "EVENING_DEFAULT_SECTIONS",
    "DEFAULT_MORNING_TIME",
    "DEFAULT_EVENING_TIME",
    "BriefingPreferences",
    "StructuredSections",
    "GeneratedBriefing",
    "BriefingDataContext",
    # preferences
    "get_preferences",
    "update_preferences",
    "seed_preferences_for_user",
    # data
    "collect_data_for_morning_briefing",
    "collect_data_for_evening_briefing",
    # generator
    "generate_morning_briefing",
    "generate_evening_briefing",
    "GenerationError",
    # delivery
    "deliver_briefing",
    # scheduler
    "sweep_briefings_to_generate",
]
