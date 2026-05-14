"""Focus Template Inheritance sub-arc B-3 — chrome substrate.

Extends the three-tier Focus inheritance chain (sub-arc A schema +
sub-arc B-1 services) with outer-chrome styling — background color,
single drop shadow, single border (with radius), and four-tuple
padding. Field-level cascade mirrors the canvas_config precedent
shipped in B-1.

Schema changes:

  1. focus_cores.chrome JSONB NOT NULL DEFAULT '{}'        (Tier 1 default)
  2. focus_templates.chrome_overrides JSONB NOT NULL DEFAULT '{}'   (Tier 2 overrides)
  3. focus_compositions: NO schema change. Tier 3 chrome lives as a
     new key inside the existing `deltas` JSONB column.

Locked decisions (see CLAUDE.md sub-arc B-3 prompt + DECISIONS.md
2026-05-14 entries):

  1. Chrome v1 vocabulary: background_color, drop_shadow (single),
     border (single), padding (four-tuple). No multi-shadow, no
     per-side border, no margin/opacity.
  2. Field-level cascade matching B-1's canvas_config precedent.
  3. Padding always stored as four-tuple. Link-all-four UI state
     is sub-arc C-1's concern.
  4. Single drop shadow: {offset_x, offset_y, blur, spread, color}.
  5. Focus chrome only. Edge-panel chrome out of scope.

Reversibility: downgrade drops the two new columns. Tier 3
chrome_overrides in deltas survives downgrade (resolver ignores
unknown delta keys post-downgrade) — data intact, no loss.

Migration head: r97_edge_panel_substrate → r98_chrome_substrate.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r98_chrome_substrate"
down_revision = "r97_edge_panel_substrate"
branch_labels = None
depends_on = None


def _existing_columns(bind, table_name: str) -> set[str]:
    insp = sa.inspect(bind)
    if table_name not in insp.get_table_names():
        return set()
    return {col["name"] for col in insp.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()

    # ── focus_cores.chrome (Tier 1 default) ──
    cols = _existing_columns(bind, "focus_cores")
    if "chrome" not in cols:
        op.add_column(
            "focus_cores",
            sa.Column(
                "chrome",
                sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )

    # ── focus_templates.chrome_overrides (Tier 2 overrides) ──
    cols = _existing_columns(bind, "focus_templates")
    if "chrome_overrides" not in cols:
        op.add_column(
            "focus_templates",
            sa.Column(
                "chrome_overrides",
                sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )

    # focus_compositions: intentionally no schema change. Tier 3
    # chrome_overrides ride the existing `deltas` JSONB column.


def downgrade() -> None:
    """Drop the two new columns. Tier 3 chrome_overrides inside
    `focus_compositions.deltas` JSONB survives the round-trip (the
    resolver post-downgrade ignores unknown delta keys gracefully).
    """
    bind = op.get_bind()

    cols = _existing_columns(bind, "focus_templates")
    if "chrome_overrides" in cols:
        op.drop_column("focus_templates", "chrome_overrides")

    cols = _existing_columns(bind, "focus_cores")
    if "chrome" in cols:
        op.drop_column("focus_cores", "chrome")
