"""Signature envelope lifecycle service — Phase D-4.

Envelope state machine:
  draft → sent → in_progress → completed
                             ↘ declined
                             ↘ voided
                             ↘ expired

Party state machine:
  pending → sent → viewed → consented → signed
                                     ↘ declined
                                     ↘ expired

Every state transition writes a SignatureEvent with a monotonically-
increasing sequence_number for the envelope.

This service has NO update/delete methods on SignatureEvent — the audit
log is append-only.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.canonical_document import Document
from app.models.signature import (
    SignatureEnvelope,
    SignatureEvent,
    SignatureField,
    SignatureParty,
)
from app.services import legacy_r2_client
from app.services.signing.token_service import generate_signer_token


class SignatureServiceError(Exception):
    """Raised when an envelope operation is rejected (state conflict,
    not-found, validation). HTTP-friendly: includes http_status."""

    def __init__(self, message: str, *, http_status: int = 400) -> None:
        super().__init__(message)
        self.http_status = http_status


# ── Inputs ────────────────────────────────────────────────────────────


@dataclass
class PartyInput:
    signing_order: int
    role: str
    display_name: str
    email: str
    phone: str | None = None


@dataclass
class FieldInput:
    """Bound to a party by `signing_order` OR `party_role`. party_role
    is preferred when you're wiring a template with named roles because
    it decouples field definitions from the order the parties are
    passed in.

    Exactly one of signing_order / party_role must resolve to a party.
    """

    # Either signing_order OR party_role must be set.
    signing_order: int | None = None
    party_role: str | None = None
    field_type: str = "signature"  # signature | initial | date | typed_name | checkbox | text
    anchor_string: str | None = None
    page_number: int | None = None
    position_x: float | None = None
    position_y: float | None = None
    width: float | None = None
    height: float | None = None
    # D-5 — offset tuning (points)
    anchor_x_offset: float = 0.0
    anchor_y_offset: float = 0.0
    anchor_units: str = "points"
    required: bool = True
    label: str | None = None
    default_value: str | None = None


# ── Event logging ─────────────────────────────────────────────────────


def _next_sequence_number(db: Session, envelope_id: str) -> int:
    val = (
        db.query(func.coalesce(func.max(SignatureEvent.sequence_number), 0) + 1)
        .filter(SignatureEvent.envelope_id == envelope_id)
        .scalar()
    )
    return int(val)


def record_event(
    db: Session,
    *,
    envelope_id: str,
    event_type: str,
    party_id: str | None = None,
    actor_user_id: str | None = None,
    actor_party_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    meta: dict[str, Any] | None = None,
) -> SignatureEvent:
    """Append an event. Never updates existing rows."""
    ev = SignatureEvent(
        id=str(uuid.uuid4()),
        envelope_id=envelope_id,
        party_id=party_id,
        sequence_number=_next_sequence_number(db, envelope_id),
        event_type=event_type,
        actor_user_id=actor_user_id,
        actor_party_id=actor_party_id,
        ip_address=ip_address,
        user_agent=user_agent,
        meta_json=meta or {},
    )
    db.add(ev)
    return ev


# ── Document hash ────────────────────────────────────────────────────


def compute_document_hash(pdf_bytes: bytes) -> str:
    """SHA-256 of the PDF bytes — captures original document state."""
    return hashlib.sha256(pdf_bytes).hexdigest()


# ── Core lifecycle ────────────────────────────────────────────────────


def create_envelope(
    db: Session,
    *,
    document_id: str,
    company_id: str,
    created_by_user_id: str,
    subject: str,
    description: str | None,
    parties: list[PartyInput],
    fields: list[FieldInput],
    routing_type: str = "sequential",
    expires_in_days: int = 30,
) -> SignatureEnvelope:
    """Create envelope in draft status. Does not send.

    Hashes the current Document PDF at creation time so we can detect
    tampering at completion.
    """
    if not parties:
        raise SignatureServiceError(
            "An envelope requires at least one party"
        )
    if routing_type not in ("sequential", "parallel"):
        raise SignatureServiceError(
            f"Invalid routing_type {routing_type!r}"
        )

    # Verify document exists + tenant-scoped
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.company_id == company_id)
        .first()
    )
    if doc is None:
        raise SignatureServiceError(
            "Document not found or not visible to this tenant",
            http_status=404,
        )

    # Compute document hash
    try:
        pdf_bytes = legacy_r2_client.download_bytes(doc.storage_key)
        doc_hash = compute_document_hash(pdf_bytes)
    except Exception as exc:  # noqa: BLE001
        # Degrade gracefully in environments without R2 access
        doc_hash = hashlib.sha256(
            f"{doc.id}:{doc.storage_key}".encode("utf-8")
        ).hexdigest()

    now = datetime.now(timezone.utc)
    envelope = SignatureEnvelope(
        id=str(uuid.uuid4()),
        company_id=company_id,
        document_id=document_id,
        subject=subject,
        description=description,
        routing_type=routing_type,
        status="draft",
        document_hash=doc_hash,
        expires_at=now + timedelta(days=expires_in_days),
        created_by_user_id=created_by_user_id,
    )
    db.add(envelope)
    db.flush()

    # Create parties
    party_by_order: dict[int, SignatureParty] = {}
    seen_orders: set[int] = set()
    for p in parties:
        if p.signing_order in seen_orders:
            raise SignatureServiceError(
                f"Duplicate signing_order {p.signing_order}"
            )
        seen_orders.add(p.signing_order)
        party = SignatureParty(
            id=str(uuid.uuid4()),
            envelope_id=envelope.id,
            signing_order=p.signing_order,
            role=p.role,
            display_name=p.display_name,
            email=p.email,
            phone=p.phone,
            signer_token=generate_signer_token(),
            status="pending",
        )
        db.add(party)
        db.flush()
        party_by_order[p.signing_order] = party

    # Create fields — bind to party by signing_order OR party_role
    party_by_role: dict[str, SignatureParty] = {
        p.role: p for p in party_by_order.values()
    }
    for f in fields:
        party: SignatureParty | None = None
        if f.signing_order is not None:
            party = party_by_order.get(f.signing_order)
        if party is None and f.party_role:
            party = party_by_role.get(f.party_role)
        if party is None:
            raise SignatureServiceError(
                f"Field could not resolve to a party "
                f"(signing_order={f.signing_order}, party_role={f.party_role})"
            )
        sf = SignatureField(
            id=str(uuid.uuid4()),
            envelope_id=envelope.id,
            party_id=party.id,
            field_type=f.field_type,
            anchor_string=f.anchor_string,
            page_number=f.page_number,
            position_x=f.position_x,
            position_y=f.position_y,
            width=f.width,
            height=f.height,
            anchor_x_offset=f.anchor_x_offset,
            anchor_y_offset=f.anchor_y_offset,
            anchor_units=f.anchor_units,
            required=f.required,
            label=f.label,
            default_value=f.default_value,
        )
        db.add(sf)

    db.flush()

    record_event(
        db,
        envelope_id=envelope.id,
        event_type="envelope_created",
        actor_user_id=created_by_user_id,
        meta={
            "party_count": len(parties),
            "routing_type": routing_type,
            "document_hash": doc_hash,
        },
    )
    return envelope


def send_envelope(
    db: Session, envelope_id: str, *, actor_user_id: str | None = None
) -> SignatureEnvelope:
    """Transition draft to sent. Unlock first party (sequential) or all
    (parallel)."""
    envelope = _get_envelope(db, envelope_id)
    if envelope.status != "draft":
        raise SignatureServiceError(
            f"Only drafts can be sent — envelope is {envelope.status!r}",
            http_status=409,
        )
    parties = sorted(envelope.parties, key=lambda p: p.signing_order)
    if not parties:
        raise SignatureServiceError("Envelope has no parties")

    now = datetime.now(timezone.utc)
    envelope.status = "sent"
    envelope.updated_at = now

    if envelope.routing_type == "sequential":
        first = parties[0]
        first.status = "sent"
        first.sent_at = now
        to_notify = [first]
    else:
        to_notify = []
        for p in parties:
            p.status = "sent"
            p.sent_at = now
            to_notify.append(p)

    record_event(
        db,
        envelope_id=envelope.id,
        event_type="envelope_sent",
        actor_user_id=actor_user_id,
        meta={
            "routing_type": envelope.routing_type,
            "notified_party_ids": [p.id for p in to_notify],
        },
    )

    # Notify parties (side effect; does not fail the transition)
    from app.services.signing import notification_service

    for p in to_notify:
        try:
            notification_service.send_invite(db, envelope, p)
        except Exception as exc:  # noqa: BLE001
            # Log but don't fail — the admin can resend
            record_event(
                db,
                envelope_id=envelope.id,
                event_type="notification_failed",
                party_id=p.id,
                meta={"error": str(exc)[:500], "notification_type": "invite"},
            )

    db.flush()
    return envelope


def record_party_view(
    db: Session,
    party: SignatureParty,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> SignatureParty:
    """Mark party as viewed on first signing-link open."""
    now = datetime.now(timezone.utc)
    if party.status == "sent":
        party.status = "viewed"
        party.viewed_at = now
    # Record event every time — for audit trail
    record_event(
        db,
        envelope_id=party.envelope_id,
        event_type="link_viewed",
        party_id=party.id,
        actor_party_id=party.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    # Envelope transitions to in_progress on first view
    env = party.envelope
    if env.status == "sent":
        env.status = "in_progress"
        record_event(
            db,
            envelope_id=env.id,
            event_type="envelope_in_progress",
        )
    return party


def record_party_consent(
    db: Session,
    party: SignatureParty,
    *,
    consent_text: str,
    ip_address: str | None,
    user_agent: str | None,
) -> SignatureParty:
    """Record ESIGN-compliant consent."""
    if party.status not in ("viewed", "sent"):
        raise SignatureServiceError(
            f"Cannot record consent when party status is {party.status!r}",
            http_status=409,
        )
    now = datetime.now(timezone.utc)
    party.status = "consented"
    party.consented_at = now
    record_event(
        db,
        envelope_id=party.envelope_id,
        event_type="consent_recorded",
        party_id=party.id,
        actor_party_id=party.id,
        ip_address=ip_address,
        user_agent=user_agent,
        meta={"consent_text": consent_text[:1000]},
    )
    sync_disinterment_case_status(db, party.envelope_id)
    return party


def record_party_signature(
    db: Session,
    party: SignatureParty,
    *,
    signature_type: str,  # drawn | typed
    signature_data: str,
    typed_signature_name: str | None,
    field_values: dict[str, str],  # field_id -> value
    ip_address: str | None,
    user_agent: str | None,
) -> SignatureParty:
    """Record the party's signature, fill their fields, and move on.

    In sequential mode: next party transitions from pending → sent and
    gets notified. If this was the last party, the envelope completes.
    """
    if party.status != "consented":
        raise SignatureServiceError(
            f"Party must consent before signing (status is {party.status!r})",
            http_status=409,
        )
    if signature_type not in ("drawn", "typed", "uploaded"):
        raise SignatureServiceError(
            f"Invalid signature_type {signature_type!r}"
        )
    envelope = party.envelope
    if envelope.status in ("voided", "expired", "declined", "completed"):
        raise SignatureServiceError(
            f"Envelope is {envelope.status!r} — cannot sign",
            http_status=409,
        )

    now = datetime.now(timezone.utc)
    party.status = "signed"
    party.signed_at = now
    party.signature_type = signature_type
    party.signature_data = signature_data
    party.typed_signature_name = typed_signature_name
    party.signing_ip_address = ip_address
    party.signing_user_agent = user_agent

    # Fill fields — only fields assigned to this party
    party_fields_by_id = {f.id: f for f in party.fields}
    for field_id, value in field_values.items():
        f = party_fields_by_id.get(field_id)
        if f is None:
            continue  # Silently ignore unknown field IDs
        f.value = value

    # Check required fields are filled
    missing = [
        f.label or f.field_type
        for f in party.fields
        if f.required and not f.value and f.field_type != "signature"
    ]
    if missing:
        raise SignatureServiceError(
            f"Required fields not filled: {', '.join(missing)}",
            http_status=400,
        )

    record_event(
        db,
        envelope_id=envelope.id,
        event_type="signature_captured",
        party_id=party.id,
        actor_party_id=party.id,
        ip_address=ip_address,
        user_agent=user_agent,
        meta={
            "signature_type": signature_type,
            "typed_signature_name": typed_signature_name,
        },
    )
    record_event(
        db,
        envelope_id=envelope.id,
        event_type="party_signed",
        party_id=party.id,
        actor_party_id=party.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    # Advance routing
    _advance_after_party_signed(db, envelope, party)
    sync_disinterment_case_status(db, envelope.id)
    return party


def _advance_after_party_signed(
    db: Session, envelope: SignatureEnvelope, just_signed: SignatureParty
) -> None:
    """Sequential: next party (higher signing_order) pending → sent, notify.
    Parallel: no-op unless all parties signed.
    Completion: if all parties signed, complete envelope."""
    parties = sorted(envelope.parties, key=lambda p: p.signing_order)
    all_signed = all(p.status == "signed" for p in parties)
    if all_signed:
        complete_envelope(db, envelope)
        return
    if envelope.routing_type != "sequential":
        return
    next_party = next(
        (
            p
            for p in parties
            if p.signing_order > just_signed.signing_order
            and p.status == "pending"
        ),
        None,
    )
    if next_party is None:
        return  # Nothing to advance (another party is already in progress)
    next_party.status = "sent"
    next_party.sent_at = datetime.now(timezone.utc)

    from app.services.signing import notification_service

    try:
        notification_service.send_invite(db, envelope, next_party)
    except Exception as exc:  # noqa: BLE001
        record_event(
            db,
            envelope_id=envelope.id,
            event_type="notification_failed",
            party_id=next_party.id,
            meta={"error": str(exc)[:500], "notification_type": "invite"},
        )


def record_party_decline(
    db: Session,
    party: SignatureParty,
    *,
    reason: str,
    ip_address: str | None,
    user_agent: str | None,
) -> SignatureEnvelope:
    """Record decline. Envelope transitions to declined; pending parties
    cancelled."""
    if not (reason or "").strip():
        raise SignatureServiceError(
            "Decline reason is required", http_status=400
        )
    envelope = party.envelope
    if envelope.status in ("completed", "voided", "declined", "expired"):
        raise SignatureServiceError(
            f"Envelope is {envelope.status!r} — cannot decline",
            http_status=409,
        )
    now = datetime.now(timezone.utc)
    party.status = "declined"
    party.declined_at = now
    party.decline_reason = reason
    party.signing_ip_address = ip_address
    party.signing_user_agent = user_agent

    envelope.status = "declined"
    envelope.updated_at = now

    # Cancel pending parties
    for p in envelope.parties:
        if p.status in ("pending", "sent", "viewed", "consented"):
            p.status = "expired"

    record_event(
        db,
        envelope_id=envelope.id,
        event_type="party_declined",
        party_id=party.id,
        actor_party_id=party.id,
        ip_address=ip_address,
        user_agent=user_agent,
        meta={"reason": reason[:1000]},
    )
    record_event(
        db,
        envelope_id=envelope.id,
        event_type="envelope_declined",
        meta={
            "decliner_party_id": party.id,
            "decliner_name": party.display_name,
            "reason": reason[:1000],
        },
    )

    # Notify the envelope creator
    from app.services.signing import notification_service

    try:
        notification_service.send_declined(db, envelope, party)
    except Exception as exc:  # noqa: BLE001
        record_event(
            db,
            envelope_id=envelope.id,
            event_type="notification_failed",
            meta={"error": str(exc)[:500], "notification_type": "declined"},
        )
    sync_disinterment_case_status(db, envelope.id)
    return envelope


def void_envelope(
    db: Session,
    envelope_id: str,
    *,
    reason: str,
    voided_by_user_id: str,
) -> SignatureEnvelope:
    """Admin voids envelope. All non-signed parties cancelled."""
    envelope = _get_envelope(db, envelope_id)
    if envelope.status in ("completed", "voided", "declined", "expired"):
        raise SignatureServiceError(
            f"Cannot void envelope in status {envelope.status!r}",
            http_status=409,
        )
    now = datetime.now(timezone.utc)
    envelope.status = "voided"
    envelope.voided_at = now
    envelope.voided_by_user_id = voided_by_user_id
    envelope.void_reason = reason
    envelope.updated_at = now

    pending_parties = [
        p
        for p in envelope.parties
        if p.status in ("pending", "sent", "viewed", "consented")
    ]
    for p in pending_parties:
        p.status = "expired"

    record_event(
        db,
        envelope_id=envelope.id,
        event_type="envelope_voided",
        actor_user_id=voided_by_user_id,
        meta={"reason": reason[:1000]},
    )

    from app.services.signing import notification_service

    for p in pending_parties:
        try:
            notification_service.send_voided(db, envelope, p)
        except Exception as exc:  # noqa: BLE001
            record_event(
                db,
                envelope_id=envelope.id,
                event_type="notification_failed",
                party_id=p.id,
                meta={"error": str(exc)[:500], "notification_type": "voided"},
            )
    sync_disinterment_case_status(db, envelope.id)
    return envelope


def resend_notification(
    db: Session, party_id: str, *, actor_user_id: str | None = None
) -> SignatureParty:
    """Resend the signing link email to `party`. Only valid for parties
    in sent/viewed/consented status."""
    party = db.query(SignatureParty).filter_by(id=party_id).first()
    if party is None:
        raise SignatureServiceError(
            "Party not found", http_status=404
        )
    if party.status not in ("sent", "viewed", "consented"):
        raise SignatureServiceError(
            f"Cannot resend to party in status {party.status!r}",
            http_status=409,
        )
    from app.services.signing import notification_service

    notification_service.send_invite(db, party.envelope, party)
    party.notification_sent_count = (party.notification_sent_count or 0) + 1
    party.last_notification_sent_at = datetime.now(timezone.utc)
    record_event(
        db,
        envelope_id=party.envelope_id,
        event_type="notification_sent",
        party_id=party.id,
        actor_user_id=actor_user_id,
        meta={"notification_type": "invite_resend"},
    )
    return party


def complete_envelope(
    db: Session, envelope: SignatureEnvelope
) -> SignatureEnvelope:
    """Internal: transition to completed. Generate signed PDF +
    Certificate of Completion, notify all parties.

    Called by `_advance_after_party_signed` when the last party signs.
    Safe to call directly in tests.
    """
    if envelope.status == "completed":
        return envelope

    now = datetime.now(timezone.utc)
    envelope.status = "completed"
    envelope.completed_at = now
    envelope.updated_at = now

    record_event(
        db,
        envelope_id=envelope.id,
        event_type="envelope_completed",
    )

    # 1. Render a signed PDF as a new DocumentVersion
    from app.services.signing import certificate_service, signature_renderer

    try:
        signature_renderer.apply_signatures_as_new_version(db, envelope)
    except Exception as exc:  # noqa: BLE001
        record_event(
            db,
            envelope_id=envelope.id,
            event_type="signed_pdf_render_failed",
            meta={"error": str(exc)[:500]},
        )

    # 2. Generate Certificate of Completion
    try:
        cert_doc = certificate_service.generate_certificate(db, envelope)
        envelope.certificate_document_id = cert_doc.id
        record_event(
            db,
            envelope_id=envelope.id,
            event_type="certificate_generated",
            meta={"certificate_document_id": cert_doc.id},
        )
    except Exception as exc:  # noqa: BLE001
        record_event(
            db,
            envelope_id=envelope.id,
            event_type="certificate_generation_failed",
            meta={"error": str(exc)[:500]},
        )

    # 3. Notify all parties
    from app.services.signing import notification_service

    for p in envelope.parties:
        try:
            notification_service.send_completed(db, envelope, p)
        except Exception as exc:  # noqa: BLE001
            record_event(
                db,
                envelope_id=envelope.id,
                event_type="notification_failed",
                party_id=p.id,
                meta={
                    "error": str(exc)[:500],
                    "notification_type": "completed",
                },
            )

    sync_disinterment_case_status(db, envelope.id)
    db.flush()
    return envelope


def check_expiration(db: Session) -> int:
    """Background job — expire any sent/in_progress envelopes past
    expires_at. Returns the count transitioned."""
    now = datetime.now(timezone.utc)
    expired = (
        db.query(SignatureEnvelope)
        .filter(
            SignatureEnvelope.status.in_(("sent", "in_progress")),
            SignatureEnvelope.expires_at.isnot(None),
            SignatureEnvelope.expires_at < now,
        )
        .all()
    )
    for env in expired:
        env.status = "expired"
        env.updated_at = now
        for p in env.parties:
            if p.status in ("pending", "sent", "viewed", "consented"):
                p.status = "expired"
        record_event(
            db,
            envelope_id=env.id,
            event_type="envelope_expired",
            meta={"expires_at": env.expires_at.isoformat()},
        )
    db.flush()
    return len(expired)


# ── Lookups ───────────────────────────────────────────────────────────


def _get_envelope(db: Session, envelope_id: str) -> SignatureEnvelope:
    env = (
        db.query(SignatureEnvelope).filter_by(id=envelope_id).first()
    )
    if env is None:
        raise SignatureServiceError(
            "Envelope not found", http_status=404
        )
    return env


def get_envelope_for_tenant(
    db: Session, envelope_id: str, company_id: str
) -> SignatureEnvelope | None:
    env = (
        db.query(SignatureEnvelope)
        .filter(
            SignatureEnvelope.id == envelope_id,
            SignatureEnvelope.company_id == company_id,
        )
        .first()
    )
    return env


def get_party_by_token(
    db: Session, token: str
) -> SignatureParty | None:
    return (
        db.query(SignatureParty).filter_by(signer_token=token).first()
    )


# ── Phase D-5: keep legacy disinterment sig_* columns in sync ──────


# party.role → (sig_*_status column, sig_*_signed_at column)
_DISINTERMENT_ROLE_COLUMNS: dict[str, tuple[str, str]] = {
    "funeral_home_director": (
        "sig_funeral_home",
        "sig_funeral_home_signed_at",
    ),
    "cemetery_rep": ("sig_cemetery", "sig_cemetery_signed_at"),
    "next_of_kin": ("sig_next_of_kin", "sig_next_of_kin_signed_at"),
    "manufacturer": ("sig_manufacturer", "sig_manufacturer_signed_at"),
}


def _map_party_status_to_sig_column(status: str) -> str:
    """Map native party status onto the legacy sig_* column vocabulary."""
    if status == "pending":
        return "not_sent"
    if status == "sent":
        return "sent"
    if status in ("viewed", "consented"):
        return "sent"  # legacy didn't distinguish these
    if status == "signed":
        return "signed"
    if status == "declined":
        return "declined"
    if status == "expired":
        return "expired"
    return "not_sent"


def sync_disinterment_case_status(
    db: Session, envelope_id: str
) -> None:
    """If this envelope is attached to a DisintermentCase, mirror party
    statuses into the legacy `sig_*` columns so code that still reads
    them sees the same truth as the envelope.

    Also drives the case's overall status when all four parties have
    signed (case.status → "signatures_complete") or any declines
    (case.status → "signatures_declined" — new status, see below).
    """
    # Import locally to avoid circular imports at package load time
    from app.models.disinterment_case import DisintermentCase

    case = (
        db.query(DisintermentCase)
        .filter_by(signature_envelope_id=envelope_id)
        .first()
    )
    if case is None:
        return

    envelope = _get_envelope(db, envelope_id)
    sig_any_declined = False
    sig_all_signed_or_skipped = True

    for party in envelope.parties:
        cols = _DISINTERMENT_ROLE_COLUMNS.get(party.role)
        if cols is None:
            continue
        status_col, signed_at_col = cols
        mapped = _map_party_status_to_sig_column(party.status)
        setattr(case, status_col, mapped)
        setattr(case, signed_at_col, party.signed_at)
        if mapped == "declined":
            sig_any_declined = True
        if mapped not in ("signed", "not_sent"):
            sig_all_signed_or_skipped = False

    now = datetime.now(timezone.utc)
    if envelope.status == "completed" and case.status == "signatures_pending":
        case.status = "signatures_complete"
    elif sig_any_declined and case.status == "signatures_pending":
        # Envelope.status will flip to declined; legacy flow didn't have
        # a "declined" case status so we keep it as signatures_pending
        # with individual sig_* showing declined. Admins see the
        # envelope status directly.
        pass
    case.updated_at = now
