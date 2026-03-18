"""Add catalog builder fields to products and product_substitution_rules table.

Revision ID: c6d7e8f9g0h1
Revises: b5c6d7e8f9g0
Create Date: 2026-03-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect
import uuid

revision = "c6d7e8f9g0h1"
down_revision = "b5c6d7e8f9g0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa_inspect(conn)

    # Add fields to products table
    prod_cols = [c["name"] for c in inspector.get_columns("products")]
    if "pricing_type" not in prod_cols:
        op.add_column("products", sa.Column("pricing_type", sa.String(20), server_default="sale"))
    if "rental_unit" not in prod_cols:
        op.add_column("products", sa.Column("rental_unit", sa.String(30), nullable=True))
    if "default_quantity" not in prod_cols:
        op.add_column("products", sa.Column("default_quantity", sa.Integer, nullable=True))
    if "source" not in prod_cols:
        op.add_column("products", sa.Column("source", sa.String(30), server_default="manual"))
    if "is_inventory_tracked" not in prod_cols:
        op.add_column("products", sa.Column("is_inventory_tracked", sa.Boolean, server_default="true"))
    if "product_line" not in prod_cols:
        op.add_column("products", sa.Column("product_line", sa.String(100), nullable=True))
    if "variant_type" not in prod_cols:
        op.add_column("products", sa.Column("variant_type", sa.String(50), nullable=True))

    # Create product_substitution_rules table
    tables = [t for t in inspector.get_table_names()]
    if "product_substitution_rules" not in tables:
        op.create_table(
            "product_substitution_rules",
            sa.Column("id", sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4())),
            sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
            sa.Column("rule_name", sa.String(255), nullable=False),
            sa.Column("trigger_field", sa.String(50), nullable=False),
            sa.Column("trigger_value", sa.String(50), nullable=False),
            sa.Column("substitute_out_product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
            sa.Column("substitute_in_product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
            sa.Column("applies_to", sa.String(30), nullable=False, server_default="order_suggestions"),
            sa.Column("is_active", sa.Boolean, server_default="true"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )


def downgrade() -> None:
    op.drop_table("product_substitution_rules")
    for col in ["variant_type", "product_line", "is_inventory_tracked", "source",
                 "default_quantity", "rental_unit", "pricing_type"]:
        op.drop_column("products", col)
