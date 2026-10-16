"""The end-of-day batch acts on an order only after its service date has arrived.

James's step 2, 2026-10-16. Covers:

  item 2  selection: confirmed AND service date <= the TENANT's today.
          A future service date is untouched. No service date is never
          auto-delivered, and is surfaced.
  item 4  the status transition graph; `draft -> delivered` must fail.
  item 5  no invoice email can leave a tenant whose switch is off.
  item 6  the hypothetical walk — Hopkins, service next Tuesday, confirmed today.

⚠️ THE SELECTION TESTS MONKEYPATCH `tenant_today`, AND THAT IS THE SEAM RATHER THAN A
DODGE. The rule under test is "compare the service date against the tenant's today", and
pinning it with the real clock would mean a test whose meaning changes at midnight — the
kind that passes for eleven months and fails on a Tuesday. `tenant_today` itself is tested
separately, against two real zones fourteen hours apart, with no mocking at all.
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
from app.services import sales_order_transitions as transitions

SLUG_PREFIX = "svcdate"


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    # ⚠️ PURGES ITS OWN TENANTS. CLAUDE.md §11: the company-litter count only shrinks, and
    # the session tripwire fires on whichever test happens to run last — so a file that
    # leaks blames an innocent neighbour.
    from tests._cleanup import purge_companies_by_slug

    purge_companies_by_slug(s, f"{SLUG_PREFIX}-%")
    s.commit()
    s.close()


def _tenant(db, *, tz: str | None = "America/New_York") -> Company:
    """A disposable tenant. `tz=None` really means NULL in the column.

    ⚠️ PASSING `timezone=None` TO THE CONSTRUCTOR DOES NOT GIVE YOU NULL. The column
    carries a MODEL-side `default="UTC"` (`app/models/company.py:39-41`), which
    SQLAlchemy applies precisely when the attribute is unset or None — so the "no
    timezone configured" case has to be written after the insert. This is the same
    two-layer-default trap CLAUDE.md §5 records, and it is why every production tenant
    reads `UTC`: nobody chose it, the model did.
    """
    suffix = uuid.uuid4().hex[:8]
    co = Company(
        id=str(uuid.uuid4()),
        name=f"SvcDate {suffix}",
        slug=f"{SLUG_PREFIX}-{suffix}",
        is_active=True,
        vertical="manufacturing",
        timezone=tz,
    )
    db.add(co)
    db.commit()
    if tz is None:
        db.execute(
            sql_text("UPDATE companies SET timezone = NULL WHERE id = :i"),
            {"i": co.id},
        )
        db.commit()
        db.refresh(co)
        assert co.timezone is None, "the model default won; the NULL case is untested"
    return co


def _customer(db, co: Company, *, preference: str = "statement_only") -> Customer:
    cust = Customer(
        id=str(uuid.uuid4()),
        company_id=co.id,
        name="Hopkins Funeral Home",
        is_active=True,
        invoice_delivery_preference=preference,
    )
    db.add(cust)
    db.commit()
    return cust


def _order(
    db,
    co: Company,
    cust: Customer,
    *,
    status: str = "confirmed",
    scheduled: date | None = None,
    required: datetime | None = None,
) -> SalesOrder:
    o = SalesOrder(
        id=str(uuid.uuid4()),
        company_id=co.id,
        number=f"SO-{uuid.uuid4().hex[:8]}",
        customer_id=cust.id,
        order_date=datetime.now(timezone.utc),
        status=status,
        order_type="funeral",
        scheduled_date=scheduled,
        required_date=required,
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


def _selected(db, co: Company) -> set[str]:
    """Order numbers the batch's own query selects. Reads the shipped expression."""
    rows = (
        db.query(SalesOrder)
        .filter(
            SalesOrder.company_id == co.id,
            SalesOrder.status.in_(dis.INVOICEABLE_STATUSES),
            ~SalesOrder.status.in_(dis.SKIP_STATUSES),
            dis.SERVICE_DATE.isnot(None),
            dis.SERVICE_DATE <= dis.tenant_today(db, co.id),
            (SalesOrder.order_type == "funeral") | (SalesOrder.order_type.is_(None)),
        )
        .all()
    )
    return {o.number for o in rows}


