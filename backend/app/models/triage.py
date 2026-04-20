"""Triage session + snooze models — Phase 5.

Two tables:

  TriageSession — user's active or completed triage session through
      a queue. `current_item_id` allows resume; per-session counters
      drive the "X of Y processed" progress indicator.

  TriageSnooze — generic entity-type-agnostic snooze. Any triage
      queue can write one. Scheduler sweeps on (wake_at, woken_at IS
      NULL) to un-snooze; triage engine filters out active snoozes
      when picking `next_item`.

Queue CONFIGS live in vault_items (item_type="triage_queue_config",
metadata_json.triage_queue_config). No table for configs — per the
audit's recommendation + Phase 2's saved-view precedent.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TriageSession(Base):
    __tablename__ = "triage_sessions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    queue_id: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    items_processed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    items_approved_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    items_rejected_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    items_snoozed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    current_item_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    # Opaque per-queue cursor state — used by queue implementations
    # that want to remember a position in their item stream. Generic
    # JSONB so each queue can shape its own.
    cursor_meta: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )


class TriageSnooze(Base):
    __tablename__ = "triage_snoozes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    queue_id: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    wake_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Set when the snooze resolves — either by scheduler sweep hitting
    # `wake_at <= now()` or by explicit un-snooze. Partial unique
    # index (ix_triage_snoozes_active) enforces "one active snooze
    # per (user, queue, entity)".
    woken_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


__all__ = ["TriageSession", "TriageSnooze"]
