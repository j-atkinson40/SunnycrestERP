"""Pulse signal tracking service — Phase W-4a Commit 4.

Persists user interaction signals (dismiss + navigation) from the
Home Pulse surface to the `pulse_signals` table, and exposes
aggregation helpers ready for Tier 2 algorithms post-September.

**Standardized metadata shapes** (per the r61 migration docstring):
  • Dismiss signals: {component_key, time_of_day, work_areas_at_dismiss}
  • Navigation signals: {from_component_key, to_route, dwell_time_seconds}

These shapes are load-bearing — Tier 2 algorithms will pattern-match
against them. Any new signal_type added post-W-4a must define its
metadata shape in the migration docstring + here in this service.

**Tenant + user scoping (canonical W-3 pattern):**
  • Every write forces `company_id = user.company_id` and
    `user_id = user.id` from the authenticated User. Request bodies
    NEVER accept user_id or company_id — cross-user writes are
    structurally impossible.
  • Every aggregation query filters by `user_id == user.id` AND
    `company_id == user.company_id` (defense-in-depth — even if a
    signal somehow ends up with a stale company_id, the second filter
    blocks cross-tenant aggregation).

**Validation discipline:**
  • `layer` must be one of the canonical four (personal /
    operational / anomaly / activity).
  • `component_key` must be non-empty and bounded (256 chars to
    match the column length defensively; the model is 128 — we
    enforce 128 here so writes fail loudly before hitting the DB).
  • `time_of_day` must be one of the canonical four signals
    (morning / midday / end_of_day / off_hours).
  • `dwell_time_seconds` must be non-negative; capped at 24 hours
    to defend against pathological client clocks.

**Aggregation helpers** are exported for future Tier 2 algorithms.
Phase W-4a does NOT consume them; they're tested + ready so when
Tier 2 algorithms ship post-September the aggregations are battle-
tested. This is the same pattern Phase 7 telemetry used (signal
collection ships now; algorithms iterate against accumulated data
post-September).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, get_args

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models.pulse_signal import PulseSignal
from app.models.user import User
from app.services.pulse.types import LayerName, TimeOfDaySignal

logger = logging.getLogger(__name__)


# ── Canonical vocabulary (validated on write) ──────────────────────


_VALID_LAYERS: frozenset[str] = frozenset(get_args(LayerName))
_VALID_TIME_OF_DAY: frozenset[str] = frozenset(get_args(TimeOfDaySignal))

# Component keys are open-ended (the widget catalog + intelligence
# stream registry both grow over time). We enforce length + non-
# emptiness, not membership in a closed set — closed-set validation
# would make this service grow brittle as the catalog evolves.
_COMPONENT_KEY_MAX_LENGTH = 128
_DWELL_TIME_MAX_SECONDS = 24 * 60 * 60  # 24 hours


class SignalValidationError(ValueError):
    """Raised on validation failure during signal record."""


# ── Validation helpers ────────────────────────────────────────────


def _validate_layer(layer: str) -> str:
    if layer not in _VALID_LAYERS:
        raise SignalValidationError(
            f"layer must be one of {sorted(_VALID_LAYERS)!r}; got {layer!r}"
        )
    return layer


def _validate_component_key(value: str, field_name: str = "component_key") -> str:
    if not isinstance(value, str):
        raise SignalValidationError(
            f"{field_name} must be a string; got {type(value).__name__}"
        )
    stripped = value.strip()
    if not stripped:
        raise SignalValidationError(f"{field_name} must be non-empty")
    if len(stripped) > _COMPONENT_KEY_MAX_LENGTH:
        raise SignalValidationError(
            f"{field_name} exceeds max length "
            f"({len(stripped)} > {_COMPONENT_KEY_MAX_LENGTH})"
        )
    return stripped


def _validate_time_of_day(value: str | None) -> str:
    """time_of_day is required for dismiss signals (drives Tier 2
    time-of-day adaptation per §3.26.2.5). Accept None as
    convenience for callers that don't have it; default to current
    server-side computation would require tenant TZ — easier to
    require client to pass it (frontend reads composition metadata)."""
    if value is None:
        raise SignalValidationError(
            "time_of_day is required for dismiss signals"
        )
    if value not in _VALID_TIME_OF_DAY:
        raise SignalValidationError(
            f"time_of_day must be one of {sorted(_VALID_TIME_OF_DAY)!r}; "
            f"got {value!r}"
        )
    return value


def _validate_work_areas_list(
    value: list[str] | None,
) -> list[str]:
    """work_areas_at_dismiss is the snapshot of user.work_areas at
    the moment of dismiss — Tier 2 algorithms correlate
    "user dismissed component X while in work_areas Y" patterns."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise SignalValidationError(
            "work_areas_at_dismiss must be a list of strings"
        )
    out: list[str] = []
    for area in value:
        if not isinstance(area, str):
            raise SignalValidationError(
                "work_areas_at_dismiss entries must be strings"
            )
        s = area.strip()
        if s:
            out.append(s)
    return out