# ── item 2: the selection rule ───────────────────────────────────────────────


def test_a_future_service_date_is_untouched(db, monkeypatch):
    co, cust = _tenant(db), None
    cust = _customer(db, co)
    today = date(2026, 10, 16)
    _freeze_today(monkeypatch, today)

    future = _order(db, co, cust, scheduled=today + timedelta(days=4))
    outcome = dis.generate_draft_invoices(db, co.id)
    db.expire_all()

    assert db.get(SalesOrder, future.id).status == "confirmed", (
        "an order whose service date has not arrived must not be auto-delivered"
    )
    assert db.get(SalesOrder, future.id).delivered_at is None
    assert outcome.detail.get("orders_due") == 0


def test_todays_service_date_is_selected_and_delivered(db, monkeypatch):
    co = _tenant(db)
    cust = _customer(db, co)
    today = date(2026, 10, 16)
    _freeze_today(monkeypatch, today)

    o = _order(db, co, cust, scheduled=today)
    dis.generate_draft_invoices(db, co.id)
    db.expire_all()

    row = db.get(SalesOrder, o.id)
    assert row.status == "delivered"
    assert row.delivered_at is not None
    assert row.delivery_auto_confirmed is True


def test_a_past_service_date_is_still_picked_up(db, monkeypatch):
    """`<= today`, not `== today` — a missed day is caught on the next run rather than
    stranded forever."""
    co = _tenant(db)
    cust = _customer(db, co)
    today = date(2026, 10, 16)
    _freeze_today(monkeypatch, today)

    o = _order(db, co, cust, scheduled=today - timedelta(days=3))
    dis.generate_draft_invoices(db, co.id)
    db.expire_all()
    assert db.get(SalesOrder, o.id).status == "delivered"


def test_a_draft_is_never_selected_however_old_its_service_date(db, monkeypatch):
    """⚠️ THE SAFETY PROPERTY `capture/session_service.approve` RELIES ON."""
    co = _tenant(db)
    cust = _customer(db, co)
    today = date(2026, 10, 16)
    _freeze_today(monkeypatch, today)

    o = _order(db, co, cust, status="draft", scheduled=today - timedelta(days=30))
    dis.generate_draft_invoices(db, co.id)
    db.expire_all()

    row = db.get(SalesOrder, o.id)
    assert row.status == "draft"
    assert row.delivered_at is None
    assert "draft" not in dis.INVOICEABLE_STATUSES


def test_no_service_date_is_never_auto_delivered(db, monkeypatch):
    co = _tenant(db)
    cust = _customer(db, co)
    _freeze_today(monkeypatch, date(2026, 10, 16))

    o = _order(db, co, cust, scheduled=None, required=None)
    dis.generate_draft_invoices(db, co.id)
    db.expire_all()

    row = db.get(SalesOrder, o.id)
    assert row.status == "confirmed", "an undated order must not be auto-delivered"
    assert row.delivered_at is None


def test_no_service_date_is_surfaced_to_the_office(db, monkeypatch):
    """⚠️ THE HALF THAT WAS MISSING BEFORE. Such an order was excluded by the date filter
    failing to match and nobody was told — it would never be delivered and never
    invoiced, discoverable only by noticing the money was absent.
    """
    co = _tenant(db)
    cust = _customer(db, co)
    _freeze_today(monkeypatch, date(2026, 10, 16))
    o = _order(db, co, cust, scheduled=None, required=None)

    stuck = dis.confirmed_without_a_service_date(db, co.id)
    assert [s.number for s in stuck] == [o.number]

    outcome = dis.generate_draft_invoices(db, co.id)
    assert outcome.detail.get("confirmed_without_service_date") == 1

    alerts = db.execute(
        sql_text(
            "SELECT title, message FROM agent_alerts "
            "WHERE tenant_id = :t AND alert_type = :k"
        ),
        {"t": co.id, "k": dis.UNDATED_ALERT_TYPE},
    ).all()
    assert len(alerts) == 1, "exactly one alert, naming the stuck orders"
    assert o.number in alerts[0][1]
    assert "never" in alerts[0][1].lower(), (
        "the message must say what happens if nobody acts, not merely that the date is "
        "absent"
    )


