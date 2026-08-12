"""MAP-5 — whether a cadence member's rhythm is actually HAPPENING.

The cadence cards teach WHEN work runs and say nothing about WHETHER it ran. This
arc measured how far those diverge [all PLATFORM-WIDE]:

    Safety Program Generation   live cron, ZERO runs ever — the sweep never reached it
    Compliance Sync             133 runs, all green, all executing nothing until r166
    Monthly Statement Run       4 runs, all parked at the gate, all pre-r165
    Pull Bank Transactions      runs twice daily and writes NOTHING (unpromoted)

A card reading "Overnight · Daily · 10:30 PM" beside any of those teaches a rhythm
that is not happening. That is silence-versus-zero in the teaching surface itself:
the card cannot tell "ran and found nothing" from "never ran".

⚠️ WE-1 A-1 IS WHAT MAKES THIS ANSWERABLE AT ALL. Before it, a step that did
nothing recorded `completed`, so "did it run" and "did it do something" were
indistinguishable in the data.

DERIVED, NEVER STORED. Read live at render — no cached liveness column. A stored
last-ran timestamp is a write-time status claim with no reader, which is the
seventh staleness variant already recorded in STATE.

ONE QUERY COVERS BOTH FIRING AUTHORITIES. The runtime sweep writes
`trigger_source='schedule'` and the MoC sweep writes `'moc_task_schedule'`, but
`execute_template` re-points mirrors back to the SOURCE `workflow_id`, so both
land on one key. Proven, not reasoned: `wf_sys_ar_collections` carries rows of
both kinds under one id.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

#: The seven states a member can be in. Four are generic (they fall out of run
#: status alone); `runs_dry` and `not_reportable` are configuration facts; the
#: seventh is a broken reference — see `UNKNOWN_JOB` below.
NEVER_RUN = "never_run"
RAN_AND_CLOSED = "ran_and_closed"
LEFT_A_DECISION = "left_a_decision"
DID_NOT_COMPLETE = "did_not_complete"
RUNS_DRY = "runs_dry"
NOT_REPORTABLE = "not_reportable"
#: ⚠️ THE SEVENTH STATE, ADDED DURING THE BUILD BECAUSE THE BUILD PRODUCED IT.
#: Verifying this module against production I passed a GUESSED workflow id that
#: does not exist. `for_workflows` returned no row, and the classifier reported
#: "Scheduled, but hasn't run yet" about a job that runs TWICE DAILY.
#:
#: A missing lookup produced a CONFIDENT FALSE CLAIM rather than an absence —
#: which is silence-versus-zero inside the feature built to fix
#: silence-versus-zero. "No run row" and "no such workflow" are different facts
#: and the card must never merge them.
UNKNOWN_JOB = "unknown_job"

LIVENESS_STATES = (
    NEVER_RUN, RAN_AND_CLOSED, LEFT_A_DECISION,
    DID_NOT_COMPLETE, RUNS_DRY, NOT_REPORTABLE, UNKNOWN_JOB,
)


@dataclass(frozen=True)
class Liveness:
    state: str
    label: str
    last_run_at: Any = None


def _humanize_ago(delta_seconds: float) -> str:
    """Coarse on purpose. A cadence card teaches rhythm; minute-precision here
    invites reading it as a monitor, and a card that looks like a monitor gets
    trusted like one."""
    mins = int(delta_seconds // 60)
    if mins < 60:
        return "just now" if mins < 5 else f"{mins} minutes ago"
    hours = mins // 60
    if hours < 24:
        return "an hour ago" if hours == 1 else f"{hours} hours ago"
    days = hours // 24
    if days == 1:
        return "yesterday"
    if days < 30:
        return f"{days} days ago"
    return "over a month ago"


def classify(
    *,
    workflow_known: bool,
    has_tenant_ledger: bool,
    last_status: str | None,
    last_run_at: Any,
    now: Any,
    live_whens: list[str] | None = None,
    dry_whens: list[str] | None = None,
) -> Liveness:
    """One member's liveness. Pure — the query lives in `for_workflows`.

    ⚠️ ORDER IS LOAD-BEARING. `runs_dry` OUTRANKS the run-status states, because
    a dry run that recorded `completed` is still a preview that wrote nothing.
    Ranking status first would render "Ran 6 hours ago" over a run that changed
    nothing — which is precisely the misreading this module exists to prevent,
    and one that was made from better data than a card shows.
    """
    if not workflow_known:
        # ⚠️ MUST COME FIRST. A card member pointing at a workflow that does not
        # exist is a BROKEN REFERENCE, and every state below would describe it
        # as a fact about the job's rhythm. Falling through to `never_run` is
        # what this module was caught doing during its own build.
        #
        # Honest on the card, loud in the log: the operator is told we cannot
        # answer; the developer gets a warning that a member is dangling.
        return Liveness(UNKNOWN_JOB, "We can't find this job's runs")

    if not has_tenant_ledger:
        # ⚠️ SAYS WHY RATHER THAN FALLING SILENT. Ten members showing liveness
        # and two showing nothing reads as a broken feature; naming the boundary
        # makes it a scope limit. Same discipline as the deliberately-unmapped
        # copy — an absence that explains itself is not a gap.
        return Liveness(
            NOT_REPORTABLE,
            "Runs outside this tenant's ledger, so we can't say when",
        )

    if last_run_at is None:
        # PRESENT-TENSE FACT, NOT AN ACCUSATION. "Has never run" reads as a
        # fault on a job nobody triggered; "hasn't run yet" is the same
        # information without the blame.
        return Liveness(NEVER_RUN, "Scheduled, but hasn't run yet")

    ago = _humanize_ago((now - last_run_at).total_seconds())
    live_whens = list(live_whens or [])
    dry_whens = list(dry_whens or [])

    # ⚠️ MIXED PROMOTION IS LIVE, AND THE CARD NAMES WHICH SCHEDULE.
    # A task can carry several schedule triggers, promoted independently.
    # `runs_dry` means NOTHING GETS WRITTEN — so if any trigger is live, calling
    # the member dry is false in the direction that matters: "preview only" over
    # a job that writes on its evening run is the same error as "green" over one
    # that wrote nothing.
    #
    # But bare "live" under-informs, because half the schedule still produces
    # nothing. So the caveat NAMES the preview schedule rather than flagging
    # one — the same principle as `not_reportable` stating its boundary. A hedge
    # becomes information when it says which.
    #
    # Possible because per-trigger `is_live` + `summary` already reach here in
    # the resolved task payload; no new query, no new field.
    # Name the TIME, not the whole humanized phrase. A summary is
    # "<cadence> · <time>", so interpolating it whole gives
    # "Ran 6 hours ago · Daily · 10:30 PM is preview only" — three items where
    # there are two. Same collision `_join_frequencies` hit; same reason it
    # matters, because a correct fix that reads as a rendering bug gets
    # "fixed" back.
    caveat = ""
    if live_whens and dry_whens:
        times = [w.split(" · ", 1)[-1] for w in dry_whens]
        joined = times[0] if len(times) == 1 else (
            " and ".join(times) if len(times) == 2
            else ", ".join(times[:-1]) + f" and {times[-1]}"
        )
        noun, verb = ("run", "is") if len(times) == 1 else ("runs", "are")
        caveat = f" — the {joined} {noun} {verb} preview only"

    if not live_whens and dry_whens:
        # THE STATE THE DESIGN IS TESTED ON. It confirms the run and denies the
        # write in one line. "Writes nothing until promoted" was rejected:
        # accurate, but `promoted` is platform-admin vocabulary for a control a
        # tenant operator cannot see, and correct-but-unhelpful is still a copy
        # failure.
        return Liveness(RUNS_DRY, f"Ran {ago} · preview only — nothing was saved", last_run_at)

    if last_status == "awaiting_input":
        return Liveness(LEFT_A_DECISION, f"Ran {ago} · waiting on you{caveat}", last_run_at)

    if last_status == "failed":
        # "Didn't finish", not "failed". A run that halted on an unimplemented
        # step or a missing mapping is not the accountant's fault and often not
        # theirs to act on; an alarming word on a surface that renders daily
        # teaches people to ignore it. Work that IS theirs belongs in a queue
        # with an action, not a status line.
        return Liveness(DID_NOT_COMPLETE, f"Ran {ago} · didn't finish{caveat}", last_run_at)

    return Liveness(RAN_AND_CLOSED, f"Ran {ago}{caveat}", last_run_at)


def known_workflows(db: Session, workflow_ids: list[str]) -> set[str]:
    """Which of these ids are real `workflows` rows.

    ⚠️ SEPARATE FROM "HAS RUNS", DELIBERATELY. `for_workflows` returns rows only
    where a run exists, so a missing key there is ambiguous between "never ran"
    and "no such workflow" — and collapsing the two is what made this module
    report "hasn't run yet" about a job that runs twice daily.

    One extra query against a primary key. The alternative — inferring existence
    from a non-null template FK — assumes a referential guarantee this code does
    not check, and the whole point of `unknown_job` is not assuming.
    """
    if not workflow_ids:
        return set()
    rows = db.execute(
        sql_text("SELECT id FROM workflows WHERE id = ANY(:ids)"),
        {"ids": workflow_ids},
    )
    return {r[0] for r in rows}


def for_workflows(
    db: Session, *, workflow_ids: list[str], company_id: str
) -> dict[str, tuple[str | None, Any]]:
    """Latest run per workflow for one tenant → `{workflow_id: (status, at)}`.

    ONE query for every member, both authorities. `DISTINCT ON` takes the latest
    row per workflow; the existing index on `(workflow_id, started_at)` serves
    it. Measured cost is ~0.5 ms, against an area render that currently issues
    262 queries.

    Tenant-scoped deliberately: `workflow_runs.company_id` is the only scope that
    makes a per-tenant card honest, and a platform-wide figure read as one
    tenant's is a mistake this codebase has already made.
    """
    if not workflow_ids:
        return {}
    rows = db.execute(
        sql_text(
            "SELECT DISTINCT ON (workflow_id) workflow_id, status, started_at "
            "FROM workflow_runs "
            "WHERE company_id = :c AND workflow_id = ANY(:ids) "
            "ORDER BY workflow_id, started_at DESC"
        ),
        {"c": company_id, "ids": workflow_ids},
    )
    return {r[0]: (r[1], r[2]) for r in rows}
