"""An anonymised two-page Payroll Register, built to exercise the real faults.

Every person, id, hour and amount here is invented. The CODES are real,
because the codes are the schema. See `build_register_pdf` for why the fixture
reproduces the page geometry rather than just the words.

Each check is here for a reason:

  C1  E01  an ordinary hourly check with Union dues, and a `Sick` line, so
           Phase 2 has a check where the sick-hours rule changes the answer.
  C2  E02  TWO glued tokens — `HealthInsS` reaching into the earnings
           description column and `MedicalPT` into the deduction one — plus a
           NEGATIVE `CellReimb` drawn over its own description.
  C3  E03  `ChSup1` and `Garn`: the sensitive codes, so the test that keeps
           them out of non-payroll surfaces has something to find.
  C4  E04  `Sal` AND a `Union` deduction on one check: the anomaly James asked
           to be reported rather than resolved in code. It also carries a
           `PTO` line with HOURS AND NO AMOUNT — the shape the parser used to
           drop, losing the hours while every amount total still balanced.
  T   —    a page TOTAL block with no `Chk/Vcr #`, which must be SKIPPED and
           COUNTED, not reported as a failed check.

And a page footer under the last check of each page, which is the thing that
used to be read as part of a person's name.
"""
from __future__ import annotations

from .build_register_pdf import Page, check_block, page_footer, write_pdf

#: What the fixture says, so a test asserts against a stated expectation
#: rather than against whatever the parser happens to produce.
EXPECTED_CHECKS = 4
EXPECTED_SUMMARY_BLOCKS = 1
EXPECTED_PEOPLE = {"E01", "E02", "E03", "E04"}
EXPECTED_DISPLAY_NAMES = {
    "E01": "Alpha, Ann A",
    "E02": "Bravo, Ben B",
    "E03": "Charlie, Cal C",
    "E04": "Delta, Dee D",
}
EXPECTED_UNION_PEOPLE = {"E01", "E03", "E04"}

#: ⚠️ **HAND-DERIVED FROM THE RULES, NOT FROM RUNNING THE ENGINE.** Each
#: `Union` amount below is the dues figure its own check's pay lines imply,
#: worked out on paper from the default rulebook (dues_pct 0.0145,
#: dues_cap_multiplier 0.6461, dues_per_hour 0.02, initiation_fee 10.00). A
#: fixture whose answer key came from the code under test would agree with any
#: formula at all, including a wrong one.
#:
#:   E01  dues wage = Reg 1000.00 + OT 375.00            = 1375.00
#:        dues hours = 40.00 + 10.00                     =   50.00
#:        (the Sick line — 8.00 hours, 200.00 — is in NEITHER, per the
#:         accountant's answer of 2026-11-03)
#:        a = 1375.00 * 0.0145                           = 19.9375  -> 19.94
#:        b = (1375.00 / 50.00) * 0.6461
#:          = 27.50 * 0.6461                             = 17.76775 -> 17.77
#:        c = 50.00 * 0.02                               =  1.00
#:        dues = min(19.94, 17.77) + 1.00 = 18.77                  (b binds)
#:
#:   E03  dues wage = Reg 720.00,  dues hours = 40.00
#:        a = 720.00 * 0.0145                            = 10.44
#:        b = (720.00 / 40.00) * 0.6461 = 18.00 * 0.6461 = 11.6298 -> 11.63
#:        c = 40.00 * 0.02                               =  0.80
#:        dues = min(10.44, 11.63) + 0.80 = 11.24                  (a binds)
#:        CHARGED 21.24 — exactly 10.00 more, an initiation fee. A deliberate
#:        MISS, so the classifier has a real case of its most important bucket.
#:
#:   E04  Sal only, so dues wage = 0 and dues hours = 0 -> dues 0.00, while
#:        45.00 was charged. The `no_dues_bearing_earnings` case, and the same
#:        check as the Sal+Union anomaly.
EXPECTED_DUES = {
    "E01": {"wage": "1375.00", "hours": "50.00", "dues": "18.77",
            "charged": "18.77", "matches": True,  "binds": "b"},
    "E03": {"wage": "720.00",  "hours": "40.00", "dues": "11.24",
            "charged": "21.24", "matches": False, "binds": "a"},
    "E04": {"wage": "0",       "hours": "0",     "dues": "0.00",
            "charged": "45.00", "matches": False, "binds": "zero"},
}


