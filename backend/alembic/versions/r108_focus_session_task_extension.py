"""Focus session task extension — focus_sessions.task_id FK to vault_items.

Ships the r108 Focus extension column per task substrate v1 build prompt §7.5
+ state doc §5.7 (Focus extension architectural specification).

Schema change:

1. **focus_sessions.task_id column.** New nullable FK column referencing
   vault_items.id with ON DELETE SET NULL. Forward-only: existing
   focus_sessions retain task_id=NULL; v1.5 B2/B3 work populates for
   newly-created sessions at task-creation time.

   Column type matches vault_items.id (String(36) UUID) per the canonical
   Bridgeable id convention.

2. **Single index** on task_id for query performance (find all focus
   sessions for a given task).

FK semantics:
- focus_sessions.task_id → vault_items.id ON DELETE SET NULL
  (when a task VaultItem is deleted, focus_session row survives with
  task_id cleared — preserves focus session history)

Idempotent: each DDL step gated on inspector-reported state. Matches the
r106/r107 precedent.

Reversible: downgrade drops index + column.

Migration head: r107_task_substrate → r108.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "r108_focus_session_task_extension"
down_revision = "r107_task_substrate"
branch_labels = None
depends_on = None


_TABLE = "focus_sessions"
_COLUMN = "task_id"
_INDEX = "ix_focus_sessions_task_id"
_FK = "fk_focus_sessions_task_id_vault_items"


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    insp = sa.inspect(bind)
    if table_name not in insp.get_table_names():
        return False
    return column_name in {c["name"] for c in insp.get_columns(table_name)}


def _existing_indexes(bind, table_name: str) -> set[str]:
    insp = sa.inspect(bind)
    if table_name not in insp.get_table_names():
        return set()
    return {idx["name"] for idx in insp.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1. Add task_id column ────────────────────────────────────────
    if not _column_exists(bind, _TABLE, _COLUMN):
        op.add_column(
            _TABLE,
            sa.Column(
                _COLUMN,
                sa.String(length=36),
                sa.ForeignKey(
                    "vault_items.id",
                    name=_FK,
                    ondelete="SET NULL",
                ),
                nullable=True,
            ),
        )

    # ── 2. Index on task_id ──────────────────────────────────────────
    existing = _existing_indexes(bind, _TABLE)
    if _INDEX not in existing:
        op.create_index(
            _INDEX,
            _TABLE,
            [_COLUMN],
            postgresql_where=sa.text(f"{_COLUMN} IS NOT NULL"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    existing = _existing_indexes(bind, _TABLE)

    if _INDEX in existing:
        op.drop_index(_INDEX, table_name=_TABLE)

    if _column_exists(bind, _TABLE, _COLUMN):
        op.drop_column(_TABLE, _COLUMN)
