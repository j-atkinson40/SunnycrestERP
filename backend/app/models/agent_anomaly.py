"""Agent anomaly — normalized anomaly records for accounting agent jobs."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AgentAnomaly(Base):
    __tablename__ = "agent_anomalies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_job_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_run_step_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agent_run_steps.id"), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    anomaly_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolved_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    job = relationship("AgentJob", foreign_keys=[agent_job_id])
    step = relationship("AgentRunStep", foreign_keys=[agent_run_step_id])
    resolver = relationship("User", foreign_keys=[resolved_by])
