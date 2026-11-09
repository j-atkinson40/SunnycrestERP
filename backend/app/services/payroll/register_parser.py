"""Parse a Payentry **Payroll Register** PDF into checks and their lines.

Payroll 4. This is the "what was actually paid" record: every check Payentry
issued, with its earnings, taxes and deductions exactly as printed. It is the
counterpart to `parsers.py`, which reads the weekly HOURS export — that one
says what we are about to pay, this one says what was paid.

⚠️ **ROWS ARE CLUSTERED BY `top`, NOT BUCKETED, AND THE DIFFERENCE IS A
SILENTLY WRONG PARSE.** `round(top / 3.5)` looks equivalent and is not: two
words on the same visual line whose `top` values straddle a bucket boundary
land in different rows, which splits one earnings line into two — one with the
code and no amount, one with the amount and no code. Both halves then fail
validation for reasons that do not name the cause. Clustering compares each
word to the OPEN cluster's first word, so a line is only split when there is a
real gap.

⚠️ **COLUMNS ARE LOCATED BY x-POSITION, NOT BY SPLITTING TEXT.** A register row
carries an earnings line, a tax line and a deduction line side by side, so the
same visual row belongs to three different records. Measured on the real file
(792x612 landscape, 262 pages):

    x < 70      person, Emp Id, Rate
    70 - 290    EARNINGS    code@78  desc@115  hours@188  rate@218  amount@264
    290 - 520   TAXES       code@297 desc@335            amount@497
    520 - 670   DEDUCTIONS  code@530 desc@567            amount@642
    x >= 670    per-check metadata, by label

⚠️ **A CODE GLUED TO ITS DESCRIPTION IS SPLIT BY CHARACTER POSITION, NOT BY
GUESSING A PREFIX.** When a code fills its column the renderer emits no space,
so `extract_words` returns `MedicalPTMedical` as one token. The first version
split these against a list of known codes, which cannot work: the list is what
you are trying to discover, so an unknown glued code stays glued and is
reported as an unknown code that does not exist. The description column starts
at a FIXED x in every band (115 earnings, 335 taxes, 567 deductions) and the
code never overlaps it, so the characters themselves say where the code ends.
Measured: `MedicalPTMedical` -> `MedicalPT` + `Medical`, `HSAEEIndHealth` ->
`HSAEEInd` + `Health`, `Med2ReimMedical` -> `Med2Reim` + `Medical`,
`HealthInsSHealth` -> `HealthInsS` + `Health`.

⚠️ **THE PERSON NAME IS READ FROM THE ROWS ABOVE `Emp Id`, AND NOTHING ELSE.**
The first version swept every left-band row in the block, which on the LAST
block of each page also swallowed the page footer — 256 pages of it. The result
was 72 distinct "people" for 30 employees, with 29 ids carrying more than one
name. The name occupies exactly the rows between the block header and the
`Emp Id` row: surname on the first, given name and middle initial on the
second. Rows at or after `Emp Id` are never name.

⚠️ **EVERY CHECK IS VALIDATED AND A FAILURE IS NEVER SILENTLY KEPT.** The sum
of a check's earnings must equal its printed Total Earnings, and the sum of its
deductions its printed Total Deductions. A register that does not add up means
the parse is wrong, not that the payroll was wrong — and a half-parsed check
would quietly understate somebody's dues.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

#: x-bands, measured from the real file. A band is a half-open interval.
BAND_PERSON = (0.0, 70.0)
BAND_EARNINGS = (70.0, 290.0)
BAND_TAXES = (290.0, 520.0)
BAND_DEDUCTIONS = (520.0, 670.0)
BAND_META = (670.0, 10_000.0)

#: Vertical tolerance for "same line". 3.5pt at this font size is about half a
#: line height, so it joins a line and never joins two.
ROW_TOLERANCE = 3.5

#: (code column x, description column x) for the earnings, tax and deduction
#: bands. A token that STARTS at a code x and reaches past its description x
#: has a code glued to its description; see the module docstring.
#:
#: ⚠️ **"STARTS AT THE CODE COLUMN" IS LOAD-BEARING.** Crossing the description
#: x is not on its own enough: the printed label `Total Earnings` puts
#: `Earnings` at x=97, which reaches past 115 and is one word. Splitting on
#: crossing alone cut it to `Earn` + `ings`, `_totals_from_rows` then found no
#: `Earnings` after `Total`, every printed total read as None, and all 1,275
#: checks failed with "block boundaries are wrong" — a reason that named
#: neither the cause nor the column. A real glued code always begins exactly
#: where its column begins.
CODE_AND_DESC_X = ((78.0, 115.0), (297.0, 335.0), (530.0, 567.0))

#: How far a token's x0 may sit from its code column and still be that column.
CODE_COLUMN_TOLERANCE = 1.5

#: Earnings codes, measured across the full year (1,275 checks). An unknown
#: code is REPORTED, never dropped — a code nobody has seen is either a new pay
#: type or a parse fault, and both need a person to look.
KNOWN_EARNING_CODES = frozenset({
    "Reg", "OT", "Sal", "PTO", "Vac", "Sick", "Comm", "HealthInsS",
    "Bonus", "Hol", "Ber", "Winter",
    #: Not seen in the year parsed, but named in the brief and expected by
    #: Phase 5. Kept so its first appearance is not reported as an anomaly.
    "VacBonus",
})

#: Deduction codes, measured across the full year. Thirteen, of which `Union`
#: is the only one that affects dues.
KNOWN_DEDUCTION_CODES = frozenset({
    "Union",
    "MedicalPT", "401k", "Kloan", "HSAEEInd", "CellReimb", "CafMed",
    "ChSup1", "Roth401K", "Garn", "Med2Reim", "BootReim", "GasReim",
})

#: ⚠️ **SENSITIVE. LINE-LEVEL ONLY, PAYROLL AREA ONLY.** Child support and
#: garnishment are a person's private legal circumstances. They are stored and
#: shown on the check they belong to, inside the payroll area, and they never
#: appear in a home note, a summary, a report total or any Opas text outside
#: the payroll area. `test_sensitive_deduction_codes.py` holds that line.
SENSITIVE_DEDUCTION_CODES = frozenset({"ChSup1", "Garn"})

#: The only deduction that is union dues.
DUES_DEDUCTION_CODE = "Union"

#: Earning codes that are NOT dues wage and NOT dues hours.
#:   `Sal` — salaried pay. Union members are hourly, so a check carrying both
#:           a Union deduction and a Sal line is an anomaly, reported by name.
#:   `Sick` — settled by the accountant on 2026-11-03: out of both dues wage
#:           and dues hours. The rulebook key `sick_in_dues_hours` is False.
DUES_EXCLUDED_EARNING_CODES = frozenset({"Sal", "Sick"})

_MONEY = re.compile(r"^-?[\d,]+\.\d{2}$")
_HOURS = re.compile(r"^-?[\d,]+\.\d{2}$")
_RATE = re.compile(r"^-?[\d,]+\.\d{4}$")
_DATE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")


class RegisterParseError(ValueError):
    """The register could not be read, or a check did not add up."""


@dataclass
class RegisterLine:
    kind: str                     # earning | tax | deduction
    code: str
    description: str
    hours: Decimal | None
    rate: Decimal | None
    amount: Decimal


@dataclass
class RegisterCheck:
    person: str
    emp_id: str
    department: str | None
    check_type: str | None        # "Reg" or an off-cycle label
    check_date: date | None
    batch: str | None
    check_number: str | None
    net: Decimal | None
    base_rate: Decimal | None
    lines: list[RegisterLine] = field(default_factory=list)
    printed_total_earnings: Decimal | None = None
    printed_total_hours: Decimal | None = None
    printed_total_deductions: Decimal | None = None
    page: int = 0

    # ── derived ──
    def sum_of(self, kind: str) -> Decimal:
        return sum((l.amount for l in self.lines if l.kind == kind), Decimal("0"))

    @property
    def idempotency_key(self) -> tuple[str, date | None, str]:
        """⚠️ Check number + check date + person, per the brief.

        The number alone is not unique: off-cycle checks are first-class and a
        person can hold more than one check on the same date, so the person is
        part of the key rather than an afterthought.
        """
        return (self.check_number or "", self.check_date, self.emp_id or self.person)


@dataclass
class RegisterParseResult:
    checks: list[RegisterCheck]
    failed: list[tuple[RegisterCheck, str]]       # check, why
    unknown_codes: dict[str, int]
    pages: int
    #: Page/company TOTAL blocks skipped — reported so "0 failures" cannot hide
    #: a block-detection change that started swallowing real checks.
    summary_blocks: int = 0
    #: One display name per Emp Id, chosen by frequency.
    display_names: dict[str, str] = field(default_factory=dict)
    #: Every name seen per Emp Id, with counts. More than one entry is
    #: REPORTED, never merged — see `resolve_display_names`.
    name_candidates: dict[str, dict[str, int]] = field(default_factory=dict)
    #: Tokens that straddled a description column but could not be split from
    #: their own characters. Counted so a layout change is visible.
    unsplit_glued_tokens: int = 0

    @property
    def people(self) -> set[str]:
        return {c.emp_id or c.person for c in self.checks}

    @property
    def ambiguous_names(self) -> dict[str, dict[str, int]]:
        """Emp Ids carrying more than one candidate name."""
        return {k: v for k, v in self.name_candidates.items() if len(v) > 1}

    @property
    def union_people(self) -> set[str]:
        """Emp Ids with at least one `Union` deduction line."""
        return {
            c.emp_id for c in self.checks
            if c.emp_id and any(l.kind == "deduction" and l.code == DUES_DEDUCTION_CODE
                                for l in c.lines)
        }


def _dec(text: str) -> Decimal | None:
    try:
        return Decimal(text.replace(",", ""))
    except (InvalidOperation, AttributeError):
        return None


def _as_date(text: str) -> date | None:
    m = _DATE.match(text)
    if not m:
        return None
    mm, dd, yyyy = (int(g) for g in m.groups())
    try:
        return date(yyyy, mm, dd)
    except ValueError:
        return None


def cluster_rows(words: list[dict], tolerance: float = ROW_TOLERANCE) -> list[list[dict]]:
    """Group words into visual rows.

    ⚠️ Compares each word to the OPEN cluster's first word rather than rounding
    `top` into a bucket. See the module docstring: bucketing splits a line whose
    words straddle a boundary, and the resulting halves fail validation without
    naming the cause.
    """
    out: list[list[dict]] = []
    cur: list[dict] = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if cur and abs(w["top"] - cur[0]["top"]) > tolerance:
            out.append(sorted(cur, key=lambda x: x["x0"]))
            cur = []
        cur.append(w)
    if cur:
        out.append(sorted(cur, key=lambda x: x["x0"]))
    return out


def unglue_amount(token: str) -> tuple[str, Decimal | None]:
    """Separate an overlapping money run from the text it is woven through.

    ⚠️ **PAYENTRY PRINTS A NEGATIVE DEDUCTION OVER ITS OWN DESCRIPTION, AND
    pdfplumber RETURNS THE TWO AS ONE TOKEN.** Measured on the real register:

        "Reimburs-1em9.e0n4t"   is "Reimbursement" + "-19.04"
        "Reimbursem-2e5n7t.07"  is "Reimbursement" + "-257.07"

    The two glyph runs overlap horizontally, so word-grouping merges them. The
    characters stay in order within each run, so splitting by character class
    recovers both exactly.

    ⚠️ **THIS IS WHY VALIDATION EARNS ITS KEEP.** The check that exposed it
    summed to 95.31 against a printed -180.80, and 95.31 - 19.04 - 257.07 is
    -180.80 to the cent — the two unreadable lines accounted for the entire
    discrepancy. Without the printed total to disagree with, the register would
    have imported two reimbursements short and nothing would have said so.
    """
    if not re.search(r"[A-Za-z]", token) or not re.search(r"\d", token):
        return token, None
    digits = "".join(ch for ch in token if ch.isdigit() or ch in "-.")
    letters = "".join(ch for ch in token if not (ch.isdigit() or ch in "-."))
    val = _dec(digits) if _MONEY.match(digits) else None
    return (letters, val) if val is not None else (token, None)


def split_glued_tokens(
    words: list[dict], chars: list[dict], columns=CODE_AND_DESC_X
) -> tuple[list[dict], int]:
    """Split tokens whose code is glued to the start of their description.

    ⚠️ **SPLITS BY CHARACTER POSITION, NOT BY A KNOWN-CODE PREFIX.** The
    previous version tried the longest known code that prefixed the token,
    which is circular — the code list is what the parse is meant to discover,
    so an unknown glued code stayed glued and was then reported as an unknown
    code that does not exist (`MedicalPTMedical`). The description column
    starts at a fixed x in every band and a code never reaches into it, so the
    character positions say exactly where the code ends.

    Only tokens that BEGIN at a code column are candidates — see
    `CODE_AND_DESC_X` for the printed label this protects.

    A candidate is only split when its own characters reconstruct it exactly.
    Anything else is left whole and COUNTED, so a font or layout change shows
    up as a number in the import report rather than as a silent mis-split.
    """
    out: list[dict] = []
    unsplit = 0
    for w in words:
        desc_x = next(
            (d for c, d in columns
             if abs(w["x0"] - c) <= CODE_COLUMN_TOLERANCE and w["x1"] > d + 1.0),
            None,
        )
        if desc_x is None:
            out.append(w)
            continue
        own = sorted(
            (c for c in chars
             if abs(c["top"] - w["top"]) <= 1.0
             and c["x0"] >= w["x0"] - 0.5 and c["x1"] <= w["x1"] + 0.5),
            key=lambda c: c["x0"],
        )
        left = [c for c in own if c["x0"] < desc_x - 1.0]
        right = [c for c in own if c["x0"] >= desc_x - 1.0]
        if not left or not right or "".join(c["text"] for c in own) != w["text"]:
            unsplit += 1
            out.append(w)
            continue
        out.append({**w, "text": "".join(c["text"] for c in left), "x1": left[-1]["x1"]})
        out.append({**w, "text": "".join(c["text"] for c in right), "x0": right[0]["x0"]})
    return out, unsplit


def _band(row: list[dict], band: tuple[float, float]) -> list[dict]:
    lo, hi = band
    return [w for w in row if lo <= w["x0"] < hi]


def _is_header_row(row: list[dict]) -> bool:
    """The `Code … Hours Rate Amount` row that opens each check block."""
    e = _band(row, BAND_EARNINGS)
    texts = {w["text"] for w in e}
    return "Code" in texts and "Hours" in texts and "Amount" in texts


def _meta_from_rows(rows: list[list[dict]]) -> dict[str, str]:
    """Read the right-hand block by LABEL, not by row offset.

    ⚠️ Keyed on the label text because the block's rows are not at fixed
    offsets from the block start: a check with four earnings lines pushes
    `Chk/Vcr #` further down than one with two. An offset-based read works on
    page 1 and drifts thereafter.
    """
    out: dict[str, str] = {}
    for row in rows:
        meta = _band(row, BAND_META)
        if not meta:
            continue
        texts = [w["text"] for w in meta]
        joined = " ".join(texts)
        # The value is the last token; the label is everything before it.
        if len(texts) < 2:
            continue
        label, value = " ".join(texts[:-1]), texts[-1]
        key = label.rstrip(":").strip()
        if key in ("Type", "Chk Date", "Batch", "Net", "Dir Dep", "Chk Amt", "Chk/Vcr #"):
            out.setdefault(key, value)
        elif joined.startswith("Chk/Vcr"):
            out.setdefault("Chk/Vcr #", value)
    return out


def _lines_from_rows(rows: list[list[dict]]) -> tuple[list[RegisterLine], dict[str, int]]:
    """Earnings, taxes and deductions from one check's rows."""
    lines: list[RegisterLine] = []
    unknown: dict[str, int] = {}

    for row in rows:
        # ── earnings ──
        e = _band(row, BAND_EARNINGS)
        if e and e[0]["text"] not in ("Code", "Total"):
            code = e[0]["text"]
            nums = [w for w in e[1:] if _MONEY.match(w["text"]) or _RATE.match(w["text"])]
            desc = " ".join(w["text"] for w in e[1:] if w not in nums)
            hours = rate = amount = None
            # ⚠️ Assign by x-position, not by order: a line with no rate (a
            # flat Bonus) would otherwise shift its amount into the rate slot.
            for w in nums:
                v = _dec(w["text"])
                if 180 <= w["x0"] < 212:
                    hours = v
                elif 212 <= w["x0"] < 250:
                    rate = v
                elif 250 <= w["x0"] < 290:
                    amount = v
            if amount is not None:
                if code not in KNOWN_EARNING_CODES:
                    unknown[code] = unknown.get(code, 0) + 1
                lines.append(RegisterLine("earning", code, desc.strip(), hours, rate, amount))

        # ── taxes ──
        t = _band(row, BAND_TAXES)
        if t and t[0]["text"] not in ("Code", "Total"):
            code = t[0]["text"]
            amt = next((_dec(w["text"]) for w in reversed(t)
                        if _MONEY.match(w["text"]) and w["x0"] >= 490), None)
            if amt is not None:
                desc = " ".join(w["text"] for w in t[1:] if not _MONEY.match(w["text"]))
                lines.append(RegisterLine("tax", code, desc.strip(), None, None, amt))

        # ── deductions ──
        d = _band(row, BAND_DEDUCTIONS)
        if d and d[0]["text"] not in ("Code", "Total"):
            code = d[0]["text"]
            amt = next((_dec(w["text"]) for w in reversed(d)
                        if _MONEY.match(w["text"]) and w["x0"] >= 630), None)
            if amt is None:
                # ⚠️ A NEGATIVE deduction is printed OVER its description and
                # comes back as one token. Recover it rather than dropping the
                # line — see `unglue_amount`.
                for w in d[1:]:
                    _text, _val = unglue_amount(w["text"])
                    if _val is not None:
                        amt = _val
                        break
            if amt is not None:
                desc = " ".join(unglue_amount(w["text"])[0]
                                for w in d[1:] if not _MONEY.match(w["text"]))
                if code not in KNOWN_DEDUCTION_CODES:
                    unknown[f"deduction:{code}"] = unknown.get(f"deduction:{code}", 0) + 1
                lines.append(RegisterLine("deduction", code, desc.strip(), None, None, amt))

    return lines, unknown


