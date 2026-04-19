"""Cross-tenant document sharing models — Phase D-6.

Two tables:
  DocumentShare       — one row per (document, target_tenant) grant.
                        `revoked_at = NULL` means currently active.
  DocumentShareEvent  — append-only audit log of share state changes.

Lifecycle:
  granted → (accessed)* → revoked
              ↑ logged but status unchanged

Permission model (D-6): read-only. Target tenants can download the
document via a presigned R2 URL, but cannot edit, annotate, or
re-share. Future phases may add comment / download-only / etc.

Enforcement:
- Grant requires an active PlatformTenantRelationship between owner
  and target (either direction — relationships are logically
  bidirectional from a sharing perspective).
- Revocation is future-access-only. The row stays; `revoked_at` is
  set. Already-downloaded copies are outside our control.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class DocumentShare(Base):
    __tablename__ = "document_shares"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    owner_company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    permission: Mapped[str] = mapped_column(
        String(32), nullable=False, default="read"
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    granted_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    revoked_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoke_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # What service created the share — used for audit filtering + for
    # identifying auto-created shares vs manual admin grants.
    source_module: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )

    # ── Relationships ─────────────────────────────────────────────
    # Use direct class reference because `Document` is ambiguous in the
    # SQLAlchemy registry (legacy + canonical both use the name).
    from app.models.canonical_document import Document as _CanonDocument

    document = relationship(
        _CanonDocument,
        foreign_keys=[document_id],
    )
    owner_company = relationship(
        "Company", foreign_keys=[owner_company_id]
    )
    target_company = relationship(
        "Company", foreign_keys=[target_company_id]
    )
    events = relationship(
        "DocumentShareEvent",
        back_populates="share",
        cascade="all, delete-orphan",
        order_by="DocumentShareEvent.created_at",
        foreign_keys="DocumentShareEvent.share_id",
    )

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

    def __repr__(self) -> str:
        state = "active" if self.is_active else "revoked"
        return (
            f"<DocumentShare doc={self.document_id[:8]} "
            f"target={self.target_company_id[:8]} {state}>"
        )


class DocumentShareEvent(Base):
    """Append-only audit trail for share lifecycle. Never mutated after
    write — service layer contract, enforced via test."""

    __tablename__ = "document_share_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    share_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_shares.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    # granted | revoked | accessed | export_downloaded
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_company_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45), nullable=True
    )
    meta_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    share = relationship(
        "DocumentShare",
        back_populates="events",
        foreign_keys=[share_id],
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentShareEvent share={self.share_id[:8]} "
            f"type={self.event_type}>"
        )
