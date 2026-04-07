"""Add job_runs table for scheduler audit logging

Revision ID: z9i6j7k8l9m0
Revises: z9h5i6j7k8l9
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa

revision = "z9i6j7k8l9m0"
down_revision = "z9h5i6j7k8l9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_type", sa.String(80), nullable=False, index=True),
        sa.Column("trigger", sa.String(20), nullable=False, server_default="scheduled"),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("tenant_count", sa.Integer, nullable=True),
        sa.Column("success_count", sa.Integer, nullable=True),
        sa.Column("error_count", sa.Integer, nullable=True),
        sa.Column("duration_seconds", sa.Float, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("triggered_by", sa.String(100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("job_runs")
