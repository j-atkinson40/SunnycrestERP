"""Seed Focus compositions for the September Wilbert demo (May 2026).

Creates two `vertical_default` compositions for the `scheduling`
focus type:

  - funeral_home: kanban prominent + calendar + today's services + anomalies
  - manufacturing: kanban prominent + production schedule + line status + anomalies

These produce visibly distinct scheduling experiences for each
vertical without changing the underlying kanban implementation —
proving the composition layer's promise: same Focus code, distinct
layout per vertical.

Idempotent: re-running deactivates the prior active row + inserts a
new active row at version+1 (per service-layer versioning semantics).
The seed always represents the current canonical baseline.

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


# ─── FH scheduling composition ──────────────────────────────────


FH_SCHEDULING_PLACEMENTS = [
    {
        "placement_id": "fh-kanban",
        "component_kind": "widget",
        "component_name": "vault-schedule",
        "grid": {
            "column_start": 1,
            "column_span": 8,
            "row_start": 1,
            "row_span": 8,
        },
        "prop_overrides": {},
        "display_config": {"show_header": True, "show_border": True},
    },
    {
        "placement_id": "fh-calendar",
        "component_kind": "widget",
        "component_name": "today",
        "grid": {
            "column_start": 9,
            "column_span": 4,
            "row_start": 1,
            "row_span": 3,
        },
        "prop_overrides": {"dateFormatStyle": "weekday-month-day"},
        "display_config": {"show_header": True, "show_border": True},
    },
    {
        "placement_id": "fh-services",
        "component_kind": "widget",
        "component_name": "recent-activity",
        "grid": {
            "column_start": 9,
            "column_span": 4,
            "row_start": 4,
            "row_span": 3,
        },
        "prop_overrides": {},
        "display_config": {"show_header": True, "show_border": True},
    },
    {
        "placement_id": "fh-anomalies",
        "component_kind": "widget",
        "component_name": "anomalies",
        "grid": {
            "column_start": 9,
            "column_span": 4,
            "row_start": 7,
            "row_span": 2,
        },
        "prop_overrides": {},
        "display_config": {"show_header": True, "show_border": True},
    },
]


# ─── MFG scheduling composition ─────────────────────────────────


MFG_SCHEDULING_PLACEMENTS = [
    {
        "placement_id": "mfg-kanban",
        "component_kind": "widget",
        "component_name": "vault-schedule",
        "grid": {
            "column_start": 1,
            "column_span": 7,
            "row_start": 1,
            "row_span": 8,
        },
        "prop_overrides": {},
        "display_config": {"show_header": True, "show_border": True},
    },
    {
        "placement_id": "mfg-production-schedule",
        "component_kind": "widget",
        "component_name": "today",
        "grid": {
            "column_start": 8,
            "column_span": 5,
            "row_start": 1,
            "row_span": 3,
        },
        "prop_overrides": {},
        "display_config": {"show_header": True, "show_border": True},
    },
    {
        "placement_id": "mfg-line-status",
        "component_kind": "widget",
        "component_name": "line-status",
        "grid": {
            "column_start": 8,
            "column_span": 5,
            "row_start": 4,
            "row_span": 3,
        },
        "prop_overrides": {},
        "display_config": {"show_header": True, "show_border": True},
    },
    {
        "placement_id": "mfg-anomalies",
        "component_kind": "widget",
        "component_name": "anomalies",
        "grid": {
            "column_start": 8,
            "column_span": 5,
            "row_start": 7,
            "row_span": 2,
        },
        "prop_overrides": {},
        "display_config": {"show_header": True, "show_border": True},
    },
]


CANVAS_CONFIG = {
    "total_columns": 12,
    "row_height": 64,
    "gap_size": 12,
    "background_treatment": "surface-base",
}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    db = SessionLocal()
    try:
        for vertical, placements in [
            ("funeral_home", FH_SCHEDULING_PLACEMENTS),
            ("manufacturing", MFG_SCHEDULING_PLACEMENTS),
        ]:
            row = create_composition(
                db,
                scope="vertical_default",
                focus_type="scheduling",
                vertical=vertical,
                placements=placements,
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
