"""Calendar event ingestion pipeline — Phase W-4b Layer 1 Calendar Step 2.

Provider-agnostic transform: ``ProviderFetchedEvent`` → ``CalendarEvent``
+ ``CalendarEventAttendee`` rows + (optionally) ``CalendarEventLinkage``
rows from auto-resolution.

Pipeline stages (each idempotent + tenant-isolated):

  1. **Idempotency check** — if a row with
     ``(account_id, provider_event_id)`` already exists, UPDATE in
     place (provider sync may emit changed events). Idempotency at
     row-level via partial unique index ``ix_calendar_events_provider_id``.

  2. **Recurrence master/instance routing** — Step 2 stores RRULE
     strings verbatim on the canonical event row; instance materialization
     happens at read time per §3.26.16.4 RRULE-as-source-of-truth.
     Modified-instance overrides (RFC 5545 RECURRENCE-ID) ship in Step 3
     alongside outbound iTIP processing — Step 2 ingests master rows
     only (most provider sync_initial calls return masters; instance
     overrides are returned with provider-specific RECURRENCE-ID
     metadata that Step 3 consumes).

  3. **Cross-tenant detection** — when ANY attendee resolves to
     ``external_tenant_id != current_tenant_id``, mark event
     ``is_cross_tenant=True``. Step 4 wires retroactive cross-tenant
     pairing flow.

  4. **Event persistence** — insert/update ``CalendarEvent`` row with
     normalized fields. Provider's raw payload is NOT persisted in Step 2
     (Email shipped a ``message_payload`` JSONB column for inspection;
     Calendar canon doesn't specify equivalent — Step 2 omits per
     scope discipline).

  5. **Attendee persistence** — upsert ``CalendarEventAttendee`` rows
     keyed on ``(event_id, email_address)``. Resolves to internal User /
     CompanyEntity / external Bridgeable tenant when matches found.

  6. **Audit log** — single row per ingested event (action=
     ``event_ingested``).

**Cross-tenant masking inheritance hooks** (per §3.25.x): the
ingested event stores all attendees + content under the ingesting
tenant's scope. Cross-tenant *visibility* (which tenant sees which
fields) is enforced at READ time — Step 2 placeholder; Step 4 wires
the masking discipline. This module ingests un-masked content; the
read path applies masking.

**Linkage auto-resolution** (per §3.26.16.7) — Step 2 ships the
attendee→CompanyEntity resolution path (when an attendee email matches
a known CompanyEntity contact, attendee.resolved_company_entity_id is
populated). Full Intelligence-inferred linkage (subject pattern matching,
location → cemetery match) ships post-Step-5 with Intelligence layer.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.calendar_primitive import (
    CalendarAccount,
    CalendarEvent,
    CalendarEventAttendee,
)
from app.services.calendar.account_service import _audit
from app.services.calendar.providers.base import ProviderFetchedEvent

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────


def ingest_provider_event(
    db: Session,
    *,
    account: CalendarAccount,
    provider_event: ProviderFetchedEvent,
) -> CalendarEvent:
    """Provider-agnostic ingestion of a single fetched event.

    Idempotent: re-ingestion of the same provider_event_id results in
    an UPDATE of the existing canonical row (preserves event.id,
    maintains stable references for linkages + cross-tenant pairing).

    Returns the persisted CalendarEvent row.
    """
    if not provider_event.provider_event_id:
        raise ValueError(
            "ProviderFetchedEvent missing provider_event_id — cannot ingest"
        )

    # Idempotency — check for existing row.
    existing = (
        db.query(CalendarEvent)
        .filter(
            CalendarEvent.account_id == account.id,
            CalendarEvent.provider_event_id == provider_event.provider_event_id,
        )
        .first()
    )

    if existing:
        return _update_existing_event(db, account=account, event=existing, src=provider_event)

    return _insert_new_event(db, account=account, src=provider_event)


# ─────────────────────────────────────────────────────────────────────
# Insert path
# ─────────────────────────────────────────────────────────────────────


def _insert_new_event(
    db: Session,
    *,
    account: CalendarAccount,
    src: ProviderFetchedEvent,
) -> CalendarEvent:
    """Persist a new CalendarEvent + its attendees from a provider fetch.

    Uses the account's default_event_timezone when src.event_timezone
    is None (fallback per §3.26.16.2 event_timezone semantics).
    """
    if src.start_at is None or src.end_at is None:
        raise ValueError(
            f"ProviderFetchedEvent for provider_event_id "
            f"{src.provider_event_id!r} missing start_at or end_at — "
            f"cannot ingest"
        )

    event = CalendarEvent(
        id=str(uuid.uuid4()),
        tenant_id=account.tenant_id,
        account_id=account.id,
        provider_event_id=src.provider_event_id,
        subject=src.subject,
        description_text=src.description_text,
        description_html=src.description_html,
        location=src.location,
        start_at=src.start_at,
        end_at=src.end_at,
        is_all_day=src.is_all_day,
        event_timezone=src.event_timezone or account.default_event_timezone,
        recurrence_rule=src.recurrence_rule,
        status=src.status or "confirmed",
        transparency=src.transparency or "opaque",
    )
    db.add(event)
    db.flush()

    # Attendees — upsert.
    is_cross_tenant = _persist_attendees(db, event=event, src=src)
    if is_cross_tenant:
        event.is_cross_tenant = True
        db.flush()

    _audit(
        db,
        tenant_id=account.tenant_id,
        actor_user_id=None,
        action="event_ingested",
        entity_type="calendar_event",
        entity_id=event.id,
        changes={
            "account_id": account.id,
            "provider_event_id": src.provider_event_id,
            "operation": "insert",
            "is_cross_tenant": is_cross_tenant,
            "is_recurring": src.recurrence_rule is not None,
        },
    )
    db.flush()
    return event


# ─────────────────────────────────────────────────────────────────────
# Update path (idempotent re-ingestion)
# ─────────────────────────────────────────────────────────────────────


def _update_existing_event(
    db: Session,
    *,
    account: CalendarAccount,
    event: CalendarEvent,
    src: ProviderFetchedEvent,
) -> CalendarEvent:
    """Refresh canonical fields from provider sync.

    Preserves event.id + audit history. Updates the mutable fields
    (subject/start_at/end_at/etc) + reconciles attendees (drop attendees
    no longer present; upsert remaining; preserve response_status from
    canonical row when provider doesn't authoritatively change it).
    """
    if src.start_at is None or src.end_at is None:
        # Provider returned partial data; skip update + log.
        logger.warning(
            "Provider fetch for event %s missing start_at/end_at — "
            "skipping update",
            event.id,
        )
        return event

    event.subject = src.subject
    event.description_text = src.description_text
    event.description_html = src.description_html
    event.location = src.location
    event.start_at = src.start_at
    event.end_at = src.end_at
    event.is_all_day = src.is_all_day
    if src.event_timezone:
        event.event_timezone = src.event_timezone
    event.recurrence_rule = src.recurrence_rule
    event.status = src.status or event.status
    event.transparency = src.transparency or event.transparency
    db.flush()

    # Reconcile attendees — provider is source of truth for membership.
    is_cross_tenant = _persist_attendees(db, event=event, src=src, reconcile=True)
    # Cross-tenant flag is sticky-True (once a thread/event has
    # external_tenant participants, retroactive removal preserves the
    # cross-tenant marker per §3.26.15.20 + §3.26.16.6 discipline).
    if is_cross_tenant:
        event.is_cross_tenant = True
        db.flush()

    _audit(
        db,
        tenant_id=account.tenant_id,
        actor_user_id=None,
        action="event_ingested",
        entity_type="calendar_event",
        entity_id=event.id,
        changes={
            "account_id": account.id,
            "provider_event_id": src.provider_event_id,
            "operation": "update",
        },
    )
    db.flush()
    return event


# ─────────────────────────────────────────────────────────────────────
# Attendee persistence + cross-tenant detection
# ─────────────────────────────────────────────────────────────────────


def _persist_attendees(
    db: Session,
    *,
    event: CalendarEvent,
    src: ProviderFetchedEvent,
    reconcile: bool = False,
) -> bool:
    """Upsert attendees for an event from the provider fetch.

    Returns True if any attendee resolved to an external Bridgeable
    tenant (triggers is_cross_tenant flag on event).

    Per §3.26.16.7: when attendee email_address matches a known
    CompanyEntity in the same tenant, attendee.resolved_company_entity_id
    is populated (auto-resolution). External-tenant resolution
    (attendee email matches a User in a different Bridgeable tenant)
    sets external_tenant_id + triggers cross-tenant marker.
    """
    if reconcile:
        # Drop attendees not present in src — provider is source of truth
        # for membership.
        existing_emails = {
            a.email_address for a in event.attendees
        }
        src_emails = {
            (att.email_address or "").strip().lower()
            for att in src.attendees
            if att.email_address
        }
        removed_emails = existing_emails - src_emails
        if removed_emails:
            db.query(CalendarEventAttendee).filter(
                CalendarEventAttendee.event_id == event.id,
                CalendarEventAttendee.email_address.in_(removed_emails),
            ).delete(synchronize_session="fetch")
            db.flush()

    is_cross_tenant = False
    for src_attendee in src.attendees:
        email = (src_attendee.email_address or "").strip().lower()
        if not email or "@" not in email:
            continue

        existing = (
            db.query(CalendarEventAttendee)
            .filter(
                CalendarEventAttendee.event_id == event.id,
                CalendarEventAttendee.email_address == email,
            )
            .first()
        )

        # Resolve external tenant via email domain match against Company.
        # Step 2 simple resolution: if email's domain matches a Company's
        # domain (when tracked) OR the email matches a User in a
        # different tenant. Full §3.25.x cross-tenant masking on read
        # path; this just sets the flag.
        external_tenant_id = _resolve_external_tenant(
            db, email=email, current_tenant_id=event.tenant_id
        )
        resolved_company_entity_id = _resolve_company_entity(
            db, email=email, tenant_id=event.tenant_id
        )

        if external_tenant_id and external_tenant_id != event.tenant_id:
            is_cross_tenant = True

        if existing:
            existing.display_name = src_attendee.display_name
            existing.role = src_attendee.role
            # Provider response state authoritative on update.
            if src_attendee.response_status:
                if (
                    existing.response_status != src_attendee.response_status
                    and src_attendee.response_status != "needs_action"
                ):
                    existing.responded_at = (
                        src_attendee.responded_at
                        or datetime.now(timezone.utc)
                    )
                existing.response_status = src_attendee.response_status
            if src_attendee.comment is not None:
                existing.comment = src_attendee.comment
            if external_tenant_id:
                existing.external_tenant_id = external_tenant_id
            if resolved_company_entity_id:
                existing.resolved_company_entity_id = (
                    resolved_company_entity_id
                )
        else:
            db.add(
                CalendarEventAttendee(
                    id=str(uuid.uuid4()),
                    event_id=event.id,
                    tenant_id=event.tenant_id,
                    email_address=email,
                    display_name=src_attendee.display_name,
                    resolved_company_entity_id=resolved_company_entity_id,
                    external_tenant_id=external_tenant_id,
                    role=src_attendee.role or "required_attendee",
                    response_status=src_attendee.response_status
                    or "needs_action",
                    responded_at=src_attendee.responded_at,
                    comment=src_attendee.comment,
                )
            )

    db.flush()
    return is_cross_tenant


def _resolve_company_entity(
    db: Session, *, email: str, tenant_id: str
) -> str | None:
    """Resolve attendee email to a CompanyEntity in the same tenant.

    Step 2 implementation: query CompanyEntity by email domain match
    OR direct primary_email match. Full Intelligence-inferred linkage
    ships post-Step-5.
    """
    from app.models.company_entity import CompanyEntity

    # Match by email (exact). CompanyEntity.email is the contact-level
    # email (may be NULL for entities without a primary contact). Step 2
    # resolution stops here; richer fuzzy resolution ships post-Step-5
    # alongside Intelligence layer.
    entity = (
        db.query(CompanyEntity)
        .filter(
            CompanyEntity.company_id == tenant_id,
            CompanyEntity.email == email,
        )
        .first()
    )
    if entity:
        return entity.id
    return None


def _resolve_external_tenant(
    db: Session, *, email: str, current_tenant_id: str
) -> str | None:
    """Resolve attendee email to an external Bridgeable tenant.

    Step 2 implementation: query User by email; if a User exists in a
    different tenant than the current event's tenant, return that
    tenant's company_id. Marks the event cross-tenant. Step 4 wires
    full bilateral cross-tenant pairing.
    """
    from app.models.user import User

    user = (
        db.query(User)
        .filter(User.email == email, User.is_active.is_(True))
        .first()
    )
    if user and user.company_id and user.company_id != current_tenant_id:
        return user.company_id
    return None
