"""The Sales Order Pane's read, and the three ways an order opens.

James's dispatch, 2026-10-19 ("Sales Order Pane, slice 1"). The session rolls back;
nothing here commits.

⚠️ WHAT EACH TEST WOULD CATCH IS NAMED ON IT, because several of these assert an
ABSENCE — a row that should not render, a cancelled order that should not reach the
list — and an absence is satisfied by a pane that renders nothing at all. Every absence
test here sits beside a positive control in the same function.
"""
from __future__ import annotations

import os
import uuid
from datetime import date, datetime, time, timedelta, timezone
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
from app.models.sales_order import SalesOrder, SalesOrderLine
from app.services.order_list import detail as D
from app.services.order_list.question import order_number_query
from app.services.order_list.service import ask, load_facts, sales_order_summary
from app.services.order_list.stage import OrderFacts, matches
from app.services.order_list.question import OrderQuestion


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:
        session.close()
        pytest.skip(f"database unavailable: {exc}")
    try:
        yield session
    finally:
        session.rollback()
        session.close()


TODAY = date(2026, 10, 19)
FRIDAY = date(2026, 10, 23)


def _company(session, name="Pane Co") -> Company:
    company = Company(
        id=str(uuid.uuid4()), name=name, slug=f"sop-{uuid.uuid4().hex[:8]}",
        is_active=True, vertical="manufacturing",
    )
    session.add(company)
    session.flush()
    return company


def _order(
    session, company, *, number, customer_name="Hopkins Funeral Home", deceased="smith",
    status="confirmed", when=FRIDAY, service_time=time(11, 0), service_location="church",
    eta=None, grave=None, cemetery_name="St. Mary's Cemetery", cemetery_city="Skaneateles",
    vault="Monticello Burial Vault", vault_price="1405.00",
    equipment="Full Equipment", equipment_price="300.00",
    preference="statement_only",
):
    customer = Customer(
        id=str(uuid.uuid4()), company_id=company.id, name=customer_name,
        is_active=True, invoice_delivery_preference=preference,
    )
    session.add(customer)
    session.flush()
    # ⚠️ ONE CEMETERY PER (company, name, city) — `uq_cemetery_company_name_city` is a
    # real constraint and two orders in one test naming St. Mary's must share the row,
    # which is also what production looks like.
    cemetery = None
    if cemetery_name:
        cemetery = session.query(Cemetery).filter(
            Cemetery.company_id == company.id,
            Cemetery.name == cemetery_name,
            Cemetery.city == cemetery_city,
        ).first()
        if cemetery is None:
            cemetery = Cemetery(
                id=str(uuid.uuid4()), company_id=company.id, name=cemetery_name,
                city=cemetery_city,
            )
            session.add(cemetery)
            session.flush()
    lines = [(vault, vault_price)] + ([(equipment, equipment_price)] if equipment else [])
    total = sum(Decimal(p) for _d, p in lines)
    order = SalesOrder(
        id=str(uuid.uuid4()), company_id=company.id, number=number,
        customer_id=customer.id, order_date=datetime.now(timezone.utc), status=status,
        order_type="funeral", subtotal=total, tax_rate=Decimal("0"),
        tax_amount=Decimal("0"), total=total, deceased_name=deceased,
        scheduled_date=when, service_time=service_time,
        service_location=service_location, eta=eta, grave_location=grave,
        cemetery_id=cemetery.id if cemetery is not None else None,
    )
    session.add(order)
    session.flush()
    for i, (desc, price) in enumerate(lines):
        session.add(SalesOrderLine(
            id=str(uuid.uuid4()), sales_order_id=order.id, description=desc,
            quantity=Decimal("1"), unit_price=Decimal(price),
            line_total=Decimal(price), sort_order=i,
        ))
    session.flush()
    return order


def _detail(db, company, order, *, role_slug=None, user_id=None):
    return sales_order_summary(
        db, company.id, order.id, TODAY, role_slug=role_slug, user_id=user_id,
    )


def _rows(detail) -> dict[str, str]:
    return {row["label"]: row["value"] for row in detail["order"]}


# ───────────────────────────────────────────────────────────────────────────
# the shape
# ───────────────────────────────────────────────────────────────────────────