def test_an_undated_order_that_was_invoiced_by_hand_is_not_alerted(db, monkeypatch):
    """Alerting nightly on an order that is not stuck trains the office to ignore the
    alert, which defeats the only surface this rule has."""
    co = _tenant(db)
    cust = _customer(db, co)
    _freeze_today(monkeypatch, date(2026, 10, 16))
    o = _order(db, co, cust, scheduled=None, required=None)

    from app.services import sales_service

    sales_service.create_invoice_from_order(db, co.id, None, o.id)
    db.commit()

    outcome = dis.generate_draft_invoices(db, co.id)
    assert outcome.detail.get("confirmed_without_service_date") == 0


def test_required_date_still_works_as_the_fallback(db, monkeypatch):
    """Pre-Opas orders carry only `required_date`. Dropping the fallback would silently
    stop invoicing them."""
    co = _tenant(db)
    cust = _customer(db, co)
    today = date(2026, 10, 16)
    _freeze_today(monkeypatch, today)

    o = _order(
        db, co, cust,
        scheduled=None,
        required=datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc),
    )
    assert _selected(db, co) == {o.number}
    assert dis.confirmed_without_a_service_date(db, co.id) == []


def test_scheduled_date_wins_over_required_date(db, monkeypatch):
    """COALESCE order matters: Opas writes both, and `scheduled_date` is the service
    date. A future scheduled_date must not be overridden by a past required_date."""
    co = _tenant(db)
    cust = _customer(db, co)
    today = date(2026, 10, 16)
    _freeze_today(monkeypatch, today)

    o = _order(
        db, co, cust,
        scheduled=today + timedelta(days=4),
        required=datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc),
    )
    assert _selected(db, co) == set(), (
        "the future scheduled_date must decide, not the past required_date"
    )
    db.expire_all()
    assert db.get(SalesOrder, o.id).status == "confirmed"


# ── item 2: "today" is the tenant's, not the container's ─────────────────────


def test_tenant_today_differs_between_two_real_zones(db):
    """⚠️ NO MOCKING, AND NO DEPENDENCE ON WHAT TIME IT IS. Kiritimati is UTC+14 and Niue
    is UTC-11 — 25 hours apart, so their calendar dates differ for 25 of every 24 hours,
    i.e. always. If `tenant_today` ignored the tenant's zone these would be equal.
    """
    from app.services.tenant_clock import tenant_today, tenant_timezone

    east = _tenant(db, tz="Pacific/Kiritimati")
    west = _tenant(db, tz="Pacific/Niue")

    assert str(tenant_timezone(db, east.id)) == "Pacific/Kiritimati"
    assert tenant_today(db, east.id) != tenant_today(db, west.id), (
        "two tenants 25 hours apart must not share a calendar date"
    )
    assert tenant_today(db, east.id) > tenant_today(db, west.id)


def test_an_absent_timezone_falls_back_to_eastern_not_utc(db):
    """The column defaults to "UTC" and seven of eight existing readers fall back to
    Eastern. This module picks Eastern; the choice is recorded rather than inherited."""
    from app.services.tenant_clock import DEFAULT_TZ, tenant_timezone

    co = _tenant(db, tz=None)
    assert str(tenant_timezone(db, co.id)) == DEFAULT_TZ == "America/New_York"


def test_an_unrecognised_timezone_falls_back_rather_than_raising(db):
    """A bad string in one tenant's config must not abort a per-tenant sweep for every
    other tenant."""
    from app.services.tenant_clock import DEFAULT_TZ, tenant_timezone

    co = _tenant(db, tz="Mars/Olympus_Mons")
    assert str(tenant_timezone(db, co.id)) == DEFAULT_TZ


def test_the_batch_reads_the_tenant_clock_not_date_today():
    """⚠️ A SOURCE CHECK, because the behavioural tests above monkeypatch the seam and
    would therefore pass even if the shipped code called `date.today()`. This is the
    assertion that the seam they patch is the one production uses.
    """
    import inspect

    src = inspect.getsource(dis.generate_draft_invoices)
    assert "tenant_today(db, tenant_id)" in src

    # ⚠️ COMMENTS ARE STRIPPED FIRST, AND THE FIRST VERSION OF THIS TEST FAILED FOR WANT
    # OF IT — the function's own comment says "This was `date.today()` until 2026-10-16",
    # so a bare substring check flags the explanation of the fix as the defect.
    code = "\n".join(
        line.split("#", 1)[0] for line in src.splitlines()
    )
    assert "date.today()" not in code, (
        "generate_draft_invoices is back on the container's date"
    )


