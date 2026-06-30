"""Demo artifacts 3c — the Invoice & Statement Run workflow_template seed.

Idempotency + a valid canvas + the MoC keystone (the workflow cell + Workflows
card populate once the template exists — the auto-populate firing for workflows).
"""
from __future__ import annotations

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.services.workflow_templates.canvas_validator import validate_canvas_state

from scripts.seed_demo_artifact_workflows import (
    CANVAS,
    LEGACY_ORDER_WORKFLOW_TYPE,
    WORKFLOW_TYPE,
    seed,
)

VERT = "manufacturing"


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    # seed() now seeds BOTH demo workflows — clean both.
    s.execute(
        sql_text(
            "DELETE FROM workflow_templates WHERE workflow_type IN "
            "(:wt, :lo) AND vertical = :v"
        ),
        {"wt": WORKFLOW_TYPE, "lo": LEGACY_ORDER_WORKFLOW_TYPE, "v": VERT},
    )
    s.commit()
    s.close()


def test_canvas_is_valid():
    # The composed canvas passes the canonical validator (start → 2
    # call_service_method nodes → end).
    validate_canvas_state(CANVAS)  # raises on invalid


def test_workflow_seed_idempotent(db):
    seed(db)
    seed(db)  # re-run must not dup
    n = db.execute(
        sql_text(
            "SELECT COUNT(*) FROM workflow_templates WHERE workflow_type = :wt "
            "AND vertical = :v AND scope = 'vertical_default'"
        ),
        {"wt": WORKFLOW_TYPE, "v": VERT},
    ).scalar()
    assert n == 1

    # It carries the composed canvas (the two adapter method calls).
    cs = db.execute(
        sql_text(
            "SELECT canvas_state FROM workflow_templates WHERE workflow_type = :wt "
            "AND vertical = :v"
        ),
        {"wt": WORKFLOW_TYPE, "v": VERT},
    ).scalar()
    methods = [
        n["config"].get("method_name")
        for n in cs["nodes"]
        if n["config"].get("action_type") == "call_service_method"
    ]
    assert methods == [
        "invoice_statement.run_invoice_generation",
        "invoice_statement.run_statement_run",
    ]
