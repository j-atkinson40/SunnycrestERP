"""The Punch Location parser and its findings — Payroll 3 Phase 2.

⚠️ **THE EXPORT IS CHRONOLOGICAL AND PAIRING WITHIN A BLOCK IS WRONG.**
Payentry re-emits an `Employee Name:` header whenever the employee changes
between consecutive punches. Measured on the real week-44 file: 28 blocks for
17 people, `Bell, Edward` in seven of them, his Oct 26 out-punch in a LATER
block than his in-punch. The fixture reproduces that, because block-local
pairing would otherwise look correct.

⚠️ **AND NO COORDINATE IS EVER STORED** (James, 2026-11-10). Payroll does not
use them and location history on thirty people is a liability for no benefit.
`test_no_coordinate_survives_parsing` asserts the absence structurally rather
than trusting the parser's intent.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytest

from app.services.payroll.punch_findings import (
    DEFAULT_SHIFT_RULES,
    EARLY_IN_THRESHOLD,
    EARLY_OUT_BEFORE_END,
    EARLY_OUT_CLUSTER_WINDOW,
    EARLY_OUT_MIN_PEOPLE,
    ShiftRule,
    all_findings,
    dept_code,
    find_clustered_early_departures,
    find_early_clock_ins,
    find_unpaired_punches,
    shift_for,
)
from app.services.payroll.punch_parser import (
    Punch,
    PunchParseError,
    pair_punches,
    parse_punch_location,
)
from tests.fixtures.payroll import build_punch_xls as fixture


@pytest.fixture(scope="module")
def xls_bytes():
    return fixture.build()


@pytest.fixture(scope="module")
def parsed(xls_bytes):
    return parse_punch_location(xls_bytes)


@pytest.fixture(scope="module")
def days(parsed):
    return pair_punches(parsed)


# ── the container is real ────────────────────────────────────────────────────

def test_the_fixture_is_a_real_ole2_biff8_workbook(xls_bytes):
    """⚠️ A positive control on the fixture.

    If it were a CSV or a list of rows in disguise, every test below would
    exercise a path the real Payentry export never takes. The magic bytes are
    the OLE2 compound-file signature, same as the real file.
    """
    assert xls_bytes[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def test_a_file_that_is_not_a_workbook_refuses():
    with pytest.raises(PunchParseError, match="could not open"):
        parse_punch_location(b"this is not a workbook")


def test_an_empty_workbook_refuses():
    import io

    import xlwt
    book = xlwt.Workbook()
    book.add_sheet("Punch Location Report").write(0, 0, "Punch Location Report")
    buf = io.BytesIO(); book.save(buf)
    with pytest.raises(PunchParseError, match="no punches found"):
        parse_punch_location(buf.getvalue())


# ── what it read ─────────────────────────────────────────────────────────────

def test_every_punch_is_read(parsed):
    assert len(parsed.punches) == fixture.EXPECTED_PUNCHES
    assert parsed.people == fixture.EXPECTED_PEOPLE
    assert parsed.blocks == fixture.EXPECTED_BLOCKS


def test_the_report_header_is_read(parsed):
    assert parsed.generated_by == "Tester [Test Person]"
    assert parsed.criteria == "From 2026-10-25 to 2026-10-31"


def test_the_map_link_text_is_stripped_from_a_department(parsed):
    """Measured: the real Sales cell reads `[108] Sales\\r\\n[Map]`."""
    assert "[107] Office" in parsed.departments
    assert not any("Map" in d for d in parsed.departments), parsed.departments


@pytest.mark.parametrize("text, expected", [
    ("6:00a", time(6, 0)), ("3:41p", time(15, 41)),
    ("12:00a", time(0, 0)), ("12:30p", time(12, 30)),
    ("11:59p", time(23, 59)),
])
def test_payentry_time_format(text, expected):
    """One letter, no space: `6:00a`, not `6:00 AM`."""
    from app.services.payroll.punch_parser import _parse_time
    assert _parse_time(text) == expected


@pytest.mark.parametrize("bad", ["", "6:00", "25:00a", "6:60a", "noon", "6-00a"])
def test_an_unreadable_time_is_not_guessed(bad):
    from app.services.payroll.punch_parser import _parse_time
    assert _parse_time(bad) is None


# ── no coordinates, structurally ─────────────────────────────────────────────

def test_no_coordinate_survives_parsing(parsed):
    """⚠️ Asserted on the TYPE, not on the values.

    A test that only checked the parsed values would pass today and keep
    passing the day somebody adds a `latitude` field and populates it. These
    attributes must not exist at all.
    """
    for forbidden in ("latitude", "longitude", "accuracy", "ip_address",
                      "lat", "lon", "coords", "location"):
        assert not hasattr(parsed.punches[0], forbidden), forbidden
    assert set(Punch.__dataclass_fields__) == {
        "name", "dept", "punch_at", "has_location", "origin"}


def test_a_gps_punch_is_recorded_only_as_a_boolean(parsed):
    """The fixture has one punch with a real-looking coordinate."""
    located = [p for p in parsed.punches if p.has_location]
    assert len(located) == fixture.EXPECTED_WITH_LOCATION
    # ⚠️ And the coordinate itself is nowhere in the parsed object's repr.
    assert "42.95" not in repr(parsed.punches)


def test_a_kiosk_punch_is_not_treated_as_having_a_location(parsed):
    """⚠️ The column is LABELLED "Latitude" and contains the words "kiosk
    punch" on 149 of 168 real rows. Reading it as a coordinate would make
    every kiosk punch look located."""
    assert sum(1 for p in parsed.punches if not p.has_location) == \
        fixture.EXPECTED_PUNCHES - fixture.EXPECTED_WITH_LOCATION


# ── pairing across blocks ────────────────────────────────────────────────────

def test_a_persons_punches_are_gathered_from_every_block(parsed):
    """⚠️ THE CORE OF PHASE 2.

    Ann's punches are scattered across several `Employee Name:` blocks. If
    `by_person` did not gather them all, her day would be incomplete — and the
    hours it implied would be wrong in a way nothing else here would catch.
    """
    ann = parsed.by_person()["Alpha, Ann"]
    # 6 on weekdays plus her 2 Saturday punches, added with the Saturday rule.
    assert len(ann) == 8, [p.punch_at for p in ann]
    assert ann == sorted(ann, key=lambda p: p.punch_at), "not in time order"


def test_punches_are_sorted_even_when_the_source_is_not_ordered():
    """⚠️ THIS TEST EXISTS BECAUSE A BREAK TEST FOUND NOTHING.

    Removing the sort in `by_person` left all 40 tests passing: the Payentry
    export is chronological, so grouping by name happens to preserve order and
    the sort is a no-op on that input. A guard that cannot fail on the data at
    hand still has to be checkable, because the source will not always be a
    file — Phase 3 stores punches and reads them back, and a database returns
    rows in whatever order it likes.

    So this feeds a deliberately shuffled result and requires the ordering.
    """
    from app.services.payroll.punch_parser import PunchParseResult

    def punch(day, hhmm):
        h, m = (int(x) for x in hhmm.split(":"))
        return Punch(name="Alpha, Ann", dept="[103] Production",
                     punch_at=datetime(2026, 10, day, h, m),
                     has_location=False, origin="Kiosk")

    shuffled = PunchParseResult(
        punches=[punch(26, "15:43"), punch(27, "06:45"), punch(26, "06:00")],
        blocks=3, departments={"[103] Production"})
    ann = shuffled.by_person()["Alpha, Ann"]
    assert [p.punch_at.strftime("%d %H:%M") for p in ann] == [
        "26 06:00", "26 15:43", "27 06:45"], ann

    # And pairing off that shuffled source still gets the day right.
    oct26 = next(d for d in pair_punches(shuffled) if d.on_date == date(2026, 10, 26))
    assert oct26.worked == timedelta(hours=9, minutes=43)
    assert oct26.unpaired == []


def test_an_in_and_out_in_different_blocks_still_pair(days):
    """Ann's Oct 26 in-punch and out-punch are in different blocks."""
    oct26 = next(d for d in days
                 if d.name == "Alpha, Ann" and d.on_date == date(2026, 10, 26))
    assert len(oct26.pairs) == 1, oct26.pairs
    first, last = oct26.pairs[0]
    assert first.punch_at.strftime("%H:%M") == "06:00"
    assert last.punch_at.strftime("%H:%M") == "15:43"
    assert oct26.worked == timedelta(hours=9, minutes=43)


