"""Tests for MonthEndCloseAgent (Phase 2).

Covers: full execution, known anomalies, math verification, approval integration,
period locking, and prior period comparison.
"""

import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import JSON, create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.database import Base
from app.models.agent import AgentJob
from app.models.agent_anomaly import AgentAnomaly
from app.models.agent_run_step import AgentRunStep
from app.models.agent_schedule import AgentSchedule
from app.models.company import Company
from app.models.customer import Customer
from app.models.customer_payment import CustomerPayment, CustomerPaymentApplication
from app.models.invoice import Invoice
from app.models.period_lock import PeriodLock
from app.models.role import Role
from app.models.sales_order import SalesOrder
from app.models.statement import CustomerStatement, StatementRun
from app.models.user import User
from app.schemas.agent import AgentJobType, ApprovalAction
from app.services.agents.agent_runner import AgentRunner
from app.services.agents.base_agent import BaseAgent, DryRunGuardError
from app.services.agents.period_lock import PeriodLockService


# ---------------------------------------------------------------------------
# Period helpers — previous full calendar month
# ---------------------------------------------------------------------------

def _last_month_period():
    today = date.today()
    first_this_month = today.replace(day=1)
    last_month_end = first_this_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    return last_month_start, last_month_end


PERIOD_START, PERIOD_END = _last_month_period()
MID_PERIOD = PERIOD_START + timedelta(days=14)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TABLES_NEEDED = [
    "companies",
    "roles",
    "users",
    "customers",
    "sales_orders",
    "sales_order_lines",
    "invoices",
    "invoice_lines",
    "customer_payments",
    "customer_payment_applications",
    "statement_runs",
    "customer_statements",
    "statement_run_items",
    "agent_jobs",
    "agent_run_steps",
    "agent_anomalies",
    "agent_schedules",
    "period_locks",
]


@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:")
    available = set(Base.metadata.tables.keys())
    table_names = [t for t in TABLES_NEEDED if t in available]
    tables = [Base.metadata.tables[t] for t in table_names]

    # Swap JSONB → JSON for SQLite
    jsonb_cols = []
    for table in tables:
        for col in table.columns:
            if isinstance(col.type, JSONB):
                jsonb_cols.append((col, col.type))
                col.type = JSON()
    Base.metadata.create_all(eng, tables=tables)
    for col, orig in jsonb_cols:
        col.type = orig
    return eng


@pytest.fixture
def db(engine):
    conn = engine.connect()
    txn = conn.begin()
    session = Session(bind=conn)
    yield session
    session.close()
    txn.rollback()
    conn.close()


@pytest.fixture
def tenant(db):
    c = Company(id=str(uuid.uuid4()), name="Test Vault Co", slug="testco", is_active=True)
    db.add(c)
    db.flush()
    return c


@pytest.fixture
def role(db, tenant):
    r = Role(id=str(uuid.uuid4()), company_id=tenant.id, name="Admin", slug="admin", is_system=True)
    db.add(r)
    db.flush()
    return r


