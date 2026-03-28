"""Add conditional pricing fields to products table.

Revision ID: r8_conditional_pricing
Revises: t1_data_migration_runs
Create Date: 2026-03-28
"""

from alembic import op
import sqlalchemy as sa

revision = "r8_conditional_pricing"
down_revision = "t1_data_migration_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # op.add_column is monkey-patched in env.py to be idempotent
    op.add_column(
        "products",
        sa.Column("price_without_our_product", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column(
            "is_call_office",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "has_conditional_pricing",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    # Add is_call_office to price_list_import_items
    op.add_column(
        "price_list_import_items",
        sa.Column(
            "is_call_office",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
def downgrade() -> None:
    op.drop_column("price_list_import_items", "is_call_office")
    op.drop_column("products", "has_conditional_pricing")
    op.drop_column("products", "is_call_office")
    op.drop_column("products", "price_without_our_product")
