"""Tests for Phases 10 & 13 accounting agents.

Phase 10 — Prep1099Agent (7 tests)
Phase 13 — AnnualBudgetAgent (8 tests)
Shared  — 2 tests (registry, no period lock)
Total   — 17 tests
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
from app.models.period_lock import PeriodLock
from app.models.role import Role
from app.models.user import User
from app.models.vendor import Vendor
from app.models.vendor_bill import VendorBill
from app.models.vendor_payment import VendorPayment
from app.models.vendor_payment_application import VendorPaymentApplication
from app.schemas.agent import (
    AgentJobType,
    AnomalySeverity,
    StepResult,
)
from app.services.agents.prep_1099_agent import (
    IRS_THRESHOLD,
    Prep1099Agent,
    mask_tax_id,
)
from app.services.agents.annual_budget_agent import (
    AnnualBudgetAgent,
    DEFAULT_COGS_GROWTH_PCT,
    DEFAULT_EXPENSE_GROWTH_PCT,
    DEFAULT_REVENUE_GROWTH_PCT,
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
            "vendors",
            "vendor_bills",
            "vendor_payments",
            "vendor_payment_applications",
        ]
    ]
    # Swap JSONB → JSON for SQLite compatibility
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
) -> AgentJob:
    job = AgentJob(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        job_type=job_type,
        status="pending",
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


def _seed_vendors(db: Session, tenant: Company) -> dict:
    """Create 4 vendors with varying 1099 configurations + payments."""
    vendors = {}

    # Vendor A — is_1099=True, has tax_id, paid $1200
    v_a = Vendor(
        id=str(uuid.uuid4()),
        company_id=tenant.id,
        name="Alpha Supplies",
        is_1099_vendor=True,
        tax_id="12-3456789",
        is_active=True,
    )
    db.add(v_a)
    vendors["a"] = v_a

    # Vendor B — is_1099=True, NO tax_id, paid $800
    v_b = Vendor(
        id=str(uuid.uuid4()),
        company_id=tenant.id,
        name="Beta Services",
        is_1099_vendor=True,
        tax_id=None,
        is_active=True,
    )
    db.add(v_b)
    vendors["b"] = v_b

    # Vendor C — is_1099=False (default), paid $900
    v_c = Vendor(
        id=str(uuid.uuid4()),
        company_id=tenant.id,
        name="Charlie Corp",
        is_1099_vendor=False,
        is_active=True,
    )
    db.add(v_c)
    vendors["c"] = v_c

    # Vendor D — is_1099=False, paid $400 (below threshold)
    v_d = Vendor(
        id=str(uuid.uuid4()),
        company_id=tenant.id,
        name="Delta LLC",
        is_1099_vendor=False,
        is_active=True,
    )
    db.add(v_d)
    vendors["d"] = v_d

    db.flush()

    # Create payments in 2025
    payments_spec = [
        (v_a, Decimal("700.00"), datetime(2025, 3, 15, tzinfo=timezone.utc)),
        (v_a, Decimal("500.00"), datetime(2025, 7, 20, tzinfo=timezone.utc)),
        (v_b, Decimal("800.00"), datetime(2025, 5, 10, tzinfo=timezone.utc)),
        (v_c, Decimal("900.00"), datetime(2025, 6, 1, tzinfo=timezone.utc)),
        (v_d, Decimal("400.00"), datetime(2025, 9, 15, tzinfo=timezone.utc)),
    ]

    # Create a dummy vendor bill for FK references
    dummy_bill = VendorBill(
        id=str(uuid.uuid4()),
        company_id=tenant.id,
        vendor_id=v_a.id,
        number="DUMMY-001",
        bill_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        due_date=datetime(2025, 2, 1, tzinfo=timezone.utc),
        status="paid",
        total=Decimal("5000.00"),
        amount_paid=Decimal("5000.00"),
    )
    db.add(dummy_bill)
    db.flush()

    for vendor, amount, pay_date in payments_spec:
        payment = VendorPayment(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            vendor_id=vendor.id,
            payment_date=pay_date,
            total_amount=amount,
            payment_method="check",
        )
        db.add(payment)
        db.flush()

        app = VendorPaymentApplication(
            id=str(uuid.uuid4()),
            payment_id=payment.id,
            bill_id=dummy_bill.id,
            amount_applied=amount,
        )
        db.add(app)

    db.flush()
    return vendors


# ---------------------------------------------------------------------------
# Phase 10 — Prep1099Agent tests (7 tests)
# ---------------------------------------------------------------------------


class TestPrep1099Agent:
    """Tests for the 1099 Prep Agent (Phase 10)."""

    def test_step1_payment_totals(self, db, tenant, user):
        """Step 1 computes correct per-vendor payment totals."""
        vendors = _seed_vendors(db, tenant)
        job = _make_job(db, tenant, user, "1099_prep", date(2025, 1, 1), date(2025, 12, 31))

        agent = Prep1099Agent(db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True)
        agent.job = job
        result = agent._step_compute_vendor_payment_totals()

        data = result.data
        assert data["total_vendors_paid"] == 4
        vendor_map = {v["vendor_id"]: v for v in data["vendors"]}

        # Alpha: $700 + $500 = $1200
        assert float(vendor_map[vendors["a"].id]["total_paid"]) == 1200.0
        assert vendor_map[vendors["a"].id]["above_threshold"] is True

        # Beta: $800
        assert float(vendor_map[vendors["b"].id]["total_paid"]) == 800.0
        assert vendor_map[vendors["b"].id]["above_threshold"] is True

        # Charlie: $900
        assert float(vendor_map[vendors["c"].id]["total_paid"]) == 900.0

        # Delta: $400 — below threshold
        assert float(vendor_map[vendors["d"].id]["total_paid"]) == 400.0
        assert vendor_map[vendors["d"].id]["above_threshold"] is False

    def test_step2_eligibility_classification(self, db, tenant, user):
        """Step 2 classifies vendors into INCLUDE, NEEDS_REVIEW, BELOW_THRESHOLD."""
        vendors = _seed_vendors(db, tenant)
        job = _make_job(db, tenant, user, "1099_prep", date(2025, 1, 1), date(2025, 12, 31))

        agent = Prep1099Agent(db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True)
        agent.job = job

        # Run step 1 first
        s1 = agent._step_compute_vendor_payment_totals()
        agent.step_results["compute_vendor_payment_totals"] = s1.data

        # Run step 2
        s2 = agent._step_apply_1099_eligibility()
        data = s2.data

        # Alpha + Beta above threshold with is_1099=True → INCLUDE
        # Charlie above threshold with is_1099=False → NEEDS_REVIEW
        # Delta below threshold → BELOW_THRESHOLD
        assert data["include_count"] == 2  # Alpha, Beta
        assert data["needs_review_count"] == 1  # Charlie
        assert data["below_threshold_count"] == 1  # Delta

    def test_step2_missing_tax_id_anomaly(self, db, tenant, user):
        """Step 2 raises CRITICAL anomaly for 1099 vendors missing tax ID."""
        vendors = _seed_vendors(db, tenant)
        job = _make_job(db, tenant, user, "1099_prep", date(2025, 1, 1), date(2025, 12, 31))

        agent = Prep1099Agent(db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True)
        agent.job = job

        s1 = agent._step_compute_vendor_payment_totals()
        agent.step_results["compute_vendor_payment_totals"] = s1.data

        s2 = agent._step_apply_1099_eligibility()

        critical = [a for a in s2.anomalies if a.severity == AnomalySeverity.CRITICAL]
        assert len(critical) == 1
        assert critical[0].anomaly_type == "missing_tax_id"
        assert critical[0].entity_id == vendors["b"].id  # Beta has no tax_id
        assert s2.data["missing_tax_id_count"] == 1

    def test_step3_data_gaps(self, db, tenant, user):
        """Step 3 flags data quality issues: unreviewed vendors and missing IDs."""
        vendors = _seed_vendors(db, tenant)
        job = _make_job(db, tenant, user, "1099_prep", date(2025, 1, 1), date(2025, 12, 31))

        agent = Prep1099Agent(db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True)
        agent.job = job

        s1 = agent._step_compute_vendor_payment_totals()
        agent.step_results["compute_vendor_payment_totals"] = s1.data
        s2 = agent._step_apply_1099_eligibility()
        agent.step_results["apply_1099_eligibility"] = s2.data

        s3 = agent._step_flag_data_gaps()

        # Should always include w9_tracking_not_implemented INFO
        w9_info = [a for a in s3.anomalies if a.anomaly_type == "w9_tracking_not_implemented"]
        assert len(w9_info) == 1
        assert w9_info[0].severity == AnomalySeverity.INFO

        # Missing tax IDs summary (CRITICAL)
        missing_summary = [a for a in s3.anomalies if a.anomaly_type == "missing_tax_ids_summary"]
        assert len(missing_summary) == 1
        assert missing_summary[0].severity == AnomalySeverity.CRITICAL

        # Unreviewed vendors (WARNING)
        unreviewed = [a for a in s3.anomalies if a.anomaly_type == "vendors_not_reviewed_for_1099"]
        assert len(unreviewed) == 1
        assert unreviewed[0].severity == AnomalySeverity.WARNING

    def test_mask_tax_id(self):
        """mask_tax_id never exposes full value."""
        assert mask_tax_id("12-3456789") == "******6789"
        assert mask_tax_id("123456789") == "*****6789"
        assert mask_tax_id(None) == "***"
        assert mask_tax_id("") == "***"
        assert mask_tax_id("ab") == "***"

    def test_tax_id_not_in_report_payload(self, db, tenant, user):
        """Full tax IDs must never appear in report_payload."""
        vendors = _seed_vendors(db, tenant)
        job = _make_job(db, tenant, user, "1099_prep", date(2025, 1, 1), date(2025, 12, 31))

        agent = Prep1099Agent(db=db, tenant_id=tenant.id, job_id=job.id, dry_run=True)
        agent.job = job

        s1 = agent._step_compute_vendor_payment_totals()
        agent.step_results["compute_vendor_payment_totals"] = s1.data
        s2 = agent._step_apply_1099_eligibility()
        agent.step_results["apply_1099_eligibility"] = s2.data

        # Check that no vendor entry in step 2 contains raw tax_id
        vendors_by_status = s2.data["vendors_by_status"]
        for status_key in ["include", "needs_review", "below_threshold"]:
            for v in vendors_by_status.get(status_key, []):
                assert "tax_id" not in v  # Only tax_id_masked should be present
                if v.get("has_tax_id"):
                    assert v["tax_id_masked"].startswith("*")

    def test_irs_threshold_constant(self):
        """IRS threshold is $600."""
        assert IRS_THRESHOLD == Decimal("600.00")


# ---------------------------------------------------------------------------
# Phase 13 — AnnualBudgetAgent tests (8 tests)
# ---------------------------------------------------------------------------


def _mock_income_statement(total_revenue=100000, total_cogs=40000, total_expenses=30000):
    """Build a mock income statement dict matching get_income_statement output."""
    gross = total_revenue - total_cogs
    net = gross - total_expenses
    return {
        "total_revenue": total_revenue,
        "total_cogs": total_cogs,
        "gross_profit": gross,
        "gross_margin_percent": round(gross / total_revenue * 100, 1) if total_revenue else 0,
        "total_expenses": total_expenses,
        "net_income": net,
        "revenue": [
            {"account_number": "4000", "account_name": "Sales Revenue", "amount": total_revenue},
        ],
        "cogs": [
            {"account_number": "5000", "account_name": "Cost of Goods Sold", "amount": total_cogs},
        ],
        "expenses": [
            {"account_number": "6000", "account_name": "Operating Expenses", "amount": total_expenses},
        ],
    }


def _mock_quarterly_income(annual_stmt, shares=None):
    """Build quarterly income statements based on seasonal shares."""
    if shares is None:
        shares = {"q1": 0.20, "q2": 0.30, "q3": 0.30, "q4": 0.20}
    results = {}
    for q, share in shares.items():
        results[q] = _mock_income_statement(
            total_revenue=annual_stmt["total_revenue"] * share,
            total_cogs=annual_stmt["total_cogs"] * share,
            total_expenses=annual_stmt["total_expenses"] * share,
        )
    return results


class TestAnnualBudgetAgent:
    """Tests for the Annual Budget Agent (Phase 13)."""

    def _make_budget_agent(self, db, tenant, user, budget_year=2026, dry_run=True, report_payload=None):
        job = _make_job(
            db, tenant, user, "annual_budget",
            date(budget_year, 1, 1), date(budget_year, 12, 31),
            dry_run=dry_run,
            report_payload=report_payload,
        )
        agent = AnnualBudgetAgent(db=db, tenant_id=tenant.id, job_id=job.id, dry_run=dry_run)
        agent.job = job
        return agent, job

    @patch("app.services.financial_report_service.get_income_statement")
    def test_step1_pulls_prior_year(self, mock_income, db, tenant, user):
        """Step 1 pulls prior year actuals for full year + 4 quarters."""
        annual = _mock_income_statement(100000, 40000, 30000)
        q_data = _mock_quarterly_income(annual)

        call_count = 0
        def side_effect(db_, tenant_id_, start, end):
            nonlocal call_count
            call_count += 1
            if start.month == 1 and end.month == 12:
                return annual
            q_key = f"q{(start.month - 1) // 3 + 1}"
            return q_data.get(q_key, _mock_income_statement(0, 0, 0))

        mock_income.side_effect = side_effect

        agent, job = self._make_budget_agent(db, tenant, user, budget_year=2026)
        result = agent._step_pull_prior_year_actuals()

        # Should call 5 times: 1 annual + 4 quarterly
        assert call_count == 5
        assert result.data["prior_year"] == 2025
        assert result.data["budget_year"] == 2026
        assert result.data["annual"]["total_revenue"] == 100000.0

    @patch("app.services.financial_report_service.get_income_statement")
    def test_step2_quarterly_shares_sum_to_one(self, mock_income, db, tenant, user):
        """Quarterly revenue shares must sum to ~1.0."""
        annual = _mock_income_statement(100000, 40000, 30000)
        q_shares = {"q1": 0.20, "q2": 0.30, "q3": 0.30, "q4": 0.20}
        q_data = _mock_quarterly_income(annual, q_shares)

        def side_effect(db_, tenant_id_, start, end):
            if start.month == 1 and end.month == 12:
                return annual
            q_key = f"q{(start.month - 1) // 3 + 1}"
            return q_data.get(q_key, _mock_income_statement(0, 0, 0))
        mock_income.side_effect = side_effect

        agent, job = self._make_budget_agent(db, tenant, user)
        s1 = agent._step_pull_prior_year_actuals()
        agent.step_results["pull_prior_year_actuals"] = s1.data

        s2 = agent._step_compute_quarterly_baseline()
        shares = s2.data["revenue_quarterly_shares"]

        total = sum(shares.values())
        assert abs(total - 1.0) < 0.001

    @patch("app.services.financial_report_service.get_income_statement")
    def test_step3_growth_math(self, mock_income, db, tenant, user):
        """Step 3 applies default growth rates correctly."""
        annual = _mock_income_statement(100000, 40000, 30000)
        q_data = _mock_quarterly_income(annual)

        def side_effect(db_, tenant_id_, start, end):
            if start.month == 1 and end.month == 12:
                return annual
            q_key = f"q{(start.month - 1) // 3 + 1}"
            return q_data.get(q_key, _mock_income_statement(0, 0, 0))
        mock_income.side_effect = side_effect

        agent, job = self._make_budget_agent(db, tenant, user)
        s1 = agent._step_pull_prior_year_actuals()
        agent.step_results["pull_prior_year_actuals"] = s1.data
        s2 = agent._step_compute_quarterly_baseline()
        agent.step_results["compute_quarterly_baseline"] = s2.data

        s3 = agent._step_apply_growth_assumptions()
        budget = s3.data["budget_year_annual"]

        # Revenue: 100000 * 1.05 = 105000
        assert abs(budget["revenue"] - 105000.0) < 0.01
        # COGS: 40000 * 1.03 = 41200
        assert abs(budget["cogs"] - 41200.0) < 0.01
        # Expenses: 30000 * 1.03 = 30900
        assert abs(budget["expenses"] - 30900.0) < 0.01
        # Net: (105000 - 41200) - 30900 = 32900
        assert abs(budget["net_income"] - 32900.0) < 0.01

    @patch("app.services.financial_report_service.get_income_statement")
    def test_step3_custom_assumptions(self, mock_income, db, tenant, user):
        """Step 3 uses user-provided growth assumptions from report_payload."""
        annual = _mock_income_statement(100000, 40000, 30000)
        q_data = _mock_quarterly_income(annual)

        def side_effect(db_, tenant_id_, start, end):
            if start.month == 1 and end.month == 12:
                return annual
            q_key = f"q{(start.month - 1) // 3 + 1}"
            return q_data.get(q_key, _mock_income_statement(0, 0, 0))
        mock_income.side_effect = side_effect

        agent, job = self._make_budget_agent(
            db, tenant, user,
            report_payload={"assumptions": {
                "revenue_growth_pct": 10.0,
                "cogs_growth_pct": 5.0,
                "expense_growth_pct": 2.0,
            }},
        )
        s1 = agent._step_pull_prior_year_actuals()
        agent.step_results["pull_prior_year_actuals"] = s1.data
        s2 = agent._step_compute_quarterly_baseline()
        agent.step_results["compute_quarterly_baseline"] = s2.data

        s3 = agent._step_apply_growth_assumptions()
        budget = s3.data["budget_year_annual"]

        # Revenue: 100000 * 1.10 = 110000
        assert abs(budget["revenue"] - 110000.0) < 0.01
        # COGS: 40000 * 1.05 = 42000
        assert abs(budget["cogs"] - 42000.0) < 0.01

    @patch("app.services.financial_report_service.get_income_statement")
    def test_step4_quarterly_sums_match_annual(self, mock_income, db, tenant, user):
        """Quarterly budget revenue sums should approximate annual target."""
        annual = _mock_income_statement(100000, 40000, 30000)
        q_data = _mock_quarterly_income(annual)

        def side_effect(db_, tenant_id_, start, end):
            if start.month == 1 and end.month == 12:
                return annual
            q_key = f"q{(start.month - 1) // 3 + 1}"
            return q_data.get(q_key, _mock_income_statement(0, 0, 0))
        mock_income.side_effect = side_effect

        agent, job = self._make_budget_agent(db, tenant, user)
        s1 = agent._step_pull_prior_year_actuals()
        agent.step_results["pull_prior_year_actuals"] = s1.data
        s2 = agent._step_compute_quarterly_baseline()
        agent.step_results["compute_quarterly_baseline"] = s2.data
        s3 = agent._step_apply_growth_assumptions()
        agent.step_results["apply_growth_assumptions"] = s3.data

        s4 = agent._step_generate_budget_lines()
        quarterly = s4.data["quarterly"]

        q_rev_sum = sum(quarterly[q]["revenue"] for q in ["q1", "q2", "q3", "q4"])
        annual_target = s3.data["budget_year_annual"]["revenue"]

        # Allow small rounding tolerance
        assert abs(q_rev_sum - annual_target) < 1.0

    @patch("app.services.financial_report_service.get_income_statement")
    def test_step4_phase9_contract(self, mock_income, db, tenant, user):
        """Step 4 quarterly_breakdown matches Phase 9 _extract_budget_for_period contract."""
        annual = _mock_income_statement(100000, 40000, 30000)
        q_data = _mock_quarterly_income(annual)

        def side_effect(db_, tenant_id_, start, end):
            if start.month == 1 and end.month == 12:
                return annual
            q_key = f"q{(start.month - 1) // 3 + 1}"
            return q_data.get(q_key, _mock_income_statement(0, 0, 0))
        mock_income.side_effect = side_effect

        agent, job = self._make_budget_agent(db, tenant, user)
        s1 = agent._step_pull_prior_year_actuals()
        agent.step_results["pull_prior_year_actuals"] = s1.data
        s2 = agent._step_compute_quarterly_baseline()
        agent.step_results["compute_quarterly_baseline"] = s2.data
        s3 = agent._step_apply_growth_assumptions()
        agent.step_results["apply_growth_assumptions"] = s3.data

        s4 = agent._step_generate_budget_lines()
        qb = s4.data["quarterly_breakdown"]

        # Must have Q1-Q4 keys
        for q_key in ["Q1", "Q2", "Q3", "Q4"]:
            assert q_key in qb, f"Missing {q_key} in quarterly_breakdown"
            q = qb[q_key]
            # Phase 9 contract requires all these keys
            for required_key in [
                "total_revenue", "total_cogs", "gross_profit",
                "gross_margin_pct", "total_expenses", "net_income",
                "net_margin_pct", "revenue_lines", "cogs_lines", "expense_lines",
            ]:
                assert required_key in q, f"Missing {required_key} in {q_key}"

    @patch("app.services.financial_report_service.get_income_statement")
    def test_step3_loss_projection_anomaly(self, mock_income, db, tenant, user):
        """Step 3 flags budget_projects_loss when net income is negative."""
        # High COGS + expenses so net income is negative after growth
        annual = _mock_income_statement(100000, 70000, 40000)
        # net = (100000 - 70000) - 40000 = -10000 (already a loss)
        q_data = _mock_quarterly_income(annual)

        def side_effect(db_, tenant_id_, start, end):
            if start.month == 1 and end.month == 12:
                return annual
            q_key = f"q{(start.month - 1) // 3 + 1}"
            return q_data.get(q_key, _mock_income_statement(0, 0, 0))
        mock_income.side_effect = side_effect

        agent, job = self._make_budget_agent(db, tenant, user)
        s1 = agent._step_pull_prior_year_actuals()
        agent.step_results["pull_prior_year_actuals"] = s1.data
        s2 = agent._step_compute_quarterly_baseline()
        agent.step_results["compute_quarterly_baseline"] = s2.data

        s3 = agent._step_apply_growth_assumptions()

        loss_anomalies = [a for a in s3.anomalies if a.anomaly_type == "budget_projects_loss"]
        assert len(loss_anomalies) == 1
        assert loss_anomalies[0].severity == AnomalySeverity.WARNING

    @patch("app.services.financial_report_service.get_income_statement")
    def test_monthly_equals_quarterly_divided_by_3(self, mock_income, db, tenant, user):
        """Monthly budget should be quarterly / 3."""
        annual = _mock_income_statement(120000, 48000, 36000)
        # Even quarters for simplicity
        q_data = _mock_quarterly_income(annual, {"q1": 0.25, "q2": 0.25, "q3": 0.25, "q4": 0.25})

        def side_effect(db_, tenant_id_, start, end):
            if start.month == 1 and end.month == 12:
                return annual
            q_key = f"q{(start.month - 1) // 3 + 1}"
            return q_data.get(q_key, _mock_income_statement(0, 0, 0))
        mock_income.side_effect = side_effect

        agent, job = self._make_budget_agent(db, tenant, user)
        s1 = agent._step_pull_prior_year_actuals()
        agent.step_results["pull_prior_year_actuals"] = s1.data
        s2 = agent._step_compute_quarterly_baseline()
        agent.step_results["compute_quarterly_baseline"] = s2.data
        s3 = agent._step_apply_growth_assumptions()
        agent.step_results["apply_growth_assumptions"] = s3.data

        s4 = agent._step_generate_budget_lines()
        monthly = s4.data["monthly"]
        quarterly = s4.data["quarterly"]

        # Jan is in Q1: monthly[jan].revenue ≈ quarterly[q1].revenue / 3
        q1_rev = quarterly["q1"]["revenue"]
        jan_rev = monthly["jan"]["revenue"]
        assert abs(jan_rev - round(q1_rev / 3, 2)) < 0.01


# ---------------------------------------------------------------------------
# Shared tests (2 tests)
# ---------------------------------------------------------------------------


class TestSharedRegistryAndApproval:
    """Tests shared across Phase 10 and Phase 13."""

    def test_both_agents_in_registry(self):
        """Both Prep1099Agent and AnnualBudgetAgent are in AGENT_REGISTRY."""
        from app.services.agents.agent_runner import AgentRunner
        AgentRunner._ensure_registry()

        assert AgentJobType.PREP_1099 in AgentRunner.AGENT_REGISTRY
        assert AgentRunner.AGENT_REGISTRY[AgentJobType.PREP_1099] is Prep1099Agent

        assert AgentJobType.ANNUAL_BUDGET in AgentRunner.AGENT_REGISTRY
        assert AgentRunner.AGENT_REGISTRY[AgentJobType.ANNUAL_BUDGET] is AnnualBudgetAgent

    def test_no_period_lock_on_approval(self, db, tenant, user):
        """Both 1099_prep and annual_budget use SIMPLE_APPROVAL_TYPES — no period lock."""
        from app.services.agents.approval_gate import ApprovalGateService

        assert "1099_prep" in ApprovalGateService.SIMPLE_APPROVAL_TYPES
        assert "annual_budget" in ApprovalGateService.SIMPLE_APPROVAL_TYPES
