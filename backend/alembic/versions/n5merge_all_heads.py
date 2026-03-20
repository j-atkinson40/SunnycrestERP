"""Merge multiple alembic heads into a single head.

Revision ID: n5merge_all_heads
Revises: z7a8b9c0d1e2, n4d5m6i7l8e9
Create Date: 2026-03-20
"""

from alembic import op

revision = "n5merge_all_heads"
down_revision = ("z7a8b9c0d1e2", "n4d5m6i7l8e9")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
