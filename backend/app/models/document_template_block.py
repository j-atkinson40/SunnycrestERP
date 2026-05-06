"""Document template block model — Phase D-10 (June 2026).

Block-based document authoring substrate. Each row is one block in a
template version. Top-level blocks have parent_block_id NULL; blocks
nested inside a conditional_wrapper have parent_block_id set.

The composer reads blocks ordered by position and emits Jinja per
block-kind. The block_kind string indexes into the in-memory registry
at `app.services.documents.block_registry`.
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


class DocumentTemplateBlock(Base):
    __tablename__ = "document_template_blocks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    template_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_template_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Block kind — matches a registration in
    # `app.services.documents.block_registry.BLOCK_REGISTRY`. String
    # rather than enum so new kinds can land via service code without
    # a schema migration.
    block_kind: Mapped[str] = mapped_column(String(64), nullable=False)

    # Position within the template version (top-level) OR within the
    # parent conditional_wrapper. Positions are not necessarily
    # contiguous; service-layer reorder normalizes them.
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    # Block-specific configuration. Shape is dictated by the block
    # kind's config_schema. Validated at write time by the registry.
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Jinja expression for conditional_wrapper blocks (e.g.,
    # "is_cremation == True"). NULL for unconditional blocks.
    condition: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Self-FK — when a block is a child of a conditional_wrapper,
    # parent_block_id points at the wrapper. ON DELETE CASCADE so
    # removing a wrapper cleans up its children atomically.
    parent_block_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("document_template_blocks.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    # Self-referential relationship for parent/children.
    parent = relationship(
        "DocumentTemplateBlock",
        remote_side=[id],
        back_populates="children",
    )
    children = relationship(
        "DocumentTemplateBlock",
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="DocumentTemplateBlock.position",
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentTemplateBlock id={self.id[:8]} kind={self.block_kind} "
            f"pos={self.position} parent={(self.parent_block_id or 'null')[:8]}>"
        )
