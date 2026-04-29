"""Phase W-4b Layer 1 Email Step 3 — outbound infrastructure foundation.

Single column add: ``email_accounts.outbound_enabled`` (default True).
Per canon §3.26.15.5 ("Per-account outbound requires
account.outbound_enabled"). Tenant admins can disable outbound on a
per-account basis (e.g., a misconfigured Gmail OAuth account where
inbound sync is wanted but outbound should remain off until the
configuration is verified).

Default ``True`` matches operator expectation: most accounts that
complete OAuth + sync are also expected to send. Operators flip to
False on the EmailAccountsPage to disable outbound while keeping
inbound flowing.

No other schema changes — the ingestion + storage discipline from
Step 1 + 2 already supports outbound:
  - ``email_messages.direction`` CHECK accepts ('inbound', 'outbound')
  - ``email_messages.provider_message_id`` partial unique index supports
    deduplication on Sent-folder round-trip
  - ``email_messages.in_reply_to_message_id`` already FK self-references
    for RFC 5322 In-Reply-To threading per §3.26.15.13

Revision ID: r65_email_outbound
Revises: r64_email_step2_credentials
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r65_email_outbound"
down_revision = "r64_email_step2_credentials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "email_accounts",
        sa.Column(
            "outbound_enabled",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("email_accounts", "outbound_enabled")
