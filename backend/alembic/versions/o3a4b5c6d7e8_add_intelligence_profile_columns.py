"""Add per-employee intelligence settings to assistant_profiles.

Revision ID: o3a4b5c6d7e8
Revises: o2a3b4c5d6e7
Create Date: 2026-03-23
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "o3a4b5c6d7e8"
down_revision = "o2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assistant_profiles",
        sa.Column("disabled_briefing_items", JSONB(), server_default="[]"),
    )
    op.add_column(
        "assistant_profiles",
        sa.Column("disabled_announcement_categories", JSONB(), server_default="[]"),
    )
    op.add_column(
        "assistant_profiles",
        sa.Column("disabled_console_items", JSONB(), server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("assistant_profiles", "disabled_console_items")
    op.drop_column("assistant_profiles", "disabled_announcement_categories")
    op.drop_column("assistant_profiles", "disabled_briefing_items")
