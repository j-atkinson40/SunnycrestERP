"""Add customer_type column to customers and backfill from notes.

Revision ID: r14_customer_type
Revises: r13_driver_status_updates
Create Date: 2026-03-30
"""

from alembic import op
import sqlalchemy as sa

revision = "r14_customer_type"
down_revision = "r13_driver_status_updates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # op.add_column is monkey-patched in env.py to be idempotent
    op.add_column(
        "customers",
        sa.Column("customer_type", sa.String(30), nullable=True),
    )

    # Backfill from notes field where data_migration_service stored it
    op.execute(
        """
        UPDATE customers
        SET customer_type = 'funeral_home'
        WHERE notes LIKE '%Type: funeral_home%'
          AND customer_type IS NULL
        """
    )
    op.execute(
        """
        UPDATE customers
        SET customer_type = 'contractor'
        WHERE notes LIKE '%Type: contractor%'
          AND customer_type IS NULL
        """
    )
    op.execute(
        """
        UPDATE customers
        SET customer_type = 'other'
        WHERE customer_type IS NULL
        """
    )

    # Index for fast filtering by type
    op.create_index(
        "idx_customers_type",
        "customers",
        ["company_id", "customer_type"],
    )


def downgrade() -> None:
    op.drop_index("idx_customers_type", table_name="customers")
    op.drop_column("customers", "customer_type")
