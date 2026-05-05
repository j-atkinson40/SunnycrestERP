"""Calendar Primitive service layer — Phase W-4b Layer 1 (§3.26.16).

This package implements the *canonical Calendar primitive* described in
BRIDGEABLE_MASTER §3.26.16 — provider abstraction + threaded calendar/
account/sync infrastructure for inbound + outbound + cross-tenant joint
scheduling. It is deliberately distinct from the platform's existing
**Vault iCal feed** at ``GET /api/v1/vault/calendar.ics`` which serializes
VaultItems with event_type to one-way iCalendar text for external
calendar clients.

The two surfaces coexist per CLAUDE.md coexist-with-legacy discipline:

  - Existing (Vault):
    one-way iCal export (operator subscribes phone calendar to their
    token-protected feed URL); read-only from external clients'
    perspective; no provider abstraction; no threaded sync; no attendee
    modeling; no cross-tenant pairing. Ships at
    ``app.api.routes.vault.get_calendar_feed``.

  - This package (W-4b §3.26.16):
    bidirectional sync with provider accounts (Google Calendar,
    Microsoft 365, Bridgeable-native local); attendees + responses;
    recurrence engine (Step 2); cross-tenant bilateral joint events
    (Step 4); magic-link contextual surface for external participants
    (Step 4); Workshop integration; Intelligence integration.

Step 1 ships entity foundation + provider abstraction stubs +
CalendarAccount service layer + UI for tenant admins to create/manage
CalendarAccount + CalendarAccountAccess records. Subsequent Steps 2-N
(real OAuth + sync, RRULE engine activation, outbound, free/busy
substrate, cross-tenant joint events, action tokens, cross-surface
rendering, Workshop integration, Intelligence integration) build atop
this foundation.

**Per Q3 architectural decision**: CalDAV provider omitted entirely
from Step 1 package per canonical deferral (§3.26.16.4 + §3.26.7.5).
When concrete operator signal warrants, add ``caldav.py`` provider as
separate scoped session — easier to add a provider than maintain unused
stub.

**Per Q4 architectural decision**: local provider ships **functional**
at Step 1 (zero transport, Bridgeable-native events stored without
provider round-trip). Local provider has no transport — implementing
is just "store the event" — cheap to implement and immediately useful
for state-changes-generate-events drafting in Step 3.
"""

from app.services.calendar import account_service
from app.services.calendar.providers import (
    CalendarProvider,
    PROVIDER_REGISTRY,
    get_provider_class,
)

# Side-effect import — registers the 5 canonical Calendar action_types
# (service_date_acceptance, delivery_date_acceptance,
# joint_event_acceptance, recurring_meeting_proposal,
# event_reschedule_proposal) per §3.26.16.17 against the central
# platform action registry. Pattern parallels Email package init
# importing email_action_service for substrate consolidation per Path B.
from app.services.calendar import calendar_action_service  # noqa: F401

__all__ = [
    "account_service",
    "calendar_action_service",
    "CalendarProvider",
    "PROVIDER_REGISTRY",
    "get_provider_class",
]
