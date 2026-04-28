"""Phase W-4a Step 3 (Layer 6) — Cross-vertical saved-view cleanup.

Removes already-seeded cross-vertical saved views from existing
tenants' ``vault_items``. Pattern A (BRIDGEABLE_MASTER §3.25 saved
view vertical-scope inheritance amendment) blocks NEW cross-vertical
saved views at three layers (seed/creation/read) — this migration
cleans up the pre-Step-3 contamination.

**Audit findings (dev DB proxy, prod likely similar):**
  - 75 saved views with ``entity_type=fh_case`` in manufacturing
    tenants — leftover from the pre-Step-1 ``(manufacturing, admin)``
    seed entry that has since been removed.
  - 0 ``fh_case`` saved views in cemetery tenants (not yet logged-in
    after the Phase 8e seed shipped, OR the seed was never applied
    in dev because dev DB has no cemetery tenants).
  - 0 ``fh_case`` saved views in crematory tenants (same).

**Cleanup strategy:**

DELETE WHERE the saved-view's ``entity_type`` is in a single-
vertical entity set AND the tenant's vertical doesn't match. Today
the only single-vertical entity is ``fh_case`` (per the Phase W-4a
Step 3 audit of the entity registry); the migration explicitly
enumerates the (vertical, entity_type) prohibited pairs so future
single-vertical entities require an explicit migration update —
fail-loud rather than silent matrix expansion.

**Idempotency:** the migration is idempotent. Running twice is safe
because the second run finds 0 rows matching the prohibited-pair
set (everything was deleted on the first run). The down-migration
is a no-op — restoring deleted contamination would re-introduce
the bug.

**Production safety:**
  - Hard DELETE on ``vault_items`` (not soft via ``is_active=false``).
    The data IS contamination; preserving it via soft-delete leaves
    it visible in admin queries that don't honor ``is_active``.
  - Limited to ``item_type='saved_view'`` rows so unrelated VaultItem
    rows (events, communications, documents, etc.) are untouched.
  - Tenant scoping enforced via JOIN to ``companies.vertical``.
  - No CASCADE — VaultItem has no children that depend on a saved-
    view row beyond the ``user_widget_layouts`` table which keys on
    widget_id (not view_id) and gracefully handles missing instances
    via the SavedViewWidget empty-state path.

**Reversibility:** down() is intentionally a no-op. Restoring the
contamination would re-introduce the bug; if a deployment needs to
reverse Step 3, the application code's seed/creation/read enforcement
must be reverted first, then the prohibited-pair set revisited.

**Migration head:** r61_user_work_areas_pulse_signals → r62.
"""

from __future__ import annotations

import logging

from alembic import op


revision = "r62_cleanup_cross_vertical_saved_views"
down_revision = "r61_user_work_areas_pulse_signals"
branch_labels = None
depends_on = None


logger = logging.getLogger("alembic.runtime.migration")


# Prohibited (entity_type, NOT-IN-vertical) pairs.
#
# Each entry: a single-vertical entity_type + the verticals where it
# is meaningful. Any saved view with this entity_type in a tenant
# whose vertical is NOT in the allowed list is contamination and
# gets deleted.
#
# Mirrors the entity registry's ``allowed_verticals`` (Phase W-4a
# Step 3, Layer 1) at the migration boundary. New single-vertical
# entities require an explicit additional pair here — the registry
# isn't queryable from a migration safely (model imports + state
# coupling), so the pair list is duplicated deliberately.
_PROHIBITED_PAIRS: list[tuple[str, list[str]]] = [
    # fh_case is funeral_home-only.
    ("fh_case", ["funeral_home"]),
]


def upgrade() -> None:
    """Delete cross-vertical saved-view contamination."""
    conn = op.get_bind()
    total_deleted = 0
    for entity_type, allowed_verticals in _PROHIBITED_PAIRS:
        # Build "NOT IN ('a', 'b', ...)" clause via parameterized query
        # — psycopg2 doesn't bind a list directly to NOT IN, so we
        # build the placeholders explicitly. Inputs are hard-coded
        # constants from this file's _PROHIBITED_PAIRS literal, so no
        # injection surface.
        placeholders = ", ".join(
            f":vert_{i}" for i in range(len(allowed_verticals))
        )
        params: dict = {f"vert_{i}": v for i, v in enumerate(allowed_verticals)}
        params["entity_type"] = entity_type

        # Postgres-safe: cast metadata_json to json before traversing
        # JSONB path. Some pre-V-1d rows were inserted as plain dicts
        # via SQLAlchemy's JSONB serializer, but all current rows
        # support the ``->`` operator regardless.
        sql = f"""
            DELETE FROM vault_items vi
            USING companies c
            WHERE vi.company_id = c.id
              AND vi.item_type = 'saved_view'
              AND (vi.metadata_json::json
                   -> 'saved_view_config'
                   -> 'query'
                   ->> 'entity_type') = :entity_type
              AND c.vertical NOT IN ({placeholders})
        """
        result = conn.execute(__import__("sqlalchemy").text(sql), params)
        rowcount = getattr(result, "rowcount", 0) or 0
        total_deleted += rowcount
        logger.info(
            "r62 cross-vertical cleanup: entity_type=%s allowed=%s "
            "deleted=%d rows",
            entity_type,
            allowed_verticals,
            rowcount,
        )

    logger.info(
        "r62 cross-vertical cleanup complete: %d total saved-view "
        "rows deleted (cross-vertical contamination)",
        total_deleted,
    )


def downgrade() -> None:
    """No-op — restoring deleted contamination would re-introduce
    the bug. To reverse Step 3, revert the application-code
    enforcement first, then re-evaluate."""
    pass
