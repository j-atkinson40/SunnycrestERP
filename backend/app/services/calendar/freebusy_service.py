"""Free/busy substrate — Phase W-4b Layer 1 Calendar Step 3.

Two query surfaces ship at Step 3:

  1. **Per-account freebusy** — operator queries their own tenant's
     events for free/busy windows. Powers internal scheduling-decision
     UX (e.g. "when is the production manager free this week").

  2. **Cross-tenant freebusy** — operator queries a partner tenant's
     free/busy across an active ``platform_tenant_relationships`` row
     per §3.26.16.14. Privacy-preserving by default (busy/free + status
     only); bilateral consent unlocks full details per §3.26.16.6.

Both query paths consult the canonical recurrence engine
(``recurrence_engine.materialize_instances_for_events``) per §3.26.16.4
RRULE-as-source-of-truth. No provider round-trip required.

**Last-sync staleness disclosure** per §3.26.16.8 transparency
discipline: every freebusy response includes ``last_sync_at`` reflecting
when the canonical state was last refreshed via provider sync. Stale
state is preferred over wrong-because-fresh.

**Three-tier anonymization granularity** per §3.26.16.6 (cross-tenant
only):
  - Subject hashing (Tier 1) — Step 3 omits subject by default; full_details consent reveals
  - Coarse attendee counts (Tier 2) — Step 3 surfaces ``attendee_count_bucket: "1" | "2-5" | "6+"``
  - Specific attendee identities (Tier 3) — Step 3 NEVER returns attendee identities cross-tenant per privacy floor

**Cross-tenant masking inheritance** per §3.25.x: when consent is
``free_busy_only``, response carries no event-content data. When
consent is ``full_details``, response carries subject + location +
attendee_count_bucket but never specific attendee identities.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.calendar_primitive import (
    CalendarAccount,
    CalendarAccountSyncState,
    CalendarEvent,
)
from app.models.platform_tenant_relationship import PlatformTenantRelationship
from app.services.calendar.account_service import (
    CalendarAccountError,
    CalendarAccountNotFound,
    CalendarAccountValidation,
)
from app.services.calendar.recurrence_engine import (
    materialize_instances_for_events,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────


class FreebusyError(CalendarAccountError):
    http_status = 400


class CrossTenantConsentDenied(CalendarAccountError):
    """Raised when no active platform_tenant_relationships row exists
    for the (tenant, partner_tenant) pair — cross-tenant freebusy
    queries require a connected relationship per §3.26.16.14 + §3.26.16.6.
    """

    http_status = 403


# ─────────────────────────────────────────────────────────────────────
# Result dataclasses
# ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FreebusyWindow:
    """A single free/busy window per RFC 5545 + canonical response shape.

    Status canonical values:
      - ``"busy"`` (RFC 5545 TRANSP=OPAQUE, STATUS=CONFIRMED)
      - ``"tentative"`` (RFC 5545 STATUS=TENTATIVE)
      - ``"out_of_office"`` (RFC 5545 ext; not yet sourced canonical at Step 3)
    """

    start_at: datetime
    end_at: datetime
    status: Literal["busy", "tentative", "out_of_office"]
    # Full-details fields (populated only when consent allows OR the
    # query is per-account/internal — never populated cross-tenant
    # under free_busy_only).
    subject: str | None = None
    location: str | None = None
    attendee_count_bucket: str | None = None


@dataclass(frozen=True)
class FreebusyResult:
    """Returned from per-account + cross-tenant freebusy queries."""

    windows: list[FreebusyWindow] = field(default_factory=list)
    consent_level: Literal["internal", "free_busy_only", "full_details"] = "internal"
    last_sync_at: datetime | None = None
    stale: bool = False
    partner_tenant_id: str | None = None


# ─────────────────────────────────────────────────────────────────────
# Per-account query (internal)
# ─────────────────────────────────────────────────────────────────────


def query_per_account_freebusy(
    db: Session,
    *,
    tenant_id: str,
    account_id: str,
    range_start: datetime,
    range_end: datetime,
) -> FreebusyResult:
    """Query free/busy windows for a single calendar account.

    Tenant-scoped per CLAUDE.md tenant isolation — caller's tenant_id
    must match the account's tenant_id (raises CalendarAccountNotFound
    otherwise; existence-hiding 404 to prevent cross-tenant id
    enumeration).

    Returns FreebusyResult with consent_level="internal" — full-details
    fields populated since the caller is querying their own tenant's
    data.
    """
    if range_end <= range_start:
        raise FreebusyError("range_end must be greater than range_start")

    account = (
        db.query(CalendarAccount)
        .filter(
            CalendarAccount.id == account_id,
            CalendarAccount.tenant_id == tenant_id,
            CalendarAccount.is_active.is_(True),
        )
        .first()
    )
    if not account:
        raise CalendarAccountNotFound(
            f"CalendarAccount {account_id!r} not found in this tenant"
        )

    return _query_account_freebusy_canonical(
        db,
        account=account,
        range_start=range_start,
        range_end=range_end,
        consent_level="internal",
    )


# ─────────────────────────────────────────────────────────────────────
# Cross-tenant query
# ─────────────────────────────────────────────────────────────────────


def query_cross_tenant_freebusy(
    db: Session,
    *,
    requesting_tenant_id: str,
    partner_tenant_id: str,
    range_start: datetime,
    range_end: datetime,
    granularity: Literal["hour", "day"] = "hour",
) -> FreebusyResult:
    """Query a partner tenant's free/busy across a cross-tenant relationship.

    Per §3.26.16.14: privacy-preserving by default. Returns
    consent_level="free_busy_only" with status-only windows unless
    the bilateral PTR consent state is "full_details", in which case
    subject + location + attendee_count_bucket are populated per window
    per §3.26.16.6 three-tier anonymization granularity.

    **Bilateral consent requirement**: BOTH directions of the relationship
    must consent to "full_details" before the response upgrades.
    Step 3 ships read-side; Step 4 ships UI for bilateral upgrade flow.

    Step 3 boundary: granularity parameter is accepted but Step 3 always
    returns event-precision windows. "hour" / "day" coarsening defers
    to Step 5 cross-surface UX (where coarsened views are useful for
    aggregate planning visualizations).

    Raises:
        CrossTenantConsentDenied: no active PTR row for the pair.
    """
    if range_end <= range_start:
        raise FreebusyError("range_end must be greater than range_start")
    if granularity not in ("hour", "day"):
        raise FreebusyError(
            f"granularity must be 'hour' or 'day', got {granularity!r}"
        )

    # Look up bilateral PTR rows (both directions).
    forward_row = (
        db.query(PlatformTenantRelationship)
        .filter(
            PlatformTenantRelationship.tenant_id == requesting_tenant_id,
            PlatformTenantRelationship.supplier_tenant_id == partner_tenant_id,
            PlatformTenantRelationship.status == "active",
        )
        .first()
    )
    reverse_row = (
        db.query(PlatformTenantRelationship)
        .filter(
            PlatformTenantRelationship.tenant_id == partner_tenant_id,
            PlatformTenantRelationship.supplier_tenant_id == requesting_tenant_id,
            PlatformTenantRelationship.status == "active",
        )
        .first()
    )
    if not forward_row and not reverse_row:
        raise CrossTenantConsentDenied(
            f"No active platform_tenant_relationships row connects "
            f"tenant {requesting_tenant_id!r} to {partner_tenant_id!r}; "
            "cross-tenant freebusy requires a connected relationship."
        )

    # Bilateral consent — BOTH directions of the PTR pair must exist
    # AND BOTH must agree on "full_details" for the response to upgrade
    # to event-content detail.
    #
    # Step 4.1 latent privacy bug fix (Q2 confirmed pre-build): the
    # original Step 3 logic ``all(level == "full_details" for level in
    # consent_levels)`` returned True for ``all([])`` (vacuously true
    # when consent_levels is empty) AND for single-row [full_details]
    # cases. That meant: if only forward_row (caller→partner) existed
    # with full_details AND reverse_row was missing, the response
    # leaked partner's data without partner ever consenting.
    #
    # Fix: require BOTH forward_row + reverse_row to exist AND both
    # carry full_details. Missing reverse_row means partner never had
    # an opportunity to opt in — privacy default per §3.26.16.6.
    bilateral_full_details = (
        forward_row is not None
        and reverse_row is not None
        and forward_row.calendar_freebusy_consent == "full_details"
        and reverse_row.calendar_freebusy_consent == "full_details"
    )
    consent_level: Literal["free_busy_only", "full_details"] = (
        "full_details" if bilateral_full_details else "free_busy_only"
    )

    # Aggregate freebusy across all active accounts in the partner tenant.
    partner_accounts = (
        db.query(CalendarAccount)
        .filter(
            CalendarAccount.tenant_id == partner_tenant_id,
            CalendarAccount.is_active.is_(True),
        )
        .all()
    )

    if not partner_accounts:
        return FreebusyResult(
            windows=[],
            consent_level=consent_level,
            last_sync_at=None,
            stale=False,
            partner_tenant_id=partner_tenant_id,
        )

    # Aggregate windows from all accounts; canonical recurrence engine
    # expands recurring events; transparent + cancelled excluded
    # per RFC 5545 TRANSP semantics.
    all_windows: list[FreebusyWindow] = []
    last_sync_candidates: list[datetime] = []
    stale_seen = False

    for account in partner_accounts:
        partial = _query_account_freebusy_canonical(
            db,
            account=account,
            range_start=range_start,
            range_end=range_end,
            consent_level=consent_level,
        )
        all_windows.extend(partial.windows)
        if partial.last_sync_at is not None:
            last_sync_candidates.append(partial.last_sync_at)
        if partial.stale:
            stale_seen = True

    # Sort + dedup overlapping windows from multiple accounts.
    all_windows.sort(key=lambda w: (w.start_at, w.end_at))

    # Step 5 (Q6 confirmed pre-build): hour/day granularity coarsening.
    # Per §3.26.16.6: "Anonymization granularity for free/busy
    # (three-tier): subject hashing optional ... attendee counts surface
    # coarsely ... specific attendee identities surface only with
    # explicit consent." The granularity parameter controls
    # WINDOW-LEVEL coarsening — bucket-aggregation at hour or day
    # boundaries with status-precedence. Privacy-preserving: coarsening
    # only LOSES detail; never exposes more than consent_level allows.
    # Step 3 stub accepted the parameter; Step 5 implements canonical
    # bucket aggregation per §3.26.16.10 cross-surface UX needs.
    #
    # **Bilateral full_details consent skips coarsening.** When both
    # tenants have explicitly opted into full-detail sharing per
    # §3.26.16.6 anonymization-at-layer canon, coarsening is NOT
    # applied — partners receive raw window detail (subject, location,
    # attendee_count_bucket) at the consent_level the bilateral PTR
    # pair authorizes. Coarsening is the privacy fallback for
    # ``free_busy_only`` consent (the default), not a universal filter.
    if granularity in ("hour", "day") and consent_level != "full_details":
        all_windows = _coarsen_windows(
            all_windows,
            granularity=granularity,
            consent_level=consent_level,
        )

    last_sync = min(last_sync_candidates) if last_sync_candidates else None

    return FreebusyResult(
        windows=all_windows,
        consent_level=consent_level,
        last_sync_at=last_sync,
        stale=stale_seen,
        partner_tenant_id=partner_tenant_id,
    )


# ─────────────────────────────────────────────────────────────────────
# Step 5 — granularity coarsening per Q6 confirmed
# ─────────────────────────────────────────────────────────────────────


# Status-precedence per Q6 confirmed: when bucket aggregates multiple
# events with different statuses, busy wins over tentative wins over
# out_of_office. Privacy-preserving: aggregate result reveals "this
# bucket has SOMETHING busy" without exposing per-event detail.
_STATUS_PRECEDENCE: dict[str, int] = {
    "busy": 3,
    "tentative": 2,
    "out_of_office": 1,
}


def _aggregate_status(
    statuses: list[str],
) -> Literal["busy", "tentative", "out_of_office"]:
    """Return the highest-precedence status across a list of windows.

    Per Q6 confirmed pre-build: busy-OR-tentative-OR-OOO precedence.
    Defensive default to "busy" if list empty (caller filters empties).
    """
    if not statuses:
        return "busy"
    sorted_statuses = sorted(
        statuses, key=lambda s: _STATUS_PRECEDENCE.get(s, 0), reverse=True
    )
    top = sorted_statuses[0]
    return top if top in _STATUS_PRECEDENCE else "busy"


def _coarsen_windows(
    windows: list[FreebusyWindow],
    *,
    granularity: Literal["hour", "day"],
    consent_level: Literal["internal", "free_busy_only", "full_details"],
) -> list[FreebusyWindow]:
    """Aggregate windows into hour or day buckets with status-precedence.

    Per Q6 confirmed pre-build: window-bucket-aggregation algorithm.
    Privacy-preserving:
      - Coarsened windows DROP subject + location regardless of
        consent_level. Per §3.26.16.6 anonymization canonical: when
        operator chooses coarsened view, detail is LOST not preserved
        — coarsening exposes less than original, never more.
      - attendee_count_bucket is dropped at coarsening since the bucket
        spans multiple events with possibly different attendee counts.

    Algorithm:
      - Bucket every input window by floor(start_at, granularity).
      - For each bucket, walk member windows; aggregate status per
        ``_aggregate_status`` precedence; produce a single output
        window spanning [bucket_start, bucket_start + granularity_unit).
      - Skip empty buckets (no aggregated output for buckets where no
        events fall within).
    """
    if not windows:
        return []

    bucket_seconds = 3600 if granularity == "hour" else 86400
    bucket_unit = timedelta(seconds=bucket_seconds)

    # Group windows by bucket key (floor of start_at to bucket boundary).
    buckets: dict[datetime, list[FreebusyWindow]] = {}
    for w in windows:
        # Floor to bucket boundary in UTC frame (granularity is
        # cross-tenant aggregate; tenant timezone application happens
        # at frontend display per §14.10.1 timezone canon).
        if granularity == "hour":
            bucket_key = w.start_at.replace(minute=0, second=0, microsecond=0)
        else:  # day
            bucket_key = w.start_at.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        buckets.setdefault(bucket_key, []).append(w)

    # Build coarsened output — one window per non-empty bucket.
    coarsened: list[FreebusyWindow] = []
    for bucket_key in sorted(buckets.keys()):
        members = buckets[bucket_key]
        agg_status = _aggregate_status([m.status for m in members])
        coarsened.append(
            FreebusyWindow(
                start_at=bucket_key,
                end_at=bucket_key + bucket_unit,
                status=agg_status,
                # Subject + location + attendee_count_bucket DROPPED
                # at coarsening per privacy-preserving discipline —
                # bucket spans multiple events; original detail no
                # longer applies.
                subject=None,
                location=None,
                attendee_count_bucket=None,
            )
        )

    return coarsened


# ─────────────────────────────────────────────────────────────────────
# Internal query helper
# ─────────────────────────────────────────────────────────────────────


_STALE_THRESHOLD_SECONDS = 600  # 10 minutes


def _query_account_freebusy_canonical(
    db: Session,
    *,
    account: CalendarAccount,
    range_start: datetime,
    range_end: datetime,
    consent_level: Literal["internal", "free_busy_only", "full_details"],
) -> FreebusyResult:
    """Query freebusy for a single account against canonical recurrence engine.

    Per §3.26.16.4: filter to active opaque non-cancelled master events
    (recurrence_master_event_id IS NULL — masters only, since override
    rows are referenced by the recurrence engine via
    calendar_event_instance_overrides during expansion). Recurring
    events expand via materialize_instances_for_events.

    Last-sync staleness disclosure per §3.26.16.8: stale=True if the
    account's sync_state.last_sync_at is older than _STALE_THRESHOLD_SECONDS
    (10 minutes default). Stale-but-correct is preferred per canonical
    transparency discipline.

    consent_level controls populated fields:
      - "internal" → subject + location populated (full_details for
        own-tenant)
      - "free_busy_only" → status-only (subject + location omitted)
      - "full_details" → subject + location + attendee_count_bucket
        populated per §3.26.16.6
    """
    events = (
        db.query(CalendarEvent)
        .filter(
            CalendarEvent.account_id == account.id,
            CalendarEvent.is_active.is_(True),
            CalendarEvent.status != "cancelled",
            CalendarEvent.transparency == "opaque",
            CalendarEvent.recurrence_master_event_id.is_(None),
            or_(
                CalendarEvent.recurrence_rule.is_(None),
                CalendarEvent.start_at < range_end,
            ),
        )
        .all()
    )

    materialized = materialize_instances_for_events(
        db,
        events=events,
        range_start=range_start,
        range_end=range_end,
    )

    # Map each materialized instance → FreebusyWindow with the appropriate
    # consent-level fields populated.
    windows: list[FreebusyWindow] = []
    for mi in materialized:
        if mi.status == "cancelled" or mi.transparency != "opaque":
            continue

        status: Literal["busy", "tentative", "out_of_office"] = (
            "tentative" if mi.status == "tentative" else "busy"
        )

        if consent_level == "free_busy_only":
            window = FreebusyWindow(
                start_at=mi.start_at,
                end_at=mi.end_at,
                status=status,
            )
        else:
            # Internal OR full_details: include subject + location.
            attendee_count_bucket = None
            if consent_level == "full_details":
                # §3.26.16.6 three-tier anonymization: coarse attendee
                # counts only.
                attendee_count_bucket = _attendee_count_bucket(
                    db, event_id=mi.event_id
                )

            window = FreebusyWindow(
                start_at=mi.start_at,
                end_at=mi.end_at,
                status=status,
                subject=mi.subject,
                location=_location_for_event(db, event_id=mi.event_id),
                attendee_count_bucket=attendee_count_bucket,
            )
        windows.append(window)

    # Last-sync staleness check.
    sync_state = account.sync_state
    last_sync = sync_state.last_sync_at if sync_state else None
    stale = False
    if last_sync is not None:
        age_seconds = (datetime.now(timezone.utc) - last_sync).total_seconds()
        stale = age_seconds > _STALE_THRESHOLD_SECONDS

    return FreebusyResult(
        windows=windows,
        consent_level=consent_level,
        last_sync_at=last_sync,
        stale=stale,
    )


def _attendee_count_bucket(db: Session, *, event_id: str) -> str:
    """Compute coarse attendee count bucket per §3.26.16.6 anonymization.

    Buckets: ``"1"`` | ``"2-5"`` | ``"6+"``.
    """
    from app.models.calendar_primitive import CalendarEventAttendee

    count = (
        db.query(CalendarEventAttendee)
        .filter(CalendarEventAttendee.event_id == event_id)
        .count()
    )
    if count <= 1:
        return "1"
    if count <= 5:
        return "2-5"
    return "6+"


def _location_for_event(db: Session, *, event_id: str) -> str | None:
    """Lookup canonical event location for full_details consent path."""
    event = (
        db.query(CalendarEvent.location)
        .filter(CalendarEvent.id == event_id)
        .first()
    )
    return event.location if event else None
