"""Inter-licensee pricing models."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InterLicenseePriceList(Base):
    __tablename__ = "inter_licensee_price_lists"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_inter_licensee_price_list_tenant"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), server_default="Inter-Licensee Transfer Pricing")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    visible_to_all_licensees: Mapped[bool] = mapped_column(Boolean, server_default="true")
    pricing_method: Mapped[str] = mapped_column(String(20), server_default="fixed")
    retail_adjustment_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), server_default="0")
    auto_created: Mapped[bool] = mapped_column(Boolean, server_default="false")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    items = relationship("InterLicenseePriceListItem", back_populates="price_list", cascade="all, delete-orphan")


class InterLicenseePriceListItem(Base):
    __tablename__ = "inter_licensee_price_list_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    price_list_id: Mapped[str] = mapped_column(String(36), ForeignKey("inter_licensee_price_lists.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    product_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    unit: Mapped[str] = mapped_column(String(50), server_default="each")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    price_list = relationship("InterLicenseePriceList", back_populates="items")


class TransferPriceRequest(Base):
    __tablename__ = "transfer_price_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    transfer_id: Mapped[str] = mapped_column(String(36), ForeignKey("licensee_transfers.id"), nullable=False, index=True)
    requesting_tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    area_tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), server_default="pending")
    items_requested: Mapped[list] = mapped_column(JSONB, server_default="[]")
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    responded_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    response_items: Mapped[list] = mapped_column(JSONB, server_default="[]")
    response_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
