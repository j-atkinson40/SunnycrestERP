"""Seed the Job Coordination Focus core + template (JCF-1).

The composition the assembly proof resolves: a thin coordination core
(Tier 1 — the scoping container; the JCF-2 frontend registers the
component under this name) + a platform_default FocusTemplate whose
accessory placements are the ALREADY-REGISTERED widgets (vault_schedule +
calendar_summary). The thread + participants widgets are JCF-2 UI and
join the template then.

Idempotent (slug-detect + skip, matching seed_focus_template_inheritance's
discipline — no version rotation on re-run). Auto-discovered by the D-1
canonical seed runner; platform-canonical content, safe in production.

Usage:
    cd backend && python -m scripts.seed_jcf_template
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models.focus_core import FocusCore  # noqa: E402
from app.models.focus_template import FocusTemplate  # noqa: E402
from app.services.focus_template_inheritance.focus_cores_service import (  # noqa: E402
    create_core,
)
from app.services.focus_template_inheritance.focus_templates_service import (  # noqa: E402
    create_template,
)

logger = logging.getLogger(__name__)

CORE_SLUG = "job-coordination-core"
TEMPLATE_SLUG = "job-coordination"

JCF_CORE = {
    "core_slug": CORE_SLUG,
    "display_name": "Job Coordination Core",
    "description": (
        "Thin scoping core for the Job Coordination Focus: binds one "
        "job (sales_order) into the composition via context-broadcast; "
        "renders no operational machinery of its own (the content is "
        "the accessory placements)."
    ),
    "registered_component_kind": "focus-core",
    "registered_component_name": "JobCoordinationCore",
    "default_starting_column": 0,
    "default_column_span": 12,
    "default_row_index": 0,
    "min_column_span": 6,
    "max_column_span": 12,
    "canvas_config": {},
    "chrome": {
        "preset": "frosted",
        "elevation": 50,
        "corner_radius": 70,
        "backdrop_blur": 44,
        "background_token": "surface-frosted",
        "border_token": "border-subtle",
        "padding_token": "space-3",
    },
}


def _template_payload(core_id: str) -> dict:
    return {
        "scope": "platform_default",
        "vertical": None,
        "template_slug": TEMPLATE_SLUG,
        "display_name": "Job Coordination",
        "description": (
            "Cross-tenant job war-room: production schedule + the joint "
            "delivery event around the thin scoping core. Thread + "
            "participants placements join in JCF-2."
        ),
        "inherits_from_core_id": core_id,
        "rows": [
            {
                "row_index": 0,
                "column_count": 12,
                "placements": [
                    {
                        "placement_id": "jcf-core",
                        "component_kind": "focus-core",
                        "component_name": "JobCoordinationCore",
                        "starting_column": 0,
                        "column_span": 12,
                        "is_core": True,
                        "prop_overrides": {},
                    }
                ],
            },
            {
                "row_index": 1,
                "column_count": 12,
                "placements": [
                    {
                        "placement_id": "jcf-schedule",
                        "component_kind": "widget",
                        "component_name": "vault_schedule",
                        "starting_column": 0,
                        "column_span": 6,
                        "is_core": False,
                        "prop_overrides": {},
                    },
                    {
                        "placement_id": "jcf-calendar",
                        "component_kind": "widget",
                        "component_name": "calendar_summary",
                        "starting_column": 6,
                        "column_span": 6,
                        "is_core": False,
                        "prop_overrides": {},
                    },
                ],
            },
        ],
        "canvas_config": {},
        "chrome_overrides": {},
        "substrate": {"preset": "morning-warm", "intensity": 100},
    }


def seed(db) -> str:
    core = (
        db.query(FocusCore).filter(FocusCore.core_slug == CORE_SLUG).first()
    )
    if core is None:
        core = create_core(db, **JCF_CORE)
        logger.info("created FocusCore %s", CORE_SLUG)

    existing = (
        db.query(FocusTemplate)
        .filter(FocusTemplate.template_slug == TEMPLATE_SLUG)
        .first()
    )
    if existing is not None:
        return "noop"

    create_template(db, **_template_payload(core.id))
    return "created"


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    db = SessionLocal()
    try:
        result = seed(db)
        print(f"[seed_jcf_template] {result}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
