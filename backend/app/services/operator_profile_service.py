"""Operator profile service — Phase W-4a operator onboarding.

Captures the structured signal of what each user does (work_areas) +
free-text responsibilities description per BRIDGEABLE_MASTER §3.26.3.

This service is the canonical write path for operator profile fields:
  • `User.work_areas` (Postgres TEXT[]) — multi-select work-area enums
  • `User.responsibilities_description` (TEXT) — free natural language

Both feed Pulse composition: work_areas drive Tier 1 rule-based widget
selection; responsibilities feed Tier 2+ intelligence post-W-4a.

**Onboarding completion semantics:**
A user is considered "operator-onboarded" when at least one work area
is set. Free-text responsibilities is encouraged but optional. The
distinction matters for first-login redirect logic — users with empty
work_areas land on `/onboarding/operator-profile`; users with work
areas set proceed to `/home`.

**Tracker flag:** `User.preferences.onboarding_touches.operator_profile`
is set to `True` when the user explicitly completes (or skips) the
onboarding flow. Distinct from `work_areas != null` because a user
may dismiss the onboarding without selecting any areas — the flag
prevents re-redirect on every login while still allowing
vertical-default Pulse fallback (D4) for the empty case.
"""
from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.user import User


# Canonical work-area vocabulary per BRIDGEABLE_MASTER §3.26.3.1.
# Multi-select cards in the onboarding UI render from this list.
# Extensible: new work areas added here without DB migration (column
# is TEXT[]; values are validated against this set at write time).
WORK_AREAS: tuple[str, ...] = (
    "Accounting",
    "HR",
    "Production Scheduling",
    "Delivery Scheduling",
    "Inside Sales",
    "Inventory Management",
    "Customer Service",
    "Family Communications",
    "Cross-tenant Coordination",
)

# Validation set for fast membership checks.
_WORK_AREA_SET = frozenset(WORK_AREAS)


# Maximum length for free-text responsibilities (matches typical
# textarea UX expectations + protects against DB bloat).
RESPONSIBILITIES_MAX_LENGTH = 2000


class OperatorProfileError(ValueError):
    """Raised on validation failure during operator profile update."""


def _set_onboarding_touch(user: User, completed: bool) -> None:
    """Set the operator_profile onboarding-touch flag in user prefs.

    Per the established Phase 7 onboarding-touches pattern:
    `preferences.onboarding_touches[touch_key] = bool`.
    """
    prefs = dict(user.preferences or {})
    touches = dict(prefs.get("onboarding_touches", {}))
    touches["operator_profile"] = bool(completed)
    prefs["onboarding_touches"] = touches
    user.preferences = prefs
    flag_modified(user, "preferences")


def get_operator_profile(user: User) -> dict:
    """Return the user's operator profile state for read endpoints.

    Shape mirrors the frontend `OperatorProfile` type. Always returns
    canonical defaults (empty list / null) for unset fields so the
    frontend doesn't have to distinguish missing-vs-empty.
    """
    prefs = user.preferences or {}
    touches = prefs.get("onboarding_touches", {}) or {}
    return {
        "work_areas": list(user.work_areas or []),
        "responsibilities_description": user.responsibilities_description,
        # Onboarding completed if either: (a) explicit flag set OR
        # (b) at least one work area selected (defensive — covers
        # users who set work_areas via API without going through the
        # onboarding flow).
        "onboarding_completed": (
            bool(touches.get("operator_profile"))
            or bool(user.work_areas)
        ),
        # Surface available work-area choices to the frontend so the
        # multi-select UI renders without hardcoding the list.
        "available_work_areas": list(WORK_AREAS),
    }


def _validate_work_areas(work_areas: Iterable[str] | None) -> list[str]:
    """Reject unknown work-area values + de-dupe + sort for stability."""
    if work_areas is None:
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in work_areas:
        if not isinstance(raw, str):
            raise OperatorProfileError(
                f"work_areas must be strings; got {type(raw).__name__}"
            )
        # Trim incidental whitespace from card-click payloads.
        value = raw.strip()
        if not value:
            continue
        if value not in _WORK_AREA_SET:
            raise OperatorProfileError(
                f"Unknown work area: {value!r}. Valid values: "
                f"{sorted(WORK_AREAS)!r}"
            )
        if value in seen:
            continue
        seen.add(value)
        cleaned.append(value)
    # Sort for stable diffs / deterministic Pulse cache keys.
    return sorted(cleaned)


def _validate_responsibilities(text: str | None) -> str | None:
    if text is None:
        return None
    if not isinstance(text, str):
        raise OperatorProfileError(
            "responsibilities_description must be a string or null"
        )
    stripped = text.strip()
    if not stripped:
        # Treat empty/whitespace-only as null (canonical "unset").
        return None
    if len(stripped) > RESPONSIBILITIES_MAX_LENGTH:
        raise OperatorProfileError(
            f"responsibilities_description exceeds max length "
            f"({len(stripped)} > {RESPONSIBILITIES_MAX_LENGTH})"
        )
    return stripped


def update_operator_profile(
    db: Session,
    *,
    user: User,
    work_areas: Iterable[str] | None = None,
    responsibilities_description: str | None = None,
    mark_onboarding_complete: bool = False,
) -> dict:
    """Update operator profile fields.

    Auto-save semantics: each field is only updated when explicitly
    passed. Pass `None` to clear (work_areas → empty list;
    responsibilities → null). Pass nothing to leave a field untouched.

    A sentinel approach was considered (e.g., `_UNSET`) but rejected:
    callers go through Pydantic which already discriminates "field
    omitted" from "field set to null" via `model_fields_set`.

    `mark_onboarding_complete=True` is set by the frontend when the
    user explicitly clicks "Save and continue" — distinguishes
    "intentional finalize" from "auto-save in progress".
    """
    if work_areas is not None:
        cleaned = _validate_work_areas(work_areas)
        user.work_areas = cleaned if cleaned else None

    if responsibilities_description is not None:
        user.responsibilities_description = _validate_responsibilities(
            responsibilities_description
        )

    if mark_onboarding_complete:
        _set_onboarding_touch(user, completed=True)

    db.commit()
    db.refresh(user)
    return get_operator_profile(user)