# ── item 4: the transition graph ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "current,target",
    [
        ("draft", "delivered"),      # James's named case
        ("draft", "completed"),
        ("draft", "shipped"),
        ("delivered", "confirmed"),  # reversal
        ("delivered", "shipped"),    # reversal
        ("completed", "delivered"),  # out of a terminal state
        ("cancelled", "confirmed"),  # out of a terminal state
        ("confirmed", "banana"),     # unknown target
    ],
)
def test_forbidden_transitions(current, target):
    assert not transitions.is_allowed(current, target)
    with pytest.raises(transitions.TransitionError):
        transitions.check(current, target)


@pytest.mark.parametrize(
    "current,target",
    [
        ("draft", "confirmed"),
        ("draft", "cancelled"),
        ("confirmed", "processing"),
        ("confirmed", "delivered"),
        ("confirmed", "cancelled"),
        ("processing", "shipped"),
        ("processing", "delivered"),
        ("shipped", "delivered"),
        ("delivered", "completed"),
        ("confirmed", "confirmed"),      # no-op: a PATCH carrying other fields
        # ⚠️ ALLOWED SINCE 2026-10-16 — "Undo confirm". It was in the FORBIDDEN list
        # above until James's step-3 addendum; whether a PARTICULAR order may take it is
        # decided by `undo_confirm_blocker`, tested separately below.
        ("confirmed", "draft"),
        ("draft", "spring_burial"),
        ("spring_burial", "confirmed"),  # the hold comes back
        ("canceled", "canceled"),        # legacy spelling normalises
    ],
)
def test_allowed_transitions(current, target):
    assert transitions.is_allowed(current, target)
    transitions.check(current, target)  # must not raise


def test_an_unknown_legacy_status_can_still_move_forward():
    """Legacy rows carry statuses the graph does not name. Refusing to touch them would
    strand them permanently — the shape the `completed` net had to be widened for."""
    assert transitions.is_allowed("pending", "confirmed")
    assert transitions.is_allowed("in_production", "delivered")
    # but the permissive branch cannot be used to write an arbitrary string
    assert not transitions.is_allowed("pending", "banana")


def test_the_patch_route_rejects_draft_to_delivered(db):
    """End to end through `update_sales_order`, which is what the PATCH calls."""
    from fastapi import HTTPException

    from app.schemas.sales import SalesOrderUpdate
    from app.services import sales_service

    co = _tenant(db)
    cust = _customer(db, co)
    o = _order(db, co, cust, status="draft", scheduled=date(2026, 10, 16))

    with pytest.raises(HTTPException) as exc:
        sales_service.update_sales_order(
            db, co.id, None, o.id, SalesOrderUpdate(status="delivered")
        )
    assert exc.value.status_code == 409
    assert "cannot go straight to delivered" in str(exc.value.detail)

    db.rollback()
    db.expire_all()
    assert db.get(SalesOrder, o.id).status == "draft", (
        "a rejected transition must leave the row untouched"
    )


def test_the_patch_route_still_allows_draft_to_confirmed(db):
    from app.schemas.sales import SalesOrderUpdate
    from app.services import sales_service

    co = _tenant(db)
    cust = _customer(db, co)
    o = _order(db, co, cust, status="draft", scheduled=date(2026, 10, 16))

    sales_service.update_sales_order(
        db, co.id, None, o.id, SalesOrderUpdate(status="confirmed")
    )
    db.expire_all()
    assert db.get(SalesOrder, o.id).status == "confirmed"


def test_a_patch_with_no_status_is_not_a_transition(db):
    """Editing the notes must not be gated on the status graph."""
    from app.schemas.sales import SalesOrderUpdate
    from app.services import sales_service

    co = _tenant(db)
    cust = _customer(db, co)
    o = _order(db, co, cust, status="confirmed", scheduled=date(2026, 10, 16))

    sales_service.update_sales_order(
        db, co.id, None, o.id, SalesOrderUpdate(notes="a note")
    )
    db.expire_all()
    row = db.get(SalesOrder, o.id)
    assert row.notes == "a note" and row.status == "confirmed"


