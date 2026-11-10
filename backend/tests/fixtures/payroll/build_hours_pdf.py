"""Build an ANONYMISED Payentry Employee Hours report with the real geometry.

⚠️ **NO REAL EXPORT EVER ENTERS THE REPOSITORY.** Invented people, invented
hours. The COLUMN POSITIONS and the GLYPH PITCH are real, because those are
what the parser reads.

⚠️ **THE PITCH MUST EQUAL THE FONT'S ADVANCE, OR THE FIXTURE CANNOT REPRODUCE
THE BUG.** The parser separates two overlapping fields by chaining glyphs where
`next.x0 == prev.x1`. On the real export the digit pitch is 5.56pt and each
glyph is exactly 5.56pt wide, so a run is contiguous. If this fixture laid
characters at 5.56pt using a narrower font, every character would leave a gap,
the chain would break at the first step, and the de-interleaving test would
pass for a reason that has nothing to do with the real file. Courier advances
0.6em, so the size is 5.56 / 0.6.
"""
from __future__ import annotations

from .build_register_pdf import write_pdf

#: 5.56pt per character, the measured digit pitch of the real export.
CHAR_W = 5.56
FONT_SIZE = CHAR_W / 0.6
PAGE_W, PAGE_H = 842.0, 595.0
ROW_H = 11.5

#: Column x, measured from the real export's header row.
X = {
    "name": 46.0, "home": 165.98, "worked": 270.97, "job": 376.0,
    "date": 481.0, "paytype": 586.0, "hours": 691.0,
}

#: ⚠️ The measured offset between the Home Dept run and the employee-number
#: run when a long name pushes the bracket onto the dept column. 167.16 -
#: 165.98. Small enough that any single tolerance matches both runs, which is
#: exactly why `_identify_runs` assigns by NEAREST column instead.
OVERLAP_OFFSET = 1.18


def _esc(t: str) -> str:
    return t.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


class Page:
    """Characters placed individually, so any pitch can be reproduced."""

    def __init__(self) -> None:
        self.items: list[tuple[float, float, str]] = []

    def at(self, x: float, top: float, text: str) -> "Page":
        """Place `text` one character at a time at the measured pitch."""
        for i, ch in enumerate(text):
            self.items.append((x + i * CHAR_W, top, ch))
        return self

    def stream(self) -> bytes:
        out = ["BT", f"/F1 {FONT_SIZE:.4f} Tf"]
        for x, top, ch in self.items:
            y = PAGE_H - top - FONT_SIZE
            out.append(f"1 0 0 1 {x:.3f} {y:.3f} Tm ({_esc(ch)}) Tj")
        out.append("ET")
        return "\n".join(out).encode("latin-1")


def header(page: Page, top: float = 8.0) -> None:
    page.at(X["name"], top, "Employee Hours Report")
    page.at(400.0, top, "Sunnycrest Inc")
    page.at(X["name"], top + ROW_H, "Name")
    page.at(X["home"], top + ROW_H, "Home Dept")
    page.at(X["worked"], top + ROW_H, "Worked Dept")
    page.at(X["job"], top + ROW_H, "Job")
    page.at(X["date"], top + ROW_H, "Date")
    page.at(X["paytype"], top + ROW_H, "PayType")
    page.at(X["hours"], top + ROW_H, "Hours")


def footer(page: Page, top: float, n: int, of: int) -> None:
    page.at(X["name"], top, f"(c) MPAY Inc. {n} of {of}")


def pay_row(page: Page, top: float, *, name: str, emp_id: str, home: str,
            worked: str, date: str, pay_type: str, hours: str) -> None:
    """One pay line.

    ⚠️ The `[ nn]` field is RIGHT-ALIGNED after the name, exactly as Payentry
    prints it. When the name is long enough the field lands on the Home Dept
    column and the two OVERLAP — which is the whole hazard. The overlap is
    produced here by geometry, not faked by writing a merged string.
    """
    page.at(X["name"], top, name)
    bracket_x = X["name"] + (len(name) + 1) * CHAR_W
    field = f"[{' ' * max(1, 4 - len(emp_id))}{emp_id}]"
    if bracket_x + len(field) * CHAR_W > X["home"]:
        # Long name: the number field is pushed onto the dept column.
        page.at(bracket_x, top, "[")
        page.at(X["home"] + OVERLAP_OFFSET, top, f"{emp_id}]")
    else:
        page.at(bracket_x, top, field)
    page.at(X["home"], top, home)
    page.at(X["worked"], top, worked)
    page.at(X["date"], top, date)
    page.at(X["paytype"], top, pay_type)
    page.at(X["hours"], top, hours)


