"""R-5.0 — seed default edge panel composition.

Creates a `platform_default` composition with `kind="edge_panel"` +
`focus_type="default"` (panel slug). Carries two pages with R-4 button
placements so operators on any tenant see something usable on first
edge-panel open.

The button slugs reference R-4.0 platform-registered buttons:
  - `open-funeral-scheduling-focus` (open_focus action)
  - `trigger-cement-order-workflow` (trigger_workflow action)
  - `navigate-to-pulse` (navigate action)

Idempotent: re-running deactivates the prior active row + inserts a
new active row at version+1 (per service-layer versioning semantics).

Usage:
    PYTHONPATH=. python backend/scripts/seed_edge_panel.py
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


def _button_placement(
    placement_id: str,
    component_name: str,
    *,
    starting_column: int = 0,
    column_span: int = 12,
) -> dict:
    return {
        "placement_id": placement_id,
        "component_kind": "button",
        "component_name": component_name,
        "starting_column": starting_column,
        "column_span": column_span,
        "prop_overrides": {},
        "display_config": {"show_header": False, "show_border": False},
        "nested_rows": None,
    }


def _label_placement(
    placement_id: str,
    *,
    text: str,
    starting_column: int = 0,
    column_span: int = 12,
) -> dict:
    return {
        "placement_id": placement_id,
        "component_kind": "edge-panel-label",
        "component_name": "default",
        "starting_column": starting_column,
        "column_span": column_span,
        "prop_overrides": {"text": text},
        "display_config": {"show_header": False, "show_border": False},
        "nested_rows": None,
    }


def _row(*, placements: list, column_count: int = 12, row_height="auto") -> dict:
    return {
        "row_id": str(uuid.uuid4()),
        "column_count": column_count,
        "row_height": row_height,
        "column_widths": None,
        "nested_rows": None,
        "placements": placements,
    }


def _quick_actions_page() -> dict:
    return {
        "page_id": "quick-actions",
        "name": "Quick Actions",
        "rows": [
            _row(placements=[
                _label_placement("lbl-quick", text="QUICK ACTIONS"),
            ]),
            _row(placements=[
                _button_placement("btn-pulse", "navigate-to-pulse"),
            ]),
            _row(placements=[
                _button_placement("btn-scheduling", "open-funeral-scheduling-focus"),
            ]),
        ],
        "canvas_config": {"gap_size": 10},
    }


def _dispatch_page() -> dict:
    return {
        "page_id": "dispatch",
        "name": "Dispatch",
        "rows": [
            _row(placements=[
                _label_placement("lbl-dispatch", text="DISPATCH"),
            ]),
            _row(placements=[
                _button_placement("btn-cement", "trigger-cement-order-workflow"),
            ]),
        ],
        "canvas_config": {"gap_size": 10},
    }


def _seed_default_panel(db) -> None:
    pages = [_quick_actions_page(), _dispatch_page()]
    row = create_composition(
        db,
        scope="platform_default",
        focus_type="default",
        kind="edge_panel",
        pages=pages,
        canvas_config={"default_page_index": 0},
    )
    logger.info(
        "Seeded edge_panel: id=%s, focus_type=default, version=%s, pages=%d",
        row.id,
        row.version,
        len(row.pages or []),
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    db = SessionLocal()
    try:
        _seed_default_panel(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
