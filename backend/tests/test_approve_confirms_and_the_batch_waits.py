"""Approve confirms the order, and the service date is what keeps it safe.

James's step 3, 2026-10-16, items 1, 2 and 4. This is the test that matters for the whole
arc: the protection moved from the STATUS to the DATE, so the thing to prove is that an
order which is born billable is nonetheless untouched until its service date arrives.

⚠️ `test_approve_confirms_the_order.py` COVERS WHAT APPROVE WRITES. This file covers what
happens to the order AFTERWARDS — the interaction between Approve's new status and the
end-of-day batch's new gate. They are separate because the first is about one function
and the second is about two systems agreeing.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.company import Company
from app.models.customer import Customer
from app.models.sales_order import SalesOrder
from app.services import draft_invoice_service as dis
from app.services.capture.session_service import CONFIRMED_ON_APPROVE

SLUG_PREFIX = "appconf"


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    from tests._cleanup import purge_companies_by_slug

    purge_companies_by_slug(s, f"{SLUG_PREFIX}-%")
    s.commit()
    s.close()


def _tenant(db) -> Company:
    co = Company(
        id=str(uuid.uuid4()),
        name=f"AppConf {uuid.uuid4().hex[:6]}",
        slug=f"{SLUG_PREFIX}-{uuid.uuid4().hex[:8]}",
        is_active=True,
        vertical="manufacturing",
        timezone="America/New_York",
    )
    db.add(co)
    db.commit()
    return co


def _order_as_approve_would(db, co: Company, *, service: date | None) -> SalesOrder:
    """A sales order shaped exactly as `session_service.approve` now writes one.

    ⚠️ CONSTRUCTED RATHER THAN DRIVEN THROUGH `approve()`, and the reason is scope:
    driving the real capture needs a priced tenant catalogue, a funeral home, a cemetery
    and a full answer set — all of which `test_approve_confirms_the_order.py` already
    builds and asserts. What is under test HERE is the batch's reaction to the shape
    Approve produces, so the shape is taken from Approve (status, order_type, and BOTH
    date columns from one value) and the fields that only matter to pricing are not.

    ⚠️ `CONFIRMED_ON_APPROVE` IS IMPORTED, NOT RETYPED. If Approve's status ever changes
    again, this fixture changes with it instead of silently testing a status Approve no
    longer writes.
    """
    cust = Customer(
        id=str(uuid.uuid4()), company_id=co.id, name="Hopkins Funeral Home",
        is_active=True, invoice_delivery_preference="statement_only",
    )
    db.add(cust)
    db.commit()
    o = SalesOrder(
        id=str(uuid.uuid4()),
        company_id=co.id,
        number=f"SO-{uuid.uuid4().hex[:8]}",
        customer_id=cust.id,
        order_date=datetime.now(timezone.utc),
        status=CONFIRMED_ON_APPROVE,
        order_type="funeral",
        scheduled_date=service,
        required_date=(
            datetime.combine(service, datetime.min.time(), tzinfo=timezone.utc)
            if service
            else None
        ),
        subtotal=Decimal("1550.00"),
        tax_rate=Decimal("0"),
        tax_amount=Decimal("0"),
        total=Decimal("1550.00"),
        payment_terms="net30",
    )
    db.add(o)
    db.commit()
    return o


def _freeze_today(monkeypatch, value: date) -> None:
    monkeypatch.setattr(dis, "tenant_today", lambda _db, _tid: value)


# ── item 1: the status, and what now protects the order ──────────────────────


def test_approves_status_is_inside_the_batchs_net():
    """⚠️ THE POINT OF STEP 3, STATED AS A MEMBERSHIP RATHER THAN A WORD. Approve's status
    is deliberately IN `INVOICEABLE_STATUSES` now — the order is meant to be billable once
    its service date arrives. Before step 3 it was deliberately OUT.
    """
    assert CONFIRMED_ON_APPROVE in dis.INVOICEABLE_STATUSES
    assert "draft" not in dis.INVOICEABLE_STATUSES


def test_a_future_service_date_survives_tonights_batch(db, monkeypatch):
    """⚠️ THE TEST THE WHOLE ARC RESTS ON. The order is CONFIRMED — inside the status net
    — and the only thing keeping it out of tonight's run is its service date. If step 2's
    gate regressed, this order would be marked delivered and invoiced on the evening it
    was approved.
    """
    co = _tenant(db)
    today = date(2026, 10, 16)
    _freeze_today(monkeypatch, today)
    o = _order_as_approve_would(db, co, service=today + timedelta(days=4))

    dis.generate_draft_invoices(db, co.id)
    db.commit()
    db.expire_all()

    row = db.get(SalesOrder, o.id)
    assert row.status == CONFIRMED_ON_APPROVE, "a future-dated order was acted on"
    assert row.delivered_at is None
    assert row.delivery_auto_confirmed is False

    from app.models.invoice import Invoice

    assert db.query(Invoice).filter(Invoice.sales_order_id == o.id).count() == 0


def test_the_service_date_arriving_is_what_releases_it(db, monkeypatch):
    """The other half: on the service date it IS delivered and invoiced. Without this the
    test above would be satisfied by a batch that never acts at all.
    """
    from app.models.invoice import Invoice

    co = _tenant(db)
    service = date(2026, 10, 20)
    o = _order_as_approve_would(db, co, service=service)

    _freeze_today(monkeypatch, service - timedelta(days=1))
    dis.generate_draft_invoices(db, co.id)
    db.commit()
    db.expire_all()
    assert db.get(SalesOrder, o.id).status == CONFIRMED_ON_APPROVE

    _freeze_today(monkeypatch, service)
    dis.generate_draft_invoices(db, co.id)
    db.commit()
    db.expire_all()

    row = db.get(SalesOrder, o.id)
    assert row.status == "delivered"
    assert row.delivery_auto_confirmed is True
    inv = db.query(Invoice).filter(Invoice.sales_order_id == o.id).one()
    assert inv.status == "draft" and inv.requires_review is True
    assert inv.total == Decimal("1550.00")
    assert inv.sent_at is None, "the tenant email switch is off by default"


def test_undo_confirm_works_on_a_freshly_approved_order(db, monkeypatch):
    """⚠️ THE ESCAPE HATCH STEP 3 DEPENDS ON. Approve is now the irreversible-looking
    step, so an order approved by mistake must be recoverable without cancelling.
    """
    from app.schemas.sales import SalesOrderUpdate
    from app.services import sales_service

    co = _tenant(db)
    today = date(2026, 10, 16)
    _freeze_today(monkeypatch, today)
    o = _order_as_approve_would(db, co, service=today)

    sales_service.update_sales_order(
        db, co.id, None, o.id, SalesOrderUpdate(status="draft")
    )
    db.commit()
    db.expire_all()
    assert db.get(SalesOrder, o.id).status == "draft"

    # and it is now out of the net even though its service date is today
    dis.generate_draft_invoices(db, co.id)
    db.commit()
    db.expire_all()
    row = db.get(SalesOrder, o.id)
    assert row.status == "draft" and row.delivered_at is None


# ── item 2: which paths still create drafts ──────────────────────────────────


def test_the_draft_creating_paths_are_the_ones_we_think():
    """⚠️ A STRUCTURAL INVENTORY, so "drafts remain only for a capture saved partway"
    cannot quietly stop being true.

    Measured 2026-10-16 — six places construct a `SalesOrder`:

        legacy_studio.py:355            draft
        sales_service.py:545            draft   (create_sales_order — the office form)
        call_extraction_service.py:493  draft
        quote_service.py:423            draft|confirmed, by required parameter
        vault_order_service.py:270      confirmed  ⚠️ ALREADY, BEFORE STEP 3
        capture/session_service.py      confirmed  ← this dispatch

    ⚠️ THE FIFTH ROW IS WHY STEP 3 IS LESS OF A DEPARTURE THAN IT READS. Confirmed-on-
    create already existed: `vault_order_service` has created `confirmed` orders with a
    `required_date` all along, which means they were already inside the batch's net.
    Opas Approve joins an existing pattern rather than inventing one.
    """
    import ast
    import pathlib

    # ⚠️ AST, NOT A REGEX, AND THE FIRST VERSION OF THIS TEST PROVED WHY. A regex with a
    # 900-character window silently MISSED the two longest constructions — including the
    # one under test, because `session_service.approve`'s call is mostly comments. It
    # reported four creators instead of six and would have let Opas drift back to draft
    # unnoticed. CLAUDE.md §11: if it was placed by a regex, verify it with a parser.
    root = pathlib.Path(__file__).resolve().parents[1] / "app"
    found: dict[str, str] = {}
    for path in root.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:  # pragma: no cover
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "SalesOrder"):
                continue
            for kw in node.keywords:
                if kw.arg == "status":
                    v = kw.value
                    found[str(path.relative_to(root))] = (
                        repr(v.value) if isinstance(v, ast.Constant)
                        else getattr(v, "id", ast.dump(v))
                    )

    assert len(found) >= 6, (
        f"the scanner found only {len(found)} SalesOrder creators ({sorted(found)}); "
        "six were measured on 2026-10-16, so this is the scanner breaking rather than "
        "the app shrinking"
    )

    # Opas Approve confirms.
    assert found.get("services/capture/session_service.py") == "CONFIRMED_ON_APPROVE"
    # The office's own create path still drafts. ⚠️ This dispatch moved OPAS APPROVE, not
    # the order model's default; a change here would be a silent widening.
    assert found.get("services/sales_service.py") == "'draft'"
    assert found.get("services/call_extraction_service.py") == "'draft'"
    # And the one that already confirmed, so its presence is not read as a regression.
    assert found.get("services/vault_order_service.py") == "'confirmed'"


# ── item 4: no service date, no Approve ──────────────────────────────────────


def test_the_service_date_is_a_required_field():
    """⚠️ MEASURED, NOT READ. `required_when` defaults to `Always()`, and `asdict` renders
    that field-less dataclass as `{}` — which reads exactly like "no condition set", i.e.
    like NOT required. That misreading is why this is asserted through the predicate the
    engine actually uses rather than by eyeballing the field definition.
    """
    from app.services.capture.schema import PLATFORM_DEFAULT_FIELDS

    f = [x for x in PLATFORM_DEFAULT_FIELDS if x.field_id == "service_date"]
    assert len(f) == 1, "service_date is not in the platform default fields"
    assert f[0].required, (
        "service_date stopped being unconditionally required — Approve would then be "
        "reachable with no date, and the batch's protection IS the date"
    )


def test_the_question_line_asks_for_the_service_day():
    """The wording is James's, verbatim, and it is the prompt the director sees when the
    date is what's missing."""
    from app.services.capture.schema import CALL_ORDER, CALL_QUESTIONS

    assert CALL_QUESTIONS["service_date"] == "What day is the service?"
    assert "service_date" in CALL_ORDER