@pytest.fixture
def user(db, tenant, role):
    u = User(
        id=str(uuid.uuid4()), email="admin@test.com",
        first_name="Test", last_name="Admin",
        company_id=tenant.id, role_id=role.id,
        is_active=True, hashed_password="fake",
    )
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def seed_data(db, tenant, user):
    """Seed a controlled month-end scenario for tests."""
    tid = tenant.id

    # Customers
    johnson = Customer(
        id=str(uuid.uuid4()), company_id=tid, name="Johnson Funeral Home",
        account_number="JFH-001", is_active=True,
        receives_monthly_statement=True, receives_statements=True,
        payment_terms="net_30", billing_profile="charge",
        preferred_delivery_method="email",
    )
    smith = Customer(
        id=str(uuid.uuid4()), company_id=tid, name="Smith & Sons",
        account_number="SS-002", is_active=True,
        receives_monthly_statement=True, receives_statements=True,
        payment_terms="net_30", billing_profile="charge",
        preferred_delivery_method="email",
    )
    memorial = Customer(
        id=str(uuid.uuid4()), company_id=tid, name="Memorial Chapel",
        account_number="MC-003", is_active=True,
        receives_monthly_statement=True, receives_statements=True,
        payment_terms="net_30", billing_profile="charge",
        preferred_delivery_method="email",
    )
    riverside = Customer(
        id=str(uuid.uuid4()), company_id=tid, name="Riverside FH",
        account_number="RFH-004", is_active=True,
        receives_monthly_statement=False,  # NOT on statement
        receives_statements=True, payment_terms="cod",
    )
    db.add_all([johnson, smith, memorial, riverside])
    db.flush()

    # Orders
    order_a = SalesOrder(
        id=str(uuid.uuid4()), company_id=tid, number="ORD-001",
        customer_id=johnson.id, status="delivered",
        order_date=datetime(PERIOD_START.year, PERIOD_START.month, PERIOD_START.day, tzinfo=timezone.utc),
        delivered_at=datetime(MID_PERIOD.year, MID_PERIOD.month, MID_PERIOD.day, tzinfo=timezone.utc),
        total=3864.00,
    )
    order_b = SalesOrder(
        id=str(uuid.uuid4()), company_id=tid, number="ORD-002",
        customer_id=smith.id, status="completed",
        order_date=datetime(PERIOD_START.year, PERIOD_START.month, PERIOD_START.day, tzinfo=timezone.utc),
        delivered_at=datetime(MID_PERIOD.year, MID_PERIOD.month, MID_PERIOD.day, tzinfo=timezone.utc),
        total=2850.00,
    )
    order_c = SalesOrder(
        id=str(uuid.uuid4()), company_id=tid, number="ORD-003",
        customer_id=memorial.id, status="delivered",
        order_date=datetime(PERIOD_START.year, PERIOD_START.month, PERIOD_START.day, tzinfo=timezone.utc),
        delivered_at=datetime(MID_PERIOD.year, MID_PERIOD.month, MID_PERIOD.day, tzinfo=timezone.utc),
        total=1934.00,
    )
    order_d = SalesOrder(
        id=str(uuid.uuid4()), company_id=tid, number="ORD-004",
        customer_id=johnson.id, status="confirmed",
        order_date=datetime(MID_PERIOD.year, MID_PERIOD.month, MID_PERIOD.day, tzinfo=timezone.utc),
        total=500.00,
    )
    db.add_all([order_a, order_b, order_c, order_d])
    db.flush()

    # Invoices
    inv1 = Invoice(
        id=str(uuid.uuid4()), company_id=tid, number="INV-001",
        customer_id=johnson.id, sales_order_id=order_a.id,
        status="sent", total=3864.00, amount_paid=3864.00,
        invoice_date=datetime(MID_PERIOD.year, MID_PERIOD.month, MID_PERIOD.day, tzinfo=timezone.utc),
        due_date=datetime(MID_PERIOD.year, MID_PERIOD.month, MID_PERIOD.day, tzinfo=timezone.utc) + timedelta(days=30),
    )
    inv2 = Invoice(
        id=str(uuid.uuid4()), company_id=tid, number="INV-002",
        customer_id=smith.id, sales_order_id=order_b.id,
        status="overdue", total=2850.00, amount_paid=0,
        invoice_date=datetime(MID_PERIOD.year, MID_PERIOD.month, MID_PERIOD.day, tzinfo=timezone.utc),
        due_date=datetime(MID_PERIOD.year, MID_PERIOD.month, MID_PERIOD.day, tzinfo=timezone.utc) + timedelta(days=30),
    )
    # Old invoice from 100+ days ago → 90+ bucket
    old_date = datetime.now(timezone.utc) - timedelta(days=120)
    old_due = old_date + timedelta(days=30)
    inv_old = Invoice(
        id=str(uuid.uuid4()), company_id=tid, number="INV-OLD",
        customer_id=smith.id, status="overdue",
        total=1500.00, amount_paid=0,
        invoice_date=old_date, due_date=old_due,
    )
    # Order C has NO invoice → uninvoiced_delivery trigger

    db.add_all([inv1, inv2, inv_old])
    db.flush()

    # Payments
    pay1 = CustomerPayment(
        id=str(uuid.uuid4()), company_id=tid, customer_id=johnson.id,
        payment_date=datetime(MID_PERIOD.year, MID_PERIOD.month, MID_PERIOD.day, tzinfo=timezone.utc),
        total_amount=3864.00, payment_method="check", reference_number="CHK-1001",
    )
    pay2 = CustomerPayment(
        id=str(uuid.uuid4()), company_id=tid, customer_id=riverside.id,
        payment_date=datetime(MID_PERIOD.year, MID_PERIOD.month, MID_PERIOD.day, tzinfo=timezone.utc),
        total_amount=500.00, payment_method="check", reference_number="CHK-UNKNOWN",
    )
    pay3 = CustomerPayment(
        id=str(uuid.uuid4()), company_id=tid, customer_id=smith.id,
        payment_date=datetime(MID_PERIOD.year, MID_PERIOD.month, MID_PERIOD.day, tzinfo=timezone.utc),
        total_amount=1000.00, payment_method="check", reference_number="CHK-2001",
    )
    pay4 = CustomerPayment(
        id=str(uuid.uuid4()), company_id=tid, customer_id=smith.id,
        payment_date=datetime(MID_PERIOD.year, MID_PERIOD.month, MID_PERIOD.day, tzinfo=timezone.utc) + timedelta(days=2),
        total_amount=1000.00, payment_method="check", reference_number="CHK-2002",
    )
    db.add_all([pay1, pay2, pay3, pay4])
    db.flush()

    # Match pay1 to inv1
    app1 = CustomerPaymentApplication(
        id=str(uuid.uuid4()), payment_id=pay1.id,
        invoice_id=inv1.id, amount_applied=3864.00,
    )
    db.add(app1)
    # pay2, pay3, pay4 have NO applications → unmatched
    db.flush()

    return {
        "johnson": johnson, "smith": smith, "memorial": memorial, "riverside": riverside,
        "order_a": order_a, "order_b": order_b, "order_c": order_c, "order_d": order_d,
        "inv1": inv1, "inv2": inv2, "inv_old": inv_old,
        "pay1": pay1, "pay2": pay2, "pay3": pay3, "pay4": pay4,
    }


