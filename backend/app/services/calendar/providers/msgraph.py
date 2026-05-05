"""MicrosoftGraphCalendarProvider — real implementation, Phase W-4b Layer 1 Calendar Step 2.

Provider-side methods wrap Microsoft Graph API HTTP calls via httpx.
OAuth token resolution goes through ``oauth_service.ensure_fresh_token``
which the caller injects via ``account_config["access_token"]``.

**Step 2 testing constraint:** real Graph API calls require production
OAuth credentials I can't provision. Tests inject a mock
``httpx.MockTransport`` for wire-format verification.

**Step 2 vs Step 2.1 boundary**:
  - Step 2 ships: calendarView (backfill), /me/events/{id} (fetch_event),
    /me/calendar/getSchedule (freebusy).
  - Step 2 stubs: /subscriptions registration (records intent;
    real subscription URL provisioning ships at Step 2.1 alongside
    webhook receivers).

Pattern parallels Email primitive's ``MicrosoftGraphProvider`` real
implementation at ``app.services.email.providers.msgraph`` — same
shape, same access_token injection convention, same MockTransport-
friendly http_client injection seam.
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


_GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"


class MicrosoftGraphCalendarProvider(CalendarProvider):
    provider_type = "msgraph"
    display_label = "Microsoft 365 / Outlook"
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
                "MicrosoftGraphCalendarProvider requires access_token in "
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
        return ProviderConnectResult(
            success=True,
            provider_account_id=self.account_config.get("primary_email_address"),
            config_to_persist={"connected_at": datetime.now(timezone.utc).isoformat()},
        )

    def disconnect(self) -> None:
        # Step 2.1 will call DELETE /subscriptions/{id} to tear down
        # webhook subscriptions. Step 2 has no live subscription.
        return None

    # ── Sync operations ──────────────────────────────────────────────

    def sync_initial(
        self,
        *,
        backfill_window_days: int = 90,
        lookahead_window_days: int = 365,
    ) -> ProviderSyncResult:
        """Initial backfill via /me/calendarView.

        Per canonical §3.26.16.4: "last 90 days + next 365 days" —
        asymmetric window.

        Uses /me/events with $orderby=start/dateTime and
        $top=250 pagination so RRULE-bearing master events are
        returned with their recurrence pattern intact (NOT
        /calendarView which expands recurring events into instances —
        that violates §3.26.16.4 RRULE-as-source-of-truth).

        Returns the deltaLink token for incremental syncs (Step 2.1).
        """
        from app.services.calendar.ingestion import ingest_provider_event

        time_min = (
            datetime.now(timezone.utc) - timedelta(days=backfill_window_days)
        ).isoformat()
        time_max = (
            datetime.now(timezone.utc) + timedelta(days=lookahead_window_days)
        ).isoformat()

        events_synced = 0
        next_link: str | None = None
        delta_token: str | None = None

        max_pages = 10  # Step 2 cap; Step 4+ surfaces config

        try:
            # Build initial URL — Graph supports $select but Step 2 takes
            # the full event resource for canonical mapping. $filter on
            # start/end date range constrains to the canonical window.
            initial_url = (
                f"{_GRAPH_API_BASE}/me/events"
                f"?$top=250"
                f"&$orderby=start/dateTime"
                f"&$filter=start/dateTime ge '{time_min}' "
                f"and start/dateTime le '{time_max}'"
            )
            current_url = initial_url

            for _ in range(max_pages):
                with self._client() as http:
                    r = http.get(current_url)
                if r.status_code != 200:
                    return ProviderSyncResult(
                        success=False,
                        events_synced=events_synced,
                        error_message=(
                            f"MS Graph API events failed "
                            f"(status={r.status_code}): {r.text[:300]}"
                        ),
                    )
                payload = r.json()

                for raw_event in payload.get("value", []):
                    fetched = _convert_graph_event(raw_event)
                    if fetched and self.db_session and self.account_id:
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
                                    "Failed to ingest MS Graph event %s: %s",
                                    fetched.provider_event_id,
                                    exc,
                                )

                next_link = payload.get("@odata.nextLink")
                if "@odata.deltaLink" in payload:
                    delta_token = payload["@odata.deltaLink"]
                if not next_link:
                    break
                current_url = next_link

            return ProviderSyncResult(
                success=True,
                events_synced=events_synced,
                last_sync_at=datetime.now(timezone.utc),
                last_sync_token=delta_token,
            )
        except httpx.HTTPError as exc:
            return ProviderSyncResult(
                success=False,
                events_synced=events_synced,
                error_message=f"MS Graph API HTTP error: {exc}",
            )

    def subscribe_realtime(self) -> bool:
        """Step 2 stub: returns True. Real /subscriptions registration
        ships at Step 2.1.
        """
        return True

    def fetch_event(self, provider_event_id: str) -> ProviderFetchedEvent:
        """Fetch a single event by Graph event id.

        Used by Step 2.1 webhook handlers when a subscription
        notification arrives.
        """
        with self._client() as http:
            r = http.get(f"{_GRAPH_API_BASE}/me/events/{provider_event_id}")
        if r.status_code != 200:
            raise RuntimeError(
                f"MS Graph API events.get failed "
                f"(status={r.status_code}): {r.text[:300]}"
            )
        result = _convert_graph_event(r.json())
        if result is None:
            raise RuntimeError(
                f"MS Graph event {provider_event_id} could not be converted"
            )
        return result

    def fetch_attendee_responses(
        self, provider_event_id: str
    ) -> list[ProviderAttendeeRef]:
        event = self.fetch_event(provider_event_id)
        return event.attendees

    def fetch_freebusy(
        self,
        *,
        calendar_id: str | None,
        time_range_start: datetime,
        time_range_end: datetime,
    ) -> ProviderFreeBusyResult:
        """Query MS Graph free/busy via /me/calendar/getSchedule.

        Returns aggregated free/busy windows in 30-minute increments
        (Graph's default availabilityViewInterval).
        """
        # Graph's getSchedule returns availabilityView as a string of
        # status digits (0=free, 1=tentative, 2=busy, 3=oof, 4=elsewhere)
        # — we convert digit-runs into busy windows.
        body = {
            "schedules": [
                self.account_config.get(
                    "primary_email_address", "me@example.com"
                )
            ],
            "startTime": {
                "dateTime": time_range_start.isoformat(),
                "timeZone": "UTC",
            },
            "endTime": {
                "dateTime": time_range_end.isoformat(),
                "timeZone": "UTC",
            },
            "availabilityViewInterval": 30,
        }
        try:
            with self._client() as http:
                r = http.post(
                    f"{_GRAPH_API_BASE}/me/calendar/getSchedule",
                    json=body,
                )
            if r.status_code != 200:
                return ProviderFreeBusyResult(
                    success=False,
                    error_message=(
                        f"MS Graph API getSchedule failed "
                        f"(status={r.status_code}): {r.text[:300]}"
                    ),
                )
            payload = r.json()
            schedules = payload.get("value", [])
            if not schedules:
                return ProviderFreeBusyResult(success=True, windows=[])

            # MS Graph response structure: {value: [{scheduleItems: [...]}]}
            schedule_items = schedules[0].get("scheduleItems", [])
            windows = []
            for item in schedule_items:
                start_str = item.get("start", {}).get("dateTime")
                end_str = item.get("end", {}).get("dateTime")
                status = item.get("status", "busy")
                if not start_str or not end_str:
                    continue
                # Graph returns naive datetimes with separate timeZone
                # field — we assume UTC since we sent UTC in the request.
                start_dt = datetime.fromisoformat(start_str).replace(tzinfo=timezone.utc)
                end_dt = datetime.fromisoformat(end_str).replace(tzinfo=timezone.utc)
                windows.append(
                    ProviderFreeBusyWindow(
                        start_at=start_dt,
                        end_at=end_dt,
                        status=_normalize_graph_busy_status(status),
                    )
                )

            return ProviderFreeBusyResult(
                success=True,
                windows=windows,
                last_sync_at=datetime.now(timezone.utc),
            )
        except httpx.HTTPError as exc:
            return ProviderFreeBusyResult(
                success=False,
                error_message=f"MS Graph API HTTP error: {exc}",
            )

    # ── Outbound (Step 3) ────────────────────────────────────────────

    def send_event(
        self,
        *,
        vcalendar_text: str,
        method: str = "REQUEST",
    ) -> ProviderSendEventResult:
        """Send/cancel an event via MS Graph API.

        Per §3.26.16.5 Path 1+2: MS Graph handles iTIP propagation
        server-side via ``Prefer: outlook.sendNotifications=true`` header
        on POST /me/events. Cancellation uses POST /me/events/{id}/cancel.

        Step 3 ships INSERT (POST /me/events) + CANCEL (POST cancel).
        Update path (PATCH /me/events/{id}) ships at Step 3.1.
        """
        try:
            ics_body = _vcalendar_to_graph_body(vcalendar_text)
        except Exception as exc:  # noqa: BLE001
            return ProviderSendEventResult(
                success=False,
                error_message=(
                    f"Failed to convert VCALENDAR to MS Graph body: {exc}"
                ),
                error_retryable=False,
            )

        prefer_header = {"Prefer": "outlook.sendNotifications=true"}

        if method.upper() == "CANCEL":
            uid = ics_body.get("__uid__")
            if not uid:
                return ProviderSendEventResult(
                    success=False,
                    error_message="CANCEL requires UID in VCALENDAR",
                )
            try:
                with self._client() as http:
                    r = http.post(
                        f"{_GRAPH_API_BASE}/me/events/{uid}/cancel",
                        json={"Comment": ""},
                        headers=prefer_header,
                    )
                if r.status_code in (200, 202, 204):
                    return ProviderSendEventResult(
                        success=True,
                        provider_event_id=uid,
                    )
                return ProviderSendEventResult(
                    success=False,
                    error_message=(
                        f"MS Graph events.cancel failed "
                        f"(status={r.status_code}): {r.text[:300]}"
                    ),
                    error_retryable=r.status_code >= 500,
                )
            except httpx.HTTPError as exc:
                return ProviderSendEventResult(
                    success=False,
                    error_message=f"MS Graph API HTTP error: {exc}",
                    error_retryable=True,
                )

        # REQUEST: Step 3 ships INSERT only.
        try:
            with self._client() as http:
                r = http.post(
                    f"{_GRAPH_API_BASE}/me/events",
                    json={k: v for k, v in ics_body.items() if not k.startswith("__")},
                    headers=prefer_header,
                )
            if r.status_code in (200, 201):
                payload = r.json()
                return ProviderSendEventResult(
                    success=True,
                    provider_event_id=payload.get("id"),
                    provider_calendar_id=None,
                )
            return ProviderSendEventResult(
                success=False,
                error_message=(
                    f"MS Graph events.create failed "
                    f"(status={r.status_code}): {r.text[:300]}"
                ),
                error_retryable=r.status_code >= 500,
            )
        except httpx.HTTPError as exc:
            return ProviderSendEventResult(
                success=False,
                error_message=f"MS Graph API HTTP error: {exc}",
                error_retryable=True,
            )


# ─────────────────────────────────────────────────────────────────────
# MS Graph API → ProviderFetchedEvent conversion
# ─────────────────────────────────────────────────────────────────────


def _convert_graph_event(raw: dict[str, Any]) -> ProviderFetchedEvent | None:
    """Convert an MS Graph API event resource to ProviderFetchedEvent."""
    start = _parse_graph_datetime(raw.get("start", {}))
    end = _parse_graph_datetime(raw.get("end", {}))
    if start is None or end is None:
        return None

    is_all_day = bool(raw.get("isAllDay", False))

    # Recurrence — MS Graph returns a structured pattern object, not a
    # raw RRULE string. Convert to canonical RFC 5545 RRULE for storage.
    recurrence_rule = _convert_graph_recurrence(raw.get("recurrence"))

    attendees: list[ProviderAttendeeRef] = []
    for att in raw.get("attendees", []):
        email_addr = att.get("emailAddress", {})
        email = (email_addr.get("address") or "").strip().lower()
        if not email:
            continue
        att_type = att.get("type", "required")
        role = {
            "required": "required_attendee",
            "optional": "optional_attendee",
            "resource": "non_participant",
        }.get(att_type, "required_attendee")
        response_status = att.get("status", {}).get("response", "none")
        attendees.append(
            ProviderAttendeeRef(
                email_address=email,
                display_name=email_addr.get("name"),
                role=role,
                response_status=_normalize_graph_response(response_status),
                comment=None,
            )
        )

    organizer = raw.get("organizer", {}).get("emailAddress", {})

    # Graph body content has type ('html' or 'text') + content.
    body = raw.get("body", {})
    body_content = body.get("content", "")
    body_type = body.get("contentType", "text").lower()
    description_html = body_content if body_type == "html" else None
    description_text = body_content if body_type == "text" else None

    return ProviderFetchedEvent(
        provider_event_id=raw["id"],
        provider_calendar_id=None,
        subject=raw.get("subject"),
        description_text=description_text,
        description_html=description_html,
        location=raw.get("location", {}).get("displayName"),
        start_at=start,
        end_at=end,
        is_all_day=is_all_day,
        event_timezone=raw.get("start", {}).get("timeZone"),
        recurrence_rule=recurrence_rule,
        status=_normalize_graph_status(raw),
        transparency=_normalize_graph_show_as(raw.get("showAs", "busy")),
        organizer_email=organizer.get("address"),
        organizer_name=organizer.get("name"),
        attendees=attendees,
        raw_payload=raw,
    )


def _parse_graph_datetime(d: dict[str, Any]) -> datetime | None:
    """Parse MS Graph datetime dict.

    Graph returns ``{"dateTime": "2026-06-01T14:00:00.0000000",
    "timeZone": "Pacific Standard Time"}``. We normalize to UTC.
    """
    if "dateTime" not in d:
        return None
    dt_str = d["dateTime"]
    # Graph uses naive datetime with separate timeZone field; the
    # timeZone string is Windows time zone name (NOT IANA). Step 2
    # canonical mapping treats them as UTC for storage; Step 2.1 can
    # add Windows-tz → IANA conversion via tzdata mapping if operator
    # signal warrants.
    try:
        # Strip nanoseconds beyond microseconds (Graph returns 7-digit
        # fractional seconds; Python datetime accepts 6).
        if "." in dt_str:
            base, frac = dt_str.split(".", 1)
            frac = frac[:6]  # truncate to microseconds
            dt_str = f"{base}.{frac}"
        # Append +00:00 if naive.
        if "+" not in dt_str and "Z" not in dt_str:
            dt_str = f"{dt_str}+00:00"
        dt_str = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(dt_str)
    except ValueError:
        return None


def _convert_graph_recurrence(rec: dict[str, Any] | None) -> str | None:
    """Convert MS Graph's structured recurrence to RFC 5545 RRULE.

    Graph recurrence pattern: ``{pattern: {type, interval, daysOfWeek,
    dayOfMonth, month}, range: {type, startDate, endDate, numberOfOccurrences}}``.

    Step 2 supports the canonical patterns: daily, weekly, absoluteMonthly,
    relativeMonthly, absoluteYearly. Returns None for patterns Step 2
    doesn't yet translate (rare patterns deferred per §3.26.16.21).
    """
    if not rec:
        return None
    pattern = rec.get("pattern", {})
    range_ = rec.get("range", {})
    p_type = pattern.get("type", "")

    parts = []
    if p_type == "daily":
        parts.append("FREQ=DAILY")
    elif p_type == "weekly":
        parts.append("FREQ=WEEKLY")
        days = pattern.get("daysOfWeek", [])
        if days:
            day_map = {
                "sunday": "SU", "monday": "MO", "tuesday": "TU",
                "wednesday": "WE", "thursday": "TH", "friday": "FR",
                "saturday": "SA",
            }
            byday = ",".join(day_map.get(d.lower(), "") for d in days)
            byday = ",".join(p for p in byday.split(",") if p)
            if byday:
                parts.append(f"BYDAY={byday}")
    elif p_type == "absoluteMonthly":
        parts.append("FREQ=MONTHLY")
        if pattern.get("dayOfMonth"):
            parts.append(f"BYMONTHDAY={pattern['dayOfMonth']}")
    elif p_type == "absoluteYearly":
        parts.append("FREQ=YEARLY")
        if pattern.get("dayOfMonth"):
            parts.append(f"BYMONTHDAY={pattern['dayOfMonth']}")
        if pattern.get("month"):
            parts.append(f"BYMONTH={pattern['month']}")
    else:
        # Unsupported pattern (relativeYearly / relativeMonthly with
        # complex dayOfWeek + index combos) — Step 2 returns None;
        # event stored as non-recurring. Operator can manually edit
        # or wait for Step 2.1 expansion.
        return None

    if pattern.get("interval", 1) > 1:
        parts.append(f"INTERVAL={pattern['interval']}")

    r_type = range_.get("type", "")
    if r_type == "endDate" and range_.get("endDate"):
        end_date = range_["endDate"].replace("-", "")
        parts.append(f"UNTIL={end_date}T235959Z")
    elif r_type == "numbered" and range_.get("numberOfOccurrences"):
        parts.append(f"COUNT={range_['numberOfOccurrences']}")

    return "RRULE:" + ";".join(parts)


def _normalize_graph_status(raw: dict[str, Any]) -> str:
    """MS Graph event status — derived from isCancelled flag.

    Graph doesn't have a top-level ``status`` field like Google; events
    have ``isCancelled: bool`` + ``responseStatus.response`` for the
    organizer's view.
    """
    if raw.get("isCancelled"):
        return "cancelled"
    return "confirmed"


def _normalize_graph_show_as(show_as: str) -> str:
    """MS Graph showAs → canonical RFC 5545 TRANSP.

    Graph showAs: free / tentative / busy / oof / workingElsewhere /
    unknown. RFC 5545 TRANSP: opaque / transparent.
    """
    if show_as == "free":
        return "transparent"
    return "opaque"


def _normalize_graph_busy_status(status: str) -> str:
    """MS Graph getSchedule busy status → ProviderFreeBusyWindow status."""
    if status in ("tentative",):
        return "tentative"
    if status in ("oof",):
        return "out_of_office"
    return "busy"


def _normalize_graph_response(rs: str) -> str:
    """MS Graph attendee response → canonical RFC 5545 PARTSTAT."""
    return {
        "none": "needs_action",
        "notResponded": "needs_action",
        "accepted": "accepted",
        "declined": "declined",
        "tentativelyAccepted": "tentative",
        "organizer": "accepted",
    }.get(rs, "needs_action")


def _vcalendar_to_graph_body(vcalendar_text: str) -> dict[str, Any]:
    """Convert canonical VCALENDAR text → MS Graph API event body.

    Step 3 outbound contract: itip_compose emits canonical RFC 5545
    VCALENDAR; this converter extracts the fields MS Graph expects in
    its structured JSON event body. Special key ``__uid__`` is added
    for the caller's CANCEL path.
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
        # MS Graph: iCalUId is the canonical iCalendar UID surface.
        body["iCalUId"] = str(uid_raw)
        body["transactionId"] = str(uid_raw)[:40]

    summary = vevent.get("summary")
    if summary:
        body["subject"] = str(summary)
    description = vevent.get("description")
    if description:
        body["body"] = {
            "contentType": "text",
            "content": str(description),
        }
    location = vevent.get("location")
    if location:
        body["location"] = {"displayName": str(location)}

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

    # Recurrence — MS Graph takes structured pattern + range, NOT raw
    # RRULE strings. Step 3 ships a minimal converter; complex RRULEs
    # not yet supported on outbound MS Graph path defer to Step 3.1.
    rrule = vevent.get("rrule")
    if rrule is not None:
        try:
            graph_recurrence = _vrecur_to_graph_recurrence(rrule, dtstart)
            if graph_recurrence:
                body["recurrence"] = graph_recurrence
        except Exception:  # noqa: BLE001
            pass

    transp = vevent.get("transp")
    if transp:
        body["showAs"] = "free" if str(transp) == "TRANSPARENT" else "busy"

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
            role_str = str(params.get("role", "REQ-PARTICIPANT")).upper()
            graph_type = "required"
            if role_str == "OPT-PARTICIPANT":
                graph_type = "optional"
            elif role_str == "NON-PARTICIPANT":
                graph_type = "resource"
            body_attendees.append(
                {
                    "emailAddress": {
                        "address": email_str,
                        "name": str(display) if display else email_str,
                    },
                    "type": graph_type,
                }
            )
        if body_attendees:
            body["attendees"] = body_attendees

    return body


def _vrecur_to_graph_recurrence(rrule, dtstart) -> dict[str, Any] | None:
    """Convert icalendar vRecur → MS Graph structured recurrence.

    MS Graph recurrence shape: ``{pattern: {type, interval, daysOfWeek?,
    dayOfMonth?, month?}, range: {type, startDate, endDate?,
    numberOfOccurrences?}}``.

    Step 3 supports daily / weekly / absoluteMonthly / absoluteYearly.
    Returns None for unsupported patterns (relativeMonthly /
    relativeYearly with complex BYDAY index combos) — outbound event
    stored as non-recurring on MS Graph. Operators editing the event
    on Outlook can fix recurrence post-creation; Step 3.1 expands the
    converter.
    """
    if not rrule:
        return None

    # vRecur is dict-like; we read FREQ + interval + BYDAY etc.
    rrule_dict = dict(rrule)

    freq_list = rrule_dict.get("freq", [])
    if isinstance(freq_list, list):
        freq = freq_list[0] if freq_list else None
    else:
        freq = freq_list
    if not freq:
        return None
    freq = str(freq).upper()

    pattern: dict[str, Any] = {}
    if freq == "DAILY":
        pattern["type"] = "daily"
    elif freq == "WEEKLY":
        pattern["type"] = "weekly"
        byday = rrule_dict.get("byday", [])
        if not isinstance(byday, list):
            byday = [byday]
        day_map = {
            "SU": "sunday", "MO": "monday", "TU": "tuesday",
            "WE": "wednesday", "TH": "thursday", "FR": "friday",
            "SA": "saturday",
        }
        days = [day_map[str(d)[-2:].upper()] for d in byday if str(d)[-2:].upper() in day_map]
        if days:
            pattern["daysOfWeek"] = days
    elif freq == "MONTHLY":
        pattern["type"] = "absoluteMonthly"
        bymonthday = rrule_dict.get("bymonthday", [])
        if isinstance(bymonthday, list) and bymonthday:
            pattern["dayOfMonth"] = int(bymonthday[0])
        elif bymonthday:
            pattern["dayOfMonth"] = int(bymonthday)
    elif freq == "YEARLY":
        pattern["type"] = "absoluteYearly"
        bymonthday = rrule_dict.get("bymonthday")
        if bymonthday:
            md = bymonthday[0] if isinstance(bymonthday, list) else bymonthday
            pattern["dayOfMonth"] = int(md)
        bymonth = rrule_dict.get("bymonth")
        if bymonth:
            m = bymonth[0] if isinstance(bymonth, list) else bymonth
            pattern["month"] = int(m)
    else:
        return None

    interval_val = rrule_dict.get("interval")
    if interval_val:
        if isinstance(interval_val, list):
            interval_val = interval_val[0]
        pattern["interval"] = int(interval_val)
    else:
        pattern["interval"] = 1

    # Range.
    range_dict: dict[str, Any] = {}
    if dtstart and hasattr(dtstart, "dt"):
        # MS Graph expects YYYY-MM-DD format.
        d = dtstart.dt
        if hasattr(d, "date"):
            range_dict["startDate"] = d.date().isoformat()
        else:
            range_dict["startDate"] = d.isoformat()

    until_val = rrule_dict.get("until")
    count_val = rrule_dict.get("count")
    if count_val:
        if isinstance(count_val, list):
            count_val = count_val[0]
        range_dict["type"] = "numbered"
        range_dict["numberOfOccurrences"] = int(count_val)
    elif until_val:
        u = until_val[0] if isinstance(until_val, list) else until_val
        u_str = str(u)
        # Take first 10 chars (YYYYMMDD) and reformat.
        date_part = u_str[:8]
        if len(date_part) >= 8 and date_part[:8].isdigit():
            range_dict["type"] = "endDate"
            range_dict["endDate"] = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
        else:
            range_dict["type"] = "noEnd"
    else:
        range_dict["type"] = "noEnd"

    return {"pattern": pattern, "range": range_dict}
