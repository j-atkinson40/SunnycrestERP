"""MoC-2a seed — manufacturing task catalog (option 1: descriptive + resolve-or-warn).

Witnesses (post-3d, all four real demo artifacts now exist, so the
mechanism tests use SYNTHETIC guaranteed-absent names — independent of seed state):
1. Idempotency + descriptive cells: the seed runs twice → exactly 2 catalog
   rows (no dup-key), descriptive cells always populate.
2. Orphan-tolerance: a reference to an absent template resolves to None / []
   + warns (never hard-fails) — exercised via the resolve-or-warn helpers with
   a synthetic absent name.
3. Auto-populate (the forward-looking witness): a task referencing an absent
   template seeds an empty cell, then resolves it once the template EXISTS —
   the same dynamic the cards use, exercised with a synthetic task + workflow.
"""
from __future__ import annotations

import logging
import uuid

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal

from scripts.seed_moc_manufacturing import _seed_task_catalog

VERT = "manufacturing"
TASK_NAMES = ("Funeral Home Billing", "New Legacy Order")


@pytest.fixture
def db():
    s = SessionLocal()
    created_artifacts: list[tuple[str, str]] = []  # (table, id) to clean
    s._created_artifacts = created_artifacts  # stash for tests
    yield s
    # teardown: drop the seeded tasks (cascades focus joins) + any artifacts a
    # test created, so bridgeable_dev isn't polluted across runs.
    s.rollback()
    for name in TASK_NAMES:
        s.execute(
            sql_text(
                "DELETE FROM moc_task_catalog WHERE vertical = :v AND name = :n"
            ),
            {"v": VERT, "n": name},
        )
    for table, _id in created_artifacts:
        s.execute(sql_text(f"DELETE FROM {table} WHERE id = :id"), {"id": _id})
    s.commit()
    s.close()


def _count_tasks(db) -> int:
    return db.execute(
        sql_text(
            "SELECT COUNT(*) FROM moc_task_catalog WHERE vertical = :v "
            "AND scope = 'vertical_default'"
        ),
        {"v": VERT},
    ).scalar()


def _task(db, name: str):
    return db.execute(
        sql_text(
            "SELECT id, frequency, task_type, description, workflow_template_id "
            "FROM moc_task_catalog WHERE vertical = :v AND name = :n"
        ),
        {"v": VERT, "n": name},
    ).first()


def test_seed_idempotent_and_descriptive(db):
    """Idempotency + descriptive cells always populate. (The relational cells
    resolve whatever's seeded; post-3d the real demo workflows/focuses exist,
    so they populate — orphan-tolerance + auto-populate get their own synthetic
    tests below, robust to seed state.)"""
    _seed_task_catalog(db)
    first = _count_tasks(db)
    _seed_task_catalog(db)  # re-run: must not dup-key
    second = _count_tasks(db)

    assert first == 2
    assert second == 2

    billing = _task(db, "Funeral Home Billing")
    assert billing is not None
    assert billing.frequency == "End of Month"
    assert billing.task_type == "Accounting"
    assert "charge accounts" in billing.description


def test_orphan_tolerance_resolve_or_warn(db, caplog):
    """A reference to an ABSENT template resolves to None / [] + warns — never
    hard-fails. Synthetic guaranteed-absent name → robust to seed state."""
    from scripts.seed_moc_manufacturing import (
        _resolve_focus_ids,
        _resolve_workflow_id,
    )

    absent = f"DEFINITELY-ABSENT-{uuid.uuid4().hex}"
    with caplog.at_level(logging.WARNING):
        assert _resolve_workflow_id(db, absent) is None
        assert _resolve_focus_ids(db, [absent]) == []
    warned = " ".join(r.message for r in caplog.records)
    assert absent in warned


def test_seed_auto_populates_when_template_appears(db):
    """A task referencing an absent workflow seeds an empty cell, then resolves
    it once the template EXISTS — option-3's auto-populate dynamic. Synthetic
    unique task + workflow name → isolated from the now-seeded real demo
    workflows (which would otherwise collide on the LIMIT-1 resolve)."""
    from app.services.maps_of_content.task_catalog import upsert_task
    from scripts.seed_moc_manufacturing import _resolve_workflow_id

    task_name = f"Synthetic Task {uuid.uuid4().hex[:8]}"
    wf_name = f"Synthetic WF {uuid.uuid4().hex[:8]}"

    def _upsert():
        return upsert_task(
            db, vertical=VERT, name=task_name, frequency="On demand",
            task_type="Synthetic", description="synthetic", icon="receipt",
            workflow_template_id=_resolve_workflow_id(db, wf_name),
            focus_template_ids=[], display_order=99,
        )

    # 1) Workflow absent → the task seeds an empty workflow cell.
    t = _upsert()
    db._created_artifacts.append(("moc_task_catalog", t.id))
    db.commit()
    assert _task(db, task_name).workflow_template_id is None

    # 2) The workflow appears.
    wf_id = str(uuid.uuid4())
    db.execute(
        sql_text(
            "INSERT INTO workflow_templates (id, scope, workflow_type, "
            "display_name, vertical, is_active) VALUES (:id, 'vertical_default', "
            ":wt, :dn, :v, true)"
        ),
        {"id": wf_id, "wt": f"syn_{uuid.uuid4().hex[:6]}", "dn": wf_name, "v": VERT},
    )
    db._created_artifacts.append(("workflow_templates", wf_id))
    db.commit()

    # 3) Re-seed the SAME task → it now resolves the workflow (cell lit).
    _upsert()
    db.commit()
    assert _task(db, task_name).workflow_template_id == wf_id
