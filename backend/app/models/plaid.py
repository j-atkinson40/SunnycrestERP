"""Plaid banking substrate (B-1, r133) — plaid_integration_investigation.md §2.

THE CROWN-JEWEL DISCIPLINE (read before touching):

  * `PlaidItem.access_token_encrypted` holds FERNET CIPHERTEXT ONLY —
    written exclusively through `app.services.plaid.crypto.encrypt_token`.
    The anti-QBO pin (test_plaid_b1.py) asserts the stored value is not
    the raw token and round-trips through decrypt. The QBO integration's
    plaintext `Company.accounting_config` tokens + dead `*_encrypted`
    columns are the documented ANTI-precedent — never model on them.
  * The raw access token is NEVER a route response field, NEVER logged,
    NEVER passed to audit_service without `redact_for_audit`. Plaid API
    errors are logged by error_code/request_id — never wholesale bodies.
  * Every read is tenant-scoped INSIDE the query. Cross-tenant ids return
    404 indistinguishable from absent — bank data is the catastrophic
    isolation class; the pins land before any surface renders.

`BankTransaction.amount` is PLATFORM sign (positive = credit/deposit,
negative = debit) — matching `ReconciliationTransaction`. Plaid's sign is
inverted ONCE at ingest (B-2), nowhere else.
"""
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric,
    String, Text, text as sql_text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PlaidItem(Base):
    __tablename__ = "plaid_items"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'login_required', 'pending_expiration', "
            "'error', 'disconnected')",
            name="ck_plaid_items_status",
        ),
        Index("ux_plaid_items_item_id", "plaid_item_id", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    plaid_item_id: Mapped[str] = mapped_column(String(120), nullable=False)
    institution_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    institution_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    sync_cursor: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    accounts = relationship(
        "BankAccount", cascade="all, delete-orphan",
        order_by="BankAccount.name", lazy="selectin",
    )


class BankAccount(Base):
    __tablename__ = "bank_accounts"
    __table_args__ = (
        Index(
            "ux_bank_accounts_tenant_plaid_account",
            "tenant_id", "plaid_account_id", unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    plaid_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plaid_items.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    plaid_account_id: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    official_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    mask: Mapped[str | None] = mapped_column(String(4), nullable=True)
    account_type: Mapped[str] = mapped_column(String(32), nullable=False)
    account_subtype: Mapped[str | None] = mapped_column(String(48), nullable=True)
    current_balance: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    available_balance: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    # Session-1 cash wire: WHEN these numbers were true (link or last
    # sync refresh) — the surface states it; no balance pretends freshness.
    balance_as_of: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    financial_account_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("financial_accounts.id"), nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class BankTransaction(Base):
    __tablename__ = "bank_transactions"
    __table_args__ = (
        Index(
            "ux_bank_transactions_tenant_plaid_txn",
            "tenant_id", "plaid_transaction_id", unique=True,
        ),
        Index(
            "ix_bank_transactions_account_date",
            "bank_account_id", "transaction_date",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    bank_account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bank_accounts.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    plaid_transaction_id: Mapped[str] = mapped_column(String(120), nullable=False)
    pending_plaid_transaction_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    authorized_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    raw_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    plaid_category_primary: Mapped[str | None] = mapped_column(String(64), nullable=True)
    plaid_category_detailed: Mapped[str | None] = mapped_column(String(128), nullable=True)
    expense_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_pending: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class PlaidCategoryMapping(Base):
    """Plaid personal_finance_category → platform expense category.

    Two-tier: `tenant_id IS NULL` = platform-seeded default (B-2 seeds
    ~30 rows); a tenant row with the same `plaid_category` overrides.
    Detailed keys win over primary keys at resolve time (B-2's resolver).
    Unmapped stays honest NULL on the transaction — never silently
    confident.
    """
    __tablename__ = "plaid_category_mappings"
    __table_args__ = (
        Index(
            "ux_plaid_cat_map_platform", "plaid_category", unique=True,
            postgresql_where=sql_text("tenant_id IS NULL"),
        ),
        Index(
            "ux_plaid_cat_map_tenant", "tenant_id", "plaid_category",
            unique=True, postgresql_where=sql_text("tenant_id IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("companies.id"), nullable=True, index=True)
    plaid_category: Mapped[str] = mapped_column(String(128), nullable=False)
    expense_category: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
