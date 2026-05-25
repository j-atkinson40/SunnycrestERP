"""Task substrate v1 — backfill script tests.

Covers:
- Legacy 5-state → action-shape mapping (per lifecycle.LEGACY_STATUS_MAP)
- backfill_for_tenant creates 1:1 VaultItem + task_details rows per Task
- Idempotent re-runs (no extra rows)
- ENVIRONMENT=production refusal guard
- Empty tenant (no Task rows) handled gracefully
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import date, datetime, timedelta, timezone


def _seed_legacy_tasks(db, company_id, user_id):
    """Seed 5 legacy Task rows covering all 5 statuses."""
    from app.models.task import Task

    tasks = []
    for status in ("open", "in_progress", "blocked", "done", "cancelled"):
        t = Task(
            id=str(uuid.uuid4()),
            company_id=company_id,
            title=f"legacy {status}",
            description="legacy desc",
            assignee_user_id=user_id if status != "open" else None,
            created_by_user_id=user_id,
            priority="normal",
            status=status,
            due_date=date.today() + timedelta(days=5),
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(t)
        tasks.append(t)
    db.commit()
    return tasks


def test_backfill_creates_vault_items_and_task_details(db_session, ts_ctx):
    from app.models.task_details import TaskDetails
    from app.models.vault_item import VaultItem
    from scripts.seed_task_substrate_backfill import backfill_for_tenant

    _seed_legacy_tasks(db_session, ts_ctx["company_id"], ts_ctx["user_id"])

    counts = backfill_for_tenant(
        db_session, company_id=ts_ctx["company_id"], dry_run=False
    )
    assert counts["created"] == 5
    assert counts["skipped"] == 0
    assert counts["failed"] == 0

    vis = (
        db_session.query(VaultItem)
        .filter(
            VaultItem.company_id == ts_ctx["company_id"],
            VaultItem.item_type == "task",
        )
        .all()
    )
    assert len(vis) == 5

    tds = (
        db_session.query(TaskDetails)
        .filter(
            TaskDetails.provenance_ref_type == "legacy_task",
        )
        .all()
    )
    # At least 5 from this tenant (could be more if other tests seeded).
    matching = [
        t for t in tds
        if t.vault_item and t.vault_item.company_id == ts_ctx["company_id"]
    ]
    assert len(matching) == 5


def test_backfill_idempotent(db_session, ts_ctx):
    from scripts.seed_task_substrate_backfill import backfill_for_tenant

    _seed_legacy_tasks(db_session, ts_ctx["company_id"], ts_ctx["user_id"])

    counts1 = backfill_for_tenant(
        db_session, company_id=ts_ctx["company_id"], dry_run=False
    )
    counts2 = backfill_for_tenant(
        db_session, company_id=ts_ctx["company_id"], dry_run=False
    )
    assert counts1["created"] == 5
    assert counts2["created"] == 0
    assert counts2["skipped"] == 5


def test_backfill_legacy_status_mapping(db_session, ts_ctx):
    """Verify each legacy status maps to the expected action-shape state."""
    from app.models.task import Task
    from app.models.task_details import TaskDetails
    from scripts.seed_task_substrate_backfill import backfill_for_tenant

    _seed_legacy_tasks(db_session, ts_ctx["company_id"], ts_ctx["user_id"])
    backfill_for_tenant(
        db_session, company_id=ts_ctx["company_id"], dry_run=False
    )

    # 'open' with assignee=NULL maps to 'created' per
    # legacy_status_to_action_state. Our seeding sets assignee=NULL for
    # status='open', so this row's current_state must be 'created'.
    open_task = (
        db_session.query(Task)
        .filter(
            Task.company_id == ts_ctx["company_id"], Task.status == "open"
        )
        .first()
    )
    td_open = (
        db_session.query(TaskDetails)
        .filter(TaskDetails.provenance_ref_id == open_task.id)
        .first()
    )
    assert td_open.current_state == "created"

    # 'in_progress' maps 1:1.
    ip_task = (
        db_session.query(Task)
        .filter(
            Task.company_id == ts_ctx["company_id"],
            Task.status == "in_progress",
        )
        .first()
    )
    td_ip = (
        db_session.query(TaskDetails)
        .filter(TaskDetails.provenance_ref_id == ip_task.id)
        .first()
    )
    assert td_ip.current_state == "in_progress"

    # 'done' preserves state + completed_at.
    done_task = (
        db_session.query(Task)
        .filter(
            Task.company_id == ts_ctx["company_id"], Task.status == "done"
        )
        .first()
    )
    td_done = (
        db_session.query(TaskDetails)
        .filter(TaskDetails.provenance_ref_id == done_task.id)
        .first()
    )
    assert td_done.current_state == "done"

    # 'cancelled' preserves state.
    cancelled_task = (
        db_session.query(Task)
        .filter(
            Task.company_id == ts_ctx["company_id"],
            Task.status == "cancelled",
        )
        .first()
    )
    td_cancelled = (
        db_session.query(TaskDetails)
        .filter(TaskDetails.provenance_ref_id == cancelled_task.id)
        .first()
    )
    assert td_cancelled.current_state == "cancelled"


def test_backfill_preserves_priority_and_due_date(db_session, ts_ctx):
    from app.models.task import Task
    from app.models.task_details import TaskDetails
    from scripts.seed_task_substrate_backfill import backfill_for_tenant

    target_date = date.today() + timedelta(days=10)
    t = Task(
        id=str(uuid.uuid4()),
        company_id=ts_ctx["company_id"],
        title="priority preservation",
        priority="high",
        status="open",
        due_date=target_date,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(t)
    db_session.commit()

    backfill_for_tenant(
        db_session, company_id=ts_ctx["company_id"], dry_run=False
    )

    td = (
        db_session.query(TaskDetails)
        .filter(TaskDetails.provenance_ref_id == t.id)
        .first()
    )
    assert td.priority == "high"
    assert td.due_date == target_date


def test_backfill_dry_run_no_writes(db_session, ts_ctx):
    from app.models.vault_item import VaultItem
    from scripts.seed_task_substrate_backfill import backfill_for_tenant

    _seed_legacy_tasks(db_session, ts_ctx["company_id"], ts_ctx["user_id"])

    counts = backfill_for_tenant(
        db_session, company_id=ts_ctx["company_id"], dry_run=True
    )
    # Counts reflect work performed but rolled back.
    assert counts["created"] == 5

    # After rollback, no VaultItem rows exist.
    vis = (
        db_session.query(VaultItem)
        .filter(
            VaultItem.company_id == ts_ctx["company_id"],
            VaultItem.item_type == "task",
        )
        .count()
    )
    assert vis == 0


def test_backfill_empty_tenant(db_session, ts_ctx):
    from scripts.seed_task_substrate_backfill import backfill_for_tenant
    counts = backfill_for_tenant(
        db_session, company_id=ts_ctx["company_id"], dry_run=False
    )
    assert counts == {"created": 0, "skipped": 0, "failed": 0}


def test_backfill_production_refusal_via_cli():
    """CLI refuses to run when ENVIRONMENT=production."""
    env = os.environ.copy()
    env["ENVIRONMENT"] = "production"
    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.seed_task_substrate_backfill", "--apply"],
        env=env,
        capture_output=True,
        text=True,
        cwd=project_root,
    )
    assert proc.returncode == 2
    assert "production" in (proc.stdout + proc.stderr).lower()


def test_backfill_preserves_metadata_legacy_task_id(db_session, ts_ctx):
    """VaultItem.metadata_json.legacy_task_id points back to original Task."""
    from app.models.task import Task
    from app.models.task_details import TaskDetails
    from app.models.vault_item import VaultItem
    from scripts.seed_task_substrate_backfill import backfill_for_tenant

    t = Task(
        id=str(uuid.uuid4()),
        company_id=ts_ctx["company_id"],
        title="meta-preservation",
        status="open",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(t)
    db_session.commit()
    backfill_for_tenant(
        db_session, company_id=ts_ctx["company_id"], dry_run=False
    )
    td = (
        db_session.query(TaskDetails)
        .filter(TaskDetails.provenance_ref_id == t.id)
        .first()
    )
    vi = (
        db_session.query(VaultItem)
        .filter(VaultItem.id == td.vault_item_id)
        .first()
    )
    assert vi.metadata_json.get("legacy_task_id") == t.id
    assert vi.source == "migrated"
    assert vi.source_entity_id == t.id
