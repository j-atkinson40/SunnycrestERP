"""The Customer Pane's rules. No database for most of it, no network, no model.

James's dispatch of 2026-10-24, slice 1.

⚠️ WHAT EACH TEST WOULD CATCH IS NAMED ON IT, because several assert an ABSENCE — no
meta line, no People tab, a phrase that must NOT be claimed — and an absence is
satisfied by a pane that renders nothing at all. Every absence test here sits beside a
positive control.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal

import pytest

from app.services.order_list.customer import (
    MAX_HABITS,
    MIN_HABIT_ORDERS,
    MIN_HABIT_SHARE,
    MIN_ORDERS_FOR_HABITS,
    NOT_ENOUGH,
    _nice_terms,
    meta_line,
    what_opas_knows,
)
from app.services.order_list.stage import DeliveryFact, OrderFacts, is_overdue

#: Saturday. SO-0001's day (Oct 16) is behind it; Oct 28 is ahead.
TODAY = date(2026, 10, 24)


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


def test_the_meta_line_is_absent_when_the_record_holds_nothing():
    """⚠️ THE PRODUCTION CASE, MEASURED BEFORE BUILDING. Every one of `customer_type`,
    `address_line1`, `city`, `state` and `contact_name` is NULL for all five of
    Sunnycrest's customers. The prototype's line is built from a fixture where all four
    exist, so a naive f-string renders "Funeral home ·  ,  · , director".
    """
    assert meta_line({"name": "Hopkins Funeral Home"}) is None
    assert meta_line({}) is None


def test_every_part_of_the_meta_line_is_optional_and_the_separators_collapse():
    full = {"kind": "funeral_home", "address_line1": "12 Genesee St",
            "city": "Skaneateles", "state": "NY", "contact_name": "Ruth Hopkins"}
    assert meta_line(full) == "Funeral home · 12 Genesee St, Skaneateles, NY · Ruth Hopkins, director"
    # Each part alone, and never a stray separator.
    assert meta_line({"kind": "funeral_home"}) == "Funeral home"
    assert meta_line({"contact_name": "Ruth Hopkins"}) == "Ruth Hopkins, director"
    assert meta_line({"city": "Skaneateles"}) == "Skaneateles"
    assert meta_line({"city": "Skaneateles", "state": "NY"}) == "Skaneateles, NY"
    # ⚠️ A STATE WITH NO TOWN IS NOT A PLACE. "NY" alone on the line would read as an
    # address; it is dropped with the town it qualifies.
    assert meta_line({"state": "NY"}) is None
    for rendered in (meta_line(full), meta_line({"kind": "funeral_home"})):
        assert rendered is not None
        assert "·  ·" not in rendered and not rendered.endswith("·")


# ── what Opas knows ───────────────────────────────────────────────────────────


def test_under_three_orders_it_says_so_instead_of_counting():
    """James: "With fewer than 3 orders, say 'Not enough orders yet' instead of a
    percentage." ⚠️ This is the PRODUCTION case for every customer — Hopkins has 2
    non-cancelled orders and Riverside 1.
    """
    two = [_order(id="a", vault="Monticello"), _order(id="b", vault="Monticello")]
    got = what_opas_knows(two)
    assert got["not_enough"] == NOT_ENOUGH
    assert got["orders"] == 2
    assert "usual_vault" not in got


def test_three_orders_counts_them_and_never_shows_a_percentage():
    three = [
        _order(id="a", vault="Monticello", cemetery="St. Mary's Cemetery"),
        _order(id="b", vault="Monticello", cemetery="St. Mary's Cemetery"),
        _order(id="c", vault="Venetian", cemetery="Lake View"),
    ]
    got = what_opas_knows(three)
    assert "not_enough" not in got
    assert got["orders"] == 3
    # ⚠️ CORRECTED 2026-10-24. This asserted a second entry on each line —
    # "Venetian · 1 of 3 orders" and "Lake View · 1 of 3 orders". A habit now needs 2+
    # orders AND 25%+ of them, and a single order clears the share (33%) but not the
    # count. "A 1-of-10 is history, not a habit" (James) — and so is a 1-of-3.
    assert [h["line"] for h in got["usual_vault"]] == ["Monticello · 2 of 3 orders"]
    assert [h["line"] for h in got["usual_cemeteries"]] == [
        "St. Mary's Cemetery · 2 of 3 orders",
    ]
    # ⚠️ THE PROTOTYPE'S OWN FORMAT IS THE THING BEING REFUSED. It shows
    # "Monticello 51%"; the dispatch overrides it. A percentage over three orders is an
    # arithmetic accident that reads as a finding.
    for habit in got["usual_vault"] + got["usual_cemeteries"]:
        assert "%" not in habit["line"]


def test_a_cancelled_order_does_not_teach_a_habit():
    """⚠️ MY JUDGEMENT, NOT THE DISPATCH'S, AND IT IS THE MOST VISIBLE ONE IN THE PANE.
    Every list in this module excludes cancelled orders and "2 of 3 orders" reads as a
    count of real ones. It is what moves Hopkins from 3 orders to 2 and therefore under
    the threshold — so if James wants cancelled orders counted, this is the test to
    argue with.
    """
    orders = [
        _order(id="a", vault="Monticello"),
        _order(id="b", vault="Monticello"),
        _order(id="c", vault="Venetian", status="cancelled"),
    ]
    got = what_opas_knows(orders)
    assert got["not_enough"] == NOT_ENOUGH, "three rows, two orders"
    assert got["orders"] == 2
    # The control: the same three with none cancelled does count.
    assert "usual_vault" in what_opas_knows([
        _order(id="a", vault="Monticello"), _order(id="b", vault="Monticello"),
        _order(id="c", vault="Venetian"),
    ])


def test_ties_break_by_name_so_the_rulebook_does_not_change_its_mind():
    """⚠️ THE TIE IS NOW AT TWO EACH, NOT ONE EACH. The original built three vaults with
    one order apiece; under the 2026-10-24 thresholds none of them is a habit, so the
    list came back empty and the test proved nothing about ordering. Six orders, two
    apiece: each clears 2 orders and 33%, so all three qualify and the ORDER is what is
    under test again.
    """
    orders = [
        _order(id="a", vault="Venetian"), _order(id="b", vault="Venetian"),
        _order(id="c", vault="Monticello"), _order(id="d", vault="Monticello"),
        _order(id="e", vault="Continental"), _order(id="f", vault="Continental"),
    ]
    lines = [h["name"] for h in what_opas_knows(orders)["usual_vault"]]
    assert lines == ["Continental", "Monticello", "Venetian"]


def test_an_order_with_no_vault_is_counted_in_the_denominator_but_not_the_tally():
    """The denominator is ORDERS, not orders-with-a-vault. "2 of 3" must mean two of the
    three orders this customer placed, or the fraction is about a set nobody chose.
    """
    orders = [
        _order(id="a", vault="Monticello"), _order(id="b", vault="Monticello"),
        _order(id="c"),
    ]
    got = what_opas_knows(orders)
    assert got["orders"] == 3
    assert got["usual_vault"] == [
        {"name": "Monticello", "count": 2, "of": 3, "line": "Monticello · 2 of 3 orders"},
    ]


def test_a_one_of_ten_is_history_not_a_habit():
    """⚠️ JAMES'S OWN SENTENCE, AND THE CASE THAT PROMPTED THE RULING. Johnson Funeral
    Home on testco has 10 orders across five vaults, every one of them 1-of-10. The cap
    stopped the line being a five-entry census; it did not stop it calling a single order
    "usual". The thresholds do: "at least 2 orders and at least 25% of the customer's
    orders" (James, 2026-10-24).
    """
    census = [_order(id=str(i), vault=f"Vault {i}") for i in range(10)]
    got = what_opas_knows(census)
    assert got["usual_vault"] == []
    assert got["usual_vault_varies"] == "Varies, no usual vault yet"
    # ⚠️ AND IT IS NOT "Not enough orders yet" — that would report a measured finding as
    # missing data. Ten orders is plenty; the answer is that there is no usual vault.
    assert "not_enough" not in got
    assert got["orders"] == 10


def test_both_halves_of_the_bar_are_load_bearing():
    """⚠️ EACH THRESHOLD CATCHES WHAT THE OTHER MISSES, which is why the ruling says both.

    A count-only rule lets 2-of-40 (5%) read as usual. A share-only rule lets 1-of-3
    (33%) read as usual off a single order. Neither case is a habit, and a test that
    exercised only one of them would go green with the other deleted.
    """
    # 2 of 40 — clears the count, fails the share.
    wide = [_order(id=str(i), vault="Monticello" if i < 2 else f"Other {i}")
            for i in range(40)]
    got = what_opas_knows(wide)
    assert got["usual_vault"] == [], "2 of 40 is 5%"
    assert got["usual_vault_varies"] == "Varies, no usual vault yet"

    # 1 of 3 — clears the share, fails the count.
    narrow = [_order(id="a", vault="Monticello"), _order(id="b", vault="Venetian"),
              _order(id="c", vault="Continental")]
    assert what_opas_knows(narrow)["usual_vault"] == [], "1 of 3 is 33% of one order"

    # The control: 2 of 4 clears both and IS a habit.
    both = [_order(id="a", vault="Monticello"), _order(id="b", vault="Monticello"),
            _order(id="c", vault="Venetian"), _order(id="d", vault="Continental")]
    assert [h["line"] for h in what_opas_knows(both)["usual_vault"]] == [
        "Monticello · 2 of 4 orders",
    ]


def test_the_varies_line_is_absent_when_there_IS_a_habit():
    """The sentence is an answer, not a label — it must not ride along beside a habit."""
    got = what_opas_knows([
        _order(id="a", vault="Monticello", cemetery="St. Mary's Cemetery"),
        _order(id="b", vault="Monticello", cemetery="St. Mary's Cemetery"),
        _order(id="c", vault="Monticello", cemetery="St. Mary's Cemetery"),
    ])
    assert "usual_vault_varies" not in got
    assert "usual_cemeteries_varies" not in got


def test_a_habit_can_vary_on_one_axis_and_not_the_other():
    """⚠️ PER-FIELD, NOT ONE FLAG FOR THE WHOLE TAB. A customer who always uses St.
    Mary's but no particular vault must read as exactly that. A single `varies` would
    have to pick one of the two to be wrong about.
    """
    orders = [
        _order(id="a", vault="Monticello", cemetery="St. Mary's Cemetery"),
        _order(id="b", vault="Venetian", cemetery="St. Mary's Cemetery"),
        _order(id="c", vault="Continental", cemetery="St. Mary's Cemetery"),
    ]
    got = what_opas_knows(orders)
    assert got["usual_vault"] == []
    assert got["usual_vault_varies"] == "Varies, no usual vault yet"
    assert [h["line"] for h in got["usual_cemeteries"]] == [
        "St. Mary's Cemetery · 3 of 3 orders",
    ]
    assert "usual_cemeteries_varies" not in got


def test_varies_needs_something_recorded_to_vary():
    """⚠️ MEASURED ON PRODUCTION, AND THE RULING DID NOT HAVE TO COVER IT.

    "Varies, no usual vault yet" asserts that the orders were looked at and no vault
    repeated. Two unlike cases on testco would both have said it:

        Johnson Funeral Home    5 orders, vault recorded 5/5, all five different
        Green Valley Memorial   5 orders, vault recorded 0/5

    The first is the finding. The second is a claim about nothing, and it is the shape
    CLAUDE.md §5 names — "not established" must stay distinguishable from a measured
    value. An unrecorded field leaves the row out instead, which is this pane's standing
    rule for missing fields.
    """
    # Green Valley: nothing recorded. No habit, and NO sentence either.
    blank = [_order(id=str(i), cemetery="Oakwood Cemetery") for i in range(5)]
    got = what_opas_knows(blank)
    assert got["usual_vault"] == []
    assert "usual_vault_varies" not in got, "nothing recorded cannot vary"
    # The control, same shape: the cemetery IS recorded, so that axis still answers.
    assert [h["line"] for h in got["usual_cemeteries"]] == [
        "Oakwood Cemetery · 5 of 5 orders",
    ]

    # Johnson: five recorded, all different. THAT varies.
    varied = [_order(id=str(i), vault=f"Vault {i}") for i in range(5)]
    got = what_opas_knows(varied)
    assert got["usual_vault"] == []
    assert got["usual_vault_varies"] == "Varies, no usual vault yet"

    # ⚠️ AND ONE RECORDED VALUE IS ENOUGH TO EARN THE SENTENCE. A single vault across
    # ten orders is 1-of-10 — not a habit, but evidence we looked.
    one = [_order(id=str(i), vault="Monticello" if i == 0 else None) for i in range(10)]
    got = what_opas_knows(one)
    assert got["usual_vault"] == []
    assert got["usual_vault_varies"] == "Varies, no usual vault yet"


def test_the_habit_bar_is_james_s_numbers():
    """⚠️ THE VALUES, PINNED, FOR THE SAME REASON AS `MIN_ORDERS_FOR_HABITS` BELOW. Every
    test above builds its fixture from literal counts, so each would stay green if the
    constants moved to meet it. These two came from outside the code: "at least 2 orders
    and at least 25% of the customer's orders" (James, 2026-10-24).
    """
    assert MIN_HABIT_ORDERS == 2
    assert MIN_HABIT_SHARE == 0.25


def test_the_threshold_is_james_s_number():
    """⚠️ MY FIRST VERSION OF THIS TEST WAS VACUOUS AND A BREAK TEST SAID SO. It built
    lists of `MIN_ORDERS_FOR_HABITS - 1` and `MIN_ORDERS_FOR_HABITS` orders and asserted
    the function agreed — so setting the constant to 1 kept it green. A test that reads
    the constant cannot notice the constant moving; it asserts only that the code is
    self-consistent, which it would be at any value.

    So this pins the VALUE, which is the thing that came from outside the code: "with
    fewer than 3 orders, say 'Not enough orders yet'" (James, 2026-10-24). The boundary
    behaviour either side is covered by the two tests above, with literal 2 and 3.
    """
    assert MIN_ORDERS_FOR_HABITS == 3


# ── the overdue predicate, shared with the order list ─────────────────────────


def test_a_past_dated_order_carrying_a_flag_is_still_overdue():
    """⚠️ THE DEFECT A PRODUCTION RENDER FOUND, AND THE REASON `is_overdue` EXISTS.

    The pane first asked `group_of(...) == "overdue"`, which was one rule shared with
    the order list — and `group_of` lets a FLAG win, returning "needs_something". So
    SO-2026-0003, dated the day before with no driver and undelivered, came back in
    NEITHER of this pane's two lists and was shown nowhere on its own customer's pane.

    Precedence belongs to whoever is ranking; the DEFINITION is shared.
    """
    from app.services.order_list.stage import flag_of, group_of

    stale = _order(status="confirmed", service_date=date(2026, 10, 23))
    assert flag_of(stale, TODAY) == "nodriver", "the flag is what used to win"
    assert group_of(stale, TODAY) == "needs_something"
    assert is_overdue(stale, TODAY) is True

    # The control: the default view is unchanged — a flagless past order still groups
    # as overdue, which is what the fourth group shipped for on 2026-10-23.
    flagless = _order(
        status="confirmed", service_date=date(2026, 10, 23),
        deliveries=[DeliveryFact(primary_assignee_id="driver-1")],
    )
    assert flag_of(flagless, TODAY) is None
    assert group_of(flagless, TODAY) == "overdue"


#: ⚠️ NO `delivered` CASE IN HERE, DELIBERATELY, AND A BREAK TEST IS WHY IT IS SAID.
#: Removing `not facts.delivered` from `is_overdue` leaves every row below unchanged —
#: none of them is delivered — so this table does NOT cover that clause. The test that
#: does is `test_a_delivered_order_is_not_overdue_even_long_past`, and it goes red.
@pytest.mark.parametrize("kw,expected", [
    ({"status": "draft", "service_date": date(2026, 10, 16)}, True),
    ({"status": "confirmed", "service_date": date(2026, 10, 16)}, True),
    # today is not overdue — the boundary is the same one `going_out` uses
    ({"status": "confirmed", "service_date": TODAY}, False),
    ({"status": "confirmed", "service_date": date(2026, 10, 28)}, False),
    ({"status": "cancelled", "service_date": date(2026, 10, 16)}, False),
    ({"status": "confirmed", "service_date": None}, False),
])
def test_what_counts_as_overdue(kw, expected):
    assert is_overdue(_order(**kw), TODAY) is expected


def test_a_delivered_order_is_not_overdue_even_long_past():
    """⚠️ THE CASE I GOT WRONG BY INFERENCE ON PRODUCTION. Hopkins' SO-2026-0003 showed
    in neither list and I reasoned it must be invoiced. It is `delivered` — which is
    why it is not overdue, and why Recent is where it belongs. Checked, not assumed.
    """
    delivered = _order(
        status="delivered", service_date=date(2026, 10, 16),
        delivered_at=datetime(2026, 10, 16, tzinfo=timezone.utc),
    )
    assert delivered.delivered is True
    assert is_overdue(delivered, TODAY) is False


def test_an_invoiced_order_is_not_overdue():
    invoiced = _order(
        status="confirmed", service_date=date(2026, 10, 16), invoice_statuses=["sent"],
    )
    assert invoiced.invoiced is True
    assert is_overdue(invoiced, TODAY) is False
    # The control: a DRAFT invoice is not an invoice, so this one is still overdue.
    drafted = _order(
        status="confirmed", service_date=date(2026, 10, 16), invoice_statuses=["draft"],
    )
    assert drafted.invoiced is False
    assert is_overdue(drafted, TODAY) is True


# ── the account line's words ──────────────────────────────────────────────────


@pytest.mark.parametrize("stored,shown", [
    ("net_30", "Net 30"),
    # ⚠️ A SHOUTED PHRASE BECOMES A PHRASE. My per-token rule turned this into
    # "DUE ON receipt" — "DUE" and "ON" kept as short all-caps, "RECEIPT" lowered.
    ("DUE_ON_RECEIPT", "Due on receipt"),
    ("NET_30", "Net 30"),
    ("due_on_receipt", "Due on receipt"),
    # A lone short acronym survives as stored.
    ("COD", "COD"),
    ("EOM", "EOM"),
    # Lowercase stays sentence-cased rather than being guessed into an acronym.
    ("cod", "Cod"),
    ("2/10 net 30", "2/10 net 30"),
    ("Net 30", "Net 30"),
    (None, None),
    ("", None),
])
def test_terms_are_words_and_not_a_database_token(stored, shown):
    """⚠️ FOUND BY WALKING THE ROUTE OVER HTTP ON testco, WHICH PRODUCTION CANNOT SHOW.
    Sunnycrest stores no terms, so the line read "$0 balance" and looked finished.
    testco stores `net_30`, and the account line rendered "$0 balance · net_30" — a
    database token on the office's screen, where the prototype says "Net 30".
    """
    assert _nice_terms(stored) == shown


def test_a_habit_line_shows_at_most_three():
    """⚠️ THE PROTOTYPE'S OWN NUMBER, and measured need. Johnson Funeral Home on testco
    has 10 orders across FIVE vaults, so the uncapped line read five entries each "1 of
    10 orders" — a census, not a habit. The prototype shows three.

    ⚠️ IT DOES NOT DECIDE WHETHER A 1-of-10 IS "USUAL" — that is James's call about his
    own rulebook, and it is in the report rather than in this assertion.
    """
    # ⚠️ CORRECTED 2026-10-24, AND THE OLD FIXTURE NOW PROVES THE OTHER RULING. It was
    # ten orders across ten vaults, one apiece — Johnson's census. Under the thresholds
    # not one of those is a habit, so `usual_vault` comes back EMPTY and this test could
    # no longer see the cap at all. It needs FOUR qualifying habits to show three.
    #
    # Eight orders, four vaults, two apiece: 2 orders each and exactly 25% each, so all
    # four qualify — which also pins the share boundary as inclusive.
    many = [
        _order(id=str(i), vault=f"Vault {i % 4}", cemetery="Oakwood Cemetery")
        for i in range(8)
    ]
    got = what_opas_knows(many)
    assert [h["line"] for h in got["usual_vault"]] == [
        "Vault 0 · 2 of 8 orders", "Vault 1 · 2 of 8 orders", "Vault 2 · 2 of 8 orders",
    ], "four qualify, three are shown, ties by name"
    assert len(got["usual_vault"]) == MAX_HABITS == 3
    # The control: a real habit is not truncated away, and the denominator is still 8.
    assert got["usual_cemeteries"] == [
        {"name": "Oakwood Cemetery", "count": 8, "of": 8,
         "line": "Oakwood Cemetery · 8 of 8 orders"},
    ]
