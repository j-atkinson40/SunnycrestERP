"""Substrate consolidation predecessor migration — email_action_tokens
→ platform_action_tokens.

Per Calendar Step 1 discovery Q1 confirmation + §3.26.16.17 Phase B Q13
refinement direction note: substrate consolidation prevents
architectural fragmentation across primitives. Email r66 ships the
canonical action-token table; Calendar Step 4 + SMS Step 4 + Phone
Step 4 inherit the substrate without parallel-table proliferation.

**Operations** (per build prompt):
  1. RENAME TABLE email_action_tokens → platform_action_tokens
  2. RENAME INDEX ix_email_action_tokens_message → ix_platform_action_tokens_linked_entity
  3. RENAME INDEX ix_email_action_tokens_active  → ix_platform_action_tokens_active
  4. RENAME COLUMN message_id → linked_entity_id (preserves all existing data verbatim)
  5. ADD COLUMN linked_entity_type VARCHAR(32) NOT NULL DEFAULT 'email_message'
     (server_default backfills every existing row to 'email_message';
      every existing token IS for an email_message — that's the only
      primitive that shipped action tokens at r66)
  6. DROP CONSTRAINT email_action_tokens_message_id_fkey
     (FK CASCADE replaced with revoked_at discipline per §3.26.16.18
      audit canon — magic-link tokens carry indefinite audit-trail
      value; service-layer cleanup is the canonical path, not hard FK
      cascade)
  7. ADD CHECK CONSTRAINT ck_platform_action_tokens_linked_entity_type
     enumerating all four future primitive values upfront
     ('email_message', 'calendar_event', 'sms_message', 'phone_call')
     so downstream Step 4 arcs inherit substrate without CHECK
     migration overhead (Q2 confirmed pre-build).
  8. DROP DEFAULT on linked_entity_type so future inserts must
     populate explicitly (defensive against caller-side bugs).

**Down-migration** reverses each step in inverse order. Down is
data-preserving — 'email_message' is the only legitimate value in
existing rows, so renaming linked_entity_id → message_id + dropping
linked_entity_type is reversible without data loss.

**Why ALTER, not drop+create**: existing email_action_tokens rows in
production hold 7-day-TTL magic-link audit traces; dropping would
invalidate live tokens. ALTER preserves rows + indexes verbatim.

**No GIN index on email_messages.message_payload touched** — that
index is canonical email-primitive infrastructure regardless of
token-table renames.

Revision ID: r70_platform_action_tokens
Revises: r69_calendar_outbound
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r70_platform_action_tokens"
down_revision = "r69_calendar_outbound"
branch_labels = None
depends_on = None


_LINKED_ENTITY_TYPES = (
    "email_message",
    "calendar_event",
    "sms_message",
    "phone_call",
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Defensive: skip rename if migration is re-applied (idempotency
    # for staging/dev re-runs against a partial state).
    table_names = set(inspector.get_table_names())
    if "email_action_tokens" in table_names and "platform_action_tokens" not in table_names:
        op.rename_table("email_action_tokens", "platform_action_tokens")

    # Re-inspect after potential rename.
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "platform_action_tokens" not in table_names:
        # Migration applied to a schema that has neither table — defensive
        # no-op rather than hard-fail (env.py's idempotent-create patches
        # don't apply to ALTER).
        return

    # 2 + 3. Rename indexes. Use IF EXISTS so re-runs don't error.
    op.execute(
        "ALTER INDEX IF EXISTS ix_email_action_tokens_message "
        "RENAME TO ix_platform_action_tokens_linked_entity"
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_email_action_tokens_active "
        "RENAME TO ix_platform_action_tokens_active"
    )

    # 4. Rename column message_id → linked_entity_id.
    columns = {col["name"] for col in inspector.get_columns("platform_action_tokens")}
    if "message_id" in columns and "linked_entity_id" not in columns:
        op.alter_column(
            "platform_action_tokens",
            "message_id",
            new_column_name="linked_entity_id",
        )

    # 5. Add linked_entity_type with server_default backfill.
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("platform_action_tokens")}
    if "linked_entity_type" not in columns:
        op.add_column(
            "platform_action_tokens",
            sa.Column(
                "linked_entity_type",
                sa.String(32),
                nullable=False,
                server_default="email_message",
            ),
        )

    # 6. Drop FK constraint on the renamed column. PostgreSQL preserves
    # the original constraint name post-rename; drop by canonical name
    # used at r66.
    op.execute(
        "ALTER TABLE platform_action_tokens "
        "DROP CONSTRAINT IF EXISTS email_action_tokens_message_id_fkey"
    )

    # 7. Add CHECK constraint enumerating all four canonical primitive values.
    # Use raw SQL with IF NOT EXISTS-equivalent guard (PG checks via pg_constraint).
    constraint_sql = """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'ck_platform_action_tokens_linked_entity_type'
        ) THEN
            ALTER TABLE platform_action_tokens
            ADD CONSTRAINT ck_platform_action_tokens_linked_entity_type
            CHECK (linked_entity_type IN (
                'email_message', 'calendar_event', 'sms_message', 'phone_call'
            ));
        END IF;
    END
    $$;
    """
    op.execute(constraint_sql)

    # 8. Drop server_default on linked_entity_type — future inserts
    # must populate explicitly. Existing rows retain their backfilled
    # 'email_message' value.
    op.alter_column(
        "platform_action_tokens",
        "linked_entity_type",
        server_default=None,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    if "platform_action_tokens" not in table_names:
        return

    # Reverse step 7: drop CHECK constraint.
    op.execute(
        "ALTER TABLE platform_action_tokens "
        "DROP CONSTRAINT IF EXISTS ck_platform_action_tokens_linked_entity_type"
    )

    # Reverse step 5: drop linked_entity_type column.
    columns = {col["name"] for col in inspector.get_columns("platform_action_tokens")}
    if "linked_entity_type" in columns:
        op.drop_column("platform_action_tokens", "linked_entity_type")

    # Reverse step 4: rename linked_entity_id → message_id.
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("platform_action_tokens")}
    if "linked_entity_id" in columns and "message_id" not in columns:
        op.alter_column(
            "platform_action_tokens",
            "linked_entity_id",
            new_column_name="message_id",
        )

    # Reverse step 6: re-add FK constraint email_messages(id) ON DELETE CASCADE.
    # Defensive: only re-add if column exists + no constraint of same name.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'platform_action_tokens'
                  AND column_name = 'message_id'
            ) AND NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'email_action_tokens_message_id_fkey'
            ) THEN
                ALTER TABLE platform_action_tokens
                ADD CONSTRAINT email_action_tokens_message_id_fkey
                FOREIGN KEY (message_id) REFERENCES email_messages(id)
                ON DELETE CASCADE;
            END IF;
        END
        $$;
        """
    )

    # Reverse steps 2 + 3: rename indexes back.
    op.execute(
        "ALTER INDEX IF EXISTS ix_platform_action_tokens_linked_entity "
        "RENAME TO ix_email_action_tokens_message"
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_platform_action_tokens_active "
        "RENAME TO ix_email_action_tokens_active"
    )

    # Reverse step 1: rename table back.
    op.rename_table("platform_action_tokens", "email_action_tokens")
