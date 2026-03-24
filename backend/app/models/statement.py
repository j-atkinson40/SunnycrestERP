"""Billing statement models — templates, runs, customer statements."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class StatementTemplate(Base):
    __tablename__ = "statement_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("companies.id"), nullable=True)
    template_key: Mapped[str] = mapped_column(String(100), nullable=False)
    template_name: Mapped[str] = mapped_column(String(200), nullable=False)
    customer_type: Mapped[str] = mapped_column(String(50), nullable=False, server_default="all")
    is_default_for_type: Mapped[bool] = mapped_column(Boolean, server_default="false")
    sections: Mapped[list] = mapped_column(JSONB, server_default='["header","period","account_number","balance_summary","invoice_list","aging_summary","payment_instructions","custom_message"]')
    logo_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    show_aging_summary: Mapped[bool] = mapped_column(Boolean, server_default="true")
    show_account_number: Mapped[bool] = mapped_column(Boolean, server_default="true")
    show_payment_instructions: Mapped[bool] = mapped_column(Boolean, server_default="true")
    remittance_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class StatementRun(Base):
    __tablename__ = "statement_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "statement_period_month", "statement_period_year", name="uq_statement_run_period"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    statement_period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    statement_period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="draft")
    total_customers: Mapped[int] = mapped_column(Integer, server_default="0")
    digital_count: Mapped[int] = mapped_column(Integer, server_default="0")
    mail_count: Mapped[int] = mapped_column(Integer, server_default="0")
    none_count: Mapped[int] = mapped_column(Integer, server_default="0")
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    initiated_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    custom_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    zip_file_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    zip_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    statements = relationship("CustomerStatement", back_populates="run")
    initiator = relationship("User", foreign_keys=[initiated_by])


class CustomerStatement(Base):
    __tablename__ = "customer_statements"
    __table_args__ = (
        UniqueConstraint("run_id", "customer_id", name="uq_customer_statement_per_run"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("statement_runs.id"), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"), nullable=False, index=True)
    statement_period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    statement_period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    delivery_method: Mapped[str] = mapped_column(String(20), nullable=False)
    template_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    previous_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0")
    new_charges: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0")
    payments_received: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0")
    balance_due: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0")
    invoice_ids: Mapped[list] = mapped_column(JSONB, server_default="[]")
    invoice_count: Mapped[int] = mapped_column(Integer, server_default="0")
    statement_pdf_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    statement_pdf_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="pending")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_sent_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    send_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Agent flagging and review
    flagged: Mapped[bool] = mapped_column(Boolean, server_default="false")
    flag_reasons: Mapped[list] = mapped_column(JSONB, server_default="[]")
    review_status: Mapped[str] = mapped_column(String(20), server_default="pending")
    reviewed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Cross-tenant delivery fields
    cross_tenant_delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cross_tenant_received_statement_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    payment_received_cross_tenant: Mapped[bool] = mapped_column(Boolean, server_default="false")
    payment_amount_cross_tenant: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    payment_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    run = relationship("StatementRun", back_populates="statements")
    customer = relationship("Customer", foreign_keys=[customer_id])
