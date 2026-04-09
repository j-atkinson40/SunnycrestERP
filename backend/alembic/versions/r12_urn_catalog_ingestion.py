"""Urn catalog ingestion — add dimensions, type, descriptions to urn_products.

Revision ID: r12_urn_catalog_ingestion
Revises: r11_urn_sales
Create Date: 2026-04-09
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "r12_urn_catalog_ingestion"
down_revision = "r11_urn_sales"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- urn_products: new catalog fields ---
    op.add_column("urn_products", sa.Column("height", sa.String(50), nullable=True))
    op.add_column("urn_products", sa.Column("width_or_diameter", sa.String(50), nullable=True))
    op.add_column("urn_products", sa.Column("depth", sa.String(50), nullable=True))
    op.add_column("urn_products", sa.Column("cubic_inches", sa.Integer(), nullable=True))
    op.add_column("urn_products", sa.Column("product_type", sa.String(50), nullable=True))
    op.add_column("urn_products", sa.Column("companion_of_sku", sa.String(100), nullable=True))
    op.add_column("urn_products", sa.Column("wilbert_description", sa.Text(), nullable=True))
    op.add_column("urn_products", sa.Column("wilbert_long_description", sa.Text(), nullable=True))
    op.add_column("urn_products", sa.Column("color_name", sa.String(200), nullable=True))
    op.add_column("urn_products", sa.Column("catalog_page", sa.Integer(), nullable=True))
    op.add_column("urn_products", sa.Column("r2_image_key", sa.String(500), nullable=True))

    op.create_index("ix_urn_products_product_type", "urn_products", ["product_type"])
    op.create_index("ix_urn_products_companion_of_sku", "urn_products", ["companion_of_sku"])

    # --- urn_catalog_sync_logs: new audit fields ---
    op.add_column("urn_catalog_sync_logs", sa.Column("sync_type", sa.String(20), nullable=True))
    op.add_column("urn_catalog_sync_logs", sa.Column("pdf_filename", sa.String(500), nullable=True))
    op.add_column("urn_catalog_sync_logs", sa.Column("products_skipped", sa.Integer(), server_default="0"))


def downgrade() -> None:
    op.drop_column("urn_catalog_sync_logs", "products_skipped")
    op.drop_column("urn_catalog_sync_logs", "pdf_filename")
    op.drop_column("urn_catalog_sync_logs", "sync_type")

    op.drop_index("ix_urn_products_companion_of_sku", table_name="urn_products")
    op.drop_index("ix_urn_products_product_type", table_name="urn_products")

    op.drop_column("urn_products", "r2_image_key")
    op.drop_column("urn_products", "catalog_page")
    op.drop_column("urn_products", "color_name")
    op.drop_column("urn_products", "wilbert_long_description")
    op.drop_column("urn_products", "wilbert_description")
    op.drop_column("urn_products", "companion_of_sku")
    op.drop_column("urn_products", "product_type")
    op.drop_column("urn_products", "cubic_inches")
    op.drop_column("urn_products", "depth")
    op.drop_column("urn_products", "width_or_diameter")
    op.drop_column("urn_products", "height")
