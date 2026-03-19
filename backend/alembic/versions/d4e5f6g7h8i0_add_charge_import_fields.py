"""Add charge import fields to price_list_import_items.

Revision ID: d4e5f6g7h8i0
Revises: c3d4e5f6g7h9
Create Date: 2026-03-19
"""

from alembic import op
import sqlalchemy as sa

revision = "d4e5f6g7h8i0"
down_revision = "c3d4e5f6g7h9"
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


def upgrade() -> None:
    # price_list_import_items — charge matching fields
    if not _column_exists("price_list_import_items", "charge_category"):
        op.add_column(
            "price_list_import_items",
            sa.Column("charge_category", sa.String(50), nullable=True),
        )
    if not _column_exists("price_list_import_items", "charge_key_suggestion"):
        op.add_column(
            "price_list_import_items",
            sa.Column("charge_key_suggestion", sa.String(100), nullable=True),
        )
    if not _column_exists("price_list_import_items", "charge_match_type"):
        op.add_column(
            "price_list_import_items",
            sa.Column("charge_match_type", sa.String(30), nullable=True),
        )
    if not _column_exists("price_list_import_items", "matched_charge_id"):
        op.add_column(
            "price_list_import_items",
            sa.Column("matched_charge_id", sa.String(36), nullable=True),
        )
    if not _column_exists("price_list_import_items", "matched_charge_name"):
        op.add_column(
            "price_list_import_items",
            sa.Column("matched_charge_name", sa.String(255), nullable=True),
        )
    if not _column_exists("price_list_import_items", "charge_key_to_use"):
        op.add_column(
            "price_list_import_items",
            sa.Column("charge_key_to_use", sa.String(100), nullable=True),
        )
    if not _column_exists("price_list_import_items", "pricing_type_suggestion"):
        op.add_column(
            "price_list_import_items",
            sa.Column("pricing_type_suggestion", sa.String(30), nullable=True),
        )
    if not _column_exists("price_list_import_items", "enable_on_import"):
        op.add_column(
            "price_list_import_items",
            sa.Column("enable_on_import", sa.Boolean(), server_default="true", nullable=False),
        )


def downgrade() -> None:
    if _column_exists("price_list_import_items", "enable_on_import"):
        op.drop_column("price_list_import_items", "enable_on_import")
    if _column_exists("price_list_import_items", "pricing_type_suggestion"):
        op.drop_column("price_list_import_items", "pricing_type_suggestion")
    if _column_exists("price_list_import_items", "charge_key_to_use"):
        op.drop_column("price_list_import_items", "charge_key_to_use")
    if _column_exists("price_list_import_items", "matched_charge_name"):
        op.drop_column("price_list_import_items", "matched_charge_name")
    if _column_exists("price_list_import_items", "matched_charge_id"):
        op.drop_column("price_list_import_items", "matched_charge_id")
    if _column_exists("price_list_import_items", "charge_match_type"):
        op.drop_column("price_list_import_items", "charge_match_type")
    if _column_exists("price_list_import_items", "charge_key_suggestion"):
        op.drop_column("price_list_import_items", "charge_key_suggestion")
    if _column_exists("price_list_import_items", "charge_category"):
        op.drop_column("price_list_import_items", "charge_category")
