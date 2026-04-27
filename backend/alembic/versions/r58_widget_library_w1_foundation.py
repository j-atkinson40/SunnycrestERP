"""Widget Library Phase W-1 — Foundation: variants + 4-axis filter columns.

Revision ID: r58_widget_library_w1_foundation
Revises: r57_delivery_settings_default_start_time
Create Date: 2026-04-27

Phase W-1 of the Widget Library Architecture per DESIGN_LANGUAGE.md Section 12.
Extends `widget_definitions` with the unified contract columns + makes the
existing 27-widget catalog conform to the new shape.

Schema changes:
  • Add `variants` JSONB column — array of variant declarations per
    Section 12.3 / 12.10 contract. Each variant carries: variant_id,
    density, grid_size, canvas_size, supported_surfaces, optional
    min_dimensions, optional required_features.
  • Add `default_variant_id` String(50) column — references one of the
    declared variants.
  • Add `required_vertical` JSONB column — Section 12.4 4-axis filter
    extension. Either a JSON array of vertical strings (e.g.
    `["funeral_home"]`, `["funeral_home", "cemetery"]`) or `["*"]`
    (cross-vertical, the canonical default). Stored as JSON array even
    when "single value" so the filter logic is uniform.
  • Add `supported_surfaces` JSONB column — array of surface enum
    strings per Section 12.5. Surfaces: pulse_grid, focus_canvas,
    focus_stack, spaces_pin, floating_tablet, dashboard_grid,
    peek_inline.
  • Add `default_surfaces` JSONB column — subset of supported_surfaces
    where the widget seeds in default layouts.
  • Add `intelligence_keywords` JSONB column — discovery hints for
    Phase W-5 Intelligence variant selection. Empty array for now;
    populated incrementally as widgets ship.

Backfill strategy:
  • Every existing widget gets a single "brief" variant matching its
    current `default_size` (e.g. 1x1 → grid_size {cols:1, rows:1}).
    `default_variant_id = "brief"`.
  • Every existing widget gets `required_vertical = ["*"]` (cross-
    vertical, default per Decision 9) EXCEPT explicit vertical-specific
    widgets:
      qc_status → ["funeral_home"] — NPCA audit prep is funeral-home
        compliance per CLAUDE.md §1; flagged in audit + decision
        documented in commit message.
  • Every existing widget gets `supported_surfaces = ["dashboard_grid"]`
    (current rendering target) and `default_surfaces` matching.
  • `intelligence_keywords = []` for all (populated later).

Legacy column treatment:
  • `required_preset` column STAYS (not dropped) for one release window
    per Decision 10 (both frameworks coexist 1-2 release windows).
    No widget currently sets a non-null value, so the column is
    effectively orphaned. It will be dropped in a Phase W-5 long-tail
    cleanup migration. Marked DEPRECATED in inline comments at the
    ORM model.
  • `default_size` + `supported_sizes` STAY (not dropped). Existing
    dashboard widgets continue to render at their current sizes
    while we propagate variant declarations across consumers in
    Phases W-2 → W-4.

NOT included in this migration (deferred):
  • Schema for AncillaryPoolPin canvas widget — its WidgetDefinition
    row gets seeded by `seed_widget_definitions()` in code (no
    schema change needed).
  • Removal of `required_preset` (Phase W-5 cleanup).
  • Removal of `default_size` / `supported_sizes` (Phase W-5 long-
    tail when all consumers migrated to variants).

Filter logic (separate from migration but related): the broken
`_get_tenant_preset()` helper at `widget_service.py:304` reading
`Company.preset` (which doesn't exist on the model — actual field is
`Company.vertical`) is fixed in the same commit by rewriting the
filter as 4-axis (permission + module + extension + vertical).
The new filter consumes `required_vertical` JSONB array; the legacy
`required_preset` field is no longer read.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = "r58_widget_library_w1_foundation"
down_revision = "r57_delivery_settings_default_start_time"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add the 6 new columns (idempotent via alembic env.py monkey-patch).
    op.add_column(
        "widget_definitions",
        sa.Column("variants", JSONB, nullable=False, server_default="[]"),
    )
    op.add_column(
        "widget_definitions",
        sa.Column("default_variant_id", sa.String(50), nullable=False, server_default="brief"),
    )
    op.add_column(
        "widget_definitions",
        sa.Column("required_vertical", JSONB, nullable=False, server_default='["*"]'),
    )
    op.add_column(
        "widget_definitions",
        sa.Column("supported_surfaces", JSONB, nullable=False, server_default='["dashboard_grid"]'),
    )
    op.add_column(
        "widget_definitions",
        sa.Column("default_surfaces", JSONB, nullable=False, server_default='["dashboard_grid"]'),
    )
    op.add_column(
        "widget_definitions",
        sa.Column("intelligence_keywords", JSONB, nullable=False, server_default="[]"),
    )

    # Backfill: every existing widget gets a single "brief" variant
    # matching its current `default_size`. Variant grid_size derives
    # from the "NxM" size string. canvas_size is a sensible default
    # mapping — Phase W-3 widget builds will refine canvas-tier sizing
    # per widget.
    #
    # We use a Python helper inline (not a service-layer function) to
    # keep the migration self-contained — alembic migrations should
    # not import from `app.services` (those modules can change shape
    # post-migration; the migration must be pinned to its time).
    # Backfill `variants` per row. Single "brief" variant matching
    # the row's existing `default_size`. Phase W-3 widget builds add
    # additional variants (Glance / Detail / Deep) per Section 12.10.
    import json as _json
    bind = op.get_bind()
    rows = bind.execute(sa.text(
        "SELECT widget_id, default_size FROM widget_definitions"
    )).fetchall()

    for row in rows:
        widget_id, default_size = row
        try:
            cols, rows_ = (int(x) for x in (default_size or "1x1").split("x"))
        except (AttributeError, ValueError):
            cols, rows_ = 1, 1

        # Default canvas size derived from grid size: 1×1 → ~280×200,
        # 2×1 → ~560×200, 1×2 → ~280×400, 2×2 → ~560×400. Phase W-3
        # widget builds refine canvas sizing per widget.
        canvas_width = 280 * cols
        canvas_height = 200 * rows_

        brief_variant = [{
            "variant_id": "brief",
            "density": "focused",
            "grid_size": {"cols": cols, "rows": rows_},
            "canvas_size": {
                "width": canvas_width,
                "height": canvas_height,
                "maxHeight": canvas_height + 200,
            },
            "supported_surfaces": ["dashboard_grid"],
        }]

        bind.execute(
            sa.text(
                "UPDATE widget_definitions SET "
                "variants = CAST(:variants AS jsonb), "
                "default_variant_id = :did "
                "WHERE widget_id = :wid"
            ),
            {
                "variants": _json.dumps(brief_variant),
                "did": "brief",
                "wid": widget_id,
            },
        )

    # Vertical-specific backfill (Phase W-1 audit-confirmed):
    #   qc_status → ["funeral_home"] (NPCA audit prep is funeral-home
    #   compliance per CLAUDE.md §1)
    bind.execute(
        sa.text(
            "UPDATE widget_definitions "
            "SET required_vertical = CAST(:vert AS jsonb) "
            "WHERE widget_id = :wid"
        ),
        {"vert": '["funeral_home"]', "wid": "qc_status"},
    )

    # Drop the server_default values for the new columns now that
    # backfill is complete. New widgets seeded via
    # `seed_widget_definitions()` will set explicit values per the
    # canonical WIDGET_DEFINITIONS list.
    op.alter_column("widget_definitions", "variants", server_default=None)
    op.alter_column("widget_definitions", "default_variant_id", server_default=None)
    op.alter_column("widget_definitions", "required_vertical", server_default=None)
    op.alter_column("widget_definitions", "supported_surfaces", server_default=None)
    op.alter_column("widget_definitions", "default_surfaces", server_default=None)
    op.alter_column("widget_definitions", "intelligence_keywords", server_default=None)


def downgrade() -> None:
    op.drop_column("widget_definitions", "intelligence_keywords")
    op.drop_column("widget_definitions", "default_surfaces")
    op.drop_column("widget_definitions", "supported_surfaces")
    op.drop_column("widget_definitions", "required_vertical")
    op.drop_column("widget_definitions", "default_variant_id")
    op.drop_column("widget_definitions", "variants")
