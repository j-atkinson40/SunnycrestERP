"""One row per condition, not per period. CR-2 A-3.

⚠️ SIX CONSECUTIVE MISSING DAYS IS ONE CONDITION. Rendering it six times makes
the report describe incidents that do not exist. Measured on testco: 28 rows, 21
`missing`, of which six were the bank feed having never run — said six times.

"Bank transactions: nothing since 6 Aug (6 days)" is TRUER than six rows saying
the same thing, and it is the difference between a report an accountant reads
and one they learn to scroll past. Expense Categorization's gate fired 12,365
times and was never once answered; that is what an un-collapsed list becomes.

This is not presentation polish. A list that describes six incidents where one
exists is wrong about the world.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.services.completeness.review import (
    ACTIONABLE,
    RENDERED,
    REPORTED_NONE,
    Verdict,
)


@dataclass(frozen=True)
class Run:
    """Consecutive periods of one expectation sharing a verdict."""

    key: str
    label: str
    role_slug: str
    verdict: str
    first: date
    last: date
    periods: int
    detail: str

    @property
    def actionable(self) -> bool:
        return self.verdict in ACTIONABLE


def collapse(verdicts: list[Verdict]) -> list[Run]:
    """Merge consecutive same-verdict periods per expectation, oldest first.

    Consecutive means ADJACENT IN THE WINDOW, not adjacent by date — weekly and
    monthly periods are not a day apart, and a date-gap test would refuse to
    merge them and quietly restore the per-period wall this exists to remove.
    """
    out: list[Run] = []
    for v in verdicts:
        prev = out[-1] if out else None
        if prev and prev.key == v.key and prev.verdict == v.verdict:
            out[-1] = Run(
                prev.key, prev.label, prev.role_slug, prev.verdict,
                prev.first, v.period_end, prev.periods + 1,
                # The RUN's detail, not the last period's — "nothing since
                # 6 Aug (6 days)" is the condition; "was due 7 Aug" is one
                # symptom of it and reads as a smaller problem than it is.
                _run_detail(prev, v),
            )
        else:
            out.append(Run(v.key, v.label, v.role_slug, v.verdict,
                           v.period_start, v.period_end, 1, v.detail))
    return out


def _run_detail(prev: Run, v: Verdict) -> str:
    n = prev.periods + 1
    if v.verdict in ACTIONABLE:
        return f"Nothing since {prev.first:%-d %b} — {n} periods."
    if v.verdict == REPORTED_NONE:
        # Kept legible on purpose: a month of nil claims is a finding, and it
        # only is one if a run of them is visible rather than merely quiet.
        return f"{n} periods reported empty, {prev.first:%-d %b}–{v.period_end:%-d %b}."
    return prev.detail


def summarise(runs: list[Run]) -> tuple[list[Run], str]:
    """Split into what renders as rows and what renders as one closing line.

    ⚠️ EXCEPTION-SHAPED. `arrived` and `not_yet_due` never enumerate — a reader
    scanning for a problem should not have to walk past everything that is fine
    to find it. But they are COUNTED, because "3 obligations current" is a
    different statement from silence, and silence is what a reader fills in with
    an assumption.

    `reported_none` renders as a ROW despite not being actionable. A month of
    signed nil claims is a finding, and folding it into the quiet count would
    hide the one thing the carve-out could be abused to do.

    ⚠️ SELECTION IS ON `RENDERED`, NOT ON `actionable`. The two are different
    properties and this function conflated them: `declined` is not actionable and
    is not quiet either, and selecting on actionability sent it to the quiet
    count — where a tenant's "we don't do that" was reported as an obligation
    that is current. See the `RENDERED` note in `review.py`.
    """
    shown = [r for r in runs if r.verdict in RENDERED]
    quiet = [r for r in runs if r not in shown]
    if not quiet:
        return shown, ""
    return shown, f"{len(quiet)} obligation{'s' if len(quiet) != 1 else ''} current."
