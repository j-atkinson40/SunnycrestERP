"""Email inbox API — Phase W-4b Layer 1 Step 4a.

Mounted at ``/api/v1/email/*``. Two surfaces:

  - Read path: GET /threads, GET /threads/{thread_id}
  - Mutation path: POST /messages/{id}/read | /unread,
    POST /threads/{id}/archive | /unarchive | /flag | /unflag

All endpoints tenant-scoped via ``current_user.company_id``. User
access enforcement happens inside the service layer via the
``EmailAccountAccess`` junction. Cross-tenant id enumeration
prevented via existence-hiding 404 returns at the service layer.

Per canon §3.26.15.13 Q1 + §3.26.15.9: read state is per-user-per-
message, archive/flag are per-user-per-thread. Sarah's mutations
never leak into Mike's view.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.email import inbox_service, recipient_service
from app.services.email.inbox_service import (
    InboxError,
    MessageNotFound,
    ThreadNotFound,
)


router = APIRouter()


# ─────────────────────────────────────────────────────────────────────
# Pydantic response shapes
# ─────────────────────────────────────────────────────────────────────


class ThreadSummaryResponse(BaseModel):
    id: str
    account_id: str
    subject: str | None
    sender_summary: str
    snippet: str
    last_message_at: str | None
    message_count: int
    unread_count: int
    is_archived: bool
    is_flagged_thread: bool
    is_cross_tenant: bool
    cross_tenant_partner_tenant_id: str | None
    label_ids: list[str]
    assigned_to_user_id: str | None


class ThreadListResponse(BaseModel):
    threads: list[ThreadSummaryResponse]
    total: int
    page: int
    page_size: int


class MessageDetailResponse(BaseModel):
    id: str
    thread_id: str
    sender_email: str
    sender_name: str | None
    subject: str | None
    body_text: str | None
    body_html: str | None
    body_html_sanitized: str | None = None
    sent_at: str | None
    received_at: str
    direction: str
    is_read: bool
    is_flagged: bool
    in_reply_to_message_id: str | None
    provider_message_id: str | None
    to: list[dict]
    cc: list[dict]
    bcc: list[dict]
    actions: list[dict] = []


class ThreadDetailResponse(BaseModel):
    id: str
    account_id: str
    subject: str | None
    is_archived: bool
    is_cross_tenant: bool
    cross_tenant_partner_tenant_id: str | None
    label_ids: list[str]
    participants_summary: list[str]
    messages: list[MessageDetailResponse]


# ─────────────────────────────────────────────────────────────────────
# Error translation
# ─────────────────────────────────────────────────────────────────────


def _translate(exc: InboxError) -> HTTPException:
    return HTTPException(status_code=exc.http_status, detail=exc.message)


# ─────────────────────────────────────────────────────────────────────
# Read path
# ─────────────────────────────────────────────────────────────────────


@router.get("/threads", response_model=ThreadListResponse)
def list_threads(
    account_id: str | None = None,
    status_filter: Literal[
        "all", "unread", "read", "archived", "flagged", "snoozed"
    ] = "all",
    label_id: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ThreadListResponse:
    threads, total = inbox_service.list_threads(
        db,
        tenant_id=current_user.company_id,
        user_id=current_user.id,
        account_id=account_id,
        status_filter=status_filter,
        label_id=label_id,
        page=page,
        page_size=page_size,
    )
    return ThreadListResponse(
        threads=[
            ThreadSummaryResponse(
                id=t.id,
                account_id=t.account_id,
                subject=t.subject,
                sender_summary=t.sender_summary,
                snippet=t.snippet,
                last_message_at=t.last_message_at,
                message_count=t.message_count,
                unread_count=t.unread_count,
                is_archived=t.is_archived,
                is_flagged_thread=t.is_flagged_thread,
                is_cross_tenant=t.is_cross_tenant,
                cross_tenant_partner_tenant_id=t.cross_tenant_partner_tenant_id,
                label_ids=t.label_ids,
                assigned_to_user_id=t.assigned_to_user_id,
            )
            for t in threads
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/threads/{thread_id}", response_model=ThreadDetailResponse)
def get_thread_detail(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ThreadDetailResponse:
    try:
        detail = inbox_service.get_thread_detail(
            db,
            thread_id=thread_id,
            tenant_id=current_user.company_id,
            user_id=current_user.id,
        )
    except ThreadNotFound as exc:
        raise _translate(exc) from exc
    return ThreadDetailResponse(
        id=detail.id,
        account_id=detail.account_id,
        subject=detail.subject,
        is_archived=detail.is_archived,
        is_cross_tenant=detail.is_cross_tenant,
        cross_tenant_partner_tenant_id=detail.cross_tenant_partner_tenant_id,
        label_ids=detail.label_ids,
        participants_summary=detail.participants_summary,
        messages=[
            MessageDetailResponse(
                id=m.id,
                thread_id=m.thread_id,
                sender_email=m.sender_email,
                sender_name=m.sender_name,
                subject=m.subject,
                body_text=m.body_text,
                body_html=m.body_html,
                body_html_sanitized=m.body_html_sanitized,
                sent_at=m.sent_at,
                received_at=m.received_at,
                direction=m.direction,
                is_read=m.is_read,
                is_flagged=m.is_flagged,
                in_reply_to_message_id=m.in_reply_to_message_id,
                provider_message_id=m.provider_message_id,
                to=m.to,
                cc=m.cc,
                bcc=m.bcc,
                actions=m.actions,
            )
            for m in detail.messages
        ],
    )


# ─────────────────────────────────────────────────────────────────────
# Mutation path
# ─────────────────────────────────────────────────────────────────────


@router.post("/messages/{message_id}/read", status_code=200)
def mark_read(
    message_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    try:
        ok = inbox_service.mark_message_read(
            db,
            message_id=message_id,
            tenant_id=current_user.company_id,
            user_id=current_user.id,
        )
    except MessageNotFound as exc:
        raise _translate(exc) from exc
    db.commit()
    return {"read": ok}


@router.post("/messages/{message_id}/unread", status_code=200)
def mark_unread(
    message_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    try:
        ok = inbox_service.mark_message_unread(
            db,
            message_id=message_id,
            tenant_id=current_user.company_id,
            user_id=current_user.id,
        )
    except MessageNotFound as exc:
        raise _translate(exc) from exc
    db.commit()
    return {"unread": True, "deleted_row": ok}


@router.post("/threads/{thread_id}/archive", status_code=200)
def archive(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    try:
        ok = inbox_service.archive_thread(
            db,
            thread_id=thread_id,
            tenant_id=current_user.company_id,
            user_id=current_user.id,
        )
    except ThreadNotFound as exc:
        raise _translate(exc) from exc
    db.commit()
    return {"archived": ok}


@router.post("/threads/{thread_id}/unarchive", status_code=200)
def unarchive(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    try:
        ok = inbox_service.unarchive_thread(
            db,
            thread_id=thread_id,
            tenant_id=current_user.company_id,
            user_id=current_user.id,
        )
    except ThreadNotFound as exc:
        raise _translate(exc) from exc
    db.commit()
    return {"unarchived": ok}


@router.post("/threads/{thread_id}/flag", status_code=200)
def flag(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    try:
        ok = inbox_service.flag_thread(
            db,
            thread_id=thread_id,
            tenant_id=current_user.company_id,
            user_id=current_user.id,
        )
    except ThreadNotFound as exc:
        raise _translate(exc) from exc
    db.commit()
    return {"flagged": ok}


@router.post("/threads/{thread_id}/unflag", status_code=200)
def unflag(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    try:
        ok = inbox_service.unflag_thread(
            db,
            thread_id=thread_id,
            tenant_id=current_user.company_id,
            user_id=current_user.id,
        )
    except ThreadNotFound as exc:
        raise _translate(exc) from exc
    db.commit()
    return {"unflagged": ok}


# ─────────────────────────────────────────────────────────────────────
# Step 4b — Snooze
# ─────────────────────────────────────────────────────────────────────


class SnoozeRequest(BaseModel):
    snoozed_until: datetime


@router.post("/threads/{thread_id}/snooze", status_code=200)
def snooze(
    thread_id: str,
    request: SnoozeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    try:
        ok = inbox_service.snooze_thread(
            db,
            thread_id=thread_id,
            tenant_id=current_user.company_id,
            user_id=current_user.id,
            snoozed_until=request.snoozed_until,
        )
    except InboxError as exc:
        raise _translate(exc) from exc
    db.commit()
    return {"snoozed": ok}


@router.delete("/threads/{thread_id}/snooze", status_code=200)
def unsnooze(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    try:
        ok = inbox_service.unsnooze_thread(
            db,
            thread_id=thread_id,
            tenant_id=current_user.company_id,
            user_id=current_user.id,
        )
    except InboxError as exc:
        raise _translate(exc) from exc
    db.commit()
    return {"unsnoozed": ok}


# ─────────────────────────────────────────────────────────────────────
# Step 4b — Labels
# ─────────────────────────────────────────────────────────────────────


class LabelResponse(BaseModel):
    id: str
    name: str
    color: str | None
    icon: str | None
    is_system: bool


class CreateLabelRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str | None = Field(default=None, max_length=16)
    icon: str | None = Field(default=None, max_length=64)


class AddLabelRequest(BaseModel):
    label_id: str = Field(min_length=1)


@router.get("/labels", response_model=list[LabelResponse])
def list_labels_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LabelResponse]:
    labels = inbox_service.list_labels(
        db, tenant_id=current_user.company_id
    )
    return [
        LabelResponse(
            id=l.id,
            name=l.name,
            color=l.color,
            icon=l.icon,
            is_system=l.is_system,
        )
        for l in labels
    ]


@router.post("/labels", response_model=LabelResponse, status_code=201)
def create_label_endpoint(
    request: CreateLabelRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LabelResponse:
    try:
        label = inbox_service.create_label(
            db,
            tenant_id=current_user.company_id,
            user_id=current_user.id,
            name=request.name,
            color=request.color,
            icon=request.icon,
        )
    except InboxError as exc:
        raise _translate(exc) from exc
    db.commit()
    return LabelResponse(
        id=label.id,
        name=label.name,
        color=label.color,
        icon=label.icon,
        is_system=label.is_system,
    )


@router.post("/threads/{thread_id}/labels", status_code=200)
def add_label_to_thread(
    thread_id: str,
    request: AddLabelRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    try:
        ok = inbox_service.add_label_to_thread(
            db,
            thread_id=thread_id,
            label_id=request.label_id,
            tenant_id=current_user.company_id,
            user_id=current_user.id,
        )
    except InboxError as exc:
        raise _translate(exc) from exc
    db.commit()
    return {"added": ok}


@router.delete("/threads/{thread_id}/labels/{label_id}", status_code=200)
def remove_label_from_thread(
    thread_id: str,
    label_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    try:
        ok = inbox_service.remove_label_from_thread(
            db,
            thread_id=thread_id,
            label_id=label_id,
            tenant_id=current_user.company_id,
            user_id=current_user.id,
        )
    except InboxError as exc:
        raise _translate(exc) from exc
    db.commit()
    return {"removed": ok}


# ─────────────────────────────────────────────────────────────────────
# Step 4b — Search
# ─────────────────────────────────────────────────────────────────────


@router.get("/search/threads", response_model=list[ThreadSummaryResponse])
def search_threads_endpoint(
    q: str = Query(min_length=2, max_length=200),
    account_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ThreadSummaryResponse]:
    threads = inbox_service.search_threads(
        db,
        tenant_id=current_user.company_id,
        user_id=current_user.id,
        query=q,
        account_id=account_id,
        limit=limit,
    )
    return [
        ThreadSummaryResponse(
            id=t.id,
            account_id=t.account_id,
            subject=t.subject,
            sender_summary=t.sender_summary,
            snippet=t.snippet,
            last_message_at=t.last_message_at,
            message_count=t.message_count,
            unread_count=t.unread_count,
            is_archived=t.is_archived,
            is_flagged_thread=t.is_flagged_thread,
            is_cross_tenant=t.is_cross_tenant,
            cross_tenant_partner_tenant_id=t.cross_tenant_partner_tenant_id,
            label_ids=t.label_ids,
            assigned_to_user_id=t.assigned_to_user_id,
        )
        for t in threads
    ]


# ─────────────────────────────────────────────────────────────────────
# Step 4b — Recipient resolution + role-based routing
# ─────────────────────────────────────────────────────────────────────


class RecipientResponse(BaseModel):
    email_address: str
    display_name: str | None
    source_type: str
    resolution_id: str | None
    rank_score: float


class RoleRecipientResponse(BaseModel):
    label: str
    role_kind: str
    id_value: str
    member_count: int


@router.get("/recipients/resolve", response_model=list[RecipientResponse])
def resolve_recipients_endpoint(
    q: str = Query(min_length=2, max_length=200),
    account_id: str | None = None,
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RecipientResponse]:
    results = recipient_service.resolve_recipients(
        db,
        tenant_id=current_user.company_id,
        user_id=current_user.id,
        query=q,
        account_id=account_id,
        limit=limit,
    )
    return [
        RecipientResponse(
            email_address=r.email_address,
            display_name=r.display_name,
            source_type=r.source_type,
            resolution_id=r.resolution_id,
            rank_score=r.rank_score,
        )
        for r in results
    ]


@router.get("/recipients/roles", response_model=list[RoleRecipientResponse])
def list_role_recipients_endpoint(
    account_id: str = Query(min_length=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RoleRecipientResponse]:
    primitives = recipient_service.list_role_recipients(
        db,
        tenant_id=current_user.company_id,
        user_id=current_user.id,
        account_id=account_id,
    )
    return [
        RoleRecipientResponse(
            label=p.label,
            role_kind=p.role_kind,
            id_value=p.id_value,
            member_count=p.member_count,
        )
        for p in primitives
    ]


class ExpandRoleRequest(BaseModel):
    role_kind: Literal["account_access", "role_slug"]
    id_value: str = Field(min_length=1)


@router.post("/recipients/expand-role", response_model=list[RecipientResponse])
def expand_role_endpoint(
    request: ExpandRoleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RecipientResponse]:
    results = recipient_service.expand_role_recipient(
        db,
        tenant_id=current_user.company_id,
        user_id=current_user.id,
        role_kind=request.role_kind,
        id_value=request.id_value,
    )
    return [
        RecipientResponse(
            email_address=r.email_address,
            display_name=r.display_name,
            source_type=r.source_type,
            resolution_id=r.resolution_id,
            rank_score=r.rank_score,
        )
        for r in results
    ]