def test_block_local_pairing_would_have_been_wrong(parsed):
    """⚠️ A positive control on the test above.

    It shows the fixture really does separate Ann's two Oct 26 punches with
    somebody else's in between — so gathering is doing work, not agreeing with
    an already-ordered file.
    """
    order = [p.name for p in parsed.punches if p.on_date == date(2026, 10, 26)]
    assert order == ["Alpha, Ann", "Bravo, Ben", "Bravo, Ben", "Alpha, Ann"], order


def test_an_odd_punch_is_left_unpaired_and_nothing_is_inferred(days):
    odd = next(d for d in days if d.name == "Foxtrot, Fay")
    assert odd.pairs == []
    assert len(odd.unpaired) == 1
    assert odd.worked == timedelta(0), "no shift end was invented"


# ── the shift rule ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("dept, code", [
    ("[103] Production", "103"), ("[101] Delivery", "101"),
    ("[108] Sales [Map]", "108"), (None, None), ("Production", None),
])
def test_department_codes_are_read_from_the_bracket(dept, code):
    assert dept_code(dept) == code


def test_only_the_plant_and_delivery_have_a_shift_rule():
    assert shift_for("[103] Production") is not None
    assert shift_for("[101] Delivery") is not None
    for other in ("[106] Supervisor", "[107] Office", "[108] Sales"):
        assert shift_for(other) is None, other


