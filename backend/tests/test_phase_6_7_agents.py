"""Tests for accounting agents Phases 6 and 7.

Covers: ExpenseCategorizationAgent, EstimatedTaxPrepAgent,
agent registry, approval behavior, write guards.
"""

import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy import create_engine, event, JSON
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base
from app.models.accounting_analysis import TenantGLMapping
from app.models.agent import AgentJob
from app.models.agent_anomaly import AgentAnomaly
from app.models.agent_run_step import AgentRunStep
from app.models.agent_schedule import AgentSchedule
from app.models.company import Company
from app.models.journal_entry import JournalEntry, JournalEntryLine
from app.models.period_lock import PeriodLock
from app.models.role import Role
from app.models.tax import TaxRate, TaxJurisdiction
from app.models.user import User
from app.models.vendor import Vendor
from app.models.vendor_bill import VendorBill
from app.models.vendor_bill_line import VendorBillLine
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
            "vendors",
            "vendor_bills",
            "vendor_bill_lines",
            "tenant_gl_mappings",
            "tax_rates",
            "journal_entries",
            "journal_entry_lines",
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
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


@pytest.fixture
def expense_seed(db: Session, tenant: Company, user: User):
    """Seed data for expense categorization tests.

    Creates:
      - 1 vendor
      - 1 vendor bill with 3 lines:
          line1: null expense_category (uncategorized)
          line2: null expense_category (uncategorized)
          line3: expense_category='bogus_category' (orphaned)
      - 2 TenantGLMapping entries (rent, utilities)
    """
    tid = tenant.id
    today = date.today()
    mid = today - timedelta(days=10)

    vendor = Vendor(
        id=str(uuid.uuid4()),
        company_id=tid,
        name="ACME Supplies",
        is_active=True,
    )
    db.add(vendor)
    db.flush()

    bill = VendorBill(
        id=str(uuid.uuid4()),
        company_id=tid,
        number="BILL-2025-001",
        vendor_id=vendor.id,
        status="approved",
        bill_date=_dt(mid),
        due_date=_dt(mid + timedelta(days=30)),
        subtotal=Decimal("1500.00"),
        tax_amount=Decimal("0.00"),
        total=Decimal("1500.00"),
    )
    db.add(bill)
    db.flush()

    line1 = VendorBillLine(
        id=str(uuid.uuid4()),
        bill_id=bill.id,
        description="Office rent payment",
        amount=Decimal("800.00"),
        expense_category=None,
        sort_order=1,
    )
    line2 = VendorBillLine(
        id=str(uuid.uuid4()),
        bill_id=bill.id,
        description="Electric utility bill",
        amount=Decimal("200.00"),
        expense_category=None,
        sort_order=2,
    )
    line3 = VendorBillLine(
        id=str(uuid.uuid4()),
        bill_id=bill.id,
        description="Concrete mix for vaults",
        amount=Decimal("500.00"),
        expense_category="bogus_category",
        sort_order=3,
    )
    db.add_all([line1, line2, line3])
    db.flush()

    # GL mappings — rent and utilities only
    gl_rent = TenantGLMapping(
        id=str(uuid.uuid4()),
        tenant_id=tid,
        platform_category="rent",
        account_number="6100",
        account_name="Rent Expense",
        is_active=True,
    )
    gl_util = TenantGLMapping(
        id=str(uuid.uuid4()),
        tenant_id=tid,
        platform_category="utilities",
        account_number="6200",
        account_name="Utilities Expense",
        is_active=True,
    )
    db.add_all([gl_rent, gl_util])
    db.flush()

    return {
        "vendor": vendor,
        "bill": bill,
        "line1": line1,
        "line2": line2,
        "line3": line3,
        "gl_rent": gl_rent,
        "gl_util": gl_util,
    }


def _mock_classify(description, **kwargs):
    """Mock Claude classification returning predictable results."""
    desc_lower = description.lower()
    if "rent" in desc_lower:
        return {"category": "rent", "confidence": 0.95, "reasoning": "Monthly rent payment"}
    elif "electric" in desc_lower or "utility" in desc_lower:
        return {"category": "utilities", "confidence": 0.92, "reasoning": "Utility expense"}
    elif "concrete" in desc_lower:
        return {"category": "vault_materials", "confidence": 0.60, "reasoning": "Raw materials for production"}
    return {"category": "other_expense", "confidence": 0.50, "reasoning": "Unknown expense"}


