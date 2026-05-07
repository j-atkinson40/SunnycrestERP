"""Seed Focus compositions for the September Wilbert demo.

Creates two `vertical_default` compositions for the `scheduling` focus
type, one each for funeral_home and manufacturing verticals. Each is the
**accessory layer** that renders alongside the bespoke
`SchedulingKanbanCore.tsx` (1,714 LOC) inside the scheduling Focus —
the kanban core itself is rendered by code, NOT a composition placement.

R-3.0 — composition data model is now a sequence of rows. Each row
declares its own column_count (1-12) and carries its own placements
with 0-indexed `starting_column` + `column_span`. Architectural
shape unchanged from R-2.x: the seeded compositions describe a
single-column accessory rail with three widgets stacked vertically;
each widget gets its own row at column_count=1. This produces the
same visual output as the prior R-2.x seed (uniform-grid stacking)
while structurally adopting the new rows shape so future per-row
column_count differentiation lands cleanly.

Idempotent: re-running deactivates the prior active row + inserts a
new active row at version+1 (per service-layer versioning semantics
in `composition_service.create_composition`).

Usage:
    PYTHONPATH=. python backend/scripts/seed_focus_compositions.py
"""

from __future__ import annotations

import logging
import sys
import uuid
from pathlib import Path

# Ensure `backend` is on sys.path so this script runs from any cwd.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.services.focus_compositions import create_composition  # noqa: E402


logger = logging.getLogger(__name__)


def _accessory_row(
    *,
    placement_id: str,
    component_name: str,
    row_height: int,
) -> dict:
    """Single-placement row at column_count=1; widget fills the row.

    Each widget gets its own row so they stack vertically in the
    accessory rail. The R-3.0 model declares column_count + the
    placement's starting_column (0-indexed) + column_span so the
    widget spans the row's full width.
    """
    return {
        "row_id": str(uuid.uuid4()),
        "column_count": 1,
        "row_height": row_height,
        "column_widths": None,
        "nested_rows": None,
        "placements": [
            {
                "placement_id": placement_id,
                "component_kind": "widget",
                "component_name": component_name,
                "starting_column": 0,
                "column_span": 1,
                "prop_overrides": {},
                "display_config": {"show_header": True, "show_border": True},
                "nested_rows": None,
            }
        ],
    }


def _accessory_rows() -> list[dict]:
    """3 accessory widgets, each in its own single-column row.

    Row heights mirror the prior R-2.x seed (3 × 64 / 4 × 64 / 3 × 64
    pixels). Verticals can override per-row row_height + column_count
    via the visual editor when concrete operator signal warrants.
    """
    return [
        _accessory_row(
            placement_id="today",
            component_name="today",
            row_height=192,  # 3 × 64
        ),
        _accessory_row(
            placement_id="recent-activity",
            component_name="recent_activity",
            row_height=256,  # 4 × 64
        ),
        _accessory_row(
            placement_id="anomalies",
            component_name="anomalies",
            row_height=192,  # 3 × 64
        ),
    ]


# canvas_config carries cosmetic settings only post-R-3.0. Per-row
# column_count + row_height live on each row.
CANVAS_CONFIG = {
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
                rows=_accessory_rows(),
                canvas_config=CANVAS_CONFIG,
            )
            logger.info(
                "Seeded %s scheduling composition (id=%s, version=%d, %d rows)",
                vertical,
                row.id,
                row.version,
                len(row.rows),
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
