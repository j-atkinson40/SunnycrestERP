"""UserSpaceAffinity — Workflow Arc Phase 8e.1.

Per-user, per-space topical affinity signal that feeds the command
bar ranking layer. One row per (user, space, target_type, target_id).
Written on deliberate user intent (pin click, PinStar toggle,
command-bar navigate, pinned-nav direct visit); read once per
command_bar/query call to compute boost factors.

Purpose-limitation: this data is used ONLY for command bar ranking
in Phase 8e.1. Any future use (briefings recommendations, dashboard
personalization) requires a separate scope-expansion audit.
Documented in `SPACES_ARCHITECTURE.md` §9.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


TargetType = Literal["nav_item", "saved_view", "entity_record", "triage_queue"]


class UserSpaceAffinity(Base):
    __tablename__ = "user_space_affinity"

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Matches SpaceConfig.space_id ("sp_<12 hex>"). No FK — spaces
    # live in JSONB on User.preferences. Cascade-on-space-delete is
    # handled at the service layer (crud.delete_space).
    space_id: Mapped[str] = mapped_column(String(36), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(255), nullable=False)
    visit_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    last_visited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("NOW()"),
    )

    __table_args__ = (
        PrimaryKeyConstraint(
            "user_id",
            "space_id",
            "target_type",
            "target_id",
            name="pk_user_space_affinity",
        ),
        CheckConstraint(
            "target_type IN ('nav_item', 'saved_view', "
            "'entity_record', 'triage_queue')",
            name="ck_user_space_affinity_target_type",
        ),
        Index(
            "ix_user_space_affinity_user_space_active",
            "user_id",
            "space_id",
            postgresql_where=text("visit_count > 0"),
        ),
        Index(
            "ix_user_space_affinity_user_recent_active",
            "user_id",
            text("last_visited_at DESC"),
            postgresql_where=text("visit_count > 0"),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<UserSpaceAffinity user={self.user_id[:8]} "
            f"space={self.space_id} "
            f"{self.target_type}:{self.target_id} "
            f"visits={self.visit_count}>"
        )
