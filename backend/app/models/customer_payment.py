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


class CustomerPayment(Base):
    """Customer payment — applied across one or more invoices."""

    __tablename__ = "customer_payments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=False, index=True
    )
    payment_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    payment_method: Mapped[str] = mapped_column(
        String(30), nullable=False, default="check"
    )  # check, ach, credit_card, cash, wire
    reference_number: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sage_payment_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    qbo_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )

    # Audit
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

    # Relationships
    company = relationship("Company")
    customer = relationship("Customer")
    applications = relationship(
        "CustomerPaymentApplication", back_populates="payment"
    )
    creator = relationship("User", foreign_keys=[created_by])


class CustomerPaymentApplication(Base):
    """Maps a payment to one or more invoices."""

    __tablename__ = "customer_payment_applications"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    payment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customer_payments.id"), nullable=False, index=True
    )
    invoice_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("invoices.id"), nullable=False, index=True
    )
    amount_applied: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )

    payment = relationship("CustomerPayment", back_populates="applications")
    invoice = relationship("Invoice", back_populates="payment_applications")