# ── item 5: no email can leave ───────────────────────────────────────────────


def test_the_switch_is_off_by_default(db):
    from app.services.invoice_email_switch import SETTING_KEY, invoice_email_allowed

    co = _tenant(db)
    allowed, why = invoice_email_allowed(db, co.id)
    assert allowed is False
    assert SETTING_KEY in why


def test_no_invoice_email_leaves_when_the_switch_is_off(db, monkeypatch):
    """⚠️ THE PROOF IS A SPY ON `delivery_service`, NOT ON OUR OWN GUARD. Asserting that
    the guard returned False would only prove the guard ran. This asserts that the thing
    which actually hands bytes to a mail provider is never reached — so a future caller
    that skips the guard fails this test too.
    """
    from app.services.delivery import delivery_service

    sent: list = []
    for name in dir(delivery_service):
        if name.startswith("send"):
            monkeypatch.setattr(
                delivery_service, name,
                lambda *a, _n=name, **k: sent.append(_n) or {"success": True},
            )

    co = _tenant(db)
    from app.services.email_service import email_service

    result = email_service.send_invoice_email(
        to_email="director@example.com",
        to_name="Hopkins",
        company_name="Sunnycrest",
        invoice_number="INV-TEST",
        invoice_date="October 16, 2026",
        due_date="November 15, 2026",
        total_amount="$1,550.00",
        balance_due="$1,550.00",
        pdf_attachment=b"%PDF-fake",
        company_id=co.id,
        db=db,
    )
    assert sent == [], f"delivery_service was reached despite the switch: {sent}"
    assert result.get("success") is False
    assert result.get("withheld") is True


def test_a_withheld_send_does_not_look_like_a_successful_one(db):
    """Callers stamp `sent_at` on a truthy `success`. A withheld send that reported
    success would mark the invoice delivered forever."""
    from app.services.email_service import email_service

    co = _tenant(db)
    result = email_service.send_invoice_email(
        to_email="x@example.com", to_name="x", company_name="x",
        invoice_number="INV-X", invoice_date="", due_date="",
        total_amount="$0.00", balance_due="$0.00", pdf_attachment=b"x",
        company_id=co.id, db=db,
    )
    assert not result.get("success")


def test_the_switch_fails_closed_without_a_session_or_company(db):
    """Both arguments are keyword-OPTIONAL on `send_invoice_email`, so a caller can reach
    the send path with neither. Defaulting an unidentifiable tenant to allowed would
    exempt the one path that cannot be checked."""
    from app.services.invoice_email_switch import invoice_email_allowed

    assert invoice_email_allowed(None, "some-id")[0] is False
    assert invoice_email_allowed(db, None)[0] is False
    assert invoice_email_allowed(db, "no-such-company")[0] is False


def test_the_string_false_does_not_open_the_gate(db):
    """`settings_json` is TEXT; a value from a form can come back as "false", which is
    truthy in Python."""
    from app.services.invoice_email_switch import SETTING_KEY, invoice_email_allowed

    co = _tenant(db)
    co.set_setting(SETTING_KEY, "false")
    db.commit()
    assert invoice_email_allowed(db, co.id)[0] is False


def test_turning_the_switch_on_opens_the_gate(db):
    """⚠️ POSITIVE CONTROL. Without this, every assertion above is satisfied by a guard
    that refuses unconditionally — including one that would never send even after James
    turns it on.
    """
    from app.services.invoice_email_switch import SETTING_KEY, invoice_email_allowed

    co = _tenant(db)
    co.set_setting(SETTING_KEY, True)
    db.commit()
    allowed, why = invoice_email_allowed(db, co.id)
    assert allowed is True, f"the switch cannot be turned on: {why}"


# ── item 6: the hypothetical walk ────────────────────────────────────────────