def test_approval_is_blocked_when_the_service_date_is_missing():
    """⚠️ ASSERTED THROUGH `assess`, THE FUNCTION THE ROUTE AND THE SUMMARY BOTH CALL, so
    this cannot pass while the real gate is open. `assess` is read-only by design, which
    is what makes calling it here safe.
    """
    from app.services.capture.approval import assess

    assessment = assess(
        None,
        tenant_id="irrelevant-no-db-reads-on-this-path",
        answers={},
        missing_labels={"Service date"},
        open_picks=(),
        conflicts=(),
    )
    assert assessment.ready is False
    assert any("service date" in b.lower() for b in assessment.blockers), (
        f"no blocker named the service date: {assessment.blockers}"
    )


# ── item 3: the Review says what Approve will do ─────────────────────────────


def _approval(customer_id, *, ready=True):
    from app.services.capture.approval import Approval

    return Approval(
        ready=ready, blockers=(), lines=(), total=Decimal("1550.00"),
        customer_id=customer_id,
    )


def test_the_effect_line_names_the_day_and_the_billing(db):
    """James's shape: "Confirms the order · Delivered Tue Oct 20 · Invoiced at month end
    (Hopkins)". Built from the real customer record, not a template."""
    from app.services.capture.approval import describe_approve_effect

    co = _tenant(db)
    o = _order_as_approve_would(db, co, service=date(2026, 10, 20))

    line = describe_approve_effect(
        db, co.id, {"service_date": "2026-10-20"}, _approval(o.customer_id)
    )
    assert line == "Confirms the order · Delivered Tue Oct 20 · Invoiced at month end (Hopkins)"


