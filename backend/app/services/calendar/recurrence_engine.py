"""Calendar recurrence engine — Phase W-4b Layer 1 Calendar Step 2.

Canonical implementation of §3.26.16.4 RRULE-as-source-of-truth:
Bridgeable owns the recurrence engine; provider is bridge. Materialized
instances answer free/busy + agenda queries directly from canonical
``calendar_events`` rows + ``calendar_event_instance_overrides``
shadowing — no provider round-trip required.

**Canonical materialization policy** (per §3.26.16.4):

  - **Materialize-on-demand for query scopes ≤ 90 days into future**
    (Step 2 ships this path)
  - **Materialize-and-persist for instances ≤ 7 days from now**
    (writes to materialization cache; refreshed nightly per provider
    sync cadence) — DEFERRED to Step 2.1 alongside webhook receivers
  - **Cap instance count per query at 500** (defensive against
    pathological recurrence rules like FREQ=SECONDLY)

**RRULE engine library**: ``python-dateutil.rrule.rrulestr`` parses
RFC 5545 RRULE strings into iterable rrule objects supporting
``between(start, end)`` for range expansion. Already installed.

**EXDATE handling**: RFC 5545 EXDATE excludes specific instances
(distinct from RDATE-cancelled-via-override which uses
``calendar_event_instance_overrides`` rows with is_cancelled=True).
Step 2 supports both: EXDATE handled inline by dateutil's RRULE
parser when EXDATE clauses are embedded in the RRULE string;
override-based cancellation handled by post-expansion filter.

**Modified-instance shadowing**: when a recurring event has one
instance modified (e.g. weekly meeting moved one week to Wednesday),
``calendar_event_instance_overrides`` row points at a separate
modified-instance event row via ``override_event_id``. The original
materialized instance at that ``recurrence_instance_start_at`` is
SKIPPED; the override event row provides the modified content.

**Step 2 API**:

  - ``materialize_instances(db, event, range_start, range_end, max_count=500)``
    → list[MaterializedInstance]
  - ``MaterializedInstance`` is a lightweight dataclass (not a DB row)
    carrying the resolved start/end/subject/etc. for an expanded
    occurrence. Free/busy + agenda views consume this directly without
    round-tripping through CalendarEvent rows.

**Step 2 boundary**:

  - On-demand expansion only (no persisted cache table)
  - Read path only (no expansion-on-write; events stored verbatim
    with their RRULE string)
  - No iTIP RECURRENCE-ID handling (Step 3 outbound concern)
  - No cross-tenant materialization variants (Step 4 concern)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterator

from dateutil.rrule import rrulestr
from sqlalchemy.orm import Session

from app.models.calendar_primitive import (
    CalendarEvent,
    CalendarEventInstanceOverride,
)

logger = logging.getLogger(__name__)


# Per §3.26.16.4: "Cap instance count per query at 500 (defensive
# against pathological recurrence rules like FREQ=SECONDLY)."
DEFAULT_MAX_INSTANCES = 500


# ─────────────────────────────────────────────────────────────────────
# Result dataclass — lightweight materialized occurrence
# ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MaterializedInstance:
    """A single expanded recurrence instance.

    Carries the resolved start/end + the source event id + the
    instance start (RFC 5545 RECURRENCE-ID semantics — used for
    override matching). Override-modified instances carry
    ``override_event_id`` pointing at the modifying event row.

    Attributes:
        event_id: The master event's id (recurring source).
        instance_start_at: RFC 5545 RECURRENCE-ID — the originally-
            scheduled start time of THIS instance (before any
            modification). Used for override resolution.
        start_at: Resolved start time (= instance_start_at unless
            override modified it).
        end_at: Resolved end time (preserves original duration unless
            override modified it).
        is_modified: True when this instance was modified by an
            override; ``override_event_id`` is set.
        override_event_id: When non-None, points at the modifying
            CalendarEvent row carrying the override's content.
        subject: Event subject (from override if modified, else master).
        status: RFC 5545 STATUS (confirmed / tentative / cancelled).
        transparency: RFC 5545 TRANSP (opaque / transparent).
    """

    event_id: str
    instance_start_at: datetime
    start_at: datetime
    end_at: datetime
    is_modified: bool
    override_event_id: str | None
    subject: str | None
    status: str
    transparency: str


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────


def materialize_instances(
    db: Session,
    *,
    event: CalendarEvent,
    range_start: datetime,
    range_end: datetime,
    max_count: int = DEFAULT_MAX_INSTANCES,
) -> list[MaterializedInstance]:
    """Expand a recurring event into instances within [range_start, range_end).

    Per canonical §3.26.16.4 materialize-on-demand path:

      1. If ``event.recurrence_rule`` is None → return single instance
         when [event.start_at, event.end_at) overlaps query range.
      2. If recurring → parse RRULE via ``dateutil.rrule.rrulestr``,
         expand via ``between(range_start, range_end)``, cap at
         ``max_count``.
      3. Load all instance overrides for this master event in the
         range (single query).
      4. For each expanded occurrence:
         - If override with is_cancelled=True at this
           recurrence_instance_start_at → SKIP (RFC 5545 cancelled
           instance not materialized).
         - If override with override_event_id at this
           recurrence_instance_start_at → emit MaterializedInstance
           carrying the override's resolved start/end/subject (modified
           instance shadowing).
         - Otherwise → emit MaterializedInstance with master's content
           shifted to the occurrence start.

    Returns instances sorted by ``start_at``.

    Per canonical §3.26.16.4: cap at ``max_count`` (default 500) is
    defensive against pathological RRULEs like FREQ=SECONDLY. When the
    cap is hit, a logger warning is emitted; the returned list contains
    the first max_count instances. The caller can disclose staleness
    per §3.26.16.8 transparency discipline if it matters.

    **Half-open range convention** matches iCalendar: an instance is
    INCLUDED when its start_at < range_end AND its end_at > range_start
    (overlap, not strict containment).
    """
    if not event.recurrence_rule:
        # Non-recurring: return single materialized instance if it
        # overlaps the query range.
        if event.end_at > range_start and event.start_at < range_end:
            return [
                MaterializedInstance(
                    event_id=event.id,
                    instance_start_at=event.start_at,
                    start_at=event.start_at,
                    end_at=event.end_at,
                    is_modified=False,
                    override_event_id=None,
                    subject=event.subject,
                    status=event.status,
                    transparency=event.transparency,
                )
            ]
        return []

    # Recurring path: parse RRULE + expand.
    duration = event.end_at - event.start_at

    try:
        # RFC 5545 RRULE expansion. dateutil's rrulestr accepts the
        # bare RRULE prefix or full ical-style block; we pass the
        # value verbatim with DTSTART injected for canonical anchoring.
        rule_str = _normalize_rrule(event.recurrence_rule, dtstart=event.start_at)
        rule = rrulestr(rule_str, dtstart=event.start_at)
    except Exception as exc:  # noqa: BLE001 — surface as warning, return empty
        logger.warning(
            "Failed to parse RRULE %r for event %s: %s — returning empty "
            "expansion (per §3.26.16.4 stale-but-correct discipline)",
            event.recurrence_rule,
            event.id,
            exc,
        )
        return []

    # Expand within range. dateutil.between is half-open [start, end)
    # by default when inc=False; we want overlap with event duration so
    # we expand a slightly wider window.
    expansion_start = range_start - duration
    occurrences = list(_expand_capped(rule, expansion_start, range_end, max_count))

    if len(occurrences) >= max_count:
        logger.warning(
            "RRULE expansion hit max_count=%d cap for event %s (rule=%r) "
            "— per §3.26.16.4 defensive cap. Returning first %d instances.",
            max_count,
            event.id,
            event.recurrence_rule,
            max_count,
        )

    # Load all overrides for this master in one query.
    overrides = _load_overrides_indexed(db, master_event_id=event.id)

    results: list[MaterializedInstance] = []
    for occ_start in occurrences:
        # Half-open overlap check against query range.
        occ_end = occ_start + duration
        if occ_end <= range_start or occ_start >= range_end:
            continue

        # Override resolution. RFC 5545 RECURRENCE-ID matches the
        # original recurrence_instance_start_at on the override row —
        # NOT the (potentially-modified) override event's start.
        override = overrides.get(occ_start)
        if override is None:
            results.append(
                MaterializedInstance(
                    event_id=event.id,
                    instance_start_at=occ_start,
                    start_at=occ_start,
                    end_at=occ_end,
                    is_modified=False,
                    override_event_id=None,
                    subject=event.subject,
                    status=event.status,
                    transparency=event.transparency,
                )
            )
            continue

        if override.is_cancelled:
            # RFC 5545 cancelled instance — DO NOT materialize.
            continue

        # Modified-instance shadowing — load the override event row.
        # The override event itself is a separate CalendarEvent row
        # carrying the modified content.
        override_event = override.override_event
        if override_event is None:
            # Defensive: override row says modified but no override_event_id
            # — fall through to master content (logged warning).
            logger.warning(
                "Override row %s for event %s claims is_cancelled=False "
                "but override_event_id is None — falling through to master.",
                override.id,
                event.id,
            )
            results.append(
                MaterializedInstance(
                    event_id=event.id,
                    instance_start_at=occ_start,
                    start_at=occ_start,
                    end_at=occ_end,
                    is_modified=False,
                    override_event_id=None,
                    subject=event.subject,
                    status=event.status,
                    transparency=event.transparency,
                )
            )
            continue

        results.append(
            MaterializedInstance(
                event_id=event.id,
                instance_start_at=occ_start,
                start_at=override_event.start_at,
                end_at=override_event.end_at,
                is_modified=True,
                override_event_id=override_event.id,
                subject=override_event.subject,
                status=override_event.status,
                transparency=override_event.transparency,
            )
        )

    results.sort(key=lambda m: m.start_at)
    return results


# ─────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────


def _normalize_rrule(rrule_str: str, *, dtstart: datetime) -> str:
    """Normalize an RRULE string for ``dateutil.rrulestr``.

    Accepts:
      - Bare ``FREQ=WEEKLY;BYDAY=MO,WE`` → wraps into ``RRULE:`` line
      - Full ``RRULE:FREQ=...`` form → passes through
      - Multi-line iCal block with embedded EXDATE/RDATE → passes through
        (dateutil parses them all)

    dateutil requires a parseable RRULE; the dtstart kwarg anchors
    the expansion. The returned string is the RRULE block; the caller
    passes ``dtstart`` to ``rrulestr(..., dtstart=...)``.
    """
    s = rrule_str.strip()
    if not s:
        return ""
    # If it's a multi-line block already (RRULE: + DTSTART: + EXDATE: ...),
    # dateutil handles it. If it's a bare FREQ=...; expression,
    # prepend the RRULE: prefix.
    if s.startswith("RRULE:") or s.startswith("DTSTART") or "\n" in s:
        return s
    if s.startswith("FREQ=") or "FREQ=" in s.split(";", 1)[0]:
        return f"RRULE:{s}"
    # Last-resort: assume it's already in some canonical form
    # dateutil accepts.
    return s


def _expand_capped(
    rule, range_start: datetime, range_end: datetime, max_count: int
) -> Iterator[datetime]:
    """Iterate occurrences in [range_start, range_end) capped at max_count.

    dateutil's ``rrule.between(after, before)`` returns all occurrences
    in the range; for unbounded RRULEs we need defensive cap before
    materializing the full list.
    """
    count = 0
    for occ in rule.between(range_start, range_end, inc=True):
        if count >= max_count:
            break
        # Ensure timezone-aware. dateutil preserves dtstart's tz; if
        # the source event was tz-naive (shouldn't happen post-Step-1
        # CHECK constraint but defensive) we attach UTC.
        if occ.tzinfo is None:
            occ = occ.replace(tzinfo=timezone.utc)
        yield occ
        count += 1


def _load_overrides_indexed(
    db: Session, *, master_event_id: str
) -> dict[datetime, CalendarEventInstanceOverride]:
    """Load all overrides for a master event indexed by recurrence_instance_start_at.

    Uses joinedload to eagerly fetch the override_event so the caller
    doesn't issue per-instance queries during materialization.
    """
    from sqlalchemy.orm import joinedload

    rows = (
        db.query(CalendarEventInstanceOverride)
        .options(joinedload(CalendarEventInstanceOverride.override_event))
        .filter(
            CalendarEventInstanceOverride.master_event_id == master_event_id
        )
        .all()
    )
    return {r.recurrence_instance_start_at: r for r in rows}


# ─────────────────────────────────────────────────────────────────────
# Bulk expansion across multiple events (used by free/busy)
# ─────────────────────────────────────────────────────────────────────


def materialize_instances_for_events(
    db: Session,
    *,
    events: list[CalendarEvent],
    range_start: datetime,
    range_end: datetime,
    max_count_per_event: int = DEFAULT_MAX_INSTANCES,
) -> list[MaterializedInstance]:
    """Bulk-expand a list of events.

    Convenience over the single-event API — used by local provider's
    ``fetch_freebusy`` to expand all opaque events for an account in
    one pass. Per-event cap defends against pathological RRULEs;
    overall result count is bounded by ``len(events) * max_count_per_event``.

    Returns instances sorted by ``start_at`` across all input events.
    """
    all_instances: list[MaterializedInstance] = []
    for event in events:
        instances = materialize_instances(
            db,
            event=event,
            range_start=range_start,
            range_end=range_end,
            max_count=max_count_per_event,
        )
        all_instances.extend(instances)
    all_instances.sort(key=lambda m: m.start_at)
    return all_instances
