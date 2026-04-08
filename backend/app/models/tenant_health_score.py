"""Tenant health score model for the self-repair system."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TenantHealthScore(Base):
    __tablename__ = "tenant_health_scores"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), nullable=False, unique=True
    )

    # Overall score
    score: Mapped[str] = mapped_column(String(20), default="unknown")

    # Component scores
    api_health: Mapped[str] = mapped_column(String(20), default="unknown")
    auth_health: Mapped[str] = mapped_column(String(20), default="unknown")
    data_health: Mapped[str] = mapped_column(String(20), default="unknown")
    background_job_health: Mapped[str] = mapped_column(
        String(20), default="unknown"
    )

    # Incident stats
    open_incident_count: Mapped[int] = mapped_column(Integer, default=0)
    last_incident_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_healthy_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Explanation
    reasons: Mapped[list | None] = mapped_column(JSONB, default=list)

    last_calculated: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("idx_tenant_health_score", "score"),
    )

    def __repr__(self) -> str:
        return (
            f"<TenantHealthScore tenant={self.tenant_id[:8]}... "
            f"score={self.score} open={self.open_incident_count}>"
        )
