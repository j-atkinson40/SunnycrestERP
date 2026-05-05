"""LocalCalendarProvider — functional Step 1 + Step 2 implementation.

Per BRIDGEABLE_MASTER §3.26.16.1: local provider is a canonical
first-class citizen — distinct from the Email primitive's
transactional-send-only provider. Some calendar events are purely
operational ("this delivery is scheduled for Thursday") and don't need
external propagation. The local provider stores them as canonical
CalendarEvent without invitation transport.

**Q4 architectural decision (Step 1):** local provider ships
**functional** at Step 1 (zero transport, Bridgeable-native events
stored without provider round-trip).

**Q1 Path A architectural decision (Step 2):** providers receive
optional ``db_session`` + ``account_id`` constructor params instead
of the Step-1 ``__db__`` injection hack. Local provider uses both.

**What the local provider does NOT do:**
  - It does NOT have a separate inbox to sync — events are created
    directly via ``event_service.create_event()`` against the
    canonical ``calendar_events`` table.
  - It does NOT have a separate provider_event_id namespace — local
    events leave ``provider_event_id`` NULL on the canonical row.
  - It does NOT subscribe to realtime callbacks — there's no remote
    state to subscribe to.
  - It does NOT fetch attendee responses from a remote provider —
    response state lives directly on canonical
    ``calendar_event_attendees`` rows.

**What the local provider DOES do:**
  - ``connect()`` succeeds immediately (no OAuth, no credentials).
  - ``disconnect()`` is a no-op.
  - ``sync_initial()`` returns success with zero events synced (there's
    no provider-side inbox to backfill — events live directly in the
    canonical table).
  - ``fetch_freebusy()`` answers from canonical CalendarEvent rows
    directly — no provider round-trip required. **Step 2 extends to
    handle recurring events via recurrence_engine** (Step 1 was
    non-recurring-only per architectural Q2).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services.calendar.providers.base import (
    CalendarProvider,
    ProviderAttendeeRef,
    ProviderConnectResult,
    ProviderFetchedEvent,
    ProviderFreeBusyResult,
    ProviderFreeBusyWindow,
    ProviderSendEventResult,
    ProviderSyncResult,
)


class LocalCalendarProvider(CalendarProvider):
    provider_type = "local"
    display_label = "Bridgeable (no external sync)"
    supports_inbound = False  # No external inbox to sync from
    supports_realtime = False  # No realtime subscription (no remote state)
    supports_freebusy = True  # Answered from canonical rows directly

    def connect(
        self, oauth_redirect_payload: dict[str, Any] | None = None
    ) -> ProviderConnectResult:
        # Local provider has no external connection to establish.
        # The "connection" is just the CalendarAccount row pointing at
        # the canonical CalendarEvent table. Returning success
        # immediately is correct.
        return ProviderConnectResult(
            success=True,
            provider_account_id=self.account_config.get("primary_email_address"),
            config_to_persist={
                "transport": "bridgeable_native",
                "external_propagation": False,
            },
        )

    def disconnect(self) -> None:
        # No external resources to tear down.
        return None

    def sync_initial(
        self,
        *,
        backfill_window_days: int = 90,
        lookahead_window_days: int = 365,
    ) -> ProviderSyncResult:
        # No external inbox to sync — local events live directly in the
        # canonical ``calendar_events`` table. Returning success with
        # zero events synced is the correct shape; callers see this as
        # "sync completed, no-op."
        return ProviderSyncResult(
            success=True,
            events_synced=0,
            last_sync_at=None,
            error_message=None,
        )

    def subscribe_realtime(self) -> bool:
        # Local provider has no remote state to subscribe to. Return
        # False (NOT raise) — the contract says "False if the provider
        # doesn't support realtime."
        return False

    def fetch_event(self, provider_event_id: str) -> ProviderFetchedEvent:
        # Local events are accessed via canonical ``event_service.get_event()``
        # not via a provider round-trip. Calling this on a local provider
        # is a programmer error — surface it clearly.
        raise NotImplementedError(
            "LocalCalendarProvider.fetch_event is not applicable — local "
            "events live in the canonical calendar_events table. Use "
            "event_service.get_event() instead."
        )

    def fetch_attendee_responses(
        self, provider_event_id: str
    ) -> list[ProviderAttendeeRef]:
        # Same rationale as fetch_event — attendee state lives directly
        # on canonical calendar_event_attendees rows.
        raise NotImplementedError(
            "LocalCalendarProvider.fetch_attendee_responses is not applicable "
            "— attendee response state lives in the canonical "
            "calendar_event_attendees table. Query directly."
        )

    def fetch_freebusy(
        self,
        *,
        calendar_id: str | None,
        time_range_start: datetime,
        time_range_end: datetime,
    ) -> ProviderFreeBusyResult:
        """Answer free/busy directly from canonical CalendarEvent rows.

        Per §3.26.16.4 RRULE-as-source-of-truth: when local provider
        answers free/busy, the query happens against Bridgeable's
        canonical recurrence engine — no provider round-trip required.

        **Step 2 extends Step 1's non-recurring-only implementation to
        handle recurring events via recurrence_engine.materialize_instances**
        (closes Step 1 architectural Q2). Recurring events with non-NULL
        ``recurrence_rule`` are expanded by the canonical engine; EXDATE
        + modified-instance shadowing apply per §3.26.16.4.

        **Q1 Path A**: db_session + account_id come from the constructor
        params (set by sync_engine before calling). Backwards-compat
        with Step 1's __db__ + __account_id__ injection: if
        constructor params not set, fall back to account_config keys.
        """
        from sqlalchemy import or_

        from app.models.calendar_primitive import CalendarEvent
        from app.services.calendar.recurrence_engine import (
            materialize_instances_for_events,
        )

        # Resolve db_session + account_id with backwards-compat fallback.
        db = self.db_session or self.account_config.get("__db__")
        account_id = self.account_id or self.account_config.get("__account_id__")

        if db is None or account_id is None:
            return ProviderFreeBusyResult(
                success=False,
                windows=[],
                error_message=(
                    "LocalCalendarProvider.fetch_freebusy requires "
                    "db_session + account_id (Step 2 Q1 Path A: pass to "
                    "constructor) — caller must set these. Direct provider "
                    "invocation outside the calendar service layer not "
                    "supported."
                ),
            )

        # Per §3.26.16.4 + §3.26.16.5 transparency: query canonical
        # CalendarEvent rows for the account, filtered by:
        #   - active rows only
        #   - cancelled events excluded (RFC 5545 cancelled events do
        #     NOT count toward free/busy)
        #   - opaque-only (transparent events do NOT count toward
        #     free/busy per RFC 5545 TRANSP)
        # Then expand recurring events via canonical recurrence engine
        # within the time range; produce free/busy windows from
        # materialized instances.

        # Step 1 partial scope: non-recurring events only (recurrence_rule IS NULL).
        # Step 2: include recurring events; recurrence engine expands them.
        events = (
            db.query(CalendarEvent)
            .filter(
                CalendarEvent.account_id == account_id,
                CalendarEvent.is_active.is_(True),
                CalendarEvent.status != "cancelled",
                CalendarEvent.transparency == "opaque",
                # For recurrence rows we want masters only (not the
                # instance-override rows pointed at by overrides).
                # Master rows have recurrence_master_event_id IS NULL;
                # non-recurring also satisfies that filter.
                CalendarEvent.recurrence_master_event_id.is_(None),
                # Either non-recurring with overlap, or recurring (range
                # check happens during expansion).
                or_(
                    # Non-recurring events: direct overlap check.
                    CalendarEvent.recurrence_rule.is_(None),
                    # Recurring events: filter naively to events that
                    # COULD overlap (started before range_end). Real
                    # overlap determined by RRULE expansion below.
                    CalendarEvent.start_at < time_range_end,
                ),
            )
            .all()
        )

        # Per §3.26.16.4 "Cap instance count per query at 500 (defensive
        # against pathological recurrence rules like FREQ=SECONDLY)" —
        # apply per-event cap; bulk expansion delegates to engine.
        materialized = materialize_instances_for_events(
            db,
            events=events,
            range_start=time_range_start,
            range_end=time_range_end,
        )

        # Filter the materialized results to only those that survive the
        # opaque + non-cancelled check (RRULE expansion may include
        # overrides whose status is cancelled — recurrence engine
        # already skips is_cancelled overrides, but we re-check here
        # for defense-in-depth).
        windows = [
            ProviderFreeBusyWindow(
                start_at=mi.start_at,
                end_at=mi.end_at,
                status=("tentative" if mi.status == "tentative" else "busy"),
            )
            for mi in materialized
            if mi.status != "cancelled" and mi.transparency == "opaque"
        ]

        return ProviderFreeBusyResult(
            success=True,
            windows=windows,
            last_sync_at=datetime.now(tz=time_range_start.tzinfo),
            error_message=None,
        )

    def send_event(
        self,
        *,
        vcalendar_text: str,
        method: str = "REQUEST",
    ) -> ProviderSendEventResult:
        """Step 3 outbound for local provider — no transport.

        Per §3.26.16.5 + Q4 architectural decision: local provider events
        are Bridgeable-native; outbound through this provider is a
        functional no-op (event already persisted canonically by the
        time the outbound service calls send_event). Returns success
        immediately with no provider_event_id.

        The outbound service still calls send_event uniformly across
        all providers so the audit log + commit-from-tentative state
        machine works the same way regardless of provider type.
        """
        return ProviderSendEventResult(
            success=True,
            provider_event_id=None,  # Local events have no provider id
            provider_calendar_id=None,
            error_message=None,
        )
