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
    assert [h["line"] for h in got["usual_vault"]] == [
        "Monticello · 2 of 3 orders", "Venetian · 1 of 3 orders",
    ]
    assert [h["line"] for h in got["usual_cemeteries"]] == [
        "St. Mary's Cemetery · 2 of 3 orders", "Lake View · 1 of 3 orders",
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
    orders = [
        _order(id="a", vault="Venetian"), _order(id="b", vault="Monticello"),
        _order(id="c", vault="Continental"),
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
    many = [
        _order(id=str(i), vault=f"Vault {i}", cemetery="Oakwood Cemetery")
        for i in range(10)
    ]
    got = what_opas_knows(many)
    assert len(got["usual_vault"]) == MAX_HABITS == 3
    # The control: a real habit is not truncated away, and the denominator is still 10.
    assert got["usual_cemeteries"] == [
        {"name": "Oakwood Cemetery", "count": 10, "of": 10,
         "line": "Oakwood Cemetery · 10 of 10 orders"},
    ]
