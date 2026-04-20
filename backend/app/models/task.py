"""Task — Phase 5 (deferred from Phase 4).

Generic task entity: title + description + assignee + priority +
due date + status + polymorphic link to a related vault entity.

Intentionally minimal. Task infrastructure was deferred from Phase 4
per approved plan so the entity could land alongside the Triage
Workspace (Phase 5) where task UX conventions naturally emerge.

Status lifecycle: `open → in_progress → (blocked →) done | cancelled`.
Soft-delete via `is_active=False`; hard delete is an admin-only path.

`metadata_json` holds arbitrary per-task flags (e.g. reassignment
history, triage-session provenance). Never overload it with first-
class fields — use columns.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignee_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Priority as varchar so we can evolve without a migration. Enum
    # values: low | normal | high | urgent.
    priority: Mapped[str] = mapped_column(
        String(16), nullable=False, default="normal"
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_datetime: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Status lifecycle: open | in_progress | blocked | done | cancelled
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="open"
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    related_entity_type: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    related_entity_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    metadata_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
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

    assignee = relationship("User", foreign_keys=[assignee_user_id])
    created_by = relationship("User", foreign_keys=[created_by_user_id])


# Valid enum-as-string values. Import from this module rather than
# hardcoding elsewhere.
TASK_PRIORITIES: tuple[str, ...] = ("low", "normal", "high", "urgent")
TASK_STATUSES: tuple[str, ...] = (
    "open",
    "in_progress",
    "blocked",
    "done",
    "cancelled",
)


__all__ = ["Task", "TASK_PRIORITIES", "TASK_STATUSES"]


# Silence unused-import warnings for the `Integer` alias — retained
# in case a future column needs it without re-importing.
_ = Integer
