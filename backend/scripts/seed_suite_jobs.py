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
        "When money needs a correction — voids, credit memos, the "
        "write-off verb, and the credit pocket's doors, every one "
        "carrying its reason.",
        [],
        [
            ("today-void", "TODAY — voiding works, honestly: void an "
             "invoice or a payment; a never-posted draft reverses "
             "nothing.", {"href": "/ar/invoices", "label": "Open Invoices"}),
            ("today-late-charges", "TODAY — late charges run under human "
             "eyes: finance charges calculate on demand, and every charge "
             "is reviewed — approved, or forgiven with a reason — before "
             "it posts. No clock fires this yet; the automation is "
             "queued.", {"href": "/financials/finance-charges",
                         "label": "Review late charges"}),
            ("coming-memos", "TODAY — credit memos: a first-class credit "
             "document with its required reason, posting as the negative "
             "through the one chokepoint; over-crediting refuses — the "
             "excess is the pocket's business.",
             {"href": "/ar/invoices", "label": "Open Invoices"}),
            ("coming-writeoff", "TODAY — the write-off verb: writes the "
             "remainder off AR deliberately, reason required; reinstating "
             "is its own verb with its own reason — no silent "
             "resurrection. (This is AR — distinct from inventory "
             "write-offs.)",
             {"href": "/ar/invoices", "label": "Open Invoices"}),
            ("coming-credit", "TODAY — the credit pocket has doors: apply "
             "held credit onto an open invoice, or record a disbursement "
             "(the money moves at the bank; Bridgeable records it) — "
             "every exit leaves a ledger row on the customer's record.",
             {"href": "/customers", "label": "Open Customers"}),
        ],
        {"coming": {"checker": "exceptions_arc"}},
    ),
    (
        "File sales tax",
        "The whole filing story — three-axis exemptions backed by "
        "certificates, periods accumulating by jurisdiction, and the "
        "return that tells you what to fix before filing.",
        [],
        [
            ("today-resolve", "TODAY — resolution is real, three axes "
             "deep: product taxability (nothing exempt without your "
             "mark), job and blanket certificates with dated validity, "
             "and the county engine — every answer carrying its "
             "specific reason. A flag without a certificate resolves "
             "TAXABLE with the gap listed.",
             {"href": "/settings/tax", "label": "Open Tax Settings"}),
            ("coming-accumulate", "TODAY — accumulation: invoice tax "
             "facts gather into periods by jurisdiction on the NY "
             "sales-tax calendar (Mar–May quarters, by invoice date), "
             "rebuilt idempotently every night.", None),
            ("coming-filing", "TODAY — the return: gross, exempt by "
             "reason class, taxable, and tax computed per jurisdiction "
             "— plus the gaps list (uncertified flags, unattached "
             "scans) so the fix happens before the filing.",
             {"href": "/reports", "label": "Open the return"}),
        ],
        {"coming": {"checker": "tax_filing_arc"}},
    ),
]


# Platform beats that join ALREADY-SEEDED jobs after their first ship.
# Append-only: a beat is inserted ONLY if its key is absent — existing
# beats (including operator-edited text) are never rewritten. Each entry:
# (job_name, beat_key, insert_after_key, beat_dict).
LATE_BEATS = [
    (
        "Handle the exceptions",
        "today-late-charges",
        "today-void",
        {
            "key": "today-late-charges",
            "text": "TODAY — late charges run under human eyes: finance "
                    "charges calculate on demand, and every charge is "
                    "reviewed — approved, or forgiven with a reason — "
                    "before it posts. No clock fires this yet; the "
                    "automation is queued.",
            "link": {"href": "/financials/finance-charges",
                     "label": "Review late charges"},
        },
    ),
]


# Platform-authored beat REWRITES for already-seeded jobs — the arc that
# makes a COMING beat real updates its words. Preserve-aware by exact
# old-text match: a beat is rewritten ONLY if its current text is
# byte-identical to the platform's own prior version — an operator-edited
# beat is never touched. Each entry: (job_name, beat_key, old_text_exact,
# new_beat_dict). The job description gets the same treatment via
# DESCRIPTION_REWRITES.
BEAT_REWRITES = [
    (
        "Handle the exceptions", "coming-memos",
        "COMING — credit memos: a first-class credit document instead of "
        "a hand edit.",
        {"key": "coming-memos",
         "text": "TODAY — credit memos: a first-class credit document "
                 "with its required reason, posting as the negative "
                 "through the one chokepoint; over-crediting refuses — "
                 "the excess is the pocket's business.",
         "link": {"href": "/ar/invoices", "label": "Open Invoices"}},
    ),
    (
        "Handle the exceptions", "coming-writeoff",
        "COMING — the write-off verb: the status exists today but nothing "
        "sets it; the arc adds the deliberate action with its guards.",
        {"key": "coming-writeoff",
         "text": "TODAY — the write-off verb: writes the remainder off AR "
                 "deliberately, reason required; reinstating is its own "
                 "verb with its own reason — no silent resurrection. "
                 "(This is AR — distinct from inventory write-offs.)",
         "link": {"href": "/ar/invoices", "label": "Open Invoices"}},
    ),
    (
        "Handle the exceptions", "coming-credit",
        "COMING — the credit pocket's door: overpayments already bank on "
        "the customer record; applying or refunding that credit is the "
        "missing verb.",
        {"key": "coming-credit",
         "text": "TODAY — the credit pocket has doors: apply held credit "
                 "onto an open invoice, or record a disbursement (the "
                 "money moves at the bank; Bridgeable records it) — every "
                 "exit leaves a ledger row on the customer's record.",
         "link": {"href": "/customers", "label": "Open Customers"}},
    ),
]

