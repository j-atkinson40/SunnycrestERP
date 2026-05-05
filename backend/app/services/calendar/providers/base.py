"""Calendar provider abstract base class + registry — §3.26.16.4.

The ``CalendarProvider`` ABC defines the contract every provider
implementation conforms to. Step 1 ships the ABC + 3 stub
subclasses (``google_calendar``, ``msgraph``, ``local``). Step 2
implements real OAuth + sync atop the OAuth provider stubs; the
local provider ships functional at Step 1 (zero transport).

**Pattern parallels Email primitive** ``EmailProvider`` ABC at
``app.services.email.providers.base`` — Calendar mirrors Email's
provider abstraction shape exactly. Future native CalDAV transport
implementation lands behind the same contract per the
integrate-now-make-native-later framework (§3.26.16.1).

**Spec-canon resolution recorded here** (per CLAUDE.md §12 Spec-Override
Discipline): user prompt called for 7 methods named
``list_calendars / list_events / create_event / update_event /
delete_event / get_freebusy / subscribe_to_changes``. Canonical
§3.26.16.4 specifies 7 methods named ``connect / sync_initial /
subscribe_realtime / fetch_event / fetch_attendee_responses /
fetch_freebusy / disconnect``. Canon prose wins per the in-tree-canon-is-
source-of-truth rule. Three of the user-prompt methods (``create_event /
update_event / delete_event``) are explicitly Step 3 outbound deferred
per §3.26.16.5 — adding them at Step 1 would have been premature.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# ─────────────────────────────────────────────────────────────────────
# Result dataclasses — provider operations return these typed shapes
# ─────────────────────────────────────────────────────────────────────


@dataclass
class ProviderConnectResult:
    """Returned from ``CalendarProvider.connect()``."""

    success: bool
    provider_account_id: str | None = None
    error_message: str | None = None
    # Provider-specific config to persist on CalendarAccount.provider_config.
    # E.g. Google watch resource_id; MSGraph subscription_id.
    config_to_persist: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderSyncResult:
    """Returned from ``CalendarProvider.sync_initial()`` and incremental sync."""

    success: bool
    events_synced: int = 0
    last_sync_at: datetime | None = None
    last_sync_token: str | None = None
    error_message: str | None = None


@dataclass
class ProviderEventRef:
    """Lightweight reference returned by realtime subscription callbacks."""

    provider_event_id: str
    provider_calendar_id: str | None = None
    updated_at: datetime | None = None


@dataclass
class ProviderFetchedEvent:
    """Full-fidelity event payload returned by ``fetch_event()``."""

    provider_event_id: str
    provider_calendar_id: str | None
    subject: str | None
    description_text: str | None = None
    description_html: str | None = None
    location: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    is_all_day: bool = False
    event_timezone: str | None = None
    recurrence_rule: str | None = None
    status: str = "confirmed"
    transparency: str = "opaque"
    organizer_email: str | None = None
    organizer_name: str | None = None
    attendees: list[ProviderAttendeeRef] = field(default_factory=list)
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderAttendeeRef:
    """Attendee shape returned in fetched events + attendee response batches."""

    email_address: str
    display_name: str | None = None
    role: str = "required_attendee"
    response_status: str = "needs_action"
    responded_at: datetime | None = None
    comment: str | None = None


@dataclass
class ProviderFreeBusyWindow:
    """Free/busy window returned by ``fetch_freebusy()``."""

    start_at: datetime
    end_at: datetime
    status: str  # "busy" | "tentative" | "out_of_office"


@dataclass
class ProviderFreeBusyResult:
    """Returned from ``CalendarProvider.fetch_freebusy()``."""

    success: bool
    windows: list[ProviderFreeBusyWindow] = field(default_factory=list)
    last_sync_at: datetime | None = None
    error_message: str | None = None


@dataclass
class ProviderSendEventResult:
    """Returned from ``CalendarProvider.send_event()`` per Step 3 outbound.

    Mirrors Email primitive's ``ProviderSendResult`` shape.
    """

    success: bool
    provider_event_id: str | None = None
    provider_calendar_id: str | None = None
    error_message: str | None = None
    error_retryable: bool = False


# ─────────────────────────────────────────────────────────────────────
# Abstract base class — 7 methods per canonical §3.26.16.4
# ─────────────────────────────────────────────────────────────────────


class CalendarProvider(ABC):
    """Contract every calendar provider implementation must satisfy.

    Each provider gets instantiated per-account when needed. The
    ``account_config`` dict is the persisted ``CalendarAccount.provider_config``;
    each provider interprets its slice of that config differently
    (Google expects ``credentials_json``, MSGraph expects ``tenant_id`` +
    ``client_id``, local expects nothing — it has no transport).

    Step 1 stubs implement ``provider_type`` + ``__init__`` cleanly;
    OAuth-bound methods raise ``NotImplementedError`` with a Step-2
    pointer message so missed calls fail loud rather than silently.
    The local provider ships functional at Step 1.
    """

    #: Identifier matching ``CalendarAccount.provider_type`` and the
    #: PROVIDER_REGISTRY key.
    provider_type: str = ""

    #: Human-readable label shown in the UI provider picker.
    display_label: str = ""

    #: Whether this provider supports inbound sync. ``local`` is
    #: storage-only.
    supports_inbound: bool = True

    #: Whether this provider supports realtime subscription callbacks
    #: (Google watch, MSGraph subscriptions). ``local`` doesn't sync at
    #: all — events are stored directly when created in Bridgeable.
    supports_realtime: bool = False

    #: Whether this provider supports cross-account free/busy queries.
    #: ``local`` answers from canonical CalendarEvent rows directly;
    #: external providers answer via provider-side free/busy API.
    supports_freebusy: bool = True

    def __init__(
        self,
        account_config: dict[str, Any],
        *,
        db_session: Any = None,
        account_id: str | None = None,
    ) -> None:
        """Construct a provider instance for a specific account.

        Per Step 2 Q1 Path A architectural decision: providers receive
        optional ``db_session`` + ``account_id`` constructor params so
        the canonical state surface (calendar_events table for local
        provider's freebusy; CalendarAccount row for sync engine) is
        reachable without the deliberate ``__db__`` injection hack from
        Step 1's local provider.

        OAuth providers (Google + MS Graph) generally don't need the
        db handle since they call out to external HTTP APIs — the
        constructor params are optional. Local provider uses both.
        """
        self.account_config = account_config
        self.db_session = db_session
        self.account_id = account_id

    # ── Connect / disconnect lifecycle ────────────────────────────────

    @abstractmethod
    def connect(self, oauth_redirect_payload: dict[str, Any] | None = None) -> ProviderConnectResult:
        """Establish a connection to the provider.

        For OAuth providers, ``oauth_redirect_payload`` carries the
        post-redirect tokens that need exchange. For local provider,
        connection is a no-op (returns success immediately).

        Step 1 stubs: google_calendar/msgraph raise NotImplementedError(step_2_oauth);
        local stub returns success with empty config.
        """

    @abstractmethod
    def disconnect(self) -> None:
        """Tear down provider-side subscriptions / watches.

        Idempotent. Called when a CalendarAccount is disabled or deleted.
        """

    # ── Sync operations ───────────────────────────────────────────────

    @abstractmethod
    def sync_initial(
        self, *, backfill_window_days: int = 90, lookahead_window_days: int = 365
    ) -> ProviderSyncResult:
        """Initial backfill of recent + upcoming events on first connect.

        Default backfill window per §3.26.16.4: last 90 days + next 365
        days. Step 1 stubs: google_calendar/msgraph raise
        NotImplementedError(step_2_sync); local stub returns success
        with zero events synced (local is storage-only — there's no
        provider-side inbox to backfill).
        """

    @abstractmethod
    def subscribe_realtime(self) -> bool:
        """Establish a realtime subscription if the provider supports it.

        Returns True if subscribed, False if the provider doesn't support
        realtime (e.g. local provider). Stubs raise NotImplementedError(step_2_sync).
        """

    @abstractmethod
    def fetch_event(self, provider_event_id: str) -> ProviderFetchedEvent:
        """Fetch the full payload of a single event by provider id.

        Used by inbound webhook handlers when a realtime callback brings
        a ``ProviderEventRef`` and the system needs full content.
        Stubs raise NotImplementedError(step_2_sync) for OAuth providers;
        local provider raises NotImplementedError because local events
        are Bridgeable-native and accessed via canonical CalendarEvent
        queries directly (the local provider has no separate transport).
        """

    @abstractmethod
    def fetch_attendee_responses(
        self, provider_event_id: str
    ) -> list[ProviderAttendeeRef]:
        """Fetch latest attendee response state for a single event.

        Used by sync engine to refresh attendee response_status when
        responses arrive between full event syncs. Stubs raise
        NotImplementedError(step_2_sync) for OAuth providers; local
        provider raises NotImplementedError (local events have no
        external attendee response transport).
        """

    @abstractmethod
    def fetch_freebusy(
        self,
        *,
        calendar_id: str | None,
        time_range_start: datetime,
        time_range_end: datetime,
    ) -> ProviderFreeBusyResult:
        """Query free/busy windows for a calendar over a time range.

        Per §3.26.16.4: when the canonical recurrence engine isn't yet
        active (Step 1), free/busy resolves by delegating to the provider.
        After Step 2 ships the canonical engine, free/busy queries
        prefer canonical resolution + fall back to provider only when
        canonical state is stale.

        Stubs raise NotImplementedError(step_2_sync) for OAuth providers;
        local provider implements canonical-resolution variant in Step 1
        because it can answer directly from CalendarEvent rows (no
        external transport needed).
        """

    # ── Outbound (Step 3) ────────────────────────────────────────────

    def send_event(
        self,
        *,
        vcalendar_text: str,
        method: str = "REQUEST",
    ) -> ProviderSendEventResult:
        """Send an outbound event via the provider's API per §3.26.16.5.

        Path 1 (per-account outbound) + Path 2 (update + cancellation
        propagation). Provider-specific implementations:

          - GoogleCalendarProvider: ``events.insert`` with
            ``sendUpdates=all`` parameter — Google handles iTIP
            propagation server-side via its own RFC 5546 implementation.
            Step 3 passes the canonical RFC 5545 fields via the
            structured JSON body (NOT the VCALENDAR text directly —
            Google's API takes JSON, not iCal); the ``vcalendar_text``
            param remains the canonical record of intent for audit log
            even when the provider takes structured JSON.
          - MicrosoftGraphCalendarProvider: ``POST /me/events`` with
            ``Prefer: outlook.sendNotifications=true`` header — MS
            Graph handles iTIP propagation server-side.
          - LocalCalendarProvider: no-op (success result with no
            provider_event_id; events stored canonically).

        Default implementation raises NotImplementedError so providers
        that don't implement outbound (none at Step 3 — all 3 implement)
        fail loud rather than silently no-op.
        """
        raise NotImplementedError(
            f"{self.provider_type!r} provider does not implement send_event"
        )


# ─────────────────────────────────────────────────────────────────────
# Provider registry — provider_type string → provider class
# ─────────────────────────────────────────────────────────────────────


PROVIDER_REGISTRY: dict[str, type[CalendarProvider]] = {}


def register_provider(provider_type: str, provider_class: type[CalendarProvider]) -> None:
    """Register a provider implementation in the global registry.

    Called from ``app.services.calendar.providers.__init__`` at import
    time for the 3 Step-1 stubs. Future native provider gets registered
    the same way. Re-registering an existing key replaces the previous
    implementation.
    """
    PROVIDER_REGISTRY[provider_type] = provider_class


def get_provider_class(provider_type: str) -> type[CalendarProvider]:
    """Resolve a registered provider class by ``provider_type``.

    Raises ``KeyError`` if the provider is not registered. Callers
    should validate ``provider_type`` against
    ``app.models.calendar_primitive.PROVIDER_TYPES`` before calling.
    """
    return PROVIDER_REGISTRY[provider_type]
