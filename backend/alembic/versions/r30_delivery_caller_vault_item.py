"""Bridgeable Vault Phase V-1f — polymorphic delivery attribution.

Adds `caller_vault_item_id` to `document_deliveries` so the Delivery
subsystem can attribute a send to an arbitrary VaultItem — not just
the `document_id` FK that currently exists. This is the last missing
linkage needed to make Delivery truly polymorphic: document_id stays
for sends that ship a canonical Document PDF; caller_vault_item_id
is for sends attached to anything else (a quote VaultItem, a delivery
VaultItem, a compliance-expiry VaultItem, etc).

Partial index on `caller_vault_item_id IS NOT NULL` keeps index size
small — the expectation is most deliveries are document-attached
(V-1c/D-6/D-7 generators all write a Document first, then send).
This column is opt-in for new callers.

Downgrade is clean: drop index + drop column. Any data written to
the column is lost on downgrade, but the column is additive and
nullable so the caller-side rollout is gated on callers actually
setting it.

Revision ID: r30_delivery_caller_vault_item
Revises: r29_notification_safety_merge
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r30_delivery_caller_vault_item"
down_revision = "r29_notification_safety_merge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_deliveries",
        sa.Column(
            "caller_vault_item_id",
            sa.String(36),
            sa.ForeignKey("vault_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_document_deliveries_caller_vault_item_id",
        "document_deliveries",
        ["caller_vault_item_id"],
        postgresql_where=sa.text("caller_vault_item_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_deliveries_caller_vault_item_id",
        table_name="document_deliveries",
    )
    op.drop_column("document_deliveries", "caller_vault_item_id")
