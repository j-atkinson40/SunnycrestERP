"""What is OWED, declared. CR-2 A-1.

⚠️ DECLARED, NOT LEARNED. A baseline derived from history cannot tell "they
stopped sending" from "they never sent" — both read as a low number — and a
brand-new obligation has no history at all, so the case most worth alarming on
is the one a learned model is quietest about. This week's `drafts_generated`
defect was the same shape one layer down: a zero that meant ABSENT, read as NONE.

⚠️ A ROLE'S OBLIGATION — not a person, not a workflow.
  - Not a person: people leave, and an obligation keyed to a user id disappears
    with the account, going quiet exactly when turnover makes a gap likely.
  - Not a workflow: the workflow is the MECHANISM. r163 deleted the Social
    Service Certificate workflow three days before this was written; the
    certificate is still owed. Had the obligation been "this workflow runs,"
    deleting it would have looked like COMPLETION.

THREE SCOPES, like themes and workflow templates: platform → vertical → tenant.
A fresh tenant must have a working review on day one; an empty review teaches
nothing at the moment a new accountant needs it most.

⚠️ DECLINING IS A RECORDED STATE, NOT A DELETION. "This tenant doesn't pour on
site" is an answer. A declined obligation and a never-declared one must not look
identical — that distinction is the whole design, and a delete would erase it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

Cadence = Literal["daily", "weekly", "monthly"]


@dataclass(frozen=True)
class Evidence:
    """Where the proof of an obligation lands.

    A-1 declares the shape and probes it generically; A-2 owns the classifier
    (including the "reported nothing" carve-out, which this cannot yet express).
    """

    table: str
    scope_column: str          # company_id | tenant_id — verified per table, not assumed
    date_column: str
    #: Below this many rows the period is `partial` rather than `arrived`.
    #: None means presence alone satisfies.
    minimum: int | None = None


@dataclass(frozen=True)
class Expectation:
    key: str
    label: str
    #: WHOSE duty. Survives the person and the mechanism.
    role_slug: str
    cadence: Cadence
    #: Days after the period ends before it counts as late. A deliverable due on
    #: the 20th is not missing on the 5th.
    due_offset_days: int
    evidence: Evidence
    #: Why a human would care — rendered on the row, not decoration.
    matters_because: str


@dataclass(frozen=True)
class Declination:
    """A tenant saying "we don't do that", with the reason kept.

    Kept as a POSITIVE record so the review can say "declined: no on-site pours"
    rather than falling silent, which is what a deletion would produce and is
    indistinguishable from never having declared it.

    ⚠️ IT HAS A BEGINNING AND MAY HAVE AN END, AND THOSE TWO DATES ARE THE ONLY
    EXPRESSION OF ITS RANGE. `[declined_on, revoked_on)` — half-open, so the
    period a tenant resumes in is owed rather than forgiven. There is deliberately
    no `effective_from` / `effective_to` pair: a second way to express the same
    interval is two derivations of one fact, which is this codebase's recurring
    defect and not one worth importing into a new table.

    Revocation is IN-ROW, not a second record. A tenant that declines, resumes,
    and declines again has one Declination per episode — so "is this declined
    now" is the predicate `revoked_on IS NULL`, never latest-wins over rows with
    no guaranteed order. Unspecified ordering deciding an outcome is a defect this
    repository has shipped twice (`_schedulable_workflows` without ORDER BY;
    duplicate `step_order` resolved by whatever Postgres returned first).

    ⚠️ THE CLAIMANT IS EVIDENCE, NOT METADATA — r168's ruling, and it applies
    with more force here. A nil claim answers for one period; a declination
    stands until someone revokes it, so WHO said it matters more, not less. Name
    and role are SNAPSHOTTED at write time by `completeness_declinations`,
    because a join answers "what do they hold now", which is a different question
    from "did they hold it when they answered".
    """

    expectation_key: str
    reason: str
    declined_on: date
    declined_by_name: str
    declined_by_role_slug: str
    #: When the tenant resumed the obligation. None means still declined.
    revoked_on: date | None = None


# ── Platform scope: owed by every vertical ────────────────────────────

PLATFORM: list[Expectation] = [
    Expectation(
        key="bank_feed_daily",
        label="Bank transactions imported",
        role_slug="admin",
        cadence="daily",
        due_offset_days=1,
        evidence=Evidence("bank_transactions", "tenant_id", "transaction_date"),
        matters_because="Un-imported days leave reconciliation working from an incomplete ledger.",
    ),
]


# ── Vertical scope ────────────────────────────────────────────────────

VERTICAL: dict[str, list[Expectation]] = {
    "manufacturing": [
        Expectation(
            key="production_log_daily",
            label="Production log filed",
            role_slug="production",
            cadence="daily",
            due_offset_days=1,
            evidence=Evidence("production_log_entries", "tenant_id", "log_date"),
            matters_because="A day with no log cannot be distinguished from a day with no production.",
        ),
        Expectation(
            key="delivery_confirmations_daily",
            label="Deliveries confirmed",
            role_slug="driver",
            cadence="daily",
            due_offset_days=1,
            evidence=Evidence("deliveries", "company_id", "completed_at"),
            matters_because="Unconfirmed deliveries stall the invoice they should trigger.",
        ),
        Expectation(
            key="toolbox_talk_weekly",
            label="Toolbox talk held",
            role_slug="safety_trainer",
            cadence="weekly",
            due_offset_days=2,
            evidence=Evidence("toolbox_talks", "tenant_id", "conducted_at"),
            matters_because="A missed week is an OSHA gap that cannot be back-filled honestly.",
        ),
    ],
}


# ── Tenant scope ──────────────────────────────────────────────────────
#
# Tenant-authored DECLARATIONS, keyed by tenant id. Empty today. Out of scope for
# CR-3 and deliberately still a code seam: an added obligation needs an evidence
# source, and a source the schema does not model can only be satisfied by
# assertion — which is what three sub-arcs were spent closing.

TENANT_EXTRA: dict[str, list[Expectation]] = {}

# ⚠️ `TENANT_DECLINED` WAS HERE AND IS GONE — CR-3 D-1 (`r169`). It was a code
# dict nothing could write to, which is what a placeholder for a table looks
# like. Declinations now live in `completeness_declinations` and are read by
# `services/completeness/declinations.load_for_tenant`.
#
# Removed rather than kept alongside: a dict and a table both answering "is this
# obligation declined" is two producers of one fact. A declaration is a PLATFORM
# statement, versioned with the code that derives it; a declination is a TENANT
# observation, authored by an operator and reversible without a release. Only the
# first belongs in this file.


def for_tenant(tenant_id: str, vertical: str) -> list[Expectation]:
    """The resolved set: platform + vertical + tenant, deeper scope appended.

    Declinations are NOT filtered here. The review must render a declined row —
    removing it here would make "declined" and "never declared" identical, which
    is precisely the distinction the ruling protects.
    """
    return [
        *PLATFORM,
        *VERTICAL.get(vertical, []),
        *TENANT_EXTRA.get(tenant_id, []),
    ]


def declination_covering(
    declinations: list[Declination], period_start: date
) -> Declination | None:
    """The episode in force when this period BEGAN, or None.

    ⚠️ KEYED ON `period_start`, AND THAT IS THE FIX FOR A MEASURED DEFECT. The
    previous resolver ignored dates entirely and rendered one current-period row
    for a declined obligation, skipping the whole lookback window — so declining
    `production_log_daily` on testco turned `missing 6–11 Aug (6 periods)` into
    `declined 13 Aug (1 period)`. Six days of red erased by an answer given
    afterwards.

    A period that had already begun was owed in full when it began, so a
    declination takes effect from the next period and a revocation resumes the
    obligation from the next one. Declining today cannot rewrite yesterday, which
    is what makes the D-2 affordance something other than a button for clearing
    rows.

    Half-open on purpose: `revoked_on` is the first day the obligation is owed
    again, not the last day it was declined. An inclusive end would leave the
    resumption period ambiguous between the two episodes that touch it.

    Sane data yields at most one match — D-1's partial unique index allows one
    live episode per obligation, and episodes do not overlap. `max` on
    `declined_on` rather than `next` anyway, so that if overlapping episodes ever
    exist the answer is a STATED RULE (the most recent statement wins) instead of
    whatever the list order happened to be.
    """
    covering = [
        d
        for d in declinations
        if d.declined_on <= period_start
        and (d.revoked_on is None or period_start < d.revoked_on)
    ]
    return max(covering, key=lambda d: d.declined_on) if covering else None


def period_for(cadence: Cadence, as_of: date) -> tuple[date, date]:
    """The period containing `as_of`, inclusive both ends."""
    if cadence == "daily":
        return as_of, as_of
    if cadence == "weekly":
        start = as_of - timedelta(days=as_of.weekday())   # Monday
        return start, start + timedelta(days=6)
    first = as_of.replace(day=1)
    nxt = (first + timedelta(days=32)).replace(day=1)
    return first, nxt - timedelta(days=1)


def _step_back(cadence: Cadence, start: date) -> date:
    """One period earlier, by cadence."""
    if cadence == "daily":
        return start - timedelta(days=1)
    if cadence == "weekly":
        return start - timedelta(days=7)
    return (start - timedelta(days=1)).replace(day=1)


#: How far back each cadence looks. Small on purpose — the review answers "are
#: the books complete through this date", not "audit the year".
LOOKBACK = {"daily": 7, "weekly": 3, "monthly": 2}


def periods_in_window(
    cadence: Cadence, as_of: date, *, not_before: date | None = None
) -> list[tuple[date, date]]:
    """Periods to evaluate, oldest first, including the current one.

    ⚠️ EVALUATING ONLY THE CURRENT PERIOD MAKES `missing` UNREACHABLE. The due
    date of the current period is by construction in the future, so every row
    renders `not_yet_due` forever — a review that can never say anything while
    looking like it works. That was the first version of this function, and the
    A-1 gate existed to catch exactly it.

    `not_before` is the tenant's start. Nobody owes a production log for a day
    before they existed, and back-filling red to the beginning of the calendar
    is how a report teaches its reader to ignore it.
    """
    start, end = period_for(cadence, as_of)
    out = [(start, end)]
    for _ in range(LOOKBACK[cadence]):
        start = _step_back(cadence, start)
        s, e = period_for(cadence, start)
        if not_before and e < not_before:
            break
        out.append((s, e))
    return sorted(out)


def due_on(exp: Expectation, period_end: date) -> date:
    return period_end + timedelta(days=exp.due_offset_days)
