"""platform_notifications table

Revision ID: z9n1o2p3q4r5
Revises: z9m0n1o2p3q4
Create Date: 2026-04-08
"""

from alembic import op
import sqlalchemy as sa

revision = "z9n1o2p3q4r5"
down_revision = "z9m0n1o2p3q4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=True, index=True),
        sa.Column(
            "incident_id",
            sa.String(36),
            sa.ForeignKey("platform_incidents.id"),
            nullable=True,
        ),
        sa.Column("level", sa.String(20), nullable=False, server_default="info"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("is_dismissed", sa.Boolean, server_default="false"),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_platform_notif_dismissed",
        "platform_notifications",
        ["is_dismissed"],
        postgresql_where=sa.text("is_dismissed = false"),
    )


def downgrade() -> None:
    op.drop_index("idx_platform_notif_dismissed", table_name="platform_notifications")
    op.drop_table("platform_notifications")
