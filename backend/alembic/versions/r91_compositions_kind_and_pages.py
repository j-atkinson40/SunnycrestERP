"""Phase R-5.0 — kind discriminator + pages JSONB on focus_compositions.

R-5 introduces edge panels — global, user-invoked transient action
surfaces. Per the investigation at /tmp/r5_edge_panel_scope.md
(Section 2 Option B), edge panels share the existing composition
substrate with Focus accessory rails. Two coexisting composition
shapes are distinguished by a `kind` discriminator:

    kind = 'focus'       — single-page Focus accessory rail (existing).
                            `rows` is the canonical row-set;
                            `pages` is NULL.

    kind = 'edge_panel'  — multi-page action panel.
                            `rows` is empty `[]`;
                            `pages` is a non-empty JSONB list of
                            `{page_id, name, rows: [...], canvas_config: {...}}`
                            records, each page being its own row-set.

`focus_type` column carries the entity slug regardless of kind:
    kind=focus       → focus_type slug like 'scheduling'
    kind=edge_panel  → panel slug like 'default' or 'dispatch'

The column-name reads slightly off for kind=edge_panel; documented in
the model docstring + accepted as lighter churn than a full rename.

Schema changes:

  - ADD COLUMN `kind` VARCHAR(32) NOT NULL DEFAULT 'focus'
    (CHECK constraint enumerates the two canonical values; default
    backfills every existing row to 'focus' on apply).

  - ADD COLUMN `pages` JSONB DEFAULT NULL
    (nullable — `kind='focus'` rows leave it NULL).

  - DROP partial unique index on (scope, vertical, tenant_id,
    focus_type) WHERE is_active=true; recreate including `kind`
    in the canonical tuple so per-kind uniqueness is independent.
    (A tenant CAN have an active `focus:scheduling` composition AND
    an active `edge_panel:default` composition simultaneously
    without conflict.)

Backfill: existing rows pick up `kind='focus'` via the column DEFAULT.
No additional UPDATE pass needed.

Down: drop kind + pages columns; recreate the original partial unique
index without the kind discriminator. Pre-R-5 callers see the same
shape they always did.

Revision ID: r91_compositions_kind_and_pages
Revises: r90_drop_legacy_composition_columns
Create Date: 2026-05-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "r91_compositions_kind_and_pages"
down_revision: Union[str, Sequence[str], None] = (
    "r90_drop_legacy_composition_columns"
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_OLD_PARTIAL_UNIQUE = "uq_focus_compositions_active"
_NEW_PARTIAL_UNIQUE = "uq_focus_compositions_active_v2"


def _conn():
    return op.get_bind()


def _index_exists(name: str) -> bool:
    insp = sa.inspect(_conn())
    indexes = insp.get_indexes("focus_compositions")
    return any(idx["name"] == name for idx in indexes)


def upgrade() -> None:
    # ADD kind column with safe DEFAULT for backfill.
    op.add_column(
        "focus_compositions",
        sa.Column(
            "kind",
            sa.String(32),
            nullable=False,
            server_default="focus",
        ),
    )

    # CHECK constraint — only canonical kinds permitted.
    op.create_check_constraint(
        "ck_focus_compositions_kind",
        "focus_compositions",
        "kind IN ('focus', 'edge_panel')",
    )

    # ADD pages column — nullable JSONB.
    op.add_column(
        "focus_compositions",
        sa.Column("pages", JSONB, nullable=True),
    )

    # Replace the partial unique index to include kind in the tuple.
    # The existing index name varies between deploys; check both
    # canonical variants and skip-if-exists semantics.
    if _index_exists(_OLD_PARTIAL_UNIQUE):
        op.drop_index(
            _OLD_PARTIAL_UNIQUE,
            table_name="focus_compositions",
        )

    # Create the new index unconditionally (idempotent via env.py wrapper).
    op.create_index(
        _NEW_PARTIAL_UNIQUE,
        "focus_compositions",
        ["scope", "vertical", "tenant_id", "focus_type", "kind"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    if _index_exists(_NEW_PARTIAL_UNIQUE):
        op.drop_index(
            _NEW_PARTIAL_UNIQUE,
            table_name="focus_compositions",
        )

    # Restore the pre-R-5 partial unique index (no kind in tuple).
    op.create_index(
        _OLD_PARTIAL_UNIQUE,
        "focus_compositions",
        ["scope", "vertical", "tenant_id", "focus_type"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )

    op.drop_constraint(
        "ck_focus_compositions_kind",
        "focus_compositions",
        type_="check",
    )
    op.drop_column("focus_compositions", "pages")
    op.drop_column("focus_compositions", "kind")
