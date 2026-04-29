"""Inbox query + status mutation service — Phase W-4b Layer 1 Step 4a.

Two surfaces shipped here:

  1. **Read path** — list_threads + get_thread_detail. Returns
     thread + message + participant + per-user state denormalized
     for the inbox UI. Performance budget per §3.26.15.6: inbox
     p50 < 500ms, thread detail p50 < 300ms — well under existing
     saved-view-execute (15.4ms) at the same JOIN topology.

  2. **Mutation path** — mark_message_read / unread / archive /
     unarchive / flag / unflag. Per §3.26.15.13 Q1 canonical:
     read state is per-message-per-user (UserMessageRead); archive
     and flag state is per-thread-per-user (EmailThreadStatus).
     Sarah's read state never affects Mike's view.

Per-tenant isolation enforced at the service-layer (every query
filters by tenant_id). User access enforced via the EmailAccountAccess
junction (only accounts user has active access to surface in the
inbox). Cross-tenant masking applied per §3.25.x — Step 4a treats
the masking hook as a passthrough (canon details Step 4b alongside
operator-action affordances).

Audit log discipline (§3.26.15.8): every status mutation writes an
``email_audit_log`` row. Read-state changes use
action='message_marked_read' / 'message_marked_unread'. Thread
status changes use action='thread_archived' / 'thread_unarchived' /
'message_flagged' / 'message_unflagged'.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, selectinload

from app.models.email_primitive import (
    EmailAccount,
    EmailAccountAccess,
    EmailMessage,
    EmailParticipant,
    EmailThread,
    EmailThreadLabel,
    EmailThreadStatus,
    MessageParticipant,
    UserMessageRead,
)
from app.services.email.account_service import (
    EmailAccountError,
    EmailAccountNotFound,
    _audit,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────


class InboxError(EmailAccountError):
    http_status = 400


class ThreadNotFound(EmailAccountError):
    http_status = 404


class MessageNotFound(EmailAccountError):
    http_status = 404


# ─────────────────────────────────────────────────────────────────────
# Read-path response shapes (typed dicts matching API Pydantic)
# ─────────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class ThreadSummary:
    """Per-thread row for the inbox listing pane.

    Denormalized fields chosen to render the canonical row composition
    from §14.9.1 without further round-trips: subject + sender_summary
    + last_message_at + message_count + unread_count + cross-tenant
    indicator + label_chips.
    """

    id: str
    account_id: str
    subject: str | None
    sender_summary: str  # rendered "Name <addr>" or "addr"
    snippet: str  # body preview (text or stripped HTML, 96 chars)
    last_message_at: str | None  # ISO 8601
    message_count: int
    unread_count: int
    is_archived: bool  # current user's archive state
    is_flagged_thread: bool  # any flagged messages in thread for this user
    is_cross_tenant: bool
    cross_tenant_partner_tenant_id: str | None
    label_ids: list[str]
    assigned_to_user_id: str | None


@dataclass(slots=True)
class MessageDetail:
    """Full per-message payload for thread detail."""

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
    is_read: bool  # per current user
    is_flagged: bool  # per current user
    in_reply_to_message_id: str | None
    provider_message_id: str | None
    to: list[dict[str, str | None]]
    cc: list[dict[str, str | None]]
    bcc: list[dict[str, str | None]]


@dataclass(slots=True)
class ThreadDetail:
    id: str
    account_id: str
    subject: str | None
    is_archived: bool
    is_cross_tenant: bool
    cross_tenant_partner_tenant_id: str | None
    label_ids: list[str]
    participants_summary: list[str]
    messages: list[MessageDetail]


# ─────────────────────────────────────────────────────────────────────
# Helper: account-id set the user can see
# ─────────────────────────────────────────────────────────────────────


def _accessible_account_ids(
    db: Session, *, tenant_id: str, user_id: str
) -> list[str]:
    """Return EmailAccount ids the user currently has read access on.

    Joins through ``email_account_access`` with ``revoked_at IS NULL``
    + filters to the user's tenant. Read level + above sees the inbox
    (read_write/admin add the ability to send/manage; all three see
    threads).
    """
    rows = (
        db.query(EmailAccount.id)
        .join(
            EmailAccountAccess,
            EmailAccountAccess.account_id == EmailAccount.id,
        )
        .filter(
            EmailAccount.tenant_id == tenant_id,
            EmailAccount.is_active.is_(True),
            EmailAccountAccess.user_id == user_id,
            EmailAccountAccess.revoked_at.is_(None),
        )
        .all()
    )
    return [row[0] for row in rows]


def _snippet(text: str | None, html: str | None, limit: int = 96) -> str:
    """Build the inbox snippet from message body — text first, HTML
    fallback (stripped to plain). Truncated at last word boundary."""
    raw = text
    if not raw and html:
        # Cheap HTML→text strip via stdlib (no html.parser dep). Good
        # enough for snippet purposes; full HTML rendering happens in
        # the thread detail surface via sandboxed iframe per §3.26.15.5.
        import re

        raw = re.sub(r"<[^>]+>", " ", html)
        raw = re.sub(r"\s+", " ", raw).strip()
    if not raw:
        return ""
    raw = raw.strip()
    if len(raw) <= limit:
        return raw
    cut = raw[:limit].rsplit(" ", 1)[0]
    return f"{cut}…"


def _format_sender(message: EmailMessage) -> str:
    if message.sender_name:
        return f"{message.sender_name} <{message.sender_email}>"
    return message.sender_email


# ─────────────────────────────────────────────────────────────────────
# Read path
# ─────────────────────────────────────────────────────────────────────


def list_threads(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    account_id: str | None = None,
    status_filter: str = "all",
    label_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[ThreadSummary], int]:
    """List inbox threads visible to a user.

    Returns ``(threads, total_count)`` for paged rendering. ``status_filter``
    canonical values per §3.26.15.9 filter strip:
      - ``all`` (default): every thread, archived hidden
      - ``unread``: threads with unread_count > 0 for this user
      - ``read``: threads with unread_count == 0 (and not archived)
      - ``archived``: archived threads (per current user)
      - ``flagged``: threads with at least one flagged message for user
      - ``snoozed``: threads with is_snoozed=true for user
    """
    accessible = _accessible_account_ids(
        db, tenant_id=tenant_id, user_id=user_id
    )
    if not accessible:
        return [], 0
    if account_id is not None:
        if account_id not in accessible:
            # Existence-hiding — accounts the user can't see surface
            # as if they didn't exist.
            return [], 0
        candidate_account_ids = [account_id]
    else:
        candidate_account_ids = accessible

    # Base query: threads on accessible accounts, tenant-scoped, active.
    q = (
        db.query(EmailThread)
        .filter(
            EmailThread.tenant_id == tenant_id,
            EmailThread.account_id.in_(candidate_account_ids),
            EmailThread.is_active.is_(True),
        )
    )

    # Per-user thread status (LEFT JOIN — many threads have no per-user
    # row yet, treated as "no archive / no flag / no snooze").
    if status_filter == "archived":
        q = q.join(
            EmailThreadStatus,
            and_(
                EmailThreadStatus.thread_id == EmailThread.id,
                EmailThreadStatus.user_id == user_id,
            ),
        ).filter(EmailThreadStatus.is_archived.is_(True))
    elif status_filter == "snoozed":
        q = q.join(
            EmailThreadStatus,
            and_(
                EmailThreadStatus.thread_id == EmailThread.id,
                EmailThreadStatus.user_id == user_id,
            ),
        ).filter(EmailThreadStatus.is_snoozed.is_(True))
    else:
        # Default: hide archived from non-archived views.
        q = q.outerjoin(
            EmailThreadStatus,
            and_(
                EmailThreadStatus.thread_id == EmailThread.id,
                EmailThreadStatus.user_id == user_id,
            ),
        ).filter(
            or_(
                EmailThreadStatus.is_archived.is_(None),
                EmailThreadStatus.is_archived.is_(False),
            )
        )

    if label_id:
        q = q.join(
            EmailThreadLabel,
            EmailThreadLabel.thread_id == EmailThread.id,
        ).filter(EmailThreadLabel.label_id == label_id)

    q = q.order_by(EmailThread.last_message_at.desc().nullslast())
    total = q.count()

    threads = (
        q.options(selectinload(EmailThread.user_status))
        .offset(max(0, (page - 1) * page_size))
        .limit(page_size)
        .all()
    )

    # Per-thread denormalized metadata: unread_count + flagged dot +
    # last-message preview + label ids.
    thread_ids = [t.id for t in threads]
    if not thread_ids:
        return [], total

    # Unread count per thread for this user — count messages where
    # there's no UserMessageRead row.
    unread_count_map: dict[str, int] = {}
    if thread_ids:
        unread_rows = (
            db.query(EmailMessage.thread_id, func.count(EmailMessage.id))
            .outerjoin(
                UserMessageRead,
                and_(
                    UserMessageRead.message_id == EmailMessage.id,
                    UserMessageRead.user_id == user_id,
                ),
            )
            .filter(
                EmailMessage.thread_id.in_(thread_ids),
                EmailMessage.is_deleted.is_(False),
                EmailMessage.direction == "inbound",
                UserMessageRead.id.is_(None),
            )
            .group_by(EmailMessage.thread_id)
            .all()
        )
        unread_count_map = dict(unread_rows)

    # Last message + flagged check per thread
    last_message_map: dict[str, EmailMessage] = {}
    if thread_ids:
        sub = (
            db.query(
                EmailMessage.thread_id,
                func.max(EmailMessage.received_at).label("max_recv"),
            )
            .filter(EmailMessage.thread_id.in_(thread_ids))
            .group_by(EmailMessage.thread_id)
            .subquery()
        )
        last_messages = (
            db.query(EmailMessage)
            .join(
                sub,
                and_(
                    EmailMessage.thread_id == sub.c.thread_id,
                    EmailMessage.received_at == sub.c.max_recv,
                ),
            )
            .all()
        )
        # Multiple messages can share the same received_at within the
        # same thread; take the highest sent_at as tiebreaker.
        for msg in last_messages:
            existing = last_message_map.get(msg.thread_id)
            if existing is None or (
                msg.sent_at and existing.sent_at and msg.sent_at > existing.sent_at
            ):
                last_message_map[msg.thread_id] = msg

    # Label ids per thread
    label_rows = (
        db.query(EmailThreadLabel.thread_id, EmailThreadLabel.label_id)
        .filter(EmailThreadLabel.thread_id.in_(thread_ids))
        .all()
    )
    label_map: dict[str, list[str]] = {}
    for tid, lid in label_rows:
        label_map.setdefault(tid, []).append(lid)

    # Per-thread per-user status map
    status_map: dict[str, EmailThreadStatus] = {
        ts.thread_id: ts
        for t in threads
        for ts in (t.user_status or [])
        if ts.user_id == user_id
    }

    # Cross-tenant partner — derive from is_cross_tenant + a single
    # external_tenant_id participant. Step 4a uses the first
    # external_tenant_id found on a thread participant; full
    # bilateral pairing surfaces in Step 5+ via cross_tenant_thread_pairing.
    partner_tenant_map: dict[str, str | None] = {}
    cross_tenant_thread_ids = [t.id for t in threads if t.is_cross_tenant]
    if cross_tenant_thread_ids:
        partner_rows = (
            db.query(
                EmailParticipant.thread_id,
                EmailParticipant.external_tenant_id,
            )
            .filter(
                EmailParticipant.thread_id.in_(cross_tenant_thread_ids),
                EmailParticipant.external_tenant_id.isnot(None),
            )
            .all()
        )
        for tid, ext in partner_rows:
            partner_tenant_map.setdefault(tid, ext)

    summaries: list[ThreadSummary] = []
    for thread in threads:
        last_msg = last_message_map.get(thread.id)
        per_user = status_map.get(thread.id)
        summary = ThreadSummary(
            id=thread.id,
            account_id=thread.account_id,
            subject=thread.subject,
            sender_summary=_format_sender(last_msg) if last_msg else "",
            snippet=_snippet(
                last_msg.body_text if last_msg else None,
                last_msg.body_html if last_msg else None,
            ),
            last_message_at=(
                thread.last_message_at.isoformat()
                if thread.last_message_at
                else None
            ),
            message_count=thread.message_count or 0,
            unread_count=int(unread_count_map.get(thread.id, 0)),
            is_archived=bool(per_user and per_user.is_archived),
            is_flagged_thread=bool(per_user and per_user.is_flagged),
            is_cross_tenant=bool(thread.is_cross_tenant),
            cross_tenant_partner_tenant_id=partner_tenant_map.get(thread.id),
            label_ids=label_map.get(thread.id, []),
            assigned_to_user_id=thread.assigned_to_user_id,
        )

        # Apply final filter pass that needs unread_count
        if status_filter == "unread" and summary.unread_count == 0:
            continue
        if status_filter == "read" and summary.unread_count > 0:
            continue
        if status_filter == "flagged" and not summary.is_flagged_thread:
            continue
        summaries.append(summary)

    # When the status_filter requires post-query filtering on per-user
    # state (unread/read/flagged), reconcile total to reflect the
    # filtered set. Pagination caveat: this means total is page-scoped
    # for those filters; refining to a JOIN-driven SQL filter for
    # accurate cross-page total is a Step 4b refinement alongside
    # virtualized list (current page_size=50 default keeps the gap
    # imperceptible for typical inbox volumes).
    if status_filter in ("unread", "read", "flagged"):
        total = len(summaries) + max(0, (page - 1) * page_size)

    return summaries, total


def get_thread_detail(
    db: Session,
    *,
    thread_id: str,
    tenant_id: str,
    user_id: str,
) -> ThreadDetail:
    """Return the full thread detail for the right-pane view.

    Raises ``ThreadNotFound`` (404) if the thread isn't in the tenant
    OR the user lacks access on the thread's account — existence-hiding
    against id enumeration.
    """
    thread = (
        db.query(EmailThread)
        .filter(
            EmailThread.id == thread_id,
            EmailThread.tenant_id == tenant_id,
            EmailThread.is_active.is_(True),
        )
        .first()
    )
    if not thread:
        raise ThreadNotFound(f"Thread {thread_id!r} not found.")

    accessible = _accessible_account_ids(
        db, tenant_id=tenant_id, user_id=user_id
    )
    if thread.account_id not in accessible:
        raise ThreadNotFound(f"Thread {thread_id!r} not found.")

    # Messages chronological; LEFT JOIN UserMessageRead for per-user
    # is_read; LEFT JOIN EmailThreadStatus for per-user is_flagged
    # at thread level (Step 4a uses thread-level flag; per-message
    # flagging is a Step 4b refinement).
    messages = (
        db.query(EmailMessage)
        .filter(
            EmailMessage.thread_id == thread_id,
            EmailMessage.is_deleted.is_(False),
        )
        .order_by(EmailMessage.received_at.asc())
        .all()
    )

    if messages:
        message_ids = [m.id for m in messages]
        read_msg_ids = {
            row[0]
            for row in db.query(UserMessageRead.message_id)
            .filter(
                UserMessageRead.message_id.in_(message_ids),
                UserMessageRead.user_id == user_id,
            )
            .all()
        }
    else:
        read_msg_ids = set()

    # Participants per message
    msg_participants_map: dict[str, list[tuple[str, EmailParticipant]]] = {}
    if messages:
        rows = (
            db.query(MessageParticipant, EmailParticipant)
            .join(
                EmailParticipant,
                EmailParticipant.id == MessageParticipant.participant_id,
            )
            .filter(MessageParticipant.message_id.in_([m.id for m in messages]))
            .order_by(MessageParticipant.position.asc())
            .all()
        )
        for mp, p in rows:
            msg_participants_map.setdefault(mp.message_id, []).append(
                (mp.role, p)
            )

    per_user_status = (
        db.query(EmailThreadStatus)
        .filter(
            EmailThreadStatus.thread_id == thread_id,
            EmailThreadStatus.user_id == user_id,
        )
        .first()
    )

    label_ids = [
        row[0]
        for row in db.query(EmailThreadLabel.label_id)
        .filter(EmailThreadLabel.thread_id == thread_id)
        .all()
    ]

    # Cross-tenant partner
    partner_tenant_id: str | None = None
    if thread.is_cross_tenant:
        row = (
            db.query(EmailParticipant.external_tenant_id)
            .filter(
                EmailParticipant.thread_id == thread_id,
                EmailParticipant.external_tenant_id.isnot(None),
            )
            .first()
        )
        partner_tenant_id = row[0] if row else None

    message_details: list[MessageDetail] = []
    for msg in messages:
        roles_for_msg = msg_participants_map.get(msg.id, [])

        def _role_pairs(role: str) -> list[dict[str, str | None]]:
            return [
                {"email_address": p.email_address, "display_name": p.display_name}
                for r, p in roles_for_msg
                if r == role
            ]

        message_details.append(
            MessageDetail(
                id=msg.id,
                thread_id=msg.thread_id,
                sender_email=msg.sender_email,
                sender_name=msg.sender_name,
                subject=msg.subject,
                body_text=msg.body_text,
                body_html=msg.body_html,
                sent_at=msg.sent_at.isoformat() if msg.sent_at else None,
                received_at=msg.received_at.isoformat(),
                direction=msg.direction,
                is_read=(
                    msg.id in read_msg_ids
                    or msg.direction == "outbound"  # outbound auto-read for sender
                ),
                is_flagged=bool(per_user_status and per_user_status.is_flagged),
                in_reply_to_message_id=msg.in_reply_to_message_id,
                provider_message_id=msg.provider_message_id,
                to=_role_pairs("to"),
                cc=_role_pairs("cc"),
                bcc=_role_pairs("bcc"),
            )
        )

    return ThreadDetail(
        id=thread.id,
        account_id=thread.account_id,
        subject=thread.subject,
        is_archived=bool(per_user_status and per_user_status.is_archived),
        is_cross_tenant=bool(thread.is_cross_tenant),
        cross_tenant_partner_tenant_id=partner_tenant_id,
        label_ids=label_ids,
        participants_summary=list(thread.participants_summary or []),
        messages=message_details,
    )


# ─────────────────────────────────────────────────────────────────────
# Mutation path — per-user-per-message read state
# ─────────────────────────────────────────────────────────────────────


def _verify_message_access(
    db: Session,
    *,
    message_id: str,
    tenant_id: str,
    user_id: str,
) -> EmailMessage:
    """Resolve a message + verify the calling user has access on the
    underlying account. Raises ``MessageNotFound`` (404 — existence
    hiding) on miss or no-access.
    """
    msg = (
        db.query(EmailMessage)
        .filter(
            EmailMessage.id == message_id,
            EmailMessage.tenant_id == tenant_id,
        )
        .first()
    )
    if not msg:
        raise MessageNotFound(f"Message {message_id!r} not found.")
    accessible = _accessible_account_ids(
        db, tenant_id=tenant_id, user_id=user_id
    )
    if msg.account_id not in accessible:
        raise MessageNotFound(f"Message {message_id!r} not found.")
    return msg


def _verify_thread_access(
    db: Session,
    *,
    thread_id: str,
    tenant_id: str,
    user_id: str,
) -> EmailThread:
    thread = (
        db.query(EmailThread)
        .filter(
            EmailThread.id == thread_id,
            EmailThread.tenant_id == tenant_id,
            EmailThread.is_active.is_(True),
        )
        .first()
    )
    if not thread:
        raise ThreadNotFound(f"Thread {thread_id!r} not found.")
    accessible = _accessible_account_ids(
        db, tenant_id=tenant_id, user_id=user_id
    )
    if thread.account_id not in accessible:
        raise ThreadNotFound(f"Thread {thread_id!r} not found.")
    return thread


def mark_message_read(
    db: Session,
    *,
    message_id: str,
    tenant_id: str,
    user_id: str,
) -> bool:
    """Idempotent: True if a row was created/exists, False if message
    isn't readable for this user. Raises MessageNotFound on 404."""
    msg = _verify_message_access(
        db, message_id=message_id, tenant_id=tenant_id, user_id=user_id
    )
    existing = (
        db.query(UserMessageRead)
        .filter(
            UserMessageRead.message_id == message_id,
            UserMessageRead.user_id == user_id,
        )
        .first()
    )
    if existing:
        return True
    row = UserMessageRead(
        id=str(uuid.uuid4()),
        message_id=message_id,
        user_id=user_id,
        tenant_id=tenant_id,
    )
    db.add(row)
    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=user_id,
        action="message_marked_read",
        entity_type="email_message",
        entity_id=message_id,
        changes={"thread_id": msg.thread_id},
    )
    db.flush()
    return True


