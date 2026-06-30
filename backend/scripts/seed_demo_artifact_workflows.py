"""Demo artifacts (option-3) — 3c-seed: the Invoice & Statement Run workflow.

Seeds the "Invoice and Statement Run" workflow_template as a vertical_default
manufacturing artifact. Its canvas composes the two `call_service_method` nodes
(3c's adapters) — start → generate invoices → run statements → end. NO new
logic, NO migration (a workflow_templates row + canvas JSON).

WHY THIS LIGHTS UP THE MoC: seed_moc_manufacturing references "Invoice and
Statement Run" by name; this seed runs before it (alphabetical: seed_demo… <
seed_moc…), so the MoC resolves it same-deploy → the "Funeral Home Billing"
task's Workflow Used cell populates + the warning vanishes. Name MUST match the
MoC ref exactly. Idempotent: find-or-create by (scope, vertical, workflow_type).

Usage:  cd backend && python -m scripts.seed_demo_artifact_workflows
"""
from __future__ import annotations

import json
import logging
import sys
import uuid
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import text as sql_text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.services.workflow_templates.canvas_validator import (  # noqa: E402
    validate_canvas_state,
)

logger = logging.getLogger(__name__)

VERTICAL = "manufacturing"
WORKFLOW_TYPE = "invoice_and_statement_run"
DISPLAY_NAME = "Invoice and Statement Run"  # MUST match the MoC ref exactly

CANVAS = {
    "version": 1,
    "trigger": {"type": "manual"},
    "nodes": [
        {"id": "n_start", "type": "start", "label": "Start", "config": {},
         "position": {"x": 0, "y": 0}},
        {"id": "n_invoices", "type": "action",
         "label": "Generate draft invoices",
         "config": {
             "action_type": "call_service_method",
             "method_name": "invoice_statement.run_invoice_generation",
             "kwargs": {},
         },
         "position": {"x": 0, "y": 120}},
        {"id": "n_statements", "type": "action",
         "label": "Run monthly statements",
         "config": {
             "action_type": "call_service_method",
             "method_name": "invoice_statement.run_statement_run",
             "kwargs": {},
         },
         "position": {"x": 0, "y": 240}},
        {"id": "n_end", "type": "end", "label": "End", "config": {},
         "position": {"x": 0, "y": 360}},
    ],
    "edges": [
        {"id": "e1", "source": "n_start", "target": "n_invoices", "label": ""},
        {"id": "e2", "source": "n_invoices", "target": "n_statements", "label": ""},
        {"id": "e3", "source": "n_statements", "target": "n_end", "label": ""},
    ],
}


def seed(db) -> str:
    validate_canvas_state(CANVAS)  # fail loud if the canvas is malformed
    canvas_json = json.dumps(CANVAS)

    row = db.execute(
        sql_text(
            "SELECT id FROM workflow_templates WHERE scope = 'vertical_default' "
            "AND vertical = :v AND workflow_type = :wt"
        ),
        {"v": VERTICAL, "wt": WORKFLOW_TYPE},
    ).first()
    if row:
        db.execute(
            sql_text(
                "UPDATE workflow_templates SET display_name = :d, "
                "canvas_state = CAST(:cs AS jsonb), is_active = true, "
                "updated_at = now() WHERE id = :id"
            ),
            {"d": DISPLAY_NAME, "cs": canvas_json, "id": row.id},
        )
        outcome = "updated"
    else:
        db.execute(
            sql_text(
                "INSERT INTO workflow_templates (id, scope, vertical, "
                "workflow_type, display_name, canvas_state, version, is_active, "
                "created_at, updated_at) VALUES (:id, 'vertical_default', :v, "
                ":wt, :d, CAST(:cs AS jsonb), 1, true, now(), now())"
            ),
            {"id": str(uuid.uuid4()), "v": VERTICAL, "wt": WORKFLOW_TYPE,
             "d": DISPLAY_NAME, "cs": canvas_json},
        )
        outcome = "created"
    db.commit()
    logger.info("[demo-workflow-seed] %r %s", DISPLAY_NAME, outcome)
    return f"{DISPLAY_NAME} {outcome}"


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    db = SessionLocal()
    try:
        print(f"[seed_demo_artifact_workflows] {seed(db)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
