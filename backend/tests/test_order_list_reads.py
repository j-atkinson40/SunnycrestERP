"""Order-list reads against a tenant's orders.

The session rolls back. Nothing here commits, and `remember()` is not called —
that helper commits a settings write, which this file is not allowed to do.
"""
from __future__ import annotations

import os
import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal

import pytest

if not os.environ.get("DATABASE_URL") or not os.environ.get("SECRET_KEY"):
    pytest.skip("DATABASE_URL is not set", allow_module_level=True)

from sqlalchemy import text

from app.database import SessionLocal
from app.models.cemetery import Cemetery
from app.models.company import Company
from app.models.customer import Customer
from app.models.delivery import Delivery
from app.models.legacy_proof import LegacyProof
from app.models.role import Role
from app.models.sales_order import SalesOrder, SalesOrderLine
from app.models.user import User
from app.services.order_list.question import OrderQuestion
from app.services.order_list.service import ask, sales_order_summary


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


def _company(session, name: str) -> Company:
    suffix = uuid.uuid4().hex[:8]
    company = Company(
        id=str(uuid.uuid4()),
        name=name,
        slug=f"olp-{suffix}",
        is_active=True,
        vertical="manufacturing",
    )
    session.add(company)
    session.flush()
    return company


def _order(session, company, *, customer_name, deceased, status="confirmed", total="100.00",
           when=None, vault="Monticello", cemetery_name=None, cemetery_city=None):
    customer = Customer(
        id=str(uuid.uuid4()), company_id=company.id, name=customer_name, is_active=True,
    )
    session.add(customer)
    session.flush()
    cemetery = None
    if cemetery_name:
        cemetery = Cemetery(
            id=str(uuid.uuid4()), company_id=company.id, name=cemetery_name, city=cemetery_city,
        )
        session.add(cemetery)
        session.flush()
    order = SalesOrder(
        id=str(uuid.uuid4()),
        company_id=company.id,
        number=f"SO-{uuid.uuid4().hex[:6]}",
        customer_id=customer.id,
        order_date=datetime.now(timezone.utc),
        status=status,
        order_type="funeral",
        subtotal=Decimal(total),
        tax_rate=Decimal("0"),
        tax_amount=Decimal("0"),
        total=Decimal(total),
        deceased_name=deceased,
        scheduled_date=when,
        service_time=time(9, 0),
        cemetery_id=cemetery.id if cemetery is not None else None,
    )
    session.add(order)
    session.flush()
    session.add(SalesOrderLine(
        id=str(uuid.uuid4()),
        sales_order_id=order.id,
        description=vault,
        quantity=Decimal("1"),
        unit_price=Decimal(total),
        line_total=Decimal(total),
        sort_order=0,
    ))
    session.flush()
    return order


def test_a_question_reads_this_tenant_and_adds_the_total(db):
    today = date.today()
    home = _company(db, "Order List Home")
    other = _company(db, "Order List Other")
    ours = _order(
        db, home, customer_name="Hopkins", deceased="John R. Albright",
        total="120.50", when=today, cemetery_name="St. Mary's", cemetery_city="Skaneateles",
    )
    _order(
        db, other, customer_name="Hopkins", deceased="John R. Albright",
        total="999.00", when=today,
    )
    _order(
        db, home, customer_name="Hopkins", deceased="Cancelled Person",
        status="cancelled", total="50.00", when=today,
    )

    body = ask(
        db,
        company_id=home.id,
        user_id=None,
        role_slug="office_staff",
        phrase="Hopkins orders this month",
        question=None,
        remove_pill_id=None,
        teach_phrase=None,
        today=today,
        propose=None,
    )

    assert body["kind"] == "question"
    ids = [row["id"] for row in body["orders"]]
    assert ids == [ours.id]
    row = body["orders"][0]
    assert row["deceased_name"] == "John R. Albright"
    assert "Monticello" in row["meta"]
    assert "Hopkins" in row["meta"]
    assert "Skaneateles" in row["meta"]
    assert body["totals"]["total"] == "120.50"
    assert body["totals"]["count"] == 1
    summary = sales_order_summary(db, home.id, ours.id, today)
    assert summary is not None
    assert summary["vault"] == "Monticello"
    assert sales_order_summary(db, home.id, "not-this-tenant", today) is None


