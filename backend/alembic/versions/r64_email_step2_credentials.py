"""Phase W-4b Layer 1 Email Step 2 — encrypted credential storage + sync extensions.

Step 1 (r63) created the entity foundation with provider_config as a
plain JSONB column accepting Step 1 placeholder shapes. Step 2 ships
real OAuth + IMAP credential persistence + sync infrastructure, which
needs:

  1. ``email_accounts.encrypted_credentials`` Text column to hold the
     Fernet-encrypted JSON blob (access_token, refresh_token, expiry,
     OR imap_password). Reuses the existing single-master-key Fernet
     pattern from ``app/services/credential_service.py`` (per-row FK
     isolation under platform-wide ``CREDENTIAL_ENCRYPTION_KEY`` env
     var). Per Step 2 canon-clarification: this matches the existing
     canon discipline; the §3.26.15.8 "per-tenant key isolation" prose
     means per-row FK-scoped isolation, not per-tenant key derivation.

  2. ``email_accounts.token_expires_at`` for fast token-refresh
     scheduling (avoids decrypting + parsing JSON every check).

  3. ``email_accounts.last_credential_op_at`` + ``last_credential_op``
     denormalized columns for the credential-status indicator on the
     EmailAccountsPage; full audit trail still in email_audit_log.

  4. ``email_accounts.backfill_days`` + ``email_accounts.backfill_status``
     + ``backfill_progress_pct`` for initial backfill tracking + UI
     progress indicator per §3.26.15.4.

  5. ``email_account_sync_state.consecutive_error_count`` already
     present (Step 1 had ``sync_status`` + ``sync_error_message`` but
     not the counter). Added so the circuit-breaker pattern in the
     sync engine can pause sync after N consecutive failures.

  6. ``email_account_sync_state.last_provider_cursor`` JSONB —
     unified provider-agnostic cursor storage. Supersedes the per-
     provider columns from Step 1 (last_history_id / last_delta_token
     / last_uid) which stay for backward-compat but become advisory.
     Per-provider sync code reads from last_provider_cursor primarily.

  7. ``oauth_state_nonces`` table — short-lived (10-min) signed-state
     records issued at OAuth flow start, validated at callback. CSRF
     protection per Step 2 prompt's discipline gate.

Revision ID: r64_email_step2_credentials
Revises: r63_email_foundation
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision = "r64_email_step2_credentials"
down_revision = "r63_email_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── email_accounts extensions ────────────────────────────────────
    op.add_column(
        "email_accounts",
        sa.Column("encrypted_credentials", sa.Text, nullable=True),
    )
    op.add_column(
        "email_accounts",
        sa.Column(
            "token_expires_at", sa.DateTime(timezone=True), nullable=True
        ),
    )
    op.add_column(
        "email_accounts",
        sa.Column("last_credential_op", sa.String(32), nullable=True),
    )
    op.add_column(
        "email_accounts",
        sa.Column(
            "last_credential_op_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "email_accounts",
        sa.Column(
            "backfill_days",
            sa.Integer,
            nullable=False,
            server_default=sa.text("30"),
        ),
    )
    op.add_column(
        "email_accounts",
        sa.Column(
            "backfill_status",
            sa.String(16),
            nullable=False,
            server_default="not_started",
        ),
    )
    op.add_column(
        "email_accounts",
        sa.Column(
            "backfill_progress_pct",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "email_accounts",
        sa.Column(
            "backfill_started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "email_accounts",
        sa.Column(
            "backfill_completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # ── email_account_sync_state extensions ──────────────────────────
    op.add_column(
        "email_account_sync_state",
        sa.Column(
            "consecutive_error_count",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "email_account_sync_state",
        sa.Column(
            "last_provider_cursor",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "email_account_sync_state",
        sa.Column(
            "sync_in_progress",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # ── oauth_state_nonces (CSRF protection on OAuth flows) ──────────
    op.create_table(
        "oauth_state_nonces",
        sa.Column("nonce", sa.String(64), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider_type", sa.String(32), nullable=False),
        sa.Column("redirect_uri", sa.String(1024), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_oauth_state_nonces_user",
        "oauth_state_nonces",
        ["user_id"],
    )
    op.create_index(
        "ix_oauth_state_nonces_expires",
        "oauth_state_nonces",
        ["expires_at"],
        postgresql_where=sa.text("consumed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("oauth_state_nonces")
    op.drop_column("email_account_sync_state", "sync_in_progress")
    op.drop_column("email_account_sync_state", "last_provider_cursor")
    op.drop_column("email_account_sync_state", "consecutive_error_count")
    op.drop_column("email_accounts", "backfill_completed_at")
    op.drop_column("email_accounts", "backfill_started_at")
    op.drop_column("email_accounts", "backfill_progress_pct")
    op.drop_column("email_accounts", "backfill_status")
    op.drop_column("email_accounts", "backfill_days")
    op.drop_column("email_accounts", "last_credential_op_at")
    op.drop_column("email_accounts", "last_credential_op")
    op.drop_column("email_accounts", "token_expires_at")
    op.drop_column("email_accounts", "encrypted_credentials")
