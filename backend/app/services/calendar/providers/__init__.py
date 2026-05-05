"""Calendar provider abstraction — Phase W-4b Layer 1 §3.26.16.4.

Per BRIDGEABLE_MASTER §3.26.16.4, every calendar account connects
through a provider implementation that conforms to the
``CalendarProvider`` ABC. Step 1 ships the ABC + 3 implementations:

    GoogleCalendarProvider             — Google Calendar OAuth (stub)
    MicrosoftGraphCalendarProvider     — Microsoft 365 OAuth (stub)
    LocalCalendarProvider              — Bridgeable-native, no transport
                                         (functional Step 1 implementation
                                         per Q4 architectural decision)

Per Q3 architectural decision (confirmed pre-build): CalDAV provider
**omitted entirely** from Step 1 package per canonical deferral
(§3.26.16.4 + §3.26.7.5). When concrete operator signal warrants, add
``caldav.py`` provider as separate scoped session.

Stubs implement the ABC contract but raise ``NotImplementedError`` for
operations that require real provider integration (OAuth exchange,
initial sync, fetch_event, etc). Step 2 wires real OAuth + sync
infrastructure on top. The local provider ships functional at Step 1.

The native-CalDAV implementation alluded to in §3.26.16.1 lands as a
4th provider (``CalDAVProvider``) without disturbing this contract,
when CalDAV interop maturity warrants per the integrate-now-make-
native-later framework.
"""

from app.services.calendar.providers.base import (
    CalendarProvider,
    PROVIDER_REGISTRY,
    get_provider_class,
    register_provider,
)
from app.services.calendar.providers.google_calendar import GoogleCalendarProvider
from app.services.calendar.providers.local import LocalCalendarProvider
from app.services.calendar.providers.msgraph import MicrosoftGraphCalendarProvider

# Side-effect registration: importing this package registers all 3
# Step-1 providers into PROVIDER_REGISTRY. Future native CalDAV provider
# would register here as well.
register_provider("google_calendar", GoogleCalendarProvider)
register_provider("msgraph", MicrosoftGraphCalendarProvider)
register_provider("local", LocalCalendarProvider)

__all__ = [
    "CalendarProvider",
    "PROVIDER_REGISTRY",
    "get_provider_class",
    "register_provider",
    "GoogleCalendarProvider",
    "MicrosoftGraphCalendarProvider",
    "LocalCalendarProvider",
]
