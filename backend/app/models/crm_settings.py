"""CrmSettings — per-tenant CRM feature toggles and health score thresholds."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CrmSettings(Base):
    __tablename__ = "crm_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, unique=True)

    pipeline_enabled: Mapped[bool] = mapped_column(Boolean, server_default="false")
    health_scoring_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    activity_log_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")

    at_risk_days_multiplier: Mapped[Decimal] = mapped_column(Numeric(4, 2), server_default="2.0")
    at_risk_payment_trend_days: Mapped[int] = mapped_column(Integer, server_default="7")
    at_risk_payment_threshold_days: Mapped[int] = mapped_column(Integer, server_default="30")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
