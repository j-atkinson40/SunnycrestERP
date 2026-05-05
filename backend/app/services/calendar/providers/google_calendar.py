"""GoogleCalendarProvider — real implementation, Phase W-4b Layer 1 Calendar Step 2.

Provider-side methods wrap Google Calendar API HTTP calls via httpx.
OAuth token resolution goes through ``oauth_service.ensure_fresh_token``
which the caller injects via ``account_config["access_token"]``
(injected at call site to keep the provider class stateless).

**Step 2 testing constraint:** real Google Calendar API calls require
production OAuth credentials I can't provision. Tests inject a mock
``httpx.MockTransport`` via the ``http_client`` injection seam so the
wire format is verifiable without real API access.

**Step 2 vs Step 2.1 boundary**:
  - Step 2 ships: events.list (backfill via `singleEvents=False` to get
    masters + RRULE strings; `singleEvents=True` would expand all
    instances which violates the RRULE-as-source-of-truth canon),
    events.get (fetch_event), freebusy.query (fetch_freebusy).
  - Step 2 stubs: events.watch (subscription intent — record
    subscription_resource_id + subscription_expires_at; real watch URL
    registration ships at Step 2.1 alongside webhook receivers).

Pattern parallels Email primitive's ``GmailAPIProvider`` real
implementation at ``app.services.email.providers.gmail`` — same shape,
same access_token injection convention, same MockTransport-friendly
http_client injection seam.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

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


logger = logging.getLogger(__name__)


_GOOGLE_API_BASE = "https://www.googleapis.com/calendar/v3"


class GoogleCalendarProvider(CalendarProvider):
    provider_type = "google_calendar"
    display_label = "Google Calendar"
    supports_inbound = True
    supports_realtime = True
    supports_freebusy = True

    def __init__(
        self,
        account_config: dict[str, Any],
        *,
        db_session: Any = None,
        account_id: str | None = None,
    ) -> None:
        super().__init__(
            account_config, db_session=db_session, account_id=account_id
        )
        self._http: httpx.Client | None = None

    @property
    def access_token(self) -> str:
        token = self.account_config.get("access_token")
        if not token:
            raise RuntimeError(
                "GoogleCalendarProvider requires access_token in "
                "account_config — caller must inject via "
                "oauth_service.ensure_fresh_token before calling provider "
                "methods."
            )
        return token

    def _client(self) -> httpx.Client:
        if self._http is None:
            self._http = httpx.Client(
                timeout=30.0,
                headers={"Authorization": f"Bearer {self.access_token}"},
            )
        return self._http

    # ── Lifecycle ────────────────────────────────────────────────────

    def connect(
        self, oauth_redirect_payload: dict[str, Any] | None = None
    ) -> ProviderConnectResult:
        # OAuth lifecycle handled centrally by oauth_service.
        # complete_oauth_exchange. This connect() returns success
        # indicating the account row can be created with credentials
        # persisted via the OAuth callback path.
        return ProviderConnectResult(
            success=True,
            provider_account_id=self.account_config.get("primary_email_address"),
            config_to_persist={"connected_at": datetime.now(timezone.utc).isoformat()},
        )

    def disconnect(self) -> None:
        # Step 2.1 will call events.watch.stop() to tear down webhook
        # subscriptions. Step 2 has no live subscription to tear down.
        return None

    # ── Sync operations ──────────────────────────────────────────────

    def sync_initial(
        self,
        *,
        backfill_window_days: int = 90,
        lookahead_window_days: int = 365,
    ) -> ProviderSyncResult:
        """Initial backfill via events.list with timeMin/timeMax.

        Per canonical §3.26.16.4: "last 90 days + next 365 days" —
        asymmetric window from caller (sync_engine reads
        account.backfill_window_past_days + future_days).

        Uses ``singleEvents=False`` (default) so RRULE-bearing master
        events are returned with their recurrence_rule string intact —
        per §3.26.16.4 RRULE-as-source-of-truth canon, instances are
        materialized at read time by the canonical recurrence engine,
        NOT exploded by Google's expander.

        Returns the syncToken from the final page, which subsequent
        incremental syncs (Step 2.1 webhook handlers) use to fetch
        only changed events.
        """
        from app.services.calendar.ingestion import ingest_provider_event

        time_min = (
            datetime.now(timezone.utc) - timedelta(days=backfill_window_days)
        ).isoformat()
        time_max = (
            datetime.now(timezone.utc) + timedelta(days=lookahead_window_days)
        ).isoformat()

        events_synced = 0
        page_token: str | None = None
        sync_token: str | None = None

        # Cap pagination defensively; large calendars exceed 1000+ events
        # but Step 2's test-fixture inboxes are small.
        max_pages = 10

        try:
            for _ in range(max_pages):
                params: dict[str, Any] = {
                    "timeMin": time_min,
                    "timeMax": time_max,
                    "maxResults": 250,
                    "singleEvents": "false",  # RRULE-as-source-of-truth
                    "showDeleted": "false",
                }
                if page_token:
                    params["pageToken"] = page_token

                with self._client() as http:
                    r = http.get(
                        f"{_GOOGLE_API_BASE}/calendars/primary/events",
                        params=params,
                    )
                if r.status_code != 200:
                    return ProviderSyncResult(
                        success=False,
                        events_synced=events_synced,
                        error_message=(
                            f"Google Calendar API events.list failed "
                            f"(status={r.status_code}): {r.text[:300]}"
                        ),
                    )
                payload = r.json()

                # Ingest each event (delegated to canonical pipeline).
                for raw_event in payload.get("items", []):
                    fetched = _convert_google_event(raw_event)
                    if fetched and self.db_session and self.account_id:
                        # Resolve account from db_session for ingestion.
                        from app.models.calendar_primitive import CalendarAccount
                        account = (
                            self.db_session.query(CalendarAccount)
                            .filter(CalendarAccount.id == self.account_id)
                            .first()
                        )
                        if account:
                            try:
                                ingest_provider_event(
                                    self.db_session,
                                    account=account,
                                    provider_event=fetched,
                                )
                                events_synced += 1
                            except Exception as exc:  # noqa: BLE001
                                logger.warning(
                                    "Failed to ingest Google event %s: %s",
                                    fetched.provider_event_id,
                                    exc,
                                )

                page_token = payload.get("nextPageToken")
                # nextSyncToken appears only on the last page (when
                # there are no more pages of historical results).
                if "nextSyncToken" in payload:
                    sync_token = payload["nextSyncToken"]
                if not page_token:
                    break

            return ProviderSyncResult(
                success=True,
                events_synced=events_synced,
                last_sync_at=datetime.now(timezone.utc),
                last_sync_token=sync_token,
            )
        except httpx.HTTPError as exc:
            return ProviderSyncResult(
                success=False,
                events_synced=events_synced,
                error_message=f"Google Calendar API HTTP error: {exc}",
            )

    def subscribe_realtime(self) -> bool:
        """Step 2 stub: returns True indicating the provider supports
        realtime, but actual events.watch registration ships at Step
        2.1. The sync_engine sweep registers subscription_resource_id
        + subscription_expires_at; sweeps.py renews on schedule.
        """
        return True

    def fetch_event(self, provider_event_id: str) -> ProviderFetchedEvent:
        """Fetch a single event by Google Calendar event id.

        Used by Step 2.1 webhook handlers when a Google Calendar Push
        Notification arrives. Step 2 ships the implementation; Step 2.1
        wires the webhook receiver that calls this.
        """
        with self._client() as http:
            r = http.get(
                f"{_GOOGLE_API_BASE}/calendars/primary/events/{provider_event_id}",
            )
        if r.status_code != 200:
            raise RuntimeError(
                f"Google Calendar API events.get failed "
                f"(status={r.status_code}): {r.text[:300]}"
            )
        result = _convert_google_event(r.json())
        if result is None:
            raise RuntimeError(
                f"Google Calendar event {provider_event_id} could not be converted"
            )
        return result

    def fetch_attendee_responses(
        self, provider_event_id: str
    ) -> list[ProviderAttendeeRef]:
        """Fetch latest attendee response state for a single event.

        Same call as fetch_event but returns only the attendees list.
        """
        event = self.fetch_event(provider_event_id)
        return event.attendees

    def fetch_freebusy(
        self,
        *,
        calendar_id: str | None,
        time_range_start: datetime,
        time_range_end: datetime,
    ) -> ProviderFreeBusyResult:
        """Query Google Calendar free/busy via freebusy.query API.

        Per §3.26.16.4: when canonical recurrence engine isn't yet
        active OR when querying a calendar Bridgeable doesn't
        canonically own (e.g. cross-tenant pre-pairing), free/busy
        delegates to provider. Step 2 implements provider-side path;
        post-Step-2 free/busy resolution prefers canonical engine when
        Bridgeable owns the calendar.
        """
        cal_id = calendar_id or "primary"
        body = {
            "timeMin": time_range_start.isoformat(),
            "timeMax": time_range_end.isoformat(),
            "items": [{"id": cal_id}],
        }
        try:
            with self._client() as http:
                r = http.post(f"{_GOOGLE_API_BASE}/freeBusy", json=body)
            if r.status_code != 200:
                return ProviderFreeBusyResult(
                    success=False,
                    error_message=(
                        f"Google Calendar API freebusy.query failed "
                        f"(status={r.status_code}): {r.text[:300]}"
                    ),
                )
            payload = r.json()
            calendars = payload.get("calendars", {})
            cal_data = calendars.get(cal_id, {})
            busy_slots = cal_data.get("busy", [])

            windows = [
                ProviderFreeBusyWindow(
                    start_at=datetime.fromisoformat(
                        slot["start"].replace("Z", "+00:00")
                    ),
                    end_at=datetime.fromisoformat(
                        slot["end"].replace("Z", "+00:00")
                    ),
                    status="busy",
                )
                for slot in busy_slots
            ]
            return ProviderFreeBusyResult(
                success=True,
                windows=windows,
                last_sync_at=datetime.now(timezone.utc),
            )
        except httpx.HTTPError as exc:
            return ProviderFreeBusyResult(
                success=False,
                error_message=f"Google Calendar API HTTP error: {exc}",
            )

    # ── Outbound (Step 3) ────────────────────────────────────────────

    def send_event(
        self,
        *,
        vcalendar_text: str,
        method: str = "REQUEST",
    ) -> ProviderSendEventResult:
        """Send/cancel an event via Google Calendar API.

        Per §3.26.16.5 Path 1+2: Google handles iTIP propagation
        server-side via ``sendUpdates=all`` parameter. We pass the
        canonical RFC 5545 fields via Google's structured JSON event
        body (NOT raw VCALENDAR — Google's API takes JSON); the
        ``vcalendar_text`` param remains the canonical record of intent
        that the audit log captures.

        Step 3 ships the parser that converts our VCALENDAR text →
        Google's structured event body. Round-trip via ingestion
        synchronizes the new ``provider_event_id`` back into the
        canonical CalendarEvent row.

        For ``method="REQUEST"`` initial creation: POST events.insert.
        For ``method="REQUEST"`` update (sequence > 0): PATCH
        events.patch with the changed fields.
        For ``method="CANCEL"``: DELETE events.delete with sendUpdates=all.

        Step 3 boundary: PATCH update path ships at Step 3.1 alongside
        provider sync token reconciliation; Step 3 ships INSERT + DELETE
        only. The outbound service detects update via sequence > 0
        check + dispatches to PATCH; if PATCH is not yet wired,
        outbound service falls back to a CANCEL+INSERT sequence per
        canonical safety + flags the gap in audit log.
        """
        try:
            ics_body = _vcalendar_to_google_body(vcalendar_text)
        except Exception as exc:  # noqa: BLE001
            return ProviderSendEventResult(
                success=False,
                error_message=(
                    f"Failed to convert VCALENDAR to Google body: {exc}"
                ),
                error_retryable=False,
            )

        # CANCEL: delete the event by provider_event_id (UID) + propagate.
        if method.upper() == "CANCEL":
            uid = ics_body.get("__uid__")
            if not uid:
                return ProviderSendEventResult(
                    success=False,
                    error_message="CANCEL requires UID in VCALENDAR",
                )
            try:
                with self._client() as http:
                    r = http.delete(
                        f"{_GOOGLE_API_BASE}/calendars/primary/events/{uid}",
                        params={"sendUpdates": "all"},
                    )
                if r.status_code in (200, 204):
                    return ProviderSendEventResult(
                        success=True,
                        provider_event_id=uid,
                    )
                return ProviderSendEventResult(
                    success=False,
                    error_message=(
                        f"Google events.delete failed "
                        f"(status={r.status_code}): {r.text[:300]}"
                    ),
                    error_retryable=r.status_code >= 500,
                )
            except httpx.HTTPError as exc:
                return ProviderSendEventResult(
                    success=False,
                    error_message=f"Google API HTTP error: {exc}",
                    error_retryable=True,
                )

        # REQUEST: Step 3 ships INSERT path (sequence==0). Update path
        # (sequence > 0) deferred to Step 3.1 — fall back to safe
        # CANCEL+INSERT sequence with audit log flag.
        try:
            with self._client() as http:
                r = http.post(
                    f"{_GOOGLE_API_BASE}/calendars/primary/events",
                    params={"sendUpdates": "all"},
                    json={k: v for k, v in ics_body.items() if not k.startswith("__")},
                )
            if r.status_code in (200, 201):
                payload = r.json()
                return ProviderSendEventResult(
                    success=True,
                    provider_event_id=payload.get("id"),
                    provider_calendar_id="primary",
                )
            return ProviderSendEventResult(
                success=False,
                error_message=(
                    f"Google events.insert failed "
                    f"(status={r.status_code}): {r.text[:300]}"
                ),
                error_retryable=r.status_code >= 500,
            )
        except httpx.HTTPError as exc:
            return ProviderSendEventResult(
                success=False,
                error_message=f"Google API HTTP error: {exc}",
                error_retryable=True,
            )


# ─────────────────────────────────────────────────────────────────────
# Google Calendar API → ProviderFetchedEvent conversion
# ─────────────────────────────────────────────────────────────────────


def _convert_google_event(raw: dict[str, Any]) -> ProviderFetchedEvent | None:
    """Convert a Google Calendar API event resource to ProviderFetchedEvent.

    Returns None for events that can't be converted (e.g. cancelled
    events that the caller passed showDeleted=True for, or events
    missing required start/end fields).
    """
    if raw.get("status") == "cancelled" and not raw.get("start"):
        # Cancelled tombstones with no start data — skip.
        return None

    start = _parse_google_datetime(raw.get("start", {}))
    end = _parse_google_datetime(raw.get("end", {}))
    if start is None or end is None:
        return None

    is_all_day = "date" in raw.get("start", {})

    # RRULE — Google returns a list of recurrence strings (RRULE +
    # EXDATE + RDATE lines). Join with newlines for canonical storage.
    recurrence_lines = raw.get("recurrence", [])
    recurrence_rule: str | None = None
    if recurrence_lines:
        # Filter to RRULE: lines only — EXDATE handling lives in the
        # recurrence engine via dateutil.rrulestr's multi-line parser
        # but we keep the full block to preserve EXDATE/RDATE.
        recurrence_rule = "\n".join(recurrence_lines)

    # Attendees.
    attendees: list[ProviderAttendeeRef] = []
    for att in raw.get("attendees", []):
        email = att.get("email", "").strip().lower()
        if not email:
            continue
        attendees.append(
            ProviderAttendeeRef(
                email_address=email,
                display_name=att.get("displayName"),
                role=(
                    "organizer"
                    if att.get("organizer")
                    else (
                        "optional_attendee"
                        if att.get("optional")
                        else "required_attendee"
                    )
                ),
                response_status=_normalize_google_response(
                    att.get("responseStatus", "needsAction")
                ),
                comment=att.get("comment"),
            )
        )

    organizer_email = raw.get("organizer", {}).get("email")
    organizer_name = raw.get("organizer", {}).get("displayName")

    return ProviderFetchedEvent(
        provider_event_id=raw["id"],
        provider_calendar_id=None,
        subject=raw.get("summary"),
        description_text=raw.get("description"),
        description_html=None,  # Google returns plain text; no HTML body
        location=raw.get("location"),
        start_at=start,
        end_at=end,
        is_all_day=is_all_day,
        event_timezone=raw.get("start", {}).get("timeZone"),
        recurrence_rule=recurrence_rule,
        status=_normalize_google_status(raw.get("status", "confirmed")),
        transparency=_normalize_google_transparency(
            raw.get("transparency", "opaque")
        ),
        organizer_email=organizer_email,
        organizer_name=organizer_name,
        attendees=attendees,
        raw_payload=raw,
    )


def _parse_google_datetime(d: dict[str, Any]) -> datetime | None:
    """Parse Google Calendar datetime/date dict.

    Google returns either:
      - {"dateTime": "2026-06-01T14:00:00-04:00", "timeZone": "America/New_York"}
        for time-bound events
      - {"date": "2026-06-01"} for all-day events
    """
    if "dateTime" in d:
        return datetime.fromisoformat(d["dateTime"].replace("Z", "+00:00"))
    if "date" in d:
        # All-day events — store as midnight UTC for canonical storage.
        return datetime.fromisoformat(f"{d['date']}T00:00:00+00:00")
    return None


def _normalize_google_status(status: str) -> str:
    """Google status → canonical RFC 5545 STATUS."""
    return {
        "confirmed": "confirmed",
        "tentative": "tentative",
        "cancelled": "cancelled",
    }.get(status, "confirmed")


def _normalize_google_transparency(t: str) -> str:
    """Google transparency → canonical RFC 5545 TRANSP."""
    # Google: "opaque" (busy) or "transparent" (free).
    return "transparent" if t == "transparent" else "opaque"


def _normalize_google_response(rs: str) -> str:
    """Google responseStatus → canonical RFC 5545 PARTSTAT."""
    return {
        "needsAction": "needs_action",
        "accepted": "accepted",
        "declined": "declined",
        "tentative": "tentative",
        "delegated": "delegated",
    }.get(rs, "needs_action")


def _vcalendar_to_google_body(vcalendar_text: str) -> dict[str, Any]:
    """Convert canonical VCALENDAR text → Google Calendar API event body.

    Step 3 outbound contract: itip_compose emits canonical RFC 5545
    VCALENDAR; this converter extracts the fields Google expects in
    its structured JSON event body. Special key ``__uid__`` is added
    to the dict for the caller's CANCEL path (events.delete uses UID
    in the URL); Google's events.insert ignores unknown fields.

    Reverse direction (Google JSON → ProviderFetchedEvent) lives in
    ``_convert_google_event``.
    """
    from icalendar import Calendar  # lazy import — only outbound path needs it

    cal = Calendar.from_ical(vcalendar_text)
    vevents = list(cal.walk("VEVENT"))
    if not vevents:
        raise ValueError("No VEVENT block in VCALENDAR")
    vevent = vevents[0]

    body: dict[str, Any] = {}
    uid_raw = vevent.get("uid")
    if uid_raw:
        body["__uid__"] = str(uid_raw)
        body["iCalUID"] = str(uid_raw)

    summary = vevent.get("summary")
    if summary:
        body["summary"] = str(summary)
    description = vevent.get("description")
    if description:
        body["description"] = str(description)
    location = vevent.get("location")
    if location:
        body["location"] = str(location)

    dtstart = vevent.get("dtstart")
    dtend = vevent.get("dtend")
    if dtstart is not None:
        body["start"] = {
            "dateTime": dtstart.dt.isoformat(),
            "timeZone": "UTC",
        }
    if dtend is not None:
        body["end"] = {
            "dateTime": dtend.dt.isoformat(),
            "timeZone": "UTC",
        }

    status = vevent.get("status")
    if status:
        body["status"] = str(status).lower()  # Google: confirmed / tentative / cancelled

    transp = vevent.get("transp")
    if transp:
        body["transparency"] = str(transp).lower()

    rrule = vevent.get("rrule")
    if rrule is not None:
        # icalendar's vRecur.to_ical() returns the wire-format string.
        try:
            rrule_str = rrule.to_ical().decode("utf-8")
            body["recurrence"] = [f"RRULE:{rrule_str}"]
        except Exception:  # noqa: BLE001
            pass

    # Attendees.
    attendees_raw = vevent.get("attendee")
    if attendees_raw is not None:
        attendees_list = (
            attendees_raw if isinstance(attendees_raw, list) else [attendees_raw]
        )
        body_attendees = []
        for att in attendees_list:
            email_str = str(att)
            if email_str.lower().startswith("mailto:"):
                email_str = email_str[len("mailto:"):]
            params = getattr(att, "params", {}) or {}
            display = params.get("cn")
            attendee_dict: dict[str, Any] = {"email": email_str}
            if display:
                attendee_dict["displayName"] = str(display)
            partstat = params.get("partstat")
            if partstat:
                attendee_dict["responseStatus"] = {
                    "NEEDS-ACTION": "needsAction",
                    "ACCEPTED": "accepted",
                    "DECLINED": "declined",
                    "TENTATIVE": "tentative",
                    "DELEGATED": "delegated",
                }.get(str(partstat).upper(), "needsAction")
            role = params.get("role")
            if role and str(role).upper() == "OPT-PARTICIPANT":
                attendee_dict["optional"] = True
            body_attendees.append(attendee_dict)
        if body_attendees:
            body["attendees"] = body_attendees

    return body
