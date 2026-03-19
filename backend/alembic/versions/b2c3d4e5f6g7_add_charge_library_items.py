"""Add charge_library_items table.

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "b2c3d4e5f6g7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def _get_tables(conn) -> list[str]:
    inspector = sa_inspect(conn)
    return inspector.get_table_names()


def upgrade() -> None:
    conn = op.get_bind()
    tables = _get_tables(conn)

    if "charge_library_items" not in tables:
        op.create_table(
            "charge_library_items",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "tenant_id",
                sa.String(36),
                sa.ForeignKey("companies.id"),
                nullable=False,
                index=True,
            ),
            sa.Column("charge_key", sa.String(100), nullable=False),
            sa.Column("charge_name", sa.String(255), nullable=False),
            sa.Column("category", sa.String(50), nullable=False),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column(
                "is_enabled",
                sa.Boolean,
                server_default=sa.text("false"),
                nullable=False,
            ),
            sa.Column(
                "is_system",
                sa.Boolean,
                server_default=sa.text("true"),
                nullable=False,
            ),
            sa.Column(
                "pricing_type",
                sa.String(30),
                nullable=False,
                server_default="variable",
            ),
            sa.Column("fixed_amount", sa.Numeric(12, 2), nullable=True),
            sa.Column("per_mile_rate", sa.Numeric(8, 2), nullable=True),
            sa.Column("free_radius_miles", sa.Numeric(8, 2), nullable=True),
            sa.Column("zone_config", sa.Text, nullable=True),
            sa.Column("guidance_min", sa.Numeric(12, 2), nullable=True),
            sa.Column("guidance_max", sa.Numeric(12, 2), nullable=True),
            sa.Column("variable_placeholder", sa.String(255), nullable=True),
            sa.Column(
                "auto_suggest",
                sa.Boolean,
                server_default=sa.text("false"),
                nullable=False,
            ),
            sa.Column("auto_suggest_trigger", sa.String(100), nullable=True),
            sa.Column("invoice_label", sa.String(255), nullable=True),
            sa.Column("sort_order", sa.Integer, server_default="0"),
            sa.Column("notes", sa.Text, nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.UniqueConstraint(
                "tenant_id", "charge_key", name="uq_charge_library_tenant_key"
            ),
        )


def downgrade() -> None:
    op.drop_table("charge_library_items")
