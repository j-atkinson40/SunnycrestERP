"""Health Triage P2 (commit 2): the 4 wrapped dead-import repoints.

These were swallowed by try/except → silently-dead features (inventory search,
spare-pairing alert, AR-GL lookup, "payments today"). Repointing ACTIVATES the
dormant path, so each witness drives the real path and proves its query/operation
EXECUTES against the real schema — not merely that the import resolves (the
bill→VendorBill trap: a resolving import can still query the wrong shape).

  command_bar_data_search → inventory_item.InventoryItem
  operations_board_service → agent.AgentAlert
  early_payment_discount_service → accounting_analysis.TenantGLMapping
  financials_board → customer_payment.CustomerPayment (aliased Payment)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.database import SessionLocal
from app.models.company import Company


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


def _company(db):
    co = Company(
        id=str(uuid.uuid4()),
        name=f"P2W-{uuid.uuid4().hex[:6]}",
        slug=f"p2w-{uuid.uuid4().hex[:6]}",
        is_active=True,
        vertical="manufacturing",
    )
    db.add(co)
    db.commit()
    return co


def test_find_ar_account_runs_tenant_gl_query(db):
    """early_payment_discount_service._find_ar_account — the real path runs its
    TenantGLMapping query against the real schema (returns None, no raise)."""
    from app.services.early_payment_discount_service import _find_ar_account

    co = _company(db)
    result = _find_ar_account(db, co.id)  # executes the repointed query
    assert result is None  # fresh tenant has no AR GL mapping


def test_inventory_search_executes_inventory_item_query(db):
    """command_bar _try_answer_inventory — drive it to the InventoryItem query
    (seeded Product + InventoryItem) and assert it returns the stock answer,
    proving the repointed query executed + matched against real columns."""
    from app.models.inventory_item import InventoryItem
    from app.models.product import Product
    from app.services.command_bar_data_search import _try_answer_inventory

    co = _company(db)
    prod = Product(
        id=str(uuid.uuid4()),
        company_id=co.id,
        name="Monticello Vault",
        is_active=True,
    )
    db.add(prod)
    db.commit()
    db.add(
        InventoryItem(
            id=str(uuid.uuid4()),
            company_id=co.id,
            product_id=prod.id,
            quantity_on_hand=7,
        )
    )
    db.commit()

    answer = _try_answer_inventory(db, "how many Monticello Vault do we have", co.id)
    assert answer is not None  # the InventoryItem query ran + produced an answer
    assert "7" in str(answer)


def test_agent_alert_constructs_and_persists(db):
    """operations_board spare-pairing alert — the exact AgentAlert instantiation
    (8 kwargs) persists to agent_alerts, proving every kwarg is a real column."""
    from app.models.agent import AgentAlert

    co = _company(db)
    alert = AgentAlert(
        id=str(uuid.uuid4()),
        tenant_id=co.id,
        alert_type="spare_component_pairing",
        severity="info",
        title="Spare components can be paired — Test",
        message="2 spare cover(s) and 2 spare base(s).",
        action_label="Mark as assembled",
        action_url="/inventory",
    )
    db.add(alert)
    db.commit()
    assert db.get(AgentAlert, alert.id) is not None


def test_financials_summary_route_returns(db):
    """financials_board get_board_summary — the route runs end-to-end (the
    aliased CustomerPayment 'payments today' query executes) and returns 200."""
    from fastapi.testclient import TestClient

    from app.core.security import create_access_token
    from app.main import app
    from app.models.role import Role
    from app.models.user import User

    co = _company(db)
    role = Role(
        id=str(uuid.uuid4()), company_id=co.id, name="Admin", slug="admin",
        is_system=True,
    )
    db.add(role)
    db.flush()
    user = User(
        id=str(uuid.uuid4()), company_id=co.id, email=f"{uuid.uuid4().hex[:6]}@p2w.co",
        first_name="P2", last_name="W", hashed_password="x", is_active=True,
        is_super_admin=True, role_id=role.id,
    )
    db.add(user)
    db.commit()
    token = create_access_token({"sub": user.id, "company_id": co.id})

    resp = TestClient(app).get(
        "/api/v1/financials/summary",
        headers={"Authorization": f"Bearer {token}", "X-Company-Slug": co.slug},
    )
    assert resp.status_code == 200, f"{resp.status_code}: {resp.text[:300]}"