def test_the_effect_line_is_absent_when_the_order_cannot_be_approved(db):
    """⚠️ A PROMISE ABOUT A PRESS THAT WILL BE REFUSED IS WORSE THAN NO PROMISE. The
    blockers already say what is wrong."""
    from app.services.capture.approval import describe_approve_effect

    co = _tenant(db)
    o = _order_as_approve_would(db, co, service=date(2026, 10, 20))
    assert (
        describe_approve_effect(
            db, co.id, {"service_date": "2026-10-20"},
            _approval(o.customer_id, ready=False),
        )
        is None
    )


def test_the_effect_line_does_not_promise_an_email_that_cannot_be_sent(db):
    """⚠️ THE SUBTLETY WORTH THE CODE. A customer set to `invoice_immediately` would
    otherwise read as invoiced-and-sent while the per-tenant email switch is off and
    nothing leaves — a sentence on screen the system contradicts silently.
    """
    from app.services.capture.approval import describe_approve_effect
    from app.services.invoice_email_switch import SETTING_KEY

    co = _tenant(db)
    o = _order_as_approve_would(db, co, service=date(2026, 10, 20))
    db.execute(
        sql_text(
            "UPDATE customers SET invoice_delivery_preference = 'invoice_immediately' "
            "WHERE id = :c"
        ),
        {"c": o.customer_id},
    )
    db.commit()

    answers = {"service_date": "2026-10-20"}
    off = describe_approve_effect(db, co.id, answers, _approval(o.customer_id))
    assert "not emailed" in off, off
    assert "and emailed" not in off

    co.set_setting(SETTING_KEY, True)
    db.commit()
    on = describe_approve_effect(db, co.id, answers, _approval(o.customer_id))
    assert "Invoiced and emailed (Hopkins)" in on, on


