"""Focus Template Inheritance sub-arc B-5 — typography substrate vocabulary.

Adds a Focus-level typography vocabulary parallel to the chrome v2
(sub-arc B-3.5) and page-background substrate (sub-arc B-4)
vocabularies. Typography is the Focus-level type-treatment defaults
(heading + body weights + color tokens), distinct from chrome
(per-surface composition) and substrate (atmospheric backdrop).

Tiered like substrate — Tier 2 templates carry default typography;
Tier 3 compositions override via the existing `deltas` JSONB column
(new key `typography_overrides`). Tier 1 cores stay typography-free
by design (locked decision).

Typography v1 shape (validated at the service layer, not the DB):

    {
        "preset": "card-text" | "frosted-text" | "headline" |
                  "custom" | None,
        "heading_weight": int (400-900) | None,
        "heading_color_token": str | None,
        "body_weight": int (400-900) | None,
        "body_color_token": str | None,
    }

Schema changes:

  1. focus_templates.typography JSONB NOT NULL DEFAULT '{}'  (Tier 2 default)
  2. focus_compositions: NO schema change. Tier 3 typography_overrides
     ride the existing `deltas` JSONB column.
  3. focus_cores: NO schema change. Tier 1 stays typography-free.

Reversibility: downgrade drops the new column. Tier 3 typography_overrides
inside `focus_compositions.deltas` JSONB survives the round-trip (the
resolver post-downgrade ignores unknown delta keys gracefully) — data
intact, no loss.

Migration head: r100_substrate_vocabulary → r101_typography_substrate.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r101_typography_substrate"
down_revision = "r100_substrate_vocabulary"
branch_labels = None
depends_on = None


def _existing_columns(bind, table_name: str) -> set[str]:
    insp = sa.inspect(bind)
    if table_name not in insp.get_table_names():
        return set()
    return {col["name"] for col in insp.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()

    # ── focus_templates.typography (Tier 2 default) ──
    cols = _existing_columns(bind, "focus_templates")
    if "typography" not in cols:
        op.add_column(
            "focus_templates",
            sa.Column(
                "typography",
                sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )

    # focus_compositions: intentionally no schema change. Tier 3
    # typography_overrides ride the existing `deltas` JSONB column.
    # focus_cores: intentionally no schema change. Cores stay
    # typography-free per locked decision.


def downgrade() -> None:
    """Drop the typography column. Tier 3 typography_overrides inside
    `focus_compositions.deltas` JSONB survives the round-trip (the
    resolver post-downgrade ignores unknown delta keys gracefully).
    """
    bind = op.get_bind()

    cols = _existing_columns(bind, "focus_templates")
    if "typography" in cols:
        op.drop_column("focus_templates", "typography")
