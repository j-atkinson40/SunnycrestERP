"""Add functional area definitions table and employee functional_areas column.

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i0
Create Date: 2026-03-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "e5f6g7h8i9j0"
down_revision = "d4e5f6g7h8i0"
branch_labels = None
depends_on = None


def _table_exists(conn, table_name: str) -> bool:
    result = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_name = :t)"
        ),
        {"t": table_name},
    )
    return result.scalar()


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    result = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c)"
        ),
        {"t": table_name, "c": column_name},
    )
    return result.scalar()


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Create functional_area_definitions table
    if not _table_exists(conn, "functional_area_definitions"):
        op.create_table(
            "functional_area_definitions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("preset", sa.String(30), nullable=False, index=True),
            sa.Column("area_key", sa.String(100), nullable=False, unique=True),
            sa.Column("display_name", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("icon", sa.String(50), nullable=True),
            sa.Column("required_extension", sa.String(100), nullable=True),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
        )

    # 2. Add functional_areas column to employee_profiles
    if not _column_exists(conn, "employee_profiles", "functional_areas"):
        op.add_column(
            "employee_profiles",
            sa.Column("functional_areas", JSONB(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("employee_profiles", "functional_areas")
    op.drop_table("functional_area_definitions")
