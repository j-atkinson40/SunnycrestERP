"""Reframe R-1 — the accounting job skeleton, seeded as PROPOSALS.

The six jobs from tasks_reframe_investigation.md §4's mapping table, refs
included — Statement Run carrying its TWO jobs (the many-to-many live on
day one). Framings are DERIVED-HONEST placeholders; the VOICE is the
operator's in R-3.

PRESERVE-AWARE (the sunnycrest-seed standard): an existing job's FIELDS are
never touched — the operator's words survive every boot. Only wholly-missing
jobs are created. Automation refs resolve at seed time by NAME → current
row id (boot seeds preserve ids; the mirrors-suite teardown re-attaches).
A ref whose automation/queue is absent on this DB is skipped with a log
line — never a dangling write (the write boundary holds in seeds too).

ONE OPENING, ADDED 2026-08-08: an existing job that carries NO REFS AT ALL
and whose entry here DECLARES refs gets them attached. `r157` §3 mints
`Cash receipts matching` and then skips the moves that would have populated
it (its source job does not exist on a fresh database), so the old
skip-if-exists left that card permanently empty on every new tenant. The
opening is deliberately "no refs at all" rather than "missing the ones we
declare": an operator who deletes ONE ref leaves a row that still has refs,
so it is skipped and their deletion survives. See the comment at the branch
for why that distinction is the entire guard.

Idempotent; production-safe (platform pedagogy — the jobs ship everywhere
the manufacturing catalog does).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal  # noqa: E402
from app.models.moc_job import MoCJob, MoCJobRef  # noqa: E402
from app.models.moc_task_catalog import MoCTaskCatalog  # noqa: E402
from app.services.maps_of_content import jobs as jobs_svc  # noqa: E402

VERT = "manufacturing"

# (name, description, [(kind, key-or-automation-NAME, order[, label])])
#
# ⚠️ THIS LIST AND `r157_map_accounting_content` ARE TWO PRODUCERS OF ONE
# STATE, and r157 shipped without this half. The migration corrects rows that
# ALREADY EXIST; this seed mints rows that do NOT. On a fresh database the
# migration runs first against zero jobs, correctly skips everything, and then
# this seed wrote the pre-r157 text — so every NEW tenant got exactly the
# content r157 exists to delete, permanently and silently.
#
# The migration keeps its own frozen copy (a migration is history and must not
# import live code that can change under it). What binds the two is
# `test_seed_matches_r157_content.py`, which loads r157 and asserts every
# corrected description here matches it. Edit one without the other and that
# test fails — which is the only mechanism, since the two files have no
# reason to be opened together.
SKELETON = [
    (
        "Bank reconciliation",
        # r157's corrected text. The old wording described the WHOLE statement
        # as a matching problem; the arc split matching onto its own job below.
        "Every line on the bank statement accounted for. A line the matcher "
        "recognises clears against what the books already recorded; a line you "
        "classify or code books its journal entry before it clears, so nothing "
        "leaves the statement unaccounted for. Whatever the matcher can't place "
        "waits in Books Review for a person.",
        [
            # The two matching refs MOVED to `Cash receipts matching` (r157 §4);
            # what stays is the review queue this job actually names.
            ("triage_queue", "reconciliation_review_triage", 0, "Books Review"),
        ],
    ),
    (
        # BORN AT r157 — the process was always distinct and had been borrowing
        # Bank reconciliation's name. Ordered second so it sits where the
        # migration puts it (Bank reconciliation's display_order + 1).
        "Cash receipts matching",
        "Payments matched to the invoices they settle — the confident ones "
        "applied, and the ones the matcher can't place with certainty queued "
        "for a person to confirm, override, or reject.",
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
        # r157's corrected text. "as they arrive" was the claim the platform
        # could not keep — event dispatch does not exist, so the workflow runs
        # on a 15-minute cron (Phase 8c's explicit workaround). The correction
        # states the sweep and keeps the phrase only as the thing it means.
        "Expenses categorized every fifteen minutes — until event dispatch "
        "exists, that sweep is what \"as they arrive\" means — with the "
        "uncertain ones queued for a quick confirm.",
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
    created = filled = 0
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
                # PRESERVE-AWARE, WITH ONE OPENING — and the opening is narrow
                # on purpose.
                #
                # `r157` §3 CREATES `Cash receipts matching` (it was born at the
                # migration) and then tries to MOVE its two refs off `Bank
                # reconciliation`. On a fresh database that source job does not
                # exist yet, so every move SKIPS — correctly, it has nothing to
                # move — and the migration leaves a job with ZERO refs. This
                # seed then saw it existed and skipped it entirely, so the refs
                # it declares were never attached and the card stayed
                # permanently empty on every new tenant. Two producers of one
                # state again, the same shape as the description drift the
                # r157/seed binding test exists to catch.
                #
                # THE RULE: attach only when this entry DECLARES refs and the
                # row has NONE AT ALL.
                #
                # "None at all" rather than "missing the ones we declare" is the
                # whole guard. An operator who deletes ONE of two refs leaves a
                # row that still has refs, so it is skipped and their deletion
                # survives — which is what `test_a_deleted_ref_is_not_
                # resurrected_on_the_destination` pins. Only a wholly ref-less
                # row can be filled, and a wholly ref-less row is the state no
                # operator produces by editing: they would have had to delete
                # every ref, and if they did, the four never-faces below show
                # that a job with no refs is a legitimate shape we never write
                # into anyway (entries declaring `[]` never reach this branch).
                if not refs:
                    continue  # never-face — nothing declared, nothing to attach
                has_any = (
                    db.query(MoCJobRef)
                    .filter(MoCJobRef.job_id == existing.id)
                    .first()
                    is not None
                )
                if has_any:
                    continue  # THE OPERATOR'S — untouched, deletions included
                job = existing  # declared refs, carries none → attach them
                filled += 1
                print(f"[seed_accounting_jobs] attaching refs to existing "
                      f"ref-less job {name!r} (r157-created)")
            else:
                job = jobs_svc.create_job(
                    db, name=name, scope="vertical_default", vertical=VERT,
                    description=description, task_type="Accounting",
                    display_order=order,
                )
                created += 1
            for ref in refs:
                # 3-tuple or 4-tuple: r157's Books Review ref carries a LABEL,
                # which the pre-r157 skeleton had no shape for. Tolerating both
                # keeps every untouched entry above unchanged.
                kind, key, ref_order = ref[0], ref[1], ref[2]
                label = ref[3] if len(ref) > 3 else None
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
                        label=label, display_order=ref_order,
                    )
                except jobs_svc.JobValidationError as e:
                    print(f"[seed_accounting_jobs] skip ref ({name}): {e}")
        db.commit()
        print(f"[seed_accounting_jobs] ok — created {created}, "
              f"filled {filled} ref-less (existing-with-refs untouched)")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
