import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        UniqueConstraint(
            "number", "company_id", name="uq_po_number_company"
        ),
    )

    # --- Standard fields ---
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )

    # --- Core fields ---
    number: Mapped[str] = mapped_column(String(50), nullable=False)  # PO-YYYY-####
    vendor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("vendors.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft"
    )  # draft|sent|partial|received|closed|cancelled
    order_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    expected_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    shipping_address: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Amounts ---
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )

    # --- Other ---
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    shipping_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0")

    # --- Approval ---
    requires_approval: Mapped[bool] = mapped_column(Boolean, server_default="false")
    approval_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    submitted_for_approval_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Delivery ---
    expected_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivered_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # --- Three-way match ---
    match_status: Mapped[str] = mapped_column(String(20), server_default="pending_receipt")
    match_variance_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    match_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Audit trail ---
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    modified_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    modified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Relationships ---
    company = relationship("Company")
    vendor = relationship("Vendor")
    lines = relationship(
        "PurchaseOrderLine",
        back_populates="purchase_order",
        order_by="PurchaseOrderLine.sort_order",
    )
    creator = relationship("User", foreign_keys=[created_by])
    receipts = relationship("PurchaseOrderReceipt", back_populates="purchase_order")


class PurchaseOrderReceipt(Base):
    __tablename__ = "purchase_order_receipts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    purchase_order_id: Mapped[str] = mapped_column(String(36), ForeignKey("purchase_orders.id"), nullable=False, index=True)
    receipt_number: Mapped[str] = mapped_column(String(30), nullable=False)
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    received_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), server_default="complete")
    has_shortage: Mapped[bool] = mapped_column(Boolean, server_default="false")
    has_overage: Mapped[bool] = mapped_column(Boolean, server_default="false")
    has_damage: Mapped[bool] = mapped_column(Boolean, server_default="false")
    has_wrong_items: Mapped[bool] = mapped_column(Boolean, server_default="false")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    purchase_order = relationship("PurchaseOrder", back_populates="receipts")
    lines = relationship("PurchaseOrderReceiptLine", cascade="all, delete-orphan")


class PurchaseOrderReceiptLine(Base):
    __tablename__ = "purchase_order_receipt_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    receipt_id: Mapped[str] = mapped_column(String(36), ForeignKey("purchase_order_receipts.id", ondelete="CASCADE"), nullable=False)
    po_line_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("purchase_order_lines.id"), nullable=True)
    quantity_received: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    quantity_expected: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    condition: Mapped[str] = mapped_column(String(20), server_default="good")
    condition_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_paths: Mapped[list] = mapped_column(JSONB, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PurchaseOrderDocument(Base):
    __tablename__ = "purchase_order_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    purchase_order_id: Mapped[str] = mapped_column(String(36), ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    document_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploaded_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
