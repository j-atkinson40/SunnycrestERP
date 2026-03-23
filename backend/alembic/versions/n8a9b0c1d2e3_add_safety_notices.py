"""add safety notices

Revision ID: n8a9b0c1d2e3
Revises: n7a8b9c0d1e2
Create Date: 2026-03-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "n8a9b0c1d2e3"
down_revision: Union[str, None] = "n7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- announcements table --
    op.add_column(
        "announcements",
        sa.Column("content_type", sa.String(30), nullable=False, server_default="announcement"),
    )
    op.add_column(
        "announcements",
        sa.Column("safety_category", sa.String(30), nullable=True),
    )
    op.add_column(
        "announcements",
        sa.Column("requires_acknowledgment", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "announcements",
        sa.Column("is_compliance_relevant", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "announcements",
        sa.Column("document_url", sa.String(500), nullable=True),
    )
    op.add_column(
        "announcements",
        sa.Column("document_filename", sa.String(255), nullable=True),
    )
    op.add_column(
        "announcements",
        sa.Column(
            "linked_equipment_id",
            sa.String(36),
            sa.ForeignKey("tenant_equipment_items.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "announcements",
        sa.Column(
            "linked_incident_id",
            sa.String(36),
            sa.ForeignKey("safety_incidents.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "announcements",
        sa.Column(
            "linked_training_id",
            sa.String(36),
            sa.ForeignKey("safety_training_events.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "announcements",
        sa.Column("acknowledgment_deadline", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "announcements",
        sa.Column("reminder_sent_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- announcement_reads table --
    op.add_column(
        "announcement_reads",
        sa.Column("acknowledgment_type", sa.String(20), nullable=True),
    )
    op.add_column(
        "announcement_reads",
        sa.Column("acknowledgment_note", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    # -- announcement_reads table --
    op.drop_column("announcement_reads", "acknowledgment_note")
    op.drop_column("announcement_reads", "acknowledgment_type")

    # -- announcements table --
    op.drop_column("announcements", "reminder_sent_at")
    op.drop_column("announcements", "acknowledgment_deadline")
    op.drop_column("announcements", "linked_training_id")
    op.drop_column("announcements", "linked_incident_id")
    op.drop_column("announcements", "linked_equipment_id")
    op.drop_column("announcements", "document_filename")
    op.drop_column("announcements", "document_url")
    op.drop_column("announcements", "is_compliance_relevant")
    op.drop_column("announcements", "requires_acknowledgment")
    op.drop_column("announcements", "safety_category")
    op.drop_column("announcements", "content_type")
