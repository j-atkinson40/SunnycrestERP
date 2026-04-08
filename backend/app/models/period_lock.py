"""Period lock — prevents financial writes to closed accounting periods."""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PeriodLock(Base):
    __tablename__ = "period_locks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    locked_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    locked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    lock_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_job_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agent_jobs.id"), nullable=True)
    unlocked_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    unlocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    locker = relationship("User", foreign_keys=[locked_by])
    unlocker = relationship("User", foreign_keys=[unlocked_by])
    agent_job = relationship("AgentJob", foreign_keys=[agent_job_id])
