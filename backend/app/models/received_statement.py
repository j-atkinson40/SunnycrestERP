"""Received statement models — funeral home side of cross-tenant billing."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ReceivedStatement(Base):
    __tablename__ = "received_statements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    from_tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    from_tenant_name: Mapped[str] = mapped_column(String(200), nullable=False)
    relationship_type: Mapped[str | None] = mapped_column(String(100), nullable=True, server_default="manufacturer_funeral_home")
    customer_statement_id: Mapped[str] = mapped_column(String(36), nullable=False)
    statement_period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    statement_period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0")
    new_charges: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0")
    payments_received: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0")
    balance_due: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0")
    invoice_count: Mapped[int] = mapped_column(Integer, server_default="0")
    statement_pdf_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(30), server_default="unread")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    dispute_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    payments = relationship("StatementPayment", back_populates="received_statement")


class StatementPayment(Base):
    __tablename__ = "statement_payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    received_statement_id: Mapped[str] = mapped_column(String(36), ForeignKey("received_statements.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    payment_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    acknowledged_by_manufacturer: Mapped[bool] = mapped_column(Boolean, server_default="false")
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    received_statement = relationship("ReceivedStatement", back_populates="payments")
    submitter = relationship("User", foreign_keys=[submitted_by])
