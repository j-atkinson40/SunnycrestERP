"""Focus Template Inheritance sub-arc C-2.1.1 — focus_cores edit-session tracking.

Adds session-aware update semantics to Tier 1 cores. C-2.1's 300ms
debounced auto-save in `useFocusCoreDraft` produces ~30+ version bumps
during a single elevation-slider scrub because `update_core` (B-1)
versions on every successful update. After the first save the frontend
holds a reference to the now-inactive prior version's UUID; the next
save returns 409 because B-1 rejects updates to inactive cores.

The fix is session-aware update semantics: updates within an explicit
edit-session window (5-minute, frontend-supplied UUID v4 token)
mutate in place; updates outside that window keep version-bumping
per B-1.

Schema changes:

  1. focus_cores.last_edit_session_id UUID NULL
  2. focus_cores.last_edit_session_at TIMESTAMPTZ NULL

Existing rows initialize NULL — the correct "no active session"
state. Reversible (downgrade drops both columns).

Migration head: r101_typography_substrate → r102_focus_cores_edit_session.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "r102_focus_cores_edit_session"
down_revision = "r101_typography_substrate"
branch_labels = None
depends_on = None


def _existing_columns(bind, table_name: str) -> set[str]:
    insp = sa.inspect(bind)
    if table_name not in insp.get_table_names():
        return set()
    return {col["name"] for col in insp.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    cols = _existing_columns(bind, "focus_cores")

    if "last_edit_session_id" not in cols:
        op.add_column(
            "focus_cores",
            sa.Column(
                "last_edit_session_id",
                postgresql.UUID(as_uuid=False),
                nullable=True,
            ),
        )
    if "last_edit_session_at" not in cols:
        op.add_column(
            "focus_cores",
            sa.Column(
                "last_edit_session_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = _existing_columns(bind, "focus_cores")

    if "last_edit_session_at" in cols:
        op.drop_column("focus_cores", "last_edit_session_at")
    if "last_edit_session_id" in cols:
        op.drop_column("focus_cores", "last_edit_session_id")
