"""The register parser, against an anonymised fixture with the real geometry.

Every case here is one that the real file actually contains and that an earlier
version of the parser got wrong. The fixture reproduces the page geometry
rather than the words alone, so these tests exercise the parser's real
mechanism — x-band column location, row clustering, character-position
splitting — and not a convenient stand-in for it.

⚠️ **NO REAL EXPORT IS INVOLVED.** See `tests/fixtures/payroll/`.
"""
from __future__ import annotations

import io
from decimal import Decimal

import pdfplumber
import pytest

from app.services.payroll.register_parser import (
    CODE_AND_DESC_X,
    DUES_EXCLUDED_EARNING_CODES,
    KNOWN_DEDUCTION_CODES,
    KNOWN_EARNING_CODES,
    SENSITIVE_DEDUCTION_CODES,
    cluster_rows,
    parse_register,
    resolve_display_names,
    split_glued_tokens,
    unglue_amount,
    union_salary_anomalies,
    validate_check,
)
from tests.fixtures.payroll import register_fixture
from tests.fixtures.payroll.build_register_pdf import FOOTER_WORDS, X


@pytest.fixture(scope="module")
def parsed():
    with pdfplumber.open(io.BytesIO(register_fixture.build())) as pdf:
        return parse_register(pdf)


@pytest.fixture(scope="module")
def by_emp(parsed):
    return {c.emp_id: c for c in parsed.checks}


def lines(chk, kind):
    return {l.code: l for l in chk.lines if l.kind == kind}


# ── the fixture is a real register, not a hopeful one ────────────────────────

def test_the_fixture_and_the_parser_agree_about_the_columns():
    """⚠️ A positive control on the fixture itself.

    Everything else here would pass against a fixture that drew its columns
    somewhere the parser does not look — the parse would simply find nothing
    and the assertions would be about an empty result. This pins the fixture's
    x positions to the parser's own column constants.
    """
    assert [(X["earn_code"], X["earn_desc"]),
            (X["tax_code"], X["tax_desc"]),
            (X["ded_code"], X["ded_desc"])] == list(CODE_AND_DESC_X)


def test_every_check_parses_and_validates(parsed):
    assert len(parsed.checks) == register_fixture.EXPECTED_CHECKS
    assert parsed.failed == []
    assert {c.emp_id for c in parsed.checks} == register_fixture.EXPECTED_PEOPLE


def test_no_unknown_codes_and_nothing_left_glued(parsed):
    assert parsed.unknown_codes == {}
    assert parsed.unsplit_glued_tokens == 0


# ── the TOTAL block ──────────────────────────────────────────────────────────

def test_a_total_block_is_skipped_and_counted(parsed):
    """⚠️ Counted, not merely absent.

    The register prints page and company TOTAL blocks in the same three-column
    shape as a check, so block detection finds them. Asserting only that they
    are absent from `checks` would also pass if block detection stopped finding
    them at all — and then real checks would go missing the same silent way.
    """
    assert parsed.summary_blocks == register_fixture.EXPECTED_SUMMARY_BLOCKS
    assert all(c.check_number for c in parsed.checks)
    # Its grand total is far larger than any real check: proof the block was
    # seen and rejected rather than never produced.
    assert Decimal("4645.00") not in {c.printed_total_earnings for c in parsed.checks}


# ── the two glue faults ──────────────────────────────────────────────────────

def test_a_deduction_code_glued_to_its_description_is_split(by_emp):
    """`MedicalPTMedical` is one token on the page. It is two things."""
    ded = lines(by_emp["E02"], "deduction")
    assert "MedicalPT" in ded, f"got {sorted(ded)}"
    assert ded["MedicalPT"].description.startswith("Medical")
    assert ded["MedicalPT"].amount == Decimal("75.00")


def test_an_earning_code_glued_to_its_description_is_split(by_emp):
    earn = lines(by_emp["E02"], "earning")
    assert "HealthInsS" in earn, f"got {sorted(earn)}"
    assert earn["HealthInsS"].description.startswith("Health")