def _validate_route(value: str, field_name: str = "to_route") -> str:
    if not isinstance(value, str):
        raise SignalValidationError(
            f"{field_name} must be a string"
        )
    stripped = value.strip()
    if not stripped:
        raise SignalValidationError(f"{field_name} must be non-empty")
    if len(stripped) > 1024:
        raise SignalValidationError(
            f"{field_name} exceeds max length"
        )
    return stripped


def _validate_dwell_time(value: int | float) -> int:
    if not isinstance(value, (int, float)):
        raise SignalValidationError(
            "dwell_time_seconds must be a number"
        )
    if value < 0:
        raise SignalValidationError(
            "dwell_time_seconds must be non-negative"
        )
    if value > _DWELL_TIME_MAX_SECONDS:
        # Cap rather than reject — pathological client clocks shouldn't
        # cause a 4xx; just sanitize the value.
        return _DWELL_TIME_MAX_SECONDS
    return int(value)


# ── Write paths ────────────────────────────────────────────────────


def record_dismiss(
    db: Session,
    *,
    user: User,
    component_key: str,
    layer: str,
    time_of_day: str,
    work_areas_at_dismiss: list[str] | None = None,
) -> PulseSignal:
    """Record a dismiss signal for the current user.

    Standardized metadata shape: {component_key, time_of_day,
    work_areas_at_dismiss}. The component_key is denormalized into
    both the column and the metadata for query convenience —
    metadata stays self-describing for analytics independent of
    column shape.

    Tenant + user scoping forced from the User parameter; never
    accepts caller-supplied user_id or company_id.
    """
    component_key = _validate_component_key(component_key)
    layer = _validate_layer(layer)
    time_of_day = _validate_time_of_day(time_of_day)
    work_areas = _validate_work_areas_list(work_areas_at_dismiss)

    sig = PulseSignal(
        id=str(uuid.uuid4()),
        user_id=user.id,
        company_id=user.company_id,
        signal_type="dismiss",
        layer=layer,
        component_key=component_key,
        timestamp=datetime.now(timezone.utc),
        signal_metadata={
            "component_key": component_key,
            "time_of_day": time_of_day,
            "work_areas_at_dismiss": work_areas,
        },
    )
    db.add(sig)
    db.commit()
    db.refresh(sig)
    return sig


def record_navigation(
    db: Session,
    *,
    user: User,
    from_component_key: str,
    to_route: str,
    dwell_time_seconds: int | float,
    layer: str,
) -> PulseSignal:
    """Record a navigation signal (user clicked through from a Pulse
    piece to another route).

    Standardized metadata shape: {from_component_key, to_route,
    dwell_time_seconds}. The `from_component_key` is denormalized
    into both the column and metadata for query convenience.

    `layer` is required (per the column constraint) and identifies
    which Pulse layer the originating piece belonged to. Frontend
    reads this from the LayerItem's parent layer at click time.
    """
    from_component_key = _validate_component_key(
        from_component_key, "from_component_key"
    )
    to_route = _validate_route(to_route)
    dwell = _validate_dwell_time(dwell_time_seconds)
    layer = _validate_layer(layer)

    sig = PulseSignal(
        id=str(uuid.uuid4()),
        user_id=user.id,
        company_id=user.company_id,
        signal_type="navigate",
        layer=layer,
        component_key=from_component_key,
        timestamp=datetime.now(timezone.utc),
        signal_metadata={
            "from_component_key": from_component_key,
            "to_route": to_route,
            "dwell_time_seconds": dwell,
        },
    )
    db.add(sig)
    db.commit()
    db.refresh(sig)
    return sig


# ── Aggregation helpers (for Tier 2 algorithms post-September) ─────


