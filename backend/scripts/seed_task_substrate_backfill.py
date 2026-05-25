"""Task substrate v1.0 — backfill legacy Task rows → VaultItem + task_details.

Per build prompt §5.1 + (c) backfill canon precedent at
seed_pending_attention_backfill.py.

For each existing row in the legacy `tasks` table:
- Check idempotency: skip if a task_details row with provenance_kind=
  'manual_creation', provenance_ref_type='legacy_task', provenance_ref_id=
  task.id, event_kind='legacy_backfill' already exists.
- Create VaultItem (item_type='task'); record task.id as
  source_entity_id + metadata_json.legacy_task_id for traceability.
- Create task_details with lifecycle_shape='action'. Map task.status →
  action-shape state via lifecycle.legacy_status_to_action_state
  (open with assignee → assigned; open with no assignee → created;
  others 1:1).
- Preserve task.priority, task.due_date, task.due_datetime, task.completed_at,
  task.created_at, task.updated_at.

Idempotent: re-running the backfill on already-backfilled rows is a no-op
because the partial-unique idempotency index rejects duplicates +
this script's pre-check matches the same composite key.

CLI:
    python -m scripts.seed_task_substrate_backfill            # dry-run
    python -m scripts.seed_task_substrate_backfill --apply
    python -m scripts.seed_task_substrate_backfill --apply --tenant-slug testco

Safety: refuses to run if ENVIRONMENT=production per the broader
seed-script convention (Lock 1 + (c) precedent).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import uuid
from datetime import datetime, timezone

# Allow `python -m scripts.seed_task_substrate_backfill` from backend/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.company import Company  # noqa: E402
from app.models.task import Task  # noqa: E402
from app.models.task_details import TaskDetails  # noqa: E402
from app.models.vault_item import VaultItem  # noqa: E402
from app.services.tasks.lifecycle import (  # noqa: E402
    legacy_status_to_action_state,
)
from app.services.vault_service import get_or_create_company_vault  # noqa: E402


logger = logging.getLogger("seed_task_substrate_backfill")
logging.basicConfig(level=logging.INFO, format="%(message)s")


# ── Idempotency check ────────────────────────────────────────────────


def _already_backfilled(db: Session, *, task_id: str) -> bool:
    """Returns True if a task_details row already exists for this legacy task."""
    existing = (
        db.query(TaskDetails)
        .filter(
            TaskDetails.provenance_kind == "manual_creation",
            TaskDetails.provenance_ref_type == "legacy_task",
            TaskDetails.provenance_ref_id == task_id,
            TaskDetails.event_kind == "legacy_backfill",
        )
        .first()
    )
    return existing is not None


# ── Per-tenant backfill ──────────────────────────────────────────────


def backfill_for_tenant(
    db: Session, *, company_id: str, dry_run: bool = False
) -> dict[str, int]:
    """Walk all Task rows for tenant; create VaultItem + task_details pairs.

    Returns counts: created / skipped / failed.
    """
    rows = (
        db.query(Task)
        .filter(Task.company_id == company_id)
        .order_by(Task.created_at.asc())
        .all()
    )

    created = 0
    skipped = 0
    failed = 0

    if not rows:
        logger.info("  (no Task rows for company %s)", company_id)
        if dry_run:
            db.rollback()
        else:
            db.commit()
        return {"created": 0, "skipped": 0, "failed": 0}

    # Resolve vault once per tenant.
    vault = get_or_create_company_vault(db, company_id)
    vault_id = vault.id

    for idx, t in enumerate(rows, start=1):
        try:
            if _already_backfilled(db, task_id=t.id):
                skipped += 1
                continue

            action_state = legacy_status_to_action_state(
                t.status,
                has_assignee=bool(t.assignee_user_id),
            )

            metadata: dict = dict(t.metadata_json or {})
            metadata["legacy_task_id"] = t.id

            vi = VaultItem(
                id=str(uuid.uuid4()),
                vault_id=vault_id,
                company_id=company_id,
                item_type="task",
                title=t.title,
                description=t.description,
                visibility="internal",
                status="active" if t.is_active else "cancelled",
                source="migrated",
                source_entity_id=t.id,
                created_by=t.created_by_user_id,
                created_at=t.created_at or datetime.now(timezone.utc),
                updated_at=t.updated_at or datetime.now(timezone.utc),
                is_active=bool(t.is_active),
                metadata_json=metadata,
            )
            td = TaskDetails(
                id=str(uuid.uuid4()),
                vault_item_id=vi.id,
                assignee_realm="user",
                assignee_user_id=t.assignee_user_id,
                lifecycle_shape="action",
                current_state=action_state,
                provenance_kind="manual_creation",
                provenance_ref_type="legacy_task",
                provenance_ref_id=t.id,
                event_kind="legacy_backfill",
                visibility="operator_internal",
                priority=t.priority or "normal",
                due_date=t.due_date,
                due_datetime=t.due_datetime,
                assigned_at=t.created_at if t.assignee_user_id else None,
                completed_at=t.completed_at,
                created_at=t.created_at or datetime.now(timezone.utc),
                updated_at=t.updated_at or datetime.now(timezone.utc),
            )
            db.add(vi)
            db.add(td)
            db.flush()
            created += 1

            if idx % 100 == 0:
                logger.info("  ... backfilled %d rows so far", idx)
        except Exception:
            logger.exception(
                "backfill failed for task_id=%s — continuing", t.id
            )
            failed += 1

    if dry_run:
        db.rollback()
    else:
        db.commit()

    logger.info(
        "  company_id=%s  created=%d  skipped=%d  failed=%d",
        company_id, created, skipped, failed,
    )
    return {"created": created, "skipped": skipped, "failed": failed}


# ── Driver ───────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill legacy Task rows into VaultItem + "
        "task_details (task substrate v1.0)."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit changes. Without --apply, rolls back at end (dry-run).",
    )
    parser.add_argument(
        "--tenant-slug",
        default=None,
        help="Optionally scope to a single tenant by slug.",
    )
    args = parser.parse_args()

    if os.getenv("ENVIRONMENT", "").lower() == "production":
        print("SAFETY: Refusing to run in production.")
        return 2

    dry_run = not args.apply
    if dry_run:
        print("DRY-RUN — pass --apply to commit task_details rows.")

    db: Session = SessionLocal()
    try:
        tenants_q = db.query(Company).filter(Company.is_active.is_(True))
        if args.tenant_slug:
            tenants_q = tenants_q.filter(Company.slug == args.tenant_slug)
        tenants = tenants_q.all()

        if not tenants:
            print(
                f"No active tenants matched "
                f"(slug={args.tenant_slug!r} if scoped)."
            )
            return 0

        grand_created = 0
        grand_skipped = 0
        grand_failed = 0
        for co in tenants:
            print(f"\nTenant {co.slug} ({co.id}):")
            counts = backfill_for_tenant(
                db, company_id=co.id, dry_run=dry_run
            )
            grand_created += counts["created"]
            grand_skipped += counts["skipped"]
            grand_failed += counts["failed"]

        verb = "would backfill" if dry_run else "backfilled"
        print(
            f"\n{verb}: created={grand_created} skipped={grand_skipped} "
            f"failed={grand_failed} across {len(tenants)} tenant(s)."
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
