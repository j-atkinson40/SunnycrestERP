"""Phase 6 — briefing preferences persisted in `User.preferences`.

Follows Phase 2/3 conventions:
  - namespace key: `briefing_preferences` (dict matching BriefingPreferences)
  - seed tracker: `briefings_seeded_for_roles: list[str]` for idempotency
  - mutations call `flag_modified(user, "preferences")` so SQLAlchemy
    detects the JSONB change

Migration behavior (spec item #6):
  - On first Phase 6 access, existing `AssistantProfile.disabled_briefing_items`
    (a blocklist) is translated to Phase 6's `enabled_sections` (an allowlist):
      morning_sections = MORNING_DEFAULT_SECTIONS - disabled_items
      evening_sections = EVENING_DEFAULT_SECTIONS - disabled_items
  - This happens exactly once per user via the seed tracker; subsequent
    edits flow through `update_preferences`.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.user import User
from app.services.briefings.types import (
    BriefingPreferences,
    MORNING_DEFAULT_SECTIONS,
    EVENING_DEFAULT_SECTIONS,
)

logger = logging.getLogger(__name__)

_PREF_KEY = "briefing_preferences"
_SEED_TRACKER_KEY = "briefings_seeded_for_roles"


def _prefs_dict(user: User) -> dict[str, Any]:
    prefs = user.preferences or {}
    return prefs.get(_PREF_KEY) or {}


def get_preferences(user: User) -> BriefingPreferences:
    """Return the current user's briefing preferences (defaults applied)."""
    raw = _prefs_dict(user)
    if not raw:
        # No preferences row — defaults (matches post-seed behavior).
        return BriefingPreferences()
    try:
        return BriefingPreferences.model_validate(raw)
    except Exception:
        logger.warning(
            "Invalid briefing_preferences for user %s; returning defaults",
            user.id,
        )
        return BriefingPreferences()


def update_preferences(
    db: Session,
    user: User,
    updates: dict[str, Any],
) -> BriefingPreferences:
    """Patch-merge updates into the user's preferences.

    Fields that aren't provided remain untouched. Validates via Pydantic
    so bad writes (e.g. unknown channel string) fail loudly.
    """
    current = get_preferences(user).model_dump()
    merged = {**current, **updates}
    # Validate the merge before writing.
    validated = BriefingPreferences.model_validate(merged)

    prefs = user.preferences or {}
    prefs[_PREF_KEY] = validated.model_dump()
    user.preferences = prefs
    flag_modified(user, "preferences")
    db.commit()
    db.refresh(user)
    return validated


def _existing_disabled_items(db: Session, user: User) -> list[str]:
    """Best-effort lookup of AssistantProfile.disabled_briefing_items.

    The legacy AssistantProfile row may be absent for new users; returns
    empty list in that case.
    """
    try:
        from app.models.assistant_profile import AssistantProfile

        ap = (
            db.query(AssistantProfile)
            .filter(AssistantProfile.user_id == user.id)
            .first()
        )
        if ap and ap.disabled_briefing_items:
            return list(ap.disabled_briefing_items)
    except Exception:  # pragma: no cover — defensive
        logger.debug("AssistantProfile lookup failed for %s", user.id)
    return []


def seed_preferences_for_user(db: Session, user: User) -> BriefingPreferences:
    """Idempotent per-user seed.

    Writes defaults (minus any items present in the legacy blocklist) on
    first call for a given role. Tracks via
    `preferences.briefings_seeded_for_roles` (list of role slugs seeded so
    far). Running twice is safe — second call short-circuits.

    Returns the effective preferences after seed (whether fresh or cached).
    """
    role_slug = None
    try:
        if user.role_id:
            from app.models.role import Role

            role = db.query(Role).filter(Role.id == user.role_id).first()
            role_slug = role.slug if role else None
    except Exception:
        role_slug = None

    prefs = user.preferences or {}
    seeded_roles: list[str] = list(prefs.get(_SEED_TRACKER_KEY) or [])
    role_key = role_slug or "__fallback__"

    if role_key in seeded_roles and _PREF_KEY in prefs:
        return get_preferences(user)

    # First seed for this role. Translate legacy blocklist → Phase 6 allowlist.
    disabled = set(_existing_disabled_items(db, user))
    morning_sections = [s for s in MORNING_DEFAULT_SECTIONS if s not in disabled]
    evening_sections = [s for s in EVENING_DEFAULT_SECTIONS if s not in disabled]

    seeded = BriefingPreferences(
        morning_sections=morning_sections,
        evening_sections=evening_sections,
    )

    # Preserve any existing user edits that may have been written directly
    # to the JSONB (e.g. if the user edited prefs before the seeding hook
    # fired — shouldn't happen in practice, but defensive merging doesn't
    # hurt).
    existing = prefs.get(_PREF_KEY) or {}
    merged = {**seeded.model_dump(), **existing}
    try:
        validated = BriefingPreferences.model_validate(merged)
    except Exception:
        validated = seeded

    prefs[_PREF_KEY] = validated.model_dump()
    if role_key not in seeded_roles:
        seeded_roles.append(role_key)
    prefs[_SEED_TRACKER_KEY] = seeded_roles
    user.preferences = prefs
    flag_modified(user, "preferences")
    db.commit()
    db.refresh(user)
    return validated


__all__ = [
    "get_preferences",
    "update_preferences",
    "seed_preferences_for_user",
]
