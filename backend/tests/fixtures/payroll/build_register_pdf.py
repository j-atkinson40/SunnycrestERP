"""Build an ANONYMISED Payroll Register PDF with the real page geometry.

⚠️ **NO REAL EXPORT EVER ENTERS THE REPOSITORY.** The register holds names,
employee ids, pay rates, child-support and garnishment lines. This module
builds a synthetic one instead: invented people (`E01`…), invented hours and
amounts, and only the CODES kept real, because the codes are the schema rather
than anybody's data.

⚠️ **THE GEOMETRY IS THE POINT, SO IT IS REPRODUCED, NOT APPROXIMATED.** The
parser locates columns by x-position and splits glued tokens by character
position. A fixture that merely contains the right words would pass while the
parser's actual mechanism rotted. So this writes text at the measured x bands
in Courier, whose fixed 0.6-em advance makes the glue deterministic:

  * a 9-character deduction code at x=530 ends at x=567.8, which is where the
    description starts — so `extract_words` returns the two as ONE token and
    the character-position splitter is genuinely exercised;
  * a negative amount placed INSIDE the description's x-range comes back as
    one interleaved token, exercising `unglue_amount`;
  * a `Total` block with no `Chk/Vcr #` exercises the summary-block skip.

Written by hand rather than with a PDF library so the tests need no dependency
the application does not already have.
"""
from __future__ import annotations

#: Courier advance width per character, as a fraction of the font size.
COURIER_ADVANCE = 0.6
#: ⚠️ 6.5, not 7. Courier's 0.6-em advance is WIDER than the register's real
#: font (3.9pt/char against Courier-at-7's 4.2), and at 7pt a ten-character
#: earnings code overflowed its column: the splitter then cut `HealthInsS`
#: into `HealthIns` + `SHealth…`, a fixture artefact with no counterpart in
#: the real file. 6.5 reproduces the measured advance, so a code that fits the
#: real column fits this one.
FONT_SIZE = 6.5
CHAR_W = FONT_SIZE * COURIER_ADVANCE          # 3.9pt

PAGE_W, PAGE_H = 792.0, 612.0
ROW_H = 9.5                                   # measured line pitch

#: x positions, measured on the real register. Kept in one place so a test can
#: assert the fixture and the parser agree about where the columns are.
X = {
    "name":        17.0,
    "emp_label":   19.0,
    "emp_value":   59.0,
    "rate_label":  19.0,
    "rate_value":  41.0,
    "earn_code":   78.0,
    "earn_desc":  115.0,
    "earn_hours": 188.0,
    "earn_rate":  218.0,
    "earn_amt":   264.0,
    "tax_code":   297.0,
    "tax_desc":   335.0,
    "tax_amt":    497.0,
    "ded_code":   530.0,
    "ded_desc":   567.0,
    "ded_amt":    642.0,
    "meta_label": 686.0,
    "meta_value": 760.0,
}


