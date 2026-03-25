"""Finance charge models."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FinanceChargeRun(Base):
    __tablename__ = "finance_charge_runs"
    __table_args__ = (UniqueConstraint("tenant_id", "charge_year", "charge_month", name="uq_fc_run_month"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    run_number: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default="calculated")
    charge_month: Mapped[int] = mapped_column(Integer, nullable=False)
    charge_year: Mapped[int] = mapped_column(Integer, nullable=False)
    calculation_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Settings snapshot
    rate_applied: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    balance_basis: Mapped[str] = mapped_column(String(30), nullable=False)
    compound: Mapped[bool] = mapped_column(Boolean, nullable=False)
    grace_days: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    minimum_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # Summary
    total_customers_evaluated: Mapped[int] = mapped_column(Integer, server_default="0")
    total_customers_charged: Mapped[int] = mapped_column(Integer, server_default="0")
    total_customers_forgiven: Mapped[int] = mapped_column(Integer, server_default="0")
    total_customers_below_minimum: Mapped[int] = mapped_column(Integer, server_default="0")
    total_amount_calculated: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0")
    total_amount_forgiven: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0")
    total_amount_posted: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0")
    calculated_by: Mapped[str] = mapped_column(String(20), server_default="agent")
    posted_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    items = relationship("FinanceChargeItem", back_populates="run", cascade="all, delete-orphan")


class FinanceChargeItem(Base):
    __tablename__ = "finance_charge_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("finance_charge_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"), nullable=False, index=True)
    eligible_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    rate_applied: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    calculated_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    minimum_applied: Mapped[bool] = mapped_column(Boolean, server_default="false")
    final_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    prior_finance_charge_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0")
    aging_snapshot: Mapped[dict] = mapped_column(JSONB, server_default="{}")
    review_status: Mapped[str] = mapped_column(String(20), server_default="pending")
    reviewed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    forgiveness_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    posted: Mapped[bool] = mapped_column(Boolean, server_default="false")
    invoice_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    journal_entry_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    run = relationship("FinanceChargeRun", back_populates="items")
    customer = relationship("Customer", foreign_keys=[customer_id])