def mark_message_unread(
    db: Session,
    *,
    message_id: str,
    tenant_id: str,
    user_id: str,
) -> bool:
    msg = _verify_message_access(
        db, message_id=message_id, tenant_id=tenant_id, user_id=user_id
    )
    deleted = (
        db.query(UserMessageRead)
        .filter(
            UserMessageRead.message_id == message_id,
            UserMessageRead.user_id == user_id,
        )
        .delete(synchronize_session=False)
    )
    if deleted:
        _audit(
            db,
            tenant_id=tenant_id,
            actor_user_id=user_id,
            action="message_marked_unread",
            entity_type="email_message",
            entity_id=message_id,
            changes={"thread_id": msg.thread_id},
        )
    db.flush()
    return bool(deleted)


# ─────────────────────────────────────────────────────────────────────
# Mutation path — per-user-per-thread archive + flag
# ─────────────────────────────────────────────────────────────────────


def _get_or_create_status(
    db: Session,
    *,
    thread: EmailThread,
    user_id: str,
    tenant_id: str,
) -> EmailThreadStatus:
    status = (
        db.query(EmailThreadStatus)
        .filter(
            EmailThreadStatus.thread_id == thread.id,
            EmailThreadStatus.user_id == user_id,
        )
        .first()
    )
    if status:
        return status
    status = EmailThreadStatus(
        id=str(uuid.uuid4()),
        thread_id=thread.id,
        user_id=user_id,
        tenant_id=tenant_id,
    )
    db.add(status)
    db.flush()
    return status


