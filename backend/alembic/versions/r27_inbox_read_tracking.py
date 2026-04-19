"""Bridgeable Documents Phase D-8 — per-user inbox read tracking.

One tiny table: `document_share_reads(share_id, user_id, read_at)`.

Each admin sees their own inbox unread count — marking a share "read"
is a per-user state, not a per-tenant state. Two admins on the same
tenant can independently work through the same shared documents.

Keyed on the composite (share_id, user_id); no separate surrogate
id. Idempotent upsert on mark-read (insert … on conflict do nothing,
or update read_at to MAX — we pick the simplest: first-read wins).

Revoking a share doesn't delete the read rows — we keep them so the
audit view can still show "read before revocation" truth. Cascade
lives on share_id → document_shares.id so that if a share is ever
hard-deleted (not something the service does, but the FK keeps the
table honest), the read rows follow.

Revision ID: r27_inbox_read_tracking
Revises: r26_delivery_abstraction
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r27_inbox_read_tracking"
down_revision = "r26_delivery_abstraction"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_share_reads",
        sa.Column(
            "share_id",
            sa.String(36),
            sa.ForeignKey("document_shares.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "read_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint(
            "share_id", "user_id", name="pk_document_share_reads"
        ),
    )
    # Per-user lookup on inbox render: "which shares has user X read?"
    op.create_index(
        "ix_document_share_reads_user",
        "document_share_reads",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_share_reads_user", table_name="document_share_reads"
    )
    op.drop_table("document_share_reads")
