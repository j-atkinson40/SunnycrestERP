"""The Cemetery Pane's rules. No database, no network, no model.

James's dispatch of 2026-10-26, slice 1.

⚠️ WHAT EACH TEST WOULD CATCH IS NAMED ON IT, because most of this pane's behaviour on
real data is an ABSENCE — no Directions action, no essentials, no People tab — and an
absence is satisfied by a pane that renders nothing at all. Every absence test here sits
beside a positive control.

⚠️ AND THE ABSENCES ARE NOT HYPOTHETICAL. Measured on production 2026-10-26: four
cemetery rows platform-wide, with `address`, `phone`, `contact_name`, `access_notes`,
`equipment_note`, `county`, `zip_code` and lat/long NULL on every one. So the empty
branch is the COMMON path here, not the edge case, which is the argument for testing it
first rather than last.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.services.order_list.cemetery import (
    NOTHING_RECORDED,
    _directions,
    _name_key,
    _row_for_pane,
    essentials,
    meta_line,
    what_opas_knows,
)
from app.services.capture.prefix_resolve import reaches
from app.services.capture.towns import town_before, town_leading
from app.services.order_list.stage import OrderFacts
from app.services.party_resolver import normalize as _pn

#: Monday. Oct 28 is ahead of it; Oct 16 is behind.
TODAY = date(2026, 10, 26)


def _order(**kw) -> OrderFacts:
    base = dict(
        id=kw.pop("id", "o1"),
        number=kw.pop("number", "SO-2026-0001"),
        deceased_name=kw.pop("deceased_name", "smith"),
        funeral_home=kw.pop("funeral_home", "Hopkins Funeral Home"),
        total=kw.pop("total", Decimal("1000")),
    )
    base.update(kw)
    return OrderFacts(**base)


# ── the meta line ─────────────────────────────────────────────────────────────


def test_the_town_is_the_meta_line():
    assert meta_line({"city": "Skaneateles", "state": "NY"}) == "Skaneateles, NY"
    assert meta_line({"city": "Skaneateles"}) == "Skaneateles"


def test_a_state_with_no_town_is_not_a_place():
    """⚠️ THE DISPATCH SAYS "town always shown" AND THE COLUMN IS NULLABLE.

    `cemeteries.city` can be NULL — it happens to be populated on all four rows that
    exist today, which is exactly the sort of fact that stops being true the first time
    somebody adds a cemetery by name alone. ", NY" on its own reads as a broken template.
    """
    assert meta_line({"state": "NY"}) is None
    assert meta_line({}) is None
    # The control: a town alone does render.
    assert meta_line({"city": "Auburn"}) == "Auburn"


# ── the one action ────────────────────────────────────────────────────────────


def test_directions_are_absent_without_an_address():
    """⚠️ THE PRODUCTION CASE FOR ALL FOUR CEMETERIES. `address` is NULL on every one, so
    this action never appears today.

    ⚠️ AND THE TEMPTING WRONG ANSWER IS A NAME-AND-TOWN SEARCH. "St. Mary's Cemetery,
    Skaneateles" would open a maps query that usually works — a guess dressed as a
    record, and the once it is wrong it sends a driver with a vault on the truck to the
    wrong gate. Lat/long would be the honest fallback and is also empty, 0 of 4.
    """
    assert _directions({"address": None, "city": "Skaneateles", "state": "NY"}) is None
    assert _directions({"address": "   ", "city": "Skaneateles"}) is None
    assert _directions({}) is None


def test_directions_use_the_whole_address_when_there_is_one():
    got = _directions({
        "address": "22 Fennell St", "city": "Skaneateles",
        "state": "NY", "zip_code": "13152",
    })
    assert got is not None
    assert got["kind"] == "directions"
    assert got["label"] == "Directions"
    # ⚠️ URL-ENCODED, AND THE COMMA MATTERS. A raw comma in a query string is legal and
    # a raw space is not; building this by f-string is how a maps link silently 400s.
    assert got["url"] == (
        "https://www.google.com/maps/search/?api=1"
        "&query=22+Fennell+St%2C+Skaneateles%2C+NY%2C+13152"
    )


# ── the essentials ────────────────────────────────────────────────────────────


def test_nothing_recorded_is_the_production_case():
    """All four cemeteries today. The caller renders `NOTHING_RECORDED` for this."""
    assert essentials({
        "address": None, "access_notes": None, "contact_name": None, "phone": None,
        "equipment_note": None,
        "cemetery_provides_lowering_device": False,
        "cemetery_provides_grass": False,
        "cemetery_provides_tent": False,
        "cemetery_provides_chairs": False,
    }) == []


def test_a_false_equipment_flag_says_nothing_at_all():
    """⚠️ CLAUDE.md §5, AND THE COLUMNS MAKE IT UNAVOIDABLE. All four
    `cemetery_provides_*` are `nullable=False, default=False`, so `False` cannot be told
    apart from "nobody said". Rendering "Tents: not provided" off a default would be the
    platform asserting something no one measured.

    ⚠️ THE TELL THAT THIS IS ENFORCED STRUCTURALLY RATHER THAN BY CARE: there is no
    "not provided" string anywhere in the module, so the sentence cannot be emitted by
    accident. This test pins the behaviour; `grep` pins the mechanism.
    """
    all_false = {
        "cemetery_provides_lowering_device": False,
        "cemetery_provides_grass": False,
        "cemetery_provides_tent": False,
        "cemetery_provides_chairs": False,
    }
    assert essentials(all_false) == []
    # The control: a TRUE is a measurement and does speak. Production has exactly one
    # such row — testco's St. Mary's, with three of the four set.
    assert essentials({**all_false, "cemetery_provides_tent": True}) == [
        {"label": "Cemetery provides", "value": "Tent"},
    ]
    assert essentials({
        "cemetery_provides_lowering_device": True,
        "cemetery_provides_grass": True,
        "cemetery_provides_tent": True,
        "cemetery_provides_chairs": False,
    }) == [{"label": "Cemetery provides", "value": "Lowering device, Grass, Tent"}]


def test_every_essential_is_optional_and_the_order_is_the_prototype_s():
    got = essentials({
        "address": "22 Fennell St", "city": "Skaneateles", "state": "NY",
        "access_notes": "Back in. Do not use the main lane.",
        "contact_name": "Paul Rinaldi", "phone": "(315) 555-0177",
        "equipment_note": "Lowering device allowed",
        "cemetery_provides_tent": True,
    })
    assert [row["label"] for row in got] == [
        "Address", "Getting in", "Contact", "Cemetery provides", "Equipment",
    ]
    assert got[0]["value"] == "22 Fennell St, Skaneateles, NY"
    assert got[2]["value"] == "Paul Rinaldi · (315) 555-0177"
    # Each part of the contact alone, and never a stray separator.
    assert essentials({"contact_name": "Paul Rinaldi"})[0]["value"] == "Paul Rinaldi"
    assert essentials({"phone": "(315) 555-0177"})[0]["value"] == "(315) 555-0177"
    for row in got:
        assert row["value"].strip() == row["value"]
        assert "·  ·" not in row["value"] and not row["value"].endswith("·")


def test_getting_in_carries_the_one_column_there_is():
    """⚠️ THE PROTOTYPE HAS `gate` AND `approach`; THE SCHEMA HAS `access_notes`.

    Two labels over one column would be the platform inventing a distinction its record
    does not make — and whichever of the two got the value, the other would render empty
    or repeat it.
    """
    got = essentials({"access_notes": "Service road gate on Fennell St. Back in."})
    assert got == [{
        "label": "Getting in",
        "value": "Service road gate on Fennell St. Back in.",
    }]


# ── name matching ─────────────────────────────────────────────────────────────


def test_punctuation_and_case_do_not_change_a_name():
    assert _name_key("St. Mary's Cemetery") == _name_key("St Marys Cemetery")
    assert _name_key("St. Mary's Cemetery") == _name_key("stmaryscemetery")
    assert _name_key("Oakwood Cemetery") != _name_key("Oakwood Memorial")


def test_the_town_is_read_word_wise_not_as_a_substring():
    """⚠️ A TOWN CAN APPEAR INSIDE THE CEMETERY'S OWN NAME. "Auburn Memorial Cemetery"
    in Auburn would have its first word sliced out by a substring cut, leaving "memorial
    cemetery" — which then matches the wrong row or nothing at all.

    ⚠️ THIS TEST USED TO EXERCISE `cemetery._strip_town`, WHICH NO LONGER EXISTS. James's
    ruling of 2026-10-29 — *"one town pattern shared by both surfaces, not a copy"* —
    moved the pane onto `capture.towns`, and `_strip_town` became a helper nothing
    called, with five assertions still on it. A tested artifact with no wiring is a check
    that cannot fail for the reason it names, so the helper was deleted and its
    protections re-pointed at the functions the pane actually runs.

    ⚠️ AND THE SHARED FUNCTIONS ARE STRICTER THAN THE HELPER THEY REPLACE. `_strip_town`
    compared squeezed keys word-wise, which was right; the PASS that called it tested
    `key.endswith(_name_key(city))`, which was a squeezed-string suffix and matched
    inside a word. Both ends are whole-run now.
    """
    known = frozenset({_pn("Skaneateles"), _pn("Auburn")})

    # The town trails the name — `town_before` finds it and hands back where it starts,
    # so the caller keeps "st marys".
    assert town_before("st marys skaneateles", known) == ("skaneateles", 9)
    assert town_before("st mary's skaneateles", known) == ("skaneateles", 10)

    # The town LEADS the name — the case James ruled in. `town_leading` hands back where
    # it ends, so the caller keeps "st marys".
    assert town_leading("skaneateles st marys", known) == ("skaneateles", 11)

    # ⚠️ "Auburn" opens the cemetery's OWN name. The leading read finds it, which is
    # correct and harmless — the remainder still has to `reaches` the same row. What must
    # not happen is the MIDDLE being cut, and neither function can do that: each only
    # ever reports a run at one edge.
    assert town_before("auburn memorial cemetery", known) is None
    assert town_leading("auburn memorial cemetery", known) == ("auburn", 6)

    # A town nobody holds records for is not a town. This is what stops "hopkins st
    # marys" reading "hopkins" as a town, and it is why both functions are strict.
    assert town_leading("hopkins st marys", known) is None
    assert town_before("st marys hopkins", known) is None

    # ⚠️ THE LONGEST RUN WINS, AND MOST TWO-WORD TOWNS CANNOT TEST THAT EITHER. The first
    # attempt here used {"new hartford", "hartford"} against "new hartford st marys" and
    # was NOT a break test: the short leading window is "new", which is not a known town,
    # so reversing the walk order lands on the same answer and the break stayed green.
    #
    # The discriminator needs a town that is a WORD-PREFIX of a longer town, so that both
    # the short and the long window are known and the walk order decides which wins.
    # ⚠️ AND THE TWO FUNCTIONS NEED DIFFERENT NESTED PAIRS, which the first version of
    # this test got wrong in a way that left `town_before` unguarded. `town_leading`
    # grows its window from the LEFT, so its short window is a word-PREFIX; `town_before`
    # grows from the RIGHT, so its short window is a word-SUFFIX. One set cannot
    # discriminate both: reversing `town_before`'s walk order against `nested_prefix`
    # stayed green, because "heights" alone is not a known town there.
    nested_prefix = frozenset({_pn("Hartford"), _pn("Hartford Heights")})
    assert town_leading("hartford heights st marys", nested_prefix) == ("hartford heights", 16)

    nested_suffix = frozenset({_pn("Heights"), _pn("Hartford Heights")})
    assert town_before("st marys hartford heights", nested_suffix) == ("hartford heights", 9)

    # No text, no town — the guard the pane relies on for rows with a blank city.
    assert town_before("", known) is None
    assert town_leading("", known) is None
    assert town_leading("skaneateles st marys", frozenset()) is None

    # ⚠️ AND THIS IS THE ASSERTION THAT ACTUALLY STOPS A BARE TOWN OPENING THE PANE,
    # which is not where it looks like it lives. The pane guards the empty remainder with
    # `if rest.strip() and reaches(...)`, and that guard is DEFENSIVE, NOT LOAD-BEARING:
    # breaking it leaves every test green, because `reaches` already returns None for an
    # empty needle and the pane strips the argument too. `reaches(name, " ")` returns a
    # position, though — so the pane's guard is one missing `.strip()` away from being
    # the only thing standing there, and it is kept for that reason rather than deleted.
    assert reaches("St. Mary's Cemetery", "", interior=True) is None


# ── the rows ──────────────────────────────────────────────────────────────────


def test_the_row_names_the_funeral_home_and_not_the_cemetery():
    """⚠️ THE MIRROR OF THE CUSTOMER PANE'S ROW, and for the same reason. We are inside
    the cemetery's pane, so its own name on every row is the blank-label problem in a
    different key; the funeral home is what the office cannot see from here.
    """
    row = _row_for_pane(
        _order(cemetery="St. Mary's Cemetery", customer_id="c1",
               service_date=date(2026, 10, 28)),
        TODAY,
    )
    assert row["funeral_home"] == "Hopkins Funeral Home"
    assert row["customer_id"] == "c1"
    assert "St. Mary's" not in str(row)


def test_a_row_with_no_customer_record_carries_no_id_to_link_with():
    """The LEFT JOIN tolerates an order with no customer row, so this must. The client
    renders plain text rather than a button that cannot resolve."""
    row = _row_for_pane(_order(customer_id=None), TODAY)
    assert "customer_id" not in row
    assert row["funeral_home"] == "Hopkins Funeral Home"
    # The control: given an id, it travels.
    assert "customer_id" in _row_for_pane(_order(customer_id="c1"), TODAY)


def test_the_status_comes_from_the_shared_rule():
    """⚠️ ONE SOURCE SINCE 2026-10-23, when a ladder rung called "scheduled" was printing
    on drafts. A pane with its own status vocabulary reintroduces exactly that drift one
    surface over."""
    assert _row_for_pane(_order(status="draft"), TODAY)["status"] == "Draft"
    assert _row_for_pane(_order(status="cancelled"), TODAY)["status"] == "Cancelled"
    assert _row_for_pane(_order(status="confirmed"), TODAY)["status"] == "Confirmed"


# ── what Opas knows ───────────────────────────────────────────────────────────


def test_deliveries_this_year_counts_delivered_in_the_current_year():
    mine = [
        _order(id="a", status="delivered", service_date=date(2026, 8, 6)),
        _order(id="b", status="completed", service_date=date(2026, 8, 20)),
        # ⚠️ LAST YEAR, so it is not "this year" however delivered it is.
        _order(id="c", status="delivered", service_date=date(2025, 12, 1)),
        # Not delivered.
        _order(id="d", status="confirmed", service_date=date(2026, 10, 28)),
    ]
    got = what_opas_knows(mine, TODAY, None)
    assert got["deliveries_this_year"] == 2, "delivered + completed, 2026 only"
    assert got["year"] == 2026


def test_completed_counts_as_delivered_because_the_shared_property_says_so():
    """⚠️ `OrderFacts.delivered` IS TRUE FOR `completed`, AND THE DATA HAS BOTH. Measured
    on production: testco's St. Mary's holds 2 `delivered` and 2 `completed`. Counting
    only the literal status would report half the deliveries and look plausible.
    """
    assert what_opas_knows(
        [_order(status="completed", service_date=date(2026, 7, 24))], TODAY, None,
    )["deliveries_this_year"] == 1


def test_the_next_delivery_is_the_soonest_upcoming_and_absent_when_there_is_none():
    mine = [
        _order(id="a", status="confirmed", service_date=date(2026, 11, 20)),
        _order(id="b", status="confirmed", service_date=date(2026, 10, 28),
               deceased_name="hart"),
        # ⚠️ CANCELLED IS NOT UPCOMING. An order the home cancelled is not a delivery
        # anybody is expecting, and it would otherwise win on date.
        _order(id="c", status="cancelled", service_date=date(2026, 10, 27)),
        # Past: not upcoming either.
        _order(id="d", status="confirmed", service_date=date(2026, 10, 16)),
    ]
    got = what_opas_knows(mine, TODAY, None)
    assert got["next_delivery"]["order_id"] == "b"
    assert "hart" in got["next_delivery"]["line"]
    # The absence, with its control above.
    assert "next_delivery" not in what_opas_knows(
        [_order(status="delivered", service_date=date(2026, 8, 6))], TODAY, None,
    )


def test_same_name_rides_along_only_when_there_is_one():
    same = {"cemetery_id": "m2", "name": "St. Mary's Cemetery", "town": "Auburn",
            "line": "not the St. Mary's Cemetery in Auburn"}
    assert what_opas_knows([], TODAY, same)["same_name"] == same
    assert "same_name" not in what_opas_knows([], TODAY, None)


def test_the_counts_say_nothing_about_what_is_not_recorded():
    """⚠️ THE DISPATCH'S OWN LIMIT: "Leave out what can't be counted." The prototype's
    `Also called` needs an alias list the schema does not have, and its "when someone
    says just St. Mary's" line is a claim about Opas rather than about the cemetery.
    Neither is here, and this test is what stops one being added back by eye.
    """
    got = what_opas_knows([_order(status="delivered", service_date=date(2026, 8, 6))],
                          TODAY, None)
    assert set(got) == {"deliveries_this_year", "year"}
