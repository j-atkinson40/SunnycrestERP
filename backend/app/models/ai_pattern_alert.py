"""AiPatternAlert — detected order/payment patterns for morning briefing."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AiPatternAlert(Base):
    __tablename__ = "ai_pattern_alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    pattern_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    master_company_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("company_entities.id"), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    surfaced_in_briefing: Mapped[bool] = mapped_column(Boolean, server_default="false")
    surfaced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed: Mapped[bool] = mapped_column(Boolean, server_default="false")
    dismissed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
