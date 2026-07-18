"""Plaid B-1 — the four-table foundation (plaid_integration_investigation.md §2).

`plaid_items` — one row per tenant↔institution connection. The access token
is FERNET CIPHERTEXT ONLY (`access_token_encrypted` — actually fed, unlike
the QBO dead columns; the anti-QBO round-trip pin enforces it). The sync
cursor lives here per-item (B-2's transactions/sync loop).

`bank_accounts` — per item; credit subtypes first-class; the nullable
`financial_account_id` FK is the hand-off to the existing reconciliation
substrate (linking is an explicit tenant-admin step).

`bank_transactions` — the durable feed (the D-3 alignment verdict: the
run-scoped `reconciliation_transactions` cannot own feed identity).
Unique `(tenant_id, plaid_transaction_id)` is the idempotency spine.
Amounts stored in PLATFORM sign (positive=credit/deposit) — the one
deliberate negation happens at ingest (B-2), never downstream.

`plaid_category_mappings` — TenantGLMapping-patterned two-tier map
(tenant_id NULL = platform default, tenant row overrides). Seeded in B-2.

Revision ID: r133_plaid_foundation
Revises: r132_moc_job
Create Date: 2026-07-18
"""

from alembic import op
import sqlalchemy as sa

revision = "r133_plaid_foundation"
down_revision = "r132_moc_job"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plaid_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id", sa.String(36),
            sa.ForeignKey("companies.id"), nullable=False, index=True,
        ),
        sa.Column("plaid_item_id", sa.String(120), nullable=False),
        sa.Column("institution_id", sa.String(64), nullable=True),
        sa.Column("institution_name", sa.String(200), nullable=True),
        sa.Column("access_token_encrypted", sa.Text, nullable=False),
        sa.Column("sync_cursor", sa.Text, nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'login_required', 'pending_expiration', "
            "'error', 'disconnected')",
            name="ck_plaid_items_status",
        ),
    )
    op.create_index(
        "ux_plaid_items_item_id", "plaid_items", ["plaid_item_id"], unique=True,
    )

    op.create_table(
        "bank_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id", sa.String(36),
            sa.ForeignKey("companies.id"), nullable=False, index=True,
        ),
        sa.Column(
            "plaid_item_id", sa.String(36),
            sa.ForeignKey("plaid_items.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("plaid_account_id", sa.String(120), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("official_name", sa.String(300), nullable=True),
        sa.Column("mask", sa.String(4), nullable=True),
        sa.Column("account_type", sa.String(32), nullable=False),
        sa.Column("account_subtype", sa.String(48), nullable=True),
        sa.Column("current_balance", sa.Numeric(14, 2), nullable=True),
        sa.Column("available_balance", sa.Numeric(14, 2), nullable=True),
        sa.Column(
            "financial_account_id", sa.String(36),
            sa.ForeignKey("financial_accounts.id"), nullable=True,
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ux_bank_accounts_tenant_plaid_account", "bank_accounts",
        ["tenant_id", "plaid_account_id"], unique=True,
    )

    op.create_table(
        "bank_transactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id", sa.String(36),
            sa.ForeignKey("companies.id"), nullable=False, index=True,
        ),
        sa.Column(
            "bank_account_id", sa.String(36),
            sa.ForeignKey("bank_accounts.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("plaid_transaction_id", sa.String(120), nullable=False),
        sa.Column("pending_plaid_transaction_id", sa.String(120), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("transaction_date", sa.Date, nullable=False),
        sa.Column("authorized_date", sa.Date, nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("raw_description", sa.Text, nullable=True),
        sa.Column("plaid_category_primary", sa.String(64), nullable=True),
        sa.Column("plaid_category_detailed", sa.String(128), nullable=True),
        sa.Column("expense_category", sa.String(100), nullable=True),
        sa.Column("is_pending", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ux_bank_transactions_tenant_plaid_txn", "bank_transactions",
        ["tenant_id", "plaid_transaction_id"], unique=True,
    )
    op.create_index(
        "ix_bank_transactions_account_date", "bank_transactions",
        ["bank_account_id", "transaction_date"],
    )

    op.create_table(
        "plaid_category_mappings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id", sa.String(36),
            sa.ForeignKey("companies.id"), nullable=True, index=True,
        ),
        sa.Column("plaid_category", sa.String(128), nullable=False),
        sa.Column("expense_category", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Two partial uniques: NULL tenant_id rows are the platform tier
    # (Postgres treats NULLs as distinct in a plain unique index).
    op.create_index(
        "ux_plaid_cat_map_platform", "plaid_category_mappings",
        ["plaid_category"], unique=True,
        postgresql_where=sa.text("tenant_id IS NULL"),
    )
    op.create_index(
        "ux_plaid_cat_map_tenant", "plaid_category_mappings",
        ["tenant_id", "plaid_category"], unique=True,
        postgresql_where=sa.text("tenant_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ux_plaid_cat_map_tenant", table_name="plaid_category_mappings")
    op.drop_index("ux_plaid_cat_map_platform", table_name="plaid_category_mappings")
    op.drop_table("plaid_category_mappings")
    op.drop_index("ix_bank_transactions_account_date", table_name="bank_transactions")
    op.drop_index("ux_bank_transactions_tenant_plaid_txn", table_name="bank_transactions")
    op.drop_table("bank_transactions")
    op.drop_index("ux_bank_accounts_tenant_plaid_account", table_name="bank_accounts")
    op.drop_table("bank_accounts")
    op.drop_index("ux_plaid_items_item_id", table_name="plaid_items")
    op.drop_table("plaid_items")
