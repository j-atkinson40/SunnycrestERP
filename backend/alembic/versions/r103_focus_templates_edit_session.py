"""Focus Template Inheritance sub-arc C-2.1.2 — focus_templates edit-session tracking.

Adds session-aware update semantics to Tier 2 templates, mirroring
r102's change to Tier 1 cores. Without this column pair every Tier 2
update version-bumps; C-2.2's auto-save editor would reproduce the
same scrub-session bloat r102 fixed for cores.

Schema changes:

  1. focus_templates.last_edit_session_id UUID NULL
  2. focus_templates.last_edit_session_at TIMESTAMPTZ NULL

Existing rows initialize NULL — the correct "no active session"
state. Reversible (downgrade drops both columns).

Migration head: r102_focus_cores_edit_session → r103_focus_templates_edit_session.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "r103_focus_templates_edit_session"
down_revision = "r102_focus_cores_edit_session"
branch_labels = None
depends_on = None


def _existing_columns(bind, table_name: str) -> set[str]:
    insp = sa.inspect(bind)
    if table_name not in insp.get_table_names():
        return set()
    return {col["name"] for col in insp.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    cols = _existing_columns(bind, "focus_templates")

    if "last_edit_session_id" not in cols:
        op.add_column(
            "focus_templates",
            sa.Column(
                "last_edit_session_id",
                postgresql.UUID(as_uuid=False),
                nullable=True,
            ),
        )
    if "last_edit_session_at" not in cols:
        op.add_column(
            "focus_templates",
            sa.Column(
                "last_edit_session_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = _existing_columns(bind, "focus_templates")

    if "last_edit_session_at" in cols:
        op.drop_column("focus_templates", "last_edit_session_at")
    if "last_edit_session_id" in cols:
        op.drop_column("focus_templates", "last_edit_session_id")
