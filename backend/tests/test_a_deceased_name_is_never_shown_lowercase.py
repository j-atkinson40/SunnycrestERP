"""No pane shows a deceased name as it was typed. James 2026-10-15, re-ruled 2026-10-29.

⚠️ THE RULING HAD ALREADY REACHED TWO SURFACES AND MISSED THE PANES. "Title-cased
wherever displayed" was applied on 2026-10-15 at the API RESPONSE BOUNDARY — a
validator on `SalesOrderResponse` — deliberately, because
`test_a_name_is_shown_the_same_way_everywhere.py` records that enumerating render
sites is "exhaustive on the day it was written and silently stop[s] being so". That
reasoning was right and the boundary was the wrong one for Opas: the panes do not
render through those schemas, they build their own dicts.

⚠️ AND THE PANES CARRIED A SECOND IMPLEMENTATION OF THE CASING RULE, which is the
reason ONE pane was right and four were not. `order_list/detail.py::title_case_name`
guarded per word; `display_name.title_case_for_display` guards on the whole string.
Measured before collapsing them, they disagreed on exactly two shapes — all-caps
"MCLEOD" and mixed "mary SMITH" — plus None (None vs ""). Neither divergent shape is
ruled, so the ruled module's guard was kept and the duplicate deleted.

⚠️ FOUND BY JAMES'S WALK, NOT BY A TEST, which is the point of this file. The Order
List pane and the Cemetery pane's "Coming up here" rendered "smith" and "smith it"
on production while every test was green.

HOW THIS FILE IS MEANT TO HOLD. Two layers, because each catches what the other
cannot:

  1. A BEHAVIOURAL test per pane, driven through the pane's own entry point with a
     lowercase name seeded, asserting the raw lowercase string appears NOWHERE in the
     payload. It walks the whole structure rather than naming keys, so a pane that
     grows a new field carrying the name is covered without this file being edited.

  2. A TEXTUAL ratchet forbidding the two idioms that produced the bug — the raw
     `deceased_name or "Unnamed"` fallback, and any second title-casing helper. This
     is what catches a FIFTH pane nobody has written yet, which layer 1 cannot.

⚠️ THE PANE LIST IS TAKEN FROM THE ROUTER, NOT FROM MEMORY. `api/routes/
order_list_pane.py` exposes exactly four pane-producing endpoints; those four are the
four exercised here. A pane reachable some other way is outside this file's
population, and layer 2 is what covers that gap.
"""

from __future__ import annotations

import os
import pathlib
import re
import uuid
from datetime import date, timedelta
from urllib.parse import urlparse

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.models.cemetery import Cemetery
from app.models.company import Company
from app.models.customer import Customer
from app.models.sales_order import SalesOrder
from app.services.display_name import (
    UNNAMED,
    deceased_for_display,
    title_case_for_display,
)
from app.services.order_list.cemetery import cemetery_detail
from app.services.order_list.customer import customer_detail
from app.services.order_list.service import ask, sales_order_summary

from tests._cleanup import purge_companies_by_slug

#: The stored value. Lowercase on purpose — this is what the office types, and what
#: production actually holds: all five Sunnycrest orders carry a lowercase name.
TYPED = "smith jones"
SHOWN = "Smith Jones"

TODAY = date(2026, 10, 29)
SLUG = "tc-lowercase-deceased"


def _local_only() -> None:
    """⚠️ THE SAME GUARD EVERY WRITING TEST IN THIS SUITE CARRIES. This file INSERTS."""
    host = (urlparse(os.environ.get("DATABASE_URL", "")).hostname or "")
    assert host in ("localhost", "127.0.0.1", "::1", ""), host


@pytest.fixture()
def seeded():
    """One order, one customer, one cemetery, a lowercase deceased name."""
    _local_only()
    db = SessionLocal()
    purge_companies_by_slug(db, SLUG)
    cid = str(uuid.uuid4())
    db.add(Company(id=cid, name="Lowercase Deceased Co", slug=SLUG, vertical="manufacturing"))
    db.flush()

    cust = Customer(
        id=str(uuid.uuid4()), company_id=cid, name="Hopkins Funeral Home",
        account_number="FH-900", customer_type="funeral_home",
    )
    cem = Cemetery(
        id=str(uuid.uuid4()), company_id=cid, name="St. Mary's Cemetery",
        city="Skaneateles", state="NY", is_active=True,
    )
    db.add_all([cust, cem])
    db.flush()

    order = SalesOrder(
        id=str(uuid.uuid4()), company_id=cid, number="SO-LC-0001",
        customer_id=cust.id, status="confirmed", order_date=TODAY,
        deceased_name=TYPED, scheduled_date=TODAY + timedelta(days=2),
        cemetery_id=cem.id, subtotal=0, tax_rate=0, tax_amount=0, total=0,
    )
    db.add(order)
    db.commit()

    yield db, cid, cust.id, cem.id, order.id

    db.rollback()
    purge_companies_by_slug(db, SLUG)
    db.commit()
    db.close()


