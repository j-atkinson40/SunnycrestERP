"""Seed Focus compositions for the September Wilbert demo (May 2026).

Creates two `vertical_default` compositions for the `scheduling`
focus type, one each for funeral_home and manufacturing verticals:

  - funeral_home_scheduling: 3 accessory widgets (today, recent_activity,
    anomalies) stacked vertically as a sidebar
  - manufacturing_scheduling: same 3 accessory widgets in the same
    arrangement (verticals can differentiate via the visual editor
    when concrete operator signal warrants)

These produce the **accessory layer** for the scheduling Focus in
each vertical. The bespoke kanban core (`SchedulingKanbanCore.tsx`,
1,714 LOC) renders the dispatcher's planning workspace itself —
the kanban surface, drag-drop, finalize workflow, ancillary pin —
and is **NOT** part of the composition. The composition only authors
the accessory widgets that render alongside the kanban in the Focus's
right-side accessory region.

Architectural pattern (May 2026 composition runtime integration phase):

  ┌── Focus surface ───────────────────────────────────────────┐
  │ ┌── kanban region (75% width) ──┐ ┌── accessory region ──┐ │
  │ │                                │ │ rendered from        │ │
  │ │   SchedulingKanbanCore         │ │ this composition     │ │
  │ │   (bespoke, code-rendered;     │ │ (visual-editor-      │ │
  │ │    NOT a composition placement)│ │  authored)            │ │
  │ │                                │ │                       │ │
  │ │                                │ │ • today              │ │
  │ │                                │ │ • recent_activity    │ │
  │ │                                │ │ • anomalies           │ │
  │ │                                │ │                       │ │
  │ └────────────────────────────────┘ └───────────────────────┘ │
  └────────────────────────────────────────────────────────────┘

Why this shape (vs. composition-as-full-Focus-layout):

The previous shipped seed included a `widget:vault-schedule` placement
intended to render the kanban-shaped Pulse widget at column 1-8.
That conflated two surfaces: the Pulse-shaped abridged kanban widget
and the dispatcher's bespoke `SchedulingKanbanCore`. They render
the same data but with substantively different interaction surfaces;
the kanban core is too tightly-coupled to decompose into widget-shaped
pieces without a regression-prone rewrite. The accessory-layer pattern
preserves operational behavior of the bespoke surface and lets the
composition author the periphery.

Naming convention: placement `component_name` is the canonical
widget_id snake_case used in the canvas widget registry
(`registerWidgetRenderer("today", TodayWidget)` etc. at
`frontend/src/components/widgets/foundation/register.ts`). The
runtime path in `CompositionRenderer.tsx` dispatches via
`getWidgetRenderer(component_name)` → real production widgets with
operational data.

Idempotent: re-running deactivates the prior active row + inserts a
new active row at version+1 (per service-layer versioning semantics
in `composition_service.create_composition`). The seed always
represents the current canonical baseline.

Usage:
    PYTHONPATH=. python backend/scripts/seed_focus_compositions.py

Run from the backend/ directory or with PYTHONPATH=. as appropriate.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure `backend` is on sys.path so this script runs from any cwd.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.services.focus_compositions import create_composition  # noqa: E402


logger = logging.getLogger(__name__)


# ─── Accessory layer placements ────────────────────────────────
#
# The composition canvas is intentionally a single-column layout
# (total_columns=1 below) so each placement fills the accessory
# region's full width. The accessory region itself is a narrow
# right-side sidebar in the scheduling Focus (~25% of viewport
# width); the composition describes its INTERNAL stacking. When a
# vertical wants to differentiate (e.g., FH adds a calendar widget,
# MFG adds line-status), it forks the composition via the visual
# editor.
#
# Row sizing: row_start increments by row_span, so widgets stack
# tightly without gaps. The frontend accessory region scrolls
# vertically when content exceeds viewport height.


def _accessory_placements() -> list[dict]:
    """3 accessory widgets stacked vertically in a single-column canvas."""
    return [
        {
            "placement_id": "today",
            "component_kind": "widget",
            "component_name": "today",
            "grid": {
                "column_start": 1,
                "column_span": 1,
                "row_start": 1,
                "row_span": 3,
            },
            "prop_overrides": {},
            "display_config": {"show_header": True, "show_border": True},
        },
        {
            "placement_id": "recent-activity",
            "component_kind": "widget",
            "component_name": "recent_activity",
            "grid": {
                "column_start": 1,
                "column_span": 1,
                "row_start": 4,
                "row_span": 4,
            },
            "prop_overrides": {},
            "display_config": {"show_header": True, "show_border": True},
        },
        {
            "placement_id": "anomalies",
            "component_kind": "widget",
            "component_name": "anomalies",
            "grid": {
                "column_start": 1,
                "column_span": 1,
                "row_start": 8,
                "row_span": 3,
            },
            "prop_overrides": {},
            "display_config": {"show_header": True, "show_border": True},
        },
    ]


CANVAS_CONFIG = {
    # Single-column canvas — accessory region is narrow; widgets stack
    # vertically and fill its full width. Verticals can override via
    # the visual editor (add columns, multi-column arrangements).
    "total_columns": 1,
    # 64px row height matches the editor canvas default. Each widget's
    # row_span × 64px = its target visual height in the accessory rail.
    "row_height": 64,
    "gap_size": 12,
    "background_treatment": "surface-base",
}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    db = SessionLocal()
    try:
        for vertical in ("funeral_home", "manufacturing"):
            row = create_composition(
                db,
                scope="vertical_default",
                focus_type="scheduling",
                vertical=vertical,
                placements=_accessory_placements(),
                canvas_config=CANVAS_CONFIG,
            )
            logger.info(
                "Seeded %s scheduling composition (id=%s, version=%d, %d placements)",
                vertical,
                row.id,
                row.version,
                len(row.placements),
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
