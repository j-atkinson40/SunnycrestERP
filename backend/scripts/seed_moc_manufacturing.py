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
from app.services.maps_of_content.task_catalog import upsert_task  # noqa: E402

logger = logging.getLogger(__name__)

VERTICAL = "manufacturing"
SLUG = "manufacturing-map"

# MoC-2a task catalog (option 1): the two Notion-example tasks. Their workflow/
# focus references are resolved by NAME at seed time — resolve-or-warn: a
# reference that doesn't exist yet (the four are queued option-3 artifacts)
# seeds an empty relational cell + logs, and AUTO-POPULATES on a later run once
# the template is seeded (the resolver is dynamic). Descriptive cells always
# populate. Platform-canonical (real platform artifacts; no demo guard).
TASK_CATALOG = [
    {
        "name": "Funeral Home Billing",
        "frequency": "End of Month",
        "task_type": "Accounting",
        "description": (
            "End of month billing for funeral homes with charge accounts. "
            "Includes all invoices from the month as well as a statement."
        ),
        "icon": "receipt",
        "workflow_name": "Invoice and Statement Run",
        "focus_names": ["Decision Triage"],
    },
    {
        "name": "New Legacy Order",
        "frequency": "On demand",
        "task_type": "Funeral Service Operations",
        "description": (
            "Creates a legacy proof using the legacy generator focus headless "
            "that then gets added to a decision triage queue for approval. "
            "After approval it is emailed to the print shop and the funeral "
            "home is alerted through preferred notification method."
        ),
        "icon": "sparkles",
        "workflow_name": "Legacy Order",
        # The two-focus case — lights up when both templates are seeded.
        "focus_names": ["Legacy Generation", "Decision Triage"],
    },
]


def _resolve_workflow_id(db, name: str) -> str | None:
    """Resolve a workflow by display_name (preferring this vertical) → id, or
    warn + None if absent (orphan-tolerant; never hard-fails the seed)."""
    row = db.execute(
        sql_text(
            "SELECT id FROM workflow_templates WHERE display_name = :n "
            "ORDER BY (vertical = :v) DESC LIMIT 1"
        ),
        {"n": name, "v": VERTICAL},
    ).first()
    if row is None:
        logger.warning(
            "[moc-task-seed] workflow %r not found — task seeded with empty "
            "workflow cell, will populate when the template is seeded",
            name,
        )
        return None
    return row[0]


def _resolve_focus_ids(db, names: list[str]) -> list[str]:
    """Resolve focuses by display_name → ids, warning + skipping any absent
    (orphan-tolerant). Returns only the ids that resolved (0..N)."""
    ids: list[str] = []
    for name in names:
        row = db.execute(
            sql_text(
                "SELECT id FROM focus_templates WHERE display_name = :n LIMIT 1"
            ),
            {"n": name},
        ).first()
        if row is None:
            logger.warning(
                "[moc-task-seed] focus %r not found — task seeded without that "
                "focus pill, will populate when the template is seeded",
                name,
            )
        else:
            ids.append(row[0])
    return ids


def _seed_task_catalog(db) -> str:
    """Idempotent (find-or-create by name+vertical via upsert_task) seed of the
    manufacturing task catalog. Commits."""
    for order, t in enumerate(TASK_CATALOG):
        upsert_task(
            db,
            vertical=VERTICAL,
            name=t["name"],
            frequency=t["frequency"],
            task_type=t["task_type"],
            description=t["description"],
            icon=t["icon"],
            workflow_template_id=_resolve_workflow_id(db, t["workflow_name"]),
            focus_template_ids=_resolve_focus_ids(db, t["focus_names"]),
            display_order=order,
        )
    db.commit()
    return f"{len(TASK_CATALOG)} tasks"


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

    # Demo-artifact workflow (option-3 3c) — surface "Invoice and Statement Run"
    # in the Workflows CARD too (the task-table Workflow cell populates via the
    # task-catalog ref). Resolve-or-skip: seed_demo_artifact_workflows seeds it
    # and runs earlier (alphabetical), so it resolves same-deploy.
    isr = db.execute(
        sql_text(
            "SELECT id FROM workflow_templates WHERE workflow_type = "
            "'invoice_and_statement_run' AND vertical = :v LIMIT 1"
        ),
        {"v": VERTICAL},
    ).first()
    if isr:
        rows.append(
            {"builder": "workflows", "artifact_id": isr.id,
             "label": "Invoice and Statement Run", "icon": "workflow"}
        )
    else:
        logger.warning(
            "seed_moc_manufacturing: invoice_and_statement_run workflow absent "
            "(run seed_demo_artifact_workflows first)"
        )

    # Demo-artifact workflow (option-3 3d) — "Legacy Order" on the Workflows
    # CARD (the four-artifact composition; the task-table Workflow cell for
    # "New Legacy Order" populates via the task-catalog ref). Resolve-or-skip.
    lo = db.execute(
        sql_text(
            "SELECT id FROM workflow_templates WHERE workflow_type = "
            "'legacy_order' AND vertical = :v LIMIT 1"
        ),
        {"v": VERTICAL},
    ).first()
    if lo:
        rows.append(
            {"builder": "workflows", "artifact_id": lo.id,
             "label": "Legacy Order", "icon": "workflow"}
        )
    else:
        logger.warning(
            "seed_moc_manufacturing: legacy_order workflow absent "
            "(run seed_demo_artifact_workflows first)"
        )

    # Workflow backfill (Build 1b; FH stamp) — the faithful runtime mirrors
    # created by seed_moc_backfill_workflow_mirrors (runs earlier:
    # seed_moc_b… < seed_moc_m…). THIS vertical's mirrors + the core mirrors
    # (platform_default scope, referenced by id). The vertical filter became
    # load-bearing at the FH stamp — without it the FH nine would pollute
    # this card. Resolve-or-skip.
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
            "seed_moc_manufacturing: no workflow mirrors found "
            "(run seed_moc_backfill_workflow_mirrors first)"
        )

    # FOCUSES — the FH-stamp back-port: QUERY-BUILT from ownership + the
    # focus_template_verticals join (both maps self-maintaining the same
    # way). Replaces the hardcoded slug list (job-coordination /
    # decision-triage / legacy-generation) — every template OWNED by this
    # vertical or JOINED to it surfaces, including variations created via
    # the V-1 flow, with zero seed edits.
    from scripts.seed_moc_funeral_home import focus_rows_for_vertical

    focus_rows = focus_rows_for_vertical(db, VERTICAL)
    if focus_rows:
        rows.extend(focus_rows)
    else:
        logger.warning(
            "seed_moc_manufacturing: no manufacturing-scoped focus templates "
            "yet (run the focus seeds first)"
        )

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
        tasks = _seed_task_catalog(db)
        return f"updated ({len(rows)} refs, {tasks})"

    moc.create_page(
        db,
        scope="vertical_default",
        vertical=VERTICAL,
        slug=SLUG,
        title="Manufacturing",
        description="Artifact-first navigation for the manufacturing floor.",
        sections=sections,
    )
    tasks = _seed_task_catalog(db)
    return f"created ({len(rows)} refs, {tasks})"


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    db = SessionLocal()
    try:
        print(f"[seed_moc_manufacturing] {seed(db)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
