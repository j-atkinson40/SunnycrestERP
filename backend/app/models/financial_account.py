"""Financial account and reconciliation models."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric,
    String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
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
    # Plaid B-2 (r135): the feed back-reference — set when this statement
    # line was materialized from bank_transactions (B-3's populate-from-feed);
    # NULL for CSV-born rows. The removal hook finds matched lines through it.
    bank_transaction_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("bank_transactions.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
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


# ── Books Review Phase 2 Arc A-1b: durable non-destructive matching ──────────
# Migration r148_reconciliation_exceptions. See that file's docstring for the
# decided design (candidates key to the TRANSACTION; the exception carries no
# match_status copy; card form derives from candidate presence at display).


class ReconciliationMatchCandidate(Base):
    """A scored candidate for a reconciliation transaction. Keys to the
    TRANSACTION (not the exception), so auto-committed matches retain the audit
    of what else was considered. `rejection_reason` NULL = a viable/proposed
    candidate (ranked by `score`); non-NULL = a retained near-miss with its
    structured reason code + measured value in `rejection_detail`
    (e.g. {"days_diff": 6}). The scoring pass (A-2) populates these."""

    __tablename__ = "reconciliation_match_candidates"
    __table_args__ = (
        UniqueConstraint("reconciliation_transaction_id", "candidate_record_type",
                         "candidate_record_id", name="uq_recon_candidate_per_txn"),
        CheckConstraint(
            # Must match migration r148. AMOUNT_MISMATCH is the band-era gate (A-2):
            # in-band but beyond exact-match tolerance — the exact-amount ladder never
            # had it. NULL = a viable proposal.
            "rejection_reason IS NULL OR rejection_reason IN "
            "('OUTSIDE_DATE_WINDOW', 'DIRECTION_MISMATCH', 'ALREADY_CLAIMED', 'AMOUNT_MISMATCH')",
            name="ck_recon_candidate_rejection_reason",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    reconciliation_transaction_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("reconciliation_transactions.id", ondelete="CASCADE"),
        nullable=False, index=True)
    candidate_record_type: Mapped[str] = mapped_column(String(30), nullable=False)
    candidate_record_id: Mapped[str] = mapped_column(String(36), nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 = best
    rejection_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    rejection_detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ReconciliationException(Base):
    """A transaction that did NOT auto-commit and needs human attention. A
    workspace object: it carries identity, resolution state, and a flag link,
    but NOT a copy of the transaction's match_status — the source transaction is
    authority on whether the item is still open (queue build filters on it). The
    card form (ranked vs coding) is DERIVED from candidate presence at display,
    not stored here. Candidates are read through the transaction."""

    __tablename__ = "reconciliation_exceptions"
    __table_args__ = (
        UniqueConstraint("reconciliation_transaction_id", name="uq_recon_exception_per_txn"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    reconciliation_transaction_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("reconciliation_transactions.id", ondelete="CASCADE"),
        nullable=False, index=True)
    reconciliation_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("reconciliation_runs.id", ondelete="CASCADE"),
        nullable=False, index=True)
    # Flag/park link. FK DELIBERATELY ABSENT (not an oversight): the flag table is
    # built in Arc B (the workspace). Referential integrity here is UNENFORCED until
    # that migration adds the FK constraint — do not treat this id as guaranteed-valid
    # until then. Tracked: Arc B wires flag_id -> <flag_table>.id.
    flag_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # Resolution state (workspace record; NOT the transaction's match_status).
    # chosen_candidate_id FK DELIBERATELY ABSENT: a FK to reconciliation_match_candidates
    # would be circular (candidate -> txn <- exception -> candidate) and buys little; the
    # accepted candidate is resolvable via the transaction's candidate set. Unenforced by
    # design — set on resolve, read through the candidate set.
    chosen_candidate_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    resolved_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc))