def name_only_row(page: Page, top: float, *, name: str, emp_id: str) -> None:
    """Listed with no hours — and therefore NO Home Dept column at all.

    ⚠️ For a long name the employee number lands exactly on x=166, where a
    rule that looks for a department first reads it as a department and loses
    the id. That is the Baran-Corgnell case.
    """
    page.at(X["name"], top, name)
    bracket_x = X["name"] + (len(name) + 1) * CHAR_W
    if bracket_x + 6 * CHAR_W > X["home"]:
        page.at(bracket_x, top, "[")
        page.at(X["home"], top, f"{emp_id}]")
    else:
        page.at(bracket_x, top, f"[{' ' * max(1, 4 - len(emp_id))}{emp_id}]")


def build() -> bytes:
    """A two-page report carrying every hazard the real export has."""
    pages = []

    p1 = Page()
    header(p1)
    top = 40.0
    # ── an ordinary short-name person: several days, REG + OT1 ──
    for d, reg, ot in (("10/26/2026", "8.00", "0.68"), ("10/27/2026", "8.00", "0.30"),
                       ("10/28/2026", "8.00", "0.10")):
        pay_row(p1, top, name="Bravo, Ben", emp_id="36", home="103",
                worked="103", date=d, pay_type="REG", hours=reg); top += ROW_H
        pay_row(p1, top, name="Bravo, Ben", emp_id="36", home="103",
                worked="103", date=d, pay_type="OT1", hours=ot); top += ROW_H
    # ── name-only, SHORT name (number nowhere near the dept column) ──
    name_only_row(p1, top, name="Echo, Eve", emp_id="38"); top += ROW_H
    # ── name-only, LONG name: the number lands ON x=166 ──
    name_only_row(p1, top, name="Baranoff, Susan Q.", emp_id="17"); top += ROW_H
    footer(p1, top + ROW_H, 1, 2)
    pages.append(p1)

    p2 = Page()
    header(p2)
    top = 40.0
    # ── THE INTERLEAVE CASE, and with it the -0.50 lunch deduction, a 0.00
    #    line, and two lines for the same day AND pay type ──
    for d, pt, h in (("10/27/2026", "REG", "-0.50"), ("10/27/2026", "REG", "9.50"),
                     ("10/31/2026", "REG", "4.00"), ("10/31/2026", "OT1", "1.37"),
                     ("10/31/2026", "REG", "0.00"), ("10/31/2026", "OT1", "0.55")):
        pay_row(p2, top, name="Delgado, Chris Jr.", emp_id="20",
                home="108", worked="108", date=d, pay_type=pt, hours=h)
        top += ROW_H
    # ── a SECOND interleave case with a two-token surname and a Sick line ──
    for d, pt, h in (("10/26/2026", "REG", "8.00"), ("10/27/2026", "Sick", "8.00")):
        pay_row(p2, top, name="Sandoval Jr, Rob", emp_id="14", home="106",
                worked="106", date=d, pay_type=pt, hours=h)
        top += ROW_H
    # ── PTO, and a misspelled-name person keyed only by emp_id ──
    pay_row(p2, top, name="Foxtrot, Micheal", emp_id="22", home="108",
            worked="108", date="10/28/2026", pay_type="PTO", hours="4.00")
    top += ROW_H
    footer(p2, top + ROW_H, 2, 2)
    pages.append(p2)
    return write_pdf(pages)


#: What the fixture says, hand-totalled, so the tests assert against a stated
#: expectation rather than whatever the parser happens to produce.
#:   Bravo    REG 8.00 x3 = 24.00    OT1 0.68+0.30+0.10 = 1.08
#:   Delgado  REG -0.50+9.50+4.00+0.00 = 13.00   OT1 1.37+0.55 = 1.92
#:   Sandoval REG 8.00                           Sick 8.00
#:   Foxtrot  PTO 4.00
EXPECTED_TOTALS = {"REG": "45.00", "OT1": "3.00", "Sick": "8.00", "PTO": "4.00"}
EXPECTED_EMP_IDS = {"36", "38", "17", "20", "14", "22"}
EXPECTED_WITH_HOURS = {"36", "20", "14", "22"}
EXPECTED_LISTED_ONLY = {"38": "Echo, Eve", "17": "Baranoff, Susan Q."}
EXPECTED_HOME = {"36": "103", "20": "108", "14": "106", "22": "108"}
