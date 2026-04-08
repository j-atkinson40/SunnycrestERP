"""Tests for Phases 11 & 12 accounting agents.

Phase 11 — YearEndCloseAgent (9 tests)
Phase 12 — TaxPackageAgent (7 tests)
Shared  — 3 tests (registry completion, approval paths, all-registered)
Total   — 19 tests
"""

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
from app.models.journal_entry import JournalEntry, JournalEntryLine
from app.models.period_lock import PeriodLock
from app.models.product import Product
from app.models.role import Role
from app.models.user import User
from app.schemas.agent import (
    AgentJobType,
    AnomalySeverity,
    StepResult,
)
from app.services.agents.year_end_close_agent import (
    BUDGET_VARIANCE_THRESHOLD,
    YearEndCloseAgent,
)
from app.services.agents.tax_package_agent import (
    REQUIRED_AGENTS,
    RECOMMENDED_AGENTS,
    REQUIRED_WEIGHT,
    RECOMMENDED_WEIGHT,
    SCHEDULE_LABELS,
    TaxPackageAgent,
)


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
            "agent_jobs",
            "agent_run_steps",
            "agent_anomalies",
            "agent_schedules",
            "period_locks",
            "products",
            "inventory_items",
            "journal_entries",
            "journal_entry_lines",
        ]
    ]
    # Swap JSONB -> JSON for SQLite compatibility
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


def _make_job(
    db: Session,
    tenant: Company,
    user: User,
    job_type: str,
    period_start: date,
    period_end: date,
    dry_run: bool = True,
    report_payload: dict | None = None,
    status: str = "pending",
) -> AgentJob:
    job = AgentJob(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        job_type=job_type,
        status=status,
        period_start=period_start,
        period_end=period_end,
        dry_run=dry_run,
        triggered_by=user.id,
        run_log=[],
        report_payload=report_payload,
    )
    db.add(job)
    db.flush()
    return job


def _mock_income_statement(total_revenue=100000, total_cogs=40000, total_expenses=30000):
    gross = total_revenue - total_cogs
    net = gross - total_expenses
    return {
        "total_revenue": total_revenue,
        "total_cogs": total_cogs,
        "gross_profit": gross,
        "gross_margin_percent": round(gross / total_revenue * 100, 1) if total_revenue else 0,
        "total_expenses": total_expenses,
        "net_income": net,
        "revenue": [{"account_number": "4000", "account_name": "Sales Revenue", "amount": total_revenue}],
        "cogs": [{"account_number": "5000", "account_name": "COGS", "amount": total_cogs}],
        "expenses": [{"account_number": "6000", "account_name": "Operating Expenses", "amount": total_expenses}],
    }


# ---------------------------------------------------------------------------
# Phase 11 — YearEndCloseAgent tests (9 tests)
# ---------------------------------------------------------------------------


