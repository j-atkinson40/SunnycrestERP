"""Create platform_incidents table for self-repair system.

Revision ID: z9l9m0n1o2p3
Revises: z9k8l9m0n1o2
Create Date: 2026-04-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "z9l9m0n1o2p3"
down_revision = "z9k8l9m0n1o2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_incidents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        # Classification
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("fingerprint", sa.String(64), nullable=True),
        # What happened
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("stack_trace", sa.Text(), nullable=True),
        sa.Column("context", postgresql.JSONB(), server_default="{}"),
        # Response
        sa.Column("resolution_tier", sa.String(20), nullable=True),
        sa.Column("resolution_status", sa.String(20), server_default="pending"),
        sa.Column("resolution_action", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_duration_seconds", sa.Integer(), nullable=True),
        # Learning
        sa.Column("was_repeat", sa.Boolean(), server_default="false"),
        sa.Column(
            "previous_incident_id",
            sa.String(36),
            sa.ForeignKey("platform_incidents.id"),
            nullable=True,
        ),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_index("idx_platform_incidents_tenant", "platform_incidents", ["tenant_id"])
    op.create_index("idx_platform_incidents_status", "platform_incidents", ["resolution_status"])
    op.create_index("idx_platform_incidents_fingerprint", "platform_incidents", ["fingerprint"])
    op.create_index(
        "idx_platform_incidents_created",
        "platform_incidents",
        [sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_platform_incidents_created", table_name="platform_incidents")
    op.drop_index("idx_platform_incidents_fingerprint", table_name="platform_incidents")
    op.drop_index("idx_platform_incidents_status", table_name="platform_incidents")
    op.drop_index("idx_platform_incidents_tenant", table_name="platform_incidents")
    op.drop_table("platform_incidents")
