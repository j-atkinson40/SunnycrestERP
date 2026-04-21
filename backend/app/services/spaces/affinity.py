"""Spaces affinity — Workflow Arc Phase 8e.1.

Per-user, per-space topical affinity signal that feeds command bar
ranking. Write path records intent signals (pin click, PinStar
toggle, command-bar navigate, pinned-nav direct visit). Read path
prefetches once per command_bar/query call + applies a multiplicative
boost factor during result scoring.

Scoring formula:

    affinity_weight = 1.0 + 0.4 * log_visits * recency_decay

    log_visits      = log10(visit_count + 1) / log10(11)     [0..1]
    recency_decay   = max(0, 1 - age_days / 30)              [0..1]

- 0 visits           → 1.00 (no boost)
- 1 visit, today     → 1.11
- 5 visits, today    → 1.31
- 10 visits, today   → 1.40 (cap at visit_count≥10)
- 10 visits, 15 days → 1.20 (half decay)
- 10 visits, 45 days → 1.00 (fully decayed, row contributes 0)

Max stack with existing boosts (`_WEIGHT_ACTIVE_SPACE_PIN_BOOST=1.25`
+ starter-template boost `1.10`):

    1.40 × 1.25 × 1.10 = 1.925

Which is slightly above the existing `_WEIGHT_CREATE_ON_CREATE_INTENT
= 1.5` single-boost ceiling. Acceptable — a space where the user
repeatedly visits a target AND pins it AND it's in the starter
template should out-rank a generic "new X" create action.

Purpose-limitation: affinity data is used ONLY for command bar
ranking. Any future use requires a separate scope-expansion audit.
See `SPACES_ARCHITECTURE.md` §9.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import and_, delete as sa_delete, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_space_affinity import UserSpaceAffinity

logger = logging.getLogger(__name__)


TargetType = Literal["nav_item", "saved_view", "entity_record", "triage_queue"]

_VALID_TARGET_TYPES: frozenset[str] = frozenset(
    ("nav_item", "saved_view", "entity_record", "triage_queue")
)

# Decay window (days). >= this value → row contributes 0 to ranking.
_DECAY_DAYS: float = 30.0

# Saturation point for visit_count in the log curve. 10 visits →
# maximum contribution. log10(visit_count + 1) / log10(11) — 11 so
# that 10 visits hits 1.0 exactly.
_VISIT_SATURATION_LOG_DIVISOR: float = math.log10(11.0)

# Maximum delta above the 1.0 baseline. 0.4 keeps max boost at 1.40,
# which composed with other boosts (1.25 pin + 1.10 starter) stays
# below the 2.0× "weird artifact" threshold.
_MAX_BOOST_DELTA: float = 0.4


# ── Server-side throttle (defense-in-depth over client throttle) ────


# (user_id, target_type, target_id) → monotonic timestamp of last
# accepted write. In-memory, per-process. Multiple web workers each
# hold their own bucket, so the effective throttle is PER-PROCESS —
# acceptable because the write semantics are upsert (duplicates
# converge) and client throttle is the primary defense.
_THROTTLE_WINDOW_SECONDS: float = 60.0
_throttle_lock = threading.Lock()
_throttle_buckets: dict[tuple[str, str, str], float] = {}


def _should_throttle(user_id: str, target_type: str, target_id: str) -> bool:
    """Return True if this visit should be throttled (i.e. write
    skipped). Uses a monotonic clock to avoid wall-clock drift."""
    now = time.monotonic()
    key = (user_id, target_type, target_id)
    with _throttle_lock:
        last = _throttle_buckets.get(key)
        if last is not None and (now - last) < _THROTTLE_WINDOW_SECONDS:
            return True
        _throttle_buckets[key] = now
    return False


def _clear_throttle_for_tests() -> None:
    """Test helper — reset in-memory throttle bucket state."""
    with _throttle_lock:
        _throttle_buckets.clear()


# ── Data types ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class AffinityRow:
    """In-memory affinity row used by the read path. Includes
    precomputed age_days so boost_factor is a pure function over
    (visit_count, age_days)."""

    target_type: str
    target_id: str
    visit_count: int
    last_visited_at: datetime


# ── Write path ──────────────────────────────────────────────────────


class SpaceNotOwnedError(Exception):
    """Raised when the caller tries to record an affinity visit
    against a space_id that doesn't belong to them. Defense-in-depth
    — Space IDs are opaque UUIDs so guessing is hard, but a buggy
    client could still send the wrong ID."""


def record_visit(
    db: Session,
    *,
    user: User,
    space_id: str,
    target_type: str,
    target_id: str,
) -> bool:
    """Upsert an affinity row for (user, space, target_type, target_id).

    Increments visit_count, refreshes last_visited_at. Returns True
    if the row was written, False if throttled.

    Validates:
      - target_type is one of the four enum values
      - space_id belongs to the user

    Does NOT validate the target_id exists — target may be deleted
    later (a deleted target just doesn't get any boost at read time).

    Raises:
      ValueError on invalid target_type
      SpaceNotOwnedError when space_id doesn't belong to user
    """
    if target_type not in _VALID_TARGET_TYPES:
        raise ValueError(
            f"target_type must be one of "
            f"{sorted(_VALID_TARGET_TYPES)}, got {target_type!r}"
        )
    if not target_id or len(target_id) > 255:
        raise ValueError("target_id must be 1..255 chars")

    # Space ownership: confirm the space exists in user.preferences.spaces.
    prefs = user.preferences or {}
    raw_spaces = prefs.get("spaces") or []
    space_ids = {s.get("space_id") for s in raw_spaces}
    if space_id not in space_ids:
        raise SpaceNotOwnedError(
            f"Space {space_id} not found for user {user.id}"
        )

    # Throttle — short-circuit BEFORE hitting the DB.
    if _should_throttle(user.id, target_type, target_id):
        return False

    now = datetime.now(timezone.utc)

    # PostgreSQL UPSERT. The dialect-specific `insert` lets us chain
    # `on_conflict_do_update`. Alternative portable paths exist but
    # we're Postgres-exclusive.
    stmt = pg_insert(UserSpaceAffinity).values(
        user_id=user.id,
        company_id=user.company_id,
        space_id=space_id,
        target_type=target_type,
        target_id=target_id,
        visit_count=1,
        last_visited_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            UserSpaceAffinity.user_id,
            UserSpaceAffinity.space_id,
            UserSpaceAffinity.target_type,
            UserSpaceAffinity.target_id,
        ],
        set_={
            "visit_count": UserSpaceAffinity.visit_count + 1,
            "last_visited_at": now,
        },
    )
    db.execute(stmt)
    db.commit()
    return True


# ── Read path ───────────────────────────────────────────────────────


def prefetch_for_user_space(
    db: Session,
    *,
    user: User,
    space_id: str | None,
) -> dict[tuple[str, str], AffinityRow]:
    """Fetch the active affinity set for (user, space_id) in one
    indexed query. Returns a dict keyed on (target_type, target_id)
    for O(1) lookup during scoring.

    Empty space_id → empty dict (no active space means no affinity
    boost). Silent fail on DB error so command bar latency isn't
    undermined by a migration gap.
    """
    if not space_id:
        return {}

    try:
        rows = (
            db.query(
                UserSpaceAffinity.target_type,
                UserSpaceAffinity.target_id,
                UserSpaceAffinity.visit_count,
                UserSpaceAffinity.last_visited_at,
            )
            .filter(
                UserSpaceAffinity.user_id == user.id,
                UserSpaceAffinity.space_id == space_id,
                UserSpaceAffinity.visit_count > 0,
            )
            .all()
        )
    except Exception:
        logger.exception(
            "affinity.prefetch_for_user_space failed (user=%s space=%s)",
            user.id,
            space_id,
        )
        return {}

    out: dict[tuple[str, str], AffinityRow] = {}
    for row in rows:
        out[(row.target_type, row.target_id)] = AffinityRow(
            target_type=row.target_type,
            target_id=row.target_id,
            visit_count=int(row.visit_count),
            last_visited_at=row.last_visited_at,
        )
    return out


def boost_factor(row: AffinityRow, *, as_of: datetime | None = None) -> float:
    """Compute the multiplicative boost for an affinity row.

    Pure function of (visit_count, age_days); `as_of` optional for
    tests. Returns 1.0 for fully-decayed rows.
    """
    now = as_of or datetime.now(timezone.utc)
    # Defensive — if last_visited_at is tz-naive, treat as UTC.
    lva = row.last_visited_at
    if lva.tzinfo is None:
        lva = lva.replace(tzinfo=timezone.utc)

    age_seconds = max(0.0, (now - lva).total_seconds())
    age_days = age_seconds / 86400.0

    if age_days >= _DECAY_DAYS:
        return 1.0

    recency_decay = max(0.0, 1.0 - (age_days / _DECAY_DAYS))
    log_visits = math.log10(max(0, row.visit_count) + 1) / _VISIT_SATURATION_LOG_DIVISOR
    # visit_count >= 10 saturates the log; clamp at 1.0.
    if log_visits > 1.0:
        log_visits = 1.0
    if log_visits < 0.0:
        log_visits = 0.0

    return 1.0 + _MAX_BOOST_DELTA * log_visits * recency_decay


def boost_for_target(
    affinity: dict[tuple[str, str], AffinityRow],
    target_type: str,
    target_id: str,
    *,
    as_of: datetime | None = None,
) -> float:
    """Convenience — returns 1.0 if no affinity row exists, else
    the boost_factor."""
    row = affinity.get((target_type, target_id))
    if row is None:
        return 1.0
    return boost_factor(row, as_of=as_of)


# ── Cascade + privacy delete ────────────────────────────────────────


def delete_affinity_for_space(
    db: Session,
    *,
    user_id: str,
    space_id: str,
) -> int:
    """Delete all affinity rows for a user's space. Called by
    crud.delete_space AFTER the space is removed. Returns count
    deleted."""
    result = db.execute(
        sa_delete(UserSpaceAffinity).where(
            and_(
                UserSpaceAffinity.user_id == user_id,
                UserSpaceAffinity.space_id == space_id,
            )
        )
    )
    db.commit()
    return int(result.rowcount or 0)


def clear_affinity_for_user(
    db: Session,
    *,
    user: User,
    space_id: str | None = None,
) -> int:
    """GDPR-style "clear my command bar learning history" action.
    When `space_id` is None, clears all rows for the user; when
    provided, clears only that space. Returns count deleted."""
    conditions = [UserSpaceAffinity.user_id == user.id]
    if space_id is not None:
        conditions.append(UserSpaceAffinity.space_id == space_id)

    result = db.execute(
        sa_delete(UserSpaceAffinity).where(and_(*conditions))
    )
    db.commit()
    return int(result.rowcount or 0)


def count_for_user(
    db: Session,
    *,
    user: User,
    space_id: str | None = None,
) -> int:
    """Returns count of active affinity rows for the user. Powers
    the "N tracked signals" counter on /settings/spaces."""
    q = db.query(func.count(UserSpaceAffinity.user_id)).filter(
        UserSpaceAffinity.user_id == user.id,
        UserSpaceAffinity.visit_count > 0,
    )
    if space_id is not None:
        q = q.filter(UserSpaceAffinity.space_id == space_id)
    result = q.scalar()
    return int(result or 0)


__all__ = [
    "AffinityRow",
    "SpaceNotOwnedError",
    "record_visit",
    "prefetch_for_user_space",
    "boost_factor",
    "boost_for_target",
    "delete_affinity_for_space",
    "clear_affinity_for_user",
    "count_for_user",
    "_clear_throttle_for_tests",
]
