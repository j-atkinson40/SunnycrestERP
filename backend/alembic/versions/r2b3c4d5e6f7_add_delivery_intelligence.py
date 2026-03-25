"""Add delivery intelligence tables.

Revision ID: r2b3c4d5e6f7
Revises: r1a2b3c4d5e6
Create Date: 2026-03-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision = "r2b3c4d5e6f7"
down_revision = "r1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Driver profiles
    op.create_table(
        "driver_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("funeral_certified", sa.Boolean(), server_default="true"),
        sa.Column("funeral_daily_rough_capacity", sa.Integer(), server_default="2"),
        sa.Column("can_deliver_wastewater", sa.Boolean(), server_default="false"),
        sa.Column("can_deliver_redi_rock", sa.Boolean(), server_default="false"),
        sa.Column("can_deliver_rosetta", sa.Boolean(), server_default="false"),
        sa.Column("can_deliver_vault", sa.Boolean(), server_default="true"),
        sa.Column("default_working_days", ARRAY(sa.Integer()), server_default="{1,2,3,4,5}"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Delivery capacity blocks
    op.create_table(
        "delivery_capacity_blocks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("block_type", sa.String(20), nullable=False),
        sa.Column("blocked_product_types", ARRAY(sa.String(20)), nullable=False),
        sa.Column("driver_id", sa.String(36), sa.ForeignKey("driver_profiles.id"), nullable=True),
        sa.Column("block_start", sa.Date(), nullable=False),
        sa.Column("block_end", sa.Date(), nullable=False),
        sa.Column("applies_to_days", ARRAY(sa.Integer()), nullable=True),
        sa.Column("reason", sa.Text()),
        sa.Column("suggested_by_agent", sa.Boolean(), server_default="false"),
        sa.Column("suggestion_confidence", sa.Numeric(4, 3)),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("confirmed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("overridden", sa.Boolean(), server_default="false"),
        sa.Column("overridden_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("overridden_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("override_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_dcb_dates", "delivery_capacity_blocks", ["tenant_id", "block_start", "block_end"])

    # Delivery demand forecasts
    op.create_table(
        "delivery_demand_forecasts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("forecast_date", sa.Date(), nullable=False),
        sa.Column("funeral_demand_low", sa.Integer(), nullable=False),
        sa.Column("funeral_demand_high", sa.Integer(), nullable=False),
        sa.Column("funeral_demand_confidence", sa.Numeric(4, 3)),
        sa.Column("confirmed_funerals", sa.Integer(), server_default="0"),
        sa.Column("portal_activity_signal", sa.Numeric(4, 3)),
        sa.Column("historical_pattern_low", sa.Integer()),
        sa.Column("historical_pattern_high", sa.Integer()),
        sa.Column("total_funeral_drivers", sa.Integer()),
        sa.Column("predicted_available_after_funerals_low", sa.Integer()),
        sa.Column("predicted_available_after_funerals_high", sa.Integer()),
        sa.Column("risk_level", sa.String(10), nullable=False),
        sa.Column("recommend_block", sa.Boolean(), server_default="false"),
        sa.Column("recommend_block_reason", sa.Text()),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_forecast_date", "delivery_demand_forecasts", ["tenant_id", "forecast_date"])
    op.create_index("idx_ddf_date", "delivery_demand_forecasts", ["tenant_id", "forecast_date"])

    # Delivery conflict log
    op.create_table(
        "delivery_conflict_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("order_id", sa.String(36), nullable=True),
        sa.Column("delivery_date", sa.Date(), nullable=False),
        sa.Column("product_type", sa.String(20), nullable=False),
        sa.Column("customer_name", sa.String(200)),
        sa.Column("conflict_type", sa.String(30), nullable=False),
        sa.Column("days_until_delivery", sa.Integer(), nullable=False),
        sa.Column("risk_level", sa.String(10), nullable=False),
        sa.Column("confirmed_funerals_that_day", sa.Integer()),
        sa.Column("predicted_funeral_range", sa.String(20)),
        sa.Column("available_driver_estimate", sa.String(20)),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolution_note", sa.Text()),
        sa.Column("alerted_at", sa.DateTime(timezone=True)),
        sa.Column("alert_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_dcl_active", "delivery_conflict_log", ["tenant_id", "status", "delivery_date"])

    # Extension awareness flag
    op.add_column("tenant_settings", sa.Column("delivery_intelligence_enabled", sa.Boolean(), server_default="false"))


def downgrade() -> None:
    op.drop_column("tenant_settings", "delivery_intelligence_enabled")
    op.drop_table("delivery_conflict_log")
    op.drop_table("delivery_demand_forecasts")
    op.drop_table("delivery_capacity_blocks")
    op.drop_table("driver_profiles")
