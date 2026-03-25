"""Add cross-system intelligence tables.

Revision ID: r1a2b3c4d5e6
Revises: q9t0u1v2w3x4
Create Date: 2026-03-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "r1a2b3c4d5e6"
down_revision = "q9t0u1v2w3x4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Financial health scores — daily grades
    op.create_table(
        "financial_health_scores",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("score_date", sa.Date(), nullable=False),
        sa.Column("overall_grade", sa.String(2), nullable=False),
        sa.Column("overall_score", sa.Numeric(4, 1), nullable=False),
        # Dimensions
        sa.Column("ar_health_score", sa.Numeric(4, 1)),
        sa.Column("ar_health_grade", sa.String(2)),
        sa.Column("ap_discipline_score", sa.Numeric(4, 1)),
        sa.Column("ap_discipline_grade", sa.String(2)),
        sa.Column("cash_position_score", sa.Numeric(4, 1)),
        sa.Column("cash_position_grade", sa.String(2)),
        sa.Column("operational_integrity_score", sa.Numeric(4, 1)),
        sa.Column("operational_integrity_grade", sa.String(2)),
        sa.Column("growth_trajectory_score", sa.Numeric(4, 1)),
        sa.Column("growth_trajectory_grade", sa.String(2)),
        # Weights and factors
        sa.Column("weights", JSONB, server_default='{"ar_health":0.25,"ap_discipline":0.20,"cash_position":0.20,"operational_integrity":0.20,"growth_trajectory":0.15}'),
        sa.Column("top_positive_factors", JSONB, server_default="[]"),
        sa.Column("top_negative_factors", JSONB, server_default="[]"),
        # Trend
        sa.Column("prior_score", sa.Numeric(4, 1)),
        sa.Column("score_change", sa.Numeric(4, 1)),
        sa.Column("trend_7_day", sa.Numeric(4, 1)),
        sa.Column("calculation_inputs", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_health_score_date", "financial_health_scores", ["tenant_id", "score_date"])
    op.create_index("idx_fhs_tenant_date", "financial_health_scores", ["tenant_id", sa.text("score_date DESC")])

    # Cross-system insights
    op.create_table(
        "cross_system_insights",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("insight_key", sa.String(100), nullable=False),
        sa.Column("primary_entity_type", sa.String(30)),
        sa.Column("primary_entity_id", sa.String(36)),
        sa.Column("connected_systems", JSONB, server_default="[]"),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("narrative", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("primary_action_label", sa.Text()),
        sa.Column("primary_action_url", sa.Text()),
        sa.Column("secondary_action_label", sa.Text()),
        sa.Column("secondary_action_url", sa.Text()),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("auto_resolved", sa.Boolean(), server_default="false"),
        sa.Column("first_detected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_confirmed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_cross_insight", "cross_system_insights", ["tenant_id", "insight_key", "primary_entity_id"])
    op.create_index("idx_csi_tenant_status", "cross_system_insights", ["tenant_id", "status", "severity"])

    # Seasonal readiness reports
    op.create_table(
        "seasonal_readiness_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("season", sa.String(20), nullable=False),
        sa.Column("season_year", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("readiness_score", sa.Numeric(4, 1)),
        sa.Column("readiness_grade", sa.String(2)),
        sa.Column("financial_readiness", sa.Numeric(4, 1)),
        sa.Column("operational_readiness", sa.Numeric(4, 1)),
        sa.Column("customer_readiness", sa.Numeric(4, 1)),
        sa.Column("inventory_readiness", sa.Numeric(4, 1)),
        sa.Column("ready_items", JSONB, server_default="[]"),
        sa.Column("action_items", JSONB, server_default="[]"),
        sa.Column("executive_summary", sa.Text()),
    )
    op.create_unique_constraint("uq_seasonal_report", "seasonal_readiness_reports", ["tenant_id", "season", "season_year"])

    # Relationship health history on behavioral profiles
    op.add_column("entity_behavioral_profiles", sa.Column("relationship_health_history", JSONB, server_default="[]"))


def downgrade() -> None:
    op.drop_column("entity_behavioral_profiles", "relationship_health_history")
    op.drop_table("seasonal_readiness_reports")
    op.drop_table("cross_system_insights")
    op.drop_table("financial_health_scores")
