"""Add subcategories and price tiers

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Subcategories: add parent_id to product_categories ---
    op.add_column(
        "product_categories",
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("product_categories.id"), nullable=True),
    )
    op.create_index("ix_product_categories_parent_id", "product_categories", ["parent_id"])

    # Drop old unique constraint and replace with parent-scoped one
    op.drop_constraint("uq_product_category_name_company", "product_categories", type_="unique")
    op.create_unique_constraint(
        "uq_product_category_name_company_parent",
        "product_categories",
        ["name", "company_id", "parent_id"],
    )

    # --- Price tiers table ---
    op.create_table(
        "product_price_tiers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False, index=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("min_quantity", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("label", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("product_id", "min_quantity", name="uq_price_tier_product_min_qty"),
    )


def downgrade() -> None:
    op.drop_table("product_price_tiers")

    op.drop_constraint("uq_product_category_name_company_parent", "product_categories", type_="unique")
    op.create_unique_constraint(
        "uq_product_category_name_company",
        "product_categories",
        ["name", "company_id"],
    )
    op.drop_index("ix_product_categories_parent_id", "product_categories")
    op.drop_column("product_categories", "parent_id")
