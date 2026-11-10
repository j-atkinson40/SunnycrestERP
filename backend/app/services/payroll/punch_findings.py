"""Questions the punch clock can answer — Payroll 3 Phase 2.

These are the detections behind the weekly Focus's early-release, early
clock-in and missed-punch questions. **They return findings only.** No UI, no
notification, no automatic consequence: a finding is something for a person to
look at, and three of these are about other people's behaviour.

⚠️ **THE SHIFT TIMES ARE A DEFAULT NOBODY HAS CONFIRMED.** 6:30-3:30 for
departments 101 and 103 is what James said the plant and delivery shift is,
and it carries `default_unconfirmed` so that every finding derived from it can
be told apart from one derived from a shift somebody actually agreed. A
department with no rule yields NO findings rather than borrowing another
department's hours — see `shift_for`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from app.services.payroll.punch_parser import DayPunches, Punch

#: How much earlier than shift start counts as early. James: more than 10 min.
EARLY_IN_THRESHOLD = timedelta(minutes=10)

#: How far before shift end counts as an early release. James: more than 1 hr.
EARLY_OUT_BEFORE_END = timedelta(hours=1)

#: How close together two early departures have to be to look coordinated.
EARLY_OUT_CLUSTER_WINDOW = timedelta(minutes=15)

#: Two is a coincidence; this is the smallest group the finding is about.
EARLY_OUT_MIN_PEOPLE = 2

SATURDAY = 5                    # Python weekday(): Monday=0

#: ⚠️ **THE EARLY DETECTORS RUN MONDAY TO FRIDAY ONLY** (James, 2026-11-10):
#: *"Saturday has no regular shift."* Measured on the real week 44: four
#: people clocked out from 10:53 on Saturday 2026-10-31 and the
#: clustered-departure detector called it a finding. It is not one — every
#: Saturday hour is overtime and a short Saturday is exactly what a short
#: Saturday looks like. A detector that cries wolf every weekend stops being
#: read within a month.
SHIFT_WEEKDAYS = frozenset({0, 1, 2, 3, 4})


def has_regular_shift(on_date) -> bool:
    """Is this a day the shift rule describes at all?"""
    return on_date.weekday() in SHIFT_WEEKDAYS


@dataclass(frozen=True)
class ShiftRule:
    """When a department is expected to start and end.

    `status` is the provenance vocabulary Payroll 4 Phase 3 introduced:
    `default_unconfirmed` means a figure is in force because something had to
    be, not because anyone agreed it.
    """

    departments: frozenset[str]
    start: time
    end: time
    status: str = "default_unconfirmed"
    source: str = "James 2026-11-10, plant and delivery shift; not confirmed"


#: The only rule there is today.
DEFAULT_SHIFT_RULES = (
    ShiftRule(departments=frozenset({"101", "103"}),
              start=time(6, 30), end=time(15, 30)),
)


@dataclass
class PunchFinding:
    kind: str
    on_date: date
    detail: str
    people: tuple[str, ...] = ()
    #: ⚠️ Carried on every finding so a reader can tell a conclusion from a
    #: guess without going to look up the rule.
    shift_status: str | None = None


def dept_code(dept: str | None) -> str | None:
    """`'[103] Production'` -> `'103'`."""
    if not dept:
        return None
    m = re.search(r"\[(\d+)\]", dept)
    return m.group(1) if m else None


def shift_for(dept: str | None, rules=DEFAULT_SHIFT_RULES) -> ShiftRule | None:
    """The rule covering a department, or None.

    ⚠️ **None MEANS NO FINDINGS FOR THAT DEPARTMENT, NOT A FALLBACK.** Office
    and sales keep different hours from the plant; applying the plant's
    6:30-3:30 to them would manufacture an "early release" finding about
    somebody working their normal day. Measured on week 44: departments 106,
    107 and 108 have no rule, so 10 of the 17 people in the punch file are
    outside every detector below.
    """
    code = dept_code(dept)
    if code is None:
        return None
    for rule in rules:
        if code in rule.departments:
            return rule
    return None


def find_unpaired_punches(days: list[DayPunches]) -> list[PunchFinding]:
    """A punch with no partner. Nothing is inferred to close it."""
    out = []
    for day in days:
        for punch in day.unpaired:
            out.append(PunchFinding(
                kind="unpaired_punch", on_date=day.on_date,
                detail=(f"{day.name} has an unmatched punch at "
                        f"{punch.punch_at.strftime('%H:%M')} "
                        f"({len(day.pairs)} complete pair(s) that day). "
                        f"No shift end is assumed."),
                people=(day.name,)))
    return out


def find_early_clock_ins(days: list[DayPunches], *, rules=DEFAULT_SHIFT_RULES
                         ) -> list[PunchFinding]:
    """Clocking in more than `EARLY_IN_THRESHOLD` before shift start."""
    out = []
    for day in days:
        # ⚠️ Saturday and Sunday have no regular shift, so "early" is undefined.
        if not has_regular_shift(day.on_date):
            continue
        first = day.first_in
        if first is None:
            continue
        rule = shift_for(first.dept, rules)
        if rule is None:
            continue
        expected = datetime.combine(day.on_date, rule.start)
        early = expected - first.punch_at
        if early > EARLY_IN_THRESHOLD:
            out.append(PunchFinding(
                kind="early_clock_in", on_date=day.on_date,
                detail=(f"{day.name} clocked in at "
                        f"{first.punch_at.strftime('%H:%M')}, "
                        f"{int(early.total_seconds() // 60)} min before the "
                        f"{rule.start.strftime('%H:%M')} shift start"),
                people=(day.name,), shift_status=rule.status))
    return out


def find_clustered_early_departures(days: list[DayPunches], *,
                                    rules=DEFAULT_SHIFT_RULES
                                    ) -> list[PunchFinding]:
    """Several people leaving together, well before shift end.

    ⚠️ **BOTH CONDITIONS, AND THE CLUSTER IS THE POINT.** One person leaving
    early is their business and a hundred reasons explain it. Several leaving
    within a quarter of an hour of each other, more than an hour early, is a
    pattern — and it is the pattern the weekly Focus was asked about. A
    detector that fired on single early departures would bury it.
    """
    out = []
    by_date: dict[date, list[tuple[Punch, DayPunches, ShiftRule]]] = {}
    for day in days:
        # ⚠️ Saturday and Sunday have no shift END to be early against.
        if not has_regular_shift(day.on_date):
            continue
        out_punch = day.last_out
        if out_punch is None:
            continue
        rule = shift_for(out_punch.dept, rules)
        if rule is None:
            continue
        end = datetime.combine(day.on_date, rule.end)
        if end - out_punch.punch_at > EARLY_OUT_BEFORE_END:
            by_date.setdefault(day.on_date, []).append((out_punch, day, rule))

    for on_date, entries in sorted(by_date.items()):
        entries.sort(key=lambda e: e[0].punch_at)
        used: set[str] = set()
        for i, (punch, day, rule) in enumerate(entries):
            if day.name in used:
                continue
            group = [(punch, day)]
            for other_punch, other_day, _ in entries[i + 1:]:
                if other_day.name in used or other_day.name == day.name:
                    continue
                if other_punch.punch_at - punch.punch_at <= EARLY_OUT_CLUSTER_WINDOW:
                    group.append((other_punch, other_day))
            if len(group) >= EARLY_OUT_MIN_PEOPLE:
                for _, d in group:
                    used.add(d.name)
                times = ", ".join(f"{d.name} {p.punch_at.strftime('%H:%M')}"
                                  for p, d in group)
                out.append(PunchFinding(
                    kind="clustered_early_departure", on_date=on_date,
                    detail=(f"{len(group)} people clocked out within "
                            f"{int(EARLY_OUT_CLUSTER_WINDOW.total_seconds()//60)} "
                            f"min of each other, more than an hour before the "
                            f"{rule.end.strftime('%H:%M')} shift end: {times}"),
                    people=tuple(d.name for _, d in group),
                    shift_status=rule.status))
    return out


def find_saturday_work(days: list[DayPunches]) -> list[PunchFinding]:
    """Saturday hours, reported as overtime WORKED.

    ⚠️ **THE POSITIVE FORM OF THE SATURDAY RULE** (James, 2026-11-10):
    *"Saturday hours are reported as overtime worked, never as leaving
    early."* Every Saturday hour is overtime, so what a reader wants is how
    much was worked — not whether somebody left before a shift end that does
    not exist on a Saturday.

    Reported for every department, including those with no shift rule: hours
    worked are a fact and need no rule to interpret.
    """
    out = []
    for day in days:
        if day.on_date.weekday() != SATURDAY or not day.pairs:
            continue
        total = day.worked.total_seconds() / 3600
        first, last = day.pairs[0][0], day.pairs[-1][1]
        out.append(PunchFinding(
            kind="saturday_overtime_worked", on_date=day.on_date,
            detail=(f"{day.name} worked {total:.2f} hours on Saturday "
                    f"({first.punch_at.strftime('%H:%M')}-"
                    f"{last.punch_at.strftime('%H:%M')}); every Saturday hour "
                    f"is overtime"),
            people=(day.name,)))
    return out


def all_findings(days: list[DayPunches], *, rules=DEFAULT_SHIFT_RULES
                 ) -> list[PunchFinding]:
    return (find_unpaired_punches(days)
            + find_early_clock_ins(days, rules=rules)
            + find_clustered_early_departures(days, rules=rules)
            + find_saturday_work(days))
