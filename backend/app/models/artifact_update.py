"""Offered updates — publishes + offers (Focus Variations V-2, r121).

The software-update model's two records:

- **ArtifactPublish** — one row per explicit "Publish update" on a default
  (patch notes + the release's own delta). A publish with no downstream
  inheritors still records the release — the boundary exists regardless.
- **ArtifactUpdateOffer** — one row per (publish × downstream target).
  Carries the per-target derived diff (from THAT target's pin) + the
  status lifecycle: pending → accepted | declined; a newer publish marks
  prior pending/declined offers `superseded` and creates a fresh offer
  from the target's CURRENT pin (the chain-collapse rule — never stepwise).

LEVEL-GENERIC: `artifact_type` / `target_kind` discriminate; V-2 ships
'focus_core' → 'focus_template'. Slug-keyed identities (C-2.1.2 canon).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ArtifactPublish(Base):
    __tablename__ = "artifact_publishes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_slug: Mapped[str] = mapped_column(String(96), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    patch_notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    derived_diff: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class ArtifactUpdateOffer(Base):
    __tablename__ = "artifact_update_offers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    publish_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("artifact_publishes.id", ondelete="CASCADE"),
        nullable=False,
    )
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_slug: Mapped[str] = mapped_column(String(96), nullable=False)
    source_version_from: Mapped[int] = mapped_column(Integer, nullable=False)
    source_version_to: Mapped[int] = mapped_column(Integer, nullable=False)
    target_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    target_slug: Mapped[str] = mapped_column(String(96), nullable=False)
    target_vertical: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    patch_notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    derived_diff: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'accepted', 'declined', 'superseded')",
            name="ck_artifact_update_offers_status",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ArtifactUpdateOffer({self.source_slug} v{self.source_version_from}"
            f"→v{self.source_version_to} → {self.target_slug}, {self.status})>"
        )