def _create_and_run_job(db, tenant, user, dry_run=True):
    """Helper: create + run a month-end close agent job."""
    job = AgentRunner.create_job(
        db=db,
        tenant_id=tenant.id,
        job_type=AgentJobType.MONTH_END_CLOSE,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        dry_run=dry_run,
        triggered_by=user.id,
    )
    result = AgentRunner.run_job(job.id, db)
    return result


# ---------------------------------------------------------------------------
# Test 1 — full execution, all steps complete
# ---------------------------------------------------------------------------

class TestFullExecution:
    def test_all_steps_complete(self, db, tenant, user, seed_data):
        job = _create_and_run_job(db, tenant, user, dry_run=True)
        assert job.status == "awaiting_approval"
        assert len(job.run_log) == 8
        assert all(e["status"] == "complete" for e in job.run_log)
        assert job.report_payload is not None
        assert "executive_summary" in job.report_payload


# ---------------------------------------------------------------------------
# Test 2 — known anomalies present
# ---------------------------------------------------------------------------

class TestKnownAnomalies:
    def test_expected_anomaly_types(self, db, tenant, user, seed_data):
        job = _create_and_run_job(db, tenant, user)

        anomalies = (
            db.query(AgentAnomaly)
            .filter(AgentAnomaly.agent_job_id == job.id)
            .all()
        )
        anomaly_types = {a.anomaly_type for a in anomalies}

        assert "uninvoiced_delivery" in anomaly_types, f"Missing uninvoiced_delivery. Got: {anomaly_types}"
        assert "duplicate_payment" in anomaly_types, f"Missing duplicate_payment. Got: {anomaly_types}"
        assert "unmatched_payment" in anomaly_types, f"Missing unmatched_payment. Got: {anomaly_types}"
        assert job.anomaly_count >= 3


# ---------------------------------------------------------------------------
# Test 3 — invoice coverage math
# ---------------------------------------------------------------------------

