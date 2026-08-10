"""Clear the agent backlog — parked-empty jobs + payment-dangling anomalies.

Two accumulated classes, one script, DRY-RUN BY DEFAULT. Both are historical
residue: neither can be produced by today's code, so this runs once per affected
environment rather than on a schedule.

CLASS A — PARKED-EMPTY JOBS. Pre-fix, `BaseAgent.execute` parked EVERY run in
`awaiting_approval` unconditionally, generated an approval token and emailed a
review request — so the 15-minute expense_categorization cron asked for a
decision on an empty result every time it fired. The fix (`_nothing_to_approve`)
completes a run that found nothing. This backfills that decision onto the rows
that predate it.

  ⚠️  THE PREDICATE IS IMPORTED, NOT RESTATED. `PER_ANOMALY_APPROVAL_JOB_TYPES`
  is read from `BaseAgent` so this script and the runtime split cannot drift.
  A second list here would be free to diverge, and the specific divergence it
  would cause is the trap `base_agent.py` documents: month_end_close's approval
  is NOT about its anomalies — the close ITSELF is the decision and
  `approval_gate` writes the PeriodLock on approve. Auto-completing a clean
  close would skip both the human and the lock. Per-JOB agents always park,
  however quiet the run, and they are absent from that frozenset for that
  reason.

CLASS B — PAYMENT-DANGLING ANOMALIES. Unresolved anomalies whose `entity_id`
names a `customer_payments` row that no longer exists. These are NOT orphaned in
the FK sense — `AgentAnomaly.agent_job_id` is NOT NULL with ON DELETE CASCADE,
so an anomaly cannot outlive its job. They are SEMANTICALLY dangling: the
anomaly is unresolved, it is about a payment, and the payment was deleted out
from under it (the P-1 cleanup removed 212 customer payments; the anomalies
referenced them by VALUE, not by FK, so nothing cascaded). An operator opening
that queue sees items referencing nothing.

  ⚠️  THE PREDICATE IS DERIVED HERE, NOT INHERITED FROM A REPORT. It is built
  from the data model: `cash_receipts_agent` stamps every payment-bearing
  anomaly `entity_type="payment"`, `entity_id=<payment id>`. THE DRY-RUN COUNT
  IS THE RE-DERIVATION — if it does not reproduce the census figure, the
  predicate and the census disagree and the right response is to investigate,
  NOT to --execute. `high_unmatched_ratio` is a summary anomaly carrying no
  entity at all; it is correctly excluded and stays unresolved.

DISPOSITION — RESOLVED WITH A NOTE, NOT DELETED. Class B marks the anomalies
resolved and writes `resolution_note` saying why. The row is the record that the
agent once flagged something; deleting it would erase that the flag ever
existed. `resolved_by` stays NULL — no human made this call, and attributing it
to one would be a lie in an audit column.

WHAT THIS SCRIPT WILL NOT DO, DELIBERATELY:
  * It does not complete jobs left parked with anomaly_count > 0 whose anomalies
    all become resolved by class B. That is a THIRD disposition question — those
    runs did find something — and it is reported as an observation for a human,
    never acted on. See "OBSERVATIONS" in the output.
  * It does not clear `approval_token` on the jobs it completes. Those tokens
    are long past their 72-hour expiry and therefore inert, and the column is
    the audit trace that a review was once requested. Counted and reported;
    `--clear-tokens` opts in.

Reads DATABASE_URL from the environment via the app's SessionLocal. No
ENVIRONMENT guard — this is operator-invoked against a named target, production
included.

Usage (dry run — inspect, writes nothing)::

    railway run --environment production --service SunnycrestERP \
        .venv/bin/python -m scripts.clear_agent_backlog --tenant-slug sunnycrest

Usage (execute)::

    ... --tenant-slug sunnycrest --execute

Idempotent: a second run finds nothing to do and reports zeros.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.agent import AgentJob
from app.models.agent_anomaly import AgentAnomaly
from app.models.company import Company
from app.models.customer_payment import CustomerPayment
from app.schemas.agent import AgentJobStatus
from app.services.agents.base_agent import BaseAgent

#: Written onto every class-B anomaly. Names the cause, not just the effect —
#: an operator reading this row a year from now should not have to reconstruct
#: why it closed itself.
CLASS_B_NOTE = (
    "Auto-resolved by clear_agent_backlog: the customer payment this anomaly "
    "referenced no longer exists (deleted by the P-1 reconciliation cleanup). "
    "The anomaly was unresolved and pointed at nothing; no financial judgement "
    "was made about it."
)


def die(msg: str) -> None:
    print(f"\n❌ {msg}", file=sys.stderr)
    sys.exit(1)


def _resolve_tenant(db: Session, slug: str) -> Company:
    company = db.query(Company).filter(Company.slug == slug).one_or_none()
    if company is None:
        die(f"No tenant with slug {slug!r}.")
    return company


def _class_a_query(db: Session, tenant_id: str | None):
    """Parked runs that found nothing — the retroactive `_nothing_to_approve`.

    COALESCE mirrors the runtime's `int(self.job.anomaly_count or 0)`. The
    column is NOT NULL today, but the runtime tolerates NULL and so does this.
    """
    q = (
        db.query(AgentJob)
        .filter(AgentJob.status == AgentJobStatus.AWAITING_APPROVAL.value)
        .filter(AgentJob.job_type.in_(sorted(BaseAgent.PER_ANOMALY_APPROVAL_JOB_TYPES)))
        .filter(func.coalesce(AgentJob.anomaly_count, 0) == 0)
    )
    if tenant_id:
        q = q.filter(AgentJob.tenant_id == tenant_id)
    return q


def _class_b_query(db: Session, tenant_id: str | None):
    """Unresolved payment-referencing anomalies whose payment is gone.

    NOT EXISTS rather than NOT IN: `entity_id` is nullable and NOT IN against a
    set containing NULL silently returns no rows — the exact shape of a query
    that answers "zero" for the wrong reason.
    """
    gone = ~select(CustomerPayment.id).where(
        CustomerPayment.id == AgentAnomaly.entity_id
    ).exists()

    q = (
        db.query(AgentAnomaly, AgentJob.job_type, AgentJob.tenant_id)
        .join(AgentJob, AgentAnomaly.agent_job_id == AgentJob.id)
        .filter(AgentAnomaly.resolved.is_(False))
        .filter(AgentAnomaly.entity_type == "payment")
        .filter(AgentAnomaly.entity_id.isnot(None))
        .filter(gone)
    )
    if tenant_id:
        q = q.filter(AgentJob.tenant_id == tenant_id)
    return q


def _breakdown(rows: list[tuple[str, str]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for key, _ in rows:
        out[key] = out.get(key, 0) + 1
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Clear the agent backlog: parked-empty jobs + payment-dangling anomalies (dry-run by default)."
    )
    scope = ap.add_mutually_exclusive_group(required=True)
    scope.add_argument("--tenant-slug", help="Restrict to one tenant (the normal case).")
    scope.add_argument("--all-tenants", action="store_true",
                       help="Every tenant. Explicit because it is the wide blast radius.")
    ap.add_argument("--execute", action="store_true", help="Actually write (default is dry-run).")
    ap.add_argument("--clear-tokens", action="store_true",
                    help="Also NULL approval_token on the jobs completed by class A.")
    ap.add_argument("--skip-class-a", action="store_true", help="Leave parked-empty jobs alone.")
    ap.add_argument("--skip-class-b", action="store_true", help="Leave dangling anomalies alone.")
    args = ap.parse_args()

    if args.skip_class_a and args.skip_class_b:
        die("Both classes skipped — nothing to do.")

    db: Session = SessionLocal()
    try:
        tenant_id = None
        label = "ALL TENANTS"
        if args.tenant_slug:
            company = _resolve_tenant(db, args.tenant_slug)
            tenant_id, label = company.id, f"{company.name} ({company.slug})"

        print("=" * 72)
        print("AGENT BACKLOG CLEAR")
        print(f"scope: {label}")
        print(f"mode:  {'EXECUTE' if args.execute else 'DRY-RUN (default)'}")
        print("=" * 72)

        # ── CLASS A ────────────────────────────────────────────────────────
        a_jobs: list[AgentJob] = []
        if not args.skip_class_a:
            a_jobs = _class_a_query(db, tenant_id).all()
            print(f"\nCLASS A — parked runs that found nothing: {len(a_jobs)}")
            print(f"  predicate: status=awaiting_approval AND anomaly_count=0 AND job_type ∈")
            print(f"             PER_ANOMALY_APPROVAL_JOB_TYPES (imported from BaseAgent)")
            print(f"             = {sorted(BaseAgent.PER_ANOMALY_APPROVAL_JOB_TYPES)}")
            by_type = _breakdown([(j.job_type, j.id) for j in a_jobs])
            for jt, n in sorted(by_type.items(), key=lambda kv: -kv[1]):
                print(f"    · {jt}: {n}")
            if not by_type:
                print("    (none)")
            with_token = sum(1 for j in a_jobs if j.approval_token)
            already_done = sum(1 for j in a_jobs if j.completed_at is not None)
            print(f"  → would set status=complete, completed_at=now() "
                  f"(mirrors BaseAgent._set_status)")
            print(f"  carrying an approval_token: {with_token}"
                  + (" — will be NULLed (--clear-tokens)" if args.clear_tokens
                     else " — LEFT INTACT (inert past 72h expiry; --clear-tokens to clear)"))
            if already_done:
                print(f"  ⚠️  {already_done} already carry completed_at — preserved, not overwritten")

        # ── CLASS B ────────────────────────────────────────────────────────
        b_rows = []
        if not args.skip_class_b:
            b_rows = _class_b_query(db, tenant_id).all()
            print(f"\nCLASS B — unresolved anomalies whose payment no longer exists: {len(b_rows)}")
            print("  predicate: resolved=false AND entity_type='payment' AND entity_id IS NOT NULL")
            print("             AND NOT EXISTS (customer_payments.id = entity_id)")
            by_job_type = _breakdown([(jt, an.id) for an, jt, _ in b_rows])
            for jt, n in sorted(by_job_type.items(), key=lambda kv: -kv[1]):
                print(f"    · {jt}: {n}")
            if not by_job_type:
                print("    (none)")
            by_anom = _breakdown([(an.anomaly_type, an.id) for an, _, _ in b_rows])
            print("  by anomaly_type:")
            for at, n in sorted(by_anom.items(), key=lambda kv: -kv[1]):
                print(f"    · {at}: {n}")
            print("  → would set resolved=true, resolved_at=now(), resolution_note=<cause>")
            print("    resolved_by stays NULL — no human made this call.")

        # ── OBSERVATIONS — reported, never acted on ────────────────────────
        print("\nOBSERVATIONS (not acted on by this script)")
        if b_rows:
            touched_job_ids = {an.agent_job_id for an, _, _ in b_rows}
            resolving = {an.id for an, _, _ in b_rows}
            would_empty = []
            for jid in touched_job_ids:
                job = db.query(AgentJob).filter(AgentJob.id == jid).one()
                if job.status != AgentJobStatus.AWAITING_APPROVAL.value:
                    continue
                remaining = (
                    db.query(func.count(AgentAnomaly.id))
                    .filter(AgentAnomaly.agent_job_id == jid)
                    .filter(AgentAnomaly.resolved.is_(False))
                    .filter(~AgentAnomaly.id.in_(resolving))
                    .scalar()
                )
                if remaining == 0:
                    would_empty.append(jid)
            print(f"  · jobs still parked whose every anomaly would be resolved by class B: "
                  f"{len(would_empty)}")
            if would_empty:
                print("    These runs DID find something, so class A's predicate does not reach")
                print("    them and this script will not complete them. Their disposition is a")
                print("    separate decision for a human.")
        else:
            print("  · (none)")

        # ── COMMIT OR STOP ─────────────────────────────────────────────────
        if not args.execute:
            print("\nDRY-RUN complete. Nothing was written.")
            print("Check these counts against the census before re-running with --execute —")
            print("if they disagree, the predicate and the census disagree, and that is the")
            print("thing to resolve first.")
            return

        now = datetime.now(timezone.utc)
        for job in a_jobs:
            job.status = AgentJobStatus.COMPLETE.value
            if job.completed_at is None:
                job.completed_at = now
            if args.clear_tokens:
                job.approval_token = None
        for anomaly, _, _ in b_rows:
            anomaly.resolved = True
            anomaly.resolved_at = now
            anomaly.resolution_note = CLASS_B_NOTE
        db.commit()

        print(f"\nEXECUTED — class A: {len(a_jobs)} job(s) completed; "
              f"class B: {len(b_rows)} anomaly/anomalies resolved.")
        print("Re-run without --execute to confirm both now report zero.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
