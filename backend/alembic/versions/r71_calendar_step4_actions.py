"""Calendar Step 4 — actions + cross-tenant pairing semantics.

Per §3.26.16.17 + §3.26.16.20 + Q1/Q2 confirmed pre-build:

  1. ADD COLUMN ``calendar_events.action_payload JSONB DEFAULT '{}'
     NOT NULL`` — Email primitive shape parallel per substrate
     consolidation discipline. Actions live on the calendar_event row
     (not a separate table); platform_action_tokens.linked_entity_id
     points at calendar_events.id; action_idx indexes into
     ``action_payload['actions']``.

  2. ALTER COLUMN ``cross_tenant_event_pairing.paired_at`` to NULLABLE
     — NULL = pending bilateral acceptance; timestamp = finalized
     post-accept. Per Q2 confirmed: single semantic field; no schema
     bloat (avoids parallel pairing_status discriminator).

  3. CREATE GIN INDEX on ``calendar_events.action_payload`` —
     supports cross-primitive action queries (e.g. "all calendar
     events with pending joint_event_acceptance for Tenant X").

Revision ID: r71_calendar_step4_actions
Revises: r70_platform_action_tokens
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r71_calendar_step4_actions"
down_revision = "r70_platform_action_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. ADD COLUMN action_payload JSONB DEFAULT '{}' NOT NULL.
    columns = {col["name"] for col in inspector.get_columns("calendar_events")}
    if "action_payload" not in columns:
        op.add_column(
            "calendar_events",
            sa.Column(
                "action_payload",
                sa.JSON().with_variant(
                    sa.dialects.postgresql.JSONB(), "postgresql"
                ),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )

    # 2. ALTER cross_tenant_event_pairing.paired_at to NULLABLE.
    # Pre-Step-4 default was nullable=False with server_default=now().
    # Step 4 semantics: NULL = pending acceptance; timestamp = finalized.
    op.alter_column(
        "cross_tenant_event_pairing",
        "paired_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )

    # 2b. ALTER cross_tenant_event_pairing.event_b_id to NULLABLE.
    # Pre-Step-4 default was nullable=False. Step 4 semantics: at
    # proposal time the partner tenant has not yet accepted; their
    # CalendarEvent row is created at accept-time. Pending state =
    # event_b_id IS NULL. Set on finalize_pairing.
    op.alter_column(
        "cross_tenant_event_pairing",
        "event_b_id",
        existing_type=sa.String(36),
        nullable=True,
    )

    # 3. CREATE GIN INDEX on action_payload for action-target queries.
    # CONCURRENTLY would be ideal but transactional DDL in alembic env
    # requires synchronous create. Use IF NOT EXISTS guard.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_calendar_events_action_payload "
        "ON calendar_events USING gin (action_payload jsonb_path_ops)"
    )


def downgrade() -> None:
    # Reverse step 3
    op.execute("DROP INDEX IF EXISTS ix_calendar_events_action_payload")

    # Reverse step 2 — restore NOT NULL with default now().
    # Defensive: backfill any NULL paired_at rows to created_at-equivalent
    # before tightening (preserves any pending-state rows as finalized).
    op.execute(
        """
        UPDATE cross_tenant_event_pairing
        SET paired_at = COALESCE(paired_at, NOW())
        WHERE paired_at IS NULL
        """
    )
    op.alter_column(
        "cross_tenant_event_pairing",
        "paired_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )

    # Reverse step 2b — restore event_b_id NOT NULL.
    # Defensive: pending rows (event_b_id IS NULL) cannot survive a
    # downgrade because partner-side event was never created. Drop
    # those rows before re-tightening — the audit log preserves the
    # propose event regardless.
    op.execute(
        """
        DELETE FROM cross_tenant_event_pairing WHERE event_b_id IS NULL
        """
    )
    op.alter_column(
        "cross_tenant_event_pairing",
        "event_b_id",
        existing_type=sa.String(36),
        nullable=False,
    )

    # Reverse step 1
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("calendar_events")}
    if "action_payload" in columns:
        op.drop_column("calendar_events", "action_payload")
