import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
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
    sent_at: Mapped[datetime | None] = mapped_column(
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

    # --- Relationships ---
    company = relationship("Company")
    vendor = relationship("Vendor")
    lines = relationship(
        "PurchaseOrderLine",
        back_populates="purchase_order",
        order_by="PurchaseOrderLine.sort_order",
    )
    creator = relationship("User", foreign_keys=[created_by])
