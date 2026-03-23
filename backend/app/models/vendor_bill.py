import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class VendorBill(Base):
    __tablename__ = "vendor_bills"

    # --- Standard fields ---
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )

    # --- Core fields ---
    number: Mapped[str] = mapped_column(String(50), nullable=False)  # BILL-YYYY-####
    vendor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("vendors.id"), nullable=False, index=True
    )
    vendor_invoice_number: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    po_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("purchase_orders.id"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft"
    )  # draft|pending|approved|paid|partial|void
    bill_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    due_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

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
    amount_paid: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )

    # --- Other ---
    payment_terms: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(30), server_default="manual")
    received_statement_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    attachment_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    attachment_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    qbo_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )
    quickbooks_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    quickbooks_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

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

    @property
    def balance_remaining(self) -> Decimal:
        return self.total - self.amount_paid

    # --- Relationships ---
    company = relationship("Company")
    vendor = relationship("Vendor")
    purchase_order = relationship("PurchaseOrder")
    lines = relationship(
        "VendorBillLine",
        back_populates="bill",
        order_by="VendorBillLine.sort_order",
    )
    approver = relationship("User", foreign_keys=[approved_by])
    creator = relationship("User", foreign_keys=[created_by])
