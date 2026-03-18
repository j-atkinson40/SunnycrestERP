"""Add settings_json to companies.

Revision ID: b5c6d7e8f9g0
Revises: a4b5c6d7e8f9
Create Date: 2026-03-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

revision = "b5c6d7e8f9g0"
down_revision = "a4b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa_inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("companies")]
    if "settings_json" not in columns:
        op.add_column("companies", sa.Column("settings_json", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("companies", "settings_json")
