"""Journal entry models — entries, lines, templates, periods."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class JournalEntry(Base):
    __tablename__ = "journal_entries"
    __table_args__ = (UniqueConstraint("tenant_id", "entry_number", name="uq_je_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    entry_number: Mapped[str] = mapped_column(String(30), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default="draft")
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_reversal: Mapped[bool] = mapped_column(Boolean, server_default="false")
    reversal_of_entry_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reversal_scheduled: Mapped[bool] = mapped_column(Boolean, server_default="false")
    reversal_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    recurring_template_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    corrects_record_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    corrects_record_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    total_debits: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0")
    total_credits: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0")
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    posted_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    lines = relationship("JournalEntryLine", back_populates="entry", cascade="all, delete-orphan")


class JournalEntryLine(Base):
    __tablename__ = "journal_entry_lines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    journal_entry_id: Mapped[str] = mapped_column(String(36), ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    gl_account_id: Mapped[str] = mapped_column(String(36), nullable=False)
    gl_account_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    gl_account_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    debit_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0")
    credit_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    entry = relationship("JournalEntry", back_populates="lines")


class JournalEntryTemplate(Base):
    __tablename__ = "journal_entry_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    template_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    entry_type: Mapped[str] = mapped_column(String(20), nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    day_of_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    months_of_year: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    next_run_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_run_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    auto_post: Mapped[bool] = mapped_column(Boolean, server_default="false")
    auto_reverse: Mapped[bool] = mapped_column(Boolean, server_default="false")
    reverse_days_after: Mapped[int] = mapped_column(Integer, server_default="1")
    template_lines: Mapped[list] = mapped_column(JSONB, server_default="[]")
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AccountingPeriod(Base):
    __tablename__ = "accounting_periods"
    __table_args__ = (UniqueConstraint("tenant_id", "period_year", "period_month", name="uq_accounting_period"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default="open")
    closed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
