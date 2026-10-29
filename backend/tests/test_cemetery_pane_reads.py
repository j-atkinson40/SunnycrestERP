"""The Cemetery Pane against a database: the resolver, the pane, the opening rule.

⚠️ THE SESSION ROLLS BACK; nothing here commits. Same shape as
`test_customer_pane_reads`.

⚠️ AND IT RUNS UNDER CI'S ENV OR NOT AT ALL, which is the lesson of 2026-10-23: a
module-level skip on `DATABASE_URL` made 44 tests one SKIPPED line locally while CI ran
them, and a pure-function test among them broke. The skip is still right — these need a
database — but the pure rules live in `test_cemetery_pane.py`, which has no guard. This
file is in `tests/ci_gate.txt` from the day it lands, for the reason
`test_capture_prefill.py` was not: a test CI never runs is documentation.

⚠️ THE SHARED-NAME CASES HERE ARE CONSTRUCTED, AND THAT IS STATED RATHER THAN HIDDEN.
Measured on production 2026-10-26: ZERO cemeteries share a name within any tenant. The
`(company_id, name)` unique constraint makes an exact duplicate impossible, so what can
collide is the same name punctuated differently — which is what these fixtures build.
Without saying so, a reader would take the feature for one that fires on real data.
"""
from __future__ import annotations

import os
import uuid
from datetime import date

import pytest

if not os.environ.get("DATABASE_URL") or not os.environ.get("SECRET_KEY"):
    pytest.skip("DATABASE_URL is not set", allow_module_level=True)

from app.database import SessionLocal
from app.models.cemetery import Cemetery
from app.models.company import Company
from app.models.customer import Customer
from app.models.sales_order import SalesOrder
from app.services.order_list import cemetery as cem
from app.services.order_list.cemetery import NOTHING_RECORDED
from app.services.order_list.customer import DID_YOU_MEAN, TOO_MANY
from app.services.order_list.service import load_facts
from tests._cleanup import purge_companies_by_slug

TODAY = date(2026, 10, 26)
SLUG = "cem1-cemetery-pane"