def test_the_hopkins_walk(db, monkeypatch):
    """Hopkins order, service next Tuesday, confirmed today. Tonight / Monday / Tuesday.

    Dates are absolute and chosen so the weekday names are real: 2026-10-16 is a Friday,
    2026-10-20 is the following Tuesday.
    """
    friday = date(2026, 10, 16)
    monday = date(2026, 10, 19)
    tuesday = date(2026, 10, 20)

    co = _tenant(db, tz="America/New_York")
    cust = _customer(db, co, preference="statement_only")

    # Opas Approve writes BOTH date columns from the one answer (item 3).
    o = _order(
        db, co, cust,
        status="draft",
        scheduled=tuesday,
        required=datetime.combine(tuesday, datetime.min.time(), tzinfo=timezone.utc),
    )

    # --- confirmed today, 11:00
    from app.schemas.sales import SalesOrderUpdate
    from app.services import sales_service

    sales_service.update_sales_order(
        db, co.id, None, o.id, SalesOrderUpdate(status="confirmed")
    )
    db.expire_all()
    assert db.get(SalesOrder, o.id).status == "confirmed"

    # --- tonight (Friday): service date is 4 days away -> untouched
    _freeze_today(monkeypatch, friday)
    dis.generate_draft_invoices(db, co.id)
    db.expire_all()
    assert db.get(SalesOrder, o.id).status == "confirmed", "Friday must not touch it"
    assert db.get(SalesOrder, o.id).delivered_at is None

    # --- Monday night: still 1 day away -> untouched
    _freeze_today(monkeypatch, monday)
    dis.generate_draft_invoices(db, co.id)
    db.expire_all()
    assert db.get(SalesOrder, o.id).status == "confirmed", "Monday must not touch it"

    # --- Tuesday night: the service date has arrived
    _freeze_today(monkeypatch, tuesday)
    dis.generate_draft_invoices(db, co.id)
    db.expire_all()

    row = db.get(SalesOrder, o.id)
    assert row.status == "delivered"
    assert row.delivered_at is not None
    assert row.delivery_auto_confirmed is True

    from app.models.invoice import Invoice

    inv = db.query(Invoice).filter(Invoice.sales_order_id == o.id).one()
    assert inv.status == "draft"
    assert inv.requires_review is True
    assert inv.auto_generated is True
    assert inv.generation_reason == "end_of_day_batch"
    assert inv.total == Decimal("1550.00")

    # --- and nothing was emailed, because the tenant switch is off
    assert inv.sent_at is None
    assert inv.sent_to_email is None


# ── step 3 addendum item 1: "Undo confirm" ───────────────────────────────────


def test_undo_confirm_takes_a_confirmed_order_back_to_draft(db):
    """The ordinary case: confirmed by mistake, nothing has happened yet."""
    from app.schemas.sales import SalesOrderUpdate
    from app.services import sales_service

    co = _tenant(db)
    cust = _customer(db, co)
    o = _order(db, co, cust, status="confirmed", scheduled=date(2026, 10, 20))

    sales_service.update_sales_order(
        db, co.id, None, o.id, SalesOrderUpdate(status="draft")
    )
    db.expire_all()
    assert db.get(SalesOrder, o.id).status == "draft"


def test_an_undone_order_is_invisible_to_the_batch(db, monkeypatch):
    """⚠️ THE POINT OF THE FEATURE, NOT A COROLLARY. Undo is only worth having if it
    actually pulls the order out of the net — and the net is what James's step 2 built.
    A service date in the PAST is used deliberately: if the undo did not work, this
    order would be delivered and invoiced on the very next run.
    """
    from app.schemas.sales import SalesOrderUpdate
    from app.services import sales_service

    co = _tenant(db)
    cust = _customer(db, co)
    today = date(2026, 10, 16)
    _freeze_today(monkeypatch, today)
    o = _order(db, co, cust, status="confirmed", scheduled=today - timedelta(days=1))

    # It IS in the net while confirmed.
    assert _selected(db, co) == {o.number}

    sales_service.update_sales_order(
        db, co.id, None, o.id, SalesOrderUpdate(status="draft")
    )
    db.commit()
    assert _selected(db, co) == set(), "an undone order must leave the batch's net"

    dis.generate_draft_invoices(db, co.id)
    db.expire_all()
    row = db.get(SalesOrder, o.id)
    assert row.status == "draft"
    assert row.delivered_at is None

    from app.models.invoice import Invoice

    assert db.query(Invoice).filter(Invoice.sales_order_id == o.id).count() == 0


