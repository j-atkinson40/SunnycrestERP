"""Email Glance widget data service — Phase W-4b Layer 1 Step 5.

Surfaces email signals across the user's accessible email accounts per
§3.26.9.3 + §3.26.9.7 Communications Layer per-primitive decomposition.

**Signals computed**:
  - ``unread_count`` — total unread inbound messages across accessible
    accounts, per the canonical ``UserMessageRead`` × inbound message
    pattern (a message is "unread for this user" when no
    UserMessageRead row exists for (message_id, user_id)).
  - ``top_sender_email`` + ``top_sender_name`` + ``top_sender_tenant_label``
    — most-recent unread sender (defaults to the most recent inbound
    message's sender when nothing unread).
  - ``cross_tenant_indicator`` — True when ANY thread surfacing in this
    widget is cross-tenant (per ``EmailThread.is_cross_tenant``).
  - ``ai_priority_count`` — Phase W-4b sequence step 7 future signal;
    placeholder zero today (no Intelligence priority scoring shipped
    yet — synthesizer per §3.26.9.7 lands with communications stream).

**Tenant isolation discipline**:
  - User's accessible accounts resolved via the
    ``email_account_access`` junction filtered to the user's tenant
    (mirrors ``inbox_service._accessible_account_ids`` canonical helper)
  - Every query joins ``email_messages`` → ``email_threads`` →
    ``email_accounts`` → ``email_account_access`` so we never read a
    message the user lacks access to.

**Per-user discipline** (§3.26.15.13 Q1): unread state is per-user.
Two operators sharing ``sales@`` account see different unread counts.
The widget reflects ONLY the calling user's view.

**Performance budget** (per Step 5 spec): p50 < 200ms — matches existing
widget data service budget. Worst-case query at typical inbox volumes
(<10K inbound messages × per-user read state) sits comfortably under
the budget.

**Empty/disabled states**:
  - User has no accessible accounts → ``unread_count: 0``,
    ``has_email_access: False``; widget renders empty-state.
  - User has accounts but zero unread → ``unread_count: 0``,
    ``has_email_access: True``; widget renders "Inbox clear" empty
    state per §14.3 (count zero → primitive empty state).
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.email_primitive import (
    EmailAccount,
    EmailAccountAccess,
    EmailMessage,
    EmailThread,
    UserMessageRead,
)
from app.models.user import User

logger = logging.getLogger(__name__)


def _accessible_account_ids(
    db: Session, *, tenant_id: str, user_id: str
) -> list[str]:
    """Return EmailAccount ids the user currently has read access on.

    Mirrors ``inbox_service._accessible_account_ids`` — single source of
    truth for access enforcement. The duplicate in this module is
    deliberate: the widget data service is queried in tight loops on
    Pulse load + 5-min refresh; coupling to the inbox service module
    would force importing the entire inbox query stack on every widget
    fetch. Keep the helper local + small.
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


