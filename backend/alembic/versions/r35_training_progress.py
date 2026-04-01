"""Add training_progress table for tracking per-user training completion.

Revision ID: r35_training_progress
Revises: r34_order_service_fields
"""

from alembic import op
import sqlalchemy as sa

revision = "r35_training_progress"
down_revision = "r34_order_service_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "training_progress",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("training_key", sa.String(100), nullable=False),
        sa.Column("stage_key", sa.String(50), nullable=False),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "user_id", "training_key", "stage_key",
            name="uq_training_progress_user_stage",
        ),
    )
    op.create_index(
        "idx_training_progress_user",
        "training_progress",
        ["user_id", "training_key"],
    )


def downgrade() -> None:
    op.drop_index("idx_training_progress_user", table_name="training_progress")
    op.drop_table("training_progress")
