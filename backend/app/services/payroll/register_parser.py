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

#: Earnings codes the register is known to use. An unknown code is REPORTED,
#: never dropped — a code nobody has seen is either a new pay type or a parse
#: fault, and both need a person to look.
KNOWN_EARNING_CODES = frozenset({
    "Reg", "OT", "PTO", "Sick", "Vac", "VacBonus", "Ber", "Hol",
    "Winter", "Bonus", "Comm", "HealthInsS",
    # ⚠️ `Sal` IS NOT IN THE BRIEF'S EXPECTED LIST AND APPEARS 260 TIMES.
    # Salaried pay, measured on the real register across the year. Added
    # because a code this common is not an anomaly to report every import —
    # but FLAGGED here rather than folded in silently, because the brief's
    # list came from James reading the registers and this one was missed.
    "Sal",
})
KNOWN_DEDUCTION_CODES = frozenset({"Union"})

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

    @property
    def people(self) -> set[str]:
        return {c.emp_id or c.person for c in self.checks}


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


def split_glued_code(token: str, known: frozenset[str]) -> tuple[str, str]:
    """Separate a code from a description printed over it.

    ⚠️ Measured: `"HealthInsSHealth"` is the code `HealthInsS` followed by the
    start of "Health Insurance Stipend". Same overlapping-glyph cause as
    `unglue_amount`. Resolved by the LONGEST known code that prefixes the
    token, so a code that is a prefix of another (none today) cannot win by
    accident.
    """
    for code in sorted(known, key=len, reverse=True):
        if token.startswith(code) and token != code:
            return code, token[len(code):]
    return token, ""


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
            code, glued_desc = split_glued_code(e[0]["text"], KNOWN_EARNING_CODES)
            nums = [w for w in e[1:] if _MONEY.match(w["text"]) or _RATE.match(w["text"])]
            desc = " ".join([glued_desc] + [w["text"] for w in e[1:] if w not in nums])
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
            code, glued = split_glued_code(d[0]["text"], KNOWN_DEDUCTION_CODES)
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
                desc = " ".join([glued] + [unglue_amount(w["text"])[0]
                                           for w in d[1:] if not _MONEY.match(w["text"])])
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
    """Person name, Emp Id and base rate from the left-hand block."""
    name_parts: list[str] = []
    emp_id = ""
    base_rate: Decimal | None = None
    for row in rows:
        p = _band(row, BAND_PERSON)
        if not p:
            continue
        texts = [w["text"] for w in p]
        if "Emp" in texts and "Id" in texts:
            emp_id = texts[-1]
        elif "Rate" in texts:
            base_rate = _dec(texts[-1])
        elif not any(t in ("Code", "Total") for t in texts):
            name_parts.extend(texts)
    return " ".join(name_parts).strip(), emp_id, base_rate


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
    pages = pdf.pages if max_pages is None else pdf.pages[:max_pages]

    for pno, page in enumerate(pages, start=1):
        rows = cluster_rows(page.extract_words())
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

    return RegisterParseResult(checks=checks, failed=failed,
                               unknown_codes=unknown, pages=len(pages),
                               summary_blocks=len(skipped_summary_blocks))


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
