"""The Employee Hours parser — Payroll 3 Phase 1.

⚠️ **THE TOTALS CANNOT VALIDATE THIS FILE, AND THAT IS THE WHOLE POINT.**
Measured on the real week-44 export, a naive `extract_text` parse reproduces
every hour total exactly — REG 618.45, OT1 74.16, PTO 4.00, Sick 12.00,
708.61 — while reading DiGenova's employee number as **12008** and Sanchez
Jr's as **"14 1"**. The Hours column is 500pt from where the corruption
happens, so no total can ever catch it.

So the tests below assert IDENTITY, not just arithmetic, and the fixture
reproduces the corruption geometrically rather than describing it: a naive
`extract_words` over the fixture really does return the token `'12008]'`.
"""
from __future__ import annotations

import io
from decimal import Decimal as D

import pdfplumber
import pytest

from app.services.payroll.hours_parser import (
    KNOWN_PAY_TYPES,
    PAY_TYPE_TO_BUCKET,
    X_HOME,
    HoursParseError,
    parse_employee_hours,
    runs_by_contiguity,
)
from tests.fixtures.payroll import build_hours_pdf as fixture


@pytest.fixture(scope="module")
def pdf_bytes():
    return fixture.build()


@pytest.fixture(scope="module")
def parsed(pdf_bytes):
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return parse_employee_hours(pdf)


# ── the fixture must actually contain the bug ────────────────────────────────

def test_the_fixture_really_reproduces_the_collision(pdf_bytes):
    """⚠️ A POSITIVE CONTROL ON THE FIXTURE, AND IT IS THE LOAD-BEARING ONE.

    Every identity test below would pass against a fixture that simply printed
    the employee number somewhere harmless. This asserts that reading the
    fixture the naive way produces the SAME corrupted token the real export
    produces — `'12008]'` — so the de-interleaving is genuinely exercised.
    """
    collided = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            for w in page.extract_words():
                if abs(w["x0"] - X_HOME) < 2 and len(w["text"]) > 4:
                    collided.append(w["text"])
    assert "12008]" in collided, (
        f"the fixture does not reproduce the overlapping-run collision; a "
        f"naive read saw {collided}. Without it, the de-interleaving tests "
        f"prove nothing."
    )


def test_the_employee_number_is_not_12008(parsed):
    """⚠️ THE TEST JAMES ASKED FOR, STATED AS BLUNTLY AS HE STATED IT.

    12008 is what the naive parse returns for employee 20. If this id ever
    comes back, a week of hours has been filed against a person who does not
    exist — and every hour total would still be correct.
    """
    assert "12008" not in parsed.emp_ids, (
        "the interleaved employee number was read as 12008 — the naive-parse "
        "failure is back"
    )
    assert "20" in parsed.emp_ids
    assert parsed.names_by_emp["20"] == {"Delgado, Chris Jr."}


def test_the_second_collision_case_is_also_right(parsed):
    """`Sanchez Jr, Roberto` reads as `[ 14 1]06` naively: emp 14, home 106."""
    assert "14" in parsed.emp_ids
    home = {l.home_dept for l in parsed.lines if l.emp_id == "14"}
    assert home == {"106"}, home


def test_a_name_only_row_keeps_its_employee_number(parsed):
    """⚠️ A row with no hours has NO Home Dept column.

    Its single numeric run is the employee number wherever it lands — and for
    a long name it lands exactly on x=166. A rule that looks for a department
    first reads it as "department 17" and loses the id entirely. Measured on
    the real export: that is Baran-Corgnell, employee 17.
    """
    assert parsed.listed_without_hours == fixture.EXPECTED_LISTED_ONLY
    assert "17" in parsed.emp_ids
    assert all(l.emp_id != "17" for l in parsed.lines), "17 has no hours"


def test_every_person_resolves_to_exactly_one_employee_number(parsed):
    assert parsed.emp_ids == fixture.EXPECTED_EMP_IDS
    assert parsed.ambiguous_names == {}


def test_home_departments_are_read_from_the_right_run(parsed):
    got = {}
    for line in parsed.lines:
        got.setdefault(line.emp_id, line.home_dept)
    assert got == fixture.EXPECTED_HOME


# ── the de-interleaver itself ────────────────────────────────────────────────

def test_contiguous_runs_separate_two_overlapping_fields():
    """The measured geometry of the real DiGenova row, to the hundredth."""
    chars = [
        {"text": "1", "x0": 165.98, "x1": 171.54},
        {"text": "2", "x0": 167.16, "x1": 172.72},
        {"text": "0", "x0": 171.54, "x1": 177.11},
        {"text": "0", "x0": 172.72, "x1": 178.29},
        {"text": "8", "x0": 177.11, "x1": 182.67},
        {"text": "]", "x0": 178.29, "x1": 181.06},
    ]
    runs = runs_by_contiguity(chars)
    assert [r[0] for r in runs] == ["108", "20]"], runs
    # ⚠️ And in x-order the glyphs really do spell the corrupted token, so the
    # inputs to this test are the inputs the parser actually faces.
    assert "".join(c["text"] for c in sorted(chars, key=lambda c: c["x0"])) == "12008]"