def _create_expense_job(db, tenant, user, dry_run=True):
    """Create an expense categorization agent job."""
    today = date.today()
    job = AgentJob(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        job_type="expense_categorization",
        status="pending",
        period_start=today - timedelta(days=30),
        period_end=today,
        dry_run=dry_run,
        triggered_by=user.id,
        run_log=[],
        created_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.flush()
    return job


def _create_tax_job(db, tenant, user, dry_run=True):
    """Create an estimated tax prep agent job."""
    today = date.today()
    # Use the current quarter as the period
    quarter = (today.month - 1) // 3
    q_start = date(today.year, quarter * 3 + 1, 1)
    if quarter == 3:
        q_end = date(today.year, 12, 31)
    else:
        q_end = date(today.year, (quarter + 1) * 3 + 1, 1) - timedelta(days=1)

    job = AgentJob(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        job_type="estimated_tax_prep",
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
# EXPENSE CATEGORIZATION TESTS
# ---------------------------------------------------------------------------


class TestExpenseCategorizationAgent:
    """Tests 1-6: ExpenseCategorizationAgent."""

    def test_1_full_execution(self, db, tenant, user, expense_seed):
        """Test 1: Full agent execution finds uncategorized + orphaned lines."""
        job = _create_expense_job(db, tenant, user)

        from app.services.agents.expense_categorization_agent import ExpenseCategorizationAgent

        with patch.object(
            ExpenseCategorizationAgent,
            "_classify_single_line",
            side_effect=lambda line_info: _mock_classify(line_info["description"]),
        ), patch.object(
            ExpenseCategorizationAgent,
            "_trigger_approval_gate",
        ):
            agent = ExpenseCategorizationAgent(
                db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True
            )
            result = agent.execute()

        assert result.status == "awaiting_approval"
        assert len(result.run_log) == 4

        find_data = result.report_payload["steps"]["find_uncategorized_expenses"]
        assert find_data["uncategorized_count"] == 2
        assert find_data["orphaned_category_count"] == 1

    def test_2_classification_runs(self, db, tenant, user, expense_seed):
        """Test 2: All lines get classified with proposed_category and confidence."""
        job = _create_expense_job(db, tenant, user)

        from app.services.agents.expense_categorization_agent import ExpenseCategorizationAgent

        with patch.object(
            ExpenseCategorizationAgent,
            "_classify_single_line",
            side_effect=lambda line_info: _mock_classify(line_info["description"]),
        ), patch.object(
            ExpenseCategorizationAgent,
            "_trigger_approval_gate",
        ):
            agent = ExpenseCategorizationAgent(
                db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True
            )
            agent.execute()

        classify_data = job.report_payload["steps"]["classify_expenses"]
        assert classify_data["classified_count"] == 3
        for clf in classify_data["classifications"]:
            assert "proposed_category" in clf
            assert "confidence" in clf
        assert (
            classify_data["needs_review_count"] + classify_data["high_confidence_count"]
            == classify_data["classified_count"]
        )

    def test_3_low_confidence_anomaly(self, db, tenant, user, expense_seed):
        """Test 3: Lines with confidence < 0.85 generate WARNING anomalies."""
        job = _create_expense_job(db, tenant, user)

        from app.services.agents.expense_categorization_agent import ExpenseCategorizationAgent

        with patch.object(
            ExpenseCategorizationAgent,
            "_classify_single_line",
            side_effect=lambda line_info: _mock_classify(line_info["description"]),
        ), patch.object(
            ExpenseCategorizationAgent,
            "_trigger_approval_gate",
        ):
            agent = ExpenseCategorizationAgent(
                db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True
            )
            agent.execute()

        # "concrete" line gets 0.60 confidence in our mock
        anomalies = job.report_payload.get("anomalies", [])
        low_conf = [a for a in anomalies if a["anomaly_type"] == "expense_low_confidence"]
        assert len(low_conf) >= 1

    def test_4_gl_mapping_lookup(self, db, tenant, user, expense_seed):
        """Test 4: GL mapping lookup works — mapped + unmapped counts are correct."""
        job = _create_expense_job(db, tenant, user)

        from app.services.agents.expense_categorization_agent import ExpenseCategorizationAgent

        with patch.object(
            ExpenseCategorizationAgent,
            "_classify_single_line",
            side_effect=lambda line_info: _mock_classify(line_info["description"]),
        ), patch.object(
            ExpenseCategorizationAgent,
            "_trigger_approval_gate",
        ):
            agent = ExpenseCategorizationAgent(
                db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True
            )
            agent.execute()

        gl_data = job.report_payload["steps"]["map_to_gl_accounts"]
        classify_data = job.report_payload["steps"]["classify_expenses"]
        high_conf = classify_data["high_confidence_count"]

        # mapped + unmapped should equal high_confidence_count
        assert gl_data["mapped_count"] + gl_data["unmapped_count"] == high_conf

        # Check for INFO anomaly on any unmapped categories
        if gl_data["unmapped_count"] > 0:
            anomalies = job.report_payload.get("anomalies", [])
            no_gl = [a for a in anomalies if a["anomaly_type"] == "expense_no_gl_mapping"]
            assert len(no_gl) >= 1

    def test_5_dry_run_write_guard(self, db, tenant, user, expense_seed):
        """Test 5: Dry-run approval completes but does NOT update VendorBillLines."""
        job = _create_expense_job(db, tenant, user, dry_run=True)

        from app.services.agents.expense_categorization_agent import ExpenseCategorizationAgent

        with patch.object(
            ExpenseCategorizationAgent,
            "_classify_single_line",
            side_effect=lambda line_info: _mock_classify(line_info["description"]),
        ), patch.object(
            ExpenseCategorizationAgent,
            "_trigger_approval_gate",
        ):
            agent = ExpenseCategorizationAgent(
                db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True
            )
            agent.execute()

        # Approve via token
        token = secrets.token_urlsafe(48)
        job.approval_token = token
        db.flush()

        action = ApprovalAction(action="approve")
        result = ApprovalGateService.process_approval(token, action, db)
        assert result.status == "complete"

        # Verify VendorBillLines NOT updated (dry_run=True)
        line1 = db.query(VendorBillLine).filter(
            VendorBillLine.id == expense_seed["line1"].id
        ).first()
        assert line1.expense_category is None  # Should remain null

    def test_6_live_approval_writes(self, db, tenant, user, expense_seed):
        """Test 6: Live (non-dry-run) approval writes categories to high-confidence lines."""
        job = _create_expense_job(db, tenant, user, dry_run=False)

        from app.services.agents.expense_categorization_agent import ExpenseCategorizationAgent

        with patch.object(
            ExpenseCategorizationAgent,
            "_classify_single_line",
            side_effect=lambda line_info: _mock_classify(line_info["description"]),
        ), patch.object(
            ExpenseCategorizationAgent,
            "_trigger_approval_gate",
        ):
            agent = ExpenseCategorizationAgent(
                db=db, tenant_id=tenant.id, job_id=job.id, dry_run=False
            )
            agent.execute()

        # Approve
        token = secrets.token_urlsafe(48)
        job.approval_token = token
        db.flush()

        action = ApprovalAction(action="approve")
        result = ApprovalGateService.process_approval(token, action, db)
        assert result.status == "complete"

        # line1 ("Office rent") → "rent" at 0.95 confidence → should be updated
        line1 = db.query(VendorBillLine).filter(
            VendorBillLine.id == expense_seed["line1"].id
        ).first()
        assert line1.expense_category == "rent"

        # line2 ("Electric utility") → "utilities" at 0.92 → should be updated
        line2 = db.query(VendorBillLine).filter(
            VendorBillLine.id == expense_seed["line2"].id
        ).first()
        assert line2.expense_category == "utilities"


# ---------------------------------------------------------------------------
# ESTIMATED TAX PREP TESTS
# ---------------------------------------------------------------------------


class TestEstimatedTaxPrepAgent:
    """Tests 7-14: EstimatedTaxPrepAgent."""

    def test_7_full_execution(self, db, tenant, user):
        """Test 7: Full agent execution completes all 5 steps."""
        job = _create_tax_job(db, tenant, user)

        from app.services.agents.estimated_tax_prep_agent import EstimatedTaxPrepAgent

        with patch.object(
            EstimatedTaxPrepAgent,
            "_trigger_approval_gate",
        ):
            agent = EstimatedTaxPrepAgent(
                db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True
            )
            result = agent.execute()

        assert result.status == "awaiting_approval"
        assert len(result.run_log) == 5

    def test_8_income_statement_integration(self, db, tenant, user):
        """Test 8: Income statement returns Decimal values with YTD >= period."""
        job = _create_tax_job(db, tenant, user)

        from app.services.agents.estimated_tax_prep_agent import EstimatedTaxPrepAgent

        with patch.object(
            EstimatedTaxPrepAgent,
            "_trigger_approval_gate",
        ):
            agent = EstimatedTaxPrepAgent(
                db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True
            )
            agent.execute()

        income_data = job.report_payload["steps"]["compute_income_statement"]
        assert isinstance(income_data["period_net_income"], (int, float))
        assert isinstance(income_data["ytd_net_income"], (int, float))
        # YTD should be >= period (since period is subset of YTD)
        assert income_data["ytd_net_income"] >= income_data["period_net_income"]

    def test_9_annualization_math(self, db, tenant, user):
        """Test 9: Annualization formula is correct."""
        job = _create_tax_job(db, tenant, user)

        from app.services.agents.estimated_tax_prep_agent import EstimatedTaxPrepAgent

        with patch.object(
            EstimatedTaxPrepAgent,
            "_trigger_approval_gate",
        ):
            agent = EstimatedTaxPrepAgent(
                db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True
            )
            agent.execute()

        annualize = job.report_payload["steps"]["annualize_income"]
        quarters = annualize["quarters_elapsed"]
        ytd = Decimal(str(annualize["ytd_net_income"]))
        annualized = Decimal(str(annualize["annualized_net_income"]))

        if quarters > 0:
            expected = (ytd / quarters * 4).quantize(Decimal("0.01"))
            assert abs(annualized - expected) < Decimal("0.02")

    def test_10_quarterly_estimate_range(self, db, tenant, user):
        """Test 10: Federal quarterly estimates form a valid range."""
        job = _create_tax_job(db, tenant, user)

        from app.services.agents.estimated_tax_prep_agent import EstimatedTaxPrepAgent

        with patch.object(
            EstimatedTaxPrepAgent,
            "_trigger_approval_gate",
        ):
            agent = EstimatedTaxPrepAgent(
                db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True
            )
            agent.execute()

        tax_data = job.report_payload["steps"]["compute_tax_liability"]
        # With no income data (empty DB), these will be 0
        assert tax_data["federal_quarterly_low"] >= 0
        assert tax_data["federal_quarterly_high"] >= tax_data["federal_quarterly_low"]
        assert tax_data["total_quarterly_low"] >= tax_data["federal_quarterly_low"]

    def test_11_next_due_date(self, db, tenant, user):
        """Test 11: Next due date is a valid date within 365 days of today."""
        job = _create_tax_job(db, tenant, user)

        from app.services.agents.estimated_tax_prep_agent import EstimatedTaxPrepAgent

        with patch.object(
            EstimatedTaxPrepAgent,
            "_trigger_approval_gate",
        ):
            agent = EstimatedTaxPrepAgent(
                db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True
            )
            agent.execute()

        tax_data = job.report_payload["steps"]["compute_tax_liability"]
        next_due = date.fromisoformat(tax_data["next_due_date"])
        today = date.today()
        assert abs((next_due - today).days) <= 365

    def test_12_no_tax_rates_anomaly(self, db, tenant, user):
        """Test 12: Missing tax rates generates WARNING anomaly."""
        job = _create_tax_job(db, tenant, user)

        from app.services.agents.estimated_tax_prep_agent import EstimatedTaxPrepAgent

        with patch.object(
            EstimatedTaxPrepAgent,
            "_trigger_approval_gate",
        ):
            agent = EstimatedTaxPrepAgent(
                db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True
            )
            agent.execute()

        # No TaxRate seeded → should have WARNING anomaly
        anomalies = job.report_payload.get("anomalies", [])
        no_rates = [a for a in anomalies if a["anomaly_type"] == "no_tax_rates_configured"]
        assert len(no_rates) == 1

    def test_13_disclaimer_in_report(self, db, tenant, user):
        """Test 13: Report HTML contains tax disclaimer."""
        job = _create_tax_job(db, tenant, user)

        from app.services.agents.estimated_tax_prep_agent import EstimatedTaxPrepAgent

        with patch.object(
            EstimatedTaxPrepAgent,
            "_trigger_approval_gate",
        ):
            agent = EstimatedTaxPrepAgent(
                db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True
            )
            agent.execute()

        report_html = job.report_payload["report_html"]
        assert "estimate" in report_html.lower()
        assert "cpa" in report_html.lower() or "tax advice" in report_html.lower()

    def test_14_approval_no_writes(self, db, tenant, user):
        """Test 14: Approval completes without creating any financial records."""
        job = _create_tax_job(db, tenant, user)

        from app.services.agents.estimated_tax_prep_agent import EstimatedTaxPrepAgent

        with patch.object(
            EstimatedTaxPrepAgent,
            "_trigger_approval_gate",
        ):
            agent = EstimatedTaxPrepAgent(
                db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True
            )
            agent.execute()

        token = secrets.token_urlsafe(48)
        job.approval_token = token
        db.flush()

        action = ApprovalAction(action="approve")
        result = ApprovalGateService.process_approval(token, action, db)
        assert result.status == "complete"

        # No VendorBill created
        bills = db.query(VendorBill).filter(VendorBill.company_id == tenant.id).all()
        assert len(bills) == 0

        # No JournalEntry created
        entries = db.query(JournalEntry).filter(JournalEntry.tenant_id == tenant.id).all()
        assert len(entries) == 0

        # No period lock
        locks = PeriodLockService.get_active_locks(db, tenant.id)
        assert len(locks) == 0


# ---------------------------------------------------------------------------
# SHARED TESTS
# ---------------------------------------------------------------------------


class TestSharedPhase67:
    """Tests 15-16: Shared agent tests."""

    def test_15_both_agents_in_registry(self):
        """Test 15: Both agents are registered in AgentRunner."""
        AgentRunner._ensure_registry()
        assert AgentJobType.EXPENSE_CATEGORIZATION in AgentRunner.AGENT_REGISTRY
        assert AgentJobType.ESTIMATED_TAX_PREP in AgentRunner.AGENT_REGISTRY

    def test_16_expense_approval_writes_only_high_confidence(
        self, db, tenant, user, expense_seed
    ):
        """Test 16: Approval writes ONLY high-confidence lines, not low-confidence."""
        job = _create_expense_job(db, tenant, user, dry_run=False)

        from app.services.agents.expense_categorization_agent import ExpenseCategorizationAgent

        # Mock: line1 (rent) → high confidence, line2 (utility) → high, line3 (concrete) → low
        with patch.object(
            ExpenseCategorizationAgent,
            "_classify_single_line",
            side_effect=lambda line_info: _mock_classify(line_info["description"]),
        ), patch.object(
            ExpenseCategorizationAgent,
            "_trigger_approval_gate",
        ):
            agent = ExpenseCategorizationAgent(
                db=db, tenant_id=tenant.id, job_id=job.id, dry_run=False
            )
            agent.execute()

        token = secrets.token_urlsafe(48)
        job.approval_token = token
        db.flush()

        action = ApprovalAction(action="approve")
        ApprovalGateService.process_approval(token, action, db)

        # High confidence lines should be updated
        line1 = db.query(VendorBillLine).filter(
            VendorBillLine.id == expense_seed["line1"].id
        ).first()
        assert line1.expense_category == "rent"

        # Low confidence line should NOT be updated (still orphaned)
        line3 = db.query(VendorBillLine).filter(
            VendorBillLine.id == expense_seed["line3"].id
        ).first()
        # line3 had "bogus_category" — it was classified at 0.60 (below threshold)
        # so it should NOT be overwritten
        assert line3.expense_category == "bogus_category"
