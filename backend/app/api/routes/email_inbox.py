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

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.email import inbox_service
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
