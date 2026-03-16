"""Add delivery type definitions table.

Revision ID: f5g6h7i8j9k0
Revises: e4f5g6h7i8j9
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = "f5g6h7i8j9k0"
down_revision = "e4f5g6h7i8j9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "delivery_type_definitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("key", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("color", sa.String(30), server_default="gray"),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("driver_instructions", sa.Text, nullable=True),
        sa.Column("requires_signature", sa.Boolean, server_default=sa.text("false")),
        sa.Column("requires_photo", sa.Boolean, server_default=sa.text("false")),
        sa.Column("requires_weight_ticket", sa.Boolean, server_default=sa.text("false")),
        sa.Column("allows_partial", sa.Boolean, server_default=sa.text("false")),
        sa.Column("sort_order", sa.Integer, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("company_id", "key", name="uq_company_delivery_type"),
    )


def downgrade() -> None:
    op.drop_table("delivery_type_definitions")
