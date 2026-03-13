"""Expand company settings with financial and email fields

Revision ID: l6f7a8b9c0d1
Revises: k5e6f7a8b9c0
Create Date: 2026-03-13

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "l6f7a8b9c0d1"
down_revision = "k5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("tax_rate", sa.Numeric(5, 4), nullable=True))
    op.add_column(
        "companies",
        sa.Column("default_payment_terms", sa.String(50), nullable=True),
    )
    op.add_column(
        "companies", sa.Column("payment_terms_options", sa.Text(), nullable=True)
    )
    op.add_column(
        "companies", sa.Column("email_from_name", sa.String(200), nullable=True)
    )
    op.add_column(
        "companies", sa.Column("email_from_address", sa.String(255), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("companies", "email_from_address")
    op.drop_column("companies", "email_from_name")
    op.drop_column("companies", "payment_terms_options")
    op.drop_column("companies", "default_payment_terms")
    op.drop_column("companies", "tax_rate")