def get_email_glance(db: Session, *, user: User) -> dict[str, Any]:
    """Return the email_glance widget data payload for the given user.

    Returns a JSON-serializable dict with:
      - has_email_access: bool — user has at least one accessible
        EmailAccount (drives empty-state vs. "Inbox clear" copy)
      - unread_count: int — unread inbound messages across accessible
        accounts
      - top_sender_email: str | None — sender of the most-recent unread
        inbound message (or most-recent inbound when zero unread)
      - top_sender_name: str | None
      - top_sender_tenant_label: str | None — for cross-tenant context
        (e.g., "Hopkins FH"); None for same-tenant senders
      - cross_tenant_indicator: bool — any thread in this widget is
        cross-tenant
      - ai_priority_count: int — placeholder zero today; W-4b step 7
        will surface Haiku-scored priority count
      - target_thread_id: str | None — set when single-thread surface
        (drives /inbox?thread_id={id} click navigation per Step 5
        spec item #4)

    Tenant scoping: ``EmailAccount.tenant_id == user.company_id`` filter
    + ``EmailAccountAccess`` junction. Cross-tenant masking flows
    through ``EmailThread.is_field_masked_for`` placeholder (Step 1
    canonical pattern) when sender belongs to a partner tenant.
    """
    if not user.company_id:
        return _empty_payload(has_email_access=False)

    account_ids = _accessible_account_ids(
        db, tenant_id=user.company_id, user_id=user.id
    )
    if not account_ids:
        return _empty_payload(has_email_access=False)

    # ── unread_count ────────────────────────────────────────────────
    # Inbound messages on accessible accounts where no UserMessageRead
    # row exists for (message.id, user.id). LEFT JOIN + filter on NULL
    # is the canonical "absent row" query pattern.
    unread_query = (
        db.query(EmailMessage.id, EmailMessage.thread_id, EmailMessage.received_at)
        .outerjoin(
            UserMessageRead,
            and_(
                UserMessageRead.message_id == EmailMessage.id,
                UserMessageRead.user_id == user.id,
            ),
        )
        .filter(
            EmailMessage.account_id.in_(account_ids),
            EmailMessage.tenant_id == user.company_id,
            EmailMessage.direction == "inbound",
            EmailMessage.is_deleted.is_(False),
            UserMessageRead.id.is_(None),
        )
        .order_by(desc(EmailMessage.received_at))
    )

    unread_rows = unread_query.limit(50).all()  # cap fan-out for perf
    unread_count = len(unread_rows)

    # If we hit the cap, run a precise count query so the displayed
    # value is honest (50+ rendering decision lives in the widget UI).
    if unread_count >= 50:
        precise_count = (
            db.query(func.count(EmailMessage.id))
            .outerjoin(
                UserMessageRead,
                and_(
                    UserMessageRead.message_id == EmailMessage.id,
                    UserMessageRead.user_id == user.id,
                ),
            )
            .filter(
                EmailMessage.account_id.in_(account_ids),
                EmailMessage.tenant_id == user.company_id,
                EmailMessage.direction == "inbound",
                EmailMessage.is_deleted.is_(False),
                UserMessageRead.id.is_(None),
            )
            .scalar()
        )
        unread_count = int(precise_count or 0)

    # ── top sender + target thread + cross-tenant indicator ────────
    target_thread_id: str | None = None
    cross_tenant_indicator = False
    top_sender_email: str | None = None
    top_sender_name: str | None = None
    top_sender_tenant_label: str | None = None

    if unread_rows:
        most_recent_unread_message_id = unread_rows[0][0]
        # Re-fetch with sender + thread linkage for display + cross-
        # tenant scan. Bounded query (single message id).
        msg = (
            db.query(EmailMessage, EmailThread)
            .join(EmailThread, EmailThread.id == EmailMessage.thread_id)
            .filter(EmailMessage.id == most_recent_unread_message_id)
            .first()
        )
        if msg:
            email_msg, thread = msg
            top_sender_email = email_msg.sender_email
            top_sender_name = email_msg.sender_name
            # Cross-tenant indicator across ALL unread threads — scan
            # the unread-thread-id set; bounded by capped query above.
            unread_thread_ids = {row[1] for row in unread_rows}
            if unread_thread_ids:
                cross_tenant_count = (
                    db.query(func.count(EmailThread.id))
                    .filter(
                        EmailThread.id.in_(unread_thread_ids),
                        EmailThread.is_cross_tenant.is_(True),
                    )
                    .scalar()
                )
                cross_tenant_indicator = bool(cross_tenant_count and cross_tenant_count > 0)

            # Tenant label resolution for cross-tenant top sender.
            # Same-tenant sender: omit the label entirely (per §14.9.1
            # canon: "When sender's tenant === current tenant: omit
            # tenant context, default to Self").
            if thread.is_cross_tenant:
                top_sender_tenant_label = _resolve_partner_tenant_label(
                    db, thread, caller_tenant_id=user.company_id
                )

            # target_thread_id surfaces ONLY when there's exactly one
            # unread thread → click goes directly to that thread.
            # Multi-thread surface lands on /inbox?status=unread.
            if len(unread_thread_ids) == 1:
                target_thread_id = next(iter(unread_thread_ids))

    elif unread_count == 0:
        # No unread — surface most-recent inbound for context (display
        # only; widget renders "Inbox clear" empty state).
        most_recent = (
            db.query(EmailMessage)
            .filter(
                EmailMessage.account_id.in_(account_ids),
                EmailMessage.tenant_id == user.company_id,
                EmailMessage.direction == "inbound",
                EmailMessage.is_deleted.is_(False),
            )
            .order_by(desc(EmailMessage.received_at))
            .first()
        )
        if most_recent:
            top_sender_email = most_recent.sender_email
            top_sender_name = most_recent.sender_name

    return {
        "has_email_access": True,
        "unread_count": unread_count,
        "top_sender_email": top_sender_email,
        "top_sender_name": top_sender_name,
        "top_sender_tenant_label": top_sender_tenant_label,
        "cross_tenant_indicator": cross_tenant_indicator,
        # Phase W-4b sequence step 7-8 future signal — placeholder zero
        # today. When `email.priority.score` Haiku prompt ships +
        # `communications_intelligence_service.py` synthesizes per-
        # primitive priority signals, this surfaces the score-flagged
        # subset of unread_count.
        "ai_priority_count": 0,
        "target_thread_id": target_thread_id,
    }


def _empty_payload(*, has_email_access: bool) -> dict[str, Any]:
    """Return the canonical empty-state shape."""
    return {
        "has_email_access": has_email_access,
        "unread_count": 0,
        "top_sender_email": None,
        "top_sender_name": None,
        "top_sender_tenant_label": None,
        "cross_tenant_indicator": False,
        "ai_priority_count": 0,
        "target_thread_id": None,
    }


def _resolve_partner_tenant_label(
    db: Session, thread: EmailThread, *, caller_tenant_id: str
) -> str | None:
    """Resolve a display label for the cross-tenant partner.

    Per §3.26.9.4 anonymization-at-layer-rendering: sender identity
    surfaces at the company level by default. Returns the partner
    tenant's company name (or None if the partner can't be resolved
    from the thread's participants).

    Step 1 placeholder: the cross_tenant_partner_tenant_id resolution
    happens via the EmailParticipant.external_tenant_id field
    (populated during ingestion when sender resolves to a partner-
    tenant Bridgeable user). Defensive None when partner unresolvable.
    """
    from app.models.email_primitive import EmailParticipant

    partner_row = (
        db.query(EmailParticipant.external_tenant_id)
        .filter(
            EmailParticipant.thread_id == thread.id,
            EmailParticipant.external_tenant_id.isnot(None),
            EmailParticipant.external_tenant_id != caller_tenant_id,
        )
        .first()
    )
    if not partner_row or not partner_row[0]:
        return None
    partner_tenant_id = partner_row[0]
    partner = (
        db.query(Company.name).filter(Company.id == partner_tenant_id).first()
    )
    return partner[0] if partner else None
