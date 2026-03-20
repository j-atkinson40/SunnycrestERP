"""Accounting enhancements — customer_accounting_mappings table + new columns.

Revision ID: z7a8b9c0d1e2
Revises: z6a7b8c9d0e1
Create Date: 2026-03-20

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = "z7a8b9c0d1e2"
down_revision = "z6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── New table: customer_accounting_mappings ─────────────────────
    op.create_table(
        "customer_accounting_mappings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "customer_id",
            sa.String(36),
            sa.ForeignKey("customers.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("qbo_customer_id", sa.String(100), nullable=True),
        sa.Column("qbd_customer_id", sa.String(100), nullable=True),
        sa.Column("sage_customer_id", sa.String(100), nullable=True),
        # auto_matched | manually_matched | created_by_sync
        sa.Column("match_method", sa.String(30), nullable=True),
        sa.Column("match_confidence", sa.Numeric(3, 2), nullable=True),
        sa.Column("matched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # ── New columns on accounting_connections ───────────────────────
    op.add_column(
        "accounting_connections",
        sa.Column(
            "connection_attempt_count",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "accounting_connections",
        sa.Column("income_account_mappings", JSONB, nullable=True),
    )
    op.add_column(
        "accounting_connections",
        sa.Column("csv_column_mappings", JSONB, nullable=True),
    )
    op.add_column(
        "accounting_connections",
        sa.Column(
            "customer_match_completed",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("accounting_connections", "customer_match_completed")
    op.drop_column("accounting_connections", "csv_column_mappings")
    op.drop_column("accounting_connections", "income_account_mappings")
    op.drop_column("accounting_connections", "connection_attempt_count")
    op.drop_table("customer_accounting_mappings")
