"""add bill_of_materials and bom_lines tables

Revision ID: i8j9k0l1m2n3
Revises: h7i8j9k0l1m2
Create Date: 2026-03-17

"""
from alembic import op
import sqlalchemy as sa

revision = "i8j9k0l1m2n3"
down_revision = "h7i8j9k0l1m2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bill_of_materials",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "product_id",
            sa.String(36),
            sa.ForeignKey("products.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("effective_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column(
            "modified_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "product_id", "version", "company_id", name="uq_bom_product_version_company"
        ),
    )

    op.create_table(
        "bom_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "bom_id",
            sa.String(36),
            sa.ForeignKey("bill_of_materials.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "component_product_id",
            sa.String(36),
            sa.ForeignKey("products.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "quantity",
            sa.Numeric(12, 4),
            nullable=False,
        ),
        sa.Column("unit_of_measure", sa.String(50), nullable=False),
        sa.Column(
            "waste_factor_pct",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "is_optional",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_table("bom_lines")
    op.drop_table("bill_of_materials")