def _person(session, company, role, first: str) -> User:
    user = User(
        id=str(uuid.uuid4()),
        company_id=company.id,
        email=f"{first.lower()}-{uuid.uuid4().hex[:8]}@example.com",
        username=f"{first.lower()}{uuid.uuid4().hex[:8]}",
        hashed_password="x",
        first_name=first,
        last_name="Driver",
        role_id=role.id,
        is_active=True,
    )
    session.add(user)
    session.flush()
    return user


def _assign(session, company, order, assignee_id: str | None, *, status: str = "scheduled"):
    session.add(Delivery(
        id=str(uuid.uuid4()),
        company_id=company.id,
        delivery_type="vault",
        order_id=order.id,
        customer_id=order.customer_id,
        status=status,
        primary_assignee_id=assignee_id,
        requested_date=order.scheduled_date,
    ))
    session.flush()


def _ask(db, company_id, *, user_id, role_slug, phrase, question=None, today):
    return ask(
        db,
        company_id=company_id,
        user_id=user_id,
        role_slug=role_slug,
        phrase=phrase,
        question=question,
        remove_pill_id=None,
        teach_phrase=None,
        today=today,
        propose=None,
    )


def test_the_default_view_includes_every_delivered_order_that_is_not_invoiced(db):
    today = date(2026, 10, 8)
    home = _company(db, "Order List Old Deliveries")
    old = _order(
        db, home, customer_name="Hopkins", deceased="Edith Carr",
        status="completed", total="40.00", when=date(2026, 1, 1),
    )
    old.delivered_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    old.completed_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    db.flush()

    body = _ask(
        db, home.id, user_id=None, role_slug="office_staff", phrase="orders", today=today,
    )
    groups = {group["id"]: [row["id"] for row in group["orders"]] for group in body["groups"]}
    assert old.id in groups["delivered_not_invoiced"]


