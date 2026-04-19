"""Bridgeable Documents Phase D-6 — cross-tenant document fabric.

Two new tables:
  document_shares         — one row per (document, target_tenant) grant,
                            with revoked_at timestamp for future-access cutoff
  document_share_events   — append-only audit log of share transitions

Adds `intelligence_executions.caller_document_share_id` for reverse
linkage (the Intelligence symmetric-linkage pattern).

Shares unify 4 ad-hoc cross-tenant mechanisms into one model:
- VaultItem.shared_with_company_ids — stays (VaultItems aren't Documents)
- Cross-tenant statements, delivery confirmations, legacy vault prints,
  training certs, COIs, licensee transfer notifications — all migrate
  to this shared-documents fabric in D-6.

Grant requires an active PlatformTenantRelationship between owner and
target — service-layer check, not a DB constraint (relationships are
bidirectional so the check needs to inspect both directions).

Revocation is future-access-only: revoked shares set `revoked_at` but
stay in the table for audit.

Revision ID: r25_document_sharing
Revises: r24_disinterment_native_signing
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r25_document_sharing"
down_revision = "r24_disinterment_native_signing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── document_shares ────────────────────────────────────────────
    op.create_table(
        "document_shares",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(36),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "owner_company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # "read" is the only permission in D-6. Future phases may add
        # "comment" / "download-only" / etc.
        sa.Column(
            "permission",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'read'"),
        ),
        # Free-form reason shown in the inbox ("Monthly statement",
        # "Delivery confirmation for order INV-42", etc).
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "granted_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "revoked_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "revoked_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        # Source field — which migration/service created this share.
        # Populated on migration-created shares so we can filter later
        # (e.g. "all shares created by the statement-generation path").
        sa.Column("source_module", sa.String(128), nullable=True),
    )
    op.create_index(
        "ix_doc_shares_target_active",
        "document_shares",
        ["target_company_id"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "ix_doc_shares_owner",
        "document_shares",
        ["owner_company_id"],
    )
    op.create_index(
        "ix_doc_shares_document",
        "document_shares",
        ["document_id"],
    )
    # Partial unique — one active share per (document, target). An
    # admin can't grant the same document twice to the same tenant.
    # Revoking then re-granting creates a new row.
    op.execute(
        "CREATE UNIQUE INDEX uq_doc_shares_active_document_target "
        "ON document_shares (document_id, target_company_id) "
        "WHERE revoked_at IS NULL"
    )

    # ── document_share_events ─────────────────────────────────────
    op.create_table(
        "document_share_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "share_id",
            sa.String(36),
            sa.ForeignKey(
                "document_shares.id", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            sa.String(36),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # granted | revoked | accessed | export_downloaded
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column(
            "actor_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "actor_company_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "meta_json",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_doc_share_events_share_created",
        "document_share_events",
        ["share_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_doc_share_events_document",
        "document_share_events",
        ["document_id"],
    )
    op.create_index(
        "ix_doc_share_events_event_type",
        "document_share_events",
        ["event_type"],
    )

    # ── intelligence_executions.caller_document_share_id ──────────
    # Reverse linkage — AI execution triggered by a shared-document action
    op.add_column(
        "intelligence_executions",
        sa.Column(
            "caller_document_share_id",
            sa.String(36),
            sa.ForeignKey(
                "document_shares.id", ondelete="SET NULL"
            ),
            nullable=True,
        ),
    )
    op.execute(
        "CREATE INDEX ix_intel_exec_caller_document_share "
        "ON intelligence_executions (caller_document_share_id) "
        "WHERE caller_document_share_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_intel_exec_caller_document_share")
    op.drop_column(
        "intelligence_executions", "caller_document_share_id"
    )

    op.drop_index(
        "ix_doc_share_events_event_type",
        table_name="document_share_events",
    )
    op.drop_index(
        "ix_doc_share_events_document",
        table_name="document_share_events",
    )
    op.drop_index(
        "ix_doc_share_events_share_created",
        table_name="document_share_events",
    )
    op.drop_table("document_share_events")

    op.execute(
        "DROP INDEX IF EXISTS uq_doc_shares_active_document_target"
    )
    op.drop_index(
        "ix_doc_shares_document", table_name="document_shares"
    )
    op.drop_index("ix_doc_shares_owner", table_name="document_shares")
    op.drop_index(
        "ix_doc_shares_target_active", table_name="document_shares"
    )
    op.drop_table("document_shares")
