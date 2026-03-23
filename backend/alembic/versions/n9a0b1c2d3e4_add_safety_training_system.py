"""Add safety training system tables.

Revision ID: n9a0b1c2d3e4
Revises: n8a9b0c1d2e3
Create Date: 2026-03-23
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "n9a0b1c2d3e4"
down_revision = "n8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Safety training topics — platform-level seed data (no tenant_id)
    op.create_table(
        "safety_training_topics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("month_number", sa.Integer(), nullable=False),
        sa.Column("topic_key", sa.String(50), unique=True, nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("osha_standard", sa.String(100), nullable=True),
        sa.Column("osha_standard_label", sa.String(200), nullable=True),
        sa.Column("suggested_duration_minutes", sa.Integer(), server_default="30"),
        sa.Column("target_roles", JSONB(), nullable=True),
        sa.Column("key_points", JSONB(), nullable=True),
        sa.Column("discussion_questions", JSONB(), nullable=True),
        sa.Column("pdf_filename_template", sa.String(200), nullable=True),
        sa.Column("is_high_risk", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # 2. Tenant training schedules — per-tenant annual calendar
    op.create_table(
        "tenant_training_schedules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month_number", sa.Integer(), nullable=False),
        sa.Column("topic_id", sa.String(36), sa.ForeignKey("safety_training_topics.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="upcoming"),
        sa.Column("reminder_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("announcement_id", sa.String(36), sa.ForeignKey("announcements.id"), nullable=True),
        sa.Column("posted_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completion_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # 3. Toolbox talks
    op.create_table(
        "toolbox_talks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("conducted_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("conducted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("topic_title", sa.String(200), nullable=False),
        sa.Column("topic_category", sa.String(30), nullable=False, server_default="other"),
        sa.Column("linked_training_topic_id", sa.String(36), sa.ForeignKey("safety_training_topics.id"), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("attendees", JSONB(), nullable=True),
        sa.Column("attendees_external", JSONB(), nullable=True),
        sa.Column("attendee_count", sa.Integer(), server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # 4. OSHA 300 entries
    op.create_table(
        "osha_300_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("safety_incidents.id"), nullable=True),
        sa.Column("year", sa.Integer(), nullable=False, index=True),
        sa.Column("entry_number", sa.Integer(), nullable=False),
        sa.Column("employee_name", sa.String(200), nullable=False),
        sa.Column("employee_job_title", sa.String(100), nullable=True),
        sa.Column("date_of_injury", sa.Date(), nullable=False),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("classification", sa.String(30), nullable=False, server_default="other_recordable"),
        sa.Column("days_away", sa.Integer(), nullable=True),
        sa.Column("days_restricted", sa.Integer(), nullable=True),
        sa.Column("injury_type", sa.String(30), nullable=False, server_default="injury"),
        sa.Column("privacy_case", sa.Boolean(), server_default="false"),
        sa.Column("is_auto_populated", sa.Boolean(), server_default="false"),
        sa.Column("reviewed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("osha_300_entries")
    op.drop_table("toolbox_talks")
    op.drop_table("tenant_training_schedules")
    op.drop_table("safety_training_topics")
