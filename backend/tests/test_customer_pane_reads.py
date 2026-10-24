"""The Customer Pane against a database: the resolver, the account, the opening rule.

⚠️ THE SESSION ROLLS BACK; nothing here commits. Same shape as `test_sales_order_pane`.

⚠️ AND IT RUNS UNDER CI'S ENV OR NOT AT ALL, which is the lesson of 2026-10-23: a
module-level skip on `DATABASE_URL` made 44 tests one SKIPPED line locally while CI ran
them, and a pure-function test among them broke. The skip is still right — these need a
database — but the pure rules live in `test_customer_pane.py`, which has no guard.
"""
from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

if not os.environ.get("DATABASE_URL") or not os.environ.get("SECRET_KEY"):
    pytest.skip("DATABASE_URL is not set", allow_module_level=True)

from sqlalchemy import text

from app.database import SessionLocal
from app.models.cemetery import Cemetery
from app.models.company import Company
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.sales_order import SalesOrder
from app.services.order_list import customer as cust
from app.services.order_list.service import load_facts
from tests._cleanup import purge_companies_by_slug

TODAY = date(2026, 10, 24)
SLUG = "cp1-customer-pane"


@pytest.fixture()
def tenant():
    """A tenant of its own, rolled back, and purged either side.

    ⚠️ PURGED BEFORE AS WELL AS AFTER. A run that died mid-test leaves rows behind, and
    the next run's assertions are then about a database nobody built — the company-litter
    class CLAUDE.md §11 records. `purge_companies_by_slug` takes a LIKE prefix.
    """
    db = SessionLocal()
    try:
        purge_companies_by_slug(db, f"{SLUG}%")
        db.commit()
        company = Company(id=str(uuid.uuid4()), name="CP1 Vault Co", slug=SLUG,
                          vertical="manufacturing", is_active=True)
        db.add(company)
        db.flush()
        yield db, company.id
    finally:
        db.rollback()
        try:
            purge_companies_by_slug(db, f"{SLUG}%")
            db.commit()
        except Exception:
            db.rollback()
        db.close()


def _customer(db, tid, name, **kw) -> Customer:
    c = Customer(id=str(uuid.uuid4()), company_id=tid, name=name, is_active=True, **kw)
    db.add(c)
    db.flush()
    return c


def _order(db, tid, cid, number, **kw) -> SalesOrder:
    """⚠️ `scheduled_date`, NOT `service_date`. `OrderFacts.service_date` is a DERIVED
    name — `load_facts` selects `so.scheduled_date AS …` — and there is no
    `service_date` column. A fixture using the derived name raises at construction,
    which is how I found out.
    """
    if "service_date" in kw:
        kw["scheduled_date"] = kw.pop("service_date")
    # `order_date` is NOT NULL on the table and the model supplies no default, so a
    # fixture that omits it raises rather than writing a row the schema permits.
    kw.setdefault("order_date", date(2026, 10, 1))
    o = SalesOrder(id=str(uuid.uuid4()), company_id=tid, customer_id=cid, number=number,
                   status=kw.pop("status", "confirmed"), **kw)
    db.add(o)
    db.flush()
    return o


def _cemetery(db, tid, name) -> Cemetery:
    """The cemetery is a JOINED row, not a column on the order."""
    c = Cemetery(id=str(uuid.uuid4()), company_id=tid, name=name)
    db.add(c)
    db.flush()
    return c


def _invoice(db, tid, cid, number, **kw) -> Invoice:
    # `due_date` is NOT NULL on the table too. A default FAR IN THE FUTURE on purpose, so
    # a test that does not care about ageing never accidentally creates a past-due row —
    # `_account` reads `due_date < today` and a convenient "today" default would have
    # made every fixture past due.
    kw.setdefault("due_date", datetime(2027, 1, 1, tzinfo=timezone.utc))
    i = Invoice(id=str(uuid.uuid4()), company_id=tid, customer_id=cid, number=number,
                status=kw.pop("status", "sent"), **kw)
    db.add(i)
    db.flush()
    return i


