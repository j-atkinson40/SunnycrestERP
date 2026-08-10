"""WE-1 A-3 — clear the workflow runs parked on an empty question.

DRY-RUN BY DEFAULT. `--execute` requires a typed confirmation.

WHAT THIS IS, AND WHAT IT IS NOT
--------------------------------
A-1 made the engine report failure; A-2 stopped gates asking empty questions.
Both stop the BLEED. This clears what already accumulated — 96.6% of every
workflow run on production sat in `awaiting_input`, and almost all of it was a
workflow asking about nothing.

⚠️ THIS IS HOUSEKEEPING IN FRONT OF THE IMPLEMENT-OR-DELETE PASS, NOT A
SUBSTITUTE FOR IT. After A-1, the workflows whose steps carry an unrecognised
`action_type` FAIL instead of parking — so clearing `awaiting_input` empties one
column and the next accumulation starts in `failed`. 47 broken steps across 18
workflows are still the underlying cause. A clean parked-run count six weeks from
now would otherwise read as "the problem was solved", and it will not have been.

⚠️ THE DISPOSITION IS PER-GROUP, NOT ONE RULE. Every exclusion below has its own
reason. A uniform sweep would be wrong in four different ways at once.

  CLEAR   Expense Categorization, pre-2026-08-10 (12,300)
          Sampled, not assumed: uncategorized_found / needs_review /
          anomaly_count are ALL ZERO on every one. The workflow fired every 15
          minutes from 2026-05-06 and found nothing every time, because the
          tenant had no vendor bills at all. Parked on nothing.

  CLEAR   AR Collections (127)
          `drafts_generated: 0` on EVERY run across three months. The gate's
          prompt asks the operator to "review drafts and dispatch one customer's
          email at a time" — there has never been a draft to review.

          ⚠️ THE 53 REAL FINDINGS ARE NOT IN THESE ROWS AND ARE NOT DELETED.
          53 of the 127 runs recorded `anomaly_count > 0` — genuine overdue-AR
          findings on live customers. Those anomalies live in `agent_anomalies`
          and surface in the `ar_collections_triage` queue. This script does not
          touch that table, and the queue reads the same after it runs as
          before. Verified by the pre/post counts this script prints, not
          asserted — see `--execute`'s output.

  LEAVE   Expense Categorization, 2026-08-10 (69)
          DEMO-2 seed artifacts. `clear_agent_backlog.py` owns the seed's rows;
          two scripts deleting the same data is how a count stops being
          attributable.

  LEAVE   Monthly Statement Run (4)
          A-1 fails these at step 1 on their next run. No manual action needed,
          and deleting them now would hide the transition from parked to failed
          that is the evidence A-1 works.

  LEAVE   First Call Intake (2)
          A PERSON started an intake and stopped. These are the only rows where
          "parked" means what the word implies — its input steps are steps 1 and
          2, before any producer, so the gate IS the workflow's input mechanism
          rather than a review gate. Clearing someone's half-finished work is a
          different act from clearing a machine's empty question, and two rows
          is not a reason to conflate them.

CASCADE, DERIVED FROM `pg_constraint` RATHER THAN REASONED ABOUT
---------------------------------------------------------------
Nine FKs reference `workflow_runs`; NONE is NO ACTION, so nothing blocks the
delete. Two are worth naming because they are silent:

  workflow_review_items.run_id      ON DELETE CASCADE   — Decision Triage items
  documents.caller_workflow_run_id  ON DELETE SET NULL  — loses provenance

Measured on the target set: **0 review items, 0 documents**. So neither fires
here. The check runs anyway at execute time — a count taken today is not a
guarantee about the database this runs against.

`workflow_run_steps.run_id` cascades: ~37,635 rows go with the runs. That is the
per-step execution history of runs that did nothing, and it is the bulk of what
is deleted by row count.

Usage::

    python -m scripts.clear_parked_workflow_runs --tenant-slug sunnycrest
    python -m scripts.clear_parked_workflow_runs --tenant-slug sunnycrest --execute
"""
from __future__ import annotations

import argparse
import sys
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.company import Company

#: The seed ran on this date; Expense Categorization runs from it are DEMO-2
#: artifacts owned by `clear_agent_backlog.py`, not by this script.
_SEED_DATE = date(2026, 8, 10)

#: (workflow name, extra SQL predicate, why it clears)
_CLEAR = [
    (
        "Expense Categorization",
        f"AND r.started_at::date < DATE '{_SEED_DATE.isoformat()}'",
        "zeros throughout — parked on nothing since 2026-05-06",
    ),
    (
        "AR Collections",
        "",
        "drafts_generated: 0 on every run — the gate reviewed a queue that was "
        "never populated. The 53 real findings live in agent_anomalies and are "
        "NOT touched.",
    ),
]

_LEAVE = [
    ("Expense Categorization (2026-08-10)", "DEMO-2 seed artifacts — clear_agent_backlog owns them"),
    ("Monthly Statement Run", "A-1 fails these at step 1 on next run; the transition is the evidence"),
    ("First Call Intake", "a person started an intake and stopped — real unfinished work"),
]


def say(msg: str) -> None:
    print(f">>> {msg}")


