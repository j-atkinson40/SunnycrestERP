"""RingCentral call extraction — AI-extracted order data from call transcripts."""

import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, String, Text, Time
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RingCentralCallExtraction(Base):
    __tablename__ = "ringcentral_call_extractions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    call_log_id: Mapped[str] = mapped_column(String(36), ForeignKey("ringcentral_call_log.id"), nullable=False)
    master_company_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("company_entities.id"), nullable=True)

    # Extracted fields
    funeral_home_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    deceased_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    vault_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    vault_size: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cemetery_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    burial_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    burial_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    grave_location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    special_requests: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Confidence per field
    confidence_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Missing fields list
    missing_fields: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Call metadata
    call_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    call_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    urgency: Mapped[str | None] = mapped_column(String(20), nullable=True)
    suggested_callback: Mapped[bool] = mapped_column(Boolean, default=False)

    # Status
    draft_order_created: Mapped[bool] = mapped_column(Boolean, default=False)
    draft_order_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("sales_orders.id"), nullable=True)
    reviewed_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    call_log = relationship("RingCentralCallLog", back_populates="extraction")
    draft_order = relationship("SalesOrder", foreign_keys=[draft_order_id])
    company_entity = relationship("CompanyEntity", foreign_keys=[master_company_id])