# ── the resolver ──────────────────────────────────────────────────────────────


def test_a_name_and_a_prefix_both_reach_the_account(tenant):
    db, tid = tenant
    hopkins = _customer(db, tid, "Hopkins Funeral Home")
    assert [h["id"] for h in cust.resolve(db, tid, "Hopkins Funeral Home")] == [hopkins.id]
    assert [h["id"] for h in cust.resolve(db, tid, "hopkins")] == [hopkins.id]
    assert [h["id"] for h in cust.resolve(db, tid, "hopk")] == [hopkins.id]


def test_a_prefix_reaches_a_word_inside_the_name(tenant):
    """James's ruling, 2026-10-21, reused rather than reimplemented: "a prefix may match
    at the start of any word inside a known name".
    """
    db, tid = tenant
    riverside = _customer(db, tid, "Riverside Memorial Chapel")
    assert [h["id"] for h in cust.resolve(db, tid, "riverside")] == [riverside.id]
    assert [h["id"] for h in cust.resolve(db, tid, "riverside memorial")] == [riverside.id]


def test_a_single_generic_word_asks_and_never_opens(tenant):
    """⚠️ SUPERSEDES `test_a_single_generic_word_reaches_nothing` (James, 2026-10-24).

    That test asserted `resolve(db, tid, generic) == []` for every generic word, and the
    reasoning was that the 2026-10-21 match-point ruling governed the contains pass too.
    It does not: "ask, don't refuse. A generic word on its own shows 'Did you mean…' with
    every customer it matches as a choice, even a single one; the person confirms. No
    matches: the honest miss. It never opens anything directly."

    So the word RESOLVES, and the confirmation happens one layer up.
    """
    db, tid = tenant
    riverside = _customer(db, tid, "Riverside Memorial Chapel")
    hopkins = _customer(db, tid, "Hopkins Funeral Home")

    # "memorial" matches one of the two — and is still a question, not an opening.
    got = cust.open_from_phrase(db, tid, "memorial")
    assert got is not None
    assert got["kind"] == "customer_picks", "even a single match is confirmed"
    assert got["hint"] == cust.DID_YOU_MEAN
    assert [p["customer_id"] for p in got["customer_picks"]] == [riverside.id]

    # "funeral" matches the other, same shape.
    got = cust.open_from_phrase(db, tid, "funeral")
    assert got["kind"] == "customer_picks"
    assert [p["customer_id"] for p in got["customer_picks"]] == [hopkins.id]

    # ⚠️ A GENERIC WORD MATCHING BOTH IS STILL ONE QUESTION, not a pick of one.
    got = cust.open_from_phrase(db, tid, "the")
    if got is not None:
        assert got["kind"] == "customer_picks"

    # ⚠️ NO MATCHES IS THE HONEST MISS, which here means None so `ask` can fall through
    # to the model door. "cemetery" is generic and matches neither name.
    assert cust.open_from_phrase(db, tid, "cemetery") is None

    # The control: two words, one distinctive, resolves AND opens directly.
    assert len(cust.resolve(db, tid, "memorial chapel")) == 1
    direct = cust.open_from_phrase(db, tid, "memorial chapel")
    assert direct["kind"] == "open_customer", "not a generic word on its own"
    assert direct["customer_id"] == riverside.id


def test_a_lone_generic_word_is_confirmed_even_when_it_names_a_customer_exactly(tenant):
    """⚠️ THE EXACT PASS IS NOT AN EXCEPTION, and that is why the rule lives in
    `open_from_phrase` rather than in `resolve`. A customer literally called "Memorial"
    is matched by the exact-name pass, which would otherwise hand back one hit and open
    it — "it never opens anything directly" (James, 2026-10-24).
    """
    db, tid = tenant
    exact = _customer(db, tid, "Memorial")
    got = cust.open_from_phrase(db, tid, "memorial")
    assert got["kind"] == "customer_picks"
    assert [p["customer_id"] for p in got["customer_picks"]] == [exact.id]


