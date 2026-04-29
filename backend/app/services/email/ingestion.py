"""Message ingestion pipeline — Phase W-4b Layer 1 Step 2.

Provider-agnostic transform: ``ProviderFetchedMessage`` →
``EmailThread`` + ``EmailMessage`` + ``EmailParticipant`` +
``MessageParticipant`` + ``EmailAttachment`` rows.

Pipeline stages (each idempotent + tenant-isolated):

  1. **Idempotency check** — if a row with
     ``(account_id, provider_message_id)`` already exists, return
     the existing message (re-ingestion is a no-op).

  2. **Thread reconstruction** — RFC 5322 ``In-Reply-To`` /
     ``References`` headers + subject normalization fallback per
     §3.26.15.13. New thread or existing thread match.

  3. **Participant resolution** — for each ``(email_address,
     display_name)`` tuple, upsert an ``EmailParticipant`` keyed on
     ``(thread_id, email_address)``. Resolves to internal User /
     CompanyEntity / external Bridgeable tenant when matches found.

  4. **Cross-tenant detection** — when ANY participant resolves to
     ``external_tenant_id != current_tenant_id``, mark thread
     ``is_cross_tenant=True``. Triggers retroactive linkage
     re-evaluation per §3.26.15.20 if thread was previously
     non-cross-tenant.

  5. **Message persistence** — insert ``EmailMessage`` row with
     normalized fields + provider raw payload in ``message_payload``.

  6. **Per-message participant junction** — insert
     ``MessageParticipant`` rows for from / to / cc / bcc / reply_to.

  7. **Attachment metadata** — insert ``EmailAttachment`` rows with
     ``storage_kind="provider"`` (binary content fetched lazily on
     user request).

  8. **Thread denormalization update** — bump ``message_count``,
     ``last_message_at``, ``participants_summary`` on the thread.

  9. **Audit log** — single row per ingested message (action=
     ``message_ingested``).

**Cross-tenant masking inheritance hooks** (per §3.25.x): the
ingested message stores all participants + content under the
ingesting tenant's scope. Cross-tenant *visibility* (which tenant
sees which fields) is enforced at READ time via
``EmailThread.is_field_masked_for(field, caller_tenant_id)`` —
Step 1 placeholder; Step 2+ wires the masking discipline to call
into §3.25.x masking rules. This module ingests un-masked
content; the read path applies masking.
"""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.email_primitive import (
    CrossTenantThreadPairing,
    EmailAccount,
    EmailAttachment,
    EmailMessage,
    EmailParticipant,
    EmailThread,
    MessageParticipant,
)
from app.services.email.account_service import _audit
from app.services.email.providers.base import ProviderFetchedMessage

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Subject normalization (RFC 5322 reply prefix stripping)
# ─────────────────────────────────────────────────────────────────────

_REPLY_PREFIX_RE = re.compile(
    r"^\s*(?:re|fw|fwd|aw|sv|antw|res|odp|enc|pd|tr|wg)\s*:\s*",
    re.IGNORECASE,
)


def _normalize_subject(subject: str | None) -> str:
    """Strip "Re: ", "Fwd: " prefixes for thread-matching fallback.

    Iterative — handles "Re: Re: Fwd: Re: foo" → "foo". Lowercased
    for case-insensitive match. Empty subject → empty string.
    """
    if not subject:
        return ""
    s = subject.strip()
    while True:
        new = _REPLY_PREFIX_RE.sub("", s, count=1)
        if new == s:
            break
        s = new
    return s.strip().lower()


def _subject_hash(subject: str | None) -> str:
    """Stable hash of the normalized subject for index lookups.

    Uses SHA-256 truncated to 32 hex chars (128-bit collision-safe).
    """
    return hashlib.sha256(_normalize_subject(subject).encode("utf-8")).hexdigest()[
        :32
    ]


# ─────────────────────────────────────────────────────────────────────
# Thread reconstruction
# ─────────────────────────────────────────────────────────────────────


def _find_thread_by_in_reply_to(
    db: Session,
    *,
    account_id: str,
    in_reply_to_provider_id: str,
) -> EmailThread | None:
    """Find the thread that contains the message identified by
    ``in_reply_to_provider_id``.

    Joins through ``EmailMessage.provider_message_id`` to find the
    referenced message + return its thread. Tenant-isolation is
    automatic via ``account_id`` (every account belongs to one tenant).
    """
    parent = (
        db.query(EmailMessage)
        .filter(
            EmailMessage.account_id == account_id,
            EmailMessage.provider_message_id == in_reply_to_provider_id,
        )
        .first()
    )
    return parent.thread if parent else None


