"""R-5.0 — seed default edge panel composition.

Creates a `platform_default` composition with `kind="edge_panel"` +
`focus_type="default"` (panel slug). Carries two pages with R-4 button
placements so operators on any tenant see something usable on first
edge-panel open.

The button slugs reference R-4.0 platform-registered buttons:
  - `open-funeral-scheduling-focus` (open_focus action)
  - `trigger-cement-order-workflow` (trigger_workflow action)
  - `navigate-to-pulse` (navigate action)

R-5.0.1 — TRUE idempotency: skips when an active platform_default row
already carries the expected pages content. Without this, every deploy
deactivates v_N and creates v_N+1 — accumulates inactive rows + churns
version numbers. Content-equality short-circuit keeps the version
number stable across redundant deploys; only changes to the seed shape
itself bump versions.

Production guard: refuses to run when `ENVIRONMENT=production` —
matches seed_staging / seed_fh_demo / seed_dispatch_demo discipline.
Production tenants author their own edge panels via the visual editor
(R-5.1+); the seeded platform_default is a staging/dev convenience.

Usage:
    PYTHONPATH=. python backend/scripts/seed_edge_panel.py
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from pathlib import Path

# Ensure `backend` is on sys.path so this script runs from any cwd.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models.focus_composition import FocusComposition  # noqa: E402
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


def _pages_content_equal(actual: list | None, expected: list) -> bool:
    """Compare two `pages` JSONB structures for content equality. The
    only volatile keys we ignore are per-row UUIDs (`row_id`); placement
    `placement_id` strings are deterministic in the seed (e.g.
    `"btn-pulse"`) so they DO equality-compare. Page `page_id` strings
    are also deterministic (e.g. `"quick-actions"`).

    Returns True when actual matches expected at the seed-relevant
    fields. Used by the idempotency short-circuit so every deploy
    doesn't bump the version number when the seed shape hasn't drifted.
    """
    if actual is None or len(actual) != len(expected):
        return False
    for a_page, e_page in zip(actual, expected):
        if a_page.get("page_id") != e_page.get("page_id"):
            return False
        if a_page.get("name") != e_page.get("name"):
            return False
        if a_page.get("canvas_config") != e_page.get("canvas_config"):
            return False
        a_rows = a_page.get("rows") or []
        e_rows = e_page.get("rows") or []
        if len(a_rows) != len(e_rows):
            return False
        for a_row, e_row in zip(a_rows, e_rows):
            # Ignore row_id (volatile UUID); compare structural fields.
            if a_row.get("column_count") != e_row.get("column_count"):
                return False
            if a_row.get("row_height") != e_row.get("row_height"):
                return False
            a_placements = a_row.get("placements") or []
            e_placements = e_row.get("placements") or []
            if len(a_placements) != len(e_placements):
                return False
            for a_p, e_p in zip(a_placements, e_placements):
                for k in (
                    "placement_id",
                    "component_kind",
                    "component_name",
                    "starting_column",
                    "column_span",
                    "prop_overrides",
                ):
                    if a_p.get(k) != e_p.get(k):
                        return False
    return True


def _seed_default_panel(db) -> None:
    pages = [_quick_actions_page(), _dispatch_page()]

    # R-5.0.1 — idempotency check. If an active platform_default
    # kind=edge_panel focus_type=default row already exists with
    # matching pages content, skip creation. Prevents version-bump
    # noise on every redundant deploy. Content drift (admin edited
    # the seed file) still triggers create + version-bump.
    existing = (
        db.query(FocusComposition)
        .filter(
            FocusComposition.scope == "platform_default",
            FocusComposition.kind == "edge_panel",
            FocusComposition.focus_type == "default",
            FocusComposition.is_active.is_(True),
        )
        .first()
    )
    if existing is not None and _pages_content_equal(existing.pages, pages):
        logger.info(
            "Edge panel already seeded with matching content "
            "(id=%s, version=%s, pages=%d) — skipping",
            existing.id,
            existing.version,
            len(existing.pages or []),
        )
        return

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

    # R-5.0.1 — production guard. Mirrors seed_staging / seed_fh_demo /
    # seed_dispatch_demo discipline; production tenants author their
    # own edge panels via the visual editor (R-5.1+).
    if os.getenv("ENVIRONMENT") == "production":
        logger.info(
            "ENVIRONMENT=production — refusing to seed edge panel. "
            "Production tenants author edge panels via the visual editor."
        )
        return

    db = SessionLocal()
    try:
        _seed_default_panel(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
