"""B-1.5 — seed default edge-panel templates for FH + Manufacturing verticals.

Seeds two `vertical_default` `EdgePanelTemplate` rows at panel_key
'default':

  - (vertical_default, funeral_home, default) — FH-relevant Quick
    Actions page with funeral scheduling Focus open + Pulse nav.
  - (vertical_default, manufacturing, default) — Manufacturing Quick
    Actions + Dispatch page with cement-order workflow trigger.

No platform_default row is seeded (locked decision 8). Tenants in
verticals without a seeded vertical_default get no edge-panel until
an admin authors one — the resolver raises EdgePanelTemplateResolveError
which the tenant-realm route can translate to a 404 or empty state.

The legacy R-5.0 `seed_edge_panel.py` (which seeds against the
dropped substrate) is left untouched per scope. Its rewrite onto
this new substrate lands in sub-arc B-2.

Button slugs reference R-4.0 platform-registered buttons:
  - `open-funeral-scheduling-focus` (FH-specific)
  - `trigger-cement-order-workflow` (manufacturing-specific)
  - `navigate-to-pulse` (cross-vertical)

Idempotency: re-runs short-circuit when an active row already
carries matching pages content. Without this, every deploy
deactivates v_N and creates v_N+1 — accumulates inactive rows +
churns version numbers. Content drift (seed file edited) triggers
create + version-bump.

Production guard: refuses to run when `ENVIRONMENT=production` —
matches seed_staging / seed_fh_demo / seed_edge_panel discipline.

Usage:
    PYTHONPATH=. python backend/scripts/seed_edge_panel_inheritance.py
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
from app.models.edge_panel_template import EdgePanelTemplate  # noqa: E402
from app.services.edge_panel_inheritance import (  # noqa: E402
    create_template,
    get_template_by_key,
)


logger = logging.getLogger(__name__)


# Namespace for deterministic UUID generation per (vertical, panel_key,
# page_id, row_index). Keeps row_ids stable across re-runs.
_NS = uuid.UUID("d2c6e3f4-5a7b-49c8-b09d-1e2f3a4b5c6d")


def _row_id(vertical: str, panel_key: str, page_id: str, row_idx: int) -> str:
    return str(
        uuid.uuid5(_NS, f"{vertical}:{panel_key}:{page_id}:{row_idx}")
    )


# ─── Placement builders (mirror seed_edge_panel.py shape verbatim) ──


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


def _row(
    *,
    row_id: str,
    placements: list,
    column_count: int = 12,
    row_height="auto",
) -> dict:
    return {
        "row_id": row_id,
        "column_count": column_count,
        "row_height": row_height,
        "column_widths": None,
        "nested_rows": None,
        "placements": placements,
    }


# ─── Vertical-specific page builders ────────────────────────────


def _fh_quick_actions_page() -> dict:
    page_id = "quick-actions"
    return {
        "page_id": page_id,
        "name": "Quick Actions",
        "rows": [
            _row(
                row_id=_row_id("funeral_home", "default", page_id, 0),
                placements=[
                    _label_placement("lbl-quick", text="QUICK ACTIONS"),
                ],
            ),
            _row(
                row_id=_row_id("funeral_home", "default", page_id, 1),
                placements=[
                    _button_placement(
                        "btn-scheduling", "open-funeral-scheduling-focus"
                    ),
                ],
            ),
            _row(
                row_id=_row_id("funeral_home", "default", page_id, 2),
                placements=[
                    _button_placement("btn-pulse", "navigate-to-pulse"),
                ],
            ),
        ],
        "canvas_config": {"gap_size": 10},
    }


def _mfg_quick_actions_page() -> dict:
    page_id = "quick-actions"
    return {
        "page_id": page_id,
        "name": "Quick Actions",
        "rows": [
            _row(
                row_id=_row_id("manufacturing", "default", page_id, 0),
                placements=[
                    _label_placement("lbl-quick", text="QUICK ACTIONS"),
                ],
            ),
            _row(
                row_id=_row_id("manufacturing", "default", page_id, 1),
                placements=[
                    _button_placement("btn-pulse", "navigate-to-pulse"),
                ],
            ),
        ],
        "canvas_config": {"gap_size": 10},
    }


def _mfg_dispatch_page() -> dict:
    page_id = "dispatch"
    return {
        "page_id": page_id,
        "name": "Dispatch",
        "rows": [
            _row(
                row_id=_row_id("manufacturing", "default", page_id, 0),
                placements=[
                    _label_placement("lbl-dispatch", text="DISPATCH"),
                ],
            ),
            _row(
                row_id=_row_id("manufacturing", "default", page_id, 1),
                placements=[
                    _button_placement(
                        "btn-cement", "trigger-cement-order-workflow"
                    ),
                ],
            ),
        ],
        "canvas_config": {"gap_size": 10},
    }


# ─── Idempotency comparator ─────────────────────────────────────


def _pages_content_equal(actual, expected) -> bool:
    """Compare two pages JSONB structures for content equality. Volatile
    row_id strings are ignored (deterministic across runs anyway, but
    defense-in-depth); placement_ids + page_ids are deterministic in
    the seed so they DO equality-compare.

    Returns True when actual matches expected at the seed-relevant
    fields. Mirrors seed_edge_panel._pages_content_equal verbatim.
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


# ─── Seeding ────────────────────────────────────────────────────


def _seed_vertical_default(
    db,
    *,
    vertical: str,
    display_name: str,
    description: str,
    pages: list[dict],
    canvas_config: dict,
) -> None:
    existing = get_template_by_key(
        db, "default", scope="vertical_default", vertical=vertical
    )
    if existing is not None and _pages_content_equal(existing.pages, pages):
        logger.info(
            "Edge-panel template already seeded for vertical=%s "
            "(id=%s, version=%s, pages=%d) — skipping",
            vertical,
            existing.id,
            existing.version,
            len(existing.pages or []),
        )
        return

    row = create_template(
        db,
        scope="vertical_default",
        vertical=vertical,
        panel_key="default",
        display_name=display_name,
        description=description,
        pages=pages,
        canvas_config=canvas_config,
        created_by=None,
    )
    logger.info(
        "Seeded edge_panel_template: vertical=%s panel_key=default "
        "id=%s version=%s pages=%d",
        vertical,
        row.id,
        row.version,
        len(row.pages or []),
    )


def _seed_funeral_home(db) -> None:
    pages = [_fh_quick_actions_page()]
    _seed_vertical_default(
        db,
        vertical="funeral_home",
        display_name="Funeral Home edge panel default",
        description="Default edge-panel for funeral home tenants.",
        pages=pages,
        canvas_config={"default_page_index": 0},
    )


def _seed_manufacturing(db) -> None:
    pages = [_mfg_quick_actions_page(), _mfg_dispatch_page()]
    _seed_vertical_default(
        db,
        vertical="manufacturing",
        display_name="Manufacturing edge panel default",
        description="Default edge-panel for manufacturing tenants.",
        pages=pages,
        canvas_config={"default_page_index": 0},
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if os.getenv("ENVIRONMENT") == "production":
        logger.info(
            "ENVIRONMENT=production — refusing to seed edge-panel inheritance "
            "templates. Production tenants author edge-panels via the visual editor."
        )
        return

    db = SessionLocal()
    try:
        _seed_funeral_home(db)
        _seed_manufacturing(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
