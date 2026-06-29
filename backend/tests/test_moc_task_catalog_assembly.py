"""MoC-2a ASSEMBLY TEST (the load-bearing witness — before any UI).

Proves the WHOLE round-trip through the REAL models, the JCF-1 discipline:
a moc_task_catalog row with a real workflow_template + TWO real focus_templates
persists and reads back through the resolver with DEEP-LINKABLE routing — the
SAME routing the MoC cards produce for those artifacts (the deep-link-reuse
keystone). The two-focus case is required (proves the join holds many — the
"New Legacy Order" shape). If this doesn't round-trip, the schema is wrong and
better caught here than after the table is built.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.services.maps_of_content.service import BUILDERS
from app.services.maps_of_content.task_catalog import (
    resolve_task_catalog,
    upsert_task,
)

VERT = "manufacturing"


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


def _real_workflow(db) -> tuple[str, str]:
    """Create a REAL workflow_templates row; return (id, workflow_type)."""
    wid, wtype = str(uuid.uuid4()), f"assembly_wf_{uuid.uuid4().hex[:6]}"
    db.execute(
        sql_text(
            "INSERT INTO workflow_templates (id, scope, workflow_type, "
            "display_name, vertical, is_active) VALUES (:id, 'vertical_default', "
            ":wt, 'Assembly Test Workflow', :v, true)"
        ),
        {"id": wid, "wt": wtype, "v": VERT},
    )
    return wid, wtype


def _real_focus(db, core_id: str, core_ver, label: str) -> tuple[str, str]:
    """Create a REAL focus_templates row (reusing an existing core to satisfy
    the inherits_from_core FK); return (id, template_slug)."""
    fid, slug = str(uuid.uuid4()), f"assembly-focus-{uuid.uuid4().hex[:6]}"
    db.execute(
        sql_text(
            "INSERT INTO focus_templates (id, scope, template_slug, "
            "display_name, inherits_from_core_id, inherits_from_core_version, "
            "vertical, is_active) VALUES (:id, 'vertical_default', :slug, :dn, "
            ":core, :cver, :v, true)"
        ),
        {"id": fid, "slug": slug, "dn": label, "core": core_id,
         "cver": core_ver, "v": VERT},
    )
    return fid, slug


def test_task_with_workflow_and_two_focuses_round_trips(db):
    # Reuse an existing focus's core to satisfy the inherits_from_core FK.
    core = db.execute(
        sql_text(
            "SELECT inherits_from_core_id, inherits_from_core_version "
            "FROM focus_templates LIMIT 1"
        )
    ).first()
    assert core is not None, "need an existing focus_template to borrow a core"

    wf_id, wf_type = _real_workflow(db)
    f1_id, f1_slug = _real_focus(db, core[0], core[1], "Legacy Generation")
    f2_id, f2_slug = _real_focus(db, core[0], core[1], "Decision Triage")
    db.flush()

    task = upsert_task(
        db,
        vertical=VERT,
        name=f"Assembly Task {uuid.uuid4().hex[:6]}",
        frequency="End of Month",
        task_type="Accounting",
        description="Assembly round-trip: one workflow + two focuses.",
        workflow_template_id=wf_id,
        focus_template_ids=[f1_id, f2_id],  # the TWO-focus case (required)
    )
    db.flush()

    # Read back through the resolver (the path the table will use).
    resolved = [
        t for t in resolve_task_catalog(db, vertical=VERT) if t["id"] == task.id
    ]
    assert len(resolved) == 1
    t = resolved[0]

    # The row carries its descriptive columns.
    assert t["name"].startswith("Assembly Task")
    assert t["frequency"] == "End of Month"
    assert t["task_type"] == "Accounting"
    assert t["description"]

    # The workflow resolves to a DEEP-LINKABLE route (the routing the card's
    # mocDeepLink consumes: workflow_type + scope), reflecting the real row.
    assert t["workflow"] is not None
    assert t["workflow"]["available"] is True
    assert t["workflow"]["routing"]["workflow_type"] == wf_type
    assert t["workflow"]["routing"]["scope"] == "vertical_default"

    # BOTH focuses resolve to their deep-linkable routes (template_slug),
    # proving the join holds many.
    assert len(t["focuses"]) == 2
    slugs = {f["routing"]["template_slug"] for f in t["focuses"]}
    assert slugs == {f1_slug, f2_slug}
    assert all(f["available"] for f in t["focuses"])

    # KEYSTONE: the task resolver's routing is byte-identical to the cards' —
    # because both go through the SAME BUILDERS path (not a parallel resolver).
    assert t["workflow"]["routing"] == BUILDERS["workflows"](db, wf_id, "x")["routing"]
    assert t["focuses"][0]["routing"] == BUILDERS["focuses"](db, f1_id, "")["routing"]
