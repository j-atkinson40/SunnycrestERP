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


def _column_exists(table: str, column: str) -> bool:
    """Check if a column already exists (makes migration idempotent)."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    return result.fetchone() is not None


def _table_exists(table: str) -> bool:
    """Check if a table exists."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = :table"
        ),
        {"table": table},
    )
    return result.fetchone() is not None


def _fk_exists(constraint_name: str) -> bool:
    """Check if a foreign key constraint exists."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE constraint_name = :name AND constraint_type = 'FOREIGN KEY'"
        ),
        {"name": constraint_name},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    # product_bundles — conditional pricing fields
    if not _column_exists("product_bundles", "has_conditional_pricing"):
        op.add_column(
            "product_bundles",
            sa.Column("has_conditional_pricing", sa.Boolean(), server_default="false", nullable=False),
        )
    if not _column_exists("product_bundles", "standalone_price"):
        op.add_column(
            "product_bundles",
            sa.Column("standalone_price", sa.Numeric(10, 2), nullable=True),
        )
    if not _column_exists("product_bundles", "with_vault_price"):
        op.add_column(
            "product_bundles",
            sa.Column("with_vault_price", sa.Numeric(10, 2), nullable=True),
        )
    if not _column_exists("product_bundles", "vault_qualifier_categories"):
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
    if not _column_exists("price_list_import_items", "extracted_price_with_vault"):
        op.add_column(
            "price_list_import_items",
            sa.Column("extracted_price_with_vault", sa.Numeric(12, 2), nullable=True),
        )
    if not _column_exists("price_list_import_items", "extracted_price_standalone"):
        op.add_column(
            "price_list_import_items",
            sa.Column("extracted_price_standalone", sa.Numeric(12, 2), nullable=True),
        )
    if not _column_exists("price_list_import_items", "has_conditional_pricing"):
        op.add_column(
            "price_list_import_items",
            sa.Column("has_conditional_pricing", sa.Boolean(), server_default="false", nullable=False),
        )
    if not _column_exists("price_list_import_items", "is_bundle_price_variant"):
        op.add_column(
            "price_list_import_items",
            sa.Column("is_bundle_price_variant", sa.Boolean(), server_default="false", nullable=False),
        )
    if not _column_exists("price_list_import_items", "parent_bundle_import_item_id"):
        op.add_column(
            "price_list_import_items",
            sa.Column("parent_bundle_import_item_id", sa.String(36), nullable=True),
        )
    if not _fk_exists("fk_import_item_parent"):
        op.create_foreign_key(
            "fk_import_item_parent",
            "price_list_import_items",
            "price_list_import_items",
            ["parent_bundle_import_item_id"],
            ["id"],
        )
    if not _column_exists("price_list_import_items", "price_variant_type"):
        op.add_column(
            "price_list_import_items",
            sa.Column("price_variant_type", sa.String(20), nullable=True),
        )

    # charge_library_items — conditional pricing fields (table may not exist yet)
    if _table_exists("charge_library_items"):
        if not _column_exists("charge_library_items", "has_conditional_pricing"):
            op.add_column(
                "charge_library_items",
                sa.Column("has_conditional_pricing", sa.Boolean(), server_default="false", nullable=False),
            )
        if not _column_exists("charge_library_items", "with_vault_price"):
            op.add_column(
                "charge_library_items",
                sa.Column("with_vault_price", sa.Numeric(12, 2), nullable=True),
            )
        if not _column_exists("charge_library_items", "standalone_price"):
            op.add_column(
                "charge_library_items",
                sa.Column("standalone_price", sa.Numeric(12, 2), nullable=True),
            )


def downgrade() -> None:
    # charge_library_items
    if _table_exists("charge_library_items"):
        if _column_exists("charge_library_items", "standalone_price"):
            op.drop_column("charge_library_items", "standalone_price")
        if _column_exists("charge_library_items", "with_vault_price"):
            op.drop_column("charge_library_items", "with_vault_price")
        if _column_exists("charge_library_items", "has_conditional_pricing"):
            op.drop_column("charge_library_items", "has_conditional_pricing")

    # price_list_import_items
    if _column_exists("price_list_import_items", "price_variant_type"):
        op.drop_column("price_list_import_items", "price_variant_type")
    if _fk_exists("fk_import_item_parent"):
        op.drop_constraint("fk_import_item_parent", "price_list_import_items", type_="foreignkey")
    if _column_exists("price_list_import_items", "parent_bundle_import_item_id"):
        op.drop_column("price_list_import_items", "parent_bundle_import_item_id")
    if _column_exists("price_list_import_items", "is_bundle_price_variant"):
        op.drop_column("price_list_import_items", "is_bundle_price_variant")
    if _column_exists("price_list_import_items", "has_conditional_pricing"):
        op.drop_column("price_list_import_items", "has_conditional_pricing")
    if _column_exists("price_list_import_items", "extracted_price_standalone"):
        op.drop_column("price_list_import_items", "extracted_price_standalone")
    if _column_exists("price_list_import_items", "extracted_price_with_vault"):
        op.drop_column("price_list_import_items", "extracted_price_with_vault")

    # product_bundles
    if _column_exists("product_bundles", "vault_qualifier_categories"):
        op.drop_column("product_bundles", "vault_qualifier_categories")
    if _column_exists("product_bundles", "with_vault_price"):
        op.drop_column("product_bundles", "with_vault_price")
    if _column_exists("product_bundles", "standalone_price"):
        op.drop_column("product_bundles", "standalone_price")
    if _column_exists("product_bundles", "has_conditional_pricing"):
        op.drop_column("product_bundles", "has_conditional_pricing")
