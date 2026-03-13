"""Add created_by and modified_by to 9 tables

Revision ID: j4d5e6f7a8b9
Revises: i3c4d5e6f7a8
Create Date: 2026-03-13

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "j4d5e6f7a8b9"
down_revision = "i3c4d5e6f7a8"
branch_labels = None
depends_on = None

TABLES = [
    "companies",
    "users",
    "products",
    "product_categories",
    "product_price_tiers",
    "roles",
    "departments",
    "employee_profiles",
    "inventory_items",
]


def upgrade() -> None:
    for table in TABLES:
        op.add_column(
            table,
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        )
        op.add_column(
            table,
            sa.Column("modified_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        )


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, "modified_by")
        op.drop_column(table, "created_by")