def test_the_splitter_leaves_a_label_that_merely_crosses_the_column_alone():
    """⚠️ The regression that reddened all 1,275 checks.

    `Earnings` in the printed `Total Earnings` label starts mid-column and
    reaches past the description x. Splitting on "crosses the boundary" cut it
    to `Earn` + `ings`, every printed total then read as None, and the failure
    reason named neither the cause nor the column. Only a token that BEGINS at
    a code column may be split.
    """
    word = {"text": "Earnings", "x0": 97.0, "x1": 130.0, "top": 10.0}
    out, unsplit = split_glued_tokens([word], chars=[])
    assert out == [word]
    assert unsplit == 0, "a token that does not start at a code column is not a candidate"


def test_a_glued_token_whose_characters_do_not_reconstruct_it_is_counted():
    """Left whole and counted, never split on a guess."""
    word = {"text": "MedicalPTMedical", "x0": 530.0, "x1": 593.0, "top": 10.0}
    out, unsplit = split_glued_tokens([word], chars=[])      # no chars at all
    assert out == [word]
    assert unsplit == 1


# ── the negative deduction ───────────────────────────────────────────────────

def test_a_negative_deduction_is_stored_negative(by_emp):
    """⚠️ Payentry draws a negative deduction OVER its own description.

    pdfplumber returns the two glyph runs as one interleaved token. Dropping
    the line would understate the deduction total by exactly that amount, and
    only the printed total would disagree.
    """
    ded = lines(by_emp["E02"], "deduction")
    assert ded["CellReimb"].amount == Decimal("-20.00")
    assert ded["CellReimb"].amount < 0, "a reimbursement is stored as a negative, not an absolute"


@pytest.mark.parametrize("token, text, value", [
    ("Reimburs-1em9.e0n4t", "Reimbursement", Decimal("-19.04")),
    ("Reimbursem-2e5n7t.07", "Reimbursement", Decimal("-257.07")),
    ("Reimbursement", "Reimbursement", None),
    ("-19.04", "-19.04", None),
])
def test_unglue_amount_recovers_both_runs(token, text, value):
    """The exact tokens measured on the real register."""
    assert unglue_amount(token) == (text, value)


# ── the name ─────────────────────────────────────────────────────────────────

def test_one_display_name_per_employee_and_none_ambiguous(parsed):
    assert parsed.display_names == register_fixture.EXPECTED_DISPLAY_NAMES
    assert parsed.ambiguous_names == {}


def test_the_footer_words_are_separate_tokens_in_the_fixture(parsed):
    """⚠️ A positive control on the test below.

    The footer test searches a name for the fixture's footer words. If Courier
    runs those words together — which it did, into
    `SunnyLcarnedsstcIanpcing` — the search is for text that is not on the
    page, and the test passes with the name bug fully reintroduced. This
    asserts the fixture really emits them as findable tokens, by checking they
    survive into the one place a footer can still reach: a name read without
    the stopping rule.
    """
    import io as _io

    import pdfplumber as _pdfplumber

    from app.services.payroll.register_parser import _band, cluster_rows, BAND_PERSON
    with _pdfplumber.open(_io.BytesIO(register_fixture.build())) as pdf:
        last = pdf.pages[-1]
        tokens = {w["text"] for row in cluster_rows(last.extract_words())
                  for w in _band(row, BAND_PERSON)}
    missing = [w for w in FOOTER_WORDS if w not in tokens]
    assert not missing, f"the fixture does not emit these as tokens: {missing}"


def test_the_page_footer_does_not_become_part_of_a_name(parsed):
    """⚠️ The fixture puts a footer under the last check of each page.

    That footer is why 30 employees once read back as 72 people. A name that
    picked it up would contain a word from it.
    """
    for chk in parsed.checks:
        for word in FOOTER_WORDS:
            assert word not in chk.person, \
                f"{chk.emp_id} name carries footer text: {chk.person!r}"