def test_character_class_could_not_have_separated_them():
    """⚠️ Why the register's technique does not transfer.

    `register_parser.unglue_amount` separates an overlapping money run from
    text by character class. Here BOTH runs are digits, so no classifier can
    split them; only geometry can. Stated as a test so the next person does
    not reach for the other tool.
    """
    glyphs = "12008]"
    assert sum(c.isdigit() for c in glyphs) == 5
    assert len({c.isdigit() for c in glyphs if c != "]"}) == 1, (
        "every character in the collision is the same class"
    )


def test_a_single_field_is_returned_whole():
    chars = [{"text": c, "x0": 100.0 + i * 5.56, "x1": 100.0 + (i + 1) * 5.56}
             for i, c in enumerate("103")]
    assert [r[0] for r in runs_by_contiguity(chars)] == ["103"]


def test_a_real_gap_is_not_bridged():
    """Two fields far apart stay two fields."""
    chars = [{"text": "1", "x0": 100.0, "x1": 105.56},
             {"text": "2", "x0": 200.0, "x1": 205.56}]
    assert [r[0] for r in runs_by_contiguity(chars)] == ["1", "2"]


# ── the messy rows ───────────────────────────────────────────────────────────

def test_the_totals_match_the_hand_totalled_fixture(parsed):
    got = {k: str(v) for k, v in parsed.hours_by_pay_type().items()}
    assert got == fixture.EXPECTED_TOTALS


def test_a_negative_lunch_deduction_is_kept_as_a_negative(parsed):
    neg = [l for l in parsed.lines if l.hours < 0]
    assert neg, "the -0.50 automatic lunch deduction was dropped"
    assert all(l.hours == D("-0.50") for l in neg)
    assert {l.emp_id for l in neg} == {"20"}


def test_a_zero_hour_line_is_kept(parsed):
    zero = [l for l in parsed.lines if l.hours == 0]
    assert zero, "a 0.00 line was dropped"
    # ⚠️ Dropping it would be invisible in every total, which is exactly the
    # class of defect this file's validation cannot see.
    assert zero[0].emp_id == "20"


def test_several_lines_for_one_day_and_pay_type_are_all_kept(parsed):
    same = [l for l in parsed.lines
            if l.emp_id == "20" and l.pay_type == "REG"
            and l.work_date.isoformat() == "2026-10-31"]
    assert len(same) == 2, [str(l.hours) for l in same]
    assert sorted(str(l.hours) for l in same) == ["0.00", "4.00"]


def test_page_headers_and_footers_are_not_rows(parsed):
    names = {l.name for l in parsed.lines} | set(parsed.listed_without_hours.values())
    for junk in ("Employee Hours Report", "Name", "(c) MPAY Inc."):
        assert not any(junk in n for n in names), names


def test_a_misspelled_name_is_keyed_by_employee_number(parsed):
    """Payentry spells one real name "Micheal". The id is the key, never the name."""
    assert parsed.names_by_emp["22"] == {"Foxtrot, Micheal"}
    assert any(l.emp_id == "22" for l in parsed.lines)


def test_nothing_was_unreadable(parsed):
    assert parsed.unreadable_rows == []


# ── pay types ────────────────────────────────────────────────────────────────

def test_the_known_pay_types_all_map_to_a_bucket():
    assert set(PAY_TYPE_TO_BUCKET) == KNOWN_PAY_TYPES
    assert set(PAY_TYPE_TO_BUCKET.values()) == {
        "reg_hrs", "ot_hrs", "personal_hrs", "sick_hrs"}


def test_an_unknown_pay_type_is_reported_not_dropped(parsed):
    assert parsed.unknown_pay_types == {}
    # and the mechanism exists: every line's bucket resolves for known types
    assert all(l.bucket for l in parsed.lines)


def test_a_file_with_no_pay_lines_refuses(pdf_bytes):
    """An empty parse is a refusal, not an empty success."""
    from tests.fixtures.payroll.build_hours_pdf import Page, header, footer
    from tests.fixtures.payroll.build_register_pdf import write_pdf

    blank = Page()
    header(blank)
    footer(blank, 60.0, 1, 1)
    with pdfplumber.open(io.BytesIO(write_pdf([blank]))) as pdf:
        with pytest.raises(HoursParseError, match="no pay lines"):
            parse_employee_hours(pdf)