def test_a_distinctive_word_still_opens_without_asking(tenant):
    """The control for the pair above: ruling 1 changed the GENERIC case only."""
    db, tid = tenant
    hopkins = _customer(db, tid, "Hopkins Funeral Home")
    got = cust.open_from_phrase(db, tid, "hopkins")
    assert got["kind"] == "open_customer"
    assert got["customer_id"] == hopkins.id
    assert cust.needs_confirmation("hopkins") is False
    assert cust.needs_confirmation("memorial") is True
    # ⚠️ CASE AND PADDING, because the phrase arrives as the director typed it.
    assert cust.needs_confirmation("  MEMORIAL  ") is True
    assert cust.needs_confirmation("memorial chapel") is False


def test_two_customers_sharing_a_word_are_a_choice_not_a_guess(tenant):
    db, tid = tenant
    _customer(db, tid, "Riverside Memorial Chapel")
    _customer(db, tid, "Riverside Burial Services")
    got = cust.open_from_phrase(db, tid, "riverside")
    assert got is not None and got["kind"] == "customer_picks"
    assert sorted(p["label"] for p in got["customer_picks"]) == [
        "Riverside Burial Services", "Riverside Memorial Chapel",
    ]
    # ⚠️ ON ITS OWN KEY, not `picks`. An order pick carries a question; this carries an
    # id that opens a pane, and a consumer that confused them would feed a customer id
    # into `ask`.
    assert "picks" not in got


def test_an_exact_name_wins_over_a_longer_one_that_contains_it(tenant):
    db, tid = tenant
    short = _customer(db, tid, "Riverside")
    _customer(db, tid, "Riverside Memorial Chapel")
    got = cust.open_from_phrase(db, tid, "riverside")
    assert got is not None and got["kind"] == "open_customer"
    assert got["customer_id"] == short.id


# ── the opening rule ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("phrase", [
    "hopkins order", "order hopkins", "hopkins orders", "hopkins orders this month",
    "order for hopkins monticello",
])
def test_an_order_word_keeps_it_an_order_request(tenant, phrase):
    """"with an order word it stays an order request as today" — so this must NOT claim
    the phrase, or "order hopkins" stops starting a capture.

    ⚠️ AND THE `_ORDER_WORDS` GUARD IS DEFENSIVE, NOT LOAD-BEARING, WHICH A BREAK TEST
    FOUND. Replacing that guard with `pass` turns NOTHING red: `resolve` is strict
    enough that "hopkins order" matches no name anyway — exact fails, the single-generic
    rule does not apply, `contains` fails because the phrase is longer than the name,
    and the prefix walk dies on "o" vs "f". So the protection here is supplied by a
    layer beneath the guard. CLAUDE.md §11.

    The guard stays: it is the only thing that would hold if `resolve` ever loosened
    (token-subset matching would make "hopkins order" match Hopkins immediately), and it
    states the rule where a reader looks for it. What this test pins is the OUTCOME
    James asked for, which is worth having whichever layer provides it.
    """
    db, tid = tenant
    _customer(db, tid, "Hopkins Funeral Home")
    assert cust.open_from_phrase(db, tid, phrase) is None


def test_a_phrase_matching_no_customer_is_not_claimed(tenant):
    """⚠️ None MEANS "NOT A CUSTOMER PHRASE", NOT "NO SUCH CUSTOMER", and `ask` depends
    on the difference: it falls through to the MODEL DOOR on None. Claiming an
    unmatched name here would make the door unreachable for every bare word.
    """
    db, tid = tenant
    _customer(db, tid, "Hopkins Funeral Home")
    for phrase in ("zzzqqq", "anything going to st marys", "what's the total"):
        assert cust.open_from_phrase(db, tid, phrase) is None
    # The control: a real name IS claimed, so the Nones above are about the phrase.
    assert cust.open_from_phrase(db, tid, "hopkins") is not None


