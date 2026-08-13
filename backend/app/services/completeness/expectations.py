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
    """

    expectation_key: str
    reason: str
    declined_on: date


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
# Declarations and DECLINATIONS, keyed by tenant id. Empty today; A-3 and the
# settings surface author into it. Kept in code for A-1 per the no-new-table
# constraint — this is the seam a table would replace, not a permanent home.

TENANT_EXTRA: dict[str, list[Expectation]] = {}
TENANT_DECLINED: dict[str, list[Declination]] = {}


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


def declination_for(tenant_id: str, key: str) -> Declination | None:
    return next(
        (d for d in TENANT_DECLINED.get(tenant_id, []) if d.expectation_key == key),
        None,
    )


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
