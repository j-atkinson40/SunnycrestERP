"""CrmOpportunity — sales pipeline opportunity tracking."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CrmOpportunity(Base):
    __tablename__ = "crm_opportunities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    master_company_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("company_entities.id"), nullable=True)

    prospect_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    prospect_city: Mapped[str | None] = mapped_column(String(200), nullable=True)
    prospect_state: Mapped[str | None] = mapped_column(String(100), nullable=True)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    stage: Mapped[str] = mapped_column(String(30), nullable=False, server_default="prospect")
    estimated_annual_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    expected_close_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    lost_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    master_company = relationship("CompanyEntity", foreign_keys=[master_company_id])
    assigned_user = relationship("User", foreign_keys=[assigned_to])