def test_a_confirmed_order_renders_the_whole_pane(db):
    company = _company(db)
    order = _order(db, company, number="SO-2026-0003")
    got = _detail(db, company, order)
    assert got is not None

    # the title, title-cased, which is the whole reason the dispatch says so: the
    # capture stores what was typed and all three production orders are lower case.
    assert got["title"] == "Smith"
    assert got["deceased_name"] == "smith", "the raw name stopped being carried"
    assert got["number"] == "SO-2026-0003"
    assert got["funeral_home"] == "Hopkins Funeral Home"

    assert got["state"]["kind"] == "steps"
    assert [(s["id"], s["done"]) for s in got["state"]["steps"]] == [
        ("confirmed", True), ("delivered", False), ("invoiced", False),
    ]

    rows = _rows(got)
    assert rows["Vault"] == "Monticello Burial Vault"
    assert rows["Cemetery"] == "St. Mary's Cemetery, Skaneateles"
    assert rows["Service"] == "Fri Oct 23 · 11:00 AM church"
    assert rows["Equipment"] == "Full Equipment"
    assert rows["Total"] == "$1,705"

    assert got["can_undo_confirm"] is True
    assert got["billing"]["total"] == "$1,705"
    assert [l["description"] for l in got["billing"]["lines"]] == [
        "Monticello Burial Vault", "Full Equipment",
    ]


def test_the_rows_are_in_the_dispatchs_order(db):
    """⚠️ THE ORDER IS SPECIFIED, NOT INCIDENTAL. James lists them Vault,
    Personalization, Cemetery, Service, Equipment, Total — a dict comparison would pass
    on any permutation.
    """
    company = _company(db)
    order = _order(db, company, number="SO-2026-0010", grave="Section 13")
    got = _detail(db, company, order)
    assert [row["label"] for row in got["order"]] == [
        "Vault", "Cemetery", "Service", "Grave", "Equipment", "Total",
    ]


def test_an_absent_fact_hides_its_row_and_a_present_one_shows(db):
    """⚠️ THE POSITIVE CONTROL IS THE POINT. Without it this is satisfied by a pane
    that renders no rows at all — which is what a broken assembler would produce.
    """
    company = _company(db)
    bare = _order(
        db, company, number="SO-2026-0011", cemetery_name=None, equipment=None,
        when=None, service_time=None, service_location=None,
    )
    rows = _rows(_detail(db, company, bare))
    assert "Cemetery" not in rows
    assert "Equipment" not in rows
    assert "Service" not in rows
    assert "Grave" not in rows
    # and nothing claims an emptiness
    assert "" not in rows.values()
    assert "—" not in rows.values()
    # ⚠️ THE CONTROL: the two facts this order DOES have still render.
    assert rows["Vault"] == "Monticello Burial Vault"
    assert rows["Total"] == "$1,405"


def test_personalization_renders_for_nothing_today_and_for_something_when_written(db):
    """⚠️ THE ROW IS CODED AND PRODUCTION HAS NO DATA FOR IT — 0 rows in
    `order_personalization_tasks` for Sunnycrest, measured 2026-10-19. So the absence is
    asserted AND the presence is forced, or "the row never appears" would be
    indistinguishable from "the row is not implemented".
    """
    from app.models.order_personalization_task import OrderPersonalizationTask

    company = _company(db)
    order = _order(db, company, number="SO-2026-0012")
    assert "Personalization" not in _rows(_detail(db, company, order))

    db.add(OrderPersonalizationTask(
        id=str(uuid.uuid4()), company_id=company.id, order_id=order.id,
        task_type="nameplate_only", print_name="SMITH",
    ))
    db.flush()
    assert _rows(_detail(db, company, order))["Personalization"] == "Nameplate only “SMITH”"


# ───────────────────────────────────────────────────────────────────────────
# steps, draft and cancelled
# ───────────────────────────────────────────────────────────────────────────

def test_a_draft_shows_as_draft_and_not_as_an_unfilled_step(db):
    company = _company(db)
    order = _order(db, company, number="SO-2026-0001", status="draft")
    got = _detail(db, company, order)
    assert got["state"] == {"kind": "draft", "label": "Draft"}
    assert "steps" not in got["state"]
    assert got["can_undo_confirm"] is False, "a draft offered Undo confirm"


