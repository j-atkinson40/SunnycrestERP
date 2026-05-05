"""Phase W-4b Layer 1 Calendar Step 2 — encrypted credential storage + sync extensions.

Calendar Step 1 (r67) created the entity foundation. Step 1's
``encrypted_credentials`` column was already shipped (Step 1 deviation 4
per ship summary), so Step 2 only needs the lifecycle + backfill
tracking columns + the dedicated ``calendar_account_sync_state`` table
(deferred from Step 1 per Email r64 precedent so Step 2 ships full
canonical shape with extensions in one go).

Mirrors Email r64 column structure with two Calendar-specific divergences:

  - **Asymmetric backfill window** per canonical §3.26.16.4 — Email r64
    shipped symmetric ``backfill_days`` (default 30 past-only); Calendar
    canon specifies "last 90 days + next 365 days" so Step 2 ships
    ``backfill_window_past_days`` (default 90) +
    ``backfill_window_future_days`` (default 365).

  - **`calendar_account_sync_state` ships full Email-r63-plus-r64 shape
    in one new table.** Email shipped sync_state at r63 (Step 1 base
    columns) + extended at r64 (consecutive_error_count +
    last_provider_cursor + sync_in_progress). Calendar Step 1 deferred
    sync_state entirely; Step 2 ships the unified canonical table with
    all columns at once.

  - **REUSES existing ``oauth_state_nonces`` table** (Email r64
    created). Calendar OAuth state nonces fit the same schema:
    nonce + tenant_id + user_id + provider_type + redirect_uri +
    expires_at + consumed_at. provider_type field accepts any string
    (Calendar uses ``google_calendar`` / ``msgraph``; disjoint from
    Email's ``gmail`` / ``msgraph``).

**Columns added to calendar_accounts** (10 total):

  1. ``token_expires_at`` DateTime tz — fast token-refresh scheduling
  2. ``last_credential_op`` String(32) — operation status indicator
  3. ``last_credential_op_at`` DateTime tz — operation timestamp
  4. ``backfill_window_past_days`` Integer (default 90)
  5. ``backfill_window_future_days`` Integer (default 365)
  6. ``backfill_status`` String(16) (default 'not_started')
  7. ``backfill_progress_pct`` Integer (default 0)
  8. ``backfill_started_at`` DateTime tz
  9. ``backfill_completed_at`` DateTime tz
 10. CHECK on ``backfill_status IN ('not_started','in_progress','completed','error')``

**New table**: ``calendar_account_sync_state`` parallel to
``email_account_sync_state``:
  - id PK + account_id FK unique + last_sync_at + last_provider_cursor
    JSONB + sync_in_progress Boolean (mutex) + sync_status String(16)
    + sync_error_message Text + consecutive_error_count Integer +
    subscription_expires_at DateTime tz + subscription_resource_id
    String + created_at + updated_at

Revision ID: r68_calendar_step2_credentials
Revises: r67_calendar_foundation
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision = "r68_calendar_step2_credentials"
down_revision = "r67_calendar_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── calendar_accounts extensions ──────────────────────────────────
    # Note: encrypted_credentials column shipped in r67 Step 1 per Step 1
    # deviation 4 (parallel structure with future Email-r64-style ship
    # without an additional schema change). Step 2 adds the lifecycle +
    # backfill tracking columns.
    op.add_column(
        "calendar_accounts",
        sa.Column(
            "token_expires_at", sa.DateTime(timezone=True), nullable=True
        ),
    )
    op.add_column(
        "calendar_accounts",
        sa.Column("last_credential_op", sa.String(32), nullable=True),
    )
    op.add_column(
        "calendar_accounts",
        sa.Column(
            "last_credential_op_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    # Asymmetric backfill window per §3.26.16.4 canonical "last 90 days
    # + next 365 days." Diverges from Email r64's symmetric backfill_days.
    op.add_column(
        "calendar_accounts",
        sa.Column(
            "backfill_window_past_days",
            sa.Integer,
            nullable=False,
            server_default=sa.text("90"),
        ),
    )
    op.add_column(
        "calendar_accounts",
        sa.Column(
            "backfill_window_future_days",
            sa.Integer,
            nullable=False,
            server_default=sa.text("365"),
        ),
    )
    op.add_column(
        "calendar_accounts",
        sa.Column(
            "backfill_status",
            sa.String(16),
            nullable=False,
            server_default="not_started",
        ),
    )
    op.add_column(
        "calendar_accounts",
        sa.Column(
            "backfill_progress_pct",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "calendar_accounts",
        sa.Column(
            "backfill_started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "calendar_accounts",
        sa.Column(
            "backfill_completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    # CHECK constraint for backfill_status state machine.
    op.create_check_constraint(
        "ck_calendar_accounts_backfill_status",
        "calendar_accounts",
        "backfill_status IN ('not_started', 'in_progress', 'completed', 'error')",
    )

    # ── calendar_account_sync_state ───────────────────────────────────
    # Parallel Email's email_account_sync_state shipped at r63 + extended
    # at r64. Calendar ships full canonical shape in one go.
    op.create_table(
        "calendar_account_sync_state",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "account_id",
            sa.String(36),
            sa.ForeignKey("calendar_accounts.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        # Provider-agnostic cursor JSONB; per-provider shape:
        #   - Google: {"sync_token": "..."}
        #   - MS Graph: {"delta_token": "https://graph.microsoft.com/...delta..."}
        sa.Column(
            "last_provider_cursor",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "sync_in_progress",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "sync_status",
            sa.String(16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("sync_error_message", sa.Text, nullable=True),
        sa.Column(
            "consecutive_error_count",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        # Subscription lifecycle for webhook-based realtime (Step 2 stubs;
        # real subscription provisioning ships in Step 2.1).
        sa.Column(
            "subscription_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "subscription_resource_id",
            sa.String(255),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "sync_status IN ('pending', 'syncing', 'synced', 'error')",
            name="ck_calendar_sync_state_status",
        ),
    )


def downgrade() -> None:
    op.drop_table("calendar_account_sync_state")
    op.drop_constraint(
        "ck_calendar_accounts_backfill_status",
        "calendar_accounts",
        type_="check",
    )
    op.drop_column("calendar_accounts", "backfill_completed_at")
    op.drop_column("calendar_accounts", "backfill_started_at")
    op.drop_column("calendar_accounts", "backfill_progress_pct")
    op.drop_column("calendar_accounts", "backfill_status")
    op.drop_column("calendar_accounts", "backfill_window_future_days")
    op.drop_column("calendar_accounts", "backfill_window_past_days")
    op.drop_column("calendar_accounts", "last_credential_op_at")
    op.drop_column("calendar_accounts", "last_credential_op")
    op.drop_column("calendar_accounts", "token_expires_at")