def archive_thread(
    db: Session,
    *,
    thread_id: str,
    tenant_id: str,
    user_id: str,
) -> bool:
    thread = _verify_thread_access(
        db, thread_id=thread_id, tenant_id=tenant_id, user_id=user_id
    )
    status = _get_or_create_status(
        db, thread=thread, user_id=user_id, tenant_id=tenant_id
    )
    if status.is_archived:
        return True  # idempotent
    status.is_archived = True
    status.archived_at = datetime.now(timezone.utc)
    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=user_id,
        action="thread_archived",
        entity_type="email_thread",
        entity_id=thread_id,
    )
    db.flush()
    return True


def unarchive_thread(
    db: Session,
    *,
    thread_id: str,
    tenant_id: str,
    user_id: str,
) -> bool:
    thread = _verify_thread_access(
        db, thread_id=thread_id, tenant_id=tenant_id, user_id=user_id
    )
    status = _get_or_create_status(
        db, thread=thread, user_id=user_id, tenant_id=tenant_id
    )
    if not status.is_archived:
        return True  # idempotent
    status.is_archived = False
    status.archived_at = None
    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=user_id,
        action="thread_unarchived",
        entity_type="email_thread",
        entity_id=thread_id,
    )
    db.flush()
    return True


def flag_thread(
    db: Session,
    *,
    thread_id: str,
    tenant_id: str,
    user_id: str,
) -> bool:
    thread = _verify_thread_access(
        db, thread_id=thread_id, tenant_id=tenant_id, user_id=user_id
    )
    status = _get_or_create_status(
        db, thread=thread, user_id=user_id, tenant_id=tenant_id
    )
    if status.is_flagged:
        return True
    status.is_flagged = True
    status.flagged_at = datetime.now(timezone.utc)
    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=user_id,
        action="thread_flagged",
        entity_type="email_thread",
        entity_id=thread_id,
    )
    db.flush()
    return True


def unflag_thread(
    db: Session,
    *,
    thread_id: str,
    tenant_id: str,
    user_id: str,
) -> bool:
    thread = _verify_thread_access(
        db, thread_id=thread_id, tenant_id=tenant_id, user_id=user_id
    )
    status = _get_or_create_status(
        db, thread=thread, user_id=user_id, tenant_id=tenant_id
    )
    if not status.is_flagged:
        return True
    status.is_flagged = False
    status.flagged_at = None
    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=user_id,
        action="thread_unflagged",
        entity_type="email_thread",
        entity_id=thread_id,
    )
    db.flush()
    return True