def test_an_opener_word_is_stripped(tenant):
    db, tid = tenant
    hopkins = _customer(db, tid, "Hopkins Funeral Home")
    for phrase in ("open hopkins", "show hopkins", "pull up hopkins"):
        got = cust.open_from_phrase(db, tid, phrase)
        assert got is not None and got["customer_id"] == hopkins.id, phrase


def test_one_letter_is_not_a_prefix(tenant):
    """`MIN_PREFIX` is 2. A single keystroke must not open a pane."""
    db, tid = tenant
    _customer(db, tid, "Hopkins Funeral Home")
    assert cust.open_from_phrase(db, tid, "h") is None


# ── the pane ──────────────────────────────────────────────────────────────────


def test_the_two_lists_split_on_today(tenant):
    db, tid = tenant
    c = _customer(db, tid, "Hopkins Funeral Home")
    _order(db, tid, c.id, "SO-1", service_date=TODAY - timedelta(days=8),
           deceased_name="past")
    _order(db, tid, c.id, "SO-2", service_date=TODAY, deceased_name="today")
    _order(db, tid, c.id, "SO-3", service_date=TODAY + timedelta(days=4),
           deceased_name="ahead")
    _order(db, tid, c.id, "SO-4", service_date=TODAY + timedelta(days=4),
           deceased_name="gone", status="cancelled")
    db.flush()
    d = cust.customer_detail(db, tid, c.id, TODAY,
                             facts=load_facts(db, tid, include_cancelled=True))
    assert d is not None
    assert [r["deceased_name"] for r in d["open_orders"]] == ["today", "ahead"]
    assert [r["deceased_name"] for r in d["overdue"]] == ["past"]
    # ⚠️ A CANCELLED ORDER IS IN NEITHER, and the control is that it exists at all.
    assert all(r["deceased_name"] != "gone" for r in d["open_orders"] + d["overdue"])
    assert d["overdue_label"] == "Service day passed, not delivered"


def test_a_row_names_the_vault_and_cemetery_but_not_the_funeral_home(tenant):
    """We are inside that customer's pane; repeating the name on every row is the
    blank-label problem in a different key.
    """
    db, tid = tenant
    c = _customer(db, tid, "Hopkins Funeral Home")
    cem = _cemetery(db, tid, "St. Mary's Cemetery")
    _order(db, tid, c.id, "SO-2026-0412", service_date=TODAY, deceased_name="smith",
           cemetery_id=cem.id)
    db.flush()
    d = cust.customer_detail(db, tid, c.id, TODAY,
                             facts=load_facts(db, tid, include_cancelled=True))
    row = d["open_orders"][0]
    assert row["short"] == "0412"
    assert "Hopkins" not in (row.get("what") or "")
    assert row["status"] == "Confirmed"


def test_no_invoices_says_so_and_never_invents_a_balance(tenant):
    db, tid = tenant
    c = _customer(db, tid, "Hopkins Funeral Home")
    db.flush()
    d = cust.customer_detail(db, tid, c.id, TODAY, facts=[])
    assert d["account"] == {"none": cust.NO_INVOICES}


def test_a_draft_invoice_is_not_a_balance(tenant):
    """⚠️ THE PRODUCTION CASE. Hopkins' $1,705 sits on a DRAFT invoice, and
    `OrderFacts.invoiced` excludes exactly draft/void/write_off — so the account line
    and the row's status cannot disagree about whether money is owed.
    """
    db, tid = tenant
    c = _customer(db, tid, "Hopkins Funeral Home")
    _invoice(db, tid, c.id, "INV-1", status="draft", total=Decimal("1705"),
             amount_paid=Decimal("0"), invoice_date=datetime(2026, 10, 1, tzinfo=timezone.utc))
    db.flush()
    d = cust.customer_detail(db, tid, c.id, TODAY, facts=[])
    assert d["account"] == {"none": cust.NO_INVOICES}
    # The control: the same invoice SENT is a balance.
    db.execute(text("UPDATE invoices SET status='sent' WHERE company_id=:t"), {"t": tid})
    db.flush()
    d2 = cust.customer_detail(db, tid, c.id, TODAY, facts=[])
    assert "none" not in d2["account"]
    assert "1,705" in d2["account"]["line"]


