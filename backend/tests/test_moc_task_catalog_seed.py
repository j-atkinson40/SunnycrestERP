"""MoC-2a seed — manufacturing task catalog (option 1: descriptive + resolve-or-warn).

Two witnesses:
1. Idempotency + orphan-tolerance: the seed runs twice → exactly 2 catalog rows
   (no dup-key), descriptive cells always populate, and the absent workflow/
   focus references log resolve-or-warn warnings (never hard-fail). Join count
   is whatever resolved (0 today — the four referenced templates are queued
   option-3 artifacts), so we assert idempotency + row count, NOT a hardcoded
   join count.
2. Auto-populate (the forward-looking witness): once a referenced template
   EXISTS, the SAME seed resolves it — proving the relational cells light up
   automatically when option-3 lands, the same dynamic the cards use.
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


def test_seed_idempotent_and_orphan_tolerant(db, caplog):
    with caplog.at_level(logging.WARNING):
        _seed_task_catalog(db)
        first = _count_tasks(db)
        _seed_task_catalog(db)  # re-run: must not dup-key
        second = _count_tasks(db)

    # Idempotent: two runs, still exactly the two tasks.
    assert first == 2
    assert second == 2

    # Descriptive cells ALWAYS populate (relational cells may be empty).
    billing = _task(db, "Funeral Home Billing")
    assert billing is not None
    assert billing.frequency == "End of Month"
    assert billing.task_type == "Accounting"
    assert "charge accounts" in billing.description

    # Orphan-tolerance witnessed via the WORKFLOWS — reliably absent until
    # 3c/3d (the focuses are seeded by seed_demo_artifact_focuses since 3a/3b,
    # so they no longer exercise the absent path; the workflows still do).
    assert billing.workflow_template_id is None  # "Invoice and Statement Run" absent
    legacy = _task(db, "New Legacy Order")
    assert legacy.workflow_template_id is None  # "Legacy Order" absent

    # The resolve-or-warn warnings for the absent WORKFLOWS fired (proving
    # orphan-tolerance — a missing ref logs + seeds an empty cell, never fails).
    warned = " ".join(r.message for r in caplog.records)
    assert "Legacy Order" in warned
    assert "Invoice and Statement Run" in warned


def test_seed_auto_populates_when_template_appears(db):
    """Create the referenced 'Invoice and Statement Run' workflow (reliably the
    only one — workflows are absent until 3c), then run the SAME seed — it now
    resolves it. Proves option-3's artifacts light up the cells automatically.
    (The FOCUS auto-populate is covered by test_demo_artifact_focuses_seed,
    which seeds the real Decision Triage / Legacy Generation focuses.)"""
    wf_id = str(uuid.uuid4())
    db.execute(
        sql_text(
            "INSERT INTO workflow_templates (id, scope, workflow_type, "
            "display_name, vertical, is_active) VALUES (:id, 'vertical_default', "
            ":wt, 'Invoice and Statement Run', :v, true)"
        ),
        {"id": wf_id, "wt": f"inv_stmt_{uuid.uuid4().hex[:6]}", "v": VERT},
    )
    db._created_artifacts.append(("workflow_templates", wf_id))
    db.commit()

    _seed_task_catalog(db)

    # "Funeral Home Billing" now resolves its workflow (was empty before).
    billing = _task(db, "Funeral Home Billing")
    assert billing.workflow_template_id == wf_id
