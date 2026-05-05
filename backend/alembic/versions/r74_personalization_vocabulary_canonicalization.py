"""Personalization vocabulary canonicalization — Step-0 migration for Personalization Studio implementation arc.

Per §3.26.11.12.19.2 canonical 4-options vocabulary (Path C canon update):

- ``legacy_print`` (unchanged — already canonical)
- ``physical_nameplate`` (canonical refinement of existing ``nameplate`` substrate)
- ``physical_emblem`` (canonical refinement of existing ``cover_emblem`` substrate)
- ``vinyl`` (canonical NEW vocabulary; was ``lifes_reflections``)

Per Q1 + Q2 canonical resolutions at Personalization Studio implementation arc Step 1 build prompt:

- ``vinyl`` is canonical substrate value; per-tenant display label customization preserved.
  Wilbert tenant displays "Life's Reflections" for canonical ``vinyl``; Sunnycrest tenant displays
  "Vinyl"; cross-tenant DocumentShare grant payload carries canonical ``vinyl`` substrate value.
- Per-tenant Workshop Tune mode display label customization stored at
  ``Company.settings_json.personalization_display_labels`` JSONB. No new table — Company.settings_json
  is canonical existing tenant-configuration substrate per CLAUDE.md §4 settings pattern.

Backfill scope (idempotent via value-existence guards):

1. ``case_merchandise.vault_personalization`` JSONB column — rewrite inline JSONB ``type`` field per
   list element: ``nameplate`` → ``physical_nameplate``; ``cover_emblem`` → ``physical_emblem``;
   ``lifes_reflections`` → ``vinyl``. ``legacy_print`` left unchanged.
2. ``order_personalization_task.task_type`` string column — UPDATE string values.
3. ``order_personalization_photo.photo_purpose`` string column — UPDATE parallel string values if any.

Idempotent via WHERE clauses targeting old values only — re-running migration on already-canonicalized
data is no-op.

Service-layer + canonical config layer (``personalization_config.py``,
``pdf_generation_service.py``, ``order_personalization_task.py`` model docstring) updated in same
commit per Step-0 substrate canonicalization scope.

Down-migration reverses backfill canonically — ``physical_nameplate`` → ``nameplate``;
``physical_emblem`` → ``cover_emblem``; ``vinyl`` → ``lifes_reflections``. Down-migration preserves
canonical history continuity for rollback scenarios.

Revision ID: r74_personalization_vocabulary_canonicalization
Revises: r72_ptr_consent_metadata

Note: r73 number is intentionally skipped (canonical-numbering sparsity acceptable per
canonical-restraint discipline; subsequent migrations resume r-numbering canonically).
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text


revision = "r74_personalization_vocabulary_canonicalization"
down_revision = "r72_ptr_consent_metadata"
branch_labels = None
depends_on = None


# Canonical vocabulary mapping per §3.26.11.12.19.2 Path C canon update.
# Map: old_canonical_name → new_canonical_name.
_VOCAB_MAPPING = {
    "nameplate": "physical_nameplate",
    "cover_emblem": "physical_emblem",
    "lifes_reflections": "vinyl",
    # legacy_print unchanged — already canonical.
}

# Inverse mapping for downgrade.
_VOCAB_MAPPING_INVERSE = {v: k for k, v in _VOCAB_MAPPING.items()}


def upgrade() -> None:
    """Backfill canonical vocabulary across substrate sites.

    Three substrate sites carry vocabulary references:
    1. ``case_merchandise.vault_personalization`` JSONB list elements with ``type`` field
    2. ``order_personalization_task.task_type`` string column
    3. ``order_personalization_photo.photo_purpose`` string column (if exists)
    """
    bind = op.get_bind()

    # ===================================================================
    # Site 1: case_merchandise.vault_personalization JSONB rewrite
    # ===================================================================
    # JSONB shape: [{"type": "nameplate", "config": {...}}, ...]
    # Use Postgres JSONB path-update via jsonb_set on each list element by index.
    # Idempotent SQL: only UPDATE rows where any element matches old vocabulary.
    #
    # Postgres-canonical JSONB rewrite pattern: convert array → text → string-replace
    # → cast back to JSONB. Atomic per-row; idempotent (only matches old values).
    for old_value, new_value in _VOCAB_MAPPING.items():
        bind.execute(
            text(
                """
                UPDATE case_merchandise
                SET vault_personalization = (
                    REPLACE(vault_personalization::text, :old_quoted, :new_quoted)
                )::jsonb
                WHERE vault_personalization::text LIKE :match_pattern
                """
            ),
            {
                "old_quoted": f'"type": "{old_value}"',
                "new_quoted": f'"type": "{new_value}"',
                "match_pattern": f'%"type": "{old_value}"%',
            },
        )

    # ===================================================================
    # Site 2: order_personalization_task.task_type string column rewrite
    # ===================================================================
    inspector = _safe_inspector(bind)
    if _table_exists(inspector, "order_personalization_tasks"):
        for old_value, new_value in _VOCAB_MAPPING.items():
            bind.execute(
                text(
                    """
                    UPDATE order_personalization_tasks
                    SET task_type = :new_value
                    WHERE task_type = :old_value
                    """
                ),
                {"old_value": old_value, "new_value": new_value},
            )

    # ===================================================================
    # Site 3: order_personalization_photo.photo_purpose string column rewrite
    # ===================================================================
    if _table_exists(inspector, "order_personalization_photos"):
        photo_columns = {col["name"] for col in inspector.get_columns("order_personalization_photos")}
        if "photo_purpose" in photo_columns:
            for old_value, new_value in _VOCAB_MAPPING.items():
                bind.execute(
                    text(
                        """
                        UPDATE order_personalization_photos
                        SET photo_purpose = :new_value
                        WHERE photo_purpose = :old_value
                        """
                    ),
                    {"old_value": old_value, "new_value": new_value},
                )


def downgrade() -> None:
    """Reverse backfill — canonical history continuity preservation for rollback scenarios."""
    bind = op.get_bind()

    # Reverse Site 1: case_merchandise.vault_personalization JSONB rewrite (inverse mapping)
    for new_value, old_value in _VOCAB_MAPPING_INVERSE.items():
        bind.execute(
            text(
                """
                UPDATE case_merchandise
                SET vault_personalization = (
                    REPLACE(vault_personalization::text, :new_quoted, :old_quoted)
                )::jsonb
                WHERE vault_personalization::text LIKE :match_pattern
                """
            ),
            {
                "new_quoted": f'"type": "{new_value}"',
                "old_quoted": f'"type": "{old_value}"',
                "match_pattern": f'%"type": "{new_value}"%',
            },
        )

    inspector = _safe_inspector(bind)

    # Reverse Site 2: order_personalization_task.task_type string column rewrite
    if _table_exists(inspector, "order_personalization_tasks"):
        for new_value, old_value in _VOCAB_MAPPING_INVERSE.items():
            bind.execute(
                text(
                    """
                    UPDATE order_personalization_tasks
                    SET task_type = :old_value
                    WHERE task_type = :new_value
                    """
                ),
                {"old_value": old_value, "new_value": new_value},
            )

    # Reverse Site 3: order_personalization_photo.photo_purpose string column rewrite
    if _table_exists(inspector, "order_personalization_photos"):
        photo_columns = {col["name"] for col in inspector.get_columns("order_personalization_photos")}
        if "photo_purpose" in photo_columns:
            for new_value, old_value in _VOCAB_MAPPING_INVERSE.items():
                bind.execute(
                    text(
                        """
                        UPDATE order_personalization_photos
                        SET photo_purpose = :old_value
                        WHERE photo_purpose = :new_value
                        """
                    ),
                    {"old_value": old_value, "new_value": new_value},
                )


def _safe_inspector(bind):
    """Return SQLAlchemy inspector — defense against bind without inspector capability."""
    from sqlalchemy import inspect

    return inspect(bind)


def _table_exists(inspector, table_name: str) -> bool:
    """Idempotent existence check for table presence in current schema."""
    try:
        return table_name in inspector.get_table_names()
    except Exception:
        return False
