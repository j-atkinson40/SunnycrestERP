"""Add vertical column to companies table.

Revision ID: w5x6y7z8a9b0
Revises: v4w5x6y7z8a9
Create Date: 2026-03-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "w5x6y7z8a9b0"
down_revision = "v4w5x6y7z8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa_inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("companies")]
    if "vertical" not in columns:
        op.add_column("companies", sa.Column("vertical", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("companies", "vertical")