def test_every_driver_question_is_limited_to_their_deliveries(db):
    today = date(2026, 10, 8)  # Thursday, so Friday is the next day
    friday = date(2026, 10, 9)

    home = _company(db, "Order List Driver Scope")
    role = Role(
        id=str(uuid.uuid4()), company_id=home.id, name="Driver", slug="driver", is_active=True,
    )
    db.add(role)
    db.flush()
    dana = _person(db, home, role, "Dana")
    owen = _person(db, home, role, "Owen")

    dana_today = _order(
        db, home, customer_name="Hopkins", deceased="Dana Stop", total="120.50", when=today,
    )
    _assign(db, home, dana_today, dana.id)
    dana_done = _order(
        db, home, customer_name="Hopkins", deceased="Dana Done",
        status="delivered", total="80.00", when=today,
    )
    dana_done.delivered_at = datetime.now(timezone.utc)
    db.flush()
    _assign(db, home, dana_done, dana.id, status="completed")
    dana_old = _order(
        db, home, customer_name="Hopkins", deceased="Dana Old",
        status="completed", total="40.00", when=date(2026, 1, 1),
    )
    dana_old.delivered_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    dana_old.completed_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    db.flush()
    _assign(db, home, dana_old, dana.id, status="completed")
    dana_friday = _order(
        db, home, customer_name="Hopkins", deceased="Dana Friday", total="10.00", when=friday,
    )
    _assign(db, home, dana_friday, dana.id)

    owen_today = _order(
        db, home, customer_name="Hopkins", deceased="Owen Stop", total="200.00", when=today,
    )
    _assign(db, home, owen_today, owen.id)
    owen_old = _order(
        db, home, customer_name="Hopkins", deceased="Owen Old",
        status="completed", total="90.00", when=date(2026, 1, 1),
    )
    owen_old.delivered_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    owen_old.completed_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    db.flush()
    _assign(db, home, owen_old, owen.id, status="completed")
    owen_friday = _order(
        db, home, customer_name="Hopkins", deceased="Owen Friday", total="15.00", when=friday,
    )
    _assign(db, home, owen_friday, owen.id)
    _order(db, home, customer_name="Hopkins", deceased="Nobody Stop", total="50.00", when=today)
    dropped = _order(
        db, home, customer_name="Hopkins", deceased="Dana Dropped", total="75.00", when=today,
    )
    _assign(db, home, dropped, dana.id, status="cancelled")

    month = _ask(
        db, home.id, user_id=dana.id, role_slug="driver",
        phrase="Hopkins orders this month", today=today,
    )
    assert {row["id"] for row in month["orders"]} == {dana_today.id, dana_done.id, dana_friday.id}
    assert month["totals"]["total"] == "210.50"

    office = _ask(
        db, home.id, user_id=None, role_slug="office_staff",
        phrase="Hopkins orders this month", today=today,
    )
    office_ids = {row["id"] for row in office["orders"]}
    assert owen_today.id in office_ids
    assert dana_today.id in office_ids

    unbilled = _ask(
        db, home.id, user_id=dana.id, role_slug="driver",
        phrase="delivered, not invoiced", today=today,
    )
    assert {row["id"] for row in unbilled["orders"]} == {dana_done.id, dana_old.id}

    day = _ask(db, home.id, user_id=dana.id, role_slug="driver", phrase="orders", today=today)
    assert day["title"] == "Going out today"
    assert day["hint"] == "Your deliveries."
    assert {row["id"] for row in day["orders"]} == {dana_today.id, dana_done.id}

    going = _ask(
        db, home.id, user_id=dana.id, role_slug="driver",
        phrase="going out friday", today=today,
    )
    assert {row["id"] for row in going["orders"]} == {dana_friday.id}

    opened = _ask(
        db, home.id, user_id=dana.id, role_slug="driver",
        phrase="open the Dana Stop order", today=today,
    )
    assert opened["kind"] == "open_order"
    assert opened["open_order_id"] == dana_today.id
    hidden = _ask(
        db, home.id, user_id=dana.id, role_slug="driver",
        phrase="open the Owen Stop order", today=today,
    )
    assert hidden["kind"] == "unrecognized"
    assert "open_order_id" not in hidden

    question = OrderQuestion.model_validate(month["question"])
    total = _ask(
        db, home.id, user_id=dana.id, role_slug="driver",
        phrase="how much is that?", question=question, today=today,
    )
    assert total["kind"] == "total"
    assert total["totals"]["total"] == "210.50"

    assert sales_order_summary(
        db, home.id, owen_today.id, today, role_slug="driver", user_id=dana.id,
    ) is None
    own = sales_order_summary(
        db, home.id, dana_today.id, today, role_slug="driver", user_id=dana.id,
    )
    assert own is not None and own["id"] == dana_today.id
    assert sales_order_summary(
        db, home.id, owen_today.id, today, role_slug="office_staff", user_id=None,
    ) is not None


def test_a_driver_with_no_user_sees_no_orders(db):
    today = date(2026, 10, 8)
    home = _company(db, "Order List Driver Missing")
    role = Role(
        id=str(uuid.uuid4()), company_id=home.id, name="Driver", slug="driver", is_active=True,
    )
    db.add(role)
    db.flush()
    dana = _person(db, home, role, "Dana")
    order = _order(db, home, customer_name="Hopkins", deceased="Dana Stop", when=today)
    _assign(db, home, order, dana.id)

    body = _ask(
        db, home.id, user_id=None, role_slug="driver",
        phrase="Hopkins orders this month", today=today,
    )
    assert body["orders"] == []
    assert sales_order_summary(
        db, home.id, order.id, today, role_slug="driver", user_id=None,
    ) is None


def test_a_draft_proof_is_a_proof_flag_on_the_order(db):
    today = date.today()
    home = _company(db, "Order List Proof")
    order = _order(
        db, home, customer_name="Hopkins", deceased="Walter Penn", when=today,
    )
    db.add(LegacyProof(
        id=str(uuid.uuid4()),
        company_id=home.id,
        source="manual",
        order_id=order.id,
        legacy_type="cameo",
        status="draft",
    ))
    db.flush()

    body = ask(
        db,
        company_id=home.id,
        user_id=None,
        role_slug="office_staff",
        phrase="orders",
        question=None,
        remove_pill_id=None,
        teach_phrase=None,
        today=today,
        propose=None,
    )
    rows = [row for group in body["groups"] for row in group["orders"]]
    match = next(row for row in rows if row["id"] == order.id)
    assert match["flag"] == "proof"
    assert match["action"] == "proof"
    assert match["action_label"] == "Open the proof"