def _strings(node) -> list[str]:
    """Every string anywhere in a pane payload, at any depth.

    ⚠️ IT WALKS RATHER THAN NAMING KEYS, so a pane that grows a new field carrying the
    deceased name is covered without this file changing. Naming keys is the
    constructed-scope failure that let the bug ship in the first place.
    """
    out: list[str] = []
    if isinstance(node, str):
        out.append(node)
    elif isinstance(node, dict):
        for k, v in node.items():
            out.extend(_strings(k))
            out.extend(_strings(v))
    elif isinstance(node, (list, tuple, set)):
        for v in node:
            out.extend(_strings(v))
    return out


# ── layer 1: behavioural, one per pane the router exposes ────────────────────


def test_the_STORED_value_really_is_lowercase(seeded):
    """⚠️ THE POSITIVE CONTROL, AND IT GOES FIRST. Every assertion below is an ABSENCE —
    "the lowercase string does not appear". An absence is satisfied by a fixture that
    never stored a lowercase name at all, or by a pane that returned nothing. This
    pins the premise so the absences below mean something."""
    db, cid, _, _, oid = seeded
    stored = db.execute(
        text("SELECT deceased_name FROM sales_orders WHERE id = :i"), {"i": oid}
    ).scalar()
    assert stored == TYPED, stored
    assert stored != SHOWN, "the ruling forbids changing what is STORED"


#: Keys that carry the name AS STORED on purpose, with the pane displaying a different
#: key instead. ONE entry, and it has to stay that way to be meaningful.
#:
#: ⚠️ THIS EXISTS BECAUSE THE FIRST VERSION OF THIS FILE WAS TOO BLUNT AND BROKE A
#: DELIBERATE CONTRACT. The whole-payload walk below made the Sales Order Pane's
#: top-level `deceased_name` title-cased too, which turned
#: `test_sales_order_pane.py`'s "the raw name stopped being carried" red. That key is
#: not rendered — `SalesOrderPane.tsx:229` renders `row.title` — so the ruling does not
#: reach it. Measured in the frontend rather than assumed: the three keys that ARE
#: rendered are `OrderListPane.tsx:196`, `CemeteryPane.tsx:365`, `CustomerPane.tsx:328`,
#: all of them row-level `deceased_name`, and all of them fixed.
RAW_BY_CONTRACT = {("sales_order", "deceased_name")}


def test_the_sales_order_pane_SHOWS_title_and_CARRIES_the_raw_name(seeded):
    """⚠️ THE EXEMPTION, PINNED, so it cannot quietly widen. If this pane ever starts
    displaying `deceased_name`, this test still passes — which is why the walk below
    only skips the key rather than skipping the pane."""
    db, cid, _, _, oid = seeded
    got = sales_order_summary(db, cid, oid, TODAY)
    assert got is not None
    assert got["title"] == SHOWN, got["title"]
    assert got["deceased_name"] == TYPED, (
        "the raw name stopped being carried — see test_sales_order_pane.py, which pins "
        "this contract with the same words"
    )


@pytest.mark.parametrize("pane", ["sales_order", "customer", "cemetery"])
def test_no_pane_payload_CONTAINS_the_lowercase_name(seeded, pane):
    db, cid, cust_id, cem_id, oid = seeded
    if pane == "sales_order":
        got = sales_order_summary(db, cid, oid, TODAY)
    elif pane == "customer":
        got = customer_detail(db, cid, cust_id, TODAY)
    else:
        got = cemetery_detail(db, cid, cem_id, TODAY)

    assert got is not None, f"{pane} pane returned nothing — the test would pass vacuously"
    if isinstance(got, dict):
        got = {k: v for k, v in got.items() if (pane, k) not in RAW_BY_CONTRACT}
    found = _strings(got)
    # ⚠️ A SECOND CONTROL, per pane: the pane must actually be SHOWING this person,
    # or "the lowercase name is absent" is true of a payload about someone else.
    assert any(SHOWN in s for s in found), (
        f"the {pane} pane never mentions {SHOWN!r}, so the absence of {TYPED!r} "
        f"proves nothing about casing"
    )
    offenders = [s for s in found if TYPED in s]
    assert not offenders, (
        f"the {pane} pane rendered the deceased name as stored: {offenders!r} — "
        f"James 2026-10-15, title-cased wherever displayed"
    )


