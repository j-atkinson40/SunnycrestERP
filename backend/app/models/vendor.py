import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Vendor(Base):
    __tablename__ = "vendors"
    __table_args__ = (
        UniqueConstraint(
            "account_number", "company_id", name="uq_vendor_account_company"
        ),
    )

    # --- Standard fields ---
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    modified_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    # --- Core info ---
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    account_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    fax: Mapped[str | None] = mapped_column(String(30), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # --- Address ---
    address_line1: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str | None] = mapped_column(
        String(100), nullable=True, default="US"
    )

    # --- Purchasing info ---
    payment_terms: Mapped[str | None] = mapped_column(String(50), nullable=True)
    vendor_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    minimum_order: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )

    # --- Other ---
    tax_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_1099_vendor: Mapped[bool] = mapped_column(Boolean, server_default="false")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- CRM master entity link ---
    master_company_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("company_entities.id"), nullable=True)

    # --- Sage sync ---
    sage_vendor_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # --- QuickBooks sync ---
    quickbooks_vendor_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quickbooks_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quickbooks_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Relationships ---
    company = relationship("Company")
    contacts = relationship(
        "VendorContact",
        back_populates="vendor",
        order_by="VendorContact.is_primary.desc()",
    )
    vendor_notes = relationship(
        "VendorNote",
        back_populates="vendor",
        order_by="VendorNote.created_at.desc()",
    )