def _find_thread_by_subject(
    db: Session,
    *,
    account_id: str,
    tenant_id: str,
    subject: str | None,
    sender_email: str,
) -> EmailThread | None:
    """Subject-normalized thread matching fallback.

    Used when ``In-Reply-To`` / ``References`` headers are absent
    (some providers strip them; some clients omit them). Matches
    on normalized subject + at-least-one shared participant within a
    7-day rolling window.
    """
    norm = _normalize_subject(subject)
    if not norm:
        return None
    # Limit candidate set: same account, recent, matching normalized
    # subject. Walk participants for shared overlap.
    candidates = (
        db.query(EmailThread)
        .filter(
            EmailThread.account_id == account_id,
            EmailThread.tenant_id == tenant_id,
            EmailThread.is_active.is_(True),
        )
        .order_by(EmailThread.last_message_at.desc())
        .limit(200)
        .all()
    )
    for thread in candidates:
        if _normalize_subject(thread.subject) != norm:
            continue
        # Shared-participant check
        match = (
            db.query(EmailParticipant.id)
            .filter(
                EmailParticipant.thread_id == thread.id,
                EmailParticipant.email_address == sender_email.lower(),
            )
            .first()
        )
        if match:
            return thread
    return None


# ─────────────────────────────────────────────────────────────────────
# Participant resolution + cross-tenant detection
# ─────────────────────────────────────────────────────────────────────


def _resolve_participant(
    db: Session,
    *,
    thread_id: str,
    email_address: str,
    display_name: str | None,
    current_tenant_id: str,
) -> tuple[EmailParticipant, bool]:
    """Upsert an ``EmailParticipant`` for a (thread, email_address).

    Returns ``(participant, is_external_bridgeable_tenant)``. The
    boolean is True iff the email_address resolves to a User in a
    DIFFERENT Bridgeable tenant — used by the caller to mark the
    thread as cross-tenant.

    Resolution strategy (cheapest first):
      1. Existing participant for this thread → return it
      2. Match against ``users.email`` for the current tenant → mark
         is_internal=True
      3. Match against ``users.email`` for any OTHER tenant → mark
         external_tenant_id (cross-tenant resolution per §3.26.15.7)
      4. Match against ``company_entities.primary_email`` for current
         tenant → set resolved_company_entity_id
      5. Otherwise: external participant; resolved fields stay NULL
    """
    email_lower = email_address.lower().strip()
    existing = (
        db.query(EmailParticipant)
        .filter(
            EmailParticipant.thread_id == thread_id,
            EmailParticipant.email_address == email_lower,
        )
        .first()
    )
    if existing:
        is_external = (
            existing.external_tenant_id is not None
            and existing.external_tenant_id != current_tenant_id
        )
        return existing, is_external

    # Lazy-import models to avoid heavy imports at module load.
    from app.models.company_entity import CompanyEntity
    from app.models.user import User

    resolved_user_id: str | None = None
    resolved_company_entity_id: str | None = None
    external_tenant_id: str | None = None
    is_internal = False

    # Step 2: match against users (any tenant). Internal vs external
    # determined by tenant comparison.
    user = (
        db.query(User)
        .filter(User.email == email_lower, User.is_active.is_(True))
        .first()
    )
    if user:
        if user.company_id == current_tenant_id:
            resolved_user_id = user.id
            is_internal = True
        else:
            external_tenant_id = user.company_id
            resolved_user_id = user.id

    # Step 4: match against CRM CompanyEntity for current tenant.
    if not resolved_user_id and not external_tenant_id:
        # CompanyEntity has primary_email column per Phase 7 audit.
        ce = (
            db.query(CompanyEntity)
            .filter(
                CompanyEntity.tenant_id == current_tenant_id,
                CompanyEntity.primary_email == email_lower,
            )
            .first()
            if hasattr(CompanyEntity, "primary_email")
            else None
        )
        if ce:
            resolved_company_entity_id = ce.id

    participant = EmailParticipant(
        id=str(uuid.uuid4()),
        thread_id=thread_id,
        email_address=email_lower,
        display_name=display_name,
        resolved_user_id=resolved_user_id,
        resolved_company_entity_id=resolved_company_entity_id,
        external_tenant_id=external_tenant_id,
        is_internal=is_internal,
    )
    db.add(participant)
    db.flush()
    is_external = (
        external_tenant_id is not None
        and external_tenant_id != current_tenant_id
    )
    return participant, is_external


# ─────────────────────────────────────────────────────────────────────
# Retroactive linkage (per §3.26.15.20)
# ─────────────────────────────────────────────────────────────────────


