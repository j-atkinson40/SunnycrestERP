"""Licensee transfer models."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LicenseeTransfer(Base):
    __tablename__ = "licensee_transfers"
    __table_args__ = (
        UniqueConstraint("home_tenant_id", "transfer_number", name="uq_transfer_number"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    transfer_number: Mapped[str] = mapped_column(String(30), nullable=False)
    # Parties
    home_tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    area_tenant_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("companies.id"), nullable=True, index=True)
    area_licensee_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    area_licensee_contact: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_platform_transfer: Mapped[bool] = mapped_column(Boolean, server_default="true")
    # Status
    status: Mapped[str] = mapped_column(String(30), server_default="pending")
    # Source order
    source_order_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # Funeral details
    funeral_home_customer_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    funeral_home_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    deceased_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    service_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Cemetery
    cemetery_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cemetery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    cemetery_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cemetery_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    cemetery_county: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cemetery_zip: Mapped[str | None] = mapped_column(String(10), nullable=True)
    cemetery_place_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Hard FK link to cemeteries table (when cemetery is in system)
    cemetery_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("cemeteries.id"), nullable=True
    )
    # Items
    transfer_items: Mapped[list] = mapped_column(JSONB, server_default="[]")
    special_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Timing
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Billing chain
    area_order_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    area_invoice_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    home_vendor_bill_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    home_passthrough_invoice_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # Pricing
    area_charge_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    markup_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), server_default="0")
    passthrough_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # Decline/cancel
    decline_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Audit
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    notifications = relationship("TransferNotification", back_populates="transfer")


class TransferNotification(Base):
    __tablename__ = "transfer_notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    transfer_id: Mapped[str] = mapped_column(String(36), ForeignKey("licensee_transfers.id"), nullable=False, index=True)
    recipient_tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(30), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    transfer = relationship("LicenseeTransfer", back_populates="notifications")
