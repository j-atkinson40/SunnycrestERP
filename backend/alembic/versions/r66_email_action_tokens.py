"""Phase W-4b Layer 1 Email Step 4c — magic-link action tokens.

Single new table: ``email_action_tokens`` — server-side stored signed
token per the existing token canon (``app/services/signing/token_service.py``
+ portal recovery + OAuth state nonces). Each token grants
single-action authorization to a non-Bridgeable recipient at the
magic-link contextual surface.

Per canon §3.26.15.17 + §14.9.5:
  - Token canonical expiry: 7 days from email send time
  - Token scope limited to single action (cannot navigate beyond
    contextual surface)
  - Token consumption on action commit (no reuse)
  - Audit log entry per click + commit (kill-the-portal discipline)

The ``message_payload`` column already exists on email_messages from
Step 1 r63 + supports the canonical action shape per §3.26.15.17.
This migration is only the action-token table; everything else lives
in JSONB on the existing message rows.

Step 4c also adds an index on ``ix_email_messages_payload_actions`` —
GIN index on the message_payload JSONB column for fast lookups by
action_target_type + action_target_id (powers the "all messages
with pending quote_approval for Quote X" query path).

Revision ID: r66_email_action_tokens
Revises: r65_email_outbound
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r66_email_action_tokens"
down_revision = "r65_email_outbound"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_action_tokens",
        sa.Column("token", sa.String(64), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "message_id",
            sa.String(36),
            sa.ForeignKey("email_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action_idx", sa.Integer, nullable=False),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column("recipient_email", sa.String(320), nullable=False),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "consumed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "click_count",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "last_clicked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_email_action_tokens_message",
        "email_action_tokens",
        ["message_id"],
    )
    op.create_index(
        "ix_email_action_tokens_active",
        "email_action_tokens",
        ["expires_at"],
        postgresql_where=sa.text("consumed_at IS NULL AND revoked_at IS NULL"),
    )

    # GIN index on message_payload for action-target lookup
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_email_messages_payload_actions "
        "ON email_messages USING gin (message_payload jsonb_path_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_email_messages_payload_actions")
    op.drop_table("email_action_tokens")
