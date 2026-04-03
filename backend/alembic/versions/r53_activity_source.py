"""Add source column to activity_log for voice memos and command bar.

Revision ID: r53_activity_source
Revises: r52_pattern_alerts
"""

from alembic import op
import sqlalchemy as sa

revision = "r53_activity_source"
down_revision = "r52_pattern_alerts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("activity_log", sa.Column("source", sa.String(20), server_default="manual"))
    op.add_column("activity_log", sa.Column("transcript", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("activity_log", "transcript")
    op.drop_column("activity_log", "source")
