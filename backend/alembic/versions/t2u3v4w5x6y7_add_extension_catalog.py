"""Add extension catalog tables.

Revision ID: t2u3v4w5x6y7
Revises: s1a2f3e4t5y6
Create Date: 2026-03-17

Expands the extension_definitions table with catalog metadata
(tagline, category, screenshots, etc.) and adds extension_notify_requests
and extension_activity_log tables.
"""

from alembic import op
import sqlalchemy as sa

revision = "t2u3v4w5x6y7"
down_revision = "s1a2f3e4t5y6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Expand extension_definitions into a full catalog ──────────────
    op.add_column("extension_definitions", sa.Column("tagline", sa.String(300), nullable=True))
    op.add_column("extension_definitions", sa.Column(
        "category", sa.String(40), nullable=False, server_default="workflow",
    ))
    op.add_column("extension_definitions", sa.Column(
        "publisher", sa.String(30), nullable=False, server_default="first_party",
    ))
    op.add_column("extension_definitions", sa.Column("applicable_verticals", sa.Text, nullable=True))
    op.add_column("extension_definitions", sa.Column("default_enabled_for", sa.Text, nullable=True))
    op.add_column("extension_definitions", sa.Column(
        "access_model", sa.String(30), nullable=False, server_default="included",
    ))
    op.add_column("extension_definitions", sa.Column("required_plan_tier", sa.String(40), nullable=True))
    op.add_column("extension_definitions", sa.Column("addon_price_monthly", sa.Numeric(10, 2), nullable=True))
    op.add_column("extension_definitions", sa.Column(
        "status", sa.String(30), nullable=False, server_default="active",
    ))
    op.add_column("extension_definitions", sa.Column("screenshots", sa.Text, nullable=True))
    op.add_column("extension_definitions", sa.Column("feature_bullets", sa.Text, nullable=True))
    op.add_column("extension_definitions", sa.Column("setup_required", sa.Boolean, server_default="false", nullable=False))
    op.add_column("extension_definitions", sa.Column("setup_config_schema", sa.Text, nullable=True))
    op.add_column("extension_definitions", sa.Column("hooks_registered", sa.Text, nullable=True))
    op.add_column("extension_definitions", sa.Column("sort_order", sa.Integer, server_default="100", nullable=False))
    op.add_column("extension_definitions", sa.Column("requested_by_tenant_id", sa.String(36), nullable=True))
    op.add_column("extension_definitions", sa.Column("is_customer_requested", sa.Boolean, server_default="false", nullable=False))
    op.add_column("extension_definitions", sa.Column("notify_me_count", sa.Integer, server_default="0", nullable=False))
    op.add_column("extension_definitions", sa.Column(
        "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True,
    ))

    # ── Expand tenant_extensions with status, disabled tracking, version ──
    op.add_column("tenant_extensions", sa.Column(
        "status", sa.String(30), nullable=False, server_default="active",
    ))
    op.add_column("tenant_extensions", sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tenant_extensions", sa.Column("disabled_by", sa.String(36), nullable=True))
    op.add_column("tenant_extensions", sa.Column("configuration", sa.Text, nullable=True))
    op.add_column("tenant_extensions", sa.Column("version_at_install", sa.String(20), nullable=True))
    op.add_column("tenant_extensions", sa.Column("extension_id", sa.String(36), nullable=True))

    # ── extension_notify_requests ──
    op.create_table(
        "extension_notify_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("extension_id", sa.String(36), sa.ForeignKey("extension_definitions.id"), nullable=False),
        sa.Column("employee_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "extension_id", name="uq_notify_tenant_extension"),
    )

    # ── extension_activity_log ──
    op.create_table(
        "extension_activity_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("extension_id", sa.String(36), sa.ForeignKey("extension_definitions.id"), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("performed_by", sa.String(36), nullable=True),
        sa.Column("details", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("extension_activity_log")
    op.drop_table("extension_notify_requests")

    # Remove tenant_extensions columns
    op.drop_column("tenant_extensions", "extension_id")
    op.drop_column("tenant_extensions", "version_at_install")
    op.drop_column("tenant_extensions", "configuration")
    op.drop_column("tenant_extensions", "disabled_by")
    op.drop_column("tenant_extensions", "disabled_at")
    op.drop_column("tenant_extensions", "status")

    # Remove extension_definitions columns
    op.drop_column("extension_definitions", "updated_at")
    op.drop_column("extension_definitions", "notify_me_count")
    op.drop_column("extension_definitions", "is_customer_requested")
    op.drop_column("extension_definitions", "requested_by_tenant_id")
    op.drop_column("extension_definitions", "sort_order")
    op.drop_column("extension_definitions", "hooks_registered")
    op.drop_column("extension_definitions", "setup_config_schema")
    op.drop_column("extension_definitions", "setup_required")
    op.drop_column("extension_definitions", "feature_bullets")
    op.drop_column("extension_definitions", "screenshots")
    op.drop_column("extension_definitions", "status")
    op.drop_column("extension_definitions", "addon_price_monthly")
    op.drop_column("extension_definitions", "required_plan_tier")
    op.drop_column("extension_definitions", "access_model")
    op.drop_column("extension_definitions", "default_enabled_for")
    op.drop_column("extension_definitions", "applicable_verticals")
    op.drop_column("extension_definitions", "publisher")
    op.drop_column("extension_definitions", "category")
    op.drop_column("extension_definitions", "tagline")
