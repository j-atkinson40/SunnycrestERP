"""Parse a Payentry **Employee Hours** report PDF into one row per pay line.

Payroll 3. This is the "what we are about to pay" record: every hour Payentry
recorded for a week, by person, day and pay type. `register_parser.py` reads
the other end — the checks actually issued.

⚠️ **THERE ARE NO PRINTED TOTALS IN THIS REPORT, SO NOTHING INSIDE THE FILE
VALIDATES IT.** The register parser could compare each check's lines against
its own printed totals; there is no equivalent here. Validation therefore comes
from outside: the week window, the punch clock, the register's own check, and —
the one that matters most — every employee id having to exist and resolve to a
single name. See `validations.py`.

⚠️ **AND "THE TOTALS MATCH" IS NOT EVIDENCE THAT THIS FILE WAS READ
CORRECTLY.** Measured on the real week-44 export: a naive `extract_text` parse
reproduces every hour total exactly — REG 618.45, OT1 74.16, PTO 4.00, Sick
12.00, 708.61 — while reading DiGenova's employee number as **12008** and
Sanchez Jr's as **"14 1"**. The Hours column sits 500pt away from where the
corruption happens, so no total can ever catch it. This is the same shape as
Payroll 4's prefix splitter silently reading every `VacBonus` line as `Vac`.

⚠️ **THE CAUSE IS TWO OVERLAPPING GLYPH RUNS, AND THE FIX IS GEOMETRIC.** The
`[ nn]` employee-number field is right-aligned immediately after the name, so a
long name pushes it onto the Home Dept column at x=166 and the two runs
overlap. Measured on DiGenova:

    glyphs sorted by x:  1  2  0  0  8  ]        -> "12008]"
    run A  x0 165.98, 171.54, 177.11  = "108"    <- Home Dept
    run B  x0 167.16, 172.72, 178.29  = "20]"    <- employee number

Within a run `next.x0 == prev.x1` exactly, so chaining on that contiguity
separates them. Nothing about character class can: both runs are digits.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.services.payroll.register_parser import cluster_rows

#: Column x positions, measured on the real export (A4 landscape, 842x595).
#: Taken from the header row, which prints `Name Home Dept Worked Dept Job
#: Date PayType Hours`.
X_NAME, X_HOME, X_WORKED, X_JOB, X_DATE, X_PAYTYPE, X_HOURS = (
    46.0, 166.0, 271.0, 376.0, 481.0, 586.0, 691.0)

#: How far a token may sit from its column and still belong to it. Generous
#: because these are left-aligned text columns; the ONE place a tight tolerance
#: matters is telling the Home Dept run from the employee-number run, which is
#: done by nearest-match rather than by tolerance. See `_identify_runs`.
COLUMN_TOLERANCE = 8.0

#: Glyph-chaining tolerance. Within a printed run the next character starts
#: exactly where the previous one ended; 0.6pt absorbs float noise without
#: ever bridging the ~1.2pt offset between two interleaved runs.
CONTIGUITY_TOLERANCE = 0.6

#: Pay types the report is known to use. Anything else is REPORTED, not
#: dropped — an unrecognised pay type is either a new one or a parse fault.
KNOWN_PAY_TYPES = frozenset({"REG", "OT1", "PTO", "Sick"})

#: Where each pay type goes in `payroll_week_lines`. Phase 3 uses this; it is
#: here so the mapping is stated once, beside the codes it maps.
PAY_TYPE_TO_BUCKET = {
    "REG": "reg_hrs",
    "OT1": "ot_hrs",
    "PTO": "personal_hrs",
    "Sick": "sick_hrs",
}

_HOURS = re.compile(r"^-?\d+\.\d{2}$")
_DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_FOOTER = re.compile(r"^\(c\)\s*MPAY", re.I)


class HoursParseError(ValueError):
    """The report could not be read as a Payentry Employee Hours export."""


@dataclass
class HoursLine:
    """One pay line: this person, this day, this pay type, these hours."""

    emp_id: str
    name: str
    home_dept: str | None
    worked_dept: str | None
    job: str | None
    work_date: date
    pay_type: str
    hours: Decimal
    page: int

    @property
    def bucket(self) -> str | None:
        return PAY_TYPE_TO_BUCKET.get(self.pay_type)


@dataclass
class HoursParseResult:
    lines: list[HoursLine]
    #: emp_id -> every name seen for it. More than one is a FINDING.
    names_by_emp: dict[str, set[str]]
    #: People printed with no hours at all: listed, nothing to pay.
    listed_without_hours: dict[str, str]          # emp_id -> name
    unknown_pay_types: dict[str, int]
    pages: int
    #: Rows that looked like data but could not be read. Never silently zero.
    unreadable_rows: list[tuple[int, str]] = field(default_factory=list)

    @property
    def emp_ids(self) -> set[str]:
        return {l.emp_id for l in self.lines} | set(self.listed_without_hours)

    def hours_by_pay_type(self) -> dict[str, Decimal]:
        out: dict[str, Decimal] = {}
        for line in self.lines:
            out[line.pay_type] = out.get(line.pay_type, Decimal("0")) + line.hours
        return out

    def hours_by_emp(self) -> dict[str, dict[str, Decimal]]:
        out: dict[str, dict[str, Decimal]] = {}
        for line in self.lines:
            per = out.setdefault(line.emp_id, {})
            per[line.pay_type] = per.get(line.pay_type, Decimal("0")) + line.hours
        return out

    @property
    def ambiguous_names(self) -> dict[str, set[str]]:
        return {e: n for e, n in self.names_by_emp.items() if len(n) > 1}


def runs_by_contiguity(chars: list[dict],
                       tolerance: float = CONTIGUITY_TOLERANCE
                       ) -> list[tuple[str, float, float]]:
    """Separate interleaved glyph runs by `next.x0 == prev.x1` chaining.

    ⚠️ **THIS IS WHAT STOPS A WRONG EMPLOYEE NUMBER.** When the `[ nn]` field
    overlaps the Home Dept column, the glyphs of the two fields interleave in
    x-order and any reading that takes them in that order is wrong. Each
    printed run is internally contiguous — the next character begins exactly
    where the previous ended — so following that chain recovers both runs
    whatever order they interleave in.

    Returns `(text, x0, x1)` per run, in left-to-right order of their starts.
    """
    remaining = sorted(chars, key=lambda c: c["x0"])
    out: list[tuple[str, float, float]] = []
    while remaining:
        run = [remaining.pop(0)]
        extended = True
        while extended:
            extended = False
            for i, c in enumerate(remaining):
                if abs(c["x0"] - run[-1]["x1"]) <= tolerance:
                    run.append(remaining.pop(i))
                    extended = True
                    break
        out.append(("".join(c["text"] for c in run), run[0]["x0"], run[-1]["x1"]))
    return sorted(out, key=lambda r: r[1])


def _cell(row: list[dict], x: float) -> str | None:
    for w in row:
        if abs(w["x0"] - x) < COLUMN_TOLERANCE:
            return w["text"]
    return None


def _dec(text: str | None) -> Decimal | None:
    if not text or not _HOURS.match(text):
        return None
    try:
        return Decimal(text)
    except InvalidOperation:                                  # pragma: no cover
        return None


def _identify_runs(numeric: list[tuple[str, float, float]], has_hours: bool
                   ) -> tuple[str | None, str | None]:
    """Decide which run is the employee number and which is the Home Dept.

    ⚠️ **BY NEAREST COLUMN, NOT BY A TOLERANCE.** The two runs can start 1.18pt
    apart, so any tolerance wide enough to find the Home Dept run also matches
    the employee-number run — and whichever is tested second wins. Measured
    consequence of getting this wrong: DiGenova parsed as `home=20, emp=None`.

    ⚠️ **AND A ROW WITH NO HOURS HAS NO HOME DEPT COLUMN AT ALL.** Payentry
    prints `Surname, Given [ nn]` and nothing else for someone listed with no
    hours, so the single numeric run is the employee number WHEREVER it lands.
    Baran-Corgnell's name is long enough to put her employee number 17 exactly
    on x=166, where a dept-first rule reads it as "department 17" and loses her
    id entirely. This branch is the only thing preventing that.
    """
    if not numeric:
        return None, None
    if not has_hours:
        return numeric[0][0], None
    home = min(numeric, key=lambda r: abs(r[1] - X_HOME))
    others = [r for r in numeric if r is not home]
    return (others[0][0] if others else None), home[0]


def parse_employee_hours(pdf, *, max_pages: int | None = None) -> HoursParseResult:
    """Parse an open `pdfplumber` PDF of a Payentry Employee Hours report.

    Takes an OPEN pdf so the caller decides where the bytes come from — an
    upload, or a local file outside the repository. The real export never
    enters version control.
    """
    lines: list[HoursLine] = []
    names_by_emp: dict[str, set[str]] = {}
    listed: dict[str, str] = {}
    unknown: dict[str, int] = {}
    unreadable: list[tuple[int, str]] = []

    pages = pdf.pages if max_pages is None else pdf.pages[:max_pages]
    for pno, page in enumerate(pages, start=1):
        chars = page.chars
        for row in cluster_rows(page.extract_words()):
            name_words = [w for w in row if w["x0"] < X_HOME - COLUMN_TOLERANCE]
            if not name_words:
                continue
            raw_name = " ".join(w["text"] for w in name_words).replace("\xa0", " ")
            if _FOOTER.match(raw_name) or raw_name.startswith("Employee Hours"):
                continue                                   # page header / footer
            if raw_name.startswith("Name") or raw_name.startswith("Generated") \
                    or raw_name.startswith("Date Criteria") \
                    or raw_name.startswith("Selected"):
                continue                                   # column head / cover
            # ⚠️ Every real name is "Surname, Given". The criteria page's
            # department list (`[101] Delivery`) has no comma, which is what
            # keeps it out without having to special-case page 1 by number.
            name = re.sub(r"\s*\[.*$", "", raw_name).strip()
            if "," not in name:
                continue

            top = row[0]["top"]
            hours_cell = _cell(row, X_HOURS)
            bracket = next((c for c in chars
                            if abs(c["top"] - top) < 3 and c["text"] == "["), None)
            emp_id = home = None
            if bracket is not None:
                region = [c for c in chars
                          if abs(c["top"] - top) < 3
                          and bracket["x1"] <= c["x0"] < X_WORKED - 6
                          and c["text"].strip()]
                numeric = [r for r in runs_by_contiguity(region)
                           if r[0].strip("[]/ ").isdigit()]
                numeric = [(r[0].strip("[]/ "), r[1], r[2]) for r in numeric]
                emp_id, home = _identify_runs(numeric, hours_cell is not None)

            if emp_id is None:
                unreadable.append((pno, raw_name[:60]))
                continue
            names_by_emp.setdefault(emp_id, set()).add(name)

            if hours_cell is None:
                listed.setdefault(emp_id, name)
                continue

            hours = _dec(hours_cell)
            date_cell = _cell(row, X_DATE)
            pay_type = _cell(row, X_PAYTYPE)
            if hours is None or not date_cell or not _DATE.match(date_cell) \
                    or not pay_type:
                unreadable.append((pno, raw_name[:60]))
                continue
            if pay_type not in KNOWN_PAY_TYPES:
                unknown[pay_type] = unknown.get(pay_type, 0) + 1

            lines.append(HoursLine(
                emp_id=emp_id, name=name, home_dept=home,
                worked_dept=_cell(row, X_WORKED), job=_cell(row, X_JOB),
                work_date=datetime.strptime(date_cell, "%m/%d/%Y").date(),
                pay_type=pay_type, hours=hours, page=pno,
            ))

    # ⚠️ Someone with hours is not "listed without hours", even if a
    # name-only row for them appeared first on an earlier page.
    with_hours = {l.emp_id for l in lines}
    listed = {e: n for e, n in listed.items() if e not in with_hours}

    if not lines:
        raise HoursParseError(
            "no pay lines found — is this a Payentry Employee Hours report? "
            f"({len(pages)} pages read, {len(unreadable)} unreadable rows)"
        )
    return HoursParseResult(lines=lines, names_by_emp=names_by_emp,
                            listed_without_hours=listed, unknown_pay_types=unknown,
                            pages=len(pages), unreadable_rows=unreadable)