def test_every_name_is_shaped_like_a_name(parsed):
    """⚠️ A second, independent guard on the same claim.

    The footer test can only catch text it knows to look for. This one says
    what a name IS — `Surname, Given` and nothing else — so anything the left
    band picks up by accident fails here even if it is not a footer word. It
    is what would have caught `Alpha, Ann A Rate 25.0000`.
    """
    import re
    for chk in parsed.checks:
        assert re.fullmatch(r"[A-Za-z'\-]+, [A-Za-z'\-]+(?: [A-Za-z])?", chk.person), \
            f"{chk.emp_id} name is not shaped like a name: {chk.person!r}"


def test_a_second_name_is_reported_and_never_merged():
    """A real name change must surface as a list, not be absorbed.

    The frequency winner is what the import shows; both candidates stay
    visible, because only a person can tell a parse fault from a marriage.
    """
    class C:
        def __init__(self, emp_id, person): self.emp_id, self.person = emp_id, person
    checks = [C("E01", "Alpha, Ann A")] * 3 + [C("E01", "Zulu, Ann A")]
    display, candidates = resolve_display_names(checks)
    assert display["E01"] == "Alpha, Ann A"
    assert candidates["E01"] == {"Alpha, Ann A": 3, "Zulu, Ann A": 1}


def test_the_chosen_name_does_not_depend_on_page_order():
    class C:
        def __init__(self, emp_id, person): self.emp_id, self.person = emp_id, person
    a = [C("E01", "Alpha, Ann A"), C("E01", "Zulu, Ann A")]
    assert resolve_display_names(a)[0] == resolve_display_names(list(reversed(a)))[0]


# ── Sal, and the anomaly ─────────────────────────────────────────────────────

def test_sal_is_a_known_code_and_is_not_dues_wage_or_hours():
    assert "Sal" in KNOWN_EARNING_CODES
    assert "Sal" in DUES_EXCLUDED_EARNING_CODES
    # Settled by the accountant on 2026-11-03.
    assert "Sick" in DUES_EXCLUDED_EARNING_CODES


def test_a_check_with_both_union_and_sal_is_reported_as_an_anomaly(parsed, by_emp):
    """Union members are hourly, so both on one check is a contradiction.

    Reported for a person to resolve in Payentry — never reconciled in code.
    """
    anomalies = union_salary_anomalies(parsed.checks)
    assert [c.emp_id for c in anomalies] == ["E04"]
    assert "Sal" in lines(by_emp["E04"], "earning")
    assert "Union" in lines(by_emp["E04"], "deduction")


def test_the_anomaly_check_finds_nothing_when_there_is_nothing(by_emp):
    """Positive control: it is not simply returning everything."""
    assert union_salary_anomalies([by_emp["E01"]]) == []


# ── dues reach, and the sensitive codes ──────────────────────────────────────

def test_union_members_are_counted_by_employee_id(parsed):
    assert parsed.union_people == register_fixture.EXPECTED_UNION_PEOPLE


def test_the_sensitive_codes_are_named_and_parsed_as_lines(by_emp):
    """⚠️ Sensitive means restricted at the SURFACE, not missing from the data.

    Child support and garnishment are real deductions on a real check and the
    register must import them, or the deduction total will not add up. What
    they must never do is leave the payroll area or appear in a summary — held
    by `test_sensitive_deduction_codes.py`.
    """
    assert SENSITIVE_DEDUCTION_CODES == {"ChSup1", "Garn"}
    assert SENSITIVE_DEDUCTION_CODES <= KNOWN_DEDUCTION_CODES
    ded = lines(by_emp["E03"], "deduction")
    assert ded["ChSup1"].amount == Decimal("150.00")
    assert ded["Garn"].amount == Decimal("80.00")


# ── validation is the thing that caught all of the above ─────────────────────

def test_validation_rejects_a_check_whose_lines_do_not_match_its_total(by_emp):
    """⚠️ A positive control on validation itself.

    Every other test here rests on `failed == []` meaning something. Break one
    check and validation must say so, naming the disagreement.
    """
    import copy
    chk = copy.deepcopy(by_emp["E01"])
    assert validate_check(chk) is None
    chk.lines = [l for l in chk.lines if l.code != "Sick"]
    why = validate_check(chk)
    assert why is not None and "earnings sum" in why, why


