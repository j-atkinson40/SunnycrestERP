"""Plaid B-2 — the reconciliation↔feed back-reference (flagged pull-forward).

The investigation placed `reconciliation_transactions.bank_transaction_id`
in B-3 (populate-from-feed). B-2's REMOVED-WHILE-MATCHED hook needs it
now: when Plaid retracts a transaction, the sync must find any statement
line materialized from it — an unlinked feed can't honor retractions of
matched money. Nullable FK; CSV-born rows simply never set it.

Revision ID: r135_recon_bank_txn_link
Revises: r134_qbo_credential_purge
Create Date: 2026-07-18
"""

from alembic import op
import sqlalchemy as sa

revision = "r135_recon_bank_txn_link"
down_revision = "r134_qbo_credential_purge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "reconciliation_transactions",
        sa.Column(
            "bank_transaction_id", sa.String(36),
            sa.ForeignKey("bank_transactions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_recon_txn_bank_transaction", "reconciliation_transactions",
        ["bank_transaction_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_recon_txn_bank_transaction", table_name="reconciliation_transactions")
    op.drop_column("reconciliation_transactions", "bank_transaction_id")
