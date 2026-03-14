"""add accounting_provider and accounting_config to companies

Revision ID: v6w7x8y9z0a1
Revises: u5v6w7x8y9z0
Create Date: 2026-03-14

"""
from alembic import op
import sqlalchemy as sa

revision = "v6w7x8y9z0a1"
down_revision = "u5v6w7x8y9z0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column(
            "accounting_provider",
            sa.String(50),
            nullable=True,
            server_default="sage_csv",
        ),
    )
    op.add_column(
        "companies",
        sa.Column("accounting_config", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("companies", "accounting_config")
    op.drop_column("companies", "accounting_provider")
