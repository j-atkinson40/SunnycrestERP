"""Create tables for AI background agents.

Revision ID: r54_ai_agents
Revises: r53_activity_source
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "r54_ai_agents"
down_revision = "r53_activity_source"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Duplicate detection reviews
    op.create_table(
        "duplicate_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("company_id_a", sa.String(36), sa.ForeignKey("company_entities.id"), nullable=False),
        sa.Column("company_id_b", sa.String(36), sa.ForeignKey("company_entities.id"), nullable=False),
        sa.Column("similarity_score", sa.Numeric(4, 3), nullable=True),
        sa.Column("claude_confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("claude_reasoning", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("resolved_by", sa.String(36), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # Upsell insights
    op.create_table(
        "ai_upsell_insights",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("master_company_id", sa.String(36), sa.ForeignKey("company_entities.id"), nullable=True),
        sa.Column("insight_type", sa.String(50), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("dismissed", sa.Boolean, server_default="false"),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("converted", sa.Boolean, server_default="false"),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Account rescue email drafts
    op.create_table(
        "ai_rescue_drafts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("master_company_id", sa.String(36), sa.ForeignKey("company_entities.id"), nullable=True),
        sa.Column("subject", sa.Text, nullable=True),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_by", sa.String(36), nullable=True),
        sa.Column("edited_body", sa.Text, nullable=True),
    )

    # Company insights (new customer intelligence, etc)
    op.create_table(
        "ai_company_insights",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("master_company_id", sa.String(36), sa.ForeignKey("company_entities.id"), nullable=True),
        sa.Column("insight_type", sa.String(50), nullable=True),
        sa.Column("content", JSONB, nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("dismissed", sa.Boolean, server_default="false"),
    )

    # Cash flow forecasts
    op.create_table(
        "cash_flow_forecasts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("forecast_week", sa.Date, nullable=False),
        sa.Column("predicted_collections", sa.Numeric(12, 2), nullable=True),
        sa.Column("invoice_count", sa.Integer, nullable=True),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # Agent run log
    op.create_table(
        "ai_agent_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("agent_name", sa.String(100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("records_processed", sa.Integer, nullable=True),
        sa.Column("results_summary", JSONB, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
    )
    op.create_index("idx_agent_runs_tenant", "ai_agent_runs", ["tenant_id", "agent_name"])

    # Add relationship score to manufacturer profiles
    op.add_column("manufacturer_company_profiles", sa.Column("relationship_score", sa.Integer, nullable=True))
    op.add_column("manufacturer_company_profiles", sa.Column("relationship_score_breakdown", JSONB, nullable=True))
    op.add_column("manufacturer_company_profiles", sa.Column("relationship_score_calculated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("manufacturer_company_profiles", "relationship_score_calculated_at")
    op.drop_column("manufacturer_company_profiles", "relationship_score_breakdown")
    op.drop_column("manufacturer_company_profiles", "relationship_score")
    op.drop_table("ai_agent_runs")
    op.drop_table("cash_flow_forecasts")
    op.drop_table("ai_company_insights")
    op.drop_table("ai_rescue_drafts")
    op.drop_table("ai_upsell_insights")
    op.drop_table("duplicate_reviews")