def test_a_cancelled_order_opens_saying_cancelled_and_stays_out_of_the_list(db):
    """The pane can open a cancelled order; the list still cannot show one.

    ⚠️ CORRECTED AFTER A BREAK TEST. This docstring said "BOTH HALVES IN ONE TEST,
    because they are one decision" — that the list's exclusion depends on
    `include_cancelled` defaulting False. It does not. Flipping that default to True
    turned `test_include_cancelled_is_off_by_default` red and left THIS test green,
    because the list is protected THREE times over and `load_facts` is only the first:

        load_facts(include_cancelled=False)   excludes them in SQL
        stage.group_of                        `if facts.cancelled … return None`
        stage.matches                         `if facts.cancelled and not include…`

    So each of the three alone is sufficient for the list, and this test measures the
    OUTCOME rather than any one guard — which is worth having, and is not what the
    docstring claimed it was. The `group_of` half is asserted directly below so the
    guard that actually fires here is pinned by something.
    """
    company = _company(db)
    cancelled = _order(db, company, number="SO-2026-0002", status="cancelled",
                       deceased="demo walker")
    live = _order(db, company, number="SO-2026-0003")

    got = _detail(db, company, cancelled)
    assert got is not None, "the pane could not open a cancelled order"
    assert got["state"] == {"kind": "cancelled", "label": "Cancelled"}
    assert got["can_undo_confirm"] is False

    body = ask(
        db, company_id=company.id, user_id=None, role_slug="office",
        phrase="orders", question=None, remove_pill_id=None, teach_phrase=None,
        today=TODAY, propose=None,
    )
    ids = [row["id"] for row in body["orders"]]
    assert cancelled.id not in ids, "a cancelled order reached the default list"
    # ⚠️ THE CONTROL: the list is not simply empty.
    assert live.id in ids

    # ⚠️ THE GUARD THAT ACTUALLY FIRES HERE, pinned. See the docstring: `load_facts`'s
    # flag is not what keeps a cancelled order out of the default view — `group_of` is,
    # and nothing else was asserting it.
    from app.services.order_list.stage import group_of

    gone = load_facts(db, company.id, order_id=cancelled.id, include_cancelled=True)[0]
    here = load_facts(db, company.id, order_id=live.id)[0]
    assert group_of(gone, TODAY) is None, "group_of admitted a cancelled order"
    assert group_of(here, TODAY) is not None, "group_of refused a live order"


def test_include_cancelled_is_off_by_default(db):
    """The flag's default, asserted directly. A flipped default would make every list
    question start showing cancelled orders and only this would fail.
    """
    company = _company(db)
    _order(db, company, number="SO-2026-0002", status="cancelled")
    assert load_facts(db, company.id) == []
    assert len(load_facts(db, company.id, include_cancelled=True)) == 1


def test_delivered_and_invoiced_fill_their_steps(db):
    company = _company(db)
    order = _order(db, company, number="SO-2026-0020", status="delivered")
    order.delivered_at = datetime.now(timezone.utc)
    db.flush()
    steps = {s["id"]: s["done"] for s in _detail(db, company, order)["state"]["steps"]}
    assert steps == {"confirmed": True, "delivered": True, "invoiced": False}

    db.add(Invoice(
        id=str(uuid.uuid4()), company_id=company.id, customer_id=order.customer_id,
        sales_order_id=order.id, number=f"INV-{uuid.uuid4().hex[:6]}",
        invoice_date=datetime.now(timezone.utc),
        # ⚠️ `due_date` IS NOT NULLABLE on `invoices`. Leaving it off raised rather than
        # defaulting, which is the right behaviour and worth the extra line here.
        due_date=datetime.now(timezone.utc) + timedelta(days=30),
        status="sent",
        subtotal=order.total, tax_amount=Decimal("0"), total=order.total,
    ))
    db.flush()
    got = _detail(db, company, order)
    steps = {s["id"]: s["done"] for s in got["state"]["steps"]}
    assert steps == {"confirmed": True, "delivered": True, "invoiced": True}
    assert "Invoiced." in got["billing"]["sentence"]