def die(msg: str) -> None:
    print(f"\n❌ {msg}", file=sys.stderr)
    sys.exit(1)


def _target_ids(db: Session, company_id: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for name, extra, _why in _CLEAR:
        rows = db.execute(
            text(
                "SELECT r.id FROM workflow_runs r JOIN workflows w ON w.id = r.workflow_id "
                "WHERE r.company_id = :c AND w.name = :n "
                "  AND r.status = 'awaiting_input' " + extra
            ),
            {"c": company_id, "n": name},
        )
        out[name] = [x[0] for x in rows]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Clear workflow runs parked on an empty question (dry-run by default)."
    )
    ap.add_argument("--tenant-slug", required=True)
    ap.add_argument("--execute", action="store_true", help="Actually delete.")
    args = ap.parse_args()

    db: Session = SessionLocal()
    try:
        company = db.query(Company).filter(Company.slug == args.tenant_slug).one_or_none()
        if company is None:
            die(f"no tenant with slug {args.tenant_slug!r}")

        targets = _target_ids(db, company.id)
        all_ids = [i for ids in targets.values() for i in ids]

        # THE ANOMALY COUNT IS THE CLAIM THIS SCRIPT MAKES ABOUT SAFETY, so it is
        # measured before and after rather than stated in a comment.
        anomalies_before = db.execute(text(
            "SELECT count(*) FROM agent_anomalies a JOIN agent_jobs j ON j.id = a.agent_job_id "
            "WHERE j.tenant_id = :c AND j.job_type = 'ar_collections'"
        ), {"c": company.id}).scalar()

        steps = db.execute(text(
            "SELECT count(*) FROM workflow_run_steps WHERE run_id = ANY(:i)"
        ), {"i": all_ids}).scalar() if all_ids else 0
        review_items = db.execute(text(
            "SELECT count(*) FROM workflow_review_items WHERE run_id = ANY(:i)"
        ), {"i": all_ids}).scalar() if all_ids else 0
        docs = db.execute(text(
            "SELECT count(*) FROM documents WHERE caller_workflow_run_id = ANY(:i)"
        ), {"i": all_ids}).scalar() if all_ids else 0

        print("\n" + "=" * 70)
        print(f"PARKED WORKFLOW RUN CLEANUP — {company.name} ({company.slug})")
        print(f"mode: {'EXECUTE' if args.execute else 'DRY-RUN (default)'}")
        print("=" * 70)
        print("\nCLEAR:")
        for name, _extra, why in _CLEAR:
            print(f"    {name:<34}{len(targets[name]):>7}   {why}")
        print(f"\n    {'workflow_run_steps (cascade)':<34}{steps:>7}")
        print(f"    {'TOTAL runs':<34}{len(all_ids):>7}")

        print("\nLEAVE, each for its own reason:")
        for name, why in _LEAVE:
            print(f"    {name:<38}{why}")

        print("\nCASCADE CHECK (derived from pg_constraint, measured now):")
        print(f"    workflow_review_items (CASCADE — Decision Triage)  {review_items}")
        print(f"    documents (SET NULL — loses provenance)            {docs}")
        if review_items or docs:
            print("    ⚠️  NON-ZERO — these would be deleted / unlinked. Review before --execute.")

        print(f"\nAR collections anomalies BEFORE: {anomalies_before}")
        print("    These are the real overdue-AR findings. They live in")
        print("    agent_anomalies, surface in ar_collections_triage, and are NOT")
        print("    touched by this script. The after-count below proves it.")

        print("\n⚠️  THIS IS HOUSEKEEPING, NOT A FIX. 47 broken steps across 18")
        print("    workflows still fail on every run after A-1 — clearing this")
        print("    column means the next accumulation starts in 'failed'.")

        if not args.execute:
            print("\nDRY-RUN complete. Nothing was deleted.")
            print("Re-run with --execute to delete.\n")
            return

        if not all_ids:
            say("nothing to delete.")
            return
        try:
            typed = input(
                f"\nType the tenant slug ({company.slug}) to confirm deleting "
                f"{len(all_ids)} runs and {steps} run-steps: "
            ).strip()
        except EOFError:
            die("no terminal to confirm on — this must be run by a human.")
        if typed != company.slug:
            die("confirmation did not match — nothing deleted.")

        # run_steps first: its FK cascades, but deleting explicitly means the
        # count in the report is the count that happened rather than an
        # inference about what the database did on our behalf.
        db.execute(text("DELETE FROM workflow_run_steps WHERE run_id = ANY(:i)"), {"i": all_ids})
        db.execute(text("DELETE FROM workflow_runs WHERE id = ANY(:i)"), {"i": all_ids})
        db.commit()

        anomalies_after = db.execute(text(
            "SELECT count(*) FROM agent_anomalies a JOIN agent_jobs j ON j.id = a.agent_job_id "
            "WHERE j.tenant_id = :c AND j.job_type = 'ar_collections'"
        ), {"c": company.id}).scalar()

        print(f"\nDELETED {len(all_ids)} runs, {steps} run-steps.")
        print(f"AR collections anomalies AFTER: {anomalies_after} "
              f"({'unchanged — the findings survive' if anomalies_after == anomalies_before else '⚠️ CHANGED — investigate'})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