class TestYearEndCloseAgent:
    """Tests for the Year-End Close Agent (Phase 11)."""

    def test_steps_inherit_plus_five(self):
        """YearEndCloseAgent.STEPS = 8 inherited + 5 new = 13 total."""
        from app.services.agents.month_end_close_agent import MonthEndCloseAgent
        assert len(YearEndCloseAgent.STEPS) == 13
        # First 8 are inherited
        assert YearEndCloseAgent.STEPS[:8] == MonthEndCloseAgent.STEPS
        # Last 5 are year-end steps
        assert YearEndCloseAgent.STEPS[8:] == [
            "full_year_summary",
            "depreciation_review",
            "accruals_review",
            "inventory_valuation",
            "retained_earnings_summary",
        ]

    def test_non_december_period_fails(self, db, tenant, user):
        """execute() fails if period is not Dec 1-31."""
        job = _make_job(db, tenant, user, "year_end_close",
                        date(2025, 11, 1), date(2025, 11, 30))
        agent = YearEndCloseAgent(
            db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True,
        )
        result = agent.execute()
        assert result.status == "failed"
        assert "Dec 1" in result.error_message

    @patch("app.services.financial_report_service.get_income_statement")
    def test_step9_full_year_summary(self, mock_income, db, tenant, user):
        """Step 9 returns annual income statement + quarterly breakdown."""
        annual = _mock_income_statement(200000, 80000, 60000)

        def side_effect(db_, tenant_id_, start, end):
            return annual

        mock_income.side_effect = side_effect

        job = _make_job(db, tenant, user, "year_end_close",
                        date(2025, 12, 1), date(2025, 12, 31))
        agent = YearEndCloseAgent(
            db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True,
        )
        agent.job = job
        result = agent._step_full_year_summary()

        assert result.data["year"] == 2025
        assert result.data["annual_income_statement"]["total_revenue"] == 200000.0
        assert result.data["annual_income_statement"]["net_income"] == 60000.0
        assert "q1" in result.data["quarterly_breakdown"]
        assert "q4" in result.data["quarterly_breakdown"]

    @patch("app.services.financial_report_service.get_income_statement")
    def test_step9_budget_variance_anomaly(self, mock_income, db, tenant, user):
        """Step 9 flags WARNING when actual vs budget variance exceeds 15%."""
        annual = _mock_income_statement(200000, 80000, 60000)
        mock_income.return_value = annual

        # Create a completed annual_budget job with budget data
        budget_payload = {
            "budget": {
                "annual": {
                    "revenue": 150000,  # actual 200k vs budget 150k = +33%
                    "cogs": 80000,
                    "gross_profit": 70000,
                    "expenses": 60000,
                    "net_income": 10000,
                },
            },
        }
        budget_job = _make_job(
            db, tenant, user, "annual_budget",
            date(2025, 1, 1), date(2025, 12, 31),
            status="complete",
            report_payload=budget_payload,
        )
        budget_job.completed_at = datetime.now(timezone.utc)
        db.flush()

        job = _make_job(db, tenant, user, "year_end_close",
                        date(2025, 12, 1), date(2025, 12, 31))
        agent = YearEndCloseAgent(
            db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True,
        )
        agent.job = job
        result = agent._step_full_year_summary()

        budget_warnings = [
            a for a in result.anomalies
            if a.anomaly_type == "yearend_budget_variance"
        ]
        assert len(budget_warnings) > 0
        assert budget_warnings[0].severity == AnomalySeverity.WARNING

    def test_step10_no_depreciation_anomaly(self, db, tenant, user):
        """Step 10 flags WARNING when no depreciation entries exist."""
        job = _make_job(db, tenant, user, "year_end_close",
                        date(2025, 12, 1), date(2025, 12, 31))
        agent = YearEndCloseAgent(
            db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True,
        )
        agent.job = job
        result = agent._step_depreciation_review()

        assert result.data["total_depreciation_posted"] == 0.0
        assert result.data["review_needed"] is True
        warnings = [a for a in result.anomalies if a.anomaly_type == "yearend_no_depreciation"]
        assert len(warnings) == 1
        assert warnings[0].severity == AnomalySeverity.WARNING

    def test_step11_no_accruals_anomaly(self, db, tenant, user):
        """Step 11 flags INFO when no accrual entries found in December."""
        job = _make_job(db, tenant, user, "year_end_close",
                        date(2025, 12, 1), date(2025, 12, 31))
        agent = YearEndCloseAgent(
            db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True,
        )
        agent.job = job
        result = agent._step_accruals_review()

        assert result.data["accrual_entries_found"] == 0
        info_anomalies = [a for a in result.anomalies if a.anomaly_type == "yearend_no_accruals"]
        assert len(info_anomalies) == 1
        assert info_anomalies[0].severity == AnomalySeverity.INFO

    def test_step12_inventory_no_cost_anomaly(self, db, tenant, user):
        """Step 12 flags WARNING per product with units on hand but no cost_price."""
        # Create a product without cost_price
        product = Product(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            name="Test Vault",
            sku="TV-001",
            is_inventory_tracked=True,
            cost_price=None,
        )
        db.add(product)
        db.flush()

        inv_item = InventoryItem(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            product_id=product.id,
            quantity_on_hand=10,
        )
        db.add(inv_item)
        db.flush()

        job = _make_job(db, tenant, user, "year_end_close",
                        date(2025, 12, 1), date(2025, 12, 31))
        agent = YearEndCloseAgent(
            db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True,
        )
        agent.job = job
        result = agent._step_inventory_valuation()

        assert result.data["products_no_cost"] >= 1
        no_cost = [a for a in result.anomalies if a.anomaly_type == "yearend_inventory_no_cost"]
        assert len(no_cost) >= 1
        assert no_cost[0].severity == AnomalySeverity.WARNING

    def test_step12_inventory_value_computed(self, db, tenant, user):
        """Step 12 computes correct total_inventory_value when cost is available."""
        product = Product(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            name="Premium Vault",
            sku="PV-001",
            is_inventory_tracked=True,
            cost_price=Decimal("250.00"),
        )
        db.add(product)
        db.flush()

        inv_item = InventoryItem(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            product_id=product.id,
            quantity_on_hand=20,
        )
        db.add(inv_item)
        db.flush()

        job = _make_job(db, tenant, user, "year_end_close",
                        date(2025, 12, 1), date(2025, 12, 31))
        agent = YearEndCloseAgent(
            db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True,
        )
        agent.job = job
        result = agent._step_inventory_valuation()

        # 20 units * $250 = $5000
        assert result.data["total_inventory_value"] >= 5000.0

    def test_step13_retained_earnings_unavailable(self, db, tenant, user):
        """Step 13 flags INFO when beginning retained earnings cannot be found."""
        job = _make_job(db, tenant, user, "year_end_close",
                        date(2025, 12, 1), date(2025, 12, 31))
        agent = YearEndCloseAgent(
            db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True,
        )
        agent.job = job
        # Populate step_results for full_year_summary (needed by step 13)
        agent.step_results["full_year_summary"] = {
            "annual_income_statement": {"net_income": 50000},
        }
        result = agent._step_retained_earnings_summary()

        assert result.data["calculation_available"] is False
        info = [a for a in result.anomalies if a.anomaly_type == "yearend_retained_earnings_unavailable"]
        assert len(info) == 1
        assert info[0].severity == AnomalySeverity.INFO