# ───────────────────────────────────────────────────────────────────────────
# the service sentence
# ───────────────────────────────────────────────────────────────────────────

def test_the_cemetery_eta_appears_only_for_a_service_away_from_the_grave(db):
    company = _company(db)
    church = _order(db, company, number="SO-2026-0030", service_location="church",
                    eta=time(12, 30))
    assert _rows(_detail(db, company, church))["Service"] == (
        "Fri Oct 23 · 11:00 AM church · at the cemetery 12:30 PM"
    )
    # ⚠️ A GRAVESIDE SERVICE IS AT THE CEMETERY, so an ETA there is the same clock twice.
    graveside = _order(db, company, number="SO-2026-0031", service_location="graveside",
                       eta=time(12, 30))
    assert _rows(_detail(db, company, graveside))["Service"] == (
        "Fri Oct 23 · 11:00 AM graveside"
    )
    # and no ETA at all omits the clause rather than saying nothing about it
    none = _order(db, company, number="SO-2026-0032", service_location="church", eta=None)
    assert _rows(_detail(db, company, none))["Service"] == "Fri Oct 23 · 11:00 AM church"


def test_a_service_somewhere_else_says_where(db):
    company = _company(db)
    order = _order(db, company, number="SO-2026-0033", service_location="other")
    order.service_location_other = "the VFW hall"
    db.flush()
    assert "the VFW hall" in _rows(_detail(db, company, order))["Service"]


# ───────────────────────────────────────────────────────────────────────────
# billing
# ───────────────────────────────────────────────────────────────────────────

def test_the_month_is_the_SERVICE_month_not_this_one(db):
    """⚠️ AN ORDER WRITTEN IN OCTOBER FOR A NOVEMBER SERVICE BILLS IN NOVEMBER. Reading
    the clock instead of the order would be wrong for every order in the last week of a
    month, and right the rest of the time — which is why it is pinned.
    """
    company = _company(db)
    order = _order(db, company, number="SO-2026-0040", when=date(2026, 11, 6))
    assert _detail(db, company, order)["billing"]["sentence"] == (
        "Not invoiced yet. It goes out at month end with the November statement."
    )


def test_an_immediate_customer_reads_as_after_delivery_and_says_sending_is_off(db):
    """⚠️ THE OTHER BRANCH, WHICH RENDERS FOR NOTHING ON PRODUCTION TODAY — all 22
    customers platform-wide are `statement_only` (measured 2026-10-19). Forced here so
    the branch is exercised rather than asserted to exist.

    ⚠️ AND IT MUST NOT SAY "EMAILED" WHILE THE TENANT SWITCH IS OFF. The switch defaults
    off, so this is the live case, and `approval._describe_billing` makes the same
    distinction on the Review — the two sentences the office reads have to agree.
    """
    company = _company(db)
    order = _order(db, company, number="SO-2026-0041", preference="invoice_immediately")
    sentence = _detail(db, company, order)["billing"]["sentence"]
    assert sentence == (
        "Invoiced after delivery. Nothing is emailed — sending is off for this tenant."
    )

    company.set_setting("invoice_email_enabled", True)
    db.flush()
    assert _detail(db, company, order)["billing"]["sentence"] == (
        "Invoiced after delivery, and emailed to Hopkins."
    )


# ───────────────────────────────────────────────────────────────────────────
# the cemetery link
# ───────────────────────────────────────────────────────────────────────────

