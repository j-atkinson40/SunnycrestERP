"""MoCPlanningItem — the personal build-backlog on the maps (r123).

Typed planning items (feature / workflow / focus / document) with status,
PERSONAL-SCOPED to the owning platform user, living at the established map
tiers (platform_default vertical-less; vertical_default with a vertical).
`created_artifact_slug` is the unused forward hook for the future
plan→artifact conversion.
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
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

PLANNING_KINDS = ("feature", "workflow", "focus", "document")
PLANNING_STATUSES = ("planned", "in_progress", "done")


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MoCPlanningItem(Base):
    __tablename__ = "moc_planning_item"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("platform_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    vertical: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("verticals.slug", ondelete="RESTRICT"),
        nullable=True,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="planned"
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_artifact_slug: Mapped[str | None] = mapped_column(
        String(96), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        CheckConstraint(
            "scope IN ('platform_default', 'vertical_default')",
            name="ck_moc_planning_item_scope",
        ),
        CheckConstraint(
            "("
            "(scope = 'platform_default' AND vertical IS NULL)"
            " OR (scope = 'vertical_default' AND vertical IS NOT NULL)"
            ")",
            name="ck_moc_planning_item_scope_vertical",
        ),
        CheckConstraint(
            "kind IN ('feature', 'workflow', 'focus', 'document')",
            name="ck_moc_planning_item_kind",
        ),
        CheckConstraint(
            "status IN ('planned', 'in_progress', 'done')",
            name="ck_moc_planning_item_status",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<MoCPlanningItem({self.kind}: {self.title!r}, {self.status}, "
            f"owner={self.owner_user_id})>"
        )