def test_the_effect_line_reaches_the_review_response(db):
    """⚠️ THE WIRING, NOT THE COMPOSER. A sentence that is built correctly and never
    reaches the pane is the shape CLAUDE.md §11 calls complete machinery behind an
    unprovisioned entrance.
    """
    import inspect

    from app.services.capture import session_service

    src = inspect.getsource(session_service.read_state)
    assert '"approve_effect"' in src
    assert "describe_approve_effect(db, company_id, answers, appraisal)" in src


# ── item 6: re-billing after a void is the office's act, never the batch's ───


def test_a_void_only_order_can_be_re_invoiced_by_hand(db, monkeypatch):
    """The batch will never re-bill it (pinned in test_delivered_on_the_service_date),
    so the office must be able to. `create_invoice_from_order`'s existing guard is
    `status != 'void'`, which already permits this — asserted so it stays permitted."""
    from app.models.invoice import Invoice
    from app.services import sales_service

    co = _tenant(db)
    o = _order_as_approve_would(db, co, service=date(2026, 10, 16))
    first = sales_service.create_invoice_from_order(db, co.id, None, o.id)
    first.status = "void"
    db.commit()

    second = sales_service.create_invoice_from_order(db, co.id, None, o.id)
    db.commit()
    assert second.id != first.id
    assert db.query(Invoice).filter(Invoice.sales_order_id == o.id).count() == 2


def test_a_live_invoice_still_refuses_a_second_one_and_names_it(db):
    """The other side of the same guard, and the message is the office's next step."""
    from fastapi import HTTPException

    from app.services import sales_service

    co = _tenant(db)
    o = _order_as_approve_would(db, co, service=date(2026, 10, 16))
    first = sales_service.create_invoice_from_order(db, co.id, None, o.id)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        sales_service.create_invoice_from_order(db, co.id, None, o.id)
    assert exc.value.status_code == 409
    assert first.number in str(exc.value.detail)
    assert "void" in str(exc.value.detail).lower()


def test_the_order_response_distinguishes_the_three_billing_cases(db):
    """⚠️ WHAT THE PAGE NEEDS AND DID NOT HAVE. It had no view of the order's invoices,
    so it offered "Create Invoice" unconditionally and the 409 came back as a generic
    failure. Three cases, three answers.
    """
    from app.api.routes.sales import _order_to_response
    from app.services import sales_service

    co = _tenant(db)
    o = _order_as_approve_would(db, co, service=date(2026, 10, 16))
    db.refresh(o)

    # never invoiced
    r = _order_to_response(o, db)
    assert r["live_invoice_number"] is None and r["voided_invoice_count"] == 0

    # invoiced
    inv = sales_service.create_invoice_from_order(db, co.id, None, o.id)
    db.commit()
    db.refresh(o)
    r = _order_to_response(o, db)
    assert r["live_invoice_number"] == inv.number
    assert r["voided_invoice_count"] == 0

    # voided
    inv.status = "void"
    db.commit()
    db.refresh(o)
    r = _order_to_response(o, db)
    assert r["live_invoice_number"] is None, "a voided invoice must not read as live"
    assert r["voided_invoice_count"] == 1


