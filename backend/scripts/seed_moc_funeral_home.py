"""Seed the Funeral Home Map of Content (FH Map stamp — the second vertical).

Follows seed_moc_manufacturing's proven shape (find-or-create by (scope,
vertical, slug); sections REFRESHED on re-run; operator title renames
PRESERVED per the platform seed's H-2 pattern). September-critical: Hopkins
FH is the pilot tenant; this page is the ground the demo walk stands on.

Cards, all query-built (content-agnostic, resolve-or-skip, self-healing):
  - WORKFLOWS: the 9 triaged FH mirrors (fh_map_investigation.md §1a(a))
    + the 6 core mirrors (include-core canon — platform_default scope,
    referenced by id, same mechanism as the manufacturing card).
  - FOCUSES: QUERY-BUILT FROM THE JOIN TABLE + vertical-owned templates —
    Cemetery Triage surfaces because its funeral_home join row exists (the
    V-1 log-skip made real, idempotently), and every FUTURE variation
    scoped to FH lights this card with ZERO seed edits.
  - DOCUMENTS: the one honest FH ref (email.fh_aftercare_7day).
  - WIDGETS: Today's Services.

Thin task rows (name + workflow pill) are seeded by the mirror pass
(seed_moc_backfill_workflow_mirrors, task_vertical='funeral_home' — runs
earlier: seed_moc_b… < seed_moc_f…). Descriptive cells stay em-dash for
operator enrichment (the demo-critical five first).

Usage:
    cd backend && python -m scripts.seed_moc_funeral_home
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

VERTICAL = "funeral_home"
SLUG = "funeral-home-map"
TITLE = "Funeral Home"
DESCRIPTION = "Artifact-first navigation for funeral service operations."


def focus_rows_for_vertical(db, vertical: str) -> list[dict]:
    """The Focuses card, QUERY-BUILT (the FH-stamp mechanism): every ACTIVE
    focus template OWNED by the vertical + every lineage JOINED to it via
    focus_template_verticals (multi-vertical variations — slug-keyed, so the
    rows survive version rotation). A variation created tomorrow surfaces on
    the next seed run with no seed edit; between runs the V-1 flow's
    auto-authoring covers the gap."""
    rows = db.execute(
        sql_text(
            "SELECT DISTINCT ft.id, ft.display_name, ft.template_slug "
            "FROM focus_templates ft "
            "LEFT JOIN focus_template_verticals ftv "
            "  ON ftv.template_slug = ft.template_slug "
            "WHERE ft.is_active = true AND ft.scope = 'vertical_default' "
            "AND (ft.vertical = :v OR ftv.vertical = :v) "
            "ORDER BY ft.display_name"
        ),
        {"v": vertical},
    ).fetchall()
    return [
        {
            "builder": "focuses",
            "artifact_id": r.id,
            "label": r.display_name,
            "icon": "focus",
        }
        for r in rows
    ]


def _resolve_artifacts(db) -> list[dict]:
    """Look each reference up by STABLE key → an MoC row. A miss is logged +
    omitted (self-heals on the next run)."""
    rows: list[dict] = []

    # WORKFLOWS — the FH mirrors + the core mirrors (include-core canon:
    # platform_default rows referenced by id, exactly the manufacturing
    # card's mechanism, confirmed carrying to a second vertical).
    mirror_rows = db.execute(
        sql_text(
            "SELECT id, display_name FROM workflow_templates "
            "WHERE mirrored_from_workflow_id IS NOT NULL AND is_active = true "
            "AND (vertical = :v OR scope = 'platform_default') "
            "ORDER BY display_name"
        ),
        {"v": VERTICAL},
    ).fetchall()
    if mirror_rows:
        for m in mirror_rows:
            rows.append(
                {"builder": "workflows", "artifact_id": m.id,
                 "label": m.display_name, "icon": "workflow"}
            )
    else:
        logger.warning(
            "seed_moc_funeral_home: no FH/core workflow mirrors found "
            "(run seed_moc_backfill_workflow_mirrors first)"
        )

    # FOCUSES — the join-table query (Cemetery Triage + future variations).
    focus_rows = focus_rows_for_vertical(db, VERTICAL)
    if focus_rows:
        rows.extend(focus_rows)
    else:
        logger.warning("seed_moc_funeral_home: no FH-scoped focus templates yet")

    # WIDGETS — Today's Services (the one FH-shaped widget).
    wid = db.execute(
        sql_text(
            "SELECT id FROM widget_definitions WHERE widget_id = "
            "'todays_services' LIMIT 1"
        )
    ).first()
    if wid:
        rows.append(
            {"builder": "widgets", "artifact_id": wid.id,
             "label": "Today's Services", "icon": "widget"}
        )
    else:
        logger.warning("seed_moc_funeral_home: todays_services widget absent")

    # DOCUMENTS — the one honest FH ref (platform-scope aftercare email, r40).
    doc = db.execute(
        sql_text(
            "SELECT id FROM document_templates WHERE template_key = "
            "'email.fh_aftercare_7day' AND company_id IS NULL LIMIT 1"
        )
    ).first()
    if doc:
        rows.append(
            {"builder": "documents", "artifact_id": doc.id,
             "label": "7-Day Aftercare Email", "icon": "document"}
        )
    else:
        logger.warning("seed_moc_funeral_home: email.fh_aftercare_7day absent")

    return rows


def seed(db) -> str:
    rows = _resolve_artifacts(db)
    sections = [
        {
            "section_id": "funeral-service",
            "title": "Funeral Service",
            "description": "The artifacts that run funeral service operations.",
            "rows": rows,
        }
    ]

    existing = moc.list_pages(db, scope="vertical_default", vertical=VERTICAL)
    existing = [p for p in existing if p.slug == SLUG]
    if existing:
        # Sections refresh (query-built); operator title/description renames
        # PRESERVED (the H-2 platform-seed pattern).
        moc.update_page(db, existing[0].id, sections=sections)
        return f"updated ({len(rows)} refs)"

    moc.create_page(
        db,
        scope="vertical_default",
        vertical=VERTICAL,
        slug=SLUG,
        title=TITLE,
        description=DESCRIPTION,
        sections=sections,
    )
    return f"created ({len(rows)} refs)"


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    db = SessionLocal()
    try:
        print(f"[seed_moc_funeral_home] {seed(db)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
