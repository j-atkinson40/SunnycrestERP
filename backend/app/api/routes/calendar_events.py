"""Calendar Events API — Phase W-4b Layer 1 Calendar Step 1.

Basic tenant CRUD for ``CalendarEvent`` + attendee management.
Subsequent Steps 2-N add the sync engine + outbound + free/busy
endpoints on top of this foundation.

All endpoints require an authenticated tenant user. Per-account access
control is enforced via ``account_service.user_has_access`` — read
operations require ``read``; create/update/delete require ``read_write``;
nothing in Step 1 requires ``admin`` (admin is account-management
scope, owned by ``calendar_accounts`` router).

Per ``CLAUDE.md`` §12 conventions:
  - All queries filter by ``tenant_id`` via ``current_user.company_id``
  - Service-layer errors (``CalendarEventError`` / ``CalendarAccountError``
    subclasses) translate to HTTP via the ``http_status`` attribute
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.calendar_primitive import (
    ATTENDEE_ROLES,
    EVENT_STATUSES,
    LINKAGE_SOURCES,
    RESPONSE_STATUSES,
    TRANSPARENCY_VALUES,
    CalendarEvent,
    CalendarEventAttendee,
    CalendarEventLinkage,
)
from app.models.user import User
from app.services.calendar import (
    account_service,
    attendee_service,
    event_service,
    outbound_service,
    state_change_drafting,
)
from app.services.calendar.account_service import (
    CalendarAccountError,
    CalendarAccountPermissionDenied,
)
from app.services.calendar.event_service import CalendarEventError


router = APIRouter()


# ─────────────────────────────────────────────────────────────────────
# Pydantic response shapes
# ─────────────────────────────────────────────────────────────────────


class CalendarEventResponse(BaseModel):
    id: str
    tenant_id: str
    account_id: str
    provider_event_id: str | None
    subject: str | None
    description_text: str | None
    description_html: str | None
    location: str | None
    start_at: str
    end_at: str
    is_all_day: bool
    event_timezone: str | None
    recurrence_rule: str | None
    recurrence_master_event_id: str | None
    status: Literal["tentative", "confirmed", "cancelled"]
    transparency: Literal["opaque", "transparent"]
    is_cross_tenant: bool
    is_active: bool
    # Step 3 — state-change drafted-event provenance per §3.26.16.18.
    # NULL for events authored directly by an operator (no state-change
    # generation). Set by ``state_change_drafting.draft_event_from_state_change``.
    generation_source: str | None = None
    generation_entity_type: str | None = None
    generation_entity_id: str | None = None
    created_by_user_id: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_model(cls, event: CalendarEvent) -> CalendarEventResponse:
        return cls(
            id=event.id,
            tenant_id=event.tenant_id,
            account_id=event.account_id,
            provider_event_id=event.provider_event_id,
            subject=event.subject,
            description_text=event.description_text,
            description_html=event.description_html,
            location=event.location,
            start_at=event.start_at.isoformat(),
            end_at=event.end_at.isoformat(),
            is_all_day=event.is_all_day,
            event_timezone=event.event_timezone,
            recurrence_rule=event.recurrence_rule,
            recurrence_master_event_id=event.recurrence_master_event_id,
            status=event.status,  # type: ignore[arg-type]
            transparency=event.transparency,  # type: ignore[arg-type]
            is_cross_tenant=event.is_cross_tenant,
            is_active=event.is_active,
            generation_source=event.generation_source,
            generation_entity_type=event.generation_entity_type,
            generation_entity_id=event.generation_entity_id,
            created_by_user_id=event.created_by_user_id,
            created_at=event.created_at.isoformat(),
            updated_at=event.updated_at.isoformat(),
        )


class CalendarEventAttendeeResponse(BaseModel):
    id: str
    event_id: str
    email_address: str
    display_name: str | None
    role: str
    response_status: str
    responded_at: str | None
    comment: str | None
    is_internal: bool
    first_seen_at: str

    @classmethod
    def from_model(
        cls, attendee: CalendarEventAttendee
    ) -> CalendarEventAttendeeResponse:
        return cls(
            id=attendee.id,
            event_id=attendee.event_id,
            email_address=attendee.email_address,
            display_name=attendee.display_name,
            role=attendee.role,
            response_status=attendee.response_status,
            responded_at=(
                attendee.responded_at.isoformat()
                if attendee.responded_at
                else None
            ),
            comment=attendee.comment,
            is_internal=attendee.is_internal,
            first_seen_at=attendee.first_seen_at.isoformat(),
        )


class CalendarEventLinkageResponse(BaseModel):
    id: str
    event_id: str
    linked_entity_type: str
    linked_entity_id: str
    linkage_source: str
    confidence: float | None
    linked_at: str
    dismissed_at: str | None

    @classmethod
    def from_model(
        cls, linkage: CalendarEventLinkage
    ) -> CalendarEventLinkageResponse:
        return cls(
            id=linkage.id,
            event_id=linkage.event_id,
            linked_entity_type=linkage.linked_entity_type,
            linked_entity_id=linkage.linked_entity_id,
            linkage_source=linkage.linkage_source,
            confidence=linkage.confidence,
            linked_at=linkage.linked_at.isoformat(),
            dismissed_at=(
                linkage.dismissed_at.isoformat()
                if linkage.dismissed_at
                else None
            ),
        )


# ─────────────────────────────────────────────────────────────────────
# Request shapes
# ─────────────────────────────────────────────────────────────────────


class CreateEventRequest(BaseModel):
    account_id: str = Field(min_length=1)
    subject: str | None = Field(default=None, max_length=998)
    description_text: str | None = None
    description_html: str | None = None
    location: str | None = Field(default=None, max_length=500)
    start_at: datetime
    end_at: datetime
    is_all_day: bool = False
    event_timezone: str | None = Field(default=None, max_length=64)
    recurrence_rule: str | None = Field(default=None, max_length=1024)
    status: Literal["tentative", "confirmed", "cancelled"] = "confirmed"
    transparency: Literal["opaque", "transparent"] = "opaque"


class UpdateEventRequest(BaseModel):
    subject: str | None = Field(default=None, max_length=998)
    description_text: str | None = None
    description_html: str | None = None
    location: str | None = Field(default=None, max_length=500)
    start_at: datetime | None = None
    end_at: datetime | None = None
    is_all_day: bool | None = None
    event_timezone: str | None = Field(default=None, max_length=64)
    recurrence_rule: str | None = Field(default=None, max_length=1024)
    status: Literal["tentative", "confirmed", "cancelled"] | None = None
    transparency: Literal["opaque", "transparent"] | None = None


class AddAttendeeRequest(BaseModel):
    email_address: str = Field(min_length=3, max_length=320)
    display_name: str | None = Field(default=None, max_length=200)
    role: Literal[
        "organizer",
        "required_attendee",
        "optional_attendee",
        "chair",
        "non_participant",
    ] = "required_attendee"
    response_status: Literal[
        "needs_action", "accepted", "declined", "tentative", "delegated"
    ] = "needs_action"
    is_internal: bool = False


class UpdateAttendeeResponseRequest(BaseModel):
    response_status: Literal[
        "needs_action", "accepted", "declined", "tentative", "delegated"
    ]
    comment: str | None = None


class AddLinkageRequest(BaseModel):
    linked_entity_type: str = Field(min_length=1, max_length=64)
    linked_entity_id: str = Field(min_length=1, max_length=36)
    linkage_source: Literal[
        "manual_pre_link", "manual_post_link", "intelligence_inferred"
    ] = "manual_post_link"
    confidence: float | None = None


# ─────────────────────────────────────────────────────────────────────
# Error translation
# ─────────────────────────────────────────────────────────────────────


def _translate(exc: CalendarAccountError) -> HTTPException:
    return HTTPException(status_code=exc.http_status, detail=exc.message)


def _require_access(
    db: Session,
    *,
    account_id: str,
    user_id: str,
    minimum_level: str = "read",
) -> None:
    """Raise HTTPException(403) if the user lacks the minimum access
    level on the account.

    Note: the account itself must already be tenant-scope-validated by
    the caller (via ``event_service.get_event`` which calls
    ``account_service.get_account``). This check layers per-user access
    control on top of tenant isolation.
    """
    if not account_service.user_has_access(
        db,
        account_id=account_id,
        user_id=user_id,
        minimum_level=minimum_level,
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                f"User does not have {minimum_level!r} access on calendar "
                f"account {account_id!r}."
            ),
        )


# ─────────────────────────────────────────────────────────────────────
# Event CRUD
# ─────────────────────────────────────────────────────────────────────


@router.get("", response_model=list[CalendarEventResponse])
def list_events(
    account_id: str = Query(min_length=1),
    range_start: datetime | None = Query(default=None),
    range_end: datetime | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    limit: int = Query(default=500, ge=1, le=5000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CalendarEventResponse]:
    """List events for a calendar account in an optional time range.

    Requires ``read`` access on the account.

    Per Step 1 boundary: this does NOT expand recurring events.
    Recurring rows return their master event row only; instance
    materialization ships in Step 2 alongside the canonical recurrence
    engine.
    """
    try:
        # Validate account is in this tenant.
        account_service.get_account(
            db, account_id=account_id, tenant_id=current_user.company_id
        )
        _require_access(
            db,
            account_id=account_id,
            user_id=current_user.id,
            minimum_level="read",
        )
        events = event_service.list_events_for_account(
            db,
            account_id=account_id,
            tenant_id=current_user.company_id,
            range_start=range_start,
            range_end=range_end,
            include_inactive=include_inactive,
            limit=limit,
        )
        return [CalendarEventResponse.from_model(e) for e in events]
    except CalendarAccountError as exc:
        raise _translate(exc) from exc


@router.post("", response_model=CalendarEventResponse, status_code=201)
def create_event_endpoint(
    request: CreateEventRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CalendarEventResponse:
    """Create a new calendar event.

    Requires ``read_write`` access on the account.
    """
    try:
        # Validate account in this tenant.
        account_service.get_account(
            db,
            account_id=request.account_id,
            tenant_id=current_user.company_id,
        )
        _require_access(
            db,
            account_id=request.account_id,
            user_id=current_user.id,
            minimum_level="read_write",
        )
        event = event_service.create_event(
            db,
            tenant_id=current_user.company_id,
            account_id=request.account_id,
            actor_user_id=current_user.id,
            subject=request.subject,
            start_at=request.start_at,
            end_at=request.end_at,
            description_text=request.description_text,
            description_html=request.description_html,
            location=request.location,
            is_all_day=request.is_all_day,
            event_timezone=request.event_timezone,
            recurrence_rule=request.recurrence_rule,
            status=request.status,
            transparency=request.transparency,
        )
        db.commit()
        db.refresh(event)
        return CalendarEventResponse.from_model(event)
    except CalendarAccountError as exc:
        db.rollback()
        raise _translate(exc) from exc


@router.get("/{event_id}", response_model=CalendarEventResponse)
def get_event_endpoint(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CalendarEventResponse:
    try:
        event = event_service.get_event(
            db, event_id=event_id, tenant_id=current_user.company_id
        )
        _require_access(
            db,
            account_id=event.account_id,
            user_id=current_user.id,
            minimum_level="read",
        )
        return CalendarEventResponse.from_model(event)
    except CalendarAccountError as exc:
        raise _translate(exc) from exc


@router.patch("/{event_id}", response_model=CalendarEventResponse)
def update_event_endpoint(
    event_id: str,
    request: UpdateEventRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CalendarEventResponse:
    try:
        existing = event_service.get_event(
            db, event_id=event_id, tenant_id=current_user.company_id
        )
        _require_access(
            db,
            account_id=existing.account_id,
            user_id=current_user.id,
            minimum_level="read_write",
        )
        event = event_service.update_event(
            db,
            event_id=event_id,
            tenant_id=current_user.company_id,
            actor_user_id=current_user.id,
            subject=request.subject,
            description_text=request.description_text,
            description_html=request.description_html,
            location=request.location,
            start_at=request.start_at,
            end_at=request.end_at,
            is_all_day=request.is_all_day,
            event_timezone=request.event_timezone,
            recurrence_rule=request.recurrence_rule,
            status=request.status,
            transparency=request.transparency,
        )
        db.commit()
        db.refresh(event)
        return CalendarEventResponse.from_model(event)
    except CalendarAccountError as exc:
        db.rollback()
        raise _translate(exc) from exc


@router.delete("/{event_id}", status_code=200)
def delete_event_endpoint(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    try:
        existing = event_service.get_event(
            db, event_id=event_id, tenant_id=current_user.company_id
        )
        _require_access(
            db,
            account_id=existing.account_id,
            user_id=current_user.id,
            minimum_level="read_write",
        )
        event_service.delete_event(
            db,
            event_id=event_id,
            tenant_id=current_user.company_id,
            actor_user_id=current_user.id,
        )
        db.commit()
        return {"deleted": True}
    except CalendarAccountError as exc:
        db.rollback()
        raise _translate(exc) from exc


# ─────────────────────────────────────────────────────────────────────
# Attendee management
# ─────────────────────────────────────────────────────────────────────


@router.get(
    "/{event_id}/attendees",
    response_model=list[CalendarEventAttendeeResponse],
)
def list_event_attendees(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CalendarEventAttendeeResponse]:
    try:
        event = event_service.get_event(
            db, event_id=event_id, tenant_id=current_user.company_id
        )
        _require_access(
            db,
            account_id=event.account_id,
            user_id=current_user.id,
            minimum_level="read",
        )
        attendees = attendee_service.list_attendees_for_event(
            db,
            event_id=event_id,
            tenant_id=current_user.company_id,
        )
        return [CalendarEventAttendeeResponse.from_model(a) for a in attendees]
    except CalendarAccountError as exc:
        raise _translate(exc) from exc


@router.post(
    "/{event_id}/attendees",
    response_model=CalendarEventAttendeeResponse,
    status_code=201,
)
def add_event_attendee(
    event_id: str,
    request: AddAttendeeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CalendarEventAttendeeResponse:
    try:
        event = event_service.get_event(
            db, event_id=event_id, tenant_id=current_user.company_id
        )
        _require_access(
            db,
            account_id=event.account_id,
            user_id=current_user.id,
            minimum_level="read_write",
        )
        attendee = attendee_service.add_attendee(
            db,
            event_id=event_id,
            tenant_id=current_user.company_id,
            actor_user_id=current_user.id,
            email_address=request.email_address,
            display_name=request.display_name,
            role=request.role,
            response_status=request.response_status,
            is_internal=request.is_internal,
        )
        db.commit()
        db.refresh(attendee)
        return CalendarEventAttendeeResponse.from_model(attendee)
    except CalendarAccountError as exc:
        db.rollback()
        raise _translate(exc) from exc


@router.patch(
    "/{event_id}/attendees/{attendee_id}/response",
    response_model=CalendarEventAttendeeResponse,
)
def update_attendee_response(
    event_id: str,
    attendee_id: str,
    request: UpdateAttendeeResponseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CalendarEventAttendeeResponse:
    try:
        event = event_service.get_event(
            db, event_id=event_id, tenant_id=current_user.company_id
        )
        _require_access(
            db,
            account_id=event.account_id,
            user_id=current_user.id,
            minimum_level="read",
        )
        attendee = attendee_service.update_response_status(
            db,
            attendee_id=attendee_id,
            tenant_id=current_user.company_id,
            actor_user_id=current_user.id,
            response_status=request.response_status,
            comment=request.comment,
        )
        # Ensure attendee belongs to the requested event (defense in depth
        # — attendee_service already tenant-scopes via attendee_id, but
        # routing event_id should match).
        if attendee.event_id != event.id:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Attendee {attendee_id!r} does not belong to event "
                    f"{event_id!r}."
                ),
            )
        db.commit()
        db.refresh(attendee)
        return CalendarEventAttendeeResponse.from_model(attendee)
    except CalendarAccountError as exc:
        db.rollback()
        raise _translate(exc) from exc


@router.delete(
    "/{event_id}/attendees/{attendee_id}",
    status_code=200,
)
def remove_event_attendee(
    event_id: str,
    attendee_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    try:
        event = event_service.get_event(
            db, event_id=event_id, tenant_id=current_user.company_id
        )
        _require_access(
            db,
            account_id=event.account_id,
            user_id=current_user.id,
            minimum_level="read_write",
        )
        attendee_service.remove_attendee(
            db,
            attendee_id=attendee_id,
            tenant_id=current_user.company_id,
            actor_user_id=current_user.id,
        )
        db.commit()
        return {"removed": True}
    except CalendarAccountError as exc:
        db.rollback()
        raise _translate(exc) from exc


# ─────────────────────────────────────────────────────────────────────
# Linkage management
# ─────────────────────────────────────────────────────────────────────


@router.get(
    "/{event_id}/linkages",
    response_model=list[CalendarEventLinkageResponse],
)
def list_event_linkages(
    event_id: str,
    include_dismissed: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CalendarEventLinkageResponse]:
    """List polymorphic linkages for a calendar event.

    Phase W-4b Layer 1 Calendar Step 5 — powers the linked-entities
    section of the native event detail page (§14.10.3). Tenant-scoped
    via event lookup. Defaults to active linkages only; pass
    ``include_dismissed=true`` for the full audit history.
    """
    try:
        event = event_service.get_event(
            db, event_id=event_id, tenant_id=current_user.company_id
        )
        _require_access(
            db,
            account_id=event.account_id,
            user_id=current_user.id,
            minimum_level="read",
        )
        linkages = event_service.list_linkages_for_event(
            db,
            event_id=event_id,
            tenant_id=current_user.company_id,
            include_dismissed=include_dismissed,
        )
        return [CalendarEventLinkageResponse.from_model(l) for l in linkages]
    except CalendarAccountError as exc:
        raise _translate(exc) from exc


@router.post(
    "/{event_id}/linkages",
    response_model=CalendarEventLinkageResponse,
    status_code=201,
)
def add_event_linkage(
    event_id: str,
    request: AddLinkageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CalendarEventLinkageResponse:
    try:
        event = event_service.get_event(
            db, event_id=event_id, tenant_id=current_user.company_id
        )
        _require_access(
            db,
            account_id=event.account_id,
            user_id=current_user.id,
            minimum_level="read_write",
        )
        linkage = event_service.add_linkage(
            db,
            event_id=event_id,
            tenant_id=current_user.company_id,
            linked_entity_type=request.linked_entity_type,
            linked_entity_id=request.linked_entity_id,
            linkage_source=request.linkage_source,
            actor_user_id=current_user.id,
            confidence=request.confidence,
        )
        db.commit()
        db.refresh(linkage)
        return CalendarEventLinkageResponse.from_model(linkage)
    except CalendarAccountError as exc:
        db.rollback()
        raise _translate(exc) from exc


@router.delete(
    "/{event_id}/linkages/{linkage_id}",
    status_code=200,
)
def dismiss_event_linkage(
    event_id: str,
    linkage_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    try:
        event = event_service.get_event(
            db, event_id=event_id, tenant_id=current_user.company_id
        )
        _require_access(
            db,
            account_id=event.account_id,
            user_id=current_user.id,
            minimum_level="read_write",
        )
        dismissed = event_service.dismiss_linkage(
            db,
            linkage_id=linkage_id,
            tenant_id=current_user.company_id,
            actor_user_id=current_user.id,
        )
        db.commit()
        return {"dismissed": dismissed}
    except CalendarAccountError as exc:
        db.rollback()
        raise _translate(exc) from exc


# ─────────────────────────────────────────────────────────────────────
# Step 3 — Outbound (commit + cancel)
# ─────────────────────────────────────────────────────────────────────


class SendEventResponse(BaseModel):
    status: str
    event_id: str
    provider_event_id: str | None
    recipient_count: int


class CancelEventResponse(BaseModel):
    status: str
    event_id: str
    recipient_count: int = 0


@router.post(
    "/{event_id}/send",
    response_model=SendEventResponse,
    status_code=200,
)
def send_event_endpoint(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SendEventResponse:
    """Commit drafted event + propagate iTIP REQUEST per §3.26.16.5 Path 1.

    Per §3.26.14.14.5 drafted-not-auto-sent discipline: tentative events
    require explicit send commit. On success, ``status`` flips from
    ``"tentative"`` → ``"confirmed"``; iTIP REQUEST propagates to
    attendees via the provider.

    Requires `read_write` access on the event's account.
    """
    try:
        event = event_service.get_event(
            db, event_id=event_id, tenant_id=current_user.company_id
        )
        _require_access(
            db,
            account_id=event.account_id,
            user_id=current_user.id,
            minimum_level="read_write",
        )
        result = outbound_service.send_event(
            db, event=event, sender=current_user
        )
        db.commit()
        return SendEventResponse(
            status=result["status"],
            event_id=result["event_id"],
            provider_event_id=result.get("provider_event_id"),
            recipient_count=result["recipient_count"],
        )
    except CalendarAccountError as exc:
        db.rollback()
        raise _translate(exc) from exc


@router.post(
    "/{event_id}/cancel",
    response_model=CancelEventResponse,
    status_code=200,
)
def cancel_event_endpoint(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CancelEventResponse:
    """Propagate iTIP CANCEL + flip status to cancelled per §3.26.16.5 Path 2.

    Idempotent: cancelling an already-cancelled event returns a no-op
    response. Requires `read_write` access on the event's account.
    """
    try:
        event = event_service.get_event(
            db, event_id=event_id, tenant_id=current_user.company_id
        )
        _require_access(
            db,
            account_id=event.account_id,
            user_id=current_user.id,
            minimum_level="read_write",
        )
        result = outbound_service.cancel_event(
            db, event=event, sender=current_user
        )
        db.commit()
        return CancelEventResponse(
            status=result["status"],
            event_id=result["event_id"],
            recipient_count=result.get("recipient_count", 0),
        )
    except CalendarAccountError as exc:
        db.rollback()
        raise _translate(exc) from exc


# ─────────────────────────────────────────────────────────────────────
# Step 3 — Drafted-event review queue per §3.26.16.18
# ─────────────────────────────────────────────────────────────────────


@router.get("-drafts/state-change", response_model=list[CalendarEventResponse])
def list_state_change_drafts(
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CalendarEventResponse]:
    """List tentative state-change-drafted events for operator review.

    Per §3.26.16.18 + §3.26.14.14.5 drafted-not-auto-sent discipline:
    state-change-generated events with status="tentative" surface here
    for explicit commit-or-discard.

    Auto-confirmed events (internal-only per auto-confirmation rules)
    do NOT appear here — they ship straight to "confirmed" status.

    Tenant-scoped; any authenticated tenant user can list (drafted-event
    queue is operator-shared per Front-style shared calendar precedent
    §3.26.16.19).
    """
    events = state_change_drafting.list_drafted_state_change_events(
        db,
        tenant_id=current_user.company_id,
        limit=limit,
    )
    return [CalendarEventResponse.from_model(e) for e in events]