def _since_window(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def get_dismiss_counts_per_component(
    db: Session,
    *,
    user: User,
    days: int = 30,
) -> dict[str, int]:
    """Count dismiss signals per component_key for a single user
    over the trailing N-day window.

    Tier 2 algorithm input: components a user dismisses repeatedly
    are deprioritized in future composition; rarely-dismissed
    components rise.

    Tenant scoping: filters by `user_id == user.id AND company_id
    == user.company_id` (defense-in-depth — even if user_id alone
    were sufficient at the row level, the company_id filter blocks
    a maliciously-crafted user-id-collision attack across tenants).
    """
    rows = (
        db.query(
            PulseSignal.component_key,
            func.count(PulseSignal.id),
        )
        .filter(
            PulseSignal.user_id == user.id,
            PulseSignal.company_id == user.company_id,
            PulseSignal.signal_type == "dismiss",
            PulseSignal.timestamp >= _since_window(days),
        )
        .group_by(PulseSignal.component_key)
        .all()
    )
    return {component_key: int(count) for component_key, count in rows}


def get_navigation_targets(
    db: Session,
    *,
    user: User,
    from_component_key: str,
    days: int = 30,
) -> list[dict[str, Any]]:
    """Return navigation targets the user has clicked through to
    from a specific component, ordered by frequency desc then
    most-recent-first.

    Output: [{ "to_route": str, "count": int, "last_navigated_at": iso }, ...]

    Tier 2 algorithm input: when a user consistently clicks through
    from component X to route Y, future compositions can offer Y as
    a quick action on X.
    """
    from_component_key = _validate_component_key(
        from_component_key, "from_component_key"
    )
    # Read raw signal rows so we can dig into JSONB metadata.
    rows = (
        db.query(PulseSignal)
        .filter(
            PulseSignal.user_id == user.id,
            PulseSignal.company_id == user.company_id,
            PulseSignal.signal_type == "navigate",
            PulseSignal.component_key == from_component_key,
            PulseSignal.timestamp >= _since_window(days),
        )
        .order_by(desc(PulseSignal.timestamp))
        .all()
    )

    # In-memory aggregation keeps the SQL simple + JSONB-portable.
    by_route: dict[str, dict[str, Any]] = {}
    for r in rows:
        meta = r.signal_metadata or {}
        to_route = meta.get("to_route")
        if not to_route:
            continue
        entry = by_route.setdefault(
            to_route,
            {
                "to_route": to_route,
                "count": 0,
                "last_navigated_at": r.timestamp,
            },
        )
        entry["count"] += 1
        # rows are timestamp-desc; first hit per route is the latest
    # Sort by count desc, then last_navigated_at desc (most-recent
    # tiebreaker)
    out = sorted(
        by_route.values(),
        key=lambda e: (-e["count"], -e["last_navigated_at"].timestamp()),
    )
    # Stringify timestamps for JSON-friendliness on the way out.
    for e in out:
        e["last_navigated_at"] = e["last_navigated_at"].isoformat()
    return out


def get_engagement_score(
    db: Session,
    *,
    user: User,
    component_key: str,
    days: int = 30,
) -> float:
    """Return a unitless engagement score for a (user, component)
    pair over the trailing N-day window.

    **Score construction (Phase W-4a placeholder):**
      score = navigations - (dismiss_weight × dismisses)

    Where `dismiss_weight = 2.0` — a dismiss is "stronger" signal of
    disengagement than a navigation is of engagement. Saturation
    bounds are NOT applied yet; Tier 2 algorithms post-September
    will tune the formula against accumulated data.

    Returns 0.0 when no signals exist (neutral baseline). Negative
    scores indicate net-disengagement (user has dismissed more than
    they've engaged with).

    Tier 2 algorithm input: combine engagement scores across
    components to drive composition priority adjustments.
    """
    component_key = _validate_component_key(component_key)
    since = _since_window(days)

    nav_count = (
        db.query(func.count(PulseSignal.id))
        .filter(
            PulseSignal.user_id == user.id,
            PulseSignal.company_id == user.company_id,
            PulseSignal.signal_type == "navigate",
            PulseSignal.component_key == component_key,
            PulseSignal.timestamp >= since,
        )
        .scalar()
        or 0
    )
    dismiss_count = (
        db.query(func.count(PulseSignal.id))
        .filter(
            PulseSignal.user_id == user.id,
            PulseSignal.company_id == user.company_id,
            PulseSignal.signal_type == "dismiss",
            PulseSignal.component_key == component_key,
            PulseSignal.timestamp >= since,
        )
        .scalar()
        or 0
    )
    DISMISS_WEIGHT = 2.0
    return float(nav_count) - DISMISS_WEIGHT * float(dismiss_count)
