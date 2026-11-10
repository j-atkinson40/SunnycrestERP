"""The week's findings, one line each, as Opas would ask them — Payroll 3.

James, 2026-11-10: the first real list for the weekly Focus. **One line each,
no UI.** These are questions for Susan, not conclusions, and each one names the
figures so she can answer without opening anything.

⚠️ **A CAUSE IS ONLY NAMED WHEN IT HAS BEEN TESTED.** Where a difference is
unexplained the line says `unexplained` rather than offering the most
plausible-sounding story. Two causes were tested against week 44 and
DISPROVED, and they are recorded here so nobody re-runs them:

  * the pre-raise rate — gives dues 0.29 to 0.46 BELOW Payentry's, further off
    than the post-raise figures, not closer;
  * the register's own wage and hours — gives an identical figure to ours in
    all eleven cases, so the 0.01-hour differences do not account for it.

⚠️ **AND A FINDING IS A QUESTION, NOT AN ACCUSATION.** Two of these are about
people's time. The wording states what the records show and asks; it does not
characterise anybody.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class WeekFinding:
    """One line for the Focus, with the handful of facts behind it."""

    kind: str
    line: str
    #: Employee ids the line is about, so the Focus can scope it.
    emp_ids: tuple[str, ...] = ()
    #: Set only when a cause has been established. `None` means unexplained
    #: and the line says so.
    cause: str | None = None


def lunch_deduction_findings(lunch, *, names=None) -> list[WeekFinding]:
    """Days in an auto-lunch department with no deduction recorded."""
    names = names or {}
    by_date: dict = {}
    for f in lunch:
        by_date.setdefault(f.on_date, []).append(f)
    out = []
    for on_date, group in sorted(by_date.items()):
        who = ", ".join(f"{names.get(f.emp_id, 'employee')} ({f.emp_id})"
                        for f in group)
        day = on_date.strftime("%a %-d %b")
        hours = group[0].day_hours
        out.append(WeekFinding(
            kind="missing_lunch_deduction",
            line=(f"{who} recorded {hours} hours on {day} with no half-hour "
                  f"lunch deduction, which is automatic in their department. "
                  f"Their overtime is 0.50 higher than the register for the "
                  f"same week — should the deduction have been taken?"),
            emp_ids=tuple(f.emp_id for f in group),
            cause="the register applied the deduction and the hours file did not"))
    return out


def dues_without_earnings_findings(checks, *, week_check_date, hours_emp_ids,
                                   names=None) -> list[WeekFinding]:
    """Members charged dues on a check that paid them nothing.

    ⚠️ The shape that found Stevenson: no hours in the week, no earnings on
    the check, and a union deduction taken anyway.
    """
    names = names or {}
    out = []
    for chk in sorted((c for c in checks if c.check_date == week_check_date),
                      key=lambda c: (len(c.emp_id or ""), c.emp_id or "")):
        dues = sum((l.amount for l in chk.lines
                    if l.kind == "deduction" and l.code == "Union"), Decimal("0"))
        earned = sum((l.amount for l in chk.lines if l.kind == "earning"),
                     Decimal("0"))
        if dues and earned == 0:
            who = names.get(chk.emp_id, "employee")
            out.append(WeekFinding(
                kind="dues_without_earnings",
                line=(f"{who} ({chk.emp_id}) has no hours in Payentry this "
                      f"week and no earnings at all on the "
                      f"{week_check_date.isoformat()} check, but ${dues} of "
                      f"union dues was deducted. What is his status?"),
                emp_ids=(chk.emp_id,)))
    return out


def dues_difference_findings(rows, *, names=None,
                             ruled_out=("pre-raise rate",
                                        "the register's own wage and hours")
                             ) -> list[WeekFinding]:
    """Per-member dues differences against the week's register check.

    `rows` is an iterable of `(emp_id, ours, payentry, cause_or_None)`.

    ⚠️ Every line carries BOTH figures and either a tested cause or the word
    `unexplained`. A line that said only "differs" would send Susan to find
    the numbers herself, and a line that guessed a cause would send her to
    check the wrong thing.
    """
    names = names or {}
    out = []
    for emp_id, ours, payentry, cause in rows:
        who = names.get(emp_id, "employee")
        diff = Decimal(str(ours)) - Decimal(str(payentry))
        tail = (f"Most likely {cause}." if cause
                else f"Unexplained — the pre-raise rate and "
                     f"{ruled_out[1]} were both tested and ruled out.")
        out.append(WeekFinding(
            kind="dues_difference",
            line=(f"{who} ({emp_id}): we calculate ${ours} of dues, Payentry "
                  f"deducted ${payentry}, a difference of ${diff}. {tail}"),
            emp_ids=(emp_id,), cause=cause))
    return out


def summarise(findings: list[WeekFinding]) -> dict[str, int]:
    out: dict[str, int] = {}
    for f in findings:
        out[f.kind] = out.get(f.kind, 0) + 1
    return out
