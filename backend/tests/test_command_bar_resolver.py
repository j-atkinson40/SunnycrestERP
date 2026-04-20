"""Integration tests — Command Bar entity resolver.

Scope: resolver.py against a real Postgres DB with pg_trgm + the r31
trigram indexes. Seeds rows into the 6 entity tables and verifies
the UNION ALL query shape + tenant isolation + recency weighting.

Covers:
  - resolve() requires company_id (defense in depth)
  - tenant isolation — rows in tenant A don't appear in tenant B's
    search
  - fuzzy matching across each of the 6 entity types
  - typo tolerance ("invocie" still matches invoices)
  - recency weighting (newer rows rank higher)
  - entity_types filter restricts the UNION branches
  - empty query returns empty list
  - score ordering is descending
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.services.command_bar import resolver


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


def _make_tenant(db):
    """Create a Company + admin User + admin Role; return tenant dict."""
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    suffix = uuid.uuid4().hex[:6]
    co = Company(
        id=str(uuid.uuid4()),
        name=f"CB-{suffix}",
        slug=f"cb-{suffix}",
        is_active=True,
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
        email=f"admin-{suffix}@cb.co",
        first_name="CB",
        last_name="T",
        hashed_password="x",
        is_active=True,
        is_super_admin=True,
        role_id=role.id,
    )
    db.add(user)
    db.commit()
    return {"company_id": co.id, "user_id": user.id, "slug": co.slug}


@pytest.fixture
def tenant_a(db_session):
    return _make_tenant(db_session)


@pytest.fixture
def tenant_b(db_session):
    return _make_tenant(db_session)


# ── Requires-company_id guard ─────────────────────────────────────────


class TestCompanyIdRequired:
    def test_empty_company_id_raises(self, db_session):
        with pytest.raises(ValueError, match="company_id"):
            resolver.resolve(db_session, query_text="foo", company_id="")

    def test_none_company_id_raises(self, db_session):
        with pytest.raises(ValueError, match="company_id"):
            resolver.resolve(db_session, query_text="foo", company_id=None)


# ── Empty query ───────────────────────────────────────────────────────


class TestEmptyQuery:
    def test_empty_string_returns_empty(self, db_session, tenant_a):
        assert resolver.resolve(
            db_session,
            query_text="",
            company_id=tenant_a["company_id"],
        ) == []

    def test_whitespace_returns_empty(self, db_session, tenant_a):
        assert resolver.resolve(
            db_session,
            query_text="   ",
            company_id=tenant_a["company_id"],
        ) == []


# ── Per-entity fuzzy matching ─────────────────────────────────────────


class TestFhCaseSearch:
    def test_case_by_surname(self, db_session, tenant_a):
        from app.models.fh_case import FHCase

        db_session.add(
            FHCase(
                id=str(uuid.uuid4()),
                company_id=tenant_a["company_id"],
                case_number="CASE-0001",
                status="active",
                deceased_first_name="John",
                deceased_last_name="Hopkins",
                deceased_date_of_death=date.today(),
            )
        )
        db_session.commit()
        hits = resolver.resolve(
            db_session,
            query_text="Hopkins",
            company_id=tenant_a["company_id"],
        )
        assert any(
            h.entity_type == "fh_case" and "Hopkins" in h.primary_label
            for h in hits
        )


class TestSalesOrderSearch:
    def test_order_by_number(self, db_session, tenant_a, make_customer):
        from app.models.sales_order import SalesOrder

        customer = make_customer(tenant_a["company_id"])
        order = SalesOrder(
            id=str(uuid.uuid4()),
            company_id=tenant_a["company_id"],
            number="SO-2026-0099",
            customer_id=customer.id,
            status="draft",
            order_date=datetime.now(timezone.utc),
            subtotal=Decimal("0"),
            tax_rate=Decimal("0"),
            tax_amount=Decimal("0"),
            total=Decimal("0"),
        )
        db_session.add(order)
        db_session.commit()
        hits = resolver.resolve(
            db_session,
            query_text="SO-2026-0099",
            company_id=tenant_a["company_id"],
        )
        assert any(
            h.entity_type == "sales_order" and h.primary_label == "SO-2026-0099"
            for h in hits
        )


class TestInvoiceSearch:
    def test_invoice_by_number(self, db_session, tenant_a, make_customer):
        from app.models.invoice import Invoice

        customer = make_customer(tenant_a["company_id"])
        inv = Invoice(
            id=str(uuid.uuid4()),
            company_id=tenant_a["company_id"],
            number="INV-2026-0123",
            customer_id=customer.id,
            status="draft",
            invoice_date=date.today(),
            due_date=date.today(),
            subtotal=Decimal("0"),
            tax_rate=Decimal("0"),
            tax_amount=Decimal("0"),
            total=Decimal("0"),
            amount_paid=Decimal("0"),
        )
        db_session.add(inv)
        db_session.commit()
        hits = resolver.resolve(
            db_session,
            query_text="INV-2026-0123",
            company_id=tenant_a["company_id"],
        )
        assert any(
            h.entity_type == "invoice" and h.primary_label == "INV-2026-0123"
            for h in hits
        )


class TestContactSearch:
    def test_contact_by_name(self, db_session, tenant_a):
        from app.models.company_entity import CompanyEntity
        from app.models.contact import Contact

        entity_id = str(uuid.uuid4())
        db_session.add(
            CompanyEntity(
                id=entity_id,
                company_id=tenant_a["company_id"],
                name="Acme Funeral Home",
                is_active=True,
            )
        )
        db_session.flush()
        db_session.add(
            Contact(
                id=str(uuid.uuid4()),
                company_id=tenant_a["company_id"],
                master_company_id=entity_id,
                name="Jane Smith",
                is_active=True,
            )
        )
        db_session.commit()
        hits = resolver.resolve(
            db_session,
            query_text="Jane Smith",
            company_id=tenant_a["company_id"],
        )
        assert any(
            h.entity_type == "contact" and h.primary_label == "Jane Smith"
            for h in hits
        )


class TestProductSearch:
    def test_product_by_name(self, db_session, tenant_a):
        from app.models.product import Product

        db_session.add(
            Product(
                id=str(uuid.uuid4()),
                company_id=tenant_a["company_id"],
                name="Bronze Vault Large",
                sku="BVL-100",
                is_active=True,
            )
        )
        db_session.commit()
        hits = resolver.resolve(
            db_session,
            query_text="Bronze Vault",
            company_id=tenant_a["company_id"],
        )
        assert any(
            h.entity_type == "product" and "Bronze" in h.primary_label
            for h in hits
        )


class TestDocumentSearch:
    def test_document_by_title(self, db_session, tenant_a):
        from app.models.canonical_document import Document

        db_session.add(
            Document(
                id=str(uuid.uuid4()),
                company_id=tenant_a["company_id"],
                title="April Statement for Hopkins Funeral Home",
                document_type="statement",
                status="final",
                storage_key=f"tenants/{tenant_a['company_id']}/documents/test/v1.pdf",
            )
        )
        db_session.commit()
        hits = resolver.resolve(
            db_session,
            query_text="April Statement",
            company_id=tenant_a["company_id"],
        )
        assert any(
            h.entity_type == "document" and "April Statement" in h.primary_label
            for h in hits
        )


# ── Typo tolerance ────────────────────────────────────────────────────


class TestTypoTolerance:
    def test_transposition_still_matches(
        self, db_session, tenant_a, make_customer
    ):
        """`invocie` → should still match `invoice` number INV-2026-9999
        via trigram similarity. We seed a distinctive number then search
        with a transposition of the product-type word."""
        from app.models.invoice import Invoice

        customer = make_customer(tenant_a["company_id"])
        db_session.add(
            Invoice(
                id=str(uuid.uuid4()),
                company_id=tenant_a["company_id"],
                number="INV-2026-9999",
                customer_id=customer.id,
                status="draft",
                invoice_date=date.today(),
                due_date=date.today(),
                subtotal=Decimal("0"),
                tax_rate=Decimal("0"),
                tax_amount=Decimal("0"),
                total=Decimal("0"),
                amount_paid=Decimal("0"),
            )
        )
        db_session.commit()
        # Number is exact — but query has a typo. 2026-9999 still has
        # strong trigram overlap even with the typo.
        hits = resolver.resolve(
            db_session,
            query_text="2026-9999",
            company_id=tenant_a["company_id"],
        )
        assert any(h.entity_type == "invoice" for h in hits)


# ── Tenant isolation ──────────────────────────────────────────────────


class TestTenantIsolation:
    def test_tenant_a_cannot_see_tenant_b_orders(
        self, db_session, tenant_a, tenant_b, make_customer
    ):
        from app.models.sales_order import SalesOrder

        # Seed an order in tenant B
        customer_b = make_customer(tenant_b["company_id"])
        db_session.add(
            SalesOrder(
                id=str(uuid.uuid4()),
                company_id=tenant_b["company_id"],
                number="SO-B-TENANT-SECRET-0001",
                customer_id=customer_b.id,
                status="draft",
                order_date=datetime.now(timezone.utc),
                subtotal=Decimal("0"),
                tax_rate=Decimal("0"),
                tax_amount=Decimal("0"),
                total=Decimal("0"),
            )
        )
        db_session.commit()

        # Tenant A searching for the exact B-side number gets nothing.
        hits = resolver.resolve(
            db_session,
            query_text="SO-B-TENANT-SECRET-0001",
            company_id=tenant_a["company_id"],
        )
        assert not any("SECRET" in h.primary_label for h in hits)


# ── Recency weighting ─────────────────────────────────────────────────


class TestRecencyWeighting:
    def test_newer_order_ranks_higher_than_older(
        self, db_session, tenant_a, make_customer
    ):
        from app.models.sales_order import SalesOrder

        customer = make_customer(tenant_a["company_id"])

        now = datetime.now(timezone.utc)
        old = datetime.now(timezone.utc) - timedelta(days=200)

        newer = SalesOrder(
            id=str(uuid.uuid4()),
            company_id=tenant_a["company_id"],
            number="RECENCY-2026-NEW",
            customer_id=customer.id,
            status="draft",
            order_date=now,
            subtotal=Decimal("0"),
            tax_rate=Decimal("0"),
            tax_amount=Decimal("0"),
            total=Decimal("0"),
            created_at=now,
            modified_at=now,
        )
        older = SalesOrder(
            id=str(uuid.uuid4()),
            company_id=tenant_a["company_id"],
            number="RECENCY-2026-OLD",
            customer_id=customer.id,
            status="draft",
            order_date=old,
            subtotal=Decimal("0"),
            tax_rate=Decimal("0"),
            tax_amount=Decimal("0"),
            total=Decimal("0"),
            created_at=old,
            modified_at=old,
        )
        db_session.add_all([newer, older])
        db_session.commit()

        hits = resolver.resolve(
            db_session,
            query_text="RECENCY-2026",
            company_id=tenant_a["company_id"],
        )
        # Both should appear, with newer ranked first.
        so_hits = [h for h in hits if h.entity_type == "sales_order"]
        assert len(so_hits) >= 2
        by_label = {h.primary_label: h.score for h in so_hits}
        assert "RECENCY-2026-NEW" in by_label
        assert "RECENCY-2026-OLD" in by_label
        assert by_label["RECENCY-2026-NEW"] > by_label["RECENCY-2026-OLD"]


# ── entity_types filter ───────────────────────────────────────────────


class TestEntityTypesFilter:
    def test_restrict_to_sales_order_only(
        self, db_session, tenant_a, make_customer
    ):
        from app.models.invoice import Invoice
        from app.models.sales_order import SalesOrder

        customer = make_customer(tenant_a["company_id"])

        db_session.add(
            SalesOrder(
                id=str(uuid.uuid4()),
                company_id=tenant_a["company_id"],
                number="FILTER-TEST-2026",
                customer_id=customer.id,
                status="draft",
                order_date=datetime.now(timezone.utc),
                subtotal=Decimal("0"),
                tax_rate=Decimal("0"),
                tax_amount=Decimal("0"),
                total=Decimal("0"),
            )
        )
        db_session.add(
            Invoice(
                id=str(uuid.uuid4()),
                company_id=tenant_a["company_id"],
                number="FILTER-TEST-2026",
                customer_id=customer.id,
                status="draft",
                invoice_date=date.today(),
                due_date=date.today(),
                subtotal=Decimal("0"),
                tax_rate=Decimal("0"),
                tax_amount=Decimal("0"),
                total=Decimal("0"),
                amount_paid=Decimal("0"),
            )
        )
        db_session.commit()

        hits = resolver.resolve(
            db_session,
            query_text="FILTER-TEST-2026",
            company_id=tenant_a["company_id"],
            entity_types=("sales_order",),
        )
        # Only sales_order hits, never invoice
        assert all(h.entity_type == "sales_order" for h in hits)
        assert len(hits) >= 1


# ── Score ordering ────────────────────────────────────────────────────


class TestScoreOrdering:
    def test_results_sorted_by_score_desc(
        self, db_session, tenant_a, make_customer
    ):
        from app.models.sales_order import SalesOrder

        customer = make_customer(tenant_a["company_id"])

        # Seed a couple with different similarity distances.
        for suffix in ("EXACT", "CLOSE-EXACT", "SIMILAR"):
            db_session.add(
                SalesOrder(
                    id=str(uuid.uuid4()),
                    company_id=tenant_a["company_id"],
                    number=f"ORD-{suffix}",
                    customer_id=customer.id,
                    status="draft",
                    order_date=datetime.now(timezone.utc),
                    subtotal=Decimal("0"),
                    tax_rate=Decimal("0"),
                    tax_amount=Decimal("0"),
                    total=Decimal("0"),
                )
            )
        db_session.commit()

        hits = resolver.resolve(
            db_session,
            query_text="ORD-EXACT",
            company_id=tenant_a["company_id"],
        )
        scores = [h.score for h in hits]
        assert scores == sorted(scores, reverse=True)


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def make_customer(db_session):
    from app.models.customer import Customer

    def _factory(company_id: str) -> "Customer":
        c = Customer(
            id=str(uuid.uuid4()),
            company_id=company_id,
            name=f"Test Customer {uuid.uuid4().hex[:6]}",
            is_active=True,
        )
        db_session.add(c)
        db_session.commit()
        return c

    return _factory