def test_rows_are_clustered_not_bucketed():
    """Two words half a point apart are one row, however the boundary falls."""
    words = [{"text": "a", "x0": 10.0, "top": 6.9}, {"text": "b", "x0": 20.0, "top": 7.1}]
    assert len(cluster_rows(words)) == 1
    far = [{"text": "a", "x0": 10.0, "top": 6.9}, {"text": "b", "x0": 20.0, "top": 20.0}]
    assert len(cluster_rows(far)) == 2


def test_idempotency_keys_are_distinct_per_check(parsed):
    keys = [c.idempotency_key for c in parsed.checks]
    assert len(set(keys)) == len(keys)


# ── hours with no money, and the validation hole that hid them ───────────────
#
# ⚠️ **FOUND AFTER THE PR WAS GREEN, WHICH IS THE POINT OF THE STORY.** The
# register prints earning lines carrying HOURS AND NO AMOUNT — a `Vac`, `PTO`,
# `Sick` or `Reg` line for salaried staff whose pay the salary already covers.
# Measured: 36 such lines across 29 checks in the year, for 4 salaried
# employees. The parser required an amount, so it dropped them and lost their
# hours.
#
# `validate_check` did not notice, and could not: it compared earnings AMOUNTS
# against the printed earnings total and deduction amounts against theirs.
# The dropped lines carried no money, so every amount still balanced to the
# cent. 1,275 of 1,275 checks "validated" with 36 lines missing.
#
# Hours are not a lesser fact than money here. `dues_hours` is the divisor in
# dues component b and the multiplier in component c, so an hour that goes
# missing understates somebody's dues twice over. None of the 29 checks carries
# union dues, so no dues figure actually moved — but that is luck about who
# happens to be salaried, not a property of the parse.


def test_an_earning_line_with_hours_and_no_amount_is_kept(by_emp):
    """E04 carries `PTO 8.00` with no money beside it."""
    earn = lines(by_emp["E04"], "earning")
    assert "PTO" in earn, f"the hours-only line was dropped; got {sorted(earn)}"
    assert earn["PTO"].hours == Decimal("8.00")
    assert earn["PTO"].amount == Decimal("0.00"), (
        "an hours-only line is stored at zero, not None — a null amount would "
        "break every sum that touches it"
    )


def test_the_hours_only_line_does_not_disturb_the_earnings_total(by_emp):
    """Zero is the right amount: the printed earnings total excludes it."""
    chk = by_emp["E04"]
    assert chk.sum_of("earning") == chk.printed_total_earnings == Decimal("1500.00")


def test_line_hours_are_validated_against_the_printed_total(parsed):
    """⚠️ THE CHECK THAT WAS MISSING.

    Comparing only amounts cannot see a line that carries no money. This
    compares hours, which is the only thing that can.
    """
    for chk in parsed.checks:
        if chk.printed_total_hours is None:
            continue
        got = sum((l.hours or Decimal("0") for l in chk.lines
                   if l.kind == "earning"), Decimal("0"))
        assert got == chk.printed_total_hours, (
            f"{chk.emp_id} chk {chk.check_number}: line hours {got} != printed "
            f"{chk.printed_total_hours}"
        )


def test_validation_rejects_a_check_whose_HOURS_do_not_match(by_emp):
    """⚠️ A positive control on the new rule.

    `test_line_hours_are_validated_against_the_printed_total` would pass
    against a `validate_check` that ignored hours entirely — it recomputes the
    comparison itself rather than exercising the validator. So this drops the
    hours-only line and requires the VALIDATOR to object, and to say hours.
    """
    import copy
    chk = copy.deepcopy(by_emp["E04"])
    assert validate_check(chk) is None
    chk.lines = [l for l in chk.lines if l.code != "PTO"]
    # ⚠️ Every AMOUNT still balances — which is exactly why this went unseen.
    assert chk.sum_of("earning") == chk.printed_total_earnings
    why = validate_check(chk)
    assert why is not None, (
        "dropping an hours-only line left validation silent, which is the "
        "original defect"
    )
    assert "hours" in why, why