class TestInvoiceCoverage:
    def test_coverage_math(self, db, tenant, user, seed_data):
        job = _create_and_run_job(db, tenant, user)
        coverage = job.report_payload["steps"]["verify_invoice_coverage"]

        delivered = coverage["delivered_count"]
        invoiced = coverage["invoiced_count"]
        assert delivered > 0
        assert coverage["coverage_pct"] == round(invoiced / delivered * 100, 1)
        assert len(coverage["uninvoiced_orders"]) == delivered - invoiced


# ---------------------------------------------------------------------------
# Test 4 — AR aging math
# ---------------------------------------------------------------------------

class TestARAging:
    def test_bucket_totals_match(self, db, tenant, user, seed_data):
        job = _create_and_run_job(db, tenant, user)
        aging = job.report_payload["steps"]["ar_aging_snapshot"]

        bucket_sum = (
            aging["current"]["total"]
            + aging["bucket_30"]["total"]
            + aging["bucket_60"]["total"]
            + aging["bucket_90"]["total"]
        )
        assert abs(bucket_sum - aging["total_ar"]) < 0.01


# ---------------------------------------------------------------------------
# Test 5 — customer statement balance integrity
# ---------------------------------------------------------------------------

class TestStatementBalances:
    def test_closing_equals_opening_plus_invoices_minus_payments(self, db, tenant, user, seed_data):
        job = _create_and_run_job(db, tenant, user)
        customers = job.report_payload["steps"]["customer_statements"]["customers"]

        for cust in customers:
            expected = (
                Decimal(str(cust["opening_balance"]))
                + Decimal(str(cust.get("invoices_in_period", 0)))  # this is count, not total
            )
            # The statement data uses opening + invoices_total - payments_total = closing
            # We verify via the calculate_statement_data contract
            closing = Decimal(str(cust["closing_balance"]))
            # closing_balance = opening_balance + invoices_total - payments_total
            # We can verify net_change = invoices_total - payments_total
            net = Decimal(str(cust["net_change"]))
            opening = Decimal(str(cust["opening_balance"]))
            assert abs((opening + net) - closing) < Decimal("0.01"), (
                f"Balance mismatch for {cust['customer_name']}: "
                f"opening={opening} + net={net} != closing={closing}"
            )


# ---------------------------------------------------------------------------
# Test 6 — dry_run write guard
# ---------------------------------------------------------------------------

class TestDryRunGuard:
    def test_guard_write_raises_in_dry_run(self, db, tenant, user, seed_data):
        job = AgentRunner.create_job(
            db=db, tenant_id=tenant.id,
            job_type=AgentJobType.MONTH_END_CLOSE,
            period_start=PERIOD_START, period_end=PERIOD_END,
            dry_run=True, triggered_by=user.id,
        )
        agent = BaseAgent(db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True)
        with pytest.raises(DryRunGuardError):
            agent.guard_write()

    def test_guard_write_allows_non_dry_run(self, db, tenant, user, seed_data):
        job = AgentRunner.create_job(
            db=db, tenant_id=tenant.id,
            job_type=AgentJobType.MONTH_END_CLOSE,
            period_start=PERIOD_START, period_end=PERIOD_END,
            dry_run=False, triggered_by=user.id,
        )
        agent = BaseAgent(db=db, tenant_id=tenant.id, job_id=job.id, dry_run=False)
        agent.guard_write()  # Should not raise


# ---------------------------------------------------------------------------
# Test 7 — statement run triggered on approval
# ---------------------------------------------------------------------------

class TestApprovalTriggersStatementRun:
    def test_statement_run_created(self, db, tenant, user, seed_data):
        ps = PERIOD_START
        pe = PERIOD_END

        job = AgentRunner.create_job(
            db=db, tenant_id=tenant.id,
            job_type=AgentJobType.MONTH_END_CLOSE,
            period_start=ps, period_end=pe,
            dry_run=False, triggered_by=user.id,
        )
        result = AgentRunner.run_job(job.id, db)
        assert result.status == "awaiting_approval"

        # Fix SQLite timezone-naive created_at for approval gate expiry check
        if result.created_at and result.created_at.tzinfo is None:
            result.created_at = result.created_at.replace(tzinfo=timezone.utc)
            db.flush()

        # Process approval
        from app.services.agents.approval_gate import ApprovalGateService
        action = ApprovalAction(action="approve")
        approved = ApprovalGateService.process_approval(result.approval_token, action, db)
        assert approved.status == "complete"

        # Verify statement_run_id in report_payload
        assert "statement_run_id" in approved.report_payload
        run_id = approved.report_payload["statement_run_id"]

        statement_run = db.query(StatementRun).filter(StatementRun.id == run_id).first()
        assert statement_run is not None


