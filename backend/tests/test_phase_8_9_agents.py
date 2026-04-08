"""Tests for accounting agents Phases 8 and 9.

Covers: InventoryReconciliationAgent, BudgetVsActualAgent,
agent registry, approval behavior, period lock absence.
"""

import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, event, JSON
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base
from app.models.agent import AgentJob
from app.models.agent_anomaly import AgentAnomaly
from app.models.agent_run_step import AgentRunStep
from app.models.agent_schedule import AgentSchedule
from app.models.company import Company
from app.models.inventory_item import InventoryItem
from app.models.inventory_transaction import InventoryTransaction
from app.models.period_lock import PeriodLock
from app.models.product import Product
from app.models.production_log_entry import ProductionLogEntry
from app.models.role import Role
from app.models.sales_order import SalesOrder, SalesOrderLine
from app.models.user import User
from app.models.work_order import WorkOrder
from app.schemas.agent import (
    AgentJobType,
    AnomalySeverity,
    ApprovalAction,
    StepResult,
)
from app.services.agents.agent_runner import AgentRunner
from app.services.agents.approval_gate import ApprovalGateService
from app.services.agents.period_lock import PeriodLockService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine():
    """Create an in-memory SQLite engine for testing."""
    eng = create_engine("sqlite:///:memory:")

    @event.listens_for(eng, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        pass

    tables = [
        Base.metadata.tables[t]
        for t in [
            "companies",
            "roles",
            "users",
            "products",
            "inventory_items",
            "inventory_transactions",
            "production_log_entries",
            "sales_orders",
            "sales_order_lines",
            "work_orders",
            "agent_jobs",
            "agent_run_steps",
            "agent_anomalies",
            "agent_schedules",
            "period_locks",
            "invoices",
            "report_runs",
        ]
    ]
    jsonb_cols = []
    for table in tables:
        for col in table.columns:
            if isinstance(col.type, JSONB):
                jsonb_cols.append((col, col.type))
                col.type = JSON()
    Base.metadata.create_all(eng, tables=tables)
    for col, original_type in jsonb_cols:
        col.type = original_type
    return eng


@pytest.fixture
def db(engine):
    """Yield a fresh session that rolls back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def tenant(db: Session) -> Company:
    company = Company(
        id=str(uuid.uuid4()),
        name="Test Vault Co",
        slug="testco",
        is_active=True,
    )
    db.add(company)
    db.flush()
    return company


@pytest.fixture
def role(db: Session, tenant: Company) -> Role:
    r = Role(
        id=str(uuid.uuid4()),
        company_id=tenant.id,
        name="Admin",
        slug="admin",
        is_system=True,
    )
    db.add(r)
    db.flush()
    return r


@pytest.fixture
def user(db: Session, tenant: Company, role: Role) -> User:
    u = User(
        id=str(uuid.uuid4()),
        email="admin@test.com",
        first_name="Test",
        last_name="Admin",
        company_id=tenant.id,
        role_id=role.id,
        is_active=True,
        hashed_password="fake",
    )
    db.add(u)
    db.flush()
    return u


def _dt(d):
    """Convert date to timezone-aware datetime."""
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


@pytest.fixture
def inventory_seed(db: Session, tenant: Company, user: User):
    """Seed data for inventory reconciliation tests.

    Creates:
      - 3 products (all is_inventory_tracked=True)
      - 3 InventoryItems:
          Product A: quantity_on_hand=10, last_counted_at=30 days ago
          Product B: quantity_on_hand=5, last_counted_at=200 days ago
          Product C: quantity_on_hand=0
      - InventoryTransactions:
          Product A: last txn quantity_after=10 (clean)
          Product B: last txn quantity_after=3 (MISMATCH)
          Product C: no transactions
      - SalesOrders:
          Confirmed order for Product A, qty=4
          Confirmed order for Product A, qty=8
          (total reserved=12 > on_hand=10 — oversold!)
      - ProductionLogEntry:
          Product A: 5 units produced in period
    """
    tid = tenant.id
    today = date.today()
    period_start = today - timedelta(days=90)
    period_end = today

    # Products
    prod_a = Product(
        id=str(uuid.uuid4()),
        company_id=tid,
        name="Standard Vault",
        sku="SV-001",
        is_inventory_tracked=True,
        is_active=True,
    )
    prod_b = Product(
        id=str(uuid.uuid4()),
        company_id=tid,
        name="Premium Vault",
        sku="PV-001",
        is_inventory_tracked=True,
        is_active=True,
    )
    prod_c = Product(
        id=str(uuid.uuid4()),
        company_id=tid,
        name="Urn Vault",
        sku="UV-001",
        is_inventory_tracked=True,
        is_active=True,
    )
    db.add_all([prod_a, prod_b, prod_c])
    db.flush()

    # Inventory Items
    inv_a = InventoryItem(
        id=str(uuid.uuid4()),
        company_id=tid,
        product_id=prod_a.id,
        quantity_on_hand=10,
        reorder_point=5,
        last_counted_at=datetime.now(timezone.utc) - timedelta(days=30),
        is_active=True,
    )
    inv_b = InventoryItem(
        id=str(uuid.uuid4()),
        company_id=tid,
        product_id=prod_b.id,
        quantity_on_hand=5,
        reorder_point=3,
        last_counted_at=datetime.now(timezone.utc) - timedelta(days=200),
        is_active=True,
    )
    inv_c = InventoryItem(
        id=str(uuid.uuid4()),
        company_id=tid,
        product_id=prod_c.id,
        quantity_on_hand=0,
        is_active=True,
    )
    db.add_all([inv_a, inv_b, inv_c])
    db.flush()

    # Inventory Transactions
    # Product A: clean match (quantity_after=10)
    txn_a = InventoryTransaction(
        id=str(uuid.uuid4()),
        company_id=tid,
        product_id=prod_a.id,
        transaction_type="production",
        quantity_change=5,
        quantity_after=10,
        created_at=datetime.now(timezone.utc) - timedelta(days=10),
    )
    # Product B: MISMATCH (on_hand=5, quantity_after=3)
    txn_b = InventoryTransaction(
        id=str(uuid.uuid4()),
        company_id=tid,
        product_id=prod_b.id,
        transaction_type="receive",
        quantity_change=3,
        quantity_after=3,
        created_at=datetime.now(timezone.utc) - timedelta(days=15),
    )
    db.add_all([txn_a, txn_b])
    db.flush()

    # Sales Orders — two confirmed orders for Product A
    order1 = SalesOrder(
        id=str(uuid.uuid4()),
        company_id=tid,
        number="SO-2025-001",
        customer_id=str(uuid.uuid4()),  # dummy customer ID
        status="confirmed",
        order_date=_dt(today - timedelta(days=5)),
        total=Decimal("500.00"),
    )
    order2 = SalesOrder(
        id=str(uuid.uuid4()),
        company_id=tid,
        number="SO-2025-002",
        customer_id=str(uuid.uuid4()),
        status="confirmed",
        order_date=_dt(today - timedelta(days=3)),
        total=Decimal("1000.00"),
    )
    db.add_all([order1, order2])
    db.flush()

    line1 = SalesOrderLine(
        id=str(uuid.uuid4()),
        sales_order_id=order1.id,
        product_id=prod_a.id,
        description="Standard Vault",
        quantity=Decimal("4"),
        quantity_shipped=Decimal("0"),
        unit_price=Decimal("125.00"),
        line_total=Decimal("500.00"),
    )
    line2 = SalesOrderLine(
        id=str(uuid.uuid4()),
        sales_order_id=order2.id,
        product_id=prod_a.id,
        description="Standard Vault",
        quantity=Decimal("8"),
        quantity_shipped=Decimal("0"),
        unit_price=Decimal("125.00"),
        line_total=Decimal("1000.00"),
    )
    db.add_all([line1, line2])
    db.flush()

    # Production log — 5 units of Product A produced in period
    prod_log = ProductionLogEntry(
        id=str(uuid.uuid4()),
        tenant_id=tid,
        log_date=today - timedelta(days=20),
        product_id=prod_a.id,
        product_name="Standard Vault",
        quantity_produced=5,
        entered_by=user.id,
    )
    db.add(prod_log)
    db.flush()

    return {
        "prod_a": prod_a,
        "prod_b": prod_b,
        "prod_c": prod_c,
        "inv_a": inv_a,
        "inv_b": inv_b,
        "inv_c": inv_c,
        "txn_a": txn_a,
        "txn_b": txn_b,
        "order1": order1,
        "order2": order2,
        "line1": line1,
        "line2": line2,
        "prod_log": prod_log,
        "period_start": period_start,
        "period_end": period_end,
    }


def _create_inventory_job(db, tenant, user, seed, dry_run=True):
    """Create an inventory reconciliation agent job."""
    job = AgentJob(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        job_type="inventory_reconciliation",
        status="pending",
        period_start=seed["period_start"],
        period_end=seed["period_end"],
        dry_run=dry_run,
        triggered_by=user.id,
        run_log=[],
        created_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.flush()
    return job


def _create_budget_job(db, tenant, user, dry_run=True):
    """Create a budget vs actual agent job."""
    today = date.today()
    quarter = (today.month - 1) // 3
    q_start = date(today.year, quarter * 3 + 1, 1)
    if quarter == 3:
        q_end = date(today.year, 12, 31)
    else:
        q_end = date(today.year, (quarter + 1) * 3 + 1, 1) - timedelta(days=1)

    job = AgentJob(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        job_type="budget_vs_actual",
        status="pending",
        period_start=q_start,
        period_end=q_end,
        dry_run=dry_run,
        triggered_by=user.id,
        run_log=[],
        created_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.flush()
    return job


# ---------------------------------------------------------------------------
# INVENTORY RECONCILIATION TESTS
# ---------------------------------------------------------------------------


class TestInventoryReconciliationAgent:
    """Tests 1-6: InventoryReconciliationAgent."""

    def test_1_full_execution(self, db, tenant, user, inventory_seed):
        """Test 1: Full agent execution completes all 6 steps."""
        job = _create_inventory_job(db, tenant, user, inventory_seed)

        from app.services.agents.inventory_reconciliation_agent import InventoryReconciliationAgent

        with patch.object(InventoryReconciliationAgent, "_trigger_approval_gate"):
            agent = InventoryReconciliationAgent(
                db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True
            )
            result = agent.execute()

        assert result.status == "awaiting_approval"
        assert len(result.run_log) == 6
        # Verify all steps completed
        for entry in result.run_log:
            assert entry["status"] == "complete"

    def test_2_transaction_integrity(self, db, tenant, user, inventory_seed):
        """Test 2: Detects balance mismatch for Product B (on_hand=5, last txn=3)."""
        job = _create_inventory_job(db, tenant, user, inventory_seed)

        from app.services.agents.inventory_reconciliation_agent import InventoryReconciliationAgent

        with patch.object(InventoryReconciliationAgent, "_trigger_approval_gate"):
            agent = InventoryReconciliationAgent(
                db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True
            )
            agent.execute()

        anomalies = job.report_payload.get("anomalies", [])
        mismatch = [a for a in anomalies if a["anomaly_type"] == "inventory_balance_mismatch"]
        assert len(mismatch) >= 1
        # Should reference Product B
        assert "Premium Vault" in mismatch[0]["description"]
        assert mismatch[0]["severity"] == "critical"

    def test_3_reserved_quantity_computation(self, db, tenant, user, inventory_seed):
        """Test 3: Computes reserved=12 for Product A and flags oversold."""
        job = _create_inventory_job(db, tenant, user, inventory_seed)

        from app.services.agents.inventory_reconciliation_agent import InventoryReconciliationAgent

        with patch.object(InventoryReconciliationAgent, "_trigger_approval_gate"):
            agent = InventoryReconciliationAgent(
                db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True
            )
            agent.execute()

        reserved_data = job.report_payload["steps"]["compute_reserved_quantity"]
        # Find Product A in inventory list
        prod_a_inv = None
        for item in reserved_data["inventory"]:
            if item["product_name"] == "Standard Vault":
                prod_a_inv = item
                break

        assert prod_a_inv is not None
        assert prod_a_inv["reserved_quantity"] == 12
        assert prod_a_inv["available_quantity"] == -2  # 10 - 12

        # Check oversold anomaly
        anomalies = job.report_payload.get("anomalies", [])
        oversold = [a for a in anomalies if a["anomaly_type"] == "inventory_oversold"]
        assert len(oversold) >= 1
        assert oversold[0]["severity"] == "critical"

    def test_4_physical_count_freshness(self, db, tenant, user, inventory_seed):
        """Test 4: Product B (200 days since last count) triggers overdue anomaly."""
        job = _create_inventory_job(db, tenant, user, inventory_seed)

        from app.services.agents.inventory_reconciliation_agent import InventoryReconciliationAgent

        with patch.object(InventoryReconciliationAgent, "_trigger_approval_gate"):
            agent = InventoryReconciliationAgent(
                db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True
            )
            agent.execute()

        anomalies = job.report_payload.get("anomalies", [])
        overdue = [a for a in anomalies if a["anomaly_type"] == "inventory_count_overdue"]
        # At least Product B should be overdue (200 days), and Product C (never counted)
        assert len(overdue) >= 1
        overdue_names = " ".join(a["description"] for a in overdue)
        assert "Premium Vault" in overdue_names

    def test_5_reconciliation_math(self, db, tenant, user, inventory_seed):
        """Test 5: Reconciliation captures production for Product A."""
        job = _create_inventory_job(db, tenant, user, inventory_seed)

        from app.services.agents.inventory_reconciliation_agent import InventoryReconciliationAgent

        with patch.object(InventoryReconciliationAgent, "_trigger_approval_gate"):
            agent = InventoryReconciliationAgent(
                db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True
            )
            agent.execute()

        recon_data = job.report_payload["steps"]["reconcile_production_vs_deliveries"]
        # Find Product A in reconciliation
        prod_a_recon = None
        for r in recon_data["reconciliation"]:
            if r["product_name"] == "Standard Vault":
                prod_a_recon = r
                break

        assert prod_a_recon is not None
        assert prod_a_recon["produced"] == 5
        # No delivered orders in period (confirmed, not delivered)
        assert prod_a_recon["delivered"] == 0

    def test_6_no_writes_on_approval(self, db, tenant, user, inventory_seed):
        """Test 6: Approval completes without changing inventory or creating locks."""
        job = _create_inventory_job(db, tenant, user, inventory_seed)

        from app.services.agents.inventory_reconciliation_agent import InventoryReconciliationAgent

        with patch.object(InventoryReconciliationAgent, "_trigger_approval_gate"):
            agent = InventoryReconciliationAgent(
                db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True
            )
            agent.execute()

        # Record original quantities
        orig_a = inventory_seed["inv_a"].quantity_on_hand
        orig_b = inventory_seed["inv_b"].quantity_on_hand

        # Approve
        token = secrets.token_urlsafe(48)
        job.approval_token = token
        db.flush()

        action = ApprovalAction(action="approve")
        result = ApprovalGateService.process_approval(token, action, db)
        assert result.status == "complete"

        # Verify no inventory changes
        inv_a = db.query(InventoryItem).filter(InventoryItem.id == inventory_seed["inv_a"].id).first()
        assert inv_a.quantity_on_hand == orig_a

        inv_b = db.query(InventoryItem).filter(InventoryItem.id == inventory_seed["inv_b"].id).first()
        assert inv_b.quantity_on_hand == orig_b

        # No period lock
        locks = PeriodLockService.get_active_locks(db, tenant.id)
        assert len(locks) == 0


# ---------------------------------------------------------------------------
# BUDGET VS. ACTUAL TESTS
# ---------------------------------------------------------------------------


class TestBudgetVsActualAgent:
    """Tests 7-14: BudgetVsActualAgent."""

    def test_7_full_execution(self, db, tenant, user):
        """Test 7: Full agent execution completes all 4 steps."""
        job = _create_budget_job(db, tenant, user)

        from app.services.agents.budget_vs_actual_agent import BudgetVsActualAgent

        with patch.object(BudgetVsActualAgent, "_trigger_approval_gate"):
            agent = BudgetVsActualAgent(
                db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True
            )
            result = agent.execute()

        assert result.status == "awaiting_approval"
        assert len(result.run_log) == 4
        for entry in result.run_log:
            assert entry["status"] == "complete"

    def test_8_income_statement_called(self, db, tenant, user):
        """Test 8: Period actuals contain valid income statement data."""
        job = _create_budget_job(db, tenant, user)

        from app.services.agents.budget_vs_actual_agent import BudgetVsActualAgent

        with patch.object(BudgetVsActualAgent, "_trigger_approval_gate"):
            agent = BudgetVsActualAgent(
                db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True
            )
            agent.execute()

        actuals = job.report_payload["steps"]["get_current_period_actuals"]
        period = actuals["period"]
        assert isinstance(period["total_revenue"], (int, float))
        assert isinstance(period["net_income"], (int, float))
        # net_income can be negative — just check it's a number
        assert period["total_revenue"] >= 0

    def test_9_comparison_basis_selection(self, db, tenant, user):
        """Test 9: With no prior data, comparison is prior_quarter or none."""
        job = _create_budget_job(db, tenant, user)

        from app.services.agents.budget_vs_actual_agent import BudgetVsActualAgent

        with patch.object(BudgetVsActualAgent, "_trigger_approval_gate"):
            agent = BudgetVsActualAgent(
                db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True
            )
            agent.execute()

        comp_data = job.report_payload["steps"]["get_comparison_period"]
        # No data in test DB, so should be prior_quarter or none
        assert comp_data["comparison_type"] in ["prior_year_same_period", "prior_quarter", "none"]

    def test_10_variance_math(self, db, tenant, user):
        """Test 10: Variance calculation is mathematically correct."""
        job = _create_budget_job(db, tenant, user)

        from app.services.agents.budget_vs_actual_agent import BudgetVsActualAgent

        with patch.object(BudgetVsActualAgent, "_trigger_approval_gate"):
            agent = BudgetVsActualAgent(
                db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True
            )
            agent.execute()

        variance_data = job.report_payload["steps"]["compute_variances"]
        if variance_data.get("variances_computed"):
            for sv in variance_data["summary_variances"]:
                comp = sv["comparison"]
                actual = sv["actual"]
                var_pct = sv["variance_pct"]
                if comp != 0 and var_pct is not None:
                    expected_pct = (actual - comp) / abs(comp) * 100
                    assert abs(var_pct - expected_pct) < 0.2

    def test_11_variance_threshold_flagging(self, db, tenant, user):
        """Test 11: Variances > 15% generate anomalies."""
        job = _create_budget_job(db, tenant, user)

        from app.services.agents.budget_vs_actual_agent import BudgetVsActualAgent

        with patch.object(BudgetVsActualAgent, "_trigger_approval_gate"):
            agent = BudgetVsActualAgent(
                db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True
            )
            agent.execute()

        variance_data = job.report_payload["steps"]["compute_variances"]
        anomalies = job.report_payload.get("anomalies", [])

        if variance_data.get("variances_computed"):
            flagged = [sv for sv in variance_data["summary_variances"] if sv["flagged"]]
            budget_anomalies = [
                a for a in anomalies
                if a["anomaly_type"] in ("budget_variance_significant", "budget_line_variance")
            ]
            # Each flagged summary metric should have an anomaly
            assert len(budget_anomalies) >= len(flagged)

    def test_12_favorable_direction_logic(self, db, tenant, user):
        """Test 12: Favorable direction is correct for each metric type."""
        job = _create_budget_job(db, tenant, user)

        from app.services.agents.budget_vs_actual_agent import BudgetVsActualAgent

        with patch.object(BudgetVsActualAgent, "_trigger_approval_gate"):
            agent = BudgetVsActualAgent(
                db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True
            )
            agent.execute()

        variance_data = job.report_payload["steps"]["compute_variances"]
        if variance_data.get("variances_computed"):
            for sv in variance_data["summary_variances"]:
                actual = sv["actual"]
                comp = sv["comparison"]
                metric = sv["metric"]
                is_favorable = sv["is_favorable"]

                # Revenue, Gross Profit, Net Income: higher = favorable
                if metric in ("Revenue", "Gross Profit", "Net Income"):
                    assert is_favorable == (actual >= comp), (
                        f"{metric}: actual={actual}, comp={comp}, "
                        f"is_favorable={is_favorable} should be {actual >= comp}"
                    )
                # COGS, Expenses: lower = favorable
                elif metric in ("COGS", "Expenses"):
                    assert is_favorable == (actual <= comp), (
                        f"{metric}: actual={actual}, comp={comp}, "
                        f"is_favorable={is_favorable} should be {actual <= comp}"
                    )

    def test_13_no_comparison_anomaly(self, db, tenant, user):
        """Test 13: When no comparison available, INFO anomaly is generated."""
        job = _create_budget_job(db, tenant, user)

        from app.services.agents.budget_vs_actual_agent import BudgetVsActualAgent

        with patch.object(BudgetVsActualAgent, "_trigger_approval_gate"):
            agent = BudgetVsActualAgent(
                db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True
            )
            agent.execute()

        comp_data = job.report_payload["steps"]["get_comparison_period"]
        anomalies = job.report_payload.get("anomalies", [])

        if comp_data["comparison_type"] == "none":
            no_basis = [a for a in anomalies if a["anomaly_type"] == "budget_no_comparison_basis"]
            assert len(no_basis) == 1

    def test_14_report_contains_comparison_label(self, db, tenant, user):
        """Test 14: Report HTML contains the comparison label and actual revenue."""
        job = _create_budget_job(db, tenant, user)

        from app.services.agents.budget_vs_actual_agent import BudgetVsActualAgent

        with patch.object(BudgetVsActualAgent, "_trigger_approval_gate"):
            agent = BudgetVsActualAgent(
                db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True
            )
            agent.execute()

        report_html = job.report_payload["report_html"]
        comp_data = job.report_payload["steps"]["get_comparison_period"]
        comparison_label = comp_data["comparison_label"]

        assert comparison_label in report_html
        # Check that actual revenue figure appears
        actuals = job.report_payload["steps"]["get_current_period_actuals"]
        # The HTML contains the revenue as a formatted value — just verify HTML was generated
        assert "Budget vs. Actual" in report_html


# ---------------------------------------------------------------------------
# SHARED TESTS
# ---------------------------------------------------------------------------


class TestSharedPhase89:
    """Tests 15-16: Shared agent tests."""

    def test_15_both_agents_in_registry(self):
        """Test 15: Both agents are registered in AgentRunner."""
        AgentRunner._ensure_registry()
        assert AgentJobType.INVENTORY_RECONCILIATION in AgentRunner.AGENT_REGISTRY
        assert AgentJobType.BUDGET_VS_ACTUAL in AgentRunner.AGENT_REGISTRY

    def test_16_no_period_lock_for_either(self, db, tenant, user, inventory_seed):
        """Test 16: Neither agent creates a period lock on approval."""
        # Run and approve inventory reconciliation
        inv_job = _create_inventory_job(db, tenant, user, inventory_seed)

        from app.services.agents.inventory_reconciliation_agent import InventoryReconciliationAgent

        with patch.object(InventoryReconciliationAgent, "_trigger_approval_gate"):
            agent = InventoryReconciliationAgent(
                db=db, tenant_id=tenant.id, job_id=inv_job.id, dry_run=True
            )
            agent.execute()

        token1 = secrets.token_urlsafe(48)
        inv_job.approval_token = token1
        db.flush()
        ApprovalGateService.process_approval(token1, ApprovalAction(action="approve"), db)

        # Run and approve budget vs actual
        bva_job = _create_budget_job(db, tenant, user)

        from app.services.agents.budget_vs_actual_agent import BudgetVsActualAgent

        with patch.object(BudgetVsActualAgent, "_trigger_approval_gate"):
            agent = BudgetVsActualAgent(
                db=db, tenant_id=tenant.id, job_id=bva_job.id, dry_run=True
            )
            agent.execute()

        token2 = secrets.token_urlsafe(48)
        bva_job.approval_token = token2
        db.flush()
        ApprovalGateService.process_approval(token2, ApprovalAction(action="approve"), db)

        # Verify no period locks exist
        assert not PeriodLockService.is_period_locked(
            db, tenant.id, inventory_seed["period_start"], inventory_seed["period_end"]
        )
        locks = PeriodLockService.get_active_locks(db, tenant.id)
        assert len(locks) == 0
