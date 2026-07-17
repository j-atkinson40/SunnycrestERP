"""Reframe R-1 — the accounting job skeleton, seeded as PROPOSALS.

The six jobs from tasks_reframe_investigation.md §4's mapping table, refs
included — Statement Run carrying its TWO jobs (the many-to-many live on
day one). Framings are DERIVED-HONEST placeholders; the VOICE is the
operator's in R-3.

PRESERVE-AWARE (the sunnycrest-seed standard): a job that EXISTS is not
touched AT ALL — not its fields, not its refs. The operator's edits
(including deliberate ref removals) survive every boot. Only wholly-missing
jobs are created. Automation refs resolve at seed time by NAME → current
row id (boot seeds preserve ids; the mirrors-suite teardown re-attaches).
A ref whose automation/queue is absent on this DB is skipped with a log
line — never a dangling write (the write boundary holds in seeds too).

Idempotent; production-safe (platform pedagogy — the jobs ship everywhere
the manufacturing catalog does).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal  # noqa: E402
from app.models.moc_job import MoCJob  # noqa: E402
from app.models.moc_task_catalog import MoCTaskCatalog  # noqa: E402
from app.services.maps_of_content import jobs as jobs_svc  # noqa: E402

VERT = "manufacturing"

# (name, description, [(kind, key-or-automation-NAME, order)])
SKELETON = [
    (
        "Bank reconciliation",
        "Keep the bank and the books telling the same story — payments "
        "matched to invoices, and the ones that can't be matched reviewed "
        "by a person.",
        [
            ("automation", "Cash Receipts Matching", 0),
            ("triage_queue", "cash_receipts_matching_triage", 1),
        ],
    ),
    (
        "Month-end close",
        "Close the month with confidence — balances checked, accruals "
        "posted, statements verified, anomalies decided by you.",
        [
            ("automation", "Month-End Close", 0),
            ("automation", "Monthly Statement Run", 1),
            ("triage_queue", "month_end_close_triage", 2),
        ],
    ),
    (
        "Collections",
        "Overdue balances chased consistently — reminders drafted nightly, "
        "each one waiting for a person to send or skip.",
        [
            ("automation", "AR Collections", 0),
            ("triage_queue", "ar_collections_triage", 1),
        ],
    ),
    (
        "Customer billing & statements",
        "Funeral homes billed monthly on their charge accounts — invoices "
        "generated, consolidated statements sent.",
        [
            ("automation", "Monthly Statement Run", 0),
            ("automation", "Funeral Home Billing", 1),
            ("triage_queue", "month_end_close_triage", 2),
        ],
    ),
    (
        "Expense management",
        "Expenses categorized as they arrive — the uncertain ones queued "
        "for a quick confirm.",
        [
            ("automation", "Expense Categorization", 0),
            ("triage_queue", "expense_categorization_triage", 1),
        ],
    ),
    (
        "Compliance & records upkeep",
        "The steady upkeep — compliance data synced, documents reviewed on "
        "schedule, training currency watched.",
        [
            ("automation", "Compliance Sync", 0),
            ("automation", "Document Review Reminder", 1),
            ("automation", "Training Expiry Monitor", 2),
        ],
    ),
]


def main() -> int:
    db = SessionLocal()
    created = 0
    try:
        for order, (name, description, refs) in enumerate(SKELETON):
            existing = (
                db.query(MoCJob)
                .filter(
                    MoCJob.scope == "vertical_default",
                    MoCJob.vertical == VERT,
                    MoCJob.name == name,
                    MoCJob.is_active.is_(True),
                )
                .first()
            )
            if existing is not None:
                continue  # THE OPERATOR'S — untouched, refs included
            job = jobs_svc.create_job(
                db, name=name, scope="vertical_default", vertical=VERT,
                description=description, task_type="Accounting",
                display_order=order,
            )
            for kind, key, ref_order in refs:
                if kind == "automation":
                    row = (
                        db.query(MoCTaskCatalog)
                        .filter(
                            MoCTaskCatalog.vertical == VERT,
                            MoCTaskCatalog.name == key,
                            MoCTaskCatalog.is_active.is_(True),
                        )
                        .first()
                    )
                    if row is None:
                        print(f"[seed_accounting_jobs] skip ref: automation "
                              f"{key!r} absent on this DB")
                        continue
                    key = row.id
                try:
                    jobs_svc.add_ref(
                        db, job_id=job.id, ref_kind=kind, ref_key=key,
                        display_order=ref_order,
                    )
                except jobs_svc.JobValidationError as e:
                    print(f"[seed_accounting_jobs] skip ref ({name}): {e}")
            created += 1
        db.commit()
        print(f"[seed_accounting_jobs] ok — created {created} "
              f"(existing untouched, refs included)")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