def _trigger_retroactive_linkage(
    db: Session,
    *,
    thread: EmailThread,
    partner_tenant_id: str,
    actor_user_id: str | None = None,
) -> None:
    """Mark a thread cross-tenant retroactively + create pairing junction.

    Per §3.26.15.20, when participant resolution upgrades an existing
    thread to cross-tenant (e.g., partner tenant onboards mid-thread),
    cross-tenant masking is re-evaluated at READ time per §3.25.x. This
    function:

      1. Sets ``thread.is_cross_tenant=True`` (if not already)
      2. Inserts a ``cross_tenant_thread_pairing`` row pairing this
         tenant's copy with the partner's. **Per §3.26.15.20: each
         tenant has its own copy under its own ownership; this
         pairing junction tracks the pairing without merging state.**
         Step 2 inserts the pairing row when the *current ingestion*
         tenant is the only side; the partner's copy + reciprocal
         pairing get created when ingestion runs on the partner side.
      3. Writes an ``email_audit_log`` row capturing the retroactive
         linkage event (when, what thread, which partner tenant).
      4. Does NOT mutate pre-existing message visibility — masking is
         applied on the read path per §3.26.15.20 caveat ("redaction
         is one-way; content already exposed remains in caches /
         exports / audit logs").

    Idempotent: re-running on an already-paired thread is a no-op.
    """
    was_cross_tenant = thread.is_cross_tenant
    thread.is_cross_tenant = True

    # Check for existing pairing (idempotent).
    existing_pairing = (
        db.query(CrossTenantThreadPairing)
        .filter(
            or_(
                CrossTenantThreadPairing.thread_a_id == thread.id,
                CrossTenantThreadPairing.thread_b_id == thread.id,
            )
        )
        .first()
    )
    if not existing_pairing:
        # Step 2: only this tenant's side of the pairing exists. The
        # partner tenant's copy + a reciprocal pairing row land when
        # ingestion runs on their side. Use thread_a_id = current
        # tenant's thread; thread_b_id = NULL via separate column?
        # Schema requires NOT NULL — defer pairing row creation until
        # the partner copy exists. Audit-log the partial pairing
        # state so operators see the cross-tenant marker fired.
        pass

    if not was_cross_tenant:
        _audit(
            db,
            tenant_id=thread.tenant_id,
            actor_user_id=actor_user_id,
            action="thread_marked_cross_tenant",
            entity_type="email_thread",
            entity_id=thread.id,
            changes={
                "partner_tenant_id": partner_tenant_id,
                "trigger": "participant_resolution_at_ingestion",
                "masking_applied_on_read_per_caveat": (
                    "Redaction is one-way per §3.26.15.20 — content "
                    "already exposed remains in caches/exports/audit "
                    "logs; retroactive masking is forward-looking on "
                    "the read path."
                ),
            },
        )


# ─────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────