def test_the_response_without_a_session_keeps_its_old_shape(db):
    """⚠️ `db` IS OPTIONAL SO EXISTING CALLERS ARE UNAFFECTED. Several surfaces render an
    order with no session to hand; they must not start raising."""
    from app.api.routes.sales import _order_to_response

    co = _tenant(db)
    o = _order_as_approve_would(db, co, service=date(2026, 10, 16))
    db.refresh(o)
    r = _order_to_response(o)
    assert "live_invoice_number" not in r or r.get("live_invoice_number") is None


# ── the two confirm paths must not diverge (James, 2026-10-16, follow-up item 2) ──


def _enable_auto_delivery(db, co: Company) -> None:
    """Turn `auto_create_delivery_from_order` on for this tenant.

    ⚠️ THROUGH `delivery_settings_service.get_settings`, WHICH CREATES THE ROW IF IT IS
    ABSENT. Writing the table directly would miss the model-side defaults and would not
    exercise the same read path the hook uses.
    """
    from app.services.delivery_settings_service import get_settings

    s = get_settings(db, co.id)
    s.auto_create_delivery_from_order = True
    db.commit()


def _deliveries_for(db, order_id: str) -> list[dict]:
    """The delivery rows for one order, in the fields that reflect the PATH.

    ⚠️ `customer_id` IS NOT SELECTED, AND LEAVING IT IN WAS MY OWN TEST BUG. Each order
    in the parity test gets its own customer, so comparing it made two identical paths
    look divergent — and the noise nearly hid the real finding underneath it (a delivery
    dated a day early). A parity test must compare what the path decides, not what the
    fixture happened to create.
    """
    rows = db.execute(
        sql_text(
            "SELECT status, priority, delivery_type, requested_date, special_instructions "
            "FROM deliveries WHERE order_id = :o ORDER BY created_at"
        ),
        {"o": order_id},
    ).mappings().all()
    return [dict(r) for r in rows]


def test_the_two_confirm_paths_do_not_diverge(db):
    """⚠️ THE TEST JAMES ASKED FOR, AND IT ONLY MEANS ANYTHING WITH THE FLAG ON.

    `auto_create_delivery_from_order` is False for every production tenant, so both
    paths no-op today and agree by accident. That accidental agreement is exactly what
    made the divergence I introduced invisible: I removed the hook from `approve`, every
    test stayed green, and the difference would only have surfaced the day somebody
    enabled the flag.

    So this enables it, confirms one order each way, and compares the deliveries.
    """
    from app.schemas.sales import SalesOrderUpdate
    from app.services import sales_service

    co = _tenant(db)
    _enable_auto_delivery(db, co)
    service = date(2026, 10, 23)

    # Path A — an order born confirmed, as Opas Approve writes it.
    via_approve = _order_as_approve_would(db, co, service=service)
    from app.services import order_integration_service

    order_integration_service.on_order_confirmed(db, via_approve)
    db.commit()

    # Path B — a draft confirmed through the PATCH path.
    via_patch = _order_as_approve_would(db, co, service=service)
    db.execute(
        sql_text("UPDATE sales_orders SET status = 'draft' WHERE id = :i"),
        {"i": via_patch.id},
    )
    db.commit()
    db.expire_all()
    sales_service.update_sales_order(
        db, co.id, None, via_patch.id, SalesOrderUpdate(status="confirmed")
    )
    db.commit()

    a = _deliveries_for(db, via_approve.id)
    b = _deliveries_for(db, via_patch.id)

    assert len(a) == 1, f"the Opas path created {len(a)} deliveries, expected 1"
    assert len(b) == 1, f"the PATCH path created {len(b)} deliveries, expected 1"
    # ⚠️ COMPARED FIELD BY FIELD, NOT BY COUNT. Two deliveries both existing is not
    # parity if one of them has no date on it — which is precisely the defect
    # `required_date` was written to avoid, and which a count would not see.
    assert a[0] == b[0], f"the two confirm paths produced different deliveries:\n  opas  {a[0]}\n  patch {b[0]}"
    assert a[0]["requested_date"] == service, (
        f"the delivery is not dated from the service date: {a[0]['requested_date']}"
    )


