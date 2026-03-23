"""Add toolbox talk suggestions and training reminder escalation.

Revision ID: o6b7c8d9e0f1
Revises: o5a6b7c8d9e0
Create Date: 2026-03-23
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "o6b7c8d9e0f1"
down_revision = "o5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Toolbox talk suggestions
    op.create_table(
        "toolbox_talk_suggestions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("suggestion_date", sa.Date(), nullable=False),
        sa.Column("topic_title", sa.String(200), nullable=False),
        sa.Column("topic_category", sa.String(30), nullable=False),
        sa.Column("trigger_type", sa.String(30), nullable=False),
        sa.Column("trigger_description", sa.Text(), nullable=False),
        sa.Column("trigger_entity_type", sa.String(50), nullable=True),
        sa.Column("trigger_entity_id", sa.String(36), nullable=True),
        sa.Column("talking_points", JSONB, nullable=True),
        sa.Column("talking_points_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_in_toolbox_talk_id", sa.String(36), sa.ForeignKey("toolbox_talks.id"), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("next_suggestion_after", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Add generated_from_suggestion_id to toolbox_talks
    op.add_column(
        "toolbox_talks",
        sa.Column("generated_from_suggestion_id", sa.String(36),
                  sa.ForeignKey("toolbox_talk_suggestions.id"), nullable=True),
    )

    # Training reminder escalation fields
    op.add_column(
        "tenant_training_schedules",
        sa.Column("second_reminder_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenant_training_schedules",
        sa.Column("owner_notified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenant_training_schedules",
        sa.Column("owner_notified_via", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenant_training_schedules", "owner_notified_via")
    op.drop_column("tenant_training_schedules", "owner_notified_at")
    op.drop_column("tenant_training_schedules", "second_reminder_sent_at")
    op.drop_column("toolbox_talks", "generated_from_suggestion_id")
    op.drop_table("toolbox_talk_suggestions")
