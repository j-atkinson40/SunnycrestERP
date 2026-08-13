"""The verdicts. CR-2 A-1.

⚠️ THERE IS NO GRACEFUL PATH. Every declared expectation emits a row, always.
Three times on 2026-08-13 a signal died in tolerant code — a seed that logged
`not found — skip` and continued, a `|| PERIOD_BADGE.open` fallback that rendered
a locked month as open, and a `.get()` default that returned a plausible zero for
a key that never existed. Each was caught only by something insisting on a
number. **The graceful path is where the signal dies**, so this module has none:
no early return, no filtered-out row, no silent skip. A probe that cannot run
produces `UNKNOWN` — a row that says so — never an omission.

⚠️ FIVE VERDICTS, NOT FOUR. The design doc named four; the declining ruling
arrived after it and adds `DECLINED`. Recorded here rather than quietly folded
in, because "the doc said four" is the kind of drift this arc is about.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.completeness.expectations import (
    periods_in_window,
    Expectation,
    declination_for,
    due_on,
    for_tenant,
    period_for,
)

#: Evidence present, and at or above any declared minimum.
ARRIVED = "arrived"
#: Something landed but less than declared. Distinct from missing on purpose.
PARTIAL = "partial"
#: Past due with nothing. The only verdict that is an accusation.
MISSING = "missing"
#: In its period, not yet late. What a two-state design eats — and reporting a
#: deliverable due on the 20th as missing on the 5th trains readers to ignore it.
NOT_YET_DUE = "not_yet_due"
#: The tenant said they don't do this, and why.
DECLINED = "declined"
#: The probe could not run. NOT absence — a broken check must not read as a
#: clean period, which is the exact substitution this module exists to refuse.
UNKNOWN = "unknown"

VERDICTS = (ARRIVED, PARTIAL, MISSING, NOT_YET_DUE, DECLINED, UNKNOWN)

#: Verdicts a reader must act on. `arrived` and `not_yet_due` are quiet.
ACTIONABLE = (MISSING, PARTIAL, UNKNOWN)


@dataclass(frozen=True)
class Verdict:
    key: str
    label: str
    role_slug: str
    verdict: str
    period_start: date
    period_end: date
    due: date
    observed: int | None      # None when the probe could not run
    detail: str               # why this verdict, in words a person can act on


def _probe(db: Session, exp: Expectation, tenant_id: str, start: date, end: date) -> int | None:
    """Count evidence rows in the period. None when the probe cannot run.

    Returning None rather than 0 on failure is load-bearing: a missing table or
    renamed column would otherwise report a clean count of nothing, which is a
    broken check wearing the costume of a complete period.
    """
    ev = exp.evidence
    try:
        return db.execute(
            text(
                f"SELECT COUNT(*) FROM {ev.table} "
                f"WHERE {ev.scope_column} = :t "
                f"AND CAST({ev.date_column} AS date) BETWEEN :s AND :e"
            ),
            {"t": tenant_id, "s": start, "e": end},
        ).scalar()
    except Exception:
        db.rollback()
        return None


def _tenant_start(db: Session, tenant_id: str) -> date | None:
    """When the tenant began. Nothing is owed for a period before that."""
    got = db.execute(
        text("SELECT created_at FROM companies WHERE id = :t"), {"t": tenant_id}
    ).scalar()
    return got.date() if got else None


def review(
    db: Session, tenant_id: str, vertical: str, as_of: date | None = None
) -> list[Verdict]:
    """Every expectation × every period in the window, each with one verdict.

    One row per (expectation, period). An expectation with nothing to say still
    emits its current period as `not_yet_due` — there is no path that returns
    fewer rows than were declared.
    """
    today = as_of or datetime.now().date()
    began = _tenant_start(db, tenant_id)
    out: list[Verdict] = []

    for exp in for_tenant(tenant_id, vertical):
        declined = declination_for(tenant_id, exp.key)
        if declined:
            # Rendered once, not filtered. A declined obligation that vanished
            # would be indistinguishable from one never declared.
            start, end = period_for(exp.cadence, today)
            out.append(Verdict(
                exp.key, exp.label, exp.role_slug, DECLINED, start, end,
                due_on(exp, end), None,
                f"Declined {declined.declined_on:%-d %b %Y}: {declined.reason}",
            ))
            continue

        for start, end in periods_in_window(exp.cadence, today, not_before=began):
            due = due_on(exp, end)
            n = _probe(db, exp, tenant_id, start, end)

            if n is None:
                verdict, detail = UNKNOWN, (
                    f"Could not read {exp.evidence.table}.{exp.evidence.date_column} — "
                    f"the check is broken, which is not the same as a clean period."
                )
            elif n == 0 and today <= due:
                verdict, detail = NOT_YET_DUE, f"Due {due:%-d %b}."
            elif n == 0:
                verdict, detail = MISSING, f"Was due {due:%-d %b}. {exp.matters_because}"
            elif exp.evidence.minimum is not None and n < exp.evidence.minimum:
                verdict, detail = PARTIAL, f"{n} of {exp.evidence.minimum} expected."
            else:
                verdict, detail = ARRIVED, f"{n} filed."

            out.append(Verdict(exp.key, exp.label, exp.role_slug, verdict,
                               start, end, due, n, detail))

    return out
