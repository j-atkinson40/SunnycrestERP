"""MoC platform page seed (MoC Hierarchy H-2) — the FIRST platform_default page.

The hierarchy's top: the login landing's pane resolves this page (the
platform_default tier existed in the scope model from MoC Phase 1; this
authors the first page into it — `read_for_context(vertical=None)` serves it).

Sections: ONE authored section — the CORE workflows' canonical home (the
scope='core' wf_sys_* mirrors: Month-End Close, AR Collections, … — they
appear on every vertical's map by reference; the platform page is where they
LIVE). Rows are built by QUERY (platform-scope mirror templates), so the seed
is correct on any DB — a fresh DB with no mirrors gets an empty section
(rendered as deliberate room, per the H-2 first-render discipline).

The page-level cards (verticals-as-links, cross-tenant fires, counts, the
platform task table) are FRONTEND composition (MoCHome), not authored rows —
same split as the vertical page (cards render around the authored content).

Idempotent: find-or-create by (scope='platform_default', slug); sections
REFRESHED on re-run (the core list re-queried). Safe on every deploy.

Usage:  cd backend && python -m scripts.seed_moc_platform
"""
from __future__ import annotations

import logging
import sys
import uuid
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models.focus_core import FocusCore  # noqa: E402
from app.models.focus_template import FocusTemplate  # noqa: E402
from app.models.moc_page import MoCPage  # noqa: E402
from app.models.workflow_template import WorkflowTemplate  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

SLUG = "platform-map"
TITLE = "Bridgeable"
DESCRIPTION = "The platform, whole — every vertical, the core machinery, and what's firing."


def _core_workflow_rows(db) -> list[dict]:
    """The platform-scope core mirrors (the backfill's 'core' → platform_default
    templates), as authored rows. Query-built — correct on any DB."""
    templates = (
        db.query(WorkflowTemplate)
        .filter(
            WorkflowTemplate.scope == "platform_default",
            WorkflowTemplate.mirrored_from_workflow_id.isnot(None),
            WorkflowTemplate.is_active.is_(True),
        )
        .order_by(WorkflowTemplate.display_name)
        .all()
    )
    return [
        {
            "row_id": f"core-{t.id[:8]}",
            "builder": "workflows",
            "artifact_id": t.id,
            "label": t.display_name,
            "order": i,
        }
        for i, t in enumerate(templates)
    ]


def _focus_default_rows(db) -> list[dict]:
    """The platform's default Focus shapes (Focus Variations V-1): every
    ACTIVE Tier 1 core (builder 'focus-cores' — the fork-menu targets) +
    every ACTIVE platform_default Tier 2 template. Query-built — correct on
    any DB, content-agnostic (dev holds job-coordination, staging holds
    scheduling-kanban; the seed hardcodes neither)."""
    rows: list[dict] = []
    cores = (
        db.query(FocusCore)
        .filter(FocusCore.is_active.is_(True))
        .order_by(FocusCore.display_name)
        .all()
    )
    for c in cores:
        rows.append(
            {
                "row_id": f"fcore-{c.core_slug}",
                "builder": "focus-cores",
                "artifact_id": c.id,
                "label": c.display_name,
                "icon": "focus",
                "order": len(rows),
            }
        )
    templates = (
        db.query(FocusTemplate)
        .filter(
            FocusTemplate.scope == "platform_default",
            FocusTemplate.is_active.is_(True),
        )
        .order_by(FocusTemplate.display_name)
        .all()
    )
    for t in templates:
        rows.append(
            {
                "row_id": f"ftmpl-{t.template_slug}",
                "builder": "focuses",
                "artifact_id": t.id,
                "label": t.display_name,
                "icon": "focus",
                "order": len(rows),
            }
        )
    return rows


def seed(db) -> dict:
    rows = _core_workflow_rows(db)
    focus_rows = _focus_default_rows(db)
    sections = [
        {
            "section_id": "core-workflows",
            "title": "Core workflows",
            "description": "Cross-vertical machinery — runs for every tenant.",
            "order": 0,
            "rows": rows,
        },
        {
            "section_id": "focus-defaults",
            "title": "Focuses",
            "description": (
                "The default Focus shapes — fork a variation or edit the "
                "default (edits reach every inheritor)."
            ),
            "order": 1,
            "rows": focus_rows,
        },
    ]
    page = (
        db.query(MoCPage)
        .filter(
            MoCPage.scope == "platform_default",
            MoCPage.slug == SLUG,
            MoCPage.is_active.is_(True),
        )
        .first()
    )
    if page is None:
        page = MoCPage(
            id=str(uuid.uuid4()),
            scope="platform_default",
            vertical=None,
            tenant_id=None,
            slug=SLUG,
            title=TITLE,
            description=DESCRIPTION,
            sections=sections,
            is_active=True,
        )
        db.add(page)
        created = True
    else:
        # Refresh the core list (query-built) + keep operator title/description
        # edits (only sections refresh — rename survives re-seeds).
        page.sections = sections
        created = False
    db.commit()
    logger.info(
        "MoC platform page %s: %s (%d core workflow rows, %d focus rows)",
        "created" if created else "refreshed", page.id, len(rows),
        len(focus_rows),
    )
    return {
        "page_id": page.id,
        "created": created,
        "core_rows": len(rows),
        "focus_rows": len(focus_rows),
    }


def main() -> None:
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