# ---------------------------------------------------------------------------
# Phase 12 — TaxPackageAgent tests (7 tests)
# ---------------------------------------------------------------------------


class TestTaxPackageAgent:
    """Tests for the Tax Package Compilation Agent (Phase 12)."""

    def test_step1_collects_completed_jobs(self, db, tenant, user):
        """Step 1 finds completed agent jobs for the tax year."""
        # Create completed year-end close
        ye_job = _make_job(
            db, tenant, user, "year_end_close",
            date(2025, 12, 1), date(2025, 12, 31),
            status="complete",
            report_payload={"steps": {}},
        )
        ye_job.completed_at = datetime.now(timezone.utc)
        db.flush()

        # Create completed 1099 prep
        prep_job = _make_job(
            db, tenant, user, "1099_prep",
            date(2025, 1, 1), date(2025, 12, 31),
            status="complete",
            report_payload={"steps": {}},
        )
        prep_job.completed_at = datetime.now(timezone.utc)
        db.flush()

        # Create a month-end close
        me_job = _make_job(
            db, tenant, user, "month_end_close",
            date(2025, 6, 1), date(2025, 6, 30),
            status="complete",
            report_payload={"steps": {}},
        )
        me_job.completed_at = datetime.now(timezone.utc)
        db.flush()

        job = _make_job(db, tenant, user, "tax_package",
                        date(2025, 1, 1), date(2025, 12, 31))
        agent = TaxPackageAgent(
            db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True,
        )
        agent.job = job
        result = agent._step_collect_agent_outputs()

        assert result.data["tax_year"] == 2025
        assert "year_end_close" in result.data["agents_found"]
        assert "1099_prep" in result.data["agents_found"]
        assert 6 in result.data["month_end_closes"]

    def test_step2_critical_gaps(self, db, tenant, user):
        """Step 2 flags CRITICAL when year_end_close or 1099_prep missing."""
        job = _make_job(db, tenant, user, "tax_package",
                        date(2025, 1, 1), date(2025, 12, 31))
        agent = TaxPackageAgent(
            db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True,
        )
        agent.job = job
        # Empty collection — nothing found
        agent.step_results["collect_agent_outputs"] = {
            "agents_found": {},
            "month_end_closes": {},
            "month_end_closes_found": 0,
            "months_missing": list(range(1, 13)),
            "required_complete": False,
            "recommended_met": 0,
            "recommended_total": 5,
        }

        result = agent._step_assess_completeness()

        critical = [a for a in result.anomalies if a.severity == AnomalySeverity.CRITICAL]
        assert len(critical) == 2
        types = {a.anomaly_type for a in critical}
        assert "tax_package_missing_year_end_close" in types
        assert "tax_package_missing_1099_prep" in types

    def test_step2_readiness_score(self, db, tenant, user):
        """Readiness score is required_score * 0.6 + recommended_score * 0.4."""
        job = _make_job(db, tenant, user, "tax_package",
                        date(2025, 1, 1), date(2025, 12, 31))
        agent = TaxPackageAgent(
            db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True,
        )
        agent.job = job

        # All required met (2/2), partial recommended (3/5)
        agent.step_results["collect_agent_outputs"] = {
            "agents_found": {"year_end_close": {}, "1099_prep": {}},
            "month_end_closes": {},
            "month_end_closes_found": 0,
            "months_missing": list(range(1, 13)),
            "required_complete": True,
            "recommended_met": 3,
            "recommended_total": 5,
        }

        result = agent._step_assess_completeness()

        # required: 2/2 = 1.0 * 0.6 = 0.6
        # recommended: 3/5 = 0.6 * 0.4 = 0.24
        # total = 0.84
        assert abs(result.data["readiness_score"] - 0.84) < 0.01

    def test_step3_financial_statements_from_year_end(self, db, tenant, user):
        """Step 3 extracts income statement from year-end close report_payload."""
        ye_payload = {
            "steps": {
                "full_year_summary": {
                    "annual_income_statement": {
                        "total_revenue": 500000,
                        "total_cogs": 200000,
                        "gross_profit": 300000,
                        "total_expenses": 150000,
                        "net_income": 150000,
                    },
                    "quarterly_breakdown": {"q1": {}, "q2": {}, "q3": {}, "q4": {}},
                },
                "ar_aging_snapshot": {"total_ar": 75000},
                "inventory_valuation": {"total_inventory_value": 120000},
            },
        }
        ye_job = _make_job(
            db, tenant, user, "year_end_close",
            date(2025, 12, 1), date(2025, 12, 31),
            status="complete",
            report_payload=ye_payload,
        )
        ye_job.completed_at = datetime.now(timezone.utc)
        db.flush()

        job = _make_job(db, tenant, user, "tax_package",
                        date(2025, 1, 1), date(2025, 12, 31))
        agent = TaxPackageAgent(
            db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True,
        )
        agent.job = job
        agent.step_results["collect_agent_outputs"] = {
            "agents_found": {
                "year_end_close": {"job_id": ye_job.id},
            },
            "month_end_closes": {},
        }

        result = agent._step_compile_financial_statements()

        assert result.data["income_statement"]["annual"]["total_revenue"] == 500000
        assert result.data["balance_sheet_components"]["accounts_receivable"] == 75000
        assert result.data["balance_sheet_components"]["inventory_value"] == 120000

    def test_step4_schedules_compiled(self, db, tenant, user):
        """Step 4 always includes schedule F (anomaly summary)."""
        job = _make_job(db, tenant, user, "tax_package",
                        date(2025, 1, 1), date(2025, 12, 31))
        agent = TaxPackageAgent(
            db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True,
        )
        agent.job = job
        agent.step_results["collect_agent_outputs"] = {
            "agents_found": {},
            "month_end_closes": {},
        }

        result = agent._step_compile_supporting_schedules()

        assert "schedule_f_anomaly_summary" in result.data["schedules_available"]
        assert result.data["schedule_f_anomaly_summary"] is not None

    def test_step5_report_generated(self, db, tenant, user):
        """Step 5 generates report_payload with executive_summary."""
        job = _make_job(db, tenant, user, "tax_package",
                        date(2025, 1, 1), date(2025, 12, 31))
        agent = TaxPackageAgent(
            db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True,
        )
        agent.job = job
        agent.step_results["collect_agent_outputs"] = {
            "agents_found": {},
            "month_end_closes": {},
            "month_end_closes_found": 0,
            "required_complete": False,
        }
        agent.step_results["assess_completeness"] = {
            "readiness_score": 0.0,
        }
        agent.step_results["compile_financial_statements"] = {
            "income_statement": None,
            "balance_sheet_components": {},
        }
        agent.step_results["compile_supporting_schedules"] = {
            "schedules_available": ["schedule_f_anomaly_summary"],
            "schedule_a_1099": None,
            "schedule_f_anomaly_summary": {"total_anomalies": 0},
        }

        result = agent._step_generate_report()

        assert result.data["report_generated"] is True
        assert job.report_payload is not None
        assert "executive_summary" in job.report_payload
        assert job.report_payload["executive_summary"]["tax_year"] == 2025
        assert "report_html" in job.report_payload

    def test_required_agents_constant(self):
        """REQUIRED_AGENTS includes year_end_close and 1099_prep."""
        assert REQUIRED_AGENTS == {"year_end_close", "1099_prep"}