def test_the_cemetery_link_carries_the_id_to_open_it_with(db):
    """⚠️ THE SERVER SIDE OF THIS LINK WAS NEVER PINNED AT ALL, which is how it stayed
    inert without anything noticing.

    It shipped 2026-10-19 as `{"kind": "cemetery", "inert": True, "why": "The cemetery
    pane isn't built yet."}`. The FRONTEND had a test for that shape; the backend had
    none, so the only assertion in the tree was one whose own fixture supplied the
    `inert` flag — green, and about a payload the server might have stopped sending at
    any time.

    ⚠️ AND THE `inert` BRANCH IS NOW UNREACHABLE FROM HERE. `OrderRowLink.inert` still
    exists in the contract as the pattern for the NEXT unbuilt link; nothing produces it
    as of 2026-10-26, and a reader should know that rather than infer a live state.
    """
    company = _company(db)
    order = _order(db, company, number="SO-2026-0101")
    rows = {row["label"]: row for row in _detail(db, company, order)["order"]}
    link = rows["Cemetery"]["link"]
    assert link["kind"] == "cemetery"
    assert link["cemetery_id"], "the id is what retired the tooltip"
    assert "inert" not in link and "why" not in link
    # The id is the real cemetery's, not the order's or anything else's.
    cemetery = db.query(Cemetery).filter(
        Cemetery.company_id == company.id,
        Cemetery.name == "St. Mary's Cemetery",
    ).one()
    assert link["cemetery_id"] == cemetery.id


def test_an_order_with_no_cemetery_has_no_link_and_no_row(db):
    """The control. `_order_extras` LEFT JOINs, so this branch is reachable, and a link
    with no id would render a button that 404s."""
    company = _company(db)
    order = _order(db, company, number="SO-2026-0102", cemetery_name=None,
                   cemetery_city=None)
    rows = {row["label"]: row for row in _detail(db, company, order)["order"]}
    assert "Cemetery" not in rows, "an absent row rather than an empty one"


# ───────────────────────────────────────────────────────────────────────────
# the vault link
# ───────────────────────────────────────────────────────────────────────────

def test_the_vault_links_only_when_its_name_reaches_exactly_one_variant(db):
    """⚠️ THE ONLY ROUTE TO THE PRODUCT PANE, and it goes through the NAME because
    `products.variant_template_id` is NULL on all 39 products platform-wide.

    ⚠️ IT IS EXERCISED THROUGH `_vault_link` WITH A STUBBED RESOLVER rather than against
    the real catalog, because the catalog is platform data this test does not own — a
    test asserting "Monticello resolves to one" would start failing the day a second
    Monticello variant is added, for a reason that is not a defect.
    """
    class _Candidate:
        def __init__(self, vid):
            self.variant_template_id = vid

    class _Resolution:
        def __init__(self, candidates):
            self.candidates = candidates

    import app.services.product_name_resolver as resolver

    seen: list[str] = []

    def fake_resolve(_index, phrase):
        seen.append(phrase)
        return _Resolution(LOOKUP.get(phrase, []))

    LOOKUP = {
        "Monticello Burial Vault": [_Candidate("one-variant")],
        "Continental Burial Vault": [_Candidate("size-a"), _Candidate("size-b")],
        "Full Equipment": [],
    }
    old_resolve, old_index = resolver.resolve, resolver.build_index
    resolver.resolve, resolver.build_index = fake_resolve, (lambda _db: object())
    try:
        assert D._vault_link(db, "Monticello Burial Vault") == "one-variant"
        # ⚠️ AMBIGUOUS MEANS NO LINK, not the first one. Same rule as the bar, where
        # several matches become a numbered pick and never a guess.
        assert D._vault_link(db, "Continental Burial Vault") is None
        assert D._vault_link(db, "Full Equipment") is None
        assert D._vault_link(db, "") is None
        assert seen == [
            "Monticello Burial Vault", "Continental Burial Vault", "Full Equipment",
        ], "the empty name reached the resolver"
    finally:
        resolver.resolve, resolver.build_index = old_resolve, old_index


def test_a_resolver_failure_does_not_break_the_read(db):
    import app.services.product_name_resolver as resolver

    def boom(_index, _phrase):
        raise RuntimeError("the index is unavailable")

    old = resolver.resolve
    resolver.resolve = boom
    try:
        assert D._vault_link(db, "Monticello Burial Vault") is None
    finally:
        resolver.resolve = old


# ───────────────────────────────────────────────────────────────────────────
# equipment vs vault
# ───────────────────────────────────────────────────────────────────────────