def test_past_due_is_named_and_flagged(tenant):
    db, tid = tenant
    c = _customer(db, tid, "Hopkins Funeral Home", payment_terms="Net 30")
    _invoice(db, tid, c.id, "INV-1", status="sent", total=Decimal("400"),
             amount_paid=Decimal("0"),
             invoice_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
             due_date=datetime(2026, 8, 28, tzinfo=timezone.utc))
    db.flush()
    d = cust.customer_detail(db, tid, c.id, TODAY, facts=[])
    assert d["account"]["past_due"] is True
    assert d["account"]["line"] == "$400 balance · $400 past due · Net 30"


def test_the_account_line_shows_words_not_the_stored_token(tenant):
    """⚠️ THE INTEGRATION SIDE, AND A BREAK TEST FORCED IT. `test_terms_are_words_...`
    exercises `_nice_terms` directly, and the past-due test stores an already-pretty
    "Net 30" — so breaking `_account`'s call to the prettifier turned NOTHING red. The
    stored value has to be the raw token for this path to be covered, which is exactly
    what testco holds: `net_30`.
    """
    db, tid = tenant
    c = _customer(db, tid, "Hopkins Funeral Home", payment_terms="net_30")
    _invoice(db, tid, c.id, "INV-1", status="sent", total=Decimal("400"),
             amount_paid=Decimal("0"),
             invoice_date=datetime(2026, 10, 1, tzinfo=timezone.utc))
    db.flush()
    d = cust.customer_detail(db, tid, c.id, TODAY, facts=[])
    assert d["account"]["line"] == "$400 balance · Net 30"
    assert "net_30" not in d["account"]["line"]


def test_terms_come_from_the_customer_and_are_absent_when_unstored(tenant):
    """⚠️ `invoices.payment_terms` IS POPULATED ON PRODUCTION ('Net 30' on 8 of 9) and
    `customers.payment_terms` is NOT — so reading the invoice would fill the line in.
    It would also answer a different question: "the terms we last billed on" is not
    "this account's terms". The dispatch says "terms if stored".
    """
    db, tid = tenant
    c = _customer(db, tid, "Hopkins Funeral Home")
    _invoice(db, tid, c.id, "INV-1", status="sent", total=Decimal("400"),
             amount_paid=Decimal("0"), payment_terms="Net 30",
             invoice_date=datetime(2026, 10, 1, tzinfo=timezone.utc))
    db.flush()
    d = cust.customer_detail(db, tid, c.id, TODAY, facts=[])
    assert "Net 30" not in d["account"]["line"]
    assert d["account"]["line"] == "$400 balance"


def test_the_people_tab_is_absent_with_no_contacts(tenant):
    """"contacts on the record, if any; otherwise leave the tab out". Zero contacts for
    the whole tenant on production, so this is the shipping case.
    """
    db, tid = tenant
    c = _customer(db, tid, "Hopkins Funeral Home")
    db.flush()
    d = cust.customer_detail(db, tid, c.id, TODAY, facts=[])
    assert "people" not in d


def test_the_action_fills_the_funeral_home_in(tenant):
    """"It starts a capture with the funeral home already filled (as if the bar said
    'order <name> ')" — including the trailing space, which is what leaves the capture
    ready for the next word rather than mid-token.
    """
    db, tid = tenant
    c = _customer(db, tid, "Hopkins Funeral Home")
    db.flush()
    d = cust.customer_detail(db, tid, c.id, TODAY, facts=[])
    assert d["action"]["label"] == "New order"
    assert d["action"]["opening_line"] == "order Hopkins Funeral Home "
    assert d["action"]["opening_line"].endswith(" ")