def test_the_cemetery_pane_COMING_UP_line_is_title_cased(seeded):
    """⚠️ THE EXACT LINE IN JAMES'S SCREENSHOT. It is asserted separately from the
    whole-payload walk above because it is built by a different code path — a
    `" · ".join(p for p in (...) if p)` — and that `if p` is why this site takes
    `title_case_for_display` and not `deceased_for_display`: feeding "Unnamed" into a
    join that is supposed to OMIT an absent name would put the word on the line.

    ⚠️ AND THE KEY PATH HERE WAS WRONG IN THE FIRST DRAFT, which the control caught.
    `next_delivery` is NOT top-level on the pane — it is nested under `knows`, built by
    `what_opas_knows`. Asserting `got["next_delivery"]` read None and the test failed
    for the wrong reason; had the control been `if nxt:` instead of `assert nxt`, it
    would have PASSED while checking nothing. Both of the pane's coming-up surfaces are
    asserted below, because they are built by two different code paths.
    """
    db, cid, _, cem_id, _ = seeded
    got = cemetery_detail(db, cid, cem_id, TODAY)
    assert got is not None

    # (a) the "Coming up here" ROWS
    coming = got.get("coming")
    assert coming, "no coming rows — the scheduled order should produce one"
    names = [r.get("deceased_name") for r in coming]
    assert SHOWN in names, names
    assert TYPED not in names, names

    # (b) the next-delivery LINE, under `knows`, joined by a different code path
    nxt = (got.get("knows") or {}).get("next_delivery")
    assert nxt, "no knows.next_delivery — the scheduled order should produce one"
    assert TYPED not in nxt["line"], nxt["line"]
    assert SHOWN in nxt["line"], nxt["line"]


def test_an_ABSENT_name_does_not_become_the_word_Unnamed_on_that_line(seeded):
    """⚠️ THE OTHER HALF, AND IT IS THE REGRESSION THE FIX COULD EASILY HAVE CAUSED.
    Wiring "Coming up here" to `deceased_for_display` would have been the obvious
    edit and would have printed "Unnamed" into a label whose whole design is to leave
    the name out when there isn't one."""
    db, cid, _, cem_id, oid = seeded
    db.execute(text("UPDATE sales_orders SET deceased_name = NULL WHERE id = :i"), {"i": oid})
    db.commit()
    got = cemetery_detail(db, cid, cem_id, TODAY)
    assert got is not None
    nxt = (got.get("knows") or {}).get("next_delivery")
    assert nxt, "the order is still scheduled, so the line should still be built"
    assert UNNAMED not in nxt["line"], (
        f"an absent name leaked {UNNAMED!r} onto the coming-up line: {nxt['line']!r}"
    )


def test_the_ORDER_LIST_and_the_REPLY_LINE_are_covered_BEHAVIOURALLY(seeded):
    """⚠️ ADDED BECAUSE THE BREAK TESTS SHOWED THESE TWO SITES HAD NO BEHAVIOURAL COVER.
    Reverting `stage.py`'s rows and `service.py`'s pick label to the raw idiom turned
    exactly ONE test red — the TEXTUAL ratchet — and nothing else. The ratchet is worth
    having, but it only recognises that one literal: a regression written as
    `facts.deceased_name if facts.deceased_name else "Unnamed"` would have passed every
    check in this file while rendering lowercase on the two surfaces James named.

    ⚠️ IT DRIVES `ask`, WHICH IS THE ORDER LIST AND THE REPLY LINE AT ONCE — the pane
    rows come from `stage.py` and the pick labels from `service.py`, and both are in
    this one payload.

    ⚠️ THE PHRASE MATTERS AND "hopkins" DOES NOT WORK, which the control caught. A bare
    customer name is a deterministic rule that opens the CUSTOMER pane, so the payload
    came back `{customer_id, customer_name, kind}` with no rows in it at all — the
    absence of the lowercase name would have been true and meaningless. "orders" is a
    phrase that returns the list.
    """
    db, cid, _, _, _ = seeded
    got = ask(
        db, company_id=cid, user_id=None, role_slug="admin",
        phrase="orders", question=None, remove_pill_id=None,
        teach_phrase=None, today=TODAY, propose=None,
    )
    found = _strings(got)
    assert any(SHOWN in s for s in found), (
        f"the ask payload never mentions {SHOWN!r}, so the absence of {TYPED!r} would "
        f"prove nothing. payload keys: {sorted(got)}"
    )
    offenders = [s for s in found if TYPED in s]
    assert not offenders, (
        f"the Order List / reply line rendered the deceased name as stored: {offenders!r}"
    )


