"""Path B platform_action_tokens — extend canonical linked_entity_type
enum with ``generation_focus_instance`` for Phase 1E.

Per Phase 1E build prompt + r70 substrate consolidation precedent:
``platform_action_tokens.linked_entity_type`` CHECK constraint at r70
locked the canonical enum to the 4 communication primitives
(``email_message, calendar_event, sms_message, phone_call``). Phase 1E
``personalization_studio_family_approval`` ActionTypeDescriptor links
to a Generation Focus instance — the canonical 5th primitive class
consuming Path B (mirrors how Calendar Step 4 / SMS Step 4 / Phone
Step 4 each consume Path B as substrate-consumers per §3.26.16.17 +
§3.26.17.18 + §3.26.18.20).

This migration extends the r70 CHECK constraint to permit
``generation_focus_instance`` as the 5th canonical value. No data
migration required — pre-r77 rows retain their existing values; the
new enum value becomes available for new inserts.

The extension preserves Path B substrate-consolidation discipline per
§3.26.16.17 Phase B Q13 (single canonical action token table with
polymorphic linkage); does NOT introduce a separate
``family_portal_action_tokens`` table per §2.5.4 Anti-pattern 15
(portal authentication-substrate fragmentation rejected).

Revision ID: r77_path_b_generation_focus_extension
Revises: r76_generation_focus_instances
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r77_path_b_generation_focus_extension"
down_revision = "r76_generation_focus_instances"
branch_labels = None
depends_on = None


# Canonical enum values per Phase 1E + Phase 8b/8c/8d/8e/8e.1/8e.2 +
# Calendar Step 4 + Personalization Studio canonical pattern. Keep in
# sync with ``app.services.platform.action_registry.PRIMITIVE_LINKED_ENTITY_TYPES``.
_CANONICAL_LINKED_ENTITY_TYPES = (
    "email_message",
    "calendar_event",
    "sms_message",
    "phone_call",
    "generation_focus_instance",
)


def upgrade() -> None:
    """Drop r70 CHECK constraint + recreate with extended enum."""

    # PostgreSQL canonical pattern: drop + recreate CHECK with new
    # value list. Matches r70's IF EXISTS guard pattern.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_platform_action_tokens_linked_entity_type'
            ) THEN
                ALTER TABLE platform_action_tokens
                DROP CONSTRAINT ck_platform_action_tokens_linked_entity_type;
            END IF;
        END
        $$;
        """
    )

    # Recreate with extended canonical enum (5 values).
    quoted = ", ".join(f"'{v}'" for v in _CANONICAL_LINKED_ENTITY_TYPES)
    op.execute(
        f"""
        ALTER TABLE platform_action_tokens
        ADD CONSTRAINT ck_platform_action_tokens_linked_entity_type
        CHECK (linked_entity_type IN ({quoted}));
        """
    )


def downgrade() -> None:
    """Restore r70 CHECK constraint (4-value enum)."""

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_platform_action_tokens_linked_entity_type'
            ) THEN
                ALTER TABLE platform_action_tokens
                DROP CONSTRAINT ck_platform_action_tokens_linked_entity_type;
            END IF;
        END
        $$;
        """
    )

    # Restore r70's 4-value enum (canonical history continuity).
    r70_quoted = ", ".join(
        f"'{v}'"
        for v in (
            "email_message",
            "calendar_event",
            "sms_message",
            "phone_call",
        )
    )
    op.execute(
        f"""
        ALTER TABLE platform_action_tokens
        ADD CONSTRAINT ck_platform_action_tokens_linked_entity_type
        CHECK (linked_entity_type IN ({r70_quoted}));
        """
    )
