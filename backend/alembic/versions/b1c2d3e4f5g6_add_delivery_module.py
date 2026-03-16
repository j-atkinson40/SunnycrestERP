"""Add delivery module tables

Revision ID: b1c2d3e4f5g6
Revises: z0a1b2c3d4e5
Create Date: 2026-03-16

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b1c2d3e4f5g6"
down_revision = "z0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # vehicles
    # ------------------------------------------------------------------
    op.create_table(
        "vehicles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("license_plate", sa.String(20), nullable=True),
        sa.Column("vehicle_type", sa.String(30), nullable=False, server_default="truck"),
        sa.Column("max_weight_lbs", sa.Numeric(10, 2), nullable=True),
        sa.Column("max_stops", sa.Integer, nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ------------------------------------------------------------------
    # drivers
    # ------------------------------------------------------------------
    op.create_table(
        "drivers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("license_number", sa.String(50), nullable=True),
        sa.Column("license_class", sa.String(10), nullable=True),
        sa.Column("license_expiry", sa.Date, nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("preferred_vehicle_id", sa.String(36), sa.ForeignKey("vehicles.id"), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ------------------------------------------------------------------
    # delivery_settings (one per tenant)
    # ------------------------------------------------------------------
    op.create_table(
        "delivery_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, unique=True),
        sa.Column("preset", sa.String(30), nullable=False, server_default="standard"),
        # Workflow toggles
        sa.Column("require_photo_on_delivery", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("require_signature", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("require_weight_ticket", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("require_setup_confirmation", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("require_departure_photo", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("require_mileage_entry", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("allow_partial_delivery", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("allow_driver_resequence", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("track_gps", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("notify_customer_on_dispatch", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("notify_customer_on_arrival", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("notify_customer_on_complete", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("notify_connected_tenant_on_arrival", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("notify_connected_tenant_on_setup", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("enable_driver_messaging", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("enable_delivery_portal", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("auto_create_delivery_from_order", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("auto_invoice_on_complete", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("max_stops_per_route", sa.Integer, nullable=True),
        sa.Column("default_delivery_window_minutes", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ------------------------------------------------------------------
    # deliveries
    # ------------------------------------------------------------------
    op.create_table(
        "deliveries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("delivery_type", sa.String(30), nullable=False),  # funeral_vault, precast, redi_rock
        sa.Column("order_id", sa.String(36), nullable=True, index=True),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("delivery_address", sa.Text, nullable=True),
        sa.Column("delivery_lat", sa.Numeric(10, 7), nullable=True),
        sa.Column("delivery_lng", sa.Numeric(10, 7), nullable=True),
        sa.Column("requested_date", sa.Date, nullable=True),
        sa.Column("required_window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("required_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("type_config", postgresql.JSONB, nullable=True),
        sa.Column("special_instructions", sa.Text, nullable=True),
        sa.Column("weight_lbs", sa.Numeric(10, 2), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ------------------------------------------------------------------
    # delivery_routes
    # ------------------------------------------------------------------
    op.create_table(
        "delivery_routes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("driver_id", sa.String(36), sa.ForeignKey("drivers.id"), nullable=False),
        sa.Column("vehicle_id", sa.String(36), sa.ForeignKey("vehicles.id"), nullable=True),
        sa.Column("route_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_mileage", sa.Numeric(8, 1), nullable=True),
        sa.Column("total_stops", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ------------------------------------------------------------------
    # delivery_stops
    # ------------------------------------------------------------------
    op.create_table(
        "delivery_stops",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("route_id", sa.String(36), sa.ForeignKey("delivery_routes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("delivery_id", sa.String(36), sa.ForeignKey("deliveries.id"), nullable=False),
        sa.Column("sequence_number", sa.Integer, nullable=False),
        sa.Column("estimated_arrival", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estimated_departure", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_arrival", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_departure", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("driver_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ------------------------------------------------------------------
    # delivery_events
    # ------------------------------------------------------------------
    op.create_table(
        "delivery_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("delivery_id", sa.String(36), sa.ForeignKey("deliveries.id"), nullable=False, index=True),
        sa.Column("route_id", sa.String(36), sa.ForeignKey("delivery_routes.id"), nullable=True),
        sa.Column("driver_id", sa.String(36), sa.ForeignKey("drivers.id"), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("lat", sa.Numeric(10, 7), nullable=True),
        sa.Column("lng", sa.Numeric(10, 7), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ------------------------------------------------------------------
    # delivery_media
    # ------------------------------------------------------------------
    op.create_table(
        "delivery_media",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("delivery_id", sa.String(36), sa.ForeignKey("deliveries.id"), nullable=False, index=True),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("delivery_events.id"), nullable=True),
        sa.Column("media_type", sa.String(30), nullable=False),  # photo, signature, weight_ticket
        sa.Column("file_url", sa.Text, nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ------------------------------------------------------------------
    # tenant_notifications
    # ------------------------------------------------------------------
    op.create_table(
        "tenant_notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("source_tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("data", postgresql.JSONB, nullable=True),
        sa.Column("read", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("tenant_notifications")
    op.drop_table("delivery_media")
    op.drop_table("delivery_events")
    op.drop_table("delivery_stops")
    op.drop_table("delivery_routes")
    op.drop_table("deliveries")
    op.drop_table("delivery_settings")
    op.drop_table("drivers")
    op.drop_table("vehicles")
