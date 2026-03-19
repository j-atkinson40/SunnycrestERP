"""Add conditional pricing to bundles, import items, and charge library.

Revision ID: c3d4e5f6g7h9
Revises: b2c3d4e5f6g8
Create Date: 2026-03-19
"""

from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6g7h9"
down_revision = "b2c3d4e5f6g8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # product_bundles — conditional pricing fields
    op.add_column(
        "product_bundles",
        sa.Column("has_conditional_pricing", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "product_bundles",
        sa.Column("standalone_price", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "product_bundles",
        sa.Column("with_vault_price", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "product_bundles",
        sa.Column(
            "vault_qualifier_categories",
            sa.Text(),
            server_default='["burial_vault","urn_vault"]',
            nullable=False,
        ),
    )

    # price_list_import_items — conditional pricing extraction fields
    op.add_column(
        "price_list_import_items",
        sa.Column("extracted_price_with_vault", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "price_list_import_items",
        sa.Column("extracted_price_standalone", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "price_list_import_items",
        sa.Column("has_conditional_pricing", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "price_list_import_items",
        sa.Column("is_bundle_price_variant", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "price_list_import_items",
        sa.Column(
            "parent_bundle_import_item_id",
            sa.String(36),
            sa.ForeignKey("price_list_import_items.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "price_list_import_items",
        sa.Column("price_variant_type", sa.String(20), nullable=True),
    )

    # charge_library_items — conditional pricing fields
    op.add_column(
        "charge_library_items",
        sa.Column("has_conditional_pricing", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "charge_library_items",
        sa.Column("with_vault_price", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "charge_library_items",
        sa.Column("standalone_price", sa.Numeric(12, 2), nullable=True),
    )


def downgrade() -> None:
    # charge_library_items
    op.drop_column("charge_library_items", "standalone_price")
    op.drop_column("charge_library_items", "with_vault_price")
    op.drop_column("charge_library_items", "has_conditional_pricing")

    # price_list_import_items
    op.drop_column("price_list_import_items", "price_variant_type")
    op.drop_column("price_list_import_items", "parent_bundle_import_item_id")
    op.drop_column("price_list_import_items", "is_bundle_price_variant")
    op.drop_column("price_list_import_items", "has_conditional_pricing")
    op.drop_column("price_list_import_items", "extracted_price_standalone")
    op.drop_column("price_list_import_items", "extracted_price_with_vault")

    # product_bundles
    op.drop_column("product_bundles", "vault_qualifier_categories")
    op.drop_column("product_bundles", "with_vault_price")
    op.drop_column("product_bundles", "standalone_price")
    op.drop_column("product_bundles", "has_conditional_pricing")
