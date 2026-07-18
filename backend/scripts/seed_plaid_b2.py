"""Plaid B-2 canonical seed — the category map + "Pull Bank Transactions"
born native (compiled workflow + catalog row + dry triggers + the job ref).

PRESERVE-AWARE (the Sunnycrest standard): every existing row is wholly
untouched — the seed creates only what is absent. Idempotent; runs via
run_canonical_seeds.sh on every deploy, production included (this is
canonical vertical content, not demo data).

BORN NATIVE per the FH Billing precedent: the workflow is compiled
(mirrored_from_workflow_id NULL) so schedule authority is `moc` from
birth; the two tenant-local triggers (22:30 + 06:30) ship is_live=False —
DRY-RUN. Promotion is the operator's, at his review, never the seed's.
"""
from __future__ import annotations

import json
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text as sql_text  # noqa: E402

from app.database import SessionLocal  # noqa: E402

VERTICAL = "manufacturing"
WORKFLOW_TYPE = "pull_bank_transactions"
DISPLAY_NAME = "Pull Bank Transactions"
AUTOMATION_NAME = "Pull Bank Transactions"
JOB_NAME = "Bank reconciliation"

# The reframe's sentence, literally.
DESCRIPTION = (
    "Pulls the bank statement in and categorizes it — every transaction "
    "lands ready to reconcile."
)

CANVAS = {
    "version": 1,
    "trigger": {"type": "manual"},
    "nodes": [
        {"id": "n_start", "type": "start", "label": "Start", "config": {},
         "position": {"x": 0, "y": 0}},
        {"id": "n_sync", "type": "action",
         "label": "Sync bank transactions (Plaid)",
         "config": {
             "action_type": "call_service_method",
             "method_name": "plaid_sync.run_sync_pipeline",
             "kwargs": {"trigger_source": "moc_task_schedule"},
         },
         "position": {"x": 0, "y": 120}},
        {"id": "n_end", "type": "end", "label": "End", "config": {},
         "position": {"x": 0, "y": 240}},
    ],
    "edges": [
        {"id": "e1", "source": "n_start", "target": "n_sync", "label": ""},
        {"id": "e2", "source": "n_sync", "target": "n_end", "label": ""},
    ],
}

# The two tenant-local clocks (the investigation's cadence call): 22:30
# feeds the 23:00–23:40 nightly block; 06:30 catches overnight postings.
TRIGGER_CRONS = ("30 22 * * *", "30 6 * * *")

# ── The platform category map (~30 rows; detailed wins over primary at
#    resolve time; INCOME/TRANSFER deliberately unmapped — deposits are
#    not expenses; honest NULL) ──────────────────────────────────────────
PLATFORM_CATEGORY_MAP = {
    # Detailed keys
    "RENT_AND_UTILITIES.RENT": "rent",
    "RENT_AND_UTILITIES.GAS_AND_ELECTRICITY": "utilities",
    "RENT_AND_UTILITIES.WATER": "utilities",
    "RENT_AND_UTILITIES.SEWAGE_AND_WASTE_MANAGEMENT": "utilities",
    "RENT_AND_UTILITIES.INTERNET_AND_CABLE": "utilities",
    "RENT_AND_UTILITIES.TELEPHONE": "utilities",
    "GENERAL_SERVICES.INSURANCE": "insurance",
    "GENERAL_SERVICES.ACCOUNTING_AND_FINANCIAL_PLANNING": "professional_fees",
    "GENERAL_SERVICES.CONSULTING_AND_LEGAL": "professional_fees",
    "GENERAL_SERVICES.POSTAGE_AND_SHIPPING": "delivery_costs",
    "GENERAL_SERVICES.STORAGE": "other_expense",
    "GENERAL_SERVICES.ADVERTISING": "advertising",
    "TRANSPORTATION.GAS": "vehicle_expense",
    "TRANSPORTATION.PARKING": "vehicle_expense",
    "TRANSPORTATION.TOLLS": "vehicle_expense",
    "TRANSPORTATION.TAXIS_AND_RIDE_SHARES": "vehicle_expense",
    "GENERAL_MERCHANDISE.OFFICE_SUPPLIES": "office_supplies",
    "HOME_IMPROVEMENT.REPAIR_AND_MAINTENANCE": "repairs_maintenance",
    "HOME_IMPROVEMENT.HARDWARE": "repairs_maintenance",
    # Primary fallbacks
    "BANK_FEES": "other_expense",
    "GENERAL_SERVICES": "professional_fees",
    "TRANSPORTATION": "vehicle_expense",
    "RENT_AND_UTILITIES": "utilities",
    "GENERAL_MERCHANDISE": "office_supplies",
    "HOME_IMPROVEMENT": "repairs_maintenance",
    "FOOD_AND_DRINK": "other_expense",
    "ENTERTAINMENT": "other_expense",
    "TRAVEL": "other_expense",
    "MEDICAL": "other_expense",
    "LOAN_PAYMENTS": "other_expense",
    "GOVERNMENT_AND_NON_PROFIT": "other_expense",
    "PERSONAL_CARE": "other_expense",
}


