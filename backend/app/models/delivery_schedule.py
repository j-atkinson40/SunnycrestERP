"""DeliverySchedule — per-tenant per-date dispatch schedule state.

Phase B Session 1. One row per (company_id, schedule_date) pair, lazy-
created on first access. Represents the dispatcher's commitment state
for a day's deliveries:

  - `state='draft'` — schedule is being composed; edits are cheap, no
    commitment.
  - `state='finalized'` — dispatcher or auto-finalize job has locked
    the day. Drivers can rely on it. Subsequent edits to any delivery
    whose `requested_date` matches this row's `schedule_date` revert
    state → draft, stamping `last_reverted_at` + `last_revert_reason`.

The state doesn't cascade to the deliveries themselves — only the
schedule row carries state. Deliveries retain their own status field
(pending/scheduled/completed/etc) tracking fulfillment, not commitment.

Auto-finalize: a scheduler job running at 1pm tenant-local finds
draft rows for today, checks if any Focus is open for scheduling that
day (Focus-open deferral), and stamps `state='finalized' +
auto_finalized=True` if no deferral. Hard cutoff 1:15pm — never defer
past that.

See r49_dispatch_schedule_state migration for schema.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DeliverySchedule(Base):
    __tablename__ = "delivery_schedules"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "schedule_date",
            name="uq_delivery_schedules_company_date",
        ),
        CheckConstraint(
            "state IN ('draft', 'finalized')",
            name="ck_delivery_schedules_state",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    schedule_date: Mapped[date] = mapped_column(Date, nullable=False)

    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft"
    )  # draft | finalized

    finalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finalized_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    auto_finalized: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    last_reverted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_revert_reason: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    company = relationship("Company")
    finalized_by = relationship("User", foreign_keys=[finalized_by_user_id])