def test_the_equipment_labels_come_from_the_capture_schema(db):
    """⚠️ DERIVED, NOT RETYPED. A package added to `EQUIPMENT_PACKAGES` must be
    classified without a second edit here, and `none` must never be a line.
    """
    from app.services.capture.schema import EQUIPMENT_PACKAGES

    expected = {label.casefold() for slug, label in EQUIPMENT_PACKAGES if slug != "none"}
    assert D.EQUIPMENT_LABELS == expected
    assert "none" not in D.EQUIPMENT_LABELS
    assert D.is_equipment_line("Full Equipment")
    assert D.is_equipment_line("  full equipment  ")
    assert not D.is_equipment_line("Monticello Burial Vault")
    assert not D.is_equipment_line(None)


def test_the_vault_is_the_most_expensive_NON_equipment_line():
    """⚠️ WITHOUT THE NON-EQUIPMENT FILTER, AN ORDER WHOSE EQUIPMENT COSTS MORE THAN ITS
    VAULT WOULD SHOW THE EQUIPMENT AS ITS VAULT. No such order exists on production
    today, which is exactly why this is a unit test over hand-built lines rather than a
    hope.
    """
    lines = [
        {"description": "Urn Vault - Standard", "line_total": Decimal("425.00")},
        {"description": "Full Equipment", "line_total": Decimal("900.00")},
    ]
    vault, equipment, rest = D.split_lines(lines)
    assert vault["description"] == "Urn Vault - Standard"
    assert [l["description"] for l in equipment] == ["Full Equipment"]
    assert rest == []


# ───────────────────────────────────────────────────────────────────────────
# history
# ───────────────────────────────────────────────────────────────────────────

def test_an_order_with_no_audit_trail_omits_the_history_key(db):
    company = _company(db)
    order = _order(db, company, number="SO-2026-0050")
    assert "history" not in _detail(db, company, order)


def test_history_reads_the_created_row_and_says_an_update_recorded_nothing(db):
    """⚠️ THE `updated` ROWS CARRY NO DETAIL, MEASURED: Sunnycrest has 2 of them and
    both have `changes` NULL, because `sales_service.update_sales_order` calls
    `log_action` without a `changes` argument. The pane says so rather than implying it
    knows what changed.
    """
    from app.services import audit_service

    company = _company(db)
    order = _order(db, company, number="SO-2026-0051")
    audit_service.log_action(
        db, company.id, "created", "sales_order", order.id, user_id=None,
        changes={"number": order.number, "total": "1705.00", "source": "opas_capture"},
    )
    audit_service.log_action(
        db, company.id, "updated", "sales_order", order.id, user_id=None,
    )
    db.flush()

    history = _detail(db, company, order)["history"]
    assert [e["action"] for e in history] == ["Created", "Updated"]
    # ⚠️ "$1,705" NOT "$1,705.00" — `stage.format_money` drops the cents on a whole
    # amount, which is also what the Total row shows. My first expectation here was
    # `$1,705.00` and the test caught the disagreement rather than the code.
    assert history[0]["detail"] == "$1,705 · from Opas capture"
    assert "detail_absent" not in history[0]
    assert history[1]["detail_absent"] == D.NO_DETAIL_NOTE
    assert "detail" not in history[1]


def test_unparseable_changes_do_not_break_the_read():
    assert D._history_detail("not json at all") is None
    assert D._history_detail("[1,2,3]") is None
    assert D._history_detail(None) is None
    # ⚠️ THE CONTROL: real JSON still produces a detail, or the three Nones above would
    # pass against a function that always returns None.
    assert D._history_detail('{"total": "12.00"}') == "$12"


# ───────────────────────────────────────────────────────────────────────────
# opening by order number
# ───────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("typed", ["SO-2026-0002", "so-2026-0002", "so 2026 0002",
                                   "2026-0002", "0002", "open SO-2026-0002"])
def test_every_shape_of_an_order_number_names_the_same_order(typed):
    assert order_number_query(typed) == "0002"


@pytest.mark.parametrize("typed", ["2", "12", "orders", "hopkins order", "",
                                   "going out friday"])
def test_what_is_not_an_order_number(typed):
    """⚠️ "2" AND "12" ARE EXCLUDED ON PURPOSE — the bar's ⌘1..9 pick settles those, and
    a 1-2 digit request would collide with answering "which one?".
    """
    assert order_number_query(typed) is None


