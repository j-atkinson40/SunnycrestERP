"""Merge all outstanding heads into a single chain.

Revision ID: r10_merge_all_heads
Revises: r9_billing_terms, e5f6g7h8i9j0, n6a7b8c9d0e1
Create Date: 2026-03-28
"""

from alembic import op
import sqlalchemy as sa

revision = "r10_merge_all_heads"
down_revision = ("r9_billing_terms", "e5f6g7h8i9j0", "n6a7b8c9d0e1")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Pure merge — no schema changes needed.
    # All column additions are handled by the individual migrations in each branch.
    pass


def downgrade() -> None:
    pass
