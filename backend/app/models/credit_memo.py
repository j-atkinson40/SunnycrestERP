"""Credit memo + customer credit ledger — the exceptions arc.

A CreditMemo is the first-class credit document the census found absent:
a correction against a specific invoice, reason REQUIRED (the
forgive-with-reason standard), born POSTED — creation IS issuance, the
same law as the finance-charge invoice (there is no draft stage, so the
draft-inert question never arises). AR moves once, at issuance, as the
negative through the Session-Two chokepoint.

CustomerCreditEntry is the pocket's ledger: every exit from
customer.credit_balance (apply onto an invoice, or a recorded
disbursement) leaves a row. The pocket stops being a silent accumulator.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

CREDIT_MEMO_STATUSES = ("posted", "void")
CREDIT_ENTRY_KINDS = ("apply", "disburse")


class CreditMemo(Base):
    __tablename__ = "credit_memos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"), nullable=False, index=True)
    invoice_id: Mapped[str] = mapped_column(String(36), ForeignKey("invoices.id"), nullable=False, index=True)
    number: Mapped[str] = mapped_column(String(50), nullable=False)  # CM-YYYY-####
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="posted")
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    invoice = relationship("Invoice")
    customer = relationship("Customer")


class CustomerCreditEntry(Base):
    __tablename__ = "customer_credit_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"), nullable=False, index=True)
    invoice_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("invoices.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # apply | disburse
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
