"""Bridgeable Vault Phase V-1d — merge SafetyAlert into Notification.

Clean break: SafetyAlert table dropped, existing rows data-migrated
into Notification with category='safety_alert'. No production data
was created by in-app code (the original SafetyAlert writers were
never wired), so in practice the data migration is a no-op on most
tenants; it's there for safety if any tenant has rows from manual
seeding / testing.

Notification schema extended with 6 optional columns that preserve
the alert-flavor semantics that SafetyAlert had:
  - severity              (critical | high | medium | low)
  - due_date              (DateTime tz — when the thing expires)
  - acknowledged_by_user_id + acknowledged_at (resolution metadata)
  - source_reference_type + source_reference_id (polymorphic linkage
    to the thing the notification is about — keeps SafetyAlert's
    reference_type / reference_id semantics for future callers)

Downgrade is schema-only — data from before the migration is not
restorable since SafetyAlert rows will have been merged into
Notification + the SafetyAlert table dropped. The downgrade recreates
an empty safety_alerts table so a rollback doesn't leave orphaned
foreign-key references, but alert content is lost.

Revision ID: r29_notification_safety_merge
Revises: r28_d9_quote_wilbert_templates
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r29_notification_safety_merge"
down_revision = "r28_d9_quote_wilbert_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Extend notifications with alert-flavor columns ──────────
    op.add_column(
        "notifications",
        sa.Column("severity", sa.String(16), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column(
            "due_date",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "notifications",
        sa.Column(
            "acknowledged_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "notifications",
        sa.Column(
            "acknowledged_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "notifications",
        sa.Column("source_reference_type", sa.String(64), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("source_reference_id", sa.String(255), nullable=True),
    )

    # ── 2. Data-migrate SafetyAlert rows into Notification ─────────
    # Fan-out to every admin user in the same tenant. If a tenant has
    # multiple admins, each gets their own Notification. If no admins,
    # the CROSS JOIN LATERAL produces zero rows for that alert — the
    # alert content is lost but the migration doesn't fail.
    #
    # Users don't have a `role` column; they have a `role_id` FK to
    # `roles.slug` so the admin filter joins through roles.
    #
    # Type coercion: SafetyAlert.severity (high|medium|...) → a
    # Notification.type UI tone (error|warning|info). Keeps the
    # original severity in the new severity column for detail views.
    # Also: SafetyAlert.due_date was Date; notification.due_date is
    # DateTime — cast appropriately.
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "safety_alerts" in inspector.get_table_names():
        conn.execute(
            sa.text(
                """
                INSERT INTO notifications (
                    id,
                    company_id,
                    user_id,
                    title,
                    message,
                    type,
                    category,
                    link,
                    is_read,
                    created_at,
                    severity,
                    due_date,
                    acknowledged_by_user_id,
                    acknowledged_at,
                    source_reference_type,
                    source_reference_id
                )
                SELECT
                    gen_random_uuid()::varchar(36),
                    sa.company_id,
                    u.id AS user_id,
                    CONCAT(sa.alert_type, ': ', COALESCE(LEFT(sa.message, 150), '')) AS title,
                    sa.message,
                    CASE
                        WHEN sa.severity = 'critical' THEN 'error'
                        WHEN sa.severity = 'high' THEN 'warning'
                        ELSE 'info'
                    END AS type,
                    'safety_alert' AS category,
                    CASE
                        WHEN sa.reference_type IS NOT NULL AND sa.reference_id IS NOT NULL
                        THEN CONCAT('/safety/', sa.reference_type, '/', sa.reference_id)
                        ELSE '/safety'
                    END AS link,
                    (sa.acknowledged_at IS NOT NULL) AS is_read,
                    sa.created_at,
                    sa.severity,
                    CASE
                        WHEN sa.due_date IS NOT NULL
                        THEN sa.due_date::timestamptz
                        ELSE NULL
                    END AS due_date,
                    sa.acknowledged_by AS acknowledged_by_user_id,
                    sa.acknowledged_at,
                    sa.reference_type AS source_reference_type,
                    sa.reference_id AS source_reference_id
                FROM safety_alerts sa
                INNER JOIN users u ON u.company_id = sa.company_id
                INNER JOIN roles r ON r.id = u.role_id
                WHERE r.slug = 'admin' AND u.is_active = TRUE
                """
            )
        )

        # ── 3. Drop the safety_alerts table ────────────────────────
        op.drop_table("safety_alerts")


def downgrade() -> None:
    # Schema-only rollback. Pre-migration SafetyAlert data is NOT
    # restorable — the data was merged into notifications and those
    # notifications stay where they are.
    op.create_table(
        "safety_alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("alert_type", sa.String(50)),
        sa.Column("severity", sa.String(20)),
        sa.Column("reference_id", sa.String(36), nullable=True),
        sa.Column("reference_type", sa.String(50), nullable=True),
        sa.Column("message", sa.Text()),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column(
            "acknowledged_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "acknowledged_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )
    op.drop_column("notifications", "source_reference_id")
    op.drop_column("notifications", "source_reference_type")
    op.drop_column("notifications", "acknowledged_at")
    op.drop_column("notifications", "acknowledged_by_user_id")
    op.drop_column("notifications", "due_date")
    op.drop_column("notifications", "severity")
