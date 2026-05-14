"""Focus Template Inheritance sub-arc B-4 — page-background substrate vocabulary.

Adds a page-background substrate vocabulary parallel to the chrome v2
vocabulary shipped in sub-arc B-3.5. Substrate is the Focus-level
atmospheric backdrop (the warm-gradient page background behind the
core + accessories), distinct from chrome (per-surface composition).

Tiered the same way as canvas_config + chrome_overrides — Tier 2
templates carry default substrate; Tier 3 compositions override via
the existing `deltas` JSONB column (new key `substrate_overrides`).
Tier 1 cores stay substrate-free by design (locked decision).

Substrate v1 shape (validated at the service layer, not the DB):

    {
        "preset": "morning-warm" | "morning-cool" | "evening-lounge"
                | "neutral" | "custom" | None,
        "intensity": int (0-100) | None,
        "base_token": str | None,
        "accent_token_1": str | None,
        "accent_token_2": str | None,
    }

Schema changes:

  1. focus_templates.substrate JSONB NOT NULL DEFAULT '{}'  (Tier 2 default)
  2. focus_compositions: NO schema change. Tier 3 substrate_overrides
     ride the existing `deltas` JSONB column.
  3. focus_cores: NO schema change. Tier 1 stays substrate-free.

Reversibility: downgrade drops the new column. Tier 3 substrate_overrides
inside `focus_compositions.deltas` JSONB survives the round-trip (the
resolver post-downgrade ignores unknown delta keys gracefully) — data
intact, no loss.

Migration head: r99_chrome_vocabulary_v2 → r100_substrate_vocabulary.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "r100_substrate_vocabulary"
down_revision = "r99_chrome_vocabulary_v2"
branch_labels = None
depends_on = None


def _existing_columns(bind, table_name: str) -> set[str]:
    insp = sa.inspect(bind)
    if table_name not in insp.get_table_names():
        return set()
    return {col["name"] for col in insp.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()

    # ── focus_templates.substrate (Tier 2 default) ──
    cols = _existing_columns(bind, "focus_templates")
    if "substrate" not in cols:
        op.add_column(
            "focus_templates",
            sa.Column(
                "substrate",
                sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )

    # focus_compositions: intentionally no schema change. Tier 3
    # substrate_overrides ride the existing `deltas` JSONB column.
    # focus_cores: intentionally no schema change. Cores stay
    # substrate-free per locked decision.


def downgrade() -> None:
    """Drop the substrate column. Tier 3 substrate_overrides inside
    `focus_compositions.deltas` JSONB survives the round-trip (the
    resolver post-downgrade ignores unknown delta keys gracefully).
    """
    bind = op.get_bind()

    cols = _existing_columns(bind, "focus_templates")
    if "substrate" in cols:
        op.drop_column("focus_templates", "substrate")