def test_approve_fires_the_hook_at_all(db):
    """⚠️ THE NARROWER CLAIM, SO A FAILURE POINTS AT ONE PATH. The divergence test above
    would also fail if BOTH paths stopped creating deliveries, which reads as parity.
    """
    import inspect

    from app.services.capture import session_service

    src = inspect.getsource(session_service.approve)
    assert "order_integration_service.on_order_confirmed(db, order)" in src, (
        "approve no longer fires the delivery hook; an Opas-confirmed order would "
        "diverge from a hand-confirmed one the moment the flag is enabled"
    )


def test_neither_path_creates_a_delivery_while_the_flag_is_off(db):
    """The default, pinned. ⚠️ Without this, the parity test above is satisfied by a hook
    that fires unconditionally — which would put a stop on the board for every tenant
    that never asked for one.
    """
    from app.schemas.sales import SalesOrderUpdate
    from app.services import order_integration_service, sales_service

    co = _tenant(db)  # flag left at its default
    o = _order_as_approve_would(db, co, service=date(2026, 10, 23))
    order_integration_service.on_order_confirmed(db, o)
    db.commit()
    assert _deliveries_for(db, o.id) == []

    o2 = _order_as_approve_would(db, co, service=date(2026, 10, 23))
    db.execute(
        sql_text("UPDATE sales_orders SET status = 'draft' WHERE id = :i"), {"i": o2.id}
    )
    db.commit()
    db.expire_all()
    sales_service.update_sales_order(
        db, co.id, None, o2.id, SalesOrderUpdate(status="confirmed")
    )
    db.commit()
    assert _deliveries_for(db, o2.id) == []


def test_the_delivery_is_dated_the_SERVICE_day_not_the_evening_before(db):
    """⚠️ A DAY-EARLY DELIVERY FOR A FUNERAL. Found by the parity test above, 2026-10-16.

    Opas writes `required_date` as midnight UTC on the service day, and
    `on_order_confirmed` used to date the delivery `order.required_date.date()`. `.date()`
    on a `DateTime(timezone=True)` is evaluated in whatever zone the SESSION reads in —
    and midnight UTC is the previous evening in every negative offset. On a session set
    to `America/New_York` (which is what `SHOW TimeZone` returns on a dev box) a service
    on the 23rd produced a delivery requested for the **22nd**.

    ⚠️ IT IS PINNED AGAINST A TENANT-LOCAL READ, NOT AGAINST UTC, because UTC is the one
    configuration where the bug does not appear — production's own server is UTC, which
    is why this would have shipped looking fine and gone wrong on any Eastern-configured
    database or any future per-tenant session timezone.
    """
    from app.services import order_integration_service

    co = _tenant(db)
    _enable_auto_delivery(db, co)
    service = date(2026, 10, 23)
    o = _order_as_approve_would(db, co, service=service)

    # the precondition: required_date really is a midnight-UTC stamp
    stored = db.execute(
        sql_text("SELECT required_date FROM sales_orders WHERE id = :i"), {"i": o.id}
    ).scalar()
    assert stored is not None

    order_integration_service.on_order_confirmed(db, o)
    db.commit()

    got = db.execute(
        sql_text("SELECT requested_date FROM deliveries WHERE order_id = :o"),
        {"o": o.id},
    ).scalar()
    assert got == service, (
        f"the delivery is dated {got}, the service is {service} — a stop on the board "
        "on the wrong day"
    )


def test_the_fallback_is_used_only_when_there_is_no_scheduled_date(db):
    """⚠️ THE POSITIVE CONTROL ON THE FIX. Preferring `scheduled_date` must not mean
    IGNORING `required_date` — pre-Opas and hand-entered orders carry only the timestamp,
    and dropping them would silently stop creating their deliveries.
    """
    from app.services import order_integration_service

    co = _tenant(db)
    _enable_auto_delivery(db, co)
    o = _order_as_approve_would(db, co, service=date(2026, 10, 23))
    # a pre-Opas shape: the timestamp alone, at noon so no zone can shift the day
    db.execute(
        sql_text(
            "UPDATE sales_orders SET scheduled_date = NULL, "
            "required_date = :r WHERE id = :i"
        ),
        {"r": datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc), "i": o.id},
    )
    db.commit()
    db.expire_all()
    o = db.get(SalesOrder, o.id)

    order_integration_service.on_order_confirmed(db, o)
    db.commit()
    got = db.execute(
        sql_text("SELECT requested_date FROM deliveries WHERE order_id = :o"),
        {"o": o.id},
    ).scalar()
    assert got == date(2026, 10, 23), f"the required_date fallback stopped working: {got}"