def _totals_from_rows(rows: list[list[dict]]) -> dict[str, Decimal]:
    """The printed Total Earnings / Taxes / Deductions, which validation uses."""
    out: dict[str, Decimal] = {}
    for row in rows:
        texts = [w["text"] for w in row]
        if "Total" not in texts:
            continue
        for i, w in enumerate(row):
            if w["text"] != "Total":
                continue
            nxt = row[i + 1]["text"] if i + 1 < len(row) else ""
            tail = [x for x in row[i:] if _MONEY.match(x["text"])]
            if nxt == "Earnings":
                hrs = [x for x in row[i:] if _HOURS.match(x["text"]) and 180 <= x["x0"] < 212]
                if hrs:
                    out["hours"] = _dec(hrs[0]["text"])
                amts = [x for x in tail if 250 <= x["x0"] < 290]
                if amts:
                    out["earnings"] = _dec(amts[-1]["text"])
            elif nxt == "Taxes" and tail:
                out["taxes"] = _dec(tail[-1]["text"])
            elif nxt == "Deductions" and tail:
                out["deductions"] = _dec(tail[-1]["text"])
    return out


def _person_from_rows(rows: list[list[dict]]) -> tuple[str, str, Decimal | None]:
    """Person name, Emp Id and base rate from the left-hand block.

    ⚠️ **THE NAME IS ONLY WHAT SITS ABOVE `Emp Id`.** See the module docstring:
    sweeping the whole left band also reads the page footer on the last block
    of each page, which produced 72 "people" for 30 employees. Reading stops at
    the `Emp Id` row, so a footer, a department line or anything else below it
    cannot become part of a name.

    Returns an empty name for a block with no `Emp Id` row at all — a page or
    company TOTAL block — rather than inventing a person out of its totals.
    """
    name_rows: list[str] = []
    emp_id = ""
    base_rate: Decimal | None = None
    found_emp_id = False

    for row in rows:
        p = _band(row, BAND_PERSON)
        if not p:
            continue
        texts = [w["text"] for w in p]
        if not found_emp_id:
            if "Emp" in texts and "Id" in texts:
                emp_id, found_emp_id = texts[-1], True
            else:
                name_rows.append(" ".join(texts))
        elif texts[0] == "Rate":
            base_rate = _dec(texts[-1])

    if not found_emp_id:
        return "", "", None

    # Surname on the first row, given name and middle initial on the second.
    # Rendered "Surname, Given M" so the two halves stay distinguishable.
    surname = name_rows[0] if name_rows else ""
    given = " ".join(name_rows[1:]).strip()
    person = f"{surname}, {given}" if surname and given else (surname or given)
    return person.strip().strip(","), emp_id, base_rate


