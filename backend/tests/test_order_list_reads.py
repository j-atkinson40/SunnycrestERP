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
from app.models.legacy_proof import LegacyProof
from app.models.sales_order import SalesOrder, SalesOrderLine
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