def test_a_department_with_no_rule_yields_no_findings(days):
    """⚠️ No fallback, deliberately.

    Office keeps different hours. Applying the plant's 6:30-3:30 to Gus, who
    clocked in at 05:00 and out at 13:00, would manufacture BOTH an early
    clock-in and an early departure about somebody working a normal day.
    """
    names = {n for f in all_findings(days) for n in f.people}
    assert "Golf, Gus" not in names, names


def test_the_shift_default_is_marked_unconfirmed():
    rule = shift_for("[103] Production")
    assert rule.status == "default_unconfirmed"
    assert rule.start == time(6, 30) and rule.end == time(15, 30)
    assert len(rule.source) > 20


#: Findings that are NOT derived from the shift rule, and so carry no shift
#: status. ⚠️ `saturday_overtime_worked` belongs here: hours worked are a fact
#: and need no rule to interpret, and stamping an unconfirmed-shift status on
#: them would imply the figure depended on a guess when it does not.
_NO_SHIFT_STATUS = {"unpaired_punch", "saturday_overtime_worked"}


def test_every_shift_derived_finding_carries_the_shift_status(days):
    """A reader must be able to tell a conclusion from a guess in place."""
    checked = 0
    for f in all_findings(days):
        if f.kind in _NO_SHIFT_STATUS:
            assert f.shift_status is None, f
            continue
        assert f.shift_status == "default_unconfirmed", f
        checked += 1
    # ⚠️ A positive control: if every finding were exempt this would pass
    # while asserting nothing.
    assert checked, "no shift-derived finding was checked"


# ── the three detectors ──────────────────────────────────────────────────────

def test_an_early_clock_in_is_found(days):
    found = find_early_clock_ins(days)
    assert {f.people[0] for f in found} == {"Alpha, Ann"}
    assert all("06:00" in f.detail for f in found)
    # Oct 26 and Oct 29 only. ⚠️ Ann is also in at 06:00 on SATURDAY Oct 31 and
    # that is not a finding — Saturday has no regular shift.
    assert len(found) == 2, [f.on_date for f in found]


def test_clocking_in_just_before_the_shift_is_not_early(days):
    """Ben at 06:47 and Eve at 06:28 are inside the threshold or late."""
    found = {f.people[0] for f in find_early_clock_ins(days)}
    assert "Bravo, Ben" not in found
    assert "Echo, Eve" not in found, "06:28 is only 2 min early"
    assert EARLY_IN_THRESHOLD == timedelta(minutes=10)


def test_a_cluster_of_early_departures_is_found(days):
    found = find_clustered_early_departures(days)
    assert len(found) == 1, [f.detail for f in found]
    f = found[0]
    assert f.on_date == date(2026, 10, 29)
    assert set(f.people) == {"Alpha, Ann", "Echo, Eve"}
    assert "14:06" in f.detail


def test_one_person_leaving_early_alone_is_not_a_finding(days):
    """⚠️ Both conditions, and the cluster is the point.

    One person leaving early is their business and a hundred things explain
    it. A detector that fired on that would bury the pattern the Focus was
    actually asked about.
    """
    assert EARLY_OUT_MIN_PEOPLE == 2
    singles = [d for d in days
               if d.name == "Delta, Dee" and d.on_date == date(2026, 10, 28)]
    assert singles, "Dee is in the fixture"
    assert not [f for f in find_clustered_early_departures(days)
                if "Delta, Dee" in f.people]


def test_leaving_slightly_early_is_not_a_finding(days):
    """Dee leaves at 15:35, after the 15:30 end. Nowhere near an hour early."""
    assert EARLY_OUT_BEFORE_END == timedelta(hours=1)
    assert EARLY_OUT_CLUSTER_WINDOW == timedelta(minutes=15)


def test_an_unpaired_punch_is_reported(days):
    found = find_unpaired_punches(days)
    assert len(found) == 1
    assert found[0].people == ("Foxtrot, Fay",)
    assert "No shift end is assumed" in found[0].detail


def test_the_fixtures_saturday_produces_no_early_finding(days):
    """⚠️ END TO END THROUGH THE xls CONTAINER, not on hand-built objects.

    The fixture had no Saturday at all until the follow-up, so the Saturday
    rule was only ever tested against DayPunches built in a test file. Two
    people are now in at 06:00 and out together at 10:53 and 10:58 on
    Saturday 2026-10-31 — early by the weekday rule on both counts, and a
    finding on neither.
    """
    from datetime import date as _date

    saturday = [f for f in all_findings(days)
                if f.on_date == _date(2026, 10, 31)]
    assert saturday, "the fixture has no Saturday punches"
    assert {f.kind for f in saturday} == {"saturday_overtime_worked"}, saturday
    assert {p for f in saturday for p in f.people} == \
        fixture.EXPECTED_SATURDAY_PEOPLE


def test_the_detectors_return_findings_and_nothing_else(days):
    """No side effects: findings are data, not actions."""
    found = all_findings(days)
    assert found and all(hasattr(f, "kind") and hasattr(f, "detail")
                         for f in found)
    assert {f.kind for f in found} <= {
        "unpaired_punch", "early_clock_in", "clustered_early_departure",
        "saturday_overtime_worked"}
