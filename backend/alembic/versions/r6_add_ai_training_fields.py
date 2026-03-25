"""Add AI training additions — sent_without_edit tracking.

Revision ID: r6_ai_training
Revises: r5_merge_all
Create Date: 2026-03-25
"""

import sqlalchemy as sa
from alembic import op

revision = "r6_ai_training"
down_revision = "r5_merge_all"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Track if collections drafts were sent without editing
    op.add_column(
        "agent_collection_sequences",
        sa.Column("sent_without_edit", sa.Boolean(), server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("agent_collection_sequences", "sent_without_edit")
