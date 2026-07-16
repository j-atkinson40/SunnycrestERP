"""MoC workflow backfill (Build 1 + 1b; FH stamp) — faithful runtime→canvas mirrors.

For each of the 27 triaged early-development runtime workflows (12 manufacturing +
9 funeral_home + 6 core), create a `workflow_template` whose canvas_state FAITHFULLY
reproduces the runtime workflow's steps, plus a thin `moc_task_catalog` row
pre-wired to it (landing on the owning vertical's map). Per
docs/investigations/moc_workflow_backfill_investigation.md (+ the FH set per
fh_map_investigation.md §2): runtime→canvas is a clean mechanical transform
(all targets linear, no branching, step_types ⊆ {action,input,output} ⊆
VALID_NODE_TYPES, config carries verbatim).

The mirrors are INERT snapshots (canvas ≠ runtime; they do not execute + may
drift). `mirrored_from_workflow_id` records the provenance — the queryable
debt-handle for the future canvas↔runtime bridge. The card refs are authored by
seed_moc_manufacturing (the page owner), which runs AFTER this (alphabetical:
seed_moc_b… < seed_moc_m…) and queries the mirrors.

Idempotent: find-or-update by `mirrored_from_workflow_id` (one mirror per runtime
workflow) + upsert_task by name. Safe to re-run on deploy.

Usage:  cd backend && python -m scripts.seed_moc_backfill_workflow_mirrors
"""
from __future__ import annotations

import json
import logging
import re
import sys
import uuid
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import text as sql_text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.services.maps_of_content.task_catalog import upsert_task  # noqa: E402
from app.services.workflow_templates.canvas_validator import (  # noqa: E402
    validate_canvas_state,
)

logger = logging.getLogger(__name__)

VERTICAL = "manufacturing"

# The exact triaged sets (the investigations' dedup lists). Runtime scope:
#   'vertical' → template scope 'vertical_default' (vertical=<the vertical>)
#   'core'     → template scope 'platform_default' (vertical=None); surfaced on
#                each vertical's card via explicit ref (resolver reads by id).
_MANUFACTURING = [
    "Bridgeable Compose", "New Order", "Order Gloves from Uline",
    "Add Team Certification", "Safety Program Generation",
    "Vault Order Fulfillment", "Log Production Pour", "Schedule Delivery",
    "Social Service Certificate", "Start Disinterment Workflow",
    "Wilbert Catalog Auto-Fetch", "Document Review Reminder",
]
# FH Map stamp — the triaged bring-in 9 (fh_map_investigation.md §1a(a)):
# the case spine + Plot Reservation (demo-critical five) + the completeness
# four. The 3 zero-step shells (obituary / insurance / EDRS) are EXCLUDED by
# triage. All 9 verified inside the clean-transform subset; the validator
# still fails loud if that verdict ever drifts.
_FUNERAL_HOME = [
    "First Call Intake", "Schedule Arrangement Conference",
    "Arrangement Scribe Processing", "7-Day Aftercare Follow-Up",
    "Plot Reservation", "Send Family Info Form", "Coordinate Removal",
    "Anniversary Acknowledgment", "Flag Pre-Need Policy",
]
_CORE = [
    "Month-End Close", "AR Collections", "Compliance Sync",
    "Monthly Statement Run", "Expense Categorization", "Training Expiry Monitor",
    # Ponder P0 — the fifth accounting artifact joins the mirrored set (it was
    # the audit's B-1 gap: no mirror = no step beats for its ponder).
    "Cash Receipts Matching",
]
# (name, runtime_scope, template_scope, template_vertical, task_vertical)
# task_vertical: where the thin task row lands (each vertical's own map).
# Core mirrors keep their task rows on the manufacturing map (the original
# backfill's choice — the platform map's task table is vertical-less).
TARGETS = (
    [(n, "vertical", "vertical_default", VERTICAL, VERTICAL) for n in _MANUFACTURING]
    + [(n, "vertical", "vertical_default", "funeral_home", "funeral_home")
       for n in _FUNERAL_HOME]
    + [(n, "core", "platform_default", None, VERTICAL) for n in _CORE]
)


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return f"mirror_{s}"


def _mirror_canvas(steps: list, trigger_type: str | None) -> dict:
    """Faithful linear transform: node per step, edges consecutive by order."""
    nodes = []
    edges = []
    for i, s in enumerate(steps):
        cfg = s.config if isinstance(s.config, dict) else json.loads(s.config or "{}")
        nodes.append({
            "id": s.step_key,
            "type": s.step_type,
            "label": s.display_name or s.step_key,
            "config": cfg,
            "position": {"x": 0, "y": int(s.step_order) * 120},
        })
        if i > 0:
            edges.append({
                "id": f"e{i}", "source": steps[i - 1].step_key,
                "target": s.step_key, "label": "",
            })
    return {
        "version": 1,
        "trigger": {"type": trigger_type or "manual"},
        "nodes": nodes,
        "edges": edges,
    }


