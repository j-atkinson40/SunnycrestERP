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


# ── Legacy Order (option-3 3d) — the four-artifact composition ────
# proof (Legacy Generation HEADLESS via 3b.1) → triage (create_task into the
# Decision Triage queue) → email the approved proof to the print shop →
# notify the funeral home via its preferred method (3d Part 1's node).
LEGACY_ORDER_WORKFLOW_TYPE = "legacy_order"
LEGACY_ORDER_DISPLAY_NAME = "Legacy Order"  # MUST match the MoC ref exactly

LEGACY_ORDER_CANVAS = {
    "version": 1,
    "trigger": {"type": "manual"},
    "nodes": [
        {"id": "n_start", "type": "start", "label": "Start", "config": {},
         "position": {"x": 0, "y": 0}},
        {"id": "n_proof", "type": "action",
         "label": "Generate legacy proof (headless)",
         "config": {
             "action_type": "invoke_generation_focus",
             "focus_id": "legacy_proof_generation",
             "op_id": "generate_proof",
             "kwargs": {"sales_order_id": "{trigger.sales_order_id}"},
         },
         "position": {"x": 0, "y": 120}},
        {"id": "n_triage", "type": "action",
         "label": "Stage proof for review (Decision Triage)",
         "config": {
             # invoke_review_focus (NOT create_task): pauses the run on a
             # WorkflowReviewItem that surfaces in workflow_review_triage — the
             # queue the Decision Triage focus renders. Approving there resumes
             # the run (send_document + notify below). create_task staged into a
             # lifecycle state no triage queue reads (3a.1 repair).
             "action_type": "invoke_review_focus",
             "review_focus_id": "legacy_proof_review",
             "input_data": {
                 "deceased_name": "{output.n_proof.deceased_name}",
                 "proof_size_bytes": "{output.n_proof.proof_size_bytes}",
                 "sales_order_id": "{trigger.sales_order_id}",
             },
         },
         "position": {"x": 0, "y": 240}},
        {"id": "n_email", "type": "send_document",
         "label": "Email approved proof to the print shop",
         "config": {
             "channel": "email",
             "recipient": {"type": "email_address",
                           "value": "{trigger.print_shop_email}"},
             "subject": "Approved legacy proof",
             "body": "The attached legacy proof has been approved for print.",
         },
         "position": {"x": 0, "y": 360}},
        {"id": "n_notify", "type": "action",
         "label": "Notify funeral home (preferred method)",
         "config": {
             "action_type": "notify_via_contact_preference",
             "customer_id": "{trigger.funeral_home_customer_id}",
             "body": "Your legacy proof has been approved and sent to the "
                     "print shop.",
         },
         "position": {"x": 0, "y": 480}},
        {"id": "n_end", "type": "end", "label": "End", "config": {},
         "position": {"x": 0, "y": 600}},
    ],
    "edges": [
        {"id": "e1", "source": "n_start", "target": "n_proof", "label": ""},
        {"id": "e2", "source": "n_proof", "target": "n_triage", "label": ""},
        {"id": "e3", "source": "n_triage", "target": "n_email", "label": ""},
        {"id": "e4", "source": "n_email", "target": "n_notify", "label": ""},
        {"id": "e5", "source": "n_notify", "target": "n_end", "label": ""},
    ],
}

# All demo-artifact workflows seeded by this script: (workflow_type, name, canvas)
_WORKFLOWS = [
    (WORKFLOW_TYPE, DISPLAY_NAME, CANVAS),
    (LEGACY_ORDER_WORKFLOW_TYPE, LEGACY_ORDER_DISPLAY_NAME, LEGACY_ORDER_CANVAS),
]


def _seed_one(db, workflow_type: str, display_name: str, canvas: dict) -> str:
    validate_canvas_state(canvas)  # fail loud if the canvas is malformed
    canvas_json = json.dumps(canvas)

    row = db.execute(
        sql_text(
            "SELECT id FROM workflow_templates WHERE scope = 'vertical_default' "
            "AND vertical = :v AND workflow_type = :wt"
        ),
        {"v": VERTICAL, "wt": workflow_type},
    ).first()
    if row:
        db.execute(
            sql_text(
                "UPDATE workflow_templates SET display_name = :d, "
                "canvas_state = CAST(:cs AS jsonb), is_active = true, "
                "updated_at = now() WHERE id = :id"
            ),
            {"d": display_name, "cs": canvas_json, "id": row.id},
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
            {"id": str(uuid.uuid4()), "v": VERTICAL, "wt": workflow_type,
             "d": display_name, "cs": canvas_json},
        )
        outcome = "created"
    db.commit()
    logger.info("[demo-workflow-seed] %r %s", display_name, outcome)
    return f"{display_name} {outcome}"


def seed(db) -> str:
    return "; ".join(_seed_one(db, wt, dn, cv) for wt, dn, cv in _WORKFLOWS)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    db = SessionLocal()
    try:
        print(f"[seed_demo_artifact_workflows] {seed(db)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
