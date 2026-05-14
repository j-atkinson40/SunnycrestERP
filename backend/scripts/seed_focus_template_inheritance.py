"""Seed canonical Focus Template Inheritance content (sub-arc B-1).

Tier 1 — one core:
    core_slug = 'scheduling-kanban'
        Canonical decision-triage Focus core. Registered against the
        in-memory component registry as
        focus-core / SchedulingKanbanCore.

Tier 2 — one template:
    template_slug = 'scheduling-fh', scope = 'vertical_default',
    vertical = 'funeral_home'
        Default funeral scheduling Focus. Minimal accessory rows in
        v1; editor populates canonical accessories in sub-arc C.

Idempotent: re-running detects the active row by slug and skips when
present (does NOT version-bump). This is distinct from the service
layer's `create_template` "version on collision" behavior — seed
scripts must be safe to re-run without rotating the active row
unnecessarily.

Usage:
    PYTHONPATH=. python backend/scripts/seed_focus_template_inheritance.py
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
from app.services.focus_template_inheritance import (  # noqa: E402
    create_core,
    create_template,
    get_core_by_slug,
    get_template_by_slug,
)


logger = logging.getLogger(__name__)


SCHEDULING_KANBAN_CORE = {
    "core_slug": "scheduling-kanban",
    "display_name": "Scheduling Kanban",
    "description": (
        "Canonical decision-triage Focus core: column-based scheduling "
        "kanban with drag-to-reorder."
    ),
    "registered_component_kind": "focus-core",
    "registered_component_name": "SchedulingKanbanCore",
    "default_starting_column": 0,
    "default_column_span": 12,
    "default_row_index": 0,
    "min_column_span": 8,
    "max_column_span": 12,
    "canvas_config": {},
}


SCHEDULING_FH_TEMPLATE = {
    "scope": "vertical_default",
    "vertical": "funeral_home",
    "template_slug": "scheduling-fh",
    "display_name": "Funeral Home Scheduling",
    "description": (
        "Default funeral scheduling Focus with case overview + day-pane "
        "accessories. Sub-arc C ships the canonical accessory layout."
    ),
    "rows": [],  # Editor populates accessories in sub-arc C.
    "canvas_config": {},
}


def _seed_core(db) -> str:
    existing = get_core_by_slug(db, SCHEDULING_KANBAN_CORE["core_slug"])
    if existing is not None:
        logger.info(
            "Tier 1 core %r already active (id=%s, version=%d) — skip",
            existing.core_slug,
            existing.id,
            existing.version,
        )
        return existing.id
    row = create_core(db, **SCHEDULING_KANBAN_CORE)
    logger.info(
        "Seeded Tier 1 core %r (id=%s, version=%d)",
        row.core_slug,
        row.id,
        row.version,
    )
    return row.id


def _seed_template(db, *, inherits_from_core_id: str) -> str:
    existing = get_template_by_slug(
        db,
        SCHEDULING_FH_TEMPLATE["template_slug"],
        scope=SCHEDULING_FH_TEMPLATE["scope"],
        vertical=SCHEDULING_FH_TEMPLATE["vertical"],
    )
    if existing is not None:
        logger.info(
            "Tier 2 template %r already active "
            "(id=%s, scope=%s, vertical=%s, version=%d) — skip",
            existing.template_slug,
            existing.id,
            existing.scope,
            existing.vertical,
            existing.version,
        )
        return existing.id
    row = create_template(
        db,
        scope=SCHEDULING_FH_TEMPLATE["scope"],
        vertical=SCHEDULING_FH_TEMPLATE["vertical"],
        template_slug=SCHEDULING_FH_TEMPLATE["template_slug"],
        display_name=SCHEDULING_FH_TEMPLATE["display_name"],
        description=SCHEDULING_FH_TEMPLATE["description"],
        inherits_from_core_id=inherits_from_core_id,
        rows=SCHEDULING_FH_TEMPLATE["rows"],
        canvas_config=SCHEDULING_FH_TEMPLATE["canvas_config"],
    )
    logger.info(
        "Seeded Tier 2 template %r (id=%s, vertical=%s, version=%d)",
        row.template_slug,
        row.id,
        row.vertical,
        row.version,
    )
    return row.id


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    db = SessionLocal()
    try:
        core_id = _seed_core(db)
        _seed_template(db, inherits_from_core_id=core_id)
    finally:
        db.close()


if __name__ == "__main__":
    main()