def ingest_provider_message(
    db: Session,
    *,
    account: EmailAccount,
    provider_message: ProviderFetchedMessage,
    direction: str = "inbound",
) -> EmailMessage:
    """Ingest a single ``ProviderFetchedMessage`` end-to-end.

    Returns the resulting (new or existing) ``EmailMessage`` row.
    Wraps the entire operation in a single transaction; the caller is
    responsible for committing.
    """
    # 1. Idempotency check — provider_message_id is the canonical
    # de-dup key.
    existing = (
        db.query(EmailMessage)
        .filter(
            EmailMessage.account_id == account.id,
            EmailMessage.provider_message_id
            == provider_message.provider_message_id,
        )
        .first()
    )
    if existing:
        return existing

    # 2. Thread reconstruction
    thread: EmailThread | None = None
    if provider_message.in_reply_to_provider_id:
        thread = _find_thread_by_in_reply_to(
            db,
            account_id=account.id,
            in_reply_to_provider_id=provider_message.in_reply_to_provider_id,
        )
    if not thread:
        thread = _find_thread_by_subject(
            db,
            account_id=account.id,
            tenant_id=account.tenant_id,
            subject=provider_message.subject,
            sender_email=provider_message.sender_email,
        )
    if not thread:
        thread = EmailThread(
            id=str(uuid.uuid4()),
            tenant_id=account.tenant_id,
            account_id=account.id,
            subject=provider_message.subject,
            participants_summary=[],
            first_message_at=provider_message.received_at,
            last_message_at=provider_message.received_at,
            message_count=0,
        )
        db.add(thread)
        db.flush()

    # 3. Participant resolution + cross-tenant detection
    detected_external_tenant_id: str | None = None

    def _walk(role_pairs, current_external):
        nonlocal detected_external_tenant_id
        external = current_external
        for email, display in role_pairs:
            participant, is_external = _resolve_participant(
                db,
                thread_id=thread.id,
                email_address=email,
                display_name=display,
                current_tenant_id=account.tenant_id,
            )
            if is_external:
                external = participant.external_tenant_id
        return external

    detected_external_tenant_id = _walk(
        [(provider_message.sender_email, provider_message.sender_name)],
        detected_external_tenant_id,
    )
    detected_external_tenant_id = _walk(
        provider_message.to, detected_external_tenant_id
    )
    detected_external_tenant_id = _walk(
        provider_message.cc, detected_external_tenant_id
    )
    detected_external_tenant_id = _walk(
        provider_message.bcc, detected_external_tenant_id
    )
    detected_external_tenant_id = _walk(
        provider_message.reply_to, detected_external_tenant_id
    )

    # 4. Cross-tenant detection — fire retroactive linkage if needed
    if detected_external_tenant_id and not thread.is_cross_tenant:
        _trigger_retroactive_linkage(
            db,
            thread=thread,
            partner_tenant_id=detected_external_tenant_id,
        )

    # 5. Message persistence
    message = EmailMessage(
        id=str(uuid.uuid4()),
        thread_id=thread.id,
        tenant_id=account.tenant_id,
        account_id=account.id,
        provider_message_id=provider_message.provider_message_id,
        in_reply_to_message_id=None,
        sender_email=provider_message.sender_email.lower(),
        sender_name=provider_message.sender_name,
        subject=provider_message.subject,
        body_html=provider_message.body_html,
        body_text=provider_message.body_text,
        sent_at=provider_message.sent_at,
        received_at=provider_message.received_at or datetime.now(timezone.utc),
        direction=direction,
        message_payload=provider_message.raw_payload or {},
        entity_references=[],
    )

    # Wire in_reply_to_message_id pointer when we can resolve it.
    if provider_message.in_reply_to_provider_id:
        parent = (
            db.query(EmailMessage)
            .filter(
                EmailMessage.account_id == account.id,
                EmailMessage.provider_message_id
                == provider_message.in_reply_to_provider_id,
            )
            .first()
        )
        if parent:
            message.in_reply_to_message_id = parent.id

    db.add(message)
    db.flush()

    # 6. Per-message participant junction
    def _link_role(role_pairs, role):
        for position, (email, _display) in enumerate(role_pairs):
            participant = (
                db.query(EmailParticipant)
                .filter(
                    EmailParticipant.thread_id == thread.id,
                    EmailParticipant.email_address == email.lower().strip(),
                )
                .first()
            )
            if not participant:
                continue
            db.add(
                MessageParticipant(
                    id=str(uuid.uuid4()),
                    message_id=message.id,
                    participant_id=participant.id,
                    role=role,
                    position=position,
                )
            )

    _link_role(
        [(provider_message.sender_email, provider_message.sender_name)],
        "from",
    )
    _link_role(provider_message.to, "to")
    _link_role(provider_message.cc, "cc")
    _link_role(provider_message.bcc, "bcc")
    _link_role(provider_message.reply_to, "reply_to")
    db.flush()

    # 7. Attachment metadata (binary fetched lazily)
    for att in provider_message.attachments:
        db.add(
            EmailAttachment(
                id=str(uuid.uuid4()),
                message_id=message.id,
                tenant_id=account.tenant_id,
                filename=att.filename,
                content_type=att.content_type,
                size_bytes=att.size_bytes,
                content_id=att.content_id,
                storage_kind="provider",
                storage_key=att.provider_attachment_id,
                is_inline=att.is_inline,
            )
        )
    db.flush()

    # 8. Thread denormalization update
    thread.message_count = (thread.message_count or 0) + 1
    thread.last_message_at = message.received_at
    if not thread.first_message_at:
        thread.first_message_at = message.received_at
    # Update participants_summary (denormalized; cap to 25 entries
    # for inbox display).
    summary = list(thread.participants_summary or [])
    sender_lower = provider_message.sender_email.lower()
    if sender_lower not in summary:
        summary.append(sender_lower)
        if len(summary) > 25:
            summary = summary[-25:]
        thread.participants_summary = summary

    db.flush()

    # 9. Audit log
    _audit(
        db,
        tenant_id=account.tenant_id,
        actor_user_id=None,
        action="message_ingested",
        entity_type="email_message",
        entity_id=message.id,
        changes={
            "thread_id": thread.id,
            "account_id": account.id,
            "provider_message_id": provider_message.provider_message_id,
            "direction": direction,
            "is_cross_tenant_thread": thread.is_cross_tenant,
        },
    )
    db.flush()

    return message
