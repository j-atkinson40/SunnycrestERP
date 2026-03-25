"""Add inter-licensee transfer pricing system.

Revision ID: q4n5o6p7q8r9
Revises: q3m4n5o6p7q8
Create Date: 2026-03-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "q4n5o6p7q8r9"
down_revision = "q3m4n5o6p7q8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Inter-licensee price lists
    op.create_table(
        "inter_licensee_price_lists",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(100), server_default="Inter-Licensee Transfer Pricing"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("visible_to_all_licensees", sa.Boolean(), server_default="true"),
        sa.Column("pricing_method", sa.String(20), server_default="fixed"),
        sa.Column("retail_adjustment_percentage", sa.Numeric(5, 2), server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_inter_licensee_price_list_tenant", "inter_licensee_price_lists", ["tenant_id"])

    # Price list items
    op.create_table(
        "inter_licensee_price_list_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("price_list_id", sa.String(36), sa.ForeignKey("inter_licensee_price_lists.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.String(36), nullable=True),
        sa.Column("product_name", sa.String(200), nullable=False),
        sa.Column("product_code", sa.String(100), nullable=True),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("unit", sa.String(50), server_default="each"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Transfer pricing fields
    op.add_column("licensee_transfers", sa.Column("pricing_status", sa.String(30), server_default="not_started"))
    op.add_column("licensee_transfers", sa.Column("area_unit_prices", JSONB, server_default="[]"))
    op.add_column("licensee_transfers", sa.Column("area_pricing_notes", sa.Text(), nullable=True))
    op.add_column("licensee_transfers", sa.Column("price_reviewed_by", sa.String(36), nullable=True))
    op.add_column("licensee_transfers", sa.Column("price_reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("licensee_transfers", sa.Column("price_review_notes", sa.Text(), nullable=True))
    op.add_column("licensee_transfers", sa.Column("fh_price_visible", sa.Boolean(), server_default="false"))
    op.add_column("licensee_transfers", sa.Column("fh_price_visible_at", sa.DateTime(timezone=True), nullable=True))

    # Transfer price requests
    op.create_table(
        "transfer_price_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("transfer_id", sa.String(36), sa.ForeignKey("licensee_transfers.id"), nullable=False, index=True),
        sa.Column("requesting_tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("area_tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("items_requested", JSONB, server_default="[]"),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_by", sa.String(36), nullable=True),
        sa.Column("response_items", JSONB, server_default="[]"),
        sa.Column("response_notes", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("transfer_price_requests")
    op.drop_column("licensee_transfers", "fh_price_visible_at")
    op.drop_column("licensee_transfers", "fh_price_visible")
    op.drop_column("licensee_transfers", "price_review_notes")
    op.drop_column("licensee_transfers", "price_reviewed_at")
    op.drop_column("licensee_transfers", "price_reviewed_by")
    op.drop_column("licensee_transfers", "area_pricing_notes")
    op.drop_column("licensee_transfers", "area_unit_prices")
    op.drop_column("licensee_transfers", "pricing_status")
    op.drop_table("inter_licensee_price_list_items")
    op.drop_table("inter_licensee_price_lists")