def test_a_PICK_LABEL_is_title_cased(seeded):
    """⚠️ THE REPLY LINE'S NUMBERED CHOICES, and a THIRD attempt at covering them.
    `service.py` builds a pick label as "<deceased> · <number> · <when>", and reverting
    that site turned only the textual ratchet red — twice. "orders" returns the list
    rather than picks, and a single match OPENS the order instead of offering a choice:
    `_pick_or_open` returns `open_order` when `len(found) == 1`.

    ⚠️ SO THE PICK PATH NEEDS TWO ORDERS SHARING A NUMBER SUFFIX. That is the condition,
    and it is the reason this test seeds a second order rather than reusing the fixture
    as-is — without it the assertion is about a payload that has no labels in it.
    """
    db, cid, cust_id, cem_id, _ = seeded
    # a second order whose number ends in the same four digits as SO-LC-0001
    db.add(SalesOrder(
        id=str(uuid.uuid4()), company_id=cid, number="SO-ZZ-0001",
        customer_id=cust_id, status="confirmed", order_date=TODAY,
        deceased_name=TYPED, scheduled_date=TODAY + timedelta(days=5),
        cemetery_id=cem_id, subtotal=0, tax_rate=0, tax_amount=0, total=0,
    ))
    db.commit()

    got = ask(
        db, company_id=cid, user_id=None, role_slug="admin",
        phrase="0001", question=None, remove_pill_id=None,
        teach_phrase=None, today=TODAY, propose=None,
    )
    assert got.get("kind") == "picks", (
        f"expected numbered picks, got {got.get('kind')!r} — two orders share the "
        f"suffix, so this should be a choice and the labels should exist"
    )
    labels = [pk["label"] for pk in got["picks"]]
    assert labels, got
    assert all(SHOWN in lab for lab in labels), labels
    assert not [lab for lab in labels if TYPED in lab], labels


# ── layer 2: the ratchet, for the pane nobody has written yet ────────────────

_APP = pathlib.Path(__file__).resolve().parent.parent / "app"


def _py_files():
    return sorted(p for p in _APP.rglob("*.py"))


def test_NO_MODULE_spells_the_Unnamed_FALLBACK_ITSELF():
    """⚠️ THIS IS THE RATCHET THAT CATCHES A FIFTH PANE. The behavioural tests above
    cover the four panes the router exposes today; they cannot cover one that does not
    exist yet. The idiom below is what every broken pane had in common, so forbidding
    it is what makes the next pane use the helper.

    ⚠️ AND IT MUST FAIL WHEN IT MATCHES NOTHING TOO, or a rename of the constant
    silently points it at empty air. The positive control is that
    `deceased_for_display` is findable and is the only place `UNNAMED` is combined
    with a name.
    """
    pattern = re.compile(r'deceased_name\s*or\s*["\']Unnamed["\']')
    offenders = [
        f"{p.relative_to(_APP)}:{i}"
        for p in _py_files()
        for i, line in enumerate(p.read_text().splitlines(), 1)
        if pattern.search(line)
    ]
    assert offenders == [], (
        f"these spell the Unnamed fallback themselves instead of calling "
        f"`display_name.deceased_for_display`: {offenders}. One shared display helper, "
        f"by ruling (James, 2026-10-29)."
    )

    # positive control — the scanner can see, and the helper really is reachable
    helper = (_APP / "services" / "display_name.py").read_text()
    assert "def deceased_for_display" in helper
    assert f'return title_case_for_display(value) or UNNAMED' in helper, (
        "the helper no longer combines the title-case rule with the Unnamed fallback, "
        "so forbidding the raw idiom no longer routes anywhere"
    )


def test_there_is_exactly_ONE_title_CASING_HELPER_IN_THE_WHOLE_APP():
    """⚠️ THE DEFECT ITSELF, RATCHETED. Two implementations is why one pane was right
    and four were wrong, and a grep for the ruling's own function name would have
    reported the rule as applied — `detail.py` had its own, under its own name.

    ⚠️ ASSERTS THE LOCATION, NOT A COUNT, so moving the definition elsewhere fails and
    deleting it entirely fails too. A bare `<= 1` is satisfied by zero.
    """
    found = []
    for p in _py_files():
        src = p.read_text()
        for m in re.finditer(r"^def (\w*title_case\w*)\(", src, re.M):
            found.append(f"{p.relative_to(_APP)}::{m.group(1)}")
    assert found == ["services/display_name.py::title_case_for_display"], (
        f"title-casing helpers found: {found or 'NONE'}. There must be exactly one, in "
        f"services/display_name.py, so a ruling about casing reaches every surface at "
        f"once — four panes were wrong because detail.py had a second one."
    )


def test_the_two_helpers_DISAGREE_about_nothing_a_pane_can_produce():
    """⚠️ NOT A TAUTOLOGY: it pins the relationship the ratchet above assumes. If
    `deceased_for_display` ever stops delegating, the single-implementation ratchet
    would still pass while two rules existed again — one of them inlined."""
    for typed in ("smith jones", "smith", "o'brien", "smith-jones", "deSoto", "MacLeod"):
        assert deceased_for_display(typed) == title_case_for_display(typed)
    # and the one place they must differ: absence
    assert title_case_for_display(None) is None
    assert deceased_for_display(None) == UNNAMED
