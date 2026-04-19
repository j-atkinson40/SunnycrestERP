"""Native e-signature models — Phase D-4.

Four tables:
  SignatureEnvelope  — a signing request (lifecycle state machine)
  SignatureParty     — one signer (with unique signer_token for public link)
  SignatureField     — fields each party fills in
  SignatureEvent     — append-only audit log

Runs in parallel with DocuSign in D-4. D-5 migrates flows.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Envelope states ─────────────────────────────────────────────────
# draft → sent → in_progress → completed
#                           ↘  declined
#                           ↘  voided
#                           ↘  expired
ENVELOPE_STATUSES = {
    "draft",
    "sent",
    "in_progress",
    "completed",
    "declined",
    "expired",
    "voided",
}

# ── Party states ────────────────────────────────────────────────────
# pending → sent → viewed → consented → signed
#                                    ↘  declined
#                                    ↘  expired
PARTY_STATUSES = {
    "pending",
    "sent",
    "viewed",
    "consented",
    "signed",
    "declined",
    "expired",
}


class SignatureEnvelope(Base):
    __tablename__ = "signature_envelopes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    routing_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="sequential"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft"
    )
    document_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    voided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    voided_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    certificate_document_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    # ── Relationships ─────────────────────────────────────────────
    parties = relationship(
        "SignatureParty",
        back_populates="envelope",
        cascade="all, delete-orphan",
        order_by="SignatureParty.signing_order",
        foreign_keys="SignatureParty.envelope_id",
    )
    fields = relationship(
        "SignatureField",
        back_populates="envelope",
        cascade="all, delete-orphan",
        foreign_keys="SignatureField.envelope_id",
    )
    events = relationship(
        "SignatureEvent",
        back_populates="envelope",
        cascade="all, delete-orphan",
        order_by="SignatureEvent.sequence_number",
        foreign_keys="SignatureEvent.envelope_id",
    )

    def __repr__(self) -> str:
        return (
            f"<SignatureEnvelope id={self.id[:8]} subject={self.subject!r} "
            f"status={self.status}>"
        )


class SignatureParty(Base):
    __tablename__ = "signature_parties"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    envelope_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("signature_envelopes.id", ondelete="CASCADE"),
        nullable=False,
    )
    signing_order: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    signer_token: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending"
    )

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    viewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consented_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    signed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    declined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decline_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    signing_ip_address: Mapped[str | None] = mapped_column(
        String(45), nullable=True
    )
    signing_user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    signature_type: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )
    signature_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    typed_signature_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    notification_sent_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    last_notification_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    envelope = relationship(
        "SignatureEnvelope",
        back_populates="parties",
        foreign_keys=[envelope_id],
    )
    fields = relationship(
        "SignatureField",
        back_populates="party",
        cascade="all, delete-orphan",
        foreign_keys="SignatureField.party_id",
    )

    def __repr__(self) -> str:
        return (
            f"<SignatureParty id={self.id[:8]} role={self.role} "
            f"status={self.status}>"
        )


class SignatureField(Base):
    __tablename__ = "signature_fields"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    envelope_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("signature_envelopes.id", ondelete="CASCADE"),
        nullable=False,
    )
    party_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("signature_parties.id", ondelete="CASCADE"),
        nullable=False,
    )
    # signature | initial | date | typed_name | checkbox | text
    field_type: Mapped[str] = mapped_column(String(16), nullable=False)
    anchor_string: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    position_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[float | None] = mapped_column(Float, nullable=True)
    height: Mapped[float | None] = mapped_column(Float, nullable=True)
    # D-5: fine-tune anchor placement without re-rendering the template.
    # Offsets are in `anchor_units` (default "points"); signature image
    # origin is placed at (anchor_x + anchor_x_offset, anchor_y + anchor_y_offset).
    anchor_x_offset: Mapped[float | None] = mapped_column(
        Float, nullable=True, default=0.0
    )
    anchor_y_offset: Mapped[float | None] = mapped_column(
        Float, nullable=True, default=0.0
    )
    anchor_units: Mapped[str | None] = mapped_column(
        String(16), nullable=True, default="points"
    )
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    default_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)

    envelope = relationship(
        "SignatureEnvelope",
        back_populates="fields",
        foreign_keys=[envelope_id],
    )
    party = relationship(
        "SignatureParty",
        back_populates="fields",
        foreign_keys=[party_id],
    )

    def __repr__(self) -> str:
        return (
            f"<SignatureField id={self.id[:8]} type={self.field_type} "
            f"party={self.party_id[:8]}>"
        )


class SignatureEvent(Base):
    """Append-only audit log. Never mutated once written.

    Enforcement: service layer has no update/delete operations on this
    table. DB-level immutability (triggers / policies) is future work.
    """

    __tablename__ = "signature_events"
    __table_args__ = (
        UniqueConstraint(
            "envelope_id",
            "sequence_number",
            name="ix_sig_event_envelope_seq",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    envelope_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("signature_envelopes.id", ondelete="CASCADE"),
        nullable=False,
    )
    party_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("signature_parties.id", ondelete="SET NULL"),
        nullable=True,
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_party_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("signature_parties.id", ondelete="SET NULL"),
        nullable=True,
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45), nullable=True
    )
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    envelope = relationship(
        "SignatureEnvelope",
        back_populates="events",
        foreign_keys=[envelope_id],
    )

    def __repr__(self) -> str:
        return (
            f"<SignatureEvent env={self.envelope_id[:8]} "
            f"seq={self.sequence_number} type={self.event_type}>"
        )
