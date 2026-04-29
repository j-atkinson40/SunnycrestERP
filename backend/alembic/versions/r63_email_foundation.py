"""Phase W-4b Layer 1 Email Step 1 — entity foundation.

Creates the foundational entity tables for the Email Primitive
(BRIDGEABLE_MASTER §3.26.15). Step 1 ships entities + provider
abstraction stubs + EmailAccount UI; subsequent Steps 2-N (sync,
outbound, inbox, composition, Workshop integration, Intelligence,
cross-tenant native messaging) build atop this foundation.

**Architectural separation from existing transactional email infra:**

The platform already has *transactional-send* infrastructure (Phase D-7
DeliveryService + EmailService + email_sends + document_deliveries).
That infrastructure handles fire-and-forget audit log of one-shot sends
(statement emails, signing invites, briefing notifications, etc) routed
through Resend. It is NOT being touched in this migration.

The Email Primitive (§3.26.15) is *conversation/thread/inbox*
infrastructure — a different architectural concern. Threaded email
conversations between Bridgeable users + external parties, integrated
with Pulse + Focus + Workshop + cross-tenant native messaging. The two
infrastructures coexist:

  - Existing (D-7): "send notification email" → DeliveryService →
    EmailChannel → Resend → email_sends + document_deliveries audit
  - New (W-4b §3.26.15): threaded inbox surface + provider abstraction
    over Gmail API / MS Graph / IMAP / TransactionalSendOnly

Per §3.26.15.6, the future ``TransactionalSendOnlyProvider`` stub
*wraps* existing DeliveryService — it does not replace it. Drafted
emails from ``state-changes-generate-communications`` (§3.26.15.17)
flow through that provider into the existing send path.

**17 tables shipped this migration:**

Account layer:
  1. email_accounts            — per-tenant account config (shared/personal,
                                  provider_type, encrypted credentials)
  2. email_account_access      — (account_id, user_id, access_level) junction
  3. email_account_sync_state  — provider sync cursor + subscription state

Thread/message layer:
  4. email_threads             — Thread entity with cross-tenant marker
  5. email_messages            — Message entity with payload + entity refs
  6. email_attachments         — hybrid storage with promote-to-Vault affordance
  7. email_participants        — per-thread participant resolution
  8. message_participants      — per-message role mapping (from/to/cc/bcc)

Per-user state (§3.26.15.13 Q1 decomposition):
  9. user_message_read         — per-message read state
 10. email_thread_status       — per-thread archive/snooze/replied/flagged

Front-style shared inbox (§3.26.15.19):
 11. internal_comments         — teammate-only thread comments
 12. email_thread_assignment_log — ownership audit trail

Polymorphic linkage (§3.26.15.7):
 13. email_thread_linkages         — thread → entity M:N (cases/orders/etc)
 14. cross_tenant_thread_pairing   — paired-thread junction across tenants

Labels:
 15. email_labels                  — tenant labels
 16. email_thread_labels           — thread ↔ label junction

Audit (§3.26.15.8):
 17. email_audit_log               — per-tenant email-action audit log

Per §3.26.15.13 Q1 decomposition canon: my Session 2 §3.26.15.13 draft
described "email_user_status keyed on (thread_id, user_id)" as a single
conceptual entity. At implementation, this decomposes into TWO tables:
``user_message_read`` (per-message read state — supports re-marking
individual messages unread, standard email UX) plus
``email_thread_status`` (per-thread archive/snooze/replied/flagged
state). The conceptual ``email_user_status`` umbrella holds both.

Cross-tenant masking inheritance hooks present on every table that
crosses tenant boundary (cross_tenant_thread_pairing) — full masking
implementation defers to subsequent steps per §3.25.x discipline.

Revision ID: r63_email_foundation
Revises: r62_cleanup_cross_vertical_saved_views
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision = "r63_email_foundation"
down_revision = "r62_cleanup_cross_vertical_saved_views"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. email_accounts ─────────────────────────────────────────────
    op.create_table(
        "email_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_type",
            sa.String(16),
            nullable=False,
            server_default="shared",
        ),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("email_address", sa.String(320), nullable=False),
        sa.Column(
            "provider_type",
            sa.String(32),
            nullable=False,
        ),
        sa.Column(
            "provider_config",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("signature_html", sa.Text, nullable=True),
        sa.Column("reply_to_override", sa.String(320), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "is_default",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
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
            "account_type IN ('shared', 'personal')",
            name="ck_email_accounts_account_type",
        ),
        sa.CheckConstraint(
            "provider_type IN ('gmail', 'msgraph', 'imap', 'transactional')",
            name="ck_email_accounts_provider_type",
        ),
    )
    op.create_index(
        "ix_email_accounts_tenant",
        "email_accounts",
        ["tenant_id"],
    )
    op.create_index(
        "uq_email_accounts_tenant_email",
        "email_accounts",
        ["tenant_id", "email_address"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )

    # ── 2. email_account_access ───────────────────────────────────────
    op.create_table(
        "email_account_access",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "account_id",
            sa.String(36),
            sa.ForeignKey("email_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "access_level",
            sa.String(16),
            nullable=False,
            server_default="read",
        ),
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
            server_default=sa.func.now(),
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "access_level IN ('read', 'read_write', 'admin')",
            name="ck_email_account_access_level",
        ),
    )
    op.create_index(
        "uq_email_account_access_active",
        "email_account_access",
        ["account_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "ix_email_account_access_user",
        "email_account_access",
        ["user_id"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    # ── 3. email_account_sync_state ───────────────────────────────────
    op.create_table(
        "email_account_sync_state",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "account_id",
            sa.String(36),
            sa.ForeignKey("email_accounts.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_history_id", sa.String(64), nullable=True),
        sa.Column("last_delta_token", sa.String(512), nullable=True),
        sa.Column("last_uid", sa.BigInteger, nullable=True),
        sa.Column(
            "sync_status",
            sa.String(16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("sync_error_message", sa.Text, nullable=True),
        sa.Column(
            "subscription_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("subscription_resource_id", sa.String(255), nullable=True),
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
            name="ck_email_sync_state_status",
        ),
    )

    # ── 4. email_threads ──────────────────────────────────────────────
    op.create_table(
        "email_threads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.String(36),
            sa.ForeignKey("email_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("subject", sa.String(998), nullable=True),
        sa.Column(
            "participants_summary",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "first_message_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_message_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "message_count",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "is_cross_tenant",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "is_archived",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "assigned_to_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
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
    )
    op.create_index(
        "ix_email_threads_tenant_last_message",
        "email_threads",
        ["tenant_id", "last_message_at"],
    )
    op.create_index(
        "ix_email_threads_account_last_message",
        "email_threads",
        ["account_id", "last_message_at"],
    )
    op.create_index(
        "ix_email_threads_assigned",
        "email_threads",
        ["assigned_to_user_id"],
        postgresql_where=sa.text("assigned_to_user_id IS NOT NULL"),
    )
    op.create_index(
        "ix_email_threads_cross_tenant",
        "email_threads",
        ["tenant_id"],
        postgresql_where=sa.text("is_cross_tenant = true"),
    )

    # ── 5. email_messages ─────────────────────────────────────────────
    op.create_table(
        "email_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "thread_id",
            sa.String(36),
            sa.ForeignKey("email_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.String(36),
            sa.ForeignKey("email_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider_message_id", sa.String(512), nullable=True),
        sa.Column(
            "in_reply_to_message_id",
            sa.String(36),
            sa.ForeignKey("email_messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("sender_email", sa.String(320), nullable=False),
        sa.Column("sender_name", sa.String(200), nullable=True),
        sa.Column("subject", sa.String(998), nullable=True),
        sa.Column("body_html", sa.Text, nullable=True),
        sa.Column("body_text", sa.Text, nullable=True),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "direction",
            sa.String(16),
            nullable=False,
        ),
        sa.Column(
            "is_draft",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "is_internal_only",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "message_payload",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "entity_references",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "is_deleted",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
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
            "direction IN ('inbound', 'outbound')",
            name="ck_email_messages_direction",
        ),
    )
    op.create_index(
        "ix_email_messages_thread_received",
        "email_messages",
        ["thread_id", "received_at"],
    )
    op.create_index(
        "ix_email_messages_tenant_received",
        "email_messages",
        ["tenant_id", "received_at"],
    )
    op.create_index(
        "ix_email_messages_provider_id",
        "email_messages",
        ["account_id", "provider_message_id"],
        unique=True,
        postgresql_where=sa.text("provider_message_id IS NOT NULL"),
    )

    # ── 6. email_attachments ──────────────────────────────────────────
    op.create_table(
        "email_attachments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "message_id",
            sa.String(36),
            sa.ForeignKey("email_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(255), nullable=True),
        sa.Column("size_bytes", sa.BigInteger, nullable=True),
        sa.Column("content_id", sa.String(255), nullable=True),
        sa.Column(
            "storage_kind",
            sa.String(16),
            nullable=False,
            server_default="provider",
        ),
        sa.Column("storage_key", sa.String(1024), nullable=True),
        sa.Column(
            "vault_item_id",
            sa.String(36),
            sa.ForeignKey("vault_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "is_inline",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "storage_kind IN ('r2', 'provider', 'vault_item')",
            name="ck_email_attachments_storage_kind",
        ),
    )
    op.create_index(
        "ix_email_attachments_message",
        "email_attachments",
        ["message_id"],
    )
    op.create_index(
        "ix_email_attachments_vault_item",
        "email_attachments",
        ["vault_item_id"],
        postgresql_where=sa.text("vault_item_id IS NOT NULL"),
    )

    # ── 7. email_participants ─────────────────────────────────────────
    op.create_table(
        "email_participants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "thread_id",
            sa.String(36),
            sa.ForeignKey("email_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email_address", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column(
            "resolved_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "resolved_company_entity_id",
            sa.String(36),
            sa.ForeignKey("company_entities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "external_tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "is_internal",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_email_participants_thread",
        "email_participants",
        ["thread_id"],
    )
    op.create_index(
        "ix_email_participants_email",
        "email_participants",
        ["email_address"],
    )
    op.create_index(
        "uq_email_participants_thread_email",
        "email_participants",
        ["thread_id", "email_address"],
        unique=True,
    )

    # ── 8. message_participants ───────────────────────────────────────
    op.create_table(
        "message_participants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "message_id",
            sa.String(36),
            sa.ForeignKey("email_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "participant_id",
            sa.String(36),
            sa.ForeignKey("email_participants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.String(16),
            nullable=False,
        ),
        sa.Column(
            "position",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.CheckConstraint(
            "role IN ('from', 'to', 'cc', 'bcc', 'reply_to')",
            name="ck_message_participants_role",
        ),
    )
    op.create_index(
        "ix_message_participants_message",
        "message_participants",
        ["message_id"],
    )
    op.create_index(
        "ix_message_participants_participant",
        "message_participants",
        ["participant_id"],
    )

    # ── 9. user_message_read ──────────────────────────────────────────
    op.create_table(
        "user_message_read",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "message_id",
            sa.String(36),
            sa.ForeignKey("email_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "read_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "uq_user_message_read",
        "user_message_read",
        ["message_id", "user_id"],
        unique=True,
    )
    op.create_index(
        "ix_user_message_read_user",
        "user_message_read",
        ["user_id"],
    )

    # ── 10. email_thread_status ───────────────────────────────────────
    op.create_table(
        "email_thread_status",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "thread_id",
            sa.String(36),
            sa.ForeignKey("email_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "is_archived",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_snoozed",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "snoozed_until",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "is_replied",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("replied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_flagged",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("flagged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "has_task",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "has_mention",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "uq_email_thread_status",
        "email_thread_status",
        ["thread_id", "user_id"],
        unique=True,
    )
    op.create_index(
        "ix_email_thread_status_user",
        "email_thread_status",
        ["user_id", "is_archived"],
    )
    op.create_index(
        "ix_email_thread_status_snoozed",
        "email_thread_status",
        ["snoozed_until"],
        postgresql_where=sa.text("is_snoozed = true"),
    )

    # ── 11. internal_comments ─────────────────────────────────────────
    op.create_table(
        "internal_comments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "thread_id",
            sa.String(36),
            sa.ForeignKey("email_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("body_text", sa.Text, nullable=False),
        sa.Column(
            "mentioned_user_ids",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "reply_to_comment_id",
            sa.String(36),
            sa.ForeignKey("internal_comments.id", ondelete="SET NULL"),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_internal_comments_thread",
        "internal_comments",
        ["thread_id", "created_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # ── 12. email_thread_assignment_log ───────────────────────────────
    op.create_table(
        "email_thread_assignment_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "thread_id",
            sa.String(36),
            sa.ForeignKey("email_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assigned_from_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "assigned_to_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "changed_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_email_thread_assignment_log_thread",
        "email_thread_assignment_log",
        ["thread_id", "changed_at"],
    )

    # ── 13. email_thread_linkages ─────────────────────────────────────
    op.create_table(
        "email_thread_linkages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "thread_id",
            sa.String(36),
            sa.ForeignKey("email_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("linked_entity_type", sa.String(64), nullable=False),
        sa.Column("linked_entity_id", sa.String(36), nullable=False),
        sa.Column(
            "linkage_source",
            sa.String(32),
            nullable=False,
        ),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column(
            "linked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "linked_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "linkage_source IN ('manual_pre_link', 'manual_post_link', 'intelligence_inferred')",
            name="ck_email_thread_linkages_source",
        ),
    )
    op.create_index(
        "ix_email_thread_linkages_thread",
        "email_thread_linkages",
        ["thread_id"],
        postgresql_where=sa.text("dismissed_at IS NULL"),
    )
    op.create_index(
        "ix_email_thread_linkages_entity",
        "email_thread_linkages",
        ["linked_entity_type", "linked_entity_id"],
        postgresql_where=sa.text("dismissed_at IS NULL"),
    )
    op.create_index(
        "uq_email_thread_linkages_active",
        "email_thread_linkages",
        ["thread_id", "linked_entity_type", "linked_entity_id"],
        unique=True,
        postgresql_where=sa.text("dismissed_at IS NULL"),
    )

    # ── 14. cross_tenant_thread_pairing ───────────────────────────────
    op.create_table(
        "cross_tenant_thread_pairing",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "thread_a_id",
            sa.String(36),
            sa.ForeignKey("email_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "thread_b_id",
            sa.String(36),
            sa.ForeignKey("email_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_a_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_b_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "relationship_id",
            sa.String(36),
            sa.ForeignKey("platform_tenant_relationships.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "paired_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "uq_cross_tenant_thread_pairing",
        "cross_tenant_thread_pairing",
        ["thread_a_id", "thread_b_id"],
        unique=True,
    )
    op.create_index(
        "ix_cross_tenant_thread_pairing_b",
        "cross_tenant_thread_pairing",
        ["thread_b_id"],
    )

    # ── 15. email_labels ──────────────────────────────────────────────
    op.create_table(
        "email_labels",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("color", sa.String(16), nullable=True),
        sa.Column("icon", sa.String(64), nullable=True),
        sa.Column(
            "is_system",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "uq_email_labels_tenant_name",
        "email_labels",
        ["tenant_id", "name"],
        unique=True,
    )

    # ── 16. email_thread_labels ───────────────────────────────────────
    op.create_table(
        "email_thread_labels",
        sa.Column(
            "thread_id",
            sa.String(36),
            sa.ForeignKey("email_threads.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "label_id",
            sa.String(36),
            sa.ForeignKey("email_labels.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "applied_by_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_email_thread_labels_label",
        "email_thread_labels",
        ["label_id"],
    )

    # ── 17. email_audit_log ───────────────────────────────────────────
    op.create_table(
        "email_audit_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=True),
        sa.Column(
            "changes",
            JSONB,
            nullable=True,
        ),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_email_audit_log_tenant_created",
        "email_audit_log",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_email_audit_log_entity",
        "email_audit_log",
        ["entity_type", "entity_id"],
    )


def downgrade() -> None:
    # Drop in reverse-FK order so dependent tables go first.
    op.drop_table("email_audit_log")
    op.drop_table("email_thread_labels")
    op.drop_table("email_labels")
    op.drop_table("cross_tenant_thread_pairing")
    op.drop_table("email_thread_linkages")
    op.drop_table("email_thread_assignment_log")
    op.drop_table("internal_comments")
    op.drop_table("email_thread_status")
    op.drop_table("user_message_read")
    op.drop_table("message_participants")
    op.drop_table("email_participants")
    op.drop_table("email_attachments")
    op.drop_table("email_messages")
    op.drop_table("email_threads")
    op.drop_table("email_account_sync_state")
    op.drop_table("email_account_access")
    op.drop_table("email_accounts")