BEAT_REWRITES += [
    (
        "File sales tax", "today-resolve",
        "TODAY — resolution is real: county jurisdictions, exemptions, "
        "and every quote carrying its reason — resolved, exempt, or an "
        "explicit override.",
        {"key": "today-resolve",
         "text": "TODAY — resolution is real, three axes deep: product "
                 "taxability (nothing exempt without your mark), job and "
                 "blanket certificates with dated validity, and the "
                 "county engine — every answer carrying its specific "
                 "reason. A flag without a certificate resolves TAXABLE "
                 "with the gap listed.",
         "link": {"href": "/settings/tax", "label": "Open Tax Settings"}},
    ),
    (
        "File sales tax", "coming-accumulate",
        "COMING — accumulation: computed tax gathered into periods by "
        "jurisdiction, so a return can be produced instead of "
        "reconstructed.",
        {"key": "coming-accumulate",
         "text": "TODAY — accumulation: invoice tax facts gather into "
                 "periods by jurisdiction on the NY sales-tax calendar "
                 "(Mar–May quarters, by invoice date), rebuilt "
                 "idempotently every night."},
    ),
    (
        "File sales tax", "coming-filing",
        "COMING — filing prep with real dollars: today's reminder knows "
        "WHICH period is due but gathers nothing; the arc gives it the "
        "numbers. It opens with the operator's filing-practice words.",
        {"key": "coming-filing",
         "text": "TODAY — the return: gross, exempt by reason class, "
                 "taxable, and tax computed per jurisdiction — plus the "
                 "gaps list (uncertified flags, unattached scans) so the "
                 "fix happens before the filing.",
         "link": {"href": "/reports", "label": "Open the return"}},
    ),
]

DESCRIPTION_REWRITES = [
    (
        "File sales tax",
        "Resolution works beautifully today — every quote carries its tax "
        "why. Gathering it into filing periods is the arc this card is "
        "waiting for.",
        "The whole filing story — three-axis exemptions backed by "
        "certificates, periods accumulating by jurisdiction, and the "
        "return that tells you what to fix before filing.",
    ),
    (
        "Handle the exceptions",
        "When money needs a correction — voids work today; memos, "
        "write-offs, and the credit pocket's door are the arc this card "
        "is waiting for.",
        "When money needs a correction — voids, credit memos, the "
        "write-off verb, and the credit pocket's doors, every one "
        "carrying its reason.",
    ),
]


def _apply_rewrites(db) -> int:
    """Rewrite platform-authored beats/descriptions whose text is still
    the platform's own prior version (idempotent; operator edits win)."""
    changed = 0
    for job_name, beat_key, old_text, new_beat in BEAT_REWRITES:
        job = (
            db.query(MoCJob)
            .filter(MoCJob.scope == "vertical_default",
                    MoCJob.vertical == VERT,
                    MoCJob.name == job_name,
                    MoCJob.is_active.is_(True))
            .first()
        )
        if job is None:
            continue
        ponder = dict(job.ponder or {})
        story = list(ponder.get("story") or [])
        for i, b in enumerate(story):
            if b.get("key") == beat_key and b.get("text") == old_text:
                story[i] = new_beat
                ponder["story"] = story
                job.ponder = ponder
                changed += 1
                break
    for job_name, old_desc, new_desc in DESCRIPTION_REWRITES:
        job = (
            db.query(MoCJob)
            .filter(MoCJob.scope == "vertical_default",
                    MoCJob.vertical == VERT,
                    MoCJob.name == job_name,
                    MoCJob.is_active.is_(True))
            .first()
        )
        if job is not None and job.description == old_desc:
            job.description = new_desc
            changed += 1
    return changed


def _ensure_late_beats(db) -> int:
    """Append missing platform beats to existing suite jobs (idempotent)."""
    added = 0
    for job_name, beat_key, after_key, beat in LATE_BEATS:
        job = (
            db.query(MoCJob)
            .filter(MoCJob.scope == "vertical_default",
                    MoCJob.vertical == VERT,
                    MoCJob.name == job_name,
                    MoCJob.is_active.is_(True))
            .first()
        )
        if job is None:
            continue
        ponder = dict(job.ponder or {})
        story = list(ponder.get("story") or [])
        if any(b.get("key") == beat_key for b in story):
            continue
        idx = next((i for i, b in enumerate(story)
                    if b.get("key") == after_key), len(story) - 1)
        story.insert(idx + 1, beat)
        ponder["story"] = story
        job.ponder = ponder
        added += 1
    return added


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
        beats_added = _ensure_late_beats(db)
        rewritten = _apply_rewrites(db)
        db.commit()
        print(f"[seed_suite_jobs] ok — {created} created (existing untouched), "
              f"{beats_added} late beats appended, {rewritten} platform beats "
              f"rewritten (operator edits preserved)")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
