"""Document delivery model — Phase D-7.

One row per send attempt across any channel. Captures:
  - who the recipient is (type + value + display name)
  - what content was sent (subject + body preview + template key)
  - where it went (channel + provider + provider_message_id)
  - whether it succeeded (status + error details + full provider_response)
  - what triggered the send (caller_* linkage columns)

Every email / SMS / future-channel send goes through `DeliveryService`
which writes rows here. Admin inbox at `/admin/documents/deliveries`
queries this table.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Status vocabulary ────────────────────────────────────────────────
# pending   — row created, not yet handed to provider
# sending   — in flight to provider (short window)
# sent      — provider accepted (message_id captured)
# delivered — provider confirmed delivery (requires webhook; future)
# bounced   — provider rejected after accepting (hard bounce)
# failed    — terminal failure (exhausted retries or non-retryable error)
# rejected  — pre-send rejection (e.g. SMS stub)
DELIVERY_STATUSES = {
    "pending",
    "sending",
    "sent",
    "delivered",
    "bounced",
    "failed",
    "rejected",
}


class DocumentDelivery(Base):
    __tablename__ = "document_deliveries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )

    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    recipient_type: Mapped[str] = mapped_column(String(32), nullable=False)
    recipient_value: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending"
    )
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    provider_response: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)

    retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    max_retries: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3
    )

    scheduled_for: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Source linkage — who/what triggered the send
    caller_module: Mapped[str | None] = mapped_column(
        String(256), nullable=True
    )
    caller_workflow_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("workflow_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    caller_workflow_step_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    caller_intelligence_execution_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("intelligence_executions.id", ondelete="SET NULL"),
        nullable=True,
    )
    caller_signature_envelope_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("signature_envelopes.id", ondelete="SET NULL"),
        nullable=True,
    )
    # V-1f: polymorphic attribution beyond the document_id FK. Lets a
    # send be attributed to any VaultItem (quote, compliance-expiry,
    # delivery, etc.) without needing a Document row. Most deliveries
    # continue to use `document_id` — this is additive, nullable.
    caller_vault_item_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("vault_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    # ── Relationships ─────────────────────────────────────────────
    # Use direct class reference for Document (canonical vs legacy
    # ambiguity) and string-name for single-registered models.
    from app.models.canonical_document import Document as _CanonDocument

    document = relationship(
        _CanonDocument,
        foreign_keys=[document_id],
    )
    # V-1f: optional companion relationship. Loaded on demand (lazy
    # select) since most callers access the row by id alone.
    caller_vault_item = relationship(
        "VaultItem",
        foreign_keys=[caller_vault_item_id],
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentDelivery id={self.id[:8]} channel={self.channel} "
            f"to={self.recipient_value} status={self.status}>"
        )