def _find_runtime(db, name: str, runtime_scope: str, vertical: str | None):
    """The canonical runtime workflow (richest by step count — avoids any
    test-fixture thin copy). Finding P-3: vertical-scope lookups also filter
    by vertical — today's FH/MFG name sets are disjoint, but a future name
    collision must not cross-wire a mirror."""
    where = "w.name = :n AND w.scope = :sc"
    params: dict = {"n": name, "sc": runtime_scope}
    if runtime_scope == "vertical" and vertical is not None:
        where += " AND w.vertical = :v"
        params["v"] = vertical
    return db.execute(
        sql_text(
            "SELECT w.id, w.name, w.trigger_type, "
            "(SELECT COUNT(*) FROM workflow_steps s WHERE s.workflow_id = w.id) n "
            f"FROM workflows w WHERE {where} "
            "ORDER BY n DESC, w.created_at ASC LIMIT 1"
        ),
        params,
    ).first()


def _mirror_one(
    db, name, runtime_scope, tmpl_scope, tmpl_vertical, task_vertical
) -> tuple[str | None, str]:
    rt = _find_runtime(db, name, runtime_scope, tmpl_vertical)
    if rt is None:
        logger.warning("[wf-mirror] runtime workflow %r (%s) not found — skip", name, runtime_scope)
        return None, f"{name}: MISSING"
    steps = db.execute(
        sql_text(
            "SELECT step_order, step_key, step_type, display_name, config "
            "FROM workflow_steps WHERE workflow_id = :id ORDER BY step_order"
        ),
        {"id": rt.id},
    ).fetchall()
    canvas = _mirror_canvas(list(steps), rt.trigger_type)
    validate_canvas_state(canvas)  # fail loud if the transform produced an invalid mirror
    canvas_json = json.dumps(canvas)

    # Idempotent by provenance: one mirror per runtime workflow.
    existing = db.execute(
        sql_text("SELECT id FROM workflow_templates WHERE mirrored_from_workflow_id = :w"),
        {"w": rt.id},
    ).first()
    desc = (
        f"Mirror of runtime workflow '{name}' ({rt.id}) — inert snapshot for MoC "
        "navigation; the runtime workflow is the source of truth and may have drifted."
    )
    if existing:
        db.execute(
            sql_text(
                "UPDATE workflow_templates SET display_name = :d, canvas_state = "
                "CAST(:cs AS jsonb), description = :desc, scope = :sc, vertical = :v, "
                "is_active = true, updated_at = now() WHERE id = :id"
            ),
            {"d": name, "cs": canvas_json, "desc": desc, "sc": tmpl_scope,
             "v": tmpl_vertical, "id": existing.id},
        )
        tmpl_id = existing.id
    else:
        tmpl_id = str(uuid.uuid4())
        db.execute(
            sql_text(
                "INSERT INTO workflow_templates (id, scope, vertical, workflow_type, "
                "display_name, description, canvas_state, version, is_active, "
                "mirrored_from_workflow_id, created_at, updated_at) VALUES "
                "(:id, :sc, :v, :wt, :d, :desc, CAST(:cs AS jsonb), 1, true, :w, now(), now())"
            ),
            {"id": tmpl_id, "sc": tmpl_scope, "v": tmpl_vertical, "wt": _slug(name),
             "d": name, "desc": desc, "cs": canvas_json, "w": rt.id},
        )

    # 1b — the thin task row (task_vertical decides which map's table it
    # lands on), workflow pre-wired, descriptive fields BLANK (the operator
    # enriches; the FH demo-critical five first).
    upsert_task(
        db, vertical=task_vertical, name=name, frequency=None, task_type=None,
        description=None, icon="workflow", workflow_template_id=tmpl_id,
        focus_template_ids=[],
    )
    return tmpl_id, f"{name}: {len(canvas['nodes'])} nodes"


def seed(db) -> str:
    made = []
    for name, rsc, tsc, tv, taskv in TARGETS:
        _id, msg = _mirror_one(db, name, rsc, tsc, tv, taskv)
        made.append(msg)
    db.commit()
    ok = [m for m in made if "MISSING" not in m]
    logger.info("[wf-mirror] mirrored %d/%d", len(ok), len(TARGETS))
    return f"mirrored {len(ok)}/{len(TARGETS)} workflows"


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    db = SessionLocal()
    try:
        print(f"[seed_moc_backfill_workflow_mirrors] {seed(db)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
