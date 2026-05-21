"""Widget definitions — published_composition_blob extension (WB-4a).

Adds the `published_composition_blob` JSONB column to `widget_definitions`,
the load-bearing column that completes Area 2's draft-then-publish lock
locked at the WB-4 investigation
(`docs/investigations/2026-05-21-widget-builder.md` Area 2).

Per the lock:

  • `composition_blob` is the DRAFT authoring surface; auto-saved per-tick
    (200 ms debounce) by the Widget Builder shell.
  • `published_composition_blob` is the LIVE render surface; updated ONLY
    when the operator clicks Publish.
  • Tenant render paths (Focus Builder palette, PlacedWidgetCore,
    `ComposedWidget` runtime) read `published_composition_blob` first;
    fall back to `composition_blob` ONLY when published is NULL AND draft
    is non-NULL (legacy backfill case for rows that existed pre-r106).
  • The fallback covers exactly one scenario: rows whose composition_blob
    was populated under WB-1 (before r106) get treated as already-published
    so existing seeded composed widgets keep rendering immediately after
    r106 lands without any operator action.

CHECK constraint:
    (published_composition_blob IS NULL) OR (composition_blob IS NOT NULL)
i.e. "can't publish without a draft." Allows draft-only and published+
draft states; rejects published-without-draft (which is meaningless under
the draft-then-publish lock).

Backfill: existing composed widgets (composition_blob IS NOT NULL) get
published_composition_blob = composition_blob in the same UPDATE pass.
Existing hand-coded widgets (composition_blob IS NULL) stay
published_composition_blob = NULL — they don't render via the composition
path at all.

Idempotent: each DDL step gated on inspector-reported state. Matches the
r103/r105 precedent.

Reversible: downgrade drops the CHECK constraint + the column.

Migration head: r105_widget_definitions_composition_extension → r106.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "r106_widget_definitions_published_blob"
down_revision = "r105_widget_definitions_composition_extension"
branch_labels = None
depends_on = None


_TABLE = "widget_definitions"
_CHECK_NAME = "ck_widget_definitions_published_requires_draft"


def _existing_columns(bind, table_name: str) -> set[str]:
    insp = sa.inspect(bind)
    if table_name not in insp.get_table_names():
        return set()
    return {col["name"] for col in insp.get_columns(table_name)}


def _existing_check_constraints(bind, table_name: str) -> set[str]:
    insp = sa.inspect(bind)
    if table_name not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_check_constraints(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    cols = _existing_columns(bind, _TABLE)

    if "published_composition_blob" not in cols:
        op.add_column(
            _TABLE,
            sa.Column(
                "published_composition_blob",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
        )

    # Backfill: existing composed widgets (composition_blob IS NOT NULL)
    # get published_composition_blob = composition_blob — treat existing
    # rows as already-published. Hand-coded widgets (composition_blob
    # NULL) stay published NULL.
    op.execute(
        sa.text(
            "UPDATE widget_definitions "
            "SET published_composition_blob = composition_blob "
            "WHERE composition_blob IS NOT NULL "
            "AND published_composition_blob IS NULL"
        )
    )

    existing_checks = _existing_check_constraints(bind, _TABLE)
    if _CHECK_NAME not in existing_checks:
        op.create_check_constraint(
            _CHECK_NAME,
            _TABLE,
            "(published_composition_blob IS NULL) "
            "OR (composition_blob IS NOT NULL)",
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = _existing_columns(bind, _TABLE)
    checks = _existing_check_constraints(bind, _TABLE)

    if _CHECK_NAME in checks:
        op.drop_constraint(_CHECK_NAME, _TABLE, type_="check")

    if "published_composition_blob" in cols:
        op.drop_column(_TABLE, "published_composition_blob")