def test_another_tenants_customer_is_not_readable(tenant):
    """Tenant isolation, asserted at the function the route calls."""
    db, tid = tenant
    c = _customer(db, tid, "Hopkins Funeral Home")
    db.flush()
    assert cust.customer_detail(db, "some-other-tenant", c.id, TODAY, facts=[]) is None
    assert cust.resolve(db, "some-other-tenant", "hopkins") == []
    # The control: the real tenant can read it.
    assert cust.customer_detail(db, tid, c.id, TODAY, facts=[]) is not None


def test_only_this_customers_orders_reach_the_pane(tenant):
    """⚠️ BY ID, NOT BY NAME. The bar matches names; a pane opened for one account must
    show that account's orders, not every order whose funeral home shares a word.
    """
    db, tid = tenant
    a = _customer(db, tid, "Riverside Memorial Chapel")
    b = _customer(db, tid, "Riverside Burial Services")
    _order(db, tid, a.id, "SO-A", service_date=TODAY, deceased_name="theirs")
    _order(db, tid, b.id, "SO-B", service_date=TODAY, deceased_name="others")
    db.flush()
    facts = load_facts(db, tid, include_cancelled=True)
    d = cust.customer_detail(db, tid, a.id, TODAY, facts=facts)
    assert [r["deceased_name"] for r in d["open_orders"]] == ["theirs"]


def test_the_bare_name_rule_runs_before_the_model_door(tenant):
    """⚠️ THE ORDERING IS THE POINT, AND THE HARNESS NAMED THIS TEST BEFORE IT EXISTED.
    My break harness listed it as the expected casualty of moving the customer rule
    after `propose`, and it reported a miss — because I had not written it. A break test
    that names a test that does not exist reports GREEN for the wrong reason.

    Rules first is the standing contract, and here it is worth money as well as
    principle: the door costs ~900 ms and would answer "hopkins" with a plausible
    order-LIST question for that home, when the tenant's own customer table settles it
    for free and exactly.
    """
    from app.services.order_list.service import ask

    db, tid = tenant
    hopkins = _customer(db, tid, "Hopkins Funeral Home")
    db.flush()

    called: list[str] = []

    def spy(phrase, today, db_, company_id):
        called.append(phrase)
        return None

    got = ask(
        db, company_id=tid, user_id=None, role_slug="admin", phrase="hopkins",
        question=None, remove_pill_id=None, teach_phrase=None, today=TODAY, propose=spy,
    )
    assert got["kind"] == "open_customer"
    assert got["customer_id"] == hopkins.id
    assert called == [], "the model door was consulted for a phrase the rules settled"

    # ⚠️ THE CONTROL: a phrase the rules and the customer table BOTH decline still
    # reaches the door. Without this, a rule that claimed everything would pass above.
    ask(
        db, company_id=tid, user_id=None, role_slug="admin",
        phrase="anything going to st marys", question=None, remove_pill_id=None,
        teach_phrase=None, today=TODAY, propose=spy,
    )
    assert called == ["anything going to st marys"]


def test_the_action_names_the_field_it_seeds(tenant):
    """⚠️ A GAP A BREAK TEST FOUND. Deleting `action.prefill` from the server turned
    NOTHING red — every prefill test called `session_service.start` directly, so the
    Customer Pane's half of the wiring was unwatched.

    The server names the field because the capture route whitelists what a pane may seed
    (`PREFILLABLE_FIELDS`); letting the client decide would put that in two places, one
    of them the side that cannot be trusted with it.
    """
    db, tid = tenant
    c = _customer(db, tid, "Hopkins Funeral Home")
    db.flush()
    d = cust.customer_detail(db, tid, c.id, TODAY, facts=[])
    assert d["action"]["prefill"] == {"funeral_home": "Hopkins Funeral Home"}
    # ⚠️ AND IT AGREES WITH THE OPENING LINE. Two strings naming the same home, from one
    # row — if they ever disagreed the bar would show one thing and the capture hold
    # another, which is the "what's on screen matches what was captured" rule broken.
    assert d["action"]["prefill"]["funeral_home"] in d["action"]["opening_line"]
