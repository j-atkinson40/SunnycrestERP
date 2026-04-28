"""Widget Library Phase W-3a — 5-axis filter (add required_product_line) +
AncillaryPoolPin retag to manufacturing + vault.

Revision ID: r59_widget_product_line_axis
Revises: r58_widget_library_w1_foundation
Create Date: 2026-04-27

Phase W-3a of the Widget Library Architecture. Extends the 4-axis filter
(permission + module + extension + vertical) to 5 axes by adding
`required_product_line` per Product Line + Operating Mode canon.

See also:
  • [BRIDGEABLE_MASTER §5.2.1](../../BRIDGEABLE_MASTER.md) — canonical
    Extension-vs-ProductLine distinction. Extension = how a line gets
    installed (or not — vault is built-in). Product line = the
    operational reality once installed.
  • [PLATFORM_ARCHITECTURE.md §9.3](../../PLATFORM_ARCHITECTURE.md) — 5-axis
    filter mechanics + the canonical statement that the two axes are
    distinct (vault is not extension-gated; product-line scoping is
    distinct from feature unlock).
  • [DESIGN_LANGUAGE.md §12.4](../../DESIGN_LANGUAGE.md) — visibility
    semantics + mode-aware-rendering-vs-mode-aware-visibility note.

Schema change:
  • Add `required_product_line` JSONB column to `widget_definitions`.
    Default `["*"]` (cross-line, visible regardless of which lines the
    tenant runs). Filter logic (in widget_service.get_available_widgets)
    matches widget's declared line_keys against tenant's enabled
    TenantProductLine.line_key set.

Backfill:
  • Every existing widget receives `required_product_line = ["*"]`
    (no per-line scoping by default — cross-line is the canonical
    default per Decision 9 carry-through).
  • Two widget retags:
    1. `scheduling.ancillary-pool` — pre-canon was tagged
       `required_vertical = ["funeral_home"]` (incorrect — this widget
       lives on Sunnycrest manufacturing's scheduling Focus, tracking
       vault-line-related ancillaries like urns and cremation trays
       riding along with vault deliveries). Retags to:
         - `required_vertical: ["manufacturing"]`
         - `required_product_line: ["vault"]`
       The asymmetry between widget and tenant fixtures was caught
       during Phase W-3a investigation.
    2. `qc_status` — already correctly tagged `required_vertical:
       ["funeral_home"]` (NPCA audit prep is FH compliance) per
       r58 backfill. No retag needed; gets `required_product_line: ["*"]`
       since QC is a cross-line concern within FH operations.

NB: This migration is the load-bearing first step of Phase W-3a Commit 1.
A subsequent r60 migration backfills `tenant_product_lines` rows for
existing manufacturing tenants so the filter has data to evaluate
against. Without r60, manufacturing tenants would lose visibility of
the retagged AncillaryPoolPin (no vault line activated → filter rejects).

Idempotent — column add wrapped via env.py monkey-patch; backfill UPDATE
runs against the new column with default-respecting WHERE clauses.
"""

import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = "r59_widget_product_line_axis"
down_revision = "r58_widget_library_w1_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Step 1 — add column with safe default ───────────────────────
    # JSONB default ["*"] means: cross-line widget, visible regardless
    # of which product lines the tenant has activated. This is the
    # canonical default per §12.4 Decision 9 carry-through.
    op.add_column(
        "widget_definitions",
        sa.Column(
            "required_product_line",
            JSONB,
            nullable=False,
            server_default=sa.text("'[\"*\"]'::jsonb"),
        ),
    )

    # ── Step 2 — backfill all existing widgets to ["*"] ────────────
    # The server_default already populated NULL values during ADD COLUMN
    # but we run an explicit UPDATE so the canonical reference query
    # ("SELECT required_product_line FROM widget_definitions") returns
    # the same shape for old + new rows. Idempotent (re-running this
    # migration after rolled-back data is safe).
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE widget_definitions "
            "SET required_product_line = :default_value "
            "WHERE required_product_line IS NULL OR required_product_line = '[]'::jsonb"
        ),
        {"default_value": json.dumps(["*"])},
    )

    # ── Step 3 — retag scheduling.ancillary-pool ───────────────────
    # Pre-canon tagging: required_vertical=["funeral_home"]. Canon
    # correction: this widget lives on Sunnycrest's scheduling Focus
    # (manufacturing operations); tracks vault-line ancillary items.
    # Retag to manufacturing vertical + vault product line.
    conn.execute(
        sa.text(
            "UPDATE widget_definitions "
            "SET required_vertical = :vertical, "
            "    required_product_line = :line "
            "WHERE widget_id = 'scheduling.ancillary-pool'"
        ),
        {
            "vertical": json.dumps(["manufacturing"]),
            "line": json.dumps(["vault"]),
        },
    )


def downgrade() -> None:
    # ── Step 1 — restore pre-canon AncillaryPoolPin tagging ────────
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE widget_definitions "
            "SET required_vertical = :vertical "
            "WHERE widget_id = 'scheduling.ancillary-pool'"
        ),
        {"vertical": json.dumps(["funeral_home"])},
    )

    # ── Step 2 — drop required_product_line column ─────────────────
    op.drop_column("widget_definitions", "required_product_line")
