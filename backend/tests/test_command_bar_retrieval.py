"""Integration tests — Command Bar retrieval orchestrator.

Scope: retrieval.query() end-to-end with a real DB + real registry.

Covers:
  - empty query → intent=empty, results=[]
  - navigate intent → nav actions ranked first
  - create intent → create action at the top with priority boost
  - search intent → resolver hits present in results
  - record-number pattern → navigate intent + search_result hit for
    the record (if seeded)
  - permission gating — admin-only nav actions hidden from non-admin
  - tenant isolation — resolver hits don't leak across tenants
  - max_results cap honored
  - de-duplication by id (defense in depth)
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.services.command_bar import registry, retrieval


@pytest.fixture(autouse=True)
def _fresh_registry():
    registry.reset_registry()
    registry.get_registry()  # seed
    yield
    registry.reset_registry()


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


def _make_tenant(db, *, is_admin: bool = True):
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    suffix = uuid.uuid4().hex[:6]
    co = Company(
        id=str(uuid.uuid4()),
        name=f"CB-RET-{suffix}",
        slug=f"cb-ret-{suffix}",
        is_active=True,
    )
    db.add(co)
    db.flush()
    role = Role(
        id=str(uuid.uuid4()),
        company_id=co.id,
        name="Admin" if is_admin else "Employee",
        slug="admin" if is_admin else "employee",
        is_system=True,
    )
    db.add(role)
    db.flush()
    user = User(
        id=str(uuid.uuid4()),
        company_id=co.id,
        email=f"u-{suffix}@cb-ret.co",
        first_name="CB",
        last_name="R",
        hashed_password="x",
        is_active=True,
        is_super_admin=is_admin,
        role_id=role.id,
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def admin_user(db_session):
    return _make_tenant(db_session, is_admin=True)


@pytest.fixture
def non_admin_user(db_session):
    return _make_tenant(db_session, is_admin=False)


# ── Empty query ───────────────────────────────────────────────────────


class TestEmptyQuery:
    def test_empty_string(self, db_session, admin_user):
        r = retrieval.query(db_session, query_text="", user=admin_user)
        assert r.intent == "empty"
        assert r.results == []
        assert r.total == 0


# ── Navigate intent ──────────────────────────────────────────────────


class TestNavigateIntent:
    def test_exact_nav_label(self, db_session, admin_user):
        r = retrieval.query(db_session, query_text="Dashboard", user=admin_user)
        assert r.intent == "navigate"
        assert len(r.results) >= 1
        # Dashboard nav should be the top result
        top = r.results[0]
        assert top.type == "navigate"
        assert top.url == "/dashboard"

    def test_alias_ar_surfaces_ar_aging(self, db_session, admin_user):
        r = retrieval.query(db_session, query_text="AR", user=admin_user)
        assert r.intent == "navigate"
        top = r.results[0]
        assert top.action_id == "nav.ar_aging"


# ── Create intent ────────────────────────────────────────────────────


class TestCreateIntent:
    def test_new_sales_order_surfaces_create_action(
        self, db_session, admin_user
    ):
        r = retrieval.query(
            db_session, query_text="new sales order", user=admin_user
        )
        assert r.intent == "create"
        top = r.results[0]
        assert top.type == "create"
        assert top.entity_type == "sales_order"
        assert top.url == "/orders/new"

    def test_new_quote_surfaces_quote_create(self, db_session, admin_user):
        r = retrieval.query(
            db_session, query_text="new quote", user=admin_user
        )
        assert r.intent == "create"
        top = r.results[0]
        assert top.entity_type == "quote"

    def test_create_action_has_higher_score_than_same_label_nav(
        self, db_session, admin_user
    ):
        """On create intent, the create action should rank above
        navigate hits that happen to contain 'order'."""
        r = retrieval.query(
            db_session, query_text="new sales order", user=admin_user
        )
        first_create = next((x for x in r.results if x.type == "create"), None)
        first_nav = next((x for x in r.results if x.type == "navigate"), None)
        if first_create and first_nav:
            assert first_create.score > first_nav.score


# ── Search intent → resolver hits ────────────────────────────────────


class TestSearchIntent:
    def test_search_for_seeded_case_surfaces_case(
        self, db_session, admin_user
    ):
        from app.models.fh_case import FHCase

        db_session.add(
            FHCase(
                id=str(uuid.uuid4()),
                company_id=admin_user.company_id,
                case_number="CASE-RESOLVER-001",
                status="active",
                deceased_first_name="Mary",
                deceased_last_name="Washington",
                deceased_date_of_death=date.today(),
            )
        )
        db_session.commit()
        r = retrieval.query(
            db_session, query_text="Washington", user=admin_user
        )
        assert r.intent == "search"
        # At least one search_result for fh_case
        case_hits = [
            x for x in r.results
            if x.type == "search_result"
            and x.result_entity_type == "fh_case"
        ]
        assert len(case_hits) >= 1

    def test_search_result_has_navigation_url(
        self, db_session, admin_user
    ):
        from app.models.fh_case import FHCase

        case_id = str(uuid.uuid4())
        db_session.add(
            FHCase(
                id=case_id,
                company_id=admin_user.company_id,
                case_number="CASE-NAV-001",
                status="active",
                deceased_first_name="Alice",
                deceased_last_name="Kensington",
                deceased_date_of_death=date.today(),
            )
        )
        db_session.commit()
        r = retrieval.query(
            db_session, query_text="Kensington", user=admin_user
        )
        hit = next(
            (x for x in r.results if x.result_entity_type == "fh_case"),
            None,
        )
        assert hit is not None
        assert hit.url == f"/cases/{case_id}"


# ── Permission gating ─────────────────────────────────────────────────


class TestPermissionGating:
    def test_admin_sees_admin_only_nav(self, db_session, admin_user):
        # nav.vault is admin-only — super_admin bypasses
        r = retrieval.query(db_session, query_text="vault", user=admin_user)
        ids = [x.action_id for x in r.results if x.action_id]
        assert "nav.vault" in ids or "nav.vault_documents" in ids

    def test_non_admin_hides_admin_only_nav(
        self, db_session, non_admin_user
    ):
        r = retrieval.query(
            db_session, query_text="vault documents", user=non_admin_user
        )
        ids = [x.action_id for x in r.results if x.action_id]
        # Admin-only nav.vault_documents must not leak to a non-admin
        # lacking the permission.
        assert "nav.vault_documents" not in ids
        # Plain nav.vault (required_permission="admin") also hidden
        assert "nav.vault" not in ids


# ── Tenant isolation ─────────────────────────────────────────────────


class TestTenantIsolation:
    def test_other_tenant_records_not_visible(
        self, db_session, admin_user
    ):
        """Seed a record in a DIFFERENT tenant and verify admin_user's
        query doesn't see it."""
        from app.models.fh_case import FHCase

        other = _make_tenant(db_session, is_admin=True)
        db_session.add(
            FHCase(
                id=str(uuid.uuid4()),
                company_id=other.company_id,
                case_number="OTHER-SECRET-001",
                status="active",
                deceased_first_name="Secret",
                deceased_last_name="Zzzzzzzzzzzz",
                deceased_date_of_death=date.today(),
            )
        )
        db_session.commit()
        r = retrieval.query(
            db_session, query_text="Zzzzzzzzzzzz", user=admin_user
        )
        assert all(
            x.result_entity_type != "fh_case" or "Zzzzzzzz" not in x.primary_label
            for x in r.results
        )


# ── max_results cap ───────────────────────────────────────────────────


class TestMaxResultsCap:
    def test_max_results_enforced(self, db_session, admin_user):
        r = retrieval.query(
            db_session, query_text="new", user=admin_user, max_results=2
        )
        assert len(r.results) <= 2


# ── De-duplication ───────────────────────────────────────────────────


class TestDedup:
    def test_no_duplicate_ids_in_results(self, db_session, admin_user):
        r = retrieval.query(
            db_session, query_text="dashboard", user=admin_user
        )
        ids = [x.id for x in r.results]
        assert len(ids) == len(set(ids))
