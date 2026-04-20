"""Saved Views Phase 2 — performance indexes + user.preferences column.

Saved views reuse `vault_items` with `item_type='saved_view'` and
store their full config under `vault_items.metadata_json` (see
`backend/app/services/saved_views/types.py` for the schema).

Four changes:

  1. GIN trigram on `vault_items.title`
     Saved views appear in the command bar as VIEW-rank results.
     The Phase 1 command-bar resolver uses pg_trgm similarity for
     fuzzy matching across entity tables (migration r31). We mirror
     that pattern here — fuzzy match on the view's title column so
     "my open cases" resolves even when the user types "open case"
     or "my cases". Uses the same pg_trgm extension r31 installed.

  2. Partial B-tree on `(company_id, created_by)` WHERE
     `item_type='saved_view' AND is_active=true`
     The hot-path query "list this user's saved views" runs on
     every command-bar open + every saved-view page load. A
     partial index skips the ~99% of vault_items rows that are
     not saved views.

  3. Widen `vault_items.source_entity_id` from String(36) → String(128)
     Historical uses were UUID-shaped (delivery IDs, etc.), but
     saved-view seeding encodes semantic seed keys like
     `saved_view_seed:{role_slug}:{template_id}` which routinely
     exceed 36 chars. Widening is backward-compatible — existing
     UUID rows still fit. Same-type (String) so no cast issues on
     rolling deploys.

  4. `users.preferences JSONB DEFAULT '{}'` column
     Generic per-user flag bag. Phase 2 stores
     `saved_views_seeded_for_roles: ["admin", "director", ...]`
     here — array of role names this user has already been seeded
     for. The seed service iterates the user's current roles and
     skips any already in this array. Handles multi-role users,
     role promotions, and future extension-driven seed expansions.
     `DEFAULT '{}'` avoids NULL-handling every read.

Indexes use CREATE INDEX CONCURRENTLY (autocommit_block). The
column add runs in the normal transactional DDL block.

Downgrade drops both indexes + the column. pg_trgm extension left
installed (other callers use it — same note as r31).

Revision ID: r32_saved_view_indexes
Revises: r31_command_bar_trigram_indexes
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision = "r32_saved_view_indexes"
down_revision = "r31_command_bar_trigram_indexes"
branch_labels = None
depends_on = None


_INDEXES = [
    # (index_name, CREATE definition)
    (
        "ix_vault_items_title_trgm",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_vault_items_title_trgm "
        "ON vault_items USING gin (title gin_trgm_ops)",
    ),
    (
        "ix_vault_items_saved_view_owner",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_vault_items_saved_view_owner "
        "ON vault_items (company_id, created_by) "
        "WHERE item_type = 'saved_view' AND is_active = true",
    ),
]


def upgrade() -> None:
    # users.preferences JSONB — add in the normal transaction.
    op.add_column(
        "users",
        sa.Column(
            "preferences",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    # Widen vault_items.source_entity_id for semantic seed keys.
    op.alter_column(
        "vault_items",
        "source_entity_id",
        existing_type=sa.String(36),
        type_=sa.String(128),
        existing_nullable=True,
    )
    # CONCURRENTLY indexes — autocommit block.
    with op.get_context().autocommit_block():
        for _, sql in _INDEXES:
            op.execute(sql)


def downgrade() -> None:
    with op.get_context().autocommit_block():
        # Drop in reverse order; IF EXISTS handles partial rollback.
        for name, _ in reversed(_INDEXES):
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
    # Narrowing would truncate long seed keys; explicit USING cast keeps
    # downgrade safe for UUID-only deployments but will error if any
    # seeded saved-view rows exist. That's intentional — you'd need to
    # delete seeded saved views before downgrading past r32.
    op.alter_column(
        "vault_items",
        "source_entity_id",
        existing_type=sa.String(128),
        type_=sa.String(36),
        existing_nullable=True,
    )
    op.drop_column("users", "preferences")
