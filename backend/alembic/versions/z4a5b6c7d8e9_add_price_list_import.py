"""Add price_list_imports and price_list_import_items tables.

Revision ID: z4a5b6c7d8e9
Revises: z3a4b5c6d7e8
Create Date: 2026-03-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "z4a5b6c7d8e9"
down_revision = "d4e5f6g7h8i9"
branch_labels = None
depends_on = None


def _table_exists(conn, table_name: str) -> bool:
    inspector = sa_inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    conn = op.get_bind()

    # ── price_list_imports ──
    if not _table_exists(conn, "price_list_imports"):
        op.create_table(
            "price_list_imports",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
            sa.Column("file_name", sa.String(255), nullable=False),
            sa.Column("file_url", sa.String(500), nullable=True),
            sa.Column("file_type", sa.String(20), nullable=False),
            sa.Column("file_size_bytes", sa.Integer, nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="uploaded"),
            sa.Column("raw_extracted_text", sa.Text, nullable=True),
            sa.Column("claude_analysis", sa.Text, nullable=True),
            sa.Column("extraction_token_usage", sa.Text, nullable=True),
            sa.Column("items_extracted", sa.Integer, server_default="0"),
            sa.Column("items_matched_high_confidence", sa.Integer, server_default="0"),
            sa.Column("items_matched_low_confidence", sa.Integer, server_default="0"),
            sa.Column("items_unmatched", sa.Integer, server_default="0"),
            sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("confirmed_by", sa.String(36), nullable=True),
            sa.Column("error_message", sa.Text, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )

    # ── price_list_import_items ──
    if not _table_exists(conn, "price_list_import_items"):
        op.create_table(
            "price_list_import_items",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
            sa.Column("import_id", sa.String(36), sa.ForeignKey("price_list_imports.id"), nullable=False, index=True),
            sa.Column("raw_text", sa.String(500), nullable=True),
            sa.Column("extracted_name", sa.String(255), nullable=False),
            sa.Column("extracted_price", sa.Numeric(12, 2), nullable=True),
            sa.Column("extracted_sku", sa.String(50), nullable=True),
            sa.Column("match_status", sa.String(20), nullable=False),
            sa.Column("matched_template_id", sa.String(36), nullable=True),
            sa.Column("matched_template_name", sa.String(255), nullable=True),
            sa.Column("match_confidence", sa.Numeric(3, 2), nullable=True),
            sa.Column("match_reasoning", sa.Text, nullable=True),
            sa.Column("final_product_name", sa.String(255), nullable=False),
            sa.Column("final_price", sa.Numeric(12, 2), nullable=True),
            sa.Column("final_sku", sa.String(50), nullable=True),
            sa.Column("action", sa.String(20), nullable=False, server_default="create_product"),
            sa.Column("product_id", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("price_list_import_items")
    op.drop_table("price_list_imports")
