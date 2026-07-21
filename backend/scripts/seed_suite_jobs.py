"""SUITE MAP EXPRESSION (2026-07-20) — the accounting area grows to eleven.

Three REAL jobs (Pay the bills · Watch the cash · Understand the numbers)
carded whole with census-backed story beats + deep links; two NEVER-FACES
(Handle the exceptions · File sales tax) in the minted coming grammar —
each teaches the job today, states what its arc brings, and COMPLETES BY
REALITY (jobs.COMING_CHECKERS reads code capability, never a flag).

Every ponder claim traces to accounting_suite_census.md — the census IS
the evidence; no beat says what the record can't support.

PRESERVE-AWARE (the accounting/S&O seed standard): existing jobs are
untouched entirely. Idempotent; production-safe (platform pedagogy).
Usage:  cd backend && python -m scripts.seed_suite_jobs
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
AREA = "Accounting"

# (name, description, refs[(kind, name, order)], story[(key, text, link|None)],
#  ponder_extra)
JOBS = [
    (
        "Pay the bills",
        "The whole AP path, working today — bills entered, approved, paid, "
        "and aged, with the batch run and true matching queued.",
        [],
        [
            ("bill-entry", "Enter a bill: vendor bills with auto-numbering, "
             "PO line pre-fill, and status discipline — draft, pending, "
             "approved, paid.", {"href": "/ap/bills", "label": "Open Vendors & Bills"}),
            ("approval", "Approve it: a deliberate gate — only pending or "
             "draft bills approve, with the approver and moment recorded.",
             None),
            ("pay", "Record the payment: applications per bill, sums checked "
             "against balances, statuses rolling to partial or paid.",
             {"href": "/ap/payments", "label": "Open AP Payments"}),
            ("aging", "Watch the age: AP aging buckets with CSV export.",
             {"href": "/ap/aging", "label": "Open AP Aging"}),
            ("coming-batch", "COMING — the batch payment run: today the "
             "suggested run is a view (bills due in 10 days); executing it "
             "as one batch is queued.", None),
            ("coming-match", "COMING — true 3-way matching: today the PO "
             "links receipts and pre-fills bills; variance checks that hold "
             "a mismatched bill are queued.", None),
        ],
        {},
    ),
    (
        "Watch the cash",
        "Real money, really watched — the bank feed pulls, the position "
        "shows, the forecast opens from actual cash.",
        [("automation", "Pull Bank Transactions", 0)],
        [
            ("feed", "The feed: transactions pull in on the nightly and "
             "morning clocks and land categorized against your map.",
             {"href": "/financials/bank-activity", "label": "Open Bank Activity"}),
            ("position", "The position: cash on hand from depository "
             "balances — credit and loans shown as owed, never as cash — "
             "with the moment the numbers were true stated on the card.",
             {"href": "/financials/board", "label": "Open the Financials Board"}),
            ("forecast", "The forecast: five weeks of AR-expected minus "
             "AP-committed, opening from your real balance — a gap means "
             "real cash below zero, not a guess.", None),
            ("health", "The pulse: the daily health score's cash component "
             "reads this same position against the next 30 days of AP.",
             None),
        ],
        {"glance_source": "cash_position"},
    ),
    (
        "Understand the numbers",
        "What the books can tell you today — and, stated plainly, what "
        "they can't yet.",
        [],
        [
            ("pnl", "The P&L: a live income statement computed from "
             "invoices and expenses by account type.",
             {"href": "/reports", "label": "Open Reports"}),
            ("statements", "Statements: monthly customer statements "
             "generated, reviewed, and delivered — with a safety refusal "
             "when a number can't be stood behind.",
             {"href": "/ar/statements", "label": "Open Statements"}),
            ("journal", "Journal entries: manual entries posted, reversed, "
             "even AI-parsed from a sentence.",
             {"href": "/journal-entries", "label": "Open Journal Entries"}),
            ("recon", "Reconciliation: the bank feed or a CSV against the "
             "books, matched and confirmed on the board.",
             {"href": "/financials/board", "label": "Open the Financials Board"}),
            ("gap-ledger", "STATED PLAINLY — today's books are subledgers "
             "and journals, not a double-entry ledger: there is no balance "
             "sheet, trial balance, or GL view yet. The ledger arc is "
             "queued.", None),
            ("gap-margin", "STATED PLAINLY — the P&L's gross margin reads "
             "~100% because no cost dimension exists yet; read revenue and "
             "expenses with confidence, margin with none. The same ledger "
             "arc fixes it.", None),
        ],
        {},
    ),
    (
        "Handle the exceptions",
        "When money needs a correction — voids work today; memos, "
        "write-offs, and the credit pocket's door are the arc this card "
        "is waiting for.",
        [],
        [
            ("today-void", "TODAY — voiding works, honestly: void an "
             "invoice or a payment; a never-posted draft reverses "
             "nothing.", {"href": "/ar/invoices", "label": "Open Invoices"}),
            ("coming-memos", "COMING — credit memos: a first-class credit "
             "document instead of a hand edit.", None),
            ("coming-writeoff", "COMING — the write-off verb: the status "
             "exists today but nothing sets it; the arc adds the deliberate "
             "action with its guards.", None),
            ("coming-credit", "COMING — the credit pocket's door: "
             "overpayments already bank on the customer record; applying "
             "or refunding that credit is the missing verb.", None),
        ],
        {"coming": {"checker": "exceptions_arc"}},
    ),
    (
        "File sales tax",
        "Resolution works beautifully today — every quote carries its tax "
        "why. Gathering it into filing periods is the arc this card is "
        "waiting for.",
        [],
        [
            ("today-resolve", "TODAY — resolution is real: county "
             "jurisdictions, exemptions, and every quote carrying its "
             "reason — resolved, exempt, or an explicit override.",
             {"href": "/settings/tax", "label": "Open Tax Settings"}),
            ("coming-accumulate", "COMING — accumulation: computed tax "
             "gathered into periods by jurisdiction, so a return can be "
             "produced instead of reconstructed.", None),
            ("coming-filing", "COMING — filing prep with real dollars: "
             "today's reminder knows WHICH period is due but gathers "
             "nothing; the arc gives it the numbers. It opens with the "
             "operator's filing-practice words.", None),
        ],
        {"coming": {"checker": "tax_filing_arc"}},
    ),
]


def main() -> int:
    db = SessionLocal()
    created = 0
    try:
        base_order = (
            db.query(MoCJob)
            .filter(MoCJob.scope == "vertical_default",
                    MoCJob.vertical == VERT,
                    MoCJob.task_type == AREA,
                    MoCJob.is_active.is_(True))
            .count()
        )
        for i, (name, description, refs, story, extra) in enumerate(JOBS):
            existing = (
                db.query(MoCJob)
                .filter(MoCJob.scope == "vertical_default",
                        MoCJob.vertical == VERT,
                        MoCJob.name == name,
                        MoCJob.is_active.is_(True))
                .first()
            )
            if existing is not None:
                continue  # THE OPERATOR'S — untouched
            job = jobs_svc.create_job(
                db, name=name, scope="vertical_default", vertical=VERT,
                description=description, task_type=AREA,
                display_order=base_order + i,
            )
            ponder: dict = {**extra}
            if story:
                ponder["story"] = [
                    {"key": k, "text": t, **({"link": link} if link else {})}
                    for (k, t, link) in story
                ]
            job.ponder = ponder
            for kind, key, ref_order in refs:
                if kind == "automation":
                    row = (
                        db.query(MoCTaskCatalog)
                        .filter(MoCTaskCatalog.name == key,
                                MoCTaskCatalog.is_active.is_(True))
                        .first()
                    )
                    if row is None:
                        print(f"[seed_suite_jobs] skip ref: automation "
                              f"{key!r} absent on this DB")
                        continue
                    key = row.id
                try:
                    jobs_svc.add_ref(db, job_id=job.id, ref_kind=kind,
                                     ref_key=key, display_order=ref_order)
                except jobs_svc.JobValidationError as e:
                    print(f"[seed_suite_jobs] skip ref ({name}): {e}")
            created += 1
        db.commit()
        print(f"[seed_suite_jobs] ok — {created} created (existing untouched)")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
