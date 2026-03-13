import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class VendorPaymentApplication(Base):
    __tablename__ = "vendor_payment_applications"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    payment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("vendor_payments.id"), nullable=False, index=True
    )
    bill_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("vendor_bills.id"), nullable=False, index=True
    )
    amount_applied: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # --- Relationships ---
    payment = relationship("VendorPayment", back_populates="applications")
    bill = relationship("VendorBill")
