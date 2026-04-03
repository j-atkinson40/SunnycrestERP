"""ManufacturerCompanyProfile — account health and order pattern stats for customer companies."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ManufacturerCompanyProfile(Base):
    __tablename__ = "manufacturer_company_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    master_company_id: Mapped[str] = mapped_column(String(36), ForeignKey("company_entities.id", ondelete="CASCADE"), nullable=False, unique=True)

    avg_days_between_orders: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    last_order_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    order_count_12mo: Mapped[int] = mapped_column(Integer, server_default="0")
    order_count_all_time: Mapped[int] = mapped_column(Integer, server_default="0")
    total_revenue_12mo: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0")
    total_revenue_all_time: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0")
    most_ordered_vault_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    most_ordered_vault_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    avg_days_to_pay_recent: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    avg_days_to_pay_prior: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)

    health_score: Mapped[str] = mapped_column(String(20), server_default="unknown")
    health_reasons: Mapped[list] = mapped_column(JSONB, server_default="'[]'")
    health_last_calculated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_briefed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    preferred_contact_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    master_company = relationship("CompanyEntity", foreign_keys=[master_company_id])
