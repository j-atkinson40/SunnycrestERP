"""TaskRoutingRule — three-tier task routing per task_type_key.

v1 task substrate B3 §7.8. Three-tier resolver (platform_default →
vertical_default → tenant). First-match-wins at READ time.

Two routing modes ship in v1:
  • direct_user — fixed assignee_user_id; resolver returns that user.
  • round_robin — load-distributes across permission-holding users in
                  the tenant.

Forward-compat: `routing_config` JSONB carries v2 escalation_chain /
capacity_aware mode parameters when those modes ship.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TaskRoutingRule(Base):
    __tablename__ = "task_routing_rules"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    vertical: Mapped[str | None] = mapped_column(String(32), nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True,
    )
    task_type_key: Mapped[str] = mapped_column(String(64), nullable=False)
    routing_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    target_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_permission_key: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    routing_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


ROUTING_SCOPES: tuple[str, ...] = (
    "platform_default",
    "vertical_default",
    "tenant",
)
ROUTING_MODES: tuple[str, ...] = ("direct_user", "round_robin")


__all__ = ["TaskRoutingRule", "ROUTING_SCOPES", "ROUTING_MODES"]
