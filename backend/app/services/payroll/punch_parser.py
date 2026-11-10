"""Parse a Payentry **Punch Location** export into punches, and pair them.

Payroll 3 Phase 2. This is the clock behind the hours: who touched the kiosk,
when. It is the evidence for the weekly Focus's early-release, early-clock-in
and missed-punch questions.

⚠️ **COORDINATES ARE DROPPED AT PARSE TIME AND NEVER STORED** (James,
2026-11-10). Payroll does not use them, and keeping location history on thirty
people is a liability with no benefit. One boolean survives —
`has_location` — because "this punch came from a phone rather than the kiosk"
is occasionally worth knowing and costs nothing. The latitude, the longitude,
the accuracy, the IP address and the `[Map]` link text are read and discarded
in the same function, so there is no window in which the file's location data
exists in memory as a stored field.

⚠️ **THE EXPORT IS CHRONOLOGICAL, NOT GROUPED BY PERSON, AND PAIRING WITHIN A
BLOCK IS WRONG.** Payentry prints an `Employee Name:` header whenever the
employee changes between consecutive punches, so one person's punches are
scattered across several blocks. Measured on the real week-44 file: 28 blocks
for 17 people, and `Bell, Edward` appears in SEVEN of them — his Oct 26
out-punch at 3:43p sits in a later block than his 6:00a in-punch. Every block
for a person must be gathered and sorted by datetime before anything is
paired.

⚠️ **THE FILE HAS NO EMPLOYEE NUMBER.** It identifies people by name only, so
joining it to the hours file needs a name match — and Payentry spells one real
name "Micheal". Matching is normalised and then EXACT; an unmatched or
ambiguous name is a finding, never a silent fuzzy guess. A mapping a person
confirms is stored as an alias.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

#: The columns Payentry prints. Only the first two are kept.
#:
#: ⚠️ The header says `Latitude`, but for a kiosk punch Payentry puts the
#: literal text "kiosk punch" in that column — 149 of 168 rows on the real
#: file. So the column cannot be read as a number, and its content is a
#: location INDICATOR rather than a location.
COL_DATE, COL_PUNCH, COL_LATITUDE = 0, 1, 2

_DATE = re.compile(r"^([A-Z][a-z]{2}) (\d{1,2}), (\d{4})$")
_TIME = re.compile(r"^(\d{1,2}):(\d{2})\s*([ap])m?$", re.I)
_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}

#: Text Payentry writes in the Latitude column when there is no location.
NO_LOCATION_MARKER = "kiosk punch"


class PunchParseError(ValueError):
    """The file could not be read as a Payentry Punch Location export."""


@dataclass(frozen=True)
class Punch:
    """One clock event. No coordinates, by design."""

    name: str
    dept: str | None
    punch_at: datetime
    has_location: bool
    origin: str | None

    @property
    def on_date(self) -> date:
        return self.punch_at.date()


@dataclass
class PunchParseResult:
    punches: list[Punch]
    #: Name blocks seen, in file order. More than one per person is NORMAL.
    blocks: int
    #: Department labels, with the `[Map]` link text already stripped.
    departments: set[str]
    generated_by: str | None = None
    generated_on: str | None = None
    criteria: str | None = None

    @property
    def people(self) -> set[str]:
        return {p.name for p in self.punches}

    def by_person(self) -> dict[str, list[Punch]]:
        """⚠️ Gathers EVERY block for a person and sorts by datetime.

        This is the function that makes the chronological layout safe. Pairing
        anything before this has run pairs punches that are not consecutive
        for that person.
        """
        out: dict[str, list[Punch]] = {}
        for p in self.punches:
            out.setdefault(p.name, []).append(p)
        for name in out:
            out[name].sort(key=lambda p: p.punch_at)
        return out


def _parse_date(text: str) -> date | None:
    m = _DATE.match(text.strip())
    if not m or m.group(1) not in _MONTHS:
        return None
    return date(int(m.group(3)), _MONTHS[m.group(1)], int(m.group(2)))


def _parse_time(text: str) -> time | None:
    """Payentry writes `6:00a` and `3:41p` — one letter, no space."""
    m = _TIME.match(text.strip())
    if not m:
        return None
    hour, minute, half = int(m.group(1)), int(m.group(2)), m.group(3).lower()
    if not (1 <= hour <= 12) or minute > 59:
        return None
    if half == "a":
        hour = 0 if hour == 12 else hour
    else:
        hour = 12 if hour == 12 else hour + 12
    return time(hour, minute)


def _clean_dept(text: str) -> str:
    """Strip the `[Map]` hyperlink label and any embedded newline.

    ⚠️ Measured: the Sales department cell reads `[108] Sales\\r\\n[Map]`.
    """
    text = text.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\[\s*Map\s*\]", "", text, flags=re.I)
    return " ".join(text.split())


def parse_punch_location(content: bytes) -> PunchParseResult:
    """Parse the BIFF8 `.xls` export. Coordinates are discarded here."""
    import xlrd                                   # see requirements.txt

    try:
        book = xlrd.open_workbook(file_contents=content)
    except Exception as exc:                       # xlrd raises broadly
        raise PunchParseError(f"could not open the workbook: {exc}") from exc
    sheet = book.sheet_by_index(0)

    def cell(r: int, c: int) -> str:
        if c >= sheet.ncols or r >= sheet.nrows:
            return ""
        v = sheet.cell_value(r, c)
        return "" if v is None else str(v).strip()

    punches: list[Punch] = []
    departments: set[str] = set()
    dept = name = None
    blocks = 0
    meta: dict[str, str] = {}

    for r in range(sheet.nrows):
        joined = " ".join(cell(r, c) for c in range(sheet.ncols)).strip()
        if not joined:
            continue
        for key, label in (("generated_by", "Generated By :"),
                           ("generated_on", "Generated On :"),
                           ("criteria", "Date Criteria:")):
            if label in joined:
                meta[key] = joined.split(label, 1)[1].strip()
        if "Department:" in joined:
            dept = _clean_dept(joined.split("Department:", 1)[1])
            departments.add(dept)
            continue
        if "Employee Name:" in joined:
            name = " ".join(joined.split("Employee Name:", 1)[1].split())
            blocks += 1
            continue
        when = _parse_date(cell(r, COL_DATE))
        if when is None:
            continue                               # header, footer, criteria
        at = _parse_time(cell(r, COL_PUNCH))
        if at is None or name is None:
            continue
        marker = cell(r, COL_LATITUDE)
        # ⚠️ The ONLY thing kept from the location columns. `marker` is a local
        # and goes out of scope with this iteration.
        has_location = bool(marker) and marker.strip().lower() != NO_LOCATION_MARKER
        punches.append(Punch(name=name, dept=dept,
                             punch_at=datetime.combine(when, at),
                             has_location=has_location,
                             origin=cell(r, 6) or None))

    if not punches:
        raise PunchParseError(
            f"no punches found — is this a Payentry Punch Location export? "
            f"({sheet.nrows} rows read, {blocks} name blocks)")
    return PunchParseResult(punches=punches, blocks=blocks,
                            departments=departments,
                            generated_by=meta.get("generated_by"),
                            generated_on=meta.get("generated_on"),
                            criteria=meta.get("criteria"))


# ── pairing ──────────────────────────────────────────────────────────────────

@dataclass
class DayPunches:
    name: str
    on_date: date
    pairs: list[tuple[Punch, Punch]] = field(default_factory=list)
    #: Punches with no partner. ⚠️ A FINDING, never a guess.
    unpaired: list[Punch] = field(default_factory=list)

    @property
    def worked(self) -> timedelta:
        return sum((b.punch_at - a.punch_at for a, b in self.pairs), timedelta())

    @property
    def first_in(self) -> Punch | None:
        return self.pairs[0][0] if self.pairs else (
            self.unpaired[0] if self.unpaired else None)

    @property
    def last_out(self) -> Punch | None:
        return self.pairs[-1][1] if self.pairs else None


def pair_punches(result: PunchParseResult) -> list[DayPunches]:
    """Pair in/out per person per day, over ALL of that person's blocks.

    ⚠️ **AN ODD NUMBER OF PUNCHES LEAVES ONE UNPAIRED AND THAT IS THE ANSWER.**
    Nothing is inferred — not a shift end, not a midnight cut-off. A missed
    punch is a fact about the day that a person has to resolve, and inventing
    the other half would turn it into hours somebody gets paid for.
    """
    days: dict[tuple[str, date], DayPunches] = {}
    for name, punches in result.by_person().items():
        per_day: dict[date, list[Punch]] = {}
        for p in punches:
            per_day.setdefault(p.on_date, []).append(p)
        for on_date, todays in per_day.items():
            todays.sort(key=lambda p: p.punch_at)
            day = DayPunches(name=name, on_date=on_date)
            i = 0
            while i + 1 < len(todays):
                day.pairs.append((todays[i], todays[i + 1]))
                i += 2
            if i < len(todays):
                day.unpaired.append(todays[i])
            days[(name, on_date)] = day
    return [days[k] for k in sorted(days, key=lambda k: (k[0], k[1]))]