def _seed_categories(db) -> int:
    created = 0
    for plaid_cat, expense_cat in PLATFORM_CATEGORY_MAP.items():
        exists = db.execute(sql_text(
            "SELECT 1 FROM plaid_category_mappings "
            "WHERE tenant_id IS NULL AND plaid_category = :pc"
        ), {"pc": plaid_cat}).first()
        if exists:
            continue  # preserve-aware: existing rows wholly untouched
        db.execute(sql_text(
            "INSERT INTO plaid_category_mappings "
            "(id, tenant_id, plaid_category, expense_category, is_active, "
            " created_at, updated_at) "
            "VALUES (:id, NULL, :pc, :ec, true, now(), now())"
        ), {"id": str(uuid.uuid4()), "pc": plaid_cat, "ec": expense_cat})
        created += 1
    return created


def _seed_workflow(db) -> str:
    from app.services.workflow_templates.canvas_validator import validate_canvas_state

    row = db.execute(sql_text(
        "SELECT id FROM workflow_templates WHERE scope = 'vertical_default' "
        "AND vertical = :v AND workflow_type = :wt"
    ), {"v": VERTICAL, "wt": WORKFLOW_TYPE}).first()
    if row:
        return row.id  # preserve-aware
    validate_canvas_state(CANVAS)
    wf_id = str(uuid.uuid4())
    db.execute(sql_text(
        "INSERT INTO workflow_templates (id, scope, vertical, workflow_type, "
        "display_name, canvas_state, version, is_active, created_at, updated_at) "
        "VALUES (:id, 'vertical_default', :v, :wt, :dn, CAST(:cs AS jsonb), 1, "
        "true, now(), now())"
    ), {"id": wf_id, "v": VERTICAL, "wt": WORKFLOW_TYPE, "dn": DISPLAY_NAME,
        "cs": json.dumps(CANVAS)})
    return wf_id


def _seed_catalog_row(db, workflow_template_id: str) -> tuple[str, bool]:
    from app.models.moc_task_catalog import MoCTaskCatalog

    existing = (
        db.query(MoCTaskCatalog)
        .filter(
            MoCTaskCatalog.scope == "vertical_default",
            MoCTaskCatalog.vertical == VERTICAL,
            MoCTaskCatalog.name == AUTOMATION_NAME,
            MoCTaskCatalog.is_active.is_(True),
        )
        .first()
    )
    if existing:
        return existing.id, False  # preserve-aware
    from app.services.maps_of_content.task_catalog import upsert_task
    task = upsert_task(
        db, vertical=VERTICAL, name=AUTOMATION_NAME,
        scope="vertical_default", icon="landmark",
        task_type="Accounting", description=DESCRIPTION,
        workflow_template_id=workflow_template_id,
    )
    return task.id, True


def _seed_triggers(db, task_id: str) -> int:
    from app.models.moc_task_trigger import MoCTaskTrigger
    from app.services.maps_of_content.triggers import add_trigger

    existing = (
        db.query(MoCTaskTrigger)
        .filter(MoCTaskTrigger.task_catalog_id == task_id,
                MoCTaskTrigger.kind == "schedule")
        .count()
    )
    if existing:
        return 0  # preserve-aware: never touch authored triggers
    for i, cron in enumerate(TRIGGER_CRONS):
        add_trigger(
            db, task_catalog_id=task_id, kind="schedule",
            config={"spec_kind": "cron", "cron": cron},
            display_order=i,
        )
        # BORN DRY: add_trigger defaults is_live=False — promotion is the
        # operator's hand, never the seed's. Asserted:
    rows = (
        db.query(MoCTaskTrigger)
        .filter(MoCTaskTrigger.task_catalog_id == task_id).all()
    )
    assert all(not t.is_live for t in rows), "seed must never promote"
    return len(TRIGGER_CRONS)


def _seed_job_ref(db, task_id: str) -> bool:
    from app.models.moc_job import MoCJob, MoCJobRef
    from app.services.maps_of_content import jobs as jobs_svc

    job = (
        db.query(MoCJob)
        .filter(MoCJob.vertical == VERTICAL, MoCJob.name == JOB_NAME,
                MoCJob.is_active.is_(True))
        .first()
    )
    if job is None:
        print(f"  [plaid-b2] job {JOB_NAME!r} absent — ref skipped (seed_accounting_jobs first)")
        return False
    exists = (
        db.query(MoCJobRef)
        .filter(MoCJobRef.job_id == job.id, MoCJobRef.ref_kind == "automation",
                MoCJobRef.ref_key == task_id)
        .first()
    )
    if exists:
        return False
    jobs_svc.add_ref(db, job_id=job.id, ref_kind="automation", ref_key=task_id,
                     display_order=2)
    return True


def main() -> None:
    db = SessionLocal()
    try:
        cats = _seed_categories(db)
        wf_id = _seed_workflow(db)
        task_id, task_created = _seed_catalog_row(db, wf_id)
        trigs = _seed_triggers(db, task_id)
        ref = _seed_job_ref(db, task_id)
        db.commit()
        print(
            f"[plaid-b2] categories +{cats} · workflow {wf_id[:8]} · "
            f"automation {'created' if task_created else 'present'} · "
            f"triggers +{trigs} (all DRY) · job-ref {'added' if ref else 'present/skipped'}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