def build() -> bytes:
    p1 = Page()
    top = 90.0
    top = check_block(
        p1, top,
        surname="Alpha", given="Ann A", emp_id="E01", base_rate="25.0000",
        check_number="9001", check_date="11/13/2025", net="1243.50",
        earnings=[
            ("Reg", "Regular", "40.00", "25.0000", "1000.00"),
            ("OT", "Overtime", "10.00", "37.5000", "375.00"),
            ("Sick", "Sick", "8.00", "25.0000", "200.00"),
        ],
        taxes=[("FITW", "Federal Income Tax", "150.00"), ("SS", "OASDI", "85.25")],
        deductions=[("Union", "Union Dues", "18.77", False),
                    ("401k", "401k", "55.00", False)],
        total_hours="58.00", total_earnings="1575.00",
        total_taxes="235.25", total_deductions="73.77",
    )
    top = check_block(
        p1, top,
        surname="Bravo", given="Ben B", emp_id="E02", base_rate="20.0000",
        check_number="9002", check_date="11/13/2025", net="705.00",
        earnings=[
            ("Reg", "Regular", "40.00", "20.0000", "800.00"),
            # 10 characters at x=78 reach past x=115, so this token comes back
            # glued to its description — the `HealthInsSHealth` case.
            ("HealthInsS", "Health Insurance Stipend", None, None, "50.00"),
        ],
        taxes=[("FITW", "Federal Income Tax", "90.00")],
        deductions=[
            # 9 characters at x=530 end at x=567.8, where the description
            # starts — the `MedicalPTMedical` case.
            ("MedicalPT", "Medical Pre Tax", "75.00", False),
            # Negative, drawn over its own description.
            ("CellReimb", "Cell Phone Reimbursement", "-20.00", True),
        ],
        total_hours="40.00", total_earnings="850.00",
        total_taxes="90.00", total_deductions="55.00",
    )
    top = check_block(
        p1, top,
        surname="Charlie", given="Cal C", emp_id="E03", base_rate="18.0000",
        check_number="9003", check_date="11/13/2025", net="398.40",
        earnings=[("Reg", "Regular", "40.00", "18.0000", "720.00")],
        taxes=[("FITW", "Federal Income Tax", "70.00")],
        deductions=[("ChSup1", "Child Support", "150.00", False),
                    ("Garn", "Garnishment", "80.00", False),
                    ("Union", "Union Dues", "21.24", False)],
        total_hours="40.00", total_earnings="720.00",
        total_taxes="70.00", total_deductions="251.24",
    )
    page_footer(p1, top)

    p2 = Page()
    top = 90.0
    top = check_block(
        p2, top,
        surname="Delta", given="Dee D", emp_id="E04", base_rate=None,
        check_number="9004", check_date="11/13/2025", net="1255.00",
        earnings=[
            ("Sal", "Salary", None, None, "1500.00"),
            # ⚠️ HOURS WITH NO AMOUNT — the shape that was silently dropped.
            # The salary covers the pay, so the register prints hours alone.
            # Requiring an amount lost the hours, and because the line carried
            # no money every AMOUNT total still added up, so validation saw
            # nothing. `dues_hours` is two of the three dues components.
            ("PTO", "Paid Time Off", "8.00", None, None),
        ],
        taxes=[("FITW", "Federal Income Tax", "200.00")],
        deductions=[("Union", "Union Dues", "45.00", False)],
        total_hours="8.00", total_earnings="1500.00",
        total_taxes="200.00", total_deductions="45.00",
    )
    top = check_block(
        p2, top,
        surname="Totals", given="For Page", emp_id="", base_rate=None,
        check_number=None, check_date="11/13/2025", net="3601.90",
        earnings=[("Reg", "Regular", "138.00", None, "4645.00")],
        taxes=[("FITW", "Federal Income Tax", "595.25")],
        deductions=[("Union", "Union Dues", "447.85", False)],
        total_hours="138.00", total_earnings="4645.00",
        total_taxes="595.25", total_deductions="447.85",
    )
    page_footer(p2, top)

    return write_pdf([p1, p2])
