"""S-1 entity portal — behavior tests (§4.2).

Covers:
  - flagship company_entity card: identity, contacts (CRM Contact
    adapter), recent/open orders via the Customer.master_company_id
    join, permission-gated financial standing (same pipeline as the
    registry gates: permission_service / `invoice.approve`)
  - quiet omission of the financial section for users without the
    permission (omitted_sections contract)
  - peek-wrapped builders enrich with pivots (contact→company,
    order→invoice/customer)
  - resolver: company_entity is searchable (8th type; the §4.9
    "Hopkins" demo path)
  - route: unknown type → 400, cross-tenant / missing → 404
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture(scope="module")
def portal_tenant():
    """Tenant with the full flagship-card constellation:
    CompanyEntity ('Hopkins Funeral Home') + AR Customer joined via
    master_company_id + 2 contacts + 2 orders (1 open) + 2 invoices
    (1 overdue) + a second tenant for isolation checks."""
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.company_entity import CompanyEntity
    from app.models.contact import Contact
    from app.models.customer import Customer
    from app.models.invoice import Invoice
    from app.models.role import Role
    from app.models.sales_order import SalesOrder
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"PORTAL-{suffix}",
            slug=f"portal-{suffix}",
            is_active=True,
            vertical="manufacturing",
        )
        db.add(co)
        db.flush()

        admin_role = Role(
            id=str(uuid.uuid4()), company_id=co.id,
            name="Admin", slug="admin", is_system=True,
        )
        limited_role = Role(
            id=str(uuid.uuid4()), company_id=co.id,
            name="Driver", slug="driver", is_system=True,
        )
        db.add_all([admin_role, limited_role])
        db.flush()

        admin = User(
            id=str(uuid.uuid4()), company_id=co.id,
            email=f"admin-{suffix}@portal.co", first_name="A",
            last_name="Dmin", hashed_password="x", is_active=True,
            role_id=admin_role.id,
        )
        limited = User(
            id=str(uuid.uuid4()), company_id=co.id,
            email=f"driver-{suffix}@portal.co", first_name="D",
            last_name="River", hashed_password="x", is_active=True,
            role_id=limited_role.id,
        )
        db.add_all([admin, limited])
        db.flush()

        ce = CompanyEntity(
            id=str(uuid.uuid4()), company_id=co.id,
            name="Hopkins Funeral Home", phone="+13155550100",
            email="office@hopkinsfh.example.com", city="Auburn",
            state="NY", is_funeral_home=True, is_customer=True,
            is_active=True,
        )
        db.add(ce)
        db.flush()

        cust = Customer(
            id=str(uuid.uuid4()), company_id=co.id,
            name="Hopkins Funeral Home", master_company_id=ce.id,
            is_active=True, current_balance=Decimal("4500.00"),
            credit_limit=Decimal("20000.00"), payment_terms="net30",
        )
        db.add(cust)
        db.flush()

        for i, (title, name) in enumerate(
            [("Director", "Mary Hopkins"), ("Office Manager", "Sam Lee")]
        ):
            db.add(
                Contact(
                    id=str(uuid.uuid4()), company_id=co.id,
                    master_company_id=ce.id, name=name, title=title,
                    phone=f"+1315555010{i+1}", is_active=True,
                )
            )

        so_open = SalesOrder(
            id=str(uuid.uuid4()), company_id=co.id, number="SO-PORTAL-1",
            customer_id=cust.id, status="confirmed",
            order_date=datetime.now(timezone.utc),
            subtotal=Decimal("1000"), tax_rate=Decimal("0"),
            tax_amount=Decimal("0"), total=Decimal("1000"),
        )
        so_done = SalesOrder(
            id=str(uuid.uuid4()), company_id=co.id, number="SO-PORTAL-2",
            customer_id=cust.id, status="delivered",
            order_date=datetime.now(timezone.utc) - timedelta(days=9),
            subtotal=Decimal("800"), tax_rate=Decimal("0"),
            tax_amount=Decimal("0"), total=Decimal("800"),
        )
        db.add_all([so_open, so_done])
        db.flush()

        inv_overdue = Invoice(
            id=str(uuid.uuid4()), company_id=co.id, number="INV-PORTAL-1",
            customer_id=cust.id, status="sent",
            invoice_date=datetime.now(timezone.utc) - timedelta(days=45),
            due_date=datetime.now(timezone.utc) - timedelta(days=15),
            subtotal=Decimal("800"), tax_rate=Decimal("0"),
            tax_amount=Decimal("0"), total=Decimal("800"),
            amount_paid=Decimal("0"),
        )
        inv_current = Invoice(
            id=str(uuid.uuid4()), company_id=co.id, number="INV-PORTAL-2",
            customer_id=cust.id, status="sent",
            invoice_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=30),
            subtotal=Decimal("500"), tax_rate=Decimal("0"),
            tax_amount=Decimal("0"), total=Decimal("500"),
            amount_paid=Decimal("0"),
        )
        db.add_all([inv_overdue, inv_current])
        db.flush()

        # Second tenant — isolation probe.
        other = Company(
            id=str(uuid.uuid4()), name=f"OTHER-{suffix}",
            slug=f"other-{suffix}", is_active=True,
            vertical="manufacturing",
        )
        db.add(other)
        db.flush()
        other_role = Role(
            id=str(uuid.uuid4()), company_id=other.id,
            name="Admin", slug="admin", is_system=True,
        )
        db.add(other_role)
        db.flush()
        other_admin = User(
            id=str(uuid.uuid4()), company_id=other.id,
            email=f"other-{suffix}@portal.co", first_name="O",
            last_name="Ther", hashed_password="x", is_active=True,
            role_id=other_role.id,
        )
        db.add(other_admin)
        db.commit()

        out = {
            "slug": co.slug,
            "admin_token": create_access_token(
                {"sub": admin.id, "company_id": co.id}
            ),
            "limited_token": create_access_token(
                {"sub": limited.id, "company_id": co.id}
            ),
            "other_slug": other.slug,
            "other_token": create_access_token(
                {"sub": other_admin.id, "company_id": other.id}
            ),
            "ce_id": ce.id,
            "so_open_id": so_open.id,
            "inv_id": inv_overdue.id,
            "_company_ids": [co.id, other.id],
        }
    finally:
        db.close()

    yield out

    # Teardown — no company litter (see tests/test_so_class_killers.py
    # world fixture for the pattern; per-table commits so one failed
    # delete doesn't roll back the rest).
    from sqlalchemy import text as sql_text

    from app.database import SessionLocal as _SL

    db = _SL()
    try:
        for t in (
            "invoices", "sales_orders", "contacts", "customers",
            "company_entities", "users", "roles", "companies",
        ):
            for cid in out["_company_ids"]:
                try:
                    col = "id" if t == "companies" else "company_id"
                    db.execute(
                        sql_text(f"DELETE FROM {t} WHERE {col} = :c"),
                        {"c": cid},
                    )
                    db.commit()
                except Exception:
                    db.rollback()
    finally:
        db.close()


def _headers(token: str, slug: str) -> dict:
    return {"Authorization": f"Bearer {token}", "X-Company-Slug": slug}


# ── Flagship card ───────────────────────────────────────────────────


def test_company_card_identity_contacts_orders(client, portal_tenant):
    r = client.get(
        f"/api/v1/command-bar/portal/company_entity/{portal_tenant['ce_id']}",
        headers=_headers(portal_tenant["admin_token"], portal_tenant["slug"]),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["display_label"] == "Hopkins Funeral Home"
    assert body["navigate_url"].endswith(portal_tenant["ce_id"])
    p = body["portal"]
    assert "Funeral home" in p["roles"]
    assert len(p["contacts"]) == 2
    assert {o["number"] for o in p["recent_orders"]} == {
        "SO-PORTAL-1", "SO-PORTAL-2",
    }
    assert p["open_order_count"] == 1


def test_company_card_financial_for_admin(client, portal_tenant):
    r = client.get(
        f"/api/v1/command-bar/portal/company_entity/{portal_tenant['ce_id']}",
        headers=_headers(portal_tenant["admin_token"], portal_tenant["slug"]),
    )
    body = r.json()
    fin = body["portal"]["financial"]
    assert fin["outstanding"] == 1300.0  # 800 overdue + 500 current
    assert fin["overdue_count"] == 1
    assert fin["overdue_total"] == 800.0
    assert fin["payment_terms"] == "net30"
    assert body["omitted_sections"] == []


def test_company_card_financial_quietly_omitted_without_permission(
    client, portal_tenant
):
    """Driver role has no invoice.approve → same card, financial
    section absent, omitted_sections names it (quiet-omit contract)."""
    r = client.get(
        f"/api/v1/command-bar/portal/company_entity/{portal_tenant['ce_id']}",
        headers=_headers(
            portal_tenant["limited_token"], portal_tenant["slug"]
        ),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "financial" not in body["portal"]
    assert body["omitted_sections"] == ["financial"]
    # Non-gated sections still render.
    assert len(body["portal"]["contacts"]) == 2


def test_company_card_pivots_and_tel_action(client, portal_tenant):
    r = client.get(
        f"/api/v1/command-bar/portal/company_entity/{portal_tenant['ce_id']}",
        headers=_headers(portal_tenant["admin_token"], portal_tenant["slug"]),
    )
    body = r.json()
    pivot_types = {p["entity_type"] for p in body["pivots"]}
    assert "contact" in pivot_types
    assert "sales_order" in pivot_types
    kinds = {a["kind"] for a in body["actions"]}
    assert "tel" in kinds  # ruled v1 click-to-call transport
    assert "navigate" in kinds


# ── Peek-wrapped builders ───────────────────────────────────────────


def test_sales_order_card_pivots_to_company_and_invoice(
    client, portal_tenant
):
    r = client.get(
        f"/api/v1/command-bar/portal/sales_order/{portal_tenant['so_open_id']}",
        headers=_headers(portal_tenant["admin_token"], portal_tenant["slug"]),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["entity_type"] == "sales_order"
    pivot_types = {p["entity_type"] for p in body["pivots"]}
    assert "company_entity" in pivot_types  # customer → flagship card


def test_invoice_card_wraps_peek_payload(client, portal_tenant):
    r = client.get(
        f"/api/v1/command-bar/portal/invoice/{portal_tenant['inv_id']}",
        headers=_headers(portal_tenant["admin_token"], portal_tenant["slug"]),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # Base payload comes from the peek builder (zero duplication).
    assert body["portal"].get("invoice_number") or body["portal"]


# ── Resolver: 8th searchable type (§4.9 demo path) ──────────────────


def test_resolver_finds_company_entity_by_name(portal_tenant):
    from app.database import SessionLocal
    from app.services.command_bar.resolver import resolve

    db = SessionLocal()
    try:
        from app.models.company import Company

        co = (
            db.query(Company)
            .filter(Company.slug == portal_tenant["slug"])
            .first()
        )
        hits = resolve(db, query_text="Hopkins", company_id=co.id)
        assert any(
            h.entity_type == "company_entity"
            and h.primary_label == "Hopkins Funeral Home"
            for h in hits
        ), [f"{h.entity_type}:{h.primary_label}" for h in hits]
        ce_hit = next(
            h for h in hits if h.entity_type == "company_entity"
        )
        assert ce_hit.url == f"/vault/crm/companies/{ce_hit.entity_id}"
    finally:
        db.close()


# ── Route errors + tenant isolation ─────────────────────────────────


def test_unknown_entity_type_is_400(client, portal_tenant):
    r = client.get(
        "/api/v1/command-bar/portal/starship/abc",
        headers=_headers(portal_tenant["admin_token"], portal_tenant["slug"]),
    )
    assert r.status_code == 400


def test_cross_tenant_company_card_is_404(client, portal_tenant):
    """Other tenant's admin cannot hydrate this tenant's company —
    the card is strictly tenant-scoped (cross-tenant STOP line)."""
    r = client.get(
        f"/api/v1/command-bar/portal/company_entity/{portal_tenant['ce_id']}",
        headers=_headers(
            portal_tenant["other_token"], portal_tenant["other_slug"]
        ),
    )
    assert r.status_code == 404


def test_missing_entity_is_404(client, portal_tenant):
    r = client.get(
        f"/api/v1/command-bar/portal/company_entity/{uuid.uuid4()}",
        headers=_headers(portal_tenant["admin_token"], portal_tenant["slug"]),
    )
    assert r.status_code == 404
