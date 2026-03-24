"""Financial account and reconciliation models."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FinancialAccount(Base):
    __tablename__ = "financial_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)
    account_name: Mapped[str] = mapped_column(String(100), nullable=False)
    institution_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_four: Mapped[str | None] = mapped_column(String(4), nullable=True)
    gl_account_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    is_primary: Mapped[bool] = mapped_column(Boolean, server_default="false")
    last_reconciled_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_reconciled_balance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    last_reconciliation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    credit_limit: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    statement_closing_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    csv_date_column: Mapped[str | None] = mapped_column(String(50), nullable=True)
    csv_description_column: Mapped[str | None] = mapped_column(String(50), nullable=True)
    csv_amount_column: Mapped[str | None] = mapped_column(String(50), nullable=True)
    csv_debit_column: Mapped[str | None] = mapped_column(String(50), nullable=True)
    csv_credit_column: Mapped[str | None] = mapped_column(String(50), nullable=True)
    csv_balance_column: Mapped[str | None] = mapped_column(String(50), nullable=True)
    csv_date_format: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ReconciliationRun(Base):
    __tablename__ = "reconciliation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    financial_account_id: Mapped[str] = mapped_column(String(36), ForeignKey("financial_accounts.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), server_default="importing")
    statement_date: Mapped[date] = mapped_column(Date, nullable=False)
    statement_closing_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_statement_transactions: Mapped[int] = mapped_column(Integer, server_default="0")
    auto_cleared_count: Mapped[int] = mapped_column(Integer, server_default="0")
    suggested_count: Mapped[int] = mapped_column(Integer, server_default="0")
    unmatched_count: Mapped[int] = mapped_column(Integer, server_default="0")
    opening_balance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    platform_cleared_balance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    outstanding_checks_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0")
    outstanding_deposits_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0")
    adjustments_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0")
    difference: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0")
    confirmed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    csv_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    csv_row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    account = relationship("FinancialAccount", foreign_keys=[financial_account_id])
    transactions = relationship("ReconciliationTransaction", back_populates="run", cascade="all, delete-orphan")
    adjustments = relationship("ReconciliationAdjustment", cascade="all, delete-orphan")


class ReconciliationTransaction(Base):
    __tablename__ = "reconciliation_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    reconciliation_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    transaction_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    reference_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    raw_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    match_status: Mapped[str] = mapped_column(String(20), server_default="unmatched")
    match_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    matched_record_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    matched_record_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    match_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    run = relationship("ReconciliationRun", back_populates="transactions")


class ReconciliationAdjustment(Base):
    __tablename__ = "reconciliation_adjustments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    reconciliation_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("reconciliation_runs.id", ondelete="CASCADE"), nullable=False)
    adjustment_type: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_record_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_record_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