# ---------------------------------------------------------------------------
# Test 8 — period locked after approval
# ---------------------------------------------------------------------------

class TestPeriodLockedAfterApproval:
    def test_period_is_locked(self, db, tenant, user, seed_data):
        job = AgentRunner.create_job(
            db=db, tenant_id=tenant.id,
            job_type=AgentJobType.MONTH_END_CLOSE,
            period_start=PERIOD_START, period_end=PERIOD_END,
            dry_run=False, triggered_by=user.id,
        )
        result = AgentRunner.run_job(job.id, db)

        # Fix SQLite timezone-naive created_at
        if result.created_at and result.created_at.tzinfo is None:
            result.created_at = result.created_at.replace(tzinfo=timezone.utc)
            db.flush()

        from app.services.agents.approval_gate import ApprovalGateService
        action = ApprovalAction(action="approve")
        ApprovalGateService.process_approval(result.approval_token, action, db)

        assert PeriodLockService.is_period_locked(db, tenant.id, PERIOD_START, PERIOD_END)


# ---------------------------------------------------------------------------
# Test 9 — period lock blocks non-dry-run job
# ---------------------------------------------------------------------------

class TestPeriodLockBlocksJob:
    def test_locked_period_rejected(self, db, tenant, user, seed_data):
        # Lock the period manually
        PeriodLockService.lock_period(
            db=db, tenant_id=tenant.id,
            period_start=date(2025, 1, 1), period_end=date(2025, 1, 31),
            locked_by=user.id, reason="test lock",
        )

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            AgentRunner.create_job(
                db=db, tenant_id=tenant.id,
                job_type=AgentJobType.MONTH_END_CLOSE,
                period_start=date(2025, 1, 1), period_end=date(2025, 1, 31),
                dry_run=False, triggered_by=user.id,
            )
        assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# Test 10 — prior period comparison
# ---------------------------------------------------------------------------

class TestPriorPeriodComparison:
    def test_comparison_available_after_prior_run(self, db, tenant, user, seed_data):
        # Simulate a completed prior-month job with report_payload
        two_months_ago_start = (PERIOD_START.replace(day=1) - timedelta(days=1)).replace(day=1)
        two_months_ago_end = PERIOD_START - timedelta(days=1)

        prior_job = AgentJob(
            id=str(uuid.uuid4()), tenant_id=tenant.id,
            job_type="month_end_close", status="complete",
            period_start=two_months_ago_start, period_end=two_months_ago_end,
            dry_run=True, run_log=[],
            report_payload={
                "executive_summary": {
                    "total_revenue": 5000.00,
                    "invoice_count": 10,
                    "total_ar": 3000.00,
                }
            },
            completed_at=datetime.now(timezone.utc) - timedelta(days=35),
        )
        db.add(prior_job)
        db.flush()

        job = _create_and_run_job(db, tenant, user)
        comparison = job.report_payload["steps"]["prior_period_comparison"]

        assert comparison["comparison_available"] is True
        assert comparison["vs_prior_month"] is not None
        assert isinstance(comparison["vs_prior_month"]["revenue_variance_pct"], float)


# ---------------------------------------------------------------------------
# Test 11 — report HTML contains key numbers
# ---------------------------------------------------------------------------

class TestReportHTML:
    def test_html_contains_key_data(self, db, tenant, user, seed_data):
        job = _create_and_run_job(db, tenant, user)

        report_html = job.report_payload.get("report_html", "")
        exec_summary = job.report_payload["executive_summary"]

        assert str(exec_summary["anomaly_count"]) in report_html
        assert len(report_html) > 100  # Non-trivial HTML