def _esc(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


class Page:
    """Text placed at absolute positions, addressed from the TOP of the page."""

    def __init__(self) -> None:
        self.items: list[tuple[float, float, str]] = []

    def at(self, x: float, top: float, text: str) -> "Page":
        self.items.append((x, top, text))
        return self

    def right_of(self, x: float, top: float, text: str) -> float:
        """Place `text` and return the x where its last character ends."""
        self.at(x, top, text)
        return x + len(text) * CHAR_W

    def stream(self) -> bytes:
        out = ["BT", f"/F1 {FONT_SIZE} Tf"]
        for x, top, text in self.items:
            # PDF y runs from the bottom; pdfplumber reports `top` from the top.
            y = PAGE_H - top - FONT_SIZE
            out.append(f"1 0 0 1 {x:.2f} {y:.2f} Tm ({_esc(text)}) Tj")
        out.append("ET")
        return "\n".join(out).encode("latin-1")


def write_pdf(pages: list[Page]) -> bytes:
    """A minimal, valid, uncompressed PDF with a real xref table."""
    objs: list[bytes] = []

    def add(body: bytes) -> int:
        objs.append(body)
        return len(objs)

    kids_num = 2
    font_num = 3
    page_nums: list[int] = []
    add(b"")                                                  # 1: catalog
    add(b"")                                                  # 2: pages
    objs[font_num - 1 : font_num - 1] = []
    add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")   # 3: font

    for page in pages:
        content = page.stream()
        c_num = add(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content))
        p_num = add(
            b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %d %d] "
            b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
            % (kids_num, int(PAGE_W), int(PAGE_H), font_num, c_num)
        )
        page_nums.append(p_num)

    objs[0] = b"<< /Type /Catalog /Pages %d 0 R >>" % kids_num
    objs[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (
        b" ".join(b"%d 0 R" % n for n in page_nums), len(page_nums))

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (i, body)

    xref_at = len(out)
    out += b"xref\n0 %d\n" % (len(objs) + 1)
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += (b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (len(objs) + 1, xref_at))
    return bytes(out)


# ── the register itself ──────────────────────────────────────────────────────

def check_block(
    page: Page,
    top: float,
    *,
    surname: str,
    given: str,
    emp_id: str,
    base_rate: str | None,
    check_number: str | None,
    check_date: str,
    net: str,
    earnings: list[tuple[str, str, str | None, str | None, str]],
    taxes: list[tuple[str, str, str]],
    deductions: list[tuple[str, str, str, bool]],
    total_hours: str,
    total_earnings: str,
    total_taxes: str,
    total_deductions: str,
) -> float:
    """One check, laid out exactly as Payentry prints it. Returns the next top.

    `deductions` entries are `(code, description, amount, overlap)`. With
    `overlap` the amount is drawn INSIDE the description, which is what
    Payentry does to a negative deduction and what produces the single
    interleaved token `unglue_amount` recovers.
    """
    # Surname sits on the same row as the `Code … Hours … Amount` header.
    page.at(X["name"], top, surname)
    page.at(X["earn_code"], top, "Code")
    page.at(X["earn_desc"], top, "Description")
    page.at(X["earn_hours"], top, "Hours")
    page.at(X["earn_rate"], top, "Rate")
    page.at(X["earn_amt"], top, "Amount")
    page.at(X["tax_code"], top, "Code")
    page.at(X["tax_desc"], top, "Description")
    page.at(X["tax_amt"], top, "Amount")
    page.at(X["ded_code"], top, "Code")
    page.at(X["ded_desc"], top, "Description")
    page.at(X["ded_amt"], top, "Amount")

    page.at(X["name"], top + ROW_H, given)
    # A page TOTAL block has no `Emp Id` row at all, which is what makes
    # `_person_from_rows` return no name for it rather than inventing one.
    if emp_id:
        page.at(X["emp_label"], top + 2 * ROW_H, "Emp Id")
        page.at(X["emp_value"], top + 2 * ROW_H, emp_id)
    if base_rate is not None:
        page.at(X["rate_label"], top + 3 * ROW_H, "Rate")
        page.at(X["rate_value"], top + 3 * ROW_H, base_rate)

    meta = [("Type", "Reg"), ("Chk Date", check_date), ("Net", net)]
    if check_number is not None:
        meta.append(("Chk/Vcr #", check_number))
    for i, (label, value) in enumerate(meta):
        page.at(X["meta_label"], top + (i + 1) * ROW_H, label)
        page.at(X["meta_value"], top + (i + 1) * ROW_H, value)

    body_top = top + ROW_H
    for i, (code, desc, hours, rate, amount) in enumerate(earnings):
        r = body_top + i * ROW_H
        end = page.right_of(X["earn_code"], r, code)
        # A code that reaches the description column glues to it, as the real
        # register does. Anything shorter leaves a gap and stays two tokens.
        page.at(max(X["earn_desc"], end), r, desc)
        if hours is not None:
            page.at(X["earn_hours"], r, hours)
        if rate is not None:
            page.at(X["earn_rate"], r, rate)
        # ⚠️ `amount=None` prints HOURS WITH NO MONEY, which the register does
        # for salaried staff — a `Vac`, `PTO` or `Hol` line whose pay the
        # salary already covers. 36 such lines in the measured year.
        if amount is not None:
            page.at(X["earn_amt"], r, amount)

    for i, (code, desc, amount) in enumerate(taxes):
        r = body_top + i * ROW_H
        page.at(X["tax_code"], r, code)
        page.at(X["tax_desc"], r, desc)
        page.at(X["tax_amt"], r, amount)

    for i, (code, desc, amount, overlap) in enumerate(deductions):
        r = body_top + i * ROW_H
        end = page.right_of(X["ded_code"], r, code)
        desc_x = max(X["ded_desc"], end)
        page.at(desc_x, r, desc)
        if overlap:
            # Drawn over the description, a few characters in — the measured
            # shape of a negative deduction.
            page.at(desc_x + 4 * CHAR_W, r, amount)
        else:
            page.at(X["ded_amt"], r, amount)

    # ⚠️ At least 3 body rows before the totals line. A check with a single
    # earnings line would otherwise put its totals ON the `Emp Id` row, which
    # clusters them into one visual row and loses the employee id — the
    # fixture's own `E04` read back as `''` until this floor existed. The real
    # register always has the metadata column to keep a block tall enough.
    n = max(len(earnings), len(taxes), len(deductions), 3)
    tr = body_top + n * ROW_H
    # ⚠️ The second word of each total label is placed clear of the first
    # rather than at its measured x. In the real font `Total` ends before
    # `Earnings` begins and the two stay separate tokens; in Courier it would
    # overlap, merge, and then be split by the code-column rule into
    # `TotalEarni` + `ngs` — a fixture artefact that reads as a parser bug.
    # +4, not +1: `extract_words` joins tokens less than 3pt apart, so a 1pt
    # gap merges them again and the fix does nothing.
    label_gap = len("Total") * CHAR_W + 4.0
    page.at(X["earn_code"], tr, "Total")
    page.at(X["earn_code"] + label_gap, tr, "Earnings")
    page.at(X["earn_hours"], tr, total_hours)
    page.at(X["earn_amt"], tr, total_earnings)
    page.at(X["tax_code"], tr, "Total")
    page.at(X["tax_code"] + label_gap, tr, "Taxes")
    page.at(X["tax_amt"] + 4.0, tr, total_taxes)
    page.at(X["ded_code"], tr, "Total")
    page.at(X["ded_code"] + label_gap, tr, "Deductions")
    page.at(X["ded_amt"] + 5.0, tr, total_deductions)
    return tr + 2 * ROW_H


#: The footer's words, exported so a test cannot look for text the fixture
#: does not actually emit.
#:
#: ⚠️ They are SHORT, and that is deliberate. The first version used the real
#: footer's wording at the real footer's x positions, but Courier is wider
#: than the register's font, so the words overlapped and `extract_words`
#: returned them as ONE interleaved token (`SunnyLcarnedsstcIanpcing`). The
#: test then searched a name for `"Sunnycrest"`, which was never going to be
#: there — it passed with the name bug deliberately reintroduced. Measured on
#: the real file the footer is THREE separate tokens per row, so the fixture
#: has to be three separate tokens too.
FOOTER_WORDS = ("Sunny", "Land", "Inc", "Payroll", "Reg", "Pg")


def page_footer(page: Page, top: float) -> None:
    """The page trailer that the first version of the parser read as a name.

    ⚠️ This is in the fixture ON PURPOSE. It sits in the left band below the
    last check, which is exactly how 256 pages of footer became part of 256
    people's names. A fixture without it cannot redden that bug.
    """
    # Placed with a gap of more than 3pt, so each word stays its own token —
    # and inside x<70, so each one is in the band the name is read from.
    page.at(X["name"], top, FOOTER_WORDS[0])
    page.at(40.0, top, FOOTER_WORDS[1])
    page.at(59.0, top, FOOTER_WORDS[2])
    page.at(X["name"], top + ROW_H, FOOTER_WORDS[3])
    page.at(48.0, top + ROW_H, FOOTER_WORDS[4])
    page.at(63.0, top + ROW_H, FOOTER_WORDS[5])
