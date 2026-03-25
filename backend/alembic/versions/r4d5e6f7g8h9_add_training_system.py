"""Add employee training and competency system.

Revision ID: r4d5e6f7g8h9
Revises: r3c4d5e6f7g8
Create Date: 2026-03-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision = "r4d5e6f7g8h9"
down_revision = "r3c4d5e6f7g8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # User learning profiles
    op.create_table(
        "user_learning_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("training_role", sa.String(30), nullable=False),
        sa.Column("is_new_employee", sa.Boolean(), server_default="true"),
        sa.Column("employee_start_date", sa.Date(), server_default=sa.func.current_date()),
        sa.Column("guided_flows_completed", JSONB, server_default="[]"),
        sa.Column("procedures_viewed", JSONB, server_default="{}"),
        sa.Column("curriculum_track_id", sa.String(36), nullable=True),
        sa.Column("tasks_completed_independently", sa.Integer(), server_default="0"),
        sa.Column("tasks_completed_with_agent", sa.Integer(), server_default="0"),
        sa.Column("coaching_moments_count", sa.Integer(), server_default="0"),
        sa.Column("last_coaching_summary_at", sa.Date(), nullable=True),
        sa.Column("show_contextual_explanations", sa.Boolean(), server_default="true"),
        sa.Column("show_guided_flow_offers", sa.Boolean(), server_default="true"),
        sa.Column("show_new_employee_briefing", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_learning_profile", "user_learning_profiles", ["tenant_id", "user_id"])

    # Curriculum tracks
    op.create_table(
        "training_curriculum_tracks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("track_name", sa.String(100), nullable=False),
        sa.Column("training_role", sa.String(30), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("modules", JSONB, server_default="[]"),
        sa.Column("total_modules", sa.Integer(), server_default="0"),
        sa.Column("estimated_weeks", sa.Integer(), server_default="4"),
        sa.Column("content_generated", sa.Boolean(), server_default="false"),
        sa.Column("content_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_edited_by", sa.String(36), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # User track progress
    op.create_table(
        "user_track_progress",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("track_id", sa.String(36), sa.ForeignKey("training_curriculum_tracks.id"), nullable=False),
        sa.Column("status", sa.String(20), server_default="in_progress"),
        sa.Column("current_module_index", sa.Integer(), server_default="0"),
        sa.Column("module_completions", JSONB, server_default="[]"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint("uq_track_progress", "user_track_progress", ["tenant_id", "user_id", "track_id"])

    # Procedure library
    op.create_table(
        "training_procedures",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("procedure_key", sa.String(100), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("applicable_roles", ARRAY(sa.String(30)), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("overview", sa.Text()),
        sa.Column("steps", JSONB, server_default="[]"),
        sa.Column("related_procedure_keys", ARRAY(sa.String(100)), nullable=True),
        sa.Column("related_feature_urls", ARRAY(sa.Text()), nullable=True),
        sa.Column("content_generated", sa.Boolean(), server_default="false"),
        sa.Column("content_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_edited_by", sa.String(36), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_procedure_key", "training_procedures", ["tenant_id", "procedure_key"])

    # Contextual explanations
    op.create_table(
        "contextual_explanations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("explanation_key", sa.String(100), nullable=False),
        sa.Column("trigger_context", sa.String(200), nullable=False),
        sa.Column("headline", sa.String(200), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("applicable_roles", ARRAY(sa.String(30)), nullable=True),
        sa.Column("content_generated", sa.Boolean(), server_default="false"),
        sa.Column("content_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_edited_by", sa.String(36), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_explanation_key", "contextual_explanations", ["tenant_id", "explanation_key"])

    # Guided flow sessions
    op.create_table(
        "guided_flow_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("flow_key", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), server_default="offered"),
        sa.Column("current_step", sa.Integer(), server_default="0"),
        sa.Column("total_steps", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("offer_count", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_guided_flow", "guided_flow_sessions", ["tenant_id", "user_id", "flow_key"])

    # Coaching observations
    op.create_table(
        "coaching_observations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("observation_type", sa.String(50), nullable=False),
        sa.Column("observation_data", JSONB, server_default="{}"),
        sa.Column("is_positive", sa.Boolean(), server_default="false"),
        sa.Column("included_in_summary", sa.Boolean(), server_default="false"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_coaching_obs_user", "coaching_observations", ["tenant_id", "user_id", sa.text("occurred_at DESC")])

    # AI assistant conversations
    op.create_table(
        "training_assistant_conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("messages", JSONB, server_default="[]"),
        sa.Column("page_context", sa.String(200), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("training_assistant_conversations")
    op.drop_table("coaching_observations")
    op.drop_table("guided_flow_sessions")
    op.drop_table("contextual_explanations")
    op.drop_table("training_procedures")
    op.drop_table("user_track_progress")
    op.drop_table("training_curriculum_tracks")
    op.drop_table("user_learning_profiles")
