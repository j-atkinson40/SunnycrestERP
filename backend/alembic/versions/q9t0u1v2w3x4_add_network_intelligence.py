"""Add network intelligence tables.

Revision ID: q9t0u1v2w3x4
Revises: q8s9t0u1v2w3
Create Date: 2026-03-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "q9t0u1v2w3x4"
down_revision = "q8s9t0u1v2w3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Network analytics snapshots
    op.create_table(
        "network_analytics_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("snapshot_type", sa.String(50), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("data", JSONB, server_default="{}"),
        sa.Column("tenant_count_included", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_network_snapshot", "network_analytics_snapshots", ["snapshot_type", "snapshot_date"])
    op.create_index("idx_nas_type_date", "network_analytics_snapshots", ["snapshot_type", sa.text("snapshot_date DESC")])

    # Network coverage gaps
    op.create_table(
        "network_coverage_gaps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("county", sa.String(100), nullable=False),
        sa.Column("gap_type", sa.String(30), nullable=False),
        sa.Column("transfer_request_count", sa.Integer(), server_default="0"),
        sa.Column("funeral_home_count", sa.Integer(), server_default="0"),
        sa.Column("platform_licensee_count", sa.Integer(), server_default="0"),
        sa.Column("nearest_licensee_miles", sa.Numeric(6, 1), nullable=True),
        sa.Column("opportunity_score", sa.Numeric(4, 3), nullable=True),
        sa.Column("first_detected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved", sa.Boolean(), server_default="false"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_tenant_id", sa.String(36), nullable=True),
    )
    op.create_unique_constraint("uq_network_gap", "network_coverage_gaps", ["state", "county", "gap_type"])
    op.create_index("idx_ncg_state", "network_coverage_gaps", ["state", "county"])
    op.create_index("idx_ncg_opportunity", "network_coverage_gaps", [sa.text("opportunity_score DESC")])

    # Onboarding pattern data
    op.create_table(
        "onboarding_pattern_data",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_type", sa.String(30), nullable=False),
        sa.Column("checklist_item_key", sa.String(100), nullable=False),
        sa.Column("avg_days_to_complete", sa.Numeric(5, 1), nullable=True),
        sa.Column("median_days_to_complete", sa.Numeric(5, 1), nullable=True),
        sa.Column("completion_rate", sa.Numeric(4, 3), nullable=True),
        sa.Column("abandonment_rate", sa.Numeric(4, 3), nullable=True),
        sa.Column("common_abandonment_point", sa.String(100), nullable=True),
        sa.Column("avg_days_from_signup", sa.Numeric(5, 1), nullable=True),
        sa.Column("tenant_count_sample", sa.Integer(), nullable=True),
        sa.Column("snapshot_month", sa.Date(), nullable=False),
    )
    op.create_unique_constraint("uq_onboarding_pattern", "onboarding_pattern_data", ["tenant_type", "checklist_item_key", "snapshot_month"])

    # Network connection suggestions
    op.create_table(
        "network_connection_suggestions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("suggested_tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("connection_type", sa.String(30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_connection_suggestion", "network_connection_suggestions", ["tenant_id", "suggested_tenant_id", "connection_type"])


def downgrade() -> None:
    op.drop_table("network_connection_suggestions")
    op.drop_table("onboarding_pattern_data")
    op.drop_table("network_coverage_gaps")
    op.drop_table("network_analytics_snapshots")