@pytest.fixture()
def tenant():
    """A tenant of its own, rolled back, and purged either side."""
    db = SessionLocal()
    try:
        purge_companies_by_slug(db, f"{SLUG}%")
        db.commit()
        company = Company(id=str(uuid.uuid4()), name="CEM1 Vault Co", slug=SLUG,
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


def _cemetery(db, tid, name, **kw) -> Cemetery:
    c = Cemetery(id=str(uuid.uuid4()), company_id=tid, name=name, **kw)
    db.add(c)
    db.flush()
    return c


def _customer(db, tid, name) -> Customer:
    c = Customer(id=str(uuid.uuid4()), company_id=tid, name=name, is_active=True)
    db.add(c)
    db.flush()
    return c


def _order(db, tid, cid, number, cemetery_id=None, **kw) -> SalesOrder:
    """⚠️ `scheduled_date`, NOT `service_date` — the latter is a DERIVED name on
    `OrderFacts`, and `order_date` is NOT NULL with no model default."""
    if "service_date" in kw:
        kw["scheduled_date"] = kw.pop("service_date")
    kw.setdefault("order_date", date(2026, 10, 1))
    o = SalesOrder(id=str(uuid.uuid4()), company_id=tid, customer_id=cid, number=number,
                   cemetery_id=cemetery_id, status=kw.pop("status", "confirmed"), **kw)
    db.add(o)
    db.flush()
    return o


# ── the resolver ──────────────────────────────────────────────────────────────


def test_a_name_a_prefix_and_the_punctuation_people_skip_all_reach_it(tenant):
    db, tid = tenant
    mary = _cemetery(db, tid, "St. Mary's Cemetery", city="Skaneateles", state="NY")
    _cemetery(db, tid, "Oakwood Cemetery", city="Auburn", state="NY")
    for phrase in ("st marys", "st mary's", "St. Mary's Cemetery", "marys", "mary"):
        got = cem.resolve(db, tid, phrase)
        assert [h["id"] for h in got] == [mary.id], phrase


def test_the_dispatch_s_own_name_and_town_phrase_resolves(tenant):
    """⚠️ IT DID NOT, AND THAT IS WHY THIS TEST EXISTS. Measured on production before
    building: `"st mary's skaneateles"` — one of the two phrases the 2026-10-26 dispatch
    names — resolved to NOTHING, on the cemetery resolver and the customer one alike,
    because the town is not part of the name and no pass joined them.

    "st marys" worked. The DISAMBIGUATING form did not, which is the one that matters
    precisely when a name is shared — so the feature would have failed in exactly the
    case it was built for.
    """
    db, tid = tenant
    mary = _cemetery(db, tid, "St. Mary's Cemetery", city="Skaneateles", state="NY")
    for phrase in ("st mary's skaneateles", "st marys skaneateles",
                   "St. Mary's Cemetery Skaneateles",
                   # town first, with the full name
                   "Skaneateles St. Mary's Cemetery"):
        got = cem.resolve(db, tid, phrase)
        assert [h["id"] for h in got] == [mary.id], phrase

    # ⚠️ THIS LINE USED TO ASSERT `== []`, AND JAMES RULED IT CHANGES (2026-10-29):
    # *"Extend the leading/bare town rule to the cemetery pane's search: change the line
    # at test_cemetery_pane_reads.py:131 and make "skaneateles st marys" /
    # "st marys skaneateles" open the pane. One town pattern shared by both surfaces,
    # not a copy."*
    #
    # The old comment argued the form was unsupported because "supporting it means
    # letting a town prefix a partial name, which starts matching phrases nobody typed."
    # That cost is real and is paid differently than the old pass would have paid it:
    # the town must be a WHOLE whitespace run that the tenant holds records for, so
    # "hopkins st marys" cannot read "hopkins" as a town. See `capture/towns.py`.
    assert [h["id"] for h in cem.resolve(db, tid, "skaneateles st marys")] == [mary.id]

    # ⚠️ AND THE BOUNDARY MOVED RATHER THAN DISAPPEARING, so here is where it sits now.
    # A town ALONE is not a cemetery phrase — the remainder after the town has to reach
    # a name, and an empty remainder reaches nothing. Without this the pane would open
    # on "skaneateles", which names a place and not a cemetery.
    assert cem.resolve(db, tid, "skaneateles") == []

    # ⚠️ AND A LEADING WORD THAT IS NOT A TOWN THIS TENANT HOLDS RECORDS FOR IS NOT A
    # TOWN. This is the assertion that pays for the ruling: it is what stops a funeral
    # home's name being read as a town and the rest as a cemetery.
    assert cem.resolve(db, tid, "hopkins st marys") == []


def test_the_town_picks_ONE_of_two_cemeteries_sharing_a_name(tenant):
    """⚠️ THE CASE THE WHOLE FEATURE IS FOR, and it is CONSTRUCTED — no production tenant
    has two cemeteries of one name. The `(company_id, name)` unique constraint forbids an
    exact duplicate, so these two differ by punctuation, which is what `_name_key`
    squeezes away.
    """
    db, tid = tenant
    skan = _cemetery(db, tid, "St. Mary's Cemetery", city="Skaneateles", state="NY")
    auburn = _cemetery(db, tid, "St Marys Cemetery", city="Auburn", state="NY")
    # Bare: both, because they ARE the same name.
    assert {h["id"] for h in cem.resolve(db, tid, "st marys")} == {skan.id, auburn.id}
    # With the town: exactly one each.
    assert [h["id"] for h in cem.resolve(db, tid, "st marys skaneateles")] == [skan.id]
    assert [h["id"] for h in cem.resolve(db, tid, "st marys auburn")] == [auburn.id]


def test_a_town_inside_the_name_is_not_mistaken_for_the_town(tenant):
    """⚠️ "Auburn Memorial Cemetery" IN Auburn. A substring cut would strip the first
    word and look for "memorial cemetery"; word-wise stripping does not."""
    db, tid = tenant
    auburn = _cemetery(db, tid, "Auburn Memorial Cemetery", city="Auburn", state="NY")
    assert [h["id"] for h in cem.resolve(db, tid, "auburn memorial")] == [auburn.id]
    assert [h["id"] for h in cem.resolve(db, tid, "auburn memorial cemetery")] == [auburn.id]


def test_tenant_isolation(tenant):
    """Another tenant's cemetery of the same name is not reachable, and the pane refuses
    the id outright. "St. Mary's Cemetery" exists on both sunnycrest and testco in
    production, so this is the live shape rather than a hypothetical."""
    db, tid = tenant
    other = Company(id=str(uuid.uuid4()), name="CEM1 Other", slug=f"{SLUG}-other",
                    vertical="manufacturing", is_active=True)
    db.add(other)
    db.flush()
    theirs = _cemetery(db, other.id, "St. Mary's Cemetery", city="Skaneateles")
    assert cem.resolve(db, tid, "st marys") == []
    assert cem.cemetery_detail(db, tid, theirs.id, TODAY) is None
    # The control: their own tenant reaches it.
    assert cem.cemetery_detail(db, other.id, theirs.id, TODAY) is not None


def test_an_inactive_cemetery_is_not_reachable(tenant):
    db, tid = tenant
    gone = _cemetery(db, tid, "Closed Cemetery", city="Auburn", is_active=False)
    assert cem.resolve(db, tid, "closed") == []
    assert cem.cemetery_detail(db, tid, gone.id, TODAY) is None


# ── the opening rule ──────────────────────────────────────────────────────────


def test_one_match_opens_and_two_ask_with_the_town_shown(tenant):
    db, tid = tenant
    skan = _cemetery(db, tid, "St. Mary's Cemetery", city="Skaneateles", state="NY")
    got = cem.open_from_phrase(db, tid, "st marys")
    assert got == {"kind": "open_cemetery", "cemetery_id": skan.id,
                   "cemetery_name": "St. Mary's Cemetery"}

    auburn = _cemetery(db, tid, "St Marys Cemetery", city="Auburn", state="NY")
    got = cem.open_from_phrase(db, tid, "st marys")
    assert got["kind"] == "cemetery_picks"
    assert got["hint"] == TOO_MANY
    # ⚠️ THE TOWN IS ON EVERY OPTION. "ask which with the choice list, town shown"
    # (dispatch) — two cemeteries of one name differ by nothing else, so options without
    # it would be a question nobody can answer.
    assert {(p["cemetery_id"], p["detail"]) for p in got["cemetery_picks"]} == {
        (skan.id, "Skaneateles"), (auburn.id, "Auburn"),
    }


def test_a_lone_generic_word_asks_here_too(tenant):
    """⚠️ RULING 1 (James, 2026-10-24) REACHING THIS SURFACE, and it fires far more often
    here: `cemetery` and `st` are both in `GENERIC_WORDS`, so "cemetery" on its own is a
    question rather than an opening — even when it matches exactly one row.
    """
    db, tid = tenant
    only = _cemetery(db, tid, "Oakwood Cemetery", city="Auburn", state="NY")
    got = cem.open_from_phrase(db, tid, "cemetery")
    assert got["kind"] == "cemetery_picks", "even a single match is confirmed"
    assert got["hint"] == DID_YOU_MEAN
    assert [p["cemetery_id"] for p in got["cemetery_picks"]] == [only.id]
    # The control: a distinctive word opens it directly.
    assert cem.open_from_phrase(db, tid, "oakwood")["kind"] == "open_cemetery"


def test_an_order_word_is_not_a_cemetery_phrase(tenant):
    db, tid = tenant
    _cemetery(db, tid, "Oakwood Cemetery", city="Auburn")
    for phrase in ("oakwood order", "order oakwood", "oakwood orders this month"):
        assert cem.open_from_phrase(db, tid, phrase) is None, phrase


def test_a_phrase_that_matches_nothing_is_not_claimed(tenant):
    """⚠️ None IS "NOT A CEMETERY PHRASE", NOT "NO SUCH CEMETERY", and `ask` depends on
    the difference: it must go on to try the customer rule and then the model door. A
    rule that claimed every unmatched phrase would silence both."""
    db, tid = tenant
    _cemetery(db, tid, "Oakwood Cemetery", city="Auburn")
    assert cem.open_from_phrase(db, tid, "zzzz") is None
    assert cem.open_from_phrase(db, tid, "") is None


def test_an_opener_is_stripped(tenant):
    db, tid = tenant
    oak = _cemetery(db, tid, "Oakwood Cemetery", city="Auburn")
    for phrase in ("open oakwood", "show oakwood", "pull up oakwood", "bring up oakwood"):
        got = cem.open_from_phrase(db, tid, phrase)
        assert got == {"kind": "open_cemetery", "cemetery_id": oak.id,
                       "cemetery_name": "Oakwood Cemetery"}, phrase


# ── the pane ──────────────────────────────────────────────────────────────────


def test_the_pane_on_a_record_holding_only_a_name_and_a_town(tenant):
    """⚠️ THE PRODUCTION SHAPE FOR ALL FOUR CEMETERIES. No action, no essentials, and the
    sentence instead — which is the dispatch's rule working rather than a defect."""
    db, tid = tenant
    mary = _cemetery(db, tid, "St. Mary's Cemetery", city="Skaneateles", state="NY")
    got = cem.cemetery_detail(db, tid, mary.id, TODAY)
    assert got["name"] == "St. Mary's Cemetery"
    assert got["meta"] == "Skaneateles, NY"
    assert "action" not in got, "no address recorded, so no Directions"
    assert "essentials" not in got
    assert got["essentials_empty"] == NOTHING_RECORDED
    assert "same_name" not in got
    assert got["coming"] == [] and got["overdue"] == []
    assert got["knows"]["deliveries_this_year"] == 0
    assert "next_delivery" not in got["knows"]


def test_coming_up_here_is_today_or_later_and_excludes_cancelled(tenant):
    """⚠️ "SERVICE DATE TODAY OR LATER", the boundary `going_out` has used since
    2026-10-23 — not "not yet delivered"."""
    db, tid = tenant
    mary = _cemetery(db, tid, "St. Mary's Cemetery", city="Skaneateles")
    home = _customer(db, tid, "Hopkins Funeral Home")
    _order(db, tid, home.id, "SO-1", mary.id, status="confirmed",
           service_date=date(2026, 10, 28), deceased_name="hart")
    _order(db, tid, home.id, "SO-2", mary.id, status="cancelled",
           service_date=date(2026, 10, 29), deceased_name="nope")
    _order(db, tid, home.id, "SO-3", mary.id, status="draft",
           service_date=date(2026, 10, 16), deceased_name="smith")
    # TODAY itself counts.
    _order(db, tid, home.id, "SO-4", mary.id, status="confirmed",
           service_date=TODAY, deceased_name="today")

    got = cem.cemetery_detail(db, tid, mary.id, TODAY,
                              facts=load_facts(db, tid, include_cancelled=True))
    assert [r["number"] for r in got["coming"]] == ["SO-4", "SO-1"], "soonest first"
    assert [r["number"] for r in got["overdue"]] == ["SO-3"]
    assert got["overdue_label"]
    # ⚠️ THE FUNERAL HOME IS ON THE ROW WITH ITS ID, which is the second half of James's
    # walk: cemetery -> order -> Hopkins.
    assert got["coming"][0]["funeral_home"] == "Hopkins Funeral Home"
    assert got["coming"][0]["customer_id"] == home.id


def test_an_order_at_another_cemetery_is_not_on_this_pane(tenant):
    db, tid = tenant
    mary = _cemetery(db, tid, "St. Mary's Cemetery", city="Skaneateles")
    oak = _cemetery(db, tid, "Oakwood Cemetery", city="Auburn")
    home = _customer(db, tid, "Hopkins Funeral Home")
    _order(db, tid, home.id, "SO-OAK", oak.id, status="confirmed",
           service_date=date(2026, 10, 28))
    facts = load_facts(db, tid, include_cancelled=True)
    assert cem.cemetery_detail(db, tid, mary.id, TODAY, facts=facts)["coming"] == []
    # The control: it IS on Oakwood's.
    assert [r["number"] for r in
            cem.cemetery_detail(db, tid, oak.id, TODAY, facts=facts)["coming"]] == ["SO-OAK"]


def test_the_essentials_render_from_whatever_is_recorded(tenant):
    db, tid = tenant
    rich = _cemetery(
        db, tid, "Fennell Cemetery", city="Skaneateles", state="NY",
        address="22 Fennell St", zip_code="13152",
        access_notes="Back in. Do not use the main lane.",
        contact_name="Paul Rinaldi", phone="(315) 555-0177",
        cemetery_provides_tent=True,
    )
    got = cem.cemetery_detail(db, tid, rich.id, TODAY)
    assert "essentials_empty" not in got
    assert [row["label"] for row in got["essentials"]] == [
        "Address", "Getting in", "Contact", "Cemetery provides",
    ]
    assert got["action"]["kind"] == "directions"
    assert "22+Fennell+St" in got["action"]["url"]


def test_same_name_links_the_other_one_and_the_server_writes_the_sentence(tenant):
    """⚠️ CONSTRUCTED — no production tenant has this. See the module docstring."""
    db, tid = tenant
    skan = _cemetery(db, tid, "St. Mary's Cemetery", city="Skaneateles", state="NY")
    auburn = _cemetery(db, tid, "St Marys Cemetery", city="Auburn", state="NY")
    got = cem.cemetery_detail(db, tid, skan.id, TODAY)
    assert got["same_name"]["cemetery_id"] == auburn.id
    assert got["same_name"]["town"] == "Auburn"
    assert got["same_name"]["line"] == "not the St Marys Cemetery in Auburn"
    # It is on `knows` too, which is where the prototype puts "Same name elsewhere".
    assert got["knows"]["same_name"]["cemetery_id"] == auburn.id
    # And it points BACK from the other one.
    assert cem.cemetery_detail(db, tid, auburn.id, TODAY)["same_name"]["cemetery_id"] == skan.id


def test_same_name_does_not_reach_across_tenants(tenant):
    """⚠️ A BREAK TEST FOUND THIS CLAIM UNNAMED. Removing `company_id` from
    `_same_name`'s query DID turn tests red — but the two that caught it were
    `test_same_name_links...` and `test_a_different_name...`, which went red because the
    dev database holds sunnycrest's own "St. Mary's Cemetery" and the unscoped query
    found it. Real contamination, caught by accident.

    A claim worth having is pinned by a test that NAMES it, so that the next reader can
    see it is checked rather than inferring it from an unrelated failure. "St. Mary's
    Cemetery" exists on both sunnycrest and testco in production; linking those would
    hand one tenant a route into another's record.
    """
    db, tid = tenant
    mine = _cemetery(db, tid, "St. Mary's Cemetery", city="Skaneateles", state="NY")
    other = Company(id=str(uuid.uuid4()), name="CEM1 Other2", slug=f"{SLUG}-other2",
                    vertical="manufacturing", is_active=True)
    db.add(other)
    db.flush()
    _cemetery(db, other.id, "St Marys Cemetery", city="Auburn", state="NY")

    got = cem.cemetery_detail(db, tid, mine.id, TODAY)
    assert "same_name" not in got, "another TENANT's same name is not this one's twin"
    assert "same_name" not in got["knows"]

    # The control: the same two names inside ONE tenant DO link.
    twin = _cemetery(db, tid, "St Marys Cemetery", city="Auburn", state="NY")
    again = cem.cemetery_detail(db, tid, mine.id, TODAY)
    assert again["same_name"]["cemetery_id"] == twin.id


def test_a_different_name_is_not_a_same_name_link(tenant):
    """The control for the test above — an absence that a broken comparison would also
    produce, so it needs the positive case beside it."""
    db, tid = tenant
    mary = _cemetery(db, tid, "St. Mary's Cemetery", city="Skaneateles")
    _cemetery(db, tid, "Oakwood Cemetery", city="Auburn")
    got = cem.cemetery_detail(db, tid, mary.id, TODAY)
    assert "same_name" not in got
    assert "same_name" not in got["knows"]


# ── the ask door ──────────────────────────────────────────────────────────────


def _ask(db, tid: str, phrase: str) -> dict:
    """`ask` with its required keyword-only arguments.

    ⚠️ EVERY ARGUMENT IS KEYWORD-ONLY AND NONE HAS A DEFAULT, which is deliberate on
    `ask`'s part — `today` without a default is what stopped a caller silently asking
    about the server's idea of today. The cost is that a test must name them all, so one
    helper names them once.

    ⚠️ AND `propose=None` IS THE POINT FOR THESE TESTS: the model door is skipped, so a
    phrase that reaches here and is not claimed by a rule comes back `unrecognized`
    rather than costing 900 ms and a model opinion.
    """
    from app.services.order_list.service import ask

    return ask(
        db, company_id=tid, user_id=None, role_slug=None, phrase=phrase,
        question=None, remove_pill_id=None, teach_phrase=None, today=TODAY,
        propose=None,
    )


def test_the_cemetery_rule_runs_before_the_customer_rule(tenant):
    """⚠️ A SHIPPED BEHAVIOUR CHANGED HERE, DELIBERATELY, AND THIS IS THE TEST THAT SAYS
    SO. On production sunnycrest "st marys" matches a CEMETERY and a CUSTOMER account of
    exactly the same name — both resolvers return one hit each, measured. Until
    2026-10-26 that phrase opened the ACCOUNT; it now opens the cemetery, because the
    dispatch makes the bar a cemetery entrance and its walk opens with "st marys. The
    pane opens."

    ⚠️ THE REVERSAL IS ONE BLOCK MOVING IN `service.ask`. If James wants the account
    back, this test is the one to argue with.
    """
    db, tid = tenant
    mary = _cemetery(db, tid, "St. Mary's Cemetery", city="Skaneateles", state="NY")
    account = _customer(db, tid, "St. Mary's Cemetery")
    got = _ask(db, tid, "st marys")
    assert got["kind"] == "open_cemetery"
    assert got["cemetery_id"] == mary.id
    # ⚠️ AND THE ACCOUNT IS STILL REACHABLE — by a name that is customer-only. The
    # control matters: a cemetery rule that swallowed every phrase would pass the
    # assertion above and break the Customer Pane entirely.
    _customer(db, tid, "Hopkins Funeral Home")
    opened = _ask(db, tid, "hopkins")
    assert opened["kind"] == "open_customer"
    assert account.id != opened["customer_id"]


def test_a_cemetery_name_still_loses_to_an_order_phrase(tenant):
    """Rules first, and the order rules are first of all. "oakwood order" opens an
    order; it must not be claimed as a cemetery."""
    db, tid = tenant
    oak = _cemetery(db, tid, "Oakwood Cemetery", city="Auburn")
    home = _customer(db, tid, "Hopkins Funeral Home")
    _order(db, tid, home.id, "SO-9", oak.id, status="confirmed",
           service_date=date(2026, 10, 28))
    got = _ask(db, tid, "oakwood order")
    assert got["kind"] != "open_cemetery"
