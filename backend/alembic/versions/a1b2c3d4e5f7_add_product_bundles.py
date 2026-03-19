"""Add product_bundles and product_bundle_components tables.

Revision ID: a1b2c3d4e5f7
Revises: z4a5b6c7d8e9
Create Date: 2026-03-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "a1b2c3d4e5f7"
down_revision = "z4a5b6c7d8e9"
branch_labels = None
depends_on = None


def _table_exists(conn, table_name: str) -> bool:
    inspector = sa_inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    conn = op.get_bind()

    # ── product_bundles ──
    if not _table_exists(conn, "product_bundles"):
        op.create_table(
            "product_bundles",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column("sku", sa.String(50), nullable=True),
            sa.Column("price", sa.Numeric(10, 2), nullable=True),
            sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
            sa.Column("sort_order", sa.Integer, server_default=sa.text("0")),
            sa.Column("source", sa.String(30), server_default=sa.text("'manual'")),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("modified_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    # ── product_bundle_components ──
    if not _table_exists(conn, "product_bundle_components"):
        op.create_table(
            "product_bundle_components",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("bundle_id", sa.String(36), sa.ForeignKey("product_bundles.id"), nullable=False, index=True),
            sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False, index=True),
            sa.Column("quantity", sa.Integer, server_default=sa.text("1")),
            sa.Column("sort_order", sa.Integer, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("bundle_id", "product_id", name="uq_bundle_product"),
        )


def downgrade() -> None:
    op.drop_table("product_bundle_components")
    op.drop_table("product_bundles")
