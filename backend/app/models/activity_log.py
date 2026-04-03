"""ActivityLog — CRM activity tracking for company entities."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    master_company_id: Mapped[str] = mapped_column(String(36), ForeignKey("company_entities.id"), nullable=False)
    contact_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("contacts.id"), nullable=True)
    logged_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    activity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    is_system_generated: Mapped[bool] = mapped_column(Boolean, server_default="false")

    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)

    follow_up_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    follow_up_assigned_to: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    follow_up_completed: Mapped[bool] = mapped_column(Boolean, server_default="false")
    follow_up_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    related_order_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    related_invoice_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    related_legacy_proof_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    source: Mapped[str] = mapped_column(String(20), server_default="manual")
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    master_company = relationship("CompanyEntity", foreign_keys=[master_company_id])
    contact = relationship("Contact", foreign_keys=[contact_id])
    logged_by_user = relationship("User", foreign_keys=[logged_by])
    assigned_user = relationship("User", foreign_keys=[follow_up_assigned_to])
