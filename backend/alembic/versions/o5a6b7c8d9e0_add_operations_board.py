"""Add operations board tables with registry architecture.

Revision ID: o5a6b7c8d9e0
Revises: o4a5b6c7d8e9
Create Date: 2026-03-23
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "o5a6b7c8d9e0"
down_revision = "o4a5b6c7d8e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Operations board per-employee settings — fixed + JSONB hybrid
    op.create_table(
        "operations_board_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        # Core zone toggles (fixed columns)
        sa.Column("zone_briefing_visible", sa.Boolean(), server_default="true"),
        sa.Column("zone_announcements_visible", sa.Boolean(), server_default="true"),
        sa.Column("zone_production_log_visible", sa.Boolean(), server_default="true"),
        # Core button toggles (fixed columns)
        sa.Column("button_log_incident", sa.Boolean(), server_default="true"),
        sa.Column("button_safety_observation", sa.Boolean(), server_default="true"),
        sa.Column("button_qc_check", sa.Boolean(), server_default="true"),
        sa.Column("button_log_product", sa.Boolean(), server_default="true"),
        sa.Column("button_end_of_day", sa.Boolean(), server_default="true"),
        sa.Column("button_equipment_inspection", sa.Boolean(), server_default="true"),
        # Core behavior settings (fixed)
        sa.Column("voice_entry_enabled", sa.Boolean(), server_default="true"),
        sa.Column("eod_reminder_enabled", sa.Boolean(), server_default="true"),
        sa.Column("eod_reminder_time", sa.String(5), server_default="16:00"),
        # Extension and contributor settings (JSONB — extensible)
        sa.Column("contributor_settings", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "employee_id", name="uq_ops_board_settings_employee"),
    )

    # Daily production summaries
    op.create_table(
        "daily_production_summaries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("summary_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("posted_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("notes_for_tomorrow", sa.Text(), nullable=True),
        sa.Column("has_qc_failures", sa.Boolean(), server_default="false"),
        sa.Column("qc_failure_acknowledged_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("qc_failure_acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        # Each contributor stores its own aggregated EOD data here
        sa.Column("contributor_data", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "summary_date", name="uq_daily_prod_summary_date"),
    )

    # Production log entries
    op.create_table(
        "ops_production_log_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("summary_id", sa.String(36), sa.ForeignKey("daily_production_summaries.id"), nullable=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=True),
        sa.Column("product_name_raw", sa.String(200), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("logged_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("logged_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("qc_status", sa.String(20), server_default="not_checked"),
        sa.Column("qc_notes", sa.Text(), nullable=True),
        sa.Column("qc_checked_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("qc_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_excluded_from_inventory", sa.Boolean(), server_default="false"),
        sa.Column("entry_method", sa.String(20), server_default="manual"),
        sa.Column("raw_prompt", sa.Text(), nullable=True),
        # Registry contributor tracking
        sa.Column("contributor_key", sa.String(50), nullable=True),
        sa.Column("contributor_data", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Announcement replies
    op.create_table(
        "announcement_replies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("announcement_id", sa.String(36), sa.ForeignKey("announcements.id"), nullable=False, index=True),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reply_type", sa.String(20), nullable=False),
        sa.Column("replied_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("previous_reply_type", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("announcement_id", "employee_id", name="uq_announcement_reply_emp"),
    )

    # Add operations board columns to announcements
    op.add_column("announcements", sa.Column("is_operations_board", sa.Boolean(), server_default="false"))
    op.add_column("announcements", sa.Column("reply_options_enabled", sa.Boolean(), server_default="false"))

    # Add operations board posting permission to employee_profiles
    op.add_column("employee_profiles", sa.Column("can_post_to_operations_board", sa.Boolean(), server_default="false"))


def downgrade() -> None:
    op.drop_column("employee_profiles", "can_post_to_operations_board")
    op.drop_column("announcements", "reply_options_enabled")
    op.drop_column("announcements", "is_operations_board")
    op.drop_table("announcement_replies")
    op.drop_table("ops_production_log_entries")
    op.drop_table("daily_production_summaries")
    op.drop_table("operations_board_settings")