# ---------------------------------------------------------------------------
# Shared tests (3 tests)
# ---------------------------------------------------------------------------


class TestSharedRegistryAndCompletion:
    """Tests shared across Phase 11 and Phase 12."""

    def test_both_agents_in_registry(self):
        """Both YearEndCloseAgent and TaxPackageAgent are in AGENT_REGISTRY."""
        from app.services.agents.agent_runner import AgentRunner
        AgentRunner._ensure_registry()

        assert AgentJobType.YEAR_END_CLOSE in AgentRunner.AGENT_REGISTRY
        assert AgentRunner.AGENT_REGISTRY[AgentJobType.YEAR_END_CLOSE] is YearEndCloseAgent

        assert AgentJobType.TAX_PACKAGE in AgentRunner.AGENT_REGISTRY
        assert AgentRunner.AGENT_REGISTRY[AgentJobType.TAX_PACKAGE] is TaxPackageAgent

    def test_approval_paths(self):
        """year_end_close uses FULL approval; tax_package uses SIMPLE."""
        from app.services.agents.approval_gate import ApprovalGateService

        # year_end_close should NOT be in SIMPLE (uses full path with period lock)
        assert "year_end_close" not in ApprovalGateService.SIMPLE_APPROVAL_TYPES

        # tax_package should be in SIMPLE (read-only, no financial writes)
        assert "tax_package" in ApprovalGateService.SIMPLE_APPROVAL_TYPES

    def test_all_12_agent_types_registered(self):
        """All 12 AgentJobType enum values have registered agent classes."""
        from app.services.agents.agent_runner import AgentRunner
        AgentRunner.AGENT_REGISTRY.clear()
        AgentRunner._ensure_registry()

        all_types = list(AgentJobType)
        assert len(all_types) == 12, f"Expected 12 AgentJobType values, got {len(all_types)}"

        for job_type in all_types:
            assert job_type in AgentRunner.AGENT_REGISTRY, (
                f"{job_type.value} is not registered in AGENT_REGISTRY"
            )
