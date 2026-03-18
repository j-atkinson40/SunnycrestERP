"""Add urn catalog fields (wilbert_sku, wholesale_cost, markup_percent) to products.

Revision ID: d7e8f9g0h1i2
Revises: c6d7e8f9g0h1
Create Date: 2026-03-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "d7e8f9g0h1i2"
down_revision = "c6d7e8f9g0h1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa_inspect(conn)

    prod_cols = [c["name"] for c in inspector.get_columns("products")]

    if "wilbert_sku" not in prod_cols:
        op.add_column(
            "products",
            sa.Column("wilbert_sku", sa.String(50), nullable=True),
        )
        op.create_index("ix_products_wilbert_sku", "products", ["wilbert_sku"])

    if "wholesale_cost" not in prod_cols:
        op.add_column(
            "products",
            sa.Column("wholesale_cost", sa.Numeric(12, 2), nullable=True),
        )

    if "markup_percent" not in prod_cols:
        op.add_column(
            "products",
            sa.Column("markup_percent", sa.Numeric(5, 2), nullable=True),
        )

    # source is a plain String(30), so 'wilbert_import' is already a valid value.
    # No enum migration needed.


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa_inspect(conn)

    prod_cols = [c["name"] for c in inspector.get_columns("products")]

    if "markup_percent" in prod_cols:
        op.drop_column("products", "markup_percent")
    if "wholesale_cost" in prod_cols:
        op.drop_column("products", "wholesale_cost")
    if "wilbert_sku" in prod_cols:
        op.drop_index("ix_products_wilbert_sku", table_name="products")
        op.drop_column("products", "wilbert_sku")
