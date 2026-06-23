"""Seed the Manufacturing Map of Content (MoC Phase 1).

The narrowest real end-to-end path: ONE vertical's authored MoC page whose
rows reference REAL artifacts in each of the four wired builders —
workflow (quote_to_pour), focus (job-coordination), widget (ar_summary),
document (quote.standard). Every reference is platform-canonical content
seeded by its own canonical-runner seed, so this map is platform-canonical
too (safe in production; no demo guard).

Robust to seed ORDER: it looks each artifact up by stable key and UPSERTS
the page with whatever currently resolves. If a referenced seed (e.g. the
Phase-4 workflow templates) hasn't run yet on this pass, that row is
omitted with a log line and filled in on the next run — so the canonical
runner's unordered discovery can't leave a half-built map.

Usage:
    cd backend && python -m scripts.seed_moc_manufacturing
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import text as sql_text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.services import maps_of_content as moc  # noqa: E402

logger = logging.getLogger(__name__)

VERTICAL = "manufacturing"
SLUG = "manufacturing-map"


def _resolve_artifacts(db) -> list[dict]:
    """Look each wired-builder reference up by STABLE key → an MoC row.
    A miss is logged + omitted (self-heals on the next run)."""
    rows: list[dict] = []

    wf = db.execute(
        sql_text(
            "SELECT id FROM workflow_templates "
            "WHERE workflow_type = 'quote_to_pour' AND scope = 'vertical_default' "
            "AND vertical = :v LIMIT 1"
        ),
        {"v": VERTICAL},
    ).first()
    if wf:
        rows.append(
            {
                "builder": "workflows",
                "artifact_id": wf.id,
                "label": "Quote → Pour",
                "icon": "workflow",
            }
        )
    else:
        logger.warning("seed_moc_manufacturing: quote_to_pour workflow absent")

    foc = db.execute(
        sql_text(
            "SELECT id FROM focus_templates WHERE template_slug = "
            "'job-coordination' LIMIT 1"
        )
    ).first()
    if foc:
        rows.append(
            {
                "builder": "focuses",
                "artifact_id": foc.id,
                "label": "Job Coordination",
                "icon": "focus",
            }
        )
    else:
        logger.warning("seed_moc_manufacturing: job-coordination focus absent")

    wid = db.execute(
        sql_text(
            "SELECT id FROM widget_definitions WHERE widget_id = 'ar_summary' "
            "LIMIT 1"
        )
    ).first()
    if wid:
        rows.append(
            {
                "builder": "widgets",
                "artifact_id": wid.id,
                "label": "Accounts Receivable",
                "icon": "widget",
            }
        )
    else:
        logger.warning("seed_moc_manufacturing: ar_summary widget absent")

    doc = db.execute(
        sql_text(
            "SELECT id FROM document_templates WHERE template_key = "
            "'quote.standard' LIMIT 1"
        )
    ).first()
    if doc:
        rows.append(
            {
                "builder": "documents",
                "artifact_id": doc.id,
                "label": "Standard Quote",
                "icon": "document",
            }
        )
    else:
        logger.warning("seed_moc_manufacturing: quote.standard document absent")

    return rows


def seed(db) -> str:
    rows = _resolve_artifacts(db)
    sections = [
        {
            "title": "Production",
            "description": "The artifacts that run the manufacturing floor.",
            "rows": rows,
        }
    ]

    existing = moc.list_pages(
        db, scope="vertical_default", vertical=VERTICAL
    )
    existing = [p for p in existing if p.slug == SLUG]
    if existing:
        moc.update_page(
            db,
            existing[0].id,
            title="Manufacturing",
            description="Artifact-first navigation for the manufacturing floor.",
            sections=sections,
        )
        return f"updated ({len(rows)} refs)"

    moc.create_page(
        db,
        scope="vertical_default",
        vertical=VERTICAL,
        slug=SLUG,
        title="Manufacturing",
        description="Artifact-first navigation for the manufacturing floor.",
        sections=sections,
    )
    return f"created ({len(rows)} refs)"


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    db = SessionLocal()
    try:
        print(f"[seed_moc_manufacturing] {seed(db)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
