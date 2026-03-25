"""Add behavioral analytics layer.

Revision ID: q7r8s9t0u1v2
Revises: q6p7q8r9s0t1
Create Date: 2026-03-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "q7r8s9t0u1v2"
down_revision = "q6p7q8r9s0t1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Behavioral events
    op.create_table(
        "behavioral_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("event_category", sa.String(30), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=True),
        sa.Column("entity_id", sa.String(36), nullable=True),
        sa.Column("secondary_entity_type", sa.String(30), nullable=True),
        sa.Column("secondary_entity_id", sa.String(36), nullable=True),
        sa.Column("caused_by_event_id", sa.String(36), sa.ForeignKey("behavioral_events.id"), nullable=True),
        sa.Column("event_data", JSONB, server_default="{}"),
        sa.Column("actor_type", sa.String(20), server_default="agent"),
        sa.Column("actor_id", sa.String(36), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("outcome_measured", sa.Boolean(), server_default="false"),
        sa.Column("outcome_measured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_be_tenant_occurred", "behavioral_events", ["tenant_id", sa.text("occurred_at DESC")])
    op.create_index("idx_be_entity", "behavioral_events", ["entity_type", "entity_id"])
    op.create_index("idx_be_type", "behavioral_events", ["tenant_id", "event_type"])

    # Behavioral insights
    op.create_table(
        "behavioral_insights",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("insight_type", sa.String(60), nullable=False),
        sa.Column("scope", sa.String(20), server_default="tenant"),
        sa.Column("scope_entity_type", sa.String(30), nullable=True),
        sa.Column("scope_entity_id", sa.String(36), nullable=True),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("supporting_data", JSONB, server_default="{}"),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("action_type", sa.String(30), nullable=True),
        sa.Column("action_label", sa.Text(), nullable=True),
        sa.Column("action_url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("first_surfaced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_by", sa.String(36), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissal_reason", sa.String(30), nullable=True),
        sa.Column("suppressed_until", sa.Date(), nullable=True),
        sa.Column("generated_by_job", sa.String(60), nullable=True),
        sa.Column("data_period_start", sa.Date(), nullable=True),
        sa.Column("data_period_end", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_bi_tenant_status", "behavioral_insights", ["tenant_id", "status"])

    # Insight feedback
    op.create_table(
        "insight_feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("insight_id", sa.String(36), sa.ForeignKey("behavioral_insights.id"), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("feedback_type", sa.String(20), nullable=False),
        sa.Column("feedback_note", sa.Text(), nullable=True),
        sa.Column("outcome_positive", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Entity behavioral profiles
    op.create_table(
        "entity_behavioral_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        # Customer profile fields
        sa.Column("avg_days_to_pay", sa.Numeric(5, 1), nullable=True),
        sa.Column("payment_consistency_score", sa.Numeric(4, 3), nullable=True),
        sa.Column("discount_uptake_rate", sa.Numeric(4, 3), nullable=True),
        sa.Column("collections_response_rate", sa.Numeric(4, 3), nullable=True),
        sa.Column("preferred_contact_day", sa.Integer(), nullable=True),
        sa.Column("finance_charge_forgiveness_rate", sa.Numeric(4, 3), nullable=True),
        sa.Column("relationship_health_score", sa.Numeric(4, 3), nullable=True),
        sa.Column("relationship_health_trend", sa.String(10), nullable=True),
        sa.Column("last_order_date", sa.Date(), nullable=True),
        sa.Column("order_frequency_days", sa.Numeric(5, 1), nullable=True),
        # Vendor profile fields
        sa.Column("on_time_delivery_rate", sa.Numeric(4, 3), nullable=True),
        sa.Column("invoice_accuracy_rate", sa.Numeric(4, 3), nullable=True),
        sa.Column("avg_price_variance_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("price_trend", sa.String(10), nullable=True),
        sa.Column("discrepancy_resolution_days", sa.Numeric(5, 1), nullable=True),
        sa.Column("last_computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "entity_type", "entity_id", name="uq_entity_profile"),
    )
    op.create_index("idx_ebp_lookup", "entity_behavioral_profiles", ["tenant_id", "entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_table("entity_behavioral_profiles")
    op.drop_table("insight_feedback")
    op.drop_table("behavioral_insights")
    op.drop_table("behavioral_events")
