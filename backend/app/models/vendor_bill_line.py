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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class VendorBillLine(Base):
    __tablename__ = "vendor_bill_lines"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    bill_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("vendor_bills.id"), nullable=False, index=True
    )
    po_line_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("purchase_order_lines.id"), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 3), nullable=True
    )
    unit_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    expense_category: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Relationships ---
    bill = relationship("VendorBill", back_populates="lines")
    po_line = relationship("PurchaseOrderLine")
