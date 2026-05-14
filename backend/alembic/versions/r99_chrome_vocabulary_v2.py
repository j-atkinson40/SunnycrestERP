"""Focus Template Inheritance sub-arc B-3.5 — chrome vocabulary v2.

Wholesale replacement of B-3's raw-value chrome vocabulary
(background_color hex / drop_shadow dict / border dict / padding
four-tuple) with a preset-driven vocabulary (canonical compositions
from DESIGN_LANGUAGE §6 + two continuous sliders + design-token
references).

New chrome v2 shape (validated at the service layer, not the DB):

    {
        "preset": "card" | "modal" | "dropdown" | "toast"
                | "floating" | "custom" | None,
        "elevation": int (0-100) | None,
        "corner_radius": int (0-100) | None,
        "background_token": str | None,
        "border_token": str | None,
        "padding_token": str | None
    }

No editor consumed B-3's chrome yet, so replacement is safe. Only
the seeded `scheduling-kanban` core has chrome data and it re-seeds
with v2 vocabulary after this migration.

Schema changes:

  1. focus_cores.chrome — DROP + re-ADD with empty default
  2. focus_templates.chrome_overrides — DROP + re-ADD with empty default
  3. focus_compositions.deltas — unchanged (chrome_overrides remains
     a service-layer-validated key inside the JSONB column)

Reversibility: downgrade restores B-3's columns with empty defaults
(pure schema reversibility — NO data restoration). Pre-existing
chrome data is lost on either direction. Documented + acceptable
because only the seed populates these columns today.

Migration head: r98_chrome_substrate → r99_chrome_vocabulary_v2.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r99_chrome_vocabulary_v2"
down_revision = "r98_chrome_substrate"
branch_labels = None
depends_on = None


def _existing_columns(bind, table_name: str) -> set[str]:
    insp = sa.inspect(bind)
    if table_name not in insp.get_table_names():
        return set()
    return {col["name"] for col in insp.get_columns(table_name)}


def upgrade() -> None:
    """Drop B-3 chrome columns + re-add as empty JSONB. No data is
    preserved — only the seeded scheduling-kanban core has chrome
    data and the seed re-populates with v2 vocabulary on next run.
    """
    bind = op.get_bind()

    # ── focus_cores.chrome ──
    cols = _existing_columns(bind, "focus_cores")
    if "chrome" in cols:
        op.drop_column("focus_cores", "chrome")
    op.add_column(
        "focus_cores",
        sa.Column(
            "chrome",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    # ── focus_templates.chrome_overrides ──
    cols = _existing_columns(bind, "focus_templates")
    if "chrome_overrides" in cols:
        op.drop_column("focus_templates", "chrome_overrides")
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
    # chrome_overrides ride the existing `deltas` JSONB column; the
    # service layer validates against the v2 vocabulary.


def downgrade() -> None:
    """Schema reversibility only — drops v2 columns + re-adds B-3's
    empty columns. NO data restoration in either direction.
    """
    bind = op.get_bind()

    cols = _existing_columns(bind, "focus_templates")
    if "chrome_overrides" in cols:
        op.drop_column("focus_templates", "chrome_overrides")
    op.add_column(
        "focus_templates",
        sa.Column(
            "chrome_overrides",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    cols = _existing_columns(bind, "focus_cores")
    if "chrome" in cols:
        op.drop_column("focus_cores", "chrome")
    op.add_column(
        "focus_cores",
        sa.Column(
            "chrome",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
