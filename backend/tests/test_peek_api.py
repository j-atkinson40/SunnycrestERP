"""Peek API — follow-up 4 of the UI/UX arc (arc finale) tests.

Covers GET /api/v1/peek/{entity_type}/{entity_id}:

  - 6 entity types × happy path (returns display_label +
    navigate_url + peek dict with entity-appropriate fields)
  - Unknown entity_type → 400 listing available types
  - Missing entity (valid type, unknown id) → 404
  - Tenant isolation: tenant A cannot peek tenant B's entity
  - Auth required → 401/403
  - Arc telemetry: record("peek_fetch", ...) called on every path
  - TRACKED_ENDPOINTS registration (regression guard)
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


def _make_ctx(*, vertical: str = "manufacturing"):
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"PEEK-{suffix}",
            slug=f"peek-{suffix}",
            is_active=True,
            vertical=vertical,
        )
        db.add(co)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name="Admin",
            slug="admin",
            is_system=True,
        )
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"u-{suffix}@peek.co",
            first_name="Peek",
            last_name="User",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        token = create_access_token({"sub": user.id, "company_id": co.id})
        return {
            "user_id": user.id,
            "company_id": co.id,
            "token": token,
            "slug": co.slug,
            "headers": {
                "Authorization": f"Bearer {token}",
                "X-Company-Slug": co.slug,
            },
        }
    finally:
        db.close()


@pytest.fixture
def admin_ctx():
    return _make_ctx()


@pytest.fixture
def other_ctx():
    return _make_ctx()


@pytest.fixture(autouse=True)
def _reset_arc_telemetry():
    from app.services.arc_telemetry import reset_for_testing

    reset_for_testing()
    yield
    reset_for_testing()


# ── Seeders ─────────────────────────────────────────────────────────


def _seed_case(db, *, company_id: str, **kwargs) -> str:
    from app.models.funeral_case import CaseDeceased, FuneralCase

    case = FuneralCase(
        id=str(uuid.uuid4()),
        company_id=company_id,
        case_number=kwargs.get("case_number", "C-001"),
        current_step=kwargs.get("current_step", "arrangement_conference"),
        status=kwargs.get("status", "active"),
    )
    db.add(case)
    db.flush()
    dec = CaseDeceased(
        id=str(uuid.uuid4()),
        case_id=case.id,
        company_id=company_id,
        first_name=kwargs.get("first_name", "John"),
        last_name=kwargs.get("last_name", "Smith"),
        date_of_death=kwargs.get("date_of_death", date(2026, 3, 15)),
    )
    db.add(dec)
    db.commit()
    return case.id


def _seed_customer_and_invoice(db, *, company_id: str) -> tuple[str, str]:
    from app.models.customer import Customer
    from app.models.invoice import Invoice

    cust = Customer(
        id=str(uuid.uuid4()),
        company_id=company_id,
        name="Hopkins Funeral Home",
        is_active=True,
    )
    db.add(cust)
    db.flush()
    inv = Invoice(
        id=str(uuid.uuid4()),
        company_id=company_id,
        number="INV-2026-0001",
        customer_id=cust.id,
        status="sent",
        invoice_date=datetime.now(timezone.utc),
        due_date=datetime.now(timezone.utc) + timedelta(days=30),
        subtotal=Decimal("500.00"),
        tax_rate=Decimal("0.08"),
        tax_amount=Decimal("40.00"),
        total=Decimal("540.00"),
        amount_paid=Decimal("100.00"),
    )
    db.add(inv)
    db.commit()
    return cust.id, inv.id


def _seed_sales_order(db, *, company_id: str) -> str:
    from app.models.customer import Customer
    from app.models.sales_order import SalesOrder, SalesOrderLine

    cust = Customer(
        id=str(uuid.uuid4()),
        company_id=company_id,
        name="Riverside FH",
        is_active=True,
    )
    db.add(cust)
    db.flush()
    so = SalesOrder(
        id=str(uuid.uuid4()),
        company_id=company_id,
        number="SO-2026-0042",
        customer_id=cust.id,
        status="confirmed",
        order_date=datetime.now(timezone.utc),
        required_date=datetime.now(timezone.utc) + timedelta(days=7),
        subtotal=Decimal("1000.00"),
        tax_rate=Decimal("0.08"),
        tax_amount=Decimal("80.00"),
        total=Decimal("1080.00"),
        deceased_name="Jane Doe",
    )
    db.add(so)
    db.flush()
    for i in range(3):
        db.add(
            SalesOrderLine(
                id=str(uuid.uuid4()),
                sales_order_id=so.id,
                product_id=None,
                description=f"Line {i}",
                quantity=Decimal("1"),
                unit_price=Decimal("100"),
                line_total=Decimal("100"),
            )
        )
    db.commit()
    return so.id


def _seed_task(db, *, company_id: str, assignee_user_id: str) -> str:
    from app.services.task_service import create_task

    t = create_task(
        db,
        company_id=company_id,
        title="Verify quote pricing",
        created_by_user_id=assignee_user_id,
        assignee_user_id=assignee_user_id,
        priority="high",
        due_date=date.today() + timedelta(days=2),
        description="Check that the Hopkins quote uses correct tiers.",
    )
    return t.id


def _seed_contact(db, *, company_id: str) -> str:
    from app.models.company_entity import CompanyEntity
    from app.models.contact import Contact

    ce = CompanyEntity(
        id=str(uuid.uuid4()),
        company_id=company_id,
        name="Acme Supplies",
        is_active=True,
    )
    db.add(ce)
    db.flush()
    contact = Contact(
        id=str(uuid.uuid4()),
        company_id=company_id,
        master_company_id=ce.id,
        name="Taylor Reyes",
        title="Sales Director",
        phone="+15551234567",
        email="taylor@acme.example",
        is_active=True,
    )
    db.add(contact)
    db.commit()
    return contact.id


def _seed_saved_view(db, *, user) -> str:
    from app.services.saved_views import create_saved_view
    from app.services.saved_views.types import (
        Permissions,
        Presentation,
        Query,
        SavedViewConfig,
    )

    config = SavedViewConfig(
        query=Query(entity_type="sales_order", filters=[], sort=[]),
        presentation=Presentation(mode="list"),
        permissions=Permissions(owner_user_id=user.id, visibility="private"),
    )
    view = create_saved_view(
        db,
        user=user,
        title="My active orders",
        description="Preview test view",
        config=config,
    )
    return view.id


# ── Happy path × 6 entity types ────────────────────────────────────


class TestPeekHappyPath:
    def test_fh_case(self, client, db_session, admin_ctx):
        case_id = _seed_case(
            db_session, company_id=admin_ctx["company_id"]
        )
        r = client.get(
            f"/api/v1/peek/fh_case/{case_id}", headers=admin_ctx["headers"]
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["entity_type"] == "fh_case"
        assert body["entity_id"] == case_id
        assert "John Smith" in body["display_label"]
        assert body["navigate_url"] == f"/fh/cases/{case_id}"
        assert body["peek"]["deceased_name"] == "John Smith"
        assert body["peek"]["date_of_death"] == "2026-03-15"
        assert body["peek"]["case_number"] == "C-001"

    def test_invoice(self, client, db_session, admin_ctx):
        _, inv_id = _seed_customer_and_invoice(
            db_session, company_id=admin_ctx["company_id"]
        )
        r = client.get(
            f"/api/v1/peek/invoice/{inv_id}", headers=admin_ctx["headers"]
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["peek"]["invoice_number"] == "INV-2026-0001"
        assert body["peek"]["customer_name"] == "Hopkins Funeral Home"
        assert body["peek"]["amount_total"] == 540.0
        assert body["peek"]["amount_paid"] == 100.0
        assert body["peek"]["amount_due"] == 440.0
        assert body["peek"]["status"] == "sent"
        assert body["navigate_url"] == f"/ar/invoices/{inv_id}"

    def test_sales_order(self, client, db_session, admin_ctx):
        so_id = _seed_sales_order(
            db_session, company_id=admin_ctx["company_id"]
        )
        r = client.get(
            f"/api/v1/peek/sales_order/{so_id}",
            headers=admin_ctx["headers"],
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["peek"]["order_number"] == "SO-2026-0042"
        assert body["peek"]["customer_name"] == "Riverside FH"
        assert body["peek"]["deceased_name"] == "Jane Doe"
        assert body["peek"]["line_count"] == 3
        assert body["peek"]["status"] == "confirmed"

    def test_task(self, client, db_session, admin_ctx):
        task_id = _seed_task(
            db_session,
            company_id=admin_ctx["company_id"],
            assignee_user_id=admin_ctx["user_id"],
        )
        r = client.get(
            f"/api/v1/peek/task/{task_id}", headers=admin_ctx["headers"]
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["peek"]["title"] == "Verify quote pricing"
        assert body["peek"]["priority"] == "high"
        # Assignee name comes from user.first_name + last_name.
        assert body["peek"]["assignee_name"] == "Peek User"
        assert body["navigate_url"] == f"/tasks/{task_id}"

    def test_contact(self, client, db_session, admin_ctx):
        contact_id = _seed_contact(
            db_session, company_id=admin_ctx["company_id"]
        )
        r = client.get(
            f"/api/v1/peek/contact/{contact_id}",
            headers=admin_ctx["headers"],
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["peek"]["name"] == "Taylor Reyes"
        assert body["peek"]["title"] == "Sales Director"
        assert body["peek"]["phone"] == "+15551234567"
        assert body["peek"]["email"] == "taylor@acme.example"
        assert body["peek"]["company_name"] == "Acme Supplies"

    def test_saved_view(self, client, db_session, admin_ctx):
        from app.models.user import User

        user = (
            db_session.query(User)
            .filter(User.id == admin_ctx["user_id"])
            .one()
        )
        view_id = _seed_saved_view(db_session, user=user)
        r = client.get(
            f"/api/v1/peek/saved_view/{view_id}",
            headers=admin_ctx["headers"],
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["peek"]["title"] == "My active orders"
        assert body["peek"]["entity_type"] == "sales_order"
        assert body["peek"]["presentation_mode"] == "list"
        assert body["peek"]["filter_count"] == 0
        assert body["peek"]["sort_count"] == 0
        assert body["navigate_url"] == f"/saved-views/{view_id}"


# ── Error paths ────────────────────────────────────────────────────


class TestPeekErrors:
    def test_unknown_entity_type(self, client, admin_ctx):
        r = client.get(
            "/api/v1/peek/nonexistent_type/abc",
            headers=admin_ctx["headers"],
        )
        assert r.status_code == 400
        assert "no peek builder" in r.text.lower()

    def test_entity_not_found(self, client, admin_ctx):
        r = client.get(
            "/api/v1/peek/fh_case/does-not-exist",
            headers=admin_ctx["headers"],
        )
        assert r.status_code == 404

    def test_tenant_isolation(self, client, db_session, admin_ctx, other_ctx):
        """Entity belongs to tenant A; tenant B cannot peek it."""
        case_id = _seed_case(
            db_session, company_id=other_ctx["company_id"]
        )
        r = client.get(
            f"/api/v1/peek/fh_case/{case_id}",
            headers=admin_ctx["headers"],
        )
        assert r.status_code == 404  # absent from caller's tenant

    def test_auth_required(self, client):
        r = client.get("/api/v1/peek/fh_case/abc")
        assert r.status_code in (401, 403)


# ── Telemetry wrapping ─────────────────────────────────────────────


class TestPeekTelemetry:
    def test_registration(self):
        from app.services.arc_telemetry import TRACKED_ENDPOINTS

        assert "peek_fetch" in TRACKED_ENDPOINTS

    def test_snapshot_includes_peek_fetch_key(self):
        from app.services.arc_telemetry import snapshot

        snap = snapshot()
        endpoint_keys = {e["endpoint"] for e in snap["endpoints"]}
        assert "peek_fetch" in endpoint_keys

    def test_successful_call_records_peek_fetch(
        self, client, db_session, admin_ctx
    ):
        from app.services import arc_telemetry as _arc_t

        case_id = _seed_case(db_session, company_id=admin_ctx["company_id"])
        with patch.object(
            _arc_t, "record", wraps=_arc_t.record
        ) as spy:
            r = client.get(
                f"/api/v1/peek/fh_case/{case_id}",
                headers=admin_ctx["headers"],
            )
        assert r.status_code == 200
        peek_calls = [
            c for c in spy.call_args_list if c.args and c.args[0] == "peek_fetch"
        ]
        assert len(peek_calls) >= 1
        assert peek_calls[0].kwargs.get("errored") is False

    def test_errored_call_records_errored_true(self, client, admin_ctx):
        from app.services import arc_telemetry as _arc_t

        with patch.object(
            _arc_t, "record", wraps=_arc_t.record
        ) as spy:
            r = client.get(
                "/api/v1/peek/nonexistent_type/abc",
                headers=admin_ctx["headers"],
            )
        assert r.status_code == 400
        peek_calls = [
            c for c in spy.call_args_list if c.args and c.args[0] == "peek_fetch"
        ]
        assert len(peek_calls) >= 1
        assert peek_calls[0].kwargs.get("errored") is True