def test_typing_an_order_number_opens_that_order(db):
    company = _company(db)
    _order(db, company, number="SO-2026-0001", status="draft")
    wanted = _order(db, company, number="SO-2026-0002")

    for phrase in ("SO-2026-0002", "0002"):
        body = ask(
            db, company_id=company.id, user_id=None, role_slug="office",
            phrase=phrase, question=None, remove_pill_id=None, teach_phrase=None,
            today=TODAY, propose=None,
        )
        assert body == {"kind": "open_order", "open_order_id": wanted.id}, phrase


def test_a_cancelled_order_can_be_opened_by_its_number(db):
    """A stale note on a desk points at a cancelled order. "No such order" would be a
    lie; the pane says Cancelled.
    """
    company = _company(db)
    gone = _order(db, company, number="SO-2026-0002", status="cancelled")
    body = ask(
        db, company_id=company.id, user_id=None, role_slug="office",
        phrase="SO-2026-0002", question=None, remove_pill_id=None, teach_phrase=None,
        today=TODAY, propose=None,
    )
    assert body == {"kind": "open_order", "open_order_id": gone.id}


def test_an_unknown_number_says_so_and_does_not_open_anything(db):
    company = _company(db)
    _order(db, company, number="SO-2026-0002")
    body = ask(
        db, company_id=company.id, user_id=None, role_slug="office",
        phrase="0404", question=None, remove_pill_id=None, teach_phrase=None,
        today=TODAY, propose=None,
    )
    assert body["kind"] == "unrecognized"
    assert "0404" in body["hint"]


def test_two_years_ending_in_the_same_digits_become_a_pick(db):
    """⚠️ SUNNYCREST CANNOT REACH THIS YET — it has one year of orders. Written now
    rather than discovered in January.
    """
    company = _company(db)
    _order(db, company, number="SO-2025-0002", deceased="older smith")
    _order(db, company, number="SO-2026-0002", deceased="newer smith")
    body = ask(
        db, company_id=company.id, user_id=None, role_slug="office",
        phrase="0002", question=None, remove_pill_id=None, teach_phrase=None,
        today=TODAY, propose=None,
    )
    assert body["kind"] == "picks"
    assert len(body["picks"]) == 2
    assert all("SO-202" in p["label"] for p in body["picks"])


# ───────────────────────────────────────────────────────────────────────────
# opening by name
# ───────────────────────────────────────────────────────────────────────────

def test_a_funeral_homes_name_opens_its_one_order(db):
    """⚠️ THIS IS JAMES'S OWN WALK — "type 'riverside order'" — and it returned
    "No order for Riverside" before 2026-10-19, because `_open_decedent` matched the
    DECEDENT and nothing else.
    """
    company = _company(db)
    riverside = _order(
        db, company, number="SO-2026-0004", customer_name="Riverside Memorial Chapel",
        deceased="hart",
    )
    _order(db, company, number="SO-2026-0005", customer_name="Hopkins Funeral Home")
    body = ask(
        db, company_id=company.id, user_id=None, role_slug="office",
        phrase="riverside order", question=None, remove_pill_id=None,
        teach_phrase=None, today=TODAY, propose=None,
    )
    assert body == {"kind": "open_order", "open_order_id": riverside.id}


def test_a_surname_still_opens_the_decedents_order(db):
    company = _company(db)
    order = _order(db, company, number="SO-2026-0006", deceased="walter penn")
    body = ask(
        db, company_id=company.id, user_id=None, role_slug="office",
        phrase="penn order", question=None, remove_pill_id=None, teach_phrase=None,
        today=TODAY, propose=None,
    )
    assert body == {"kind": "open_order", "open_order_id": order.id}


def test_a_cemetery_and_a_vault_name_open_an_order_too(db):
    company = _company(db)
    order = _order(db, company, number="SO-2026-0007", cemetery_name="Fort Hill Cemetery",
                   cemetery_city="Auburn", deceased="unique one")
    for phrase in ("fort hill order", "monticello burial vault order"):
        body = ask(
            db, company_id=company.id, user_id=None, role_slug="office",
            phrase=phrase, question=None, remove_pill_id=None, teach_phrase=None,
            today=TODAY, propose=None,
        )
        assert body == {"kind": "open_order", "open_order_id": order.id}, phrase