def resolve_display_names(
    checks: list["RegisterCheck"],
) -> tuple[dict[str, str], dict[str, dict[str, int]]]:
    """One display name per Emp Id, by frequency, plus every candidate seen.

    ⚠️ **CANDIDATES ARE REPORTED, NEVER MERGED.** An id with two names is
    either a parse fault or a real name change, and only a person can tell
    which. The frequency winner is what the import shows; the full candidate
    list goes in the report so a second name is never silently absorbed.
    Ties break on the name text so the chosen name does not depend on page
    order.
    """
    counts: dict[str, dict[str, int]] = {}
    for chk in checks:
        if not chk.emp_id or not chk.person:
            continue
        per = counts.setdefault(chk.emp_id, {})
        per[chk.person] = per.get(chk.person, 0) + 1
    display = {
        emp_id: sorted(per.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        for emp_id, per in counts.items()
    }
    return display, counts


def union_salary_anomalies(checks: list["RegisterCheck"]) -> list["RegisterCheck"]:
    """Checks carrying BOTH a Union deduction and a `Sal` earning line.

    ⚠️ Union members are hourly (James, 2026-11-09). A check with both is a
    contradiction worth a person's attention, not something to resolve in code:
    either the pay type or the membership is wrong in Payentry.
    """
    return [
        chk for chk in checks
        if any(l.kind == "deduction" and l.code == DUES_DEDUCTION_CODE for l in chk.lines)
        and any(l.kind == "earning" and l.code == "Sal" for l in chk.lines)
    ]


def parse_register(pdf, *, max_pages: int | None = None) -> RegisterParseResult:
    """Parse an open `pdfplumber` PDF into checks.

    Takes an OPEN pdf object rather than a path, so the caller decides where the
    bytes come from — an upload, or a local file in a developer's Downloads. The
    real export never enters the repository.
    """
    checks: list[RegisterCheck] = []
    failed: list[tuple[RegisterCheck, str]] = []
    unknown: dict[str, int] = {}
    skipped_summary_blocks: list[tuple[int, object]] = []
    unsplit = 0
    pages = pdf.pages if max_pages is None else pdf.pages[:max_pages]

    for pno, page in enumerate(pages, start=1):
        words, page_unsplit = split_glued_tokens(page.extract_words(), page.chars)
        unsplit += page_unsplit
        rows = cluster_rows(words)
        # Block boundaries: each check opens with the `Code … Hours … Amount`
        # header row. Everything up to the next header belongs to that check.
        starts = [i for i, r in enumerate(rows) if _is_header_row(r)]
        for n, start in enumerate(starts):
            end = starts[n + 1] if n + 1 < len(starts) else len(rows)
            block = rows[start:end]

            person, emp_id, base_rate = _person_from_rows(block)
            meta = _meta_from_rows(block)
            lines, unk = _lines_from_rows(block)
            totals = _totals_from_rows(block)

            chk = RegisterCheck(
                person=person,
                emp_id=emp_id,
                department=None,
                check_type=meta.get("Type"),
                check_date=_as_date(meta.get("Chk Date", "")),
                batch=meta.get("Batch"),
                check_number=meta.get("Chk/Vcr #"),
                net=_dec(meta.get("Net", "")),
                base_rate=base_rate,
                lines=lines,
                printed_total_earnings=totals.get("earnings"),
                printed_total_hours=totals.get("hours"),
                printed_total_deductions=totals.get("deductions"),
                page=pno,
            )

            # ⚠️ **A BLOCK WITH NO CHECK NUMBER IS NOT A CHECK.** The register
            # prints page and company TOTAL blocks in the same three-column
            # shape, so block detection finds them too. Measured: 8 such blocks
            # across 262 pages, with printed deduction totals up to 95,676.26 —
            # grand totals, not payments. Skipping them is correct; reporting
            # them as failed checks would be 8 permanent false alarms, and
            # whoever read the import would learn to ignore the failure list.
            #
            # ⚠️ The ORDER matters: this must be decided BEFORE the sum checks,
            # which otherwise fire first and report a wrong reason (a summary
            # block "failing" because its totals do not match its lines).
            if not chk.check_number:
                skipped_summary_blocks.append((pno, totals.get("deductions")))
                continue

            # ⚠️ **VALIDATE, AND NEVER SILENTLY KEEP A FAILURE.** A register
            # that does not add up means the PARSE is wrong — the payroll
            # already happened and Payentry's own totals are the authority. A
            # half-read check would understate somebody's dues by exactly the
            # lines that went missing, and nothing downstream would notice.
            # ⚠️ Unknown codes are counted only for blocks that ARE checks.
            # Counting them before the summary-block skip mixed grand-total
            # noise ("0", "167", "457") into the report, which is how a real
            # unknown code would get lost in a list of 36 entries.
            for k, v in unk.items():
                unknown[k] = unknown.get(k, 0) + v

            why = validate_check(chk)
            (failed.append((chk, why)) if why else checks.append(chk))

    display, candidates = resolve_display_names(checks)
    return RegisterParseResult(checks=checks, failed=failed,
                               unknown_codes=unknown, pages=len(pages),
                               summary_blocks=len(skipped_summary_blocks),
                               display_names=display, name_candidates=candidates,
                               unsplit_glued_tokens=unsplit)


def validate_check(chk: RegisterCheck) -> str | None:
    """None if the check adds up, otherwise why it does not."""
    if chk.printed_total_earnings is None:
        return "no printed Total Earnings — block boundaries are wrong"
    got = chk.sum_of("earning")
    if got != chk.printed_total_earnings:
        return (f"earnings sum {got} != printed total "
                f"{chk.printed_total_earnings} (diff {got - chk.printed_total_earnings})")
    if chk.printed_total_deductions is not None:
        gotd = chk.sum_of("deduction")
        if gotd != chk.printed_total_deductions:
            return (f"deductions sum {gotd} != printed total "
                    f"{chk.printed_total_deductions} (diff {gotd - chk.printed_total_deductions})")
    if not chk.check_number:
        return "no check number — cannot be made idempotent"
    return None