def test_undo_confirm_is_refused_once_delivered_at_is_set(db):
    """⚠️ CHECKED ON `delivered_at`, NOT ON THE STATUS WORD. This row's status is
    `confirmed` and its `delivered_at` is set — the state a hand-PATCH can produce, and
    the one case where trusting the status would undo a real delivery.
    """
    from fastapi import HTTPException

    from app.schemas.sales import SalesOrderUpdate
    from app.services import sales_service

    co = _tenant(db)
    cust = _customer(db, co)
    o = _order(db, co, cust, status="confirmed", scheduled=date(2026, 10, 16))
    o.delivered_at = datetime(2026, 10, 16, 22, 0, tzinfo=timezone.utc)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        sales_service.update_sales_order(
            db, co.id, None, o.id, SalesOrderUpdate(status="draft")
        )
    assert exc.value.status_code == 409
    assert "marked delivered" in str(exc.value.detail)
    db.rollback()
    db.expire_all()
    assert db.get(SalesOrder, o.id).status == "confirmed"


def test_undo_confirm_is_refused_once_an_invoice_exists(db):
    """`create_invoice_from_order` accepts a CONFIRMED order, so the office can invoice
    before the service night. Undoing then would leave a draft order with a live invoice
    against it."""
    from fastapi import HTTPException

    from app.schemas.sales import SalesOrderUpdate
    from app.services import sales_service

    co = _tenant(db)
    cust = _customer(db, co)
    o = _order(db, co, cust, status="confirmed", scheduled=date(2026, 10, 16))
    inv = sales_service.create_invoice_from_order(db, co.id, None, o.id)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        sales_service.update_sales_order(
            db, co.id, None, o.id, SalesOrderUpdate(status="draft")
        )
    assert exc.value.status_code == 409
    assert inv.number in str(exc.value.detail)
    db.rollback()
    db.expire_all()
    assert db.get(SalesOrder, o.id).status == "confirmed"


def test_a_voided_invoice_does_not_block_undo(db):
    """A voided invoice is the office saying it did not happen — the same direction as
    the undo, so it must not stand in the way."""
    from app.schemas.sales import SalesOrderUpdate
    from app.services import sales_service

    co = _tenant(db)
    cust = _customer(db, co)
    o = _order(db, co, cust, status="confirmed", scheduled=date(2026, 10, 16))
    inv = sales_service.create_invoice_from_order(db, co.id, None, o.id)
    inv.status = "void"
    db.commit()

    sales_service.update_sales_order(
        db, co.id, None, o.id, SalesOrderUpdate(status="draft")
    )
    db.expire_all()
    assert db.get(SalesOrder, o.id).status == "draft"


def test_undo_is_not_available_from_delivered_or_later(db):
    """Undo is `confirmed -> draft` only. `delivered` and `completed` are not confirmed,
    and the graph must not have quietly opened a path from them."""
    assert not transitions.is_allowed("delivered", "draft")
    assert not transitions.is_allowed("completed", "draft")
    assert not transitions.is_allowed("processing", "draft")
    assert not transitions.is_allowed("shipped", "draft")


def test_the_blocker_is_consulted_only_for_the_undo_edge(db):
    """⚠️ A POSITIVE CONTROL ON THE WIRING. If `is_undo_confirm` were wrong in the
    permissive direction, the blocker would run on ordinary transitions and an order with
    an invoice could not move at all. Confirmed -> delivered on an invoiced order must
    still work.
    """
    from app.schemas.sales import SalesOrderUpdate
    from app.services import sales_service

    co = _tenant(db)
    cust = _customer(db, co)
    o = _order(db, co, cust, status="confirmed", scheduled=date(2026, 10, 16))
    sales_service.create_invoice_from_order(db, co.id, None, o.id)
    db.commit()

    sales_service.update_sales_order(
        db, co.id, None, o.id, SalesOrderUpdate(status="delivered")
    )
    db.expire_all()
    assert db.get(SalesOrder, o.id).status == "delivered"