def test_several_matches_become_a_numbered_pick_carrying_the_number(db):
    company = _company(db)
    _order(db, company, number="SO-2026-0008", customer_name="Hopkins Funeral Home",
           deceased="one", when=FRIDAY)
    _order(db, company, number="SO-2026-0009", customer_name="Hopkins Funeral Home",
           deceased="two", when=FRIDAY + timedelta(days=1))
    body = ask(
        db, company_id=company.id, user_id=None, role_slug="office",
        phrase="hopkins order", question=None, remove_pill_id=None, teach_phrase=None,
        today=TODAY, propose=None,
    )
    assert body["kind"] == "picks"
    assert [p["n"] for p in body["picks"]] == [1, 2]
    # ⚠️ THE NUMBER IS ON THE LABEL. Two orders with no decedent recorded would
    # otherwise be two identical choices.
    assert "SO-2026-0008" in body["picks"][0]["label"]
    assert "SO-2026-0009" in body["picks"][1]["label"]
    assert all("order_id" in p for p in body["picks"])


def test_a_live_order_is_preferred_over_a_cancelled_namesake(db):
    """⚠️ TWO PASSES, NOT ONE. Searching cancelled orders in the same pass would make a
    cancelled order compete with a live one for the same name.
    """
    company = _company(db)
    _order(db, company, number="SO-2026-0002", customer_name="Riverside Memorial Chapel",
           deceased="old", status="cancelled")
    live = _order(db, company, number="SO-2026-0004",
                  customer_name="Riverside Memorial Chapel", deceased="new")
    body = ask(
        db, company_id=company.id, user_id=None, role_slug="office",
        phrase="riverside order", question=None, remove_pill_id=None,
        teach_phrase=None, today=TODAY, propose=None,
    )
    assert body == {"kind": "open_order", "open_order_id": live.id}


def test_a_name_with_only_a_cancelled_order_still_opens_it(db):
    company = _company(db)
    gone = _order(db, company, number="SO-2026-0002",
                  customer_name="Riverside Memorial Chapel", status="cancelled")
    body = ask(
        db, company_id=company.id, user_id=None, role_slug="office",
        phrase="riverside order", question=None, remove_pill_id=None,
        teach_phrase=None, today=TODAY, propose=None,
    )
    assert body == {"kind": "open_order", "open_order_id": gone.id}


def test_a_name_that_matches_nothing_says_so(db):
    company = _company(db)
    _order(db, company, number="SO-2026-0002")
    body = ask(
        db, company_id=company.id, user_id=None, role_slug="office",
        phrase="nobody order", question=None, remove_pill_id=None, teach_phrase=None,
        today=TODAY, propose=None,
    )
    assert body["kind"] == "unrecognized"
    assert "Nobody" in body["hint"]


def test_matches_still_refuses_a_cancelled_order_by_default():
    """The flag on `matches`, asserted at the function. Every LIST caller depends on
    the default, so a flipped default would change every question at once.
    """
    facts = OrderFacts(
        id="x", number="SO-1", deceased_name="smith", funeral_home="Hopkins",
        status="cancelled",
    )
    question = OrderQuestion(decedent="smith", title="t")
    # `today` is required since 2026-10-23 (the going_out fix) and is not load-bearing
    # here — this order has no service date, and the cancelled refusal is the first
    # clause in `matches`, before any date is read.
    assert matches(facts, question, TODAY) is False
    assert matches(facts, question, TODAY, include_cancelled=True) is True


# ───────────────────────────────────────────────────────────────────────────
# the boundary the pane must not cross
# ───────────────────────────────────────────────────────────────────────────

def test_another_tenants_order_is_not_readable(db):
    ours = _company(db, "Ours")
    theirs = _company(db, "Theirs")
    mine = _order(db, ours, number="SO-2026-0060")
    yours = _order(db, theirs, number="SO-2026-0061")
    assert _detail(db, ours, mine) is not None
    assert sales_order_summary(db, ours.id, yours.id, TODAY) is None
    assert sales_order_summary(db, theirs.id, mine.id, TODAY) is None
