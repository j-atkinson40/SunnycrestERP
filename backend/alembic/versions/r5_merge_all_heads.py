"""Merge all migration heads into single head.

Revision ID: r5_merge_all
Revises: o6b7c8d9e0f1, p4a5b6c7d8e9, r4d5e6f7g8h9, s4a5b6c7d8e9
Create Date: 2026-03-25
"""

revision = "r5_merge_all"
down_revision = ("o6b7c8d9e0f1", "p4a5b6c7d8e9", "r4d5e6f7g8h9", "s4a5b6c7d8e9")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
