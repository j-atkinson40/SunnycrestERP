"""Add morning briefings tables and employee_profiles columns.

Revision ID: n6a7b8c9d0e1
Revises: n5merge_all_heads
Create Date: 2026-03-23
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "n6a7b8c9d0e1"
down_revision = "n5merge_all_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create employee_briefings table
    op.create_table(
        "employee_briefings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("briefing_date", sa.Date(), nullable=False),
        sa.Column("primary_area", sa.String(50), nullable=True),
        sa.Column("tier", sa.String(20), nullable=False),
        sa.Column("context_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("generated_content", sa.Text(), nullable=True),
        sa.Column("parsed_items", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("token_usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("generation_duration_ms", sa.Integer(), nullable=True),
        sa.Column("was_cached", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("company_id", "user_id", "briefing_date", name="uq_employee_briefing_daily"),
    )
    # Index for fast cache lookups
    op.create_index("ix_employee_briefings_user_date", "employee_briefings", ["user_id", "briefing_date"])

    # Create assistant_profiles table
    op.create_table(
        "assistant_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), unique=True, nullable=False, index=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("primary_area", sa.String(50), nullable=True),
        sa.Column("last_briefing_date", sa.Date(), nullable=True),
        sa.Column("last_briefing_content", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # Add briefing columns to employee_profiles
    op.add_column("employee_profiles", sa.Column("briefing_enabled", sa.Boolean(), server_default="true", nullable=False))
    op.add_column("employee_profiles", sa.Column("briefing_primary_area_override", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("employee_profiles", "briefing_primary_area_override")
    op.drop_column("employee_profiles", "briefing_enabled")
    op.drop_index("ix_employee_briefings_user_date", table_name="employee_briefings")
    op.drop_table("assistant_profiles")
    op.drop_table("employee_briefings")
