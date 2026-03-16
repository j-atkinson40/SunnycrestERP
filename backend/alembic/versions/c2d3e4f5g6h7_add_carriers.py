"""Add carriers table and carrier fields to deliveries/events/settings

Revision ID: c2d3e4f5g6h7
Revises: b1c2d3e4f5g6
Create Date: 2026-03-16

"""

import uuid

from alembic import op
import sqlalchemy as sa

revision = "c2d3e4f5g6h7"
down_revision = "b1c2d3e4f5g6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # carriers
    # ------------------------------------------------------------------
    op.create_table(
        "carriers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("contact_name", sa.String(100), nullable=True),
        sa.Column("contact_phone", sa.String(30), nullable=True),
        sa.Column("contact_email", sa.String(200), nullable=True),
        sa.Column("carrier_type", sa.String(20), nullable=False, server_default="own_fleet"),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ------------------------------------------------------------------
    # deliveries — add carrier fields
    # ------------------------------------------------------------------
    op.add_column("deliveries", sa.Column("carrier_id", sa.String(36), sa.ForeignKey("carriers.id"), nullable=True))
    op.add_column("deliveries", sa.Column("carrier_tracking_reference", sa.String(100), nullable=True))

    # ------------------------------------------------------------------
    # delivery_events — add source field
    # ------------------------------------------------------------------
    op.add_column("delivery_events", sa.Column("source", sa.String(30), nullable=True, server_default="driver"))

    # ------------------------------------------------------------------
    # delivery_settings — add carrier toggles
    # ------------------------------------------------------------------
    op.add_column("delivery_settings", sa.Column("sms_carrier_updates", sa.Boolean, nullable=False, server_default=sa.text("false")))
    op.add_column("delivery_settings", sa.Column("carrier_portal", sa.Boolean, nullable=False, server_default=sa.text("false")))

    # ------------------------------------------------------------------
    # Seed carrier feature flags
    # ------------------------------------------------------------------
    flags_table = sa.table(
        "feature_flags",
        sa.column("id", sa.String),
        sa.column("key", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("category", sa.String),
        sa.column("default_enabled", sa.Boolean),
        sa.column("is_global", sa.Boolean),
    )
    op.bulk_insert(flags_table, [
        {
            "id": str(uuid.uuid4()),
            "key": "sms_carrier_updates",
            "name": "SMS Carrier Updates",
            "description": "Enable SMS-based carrier status updates via Twilio keyword replies (PICKED/DELIVERED/ISSUE).",
            "category": "delivery",
            "default_enabled": False,
            "is_global": False,
        },
        {
            "id": str(uuid.uuid4()),
            "key": "carrier_portal",
            "name": "Carrier Portal",
            "description": "Enable external carrier portal with simplified delivery view and status update buttons.",
            "category": "delivery",
            "default_enabled": False,
            "is_global": False,
        },
    ])


def downgrade() -> None:
    op.execute("DELETE FROM feature_flags WHERE key IN ('sms_carrier_updates', 'carrier_portal')")
    op.drop_column("delivery_settings", "carrier_portal")
    op.drop_column("delivery_settings", "sms_carrier_updates")
    op.drop_column("delivery_events", "source")
    op.drop_column("deliveries", "carrier_tracking_reference")
    op.drop_column("deliveries", "carrier_id")
    op.drop_table("carriers")
