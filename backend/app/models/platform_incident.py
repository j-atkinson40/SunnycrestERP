"""Platform incident model for the self-repair system."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PlatformIncident(Base):
    __tablename__ = "platform_incidents"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )

    # Classification
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default="medium"
    )
    fingerprint: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )

    # What happened
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    stack_trace: Mapped[str | None] = mapped_column(Text, nullable=True)
    context: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    # Response
    resolution_tier: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    resolution_status: Mapped[str] = mapped_column(
        String(20), default="pending", index=True
    )
    resolution_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution_duration_seconds: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    # Learning
    was_repeat: Mapped[bool] = mapped_column(Boolean, default=False)
    previous_incident_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("platform_incidents.id"),
        nullable=True,
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

    # Self-referential relationship
    previous_incident = relationship(
        "PlatformIncident", remote_side=[id], foreign_keys=[previous_incident_id]
    )

    __table_args__ = (
        Index("idx_platform_incidents_created", created_at.desc()),
    )

    def __repr__(self) -> str:
        return (
            f"<PlatformIncident {self.id[:8]} "
            f"category={self.category} severity={self.severity} "
            f"status={self.resolution_status}>"
        )
