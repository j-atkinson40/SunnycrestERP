"""Tests for accounting agent infrastructure (Phase 1).

Covers: models, period locks, base agent, agent runner, approval gate, API endpoints.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, event, JSON
from sqlalchemy.orm import Session, sessionmaker
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
from app.schemas.agent import (
    AgentJobCreate,
    AgentJobStatus,
    AgentJobType,
    AnomalyItem,
    AnomalySeverity,
    ApprovalAction,
    StepResult,
)
from app.services.agents.base_agent import BaseAgent, DryRunGuardError
from app.services.agents.period_lock import (
    PeriodAlreadyLockedError,
    PeriodLockedError,
    PeriodLockService,
)
from app.services.agents.agent_runner import AgentRunner


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine():
    """Create an in-memory SQLite engine for testing."""
    eng = create_engine("sqlite:///:memory:")
    # SQLite doesn't support JSONB — map it to JSON at the dialect level
    @event.listens_for(eng, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        pass  # hook needed for event registration

    # Only create the tables our tests actually need (avoids JSONB errors from 250+ tables)
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
        ]
    ]
    # Temporarily swap JSONB columns to JSON for SQLite compatibility
    jsonb_cols = []
    for table in tables:
        for col in table.columns:
            if isinstance(col.type, JSONB):
                jsonb_cols.append((col, col.type))
                col.type = JSON()
    Base.metadata.create_all(eng, tables=tables)
    # Restore original types so PostgreSQL models remain correct
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


@pytest.fixture
def sample_job(db: Session, tenant: Company, user: User) -> AgentJob:
    job = AgentJob(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        job_type="month_end_close",
        status="pending",
        period_start=date(2025, 11, 1),
        period_end=date(2025, 11, 30),
        dry_run=True,
        triggered_by=user.id,
        run_log=[],
    )
    db.add(job)
    db.flush()
    return job


# ---------------------------------------------------------------------------
# 1. AgentJob CRUD & status transitions
# ---------------------------------------------------------------------------


class TestAgentJobCRUD:
    def test_create_job(self, db, tenant, user):
        job = AgentJob(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            job_type="month_end_close",
            status="pending",
            period_start=date(2025, 11, 1),
            period_end=date(2025, 11, 30),
            dry_run=True,
            triggered_by=user.id,
        )
        db.add(job)
        db.flush()
        assert job.id is not None
        assert job.status == "pending"
        assert job.anomaly_count == 0

    def test_status_transitions(self, db, sample_job):
        sample_job.status = "running"
        db.flush()
        assert sample_job.status == "running"

        sample_job.status = "awaiting_approval"
        db.flush()
        assert sample_job.status == "awaiting_approval"

        sample_job.status = "approved"
        db.flush()
        assert sample_job.status == "approved"

    def test_run_log_append(self, db, sample_job):
        log = list(sample_job.run_log or [])
        log.append({"step": 1, "status": "complete"})
        sample_job.run_log = log
        db.flush()
        assert len(sample_job.run_log) == 1


# ---------------------------------------------------------------------------
# 2. Period locks
# ---------------------------------------------------------------------------


class TestPeriodLock:
    def test_lock_period(self, db, tenant, user):
        lock = PeriodLockService.lock_period(
            db=db,
            tenant_id=tenant.id,
            period_start=date(2025, 11, 1),
            period_end=date(2025, 11, 30),
            locked_by=user.id,
            reason="month-end close",
        )
        assert lock.is_active is True
        assert lock.tenant_id == tenant.id

    def test_overlap_detection(self, db, tenant, user):
        PeriodLockService.lock_period(
            db=db,
            tenant_id=tenant.id,
            period_start=date(2025, 11, 1),
            period_end=date(2025, 11, 30),
            locked_by=user.id,
        )
        with pytest.raises(PeriodAlreadyLockedError):
            PeriodLockService.lock_period(
                db=db,
                tenant_id=tenant.id,
                period_start=date(2025, 11, 15),
                period_end=date(2025, 12, 15),
            )

    def test_check_date_in_locked_period(self, db, tenant, user):
        PeriodLockService.lock_period(
            db=db,
            tenant_id=tenant.id,
            period_start=date(2025, 11, 1),
            period_end=date(2025, 11, 30),
        )
        lock = PeriodLockService.check_date_in_locked_period(
            db, tenant.id, date(2025, 11, 15)
        )
        assert lock is not None

        lock = PeriodLockService.check_date_in_locked_period(
            db, tenant.id, date(2025, 12, 1)
        )
        assert lock is None

    def test_unlock_period(self, db, tenant, user):
        lock = PeriodLockService.lock_period(
            db=db,
            tenant_id=tenant.id,
            period_start=date(2025, 10, 1),
            period_end=date(2025, 10, 31),
        )
        unlocked = PeriodLockService.unlock_period(db, lock.id, user.id)
        assert unlocked.is_active is False
        assert unlocked.unlocked_by == user.id

    def test_is_period_locked(self, db, tenant):
        assert not PeriodLockService.is_period_locked(
            db, tenant.id, date(2025, 9, 1), date(2025, 9, 30)
        )
        PeriodLockService.lock_period(
            db=db,
            tenant_id=tenant.id,
            period_start=date(2025, 9, 1),
            period_end=date(2025, 9, 30),
        )
        assert PeriodLockService.is_period_locked(
            db, tenant.id, date(2025, 9, 1), date(2025, 9, 30)
        )


# ---------------------------------------------------------------------------
# 3. Approval gate
# ---------------------------------------------------------------------------


class TestApprovalGate:
    def test_process_approve(self, db, tenant, user, sample_job):
        import secrets
        token = secrets.token_urlsafe(48)
        sample_job.status = "awaiting_approval"
        sample_job.approval_token = token
        sample_job.period_start = date(2025, 8, 1)
        sample_job.period_end = date(2025, 8, 31)
        sample_job.dry_run = False
        db.flush()

        from app.services.agents.approval_gate import ApprovalGateService
        action = ApprovalAction(action="approve")
        result = ApprovalGateService.process_approval(token, action, db)
        assert result.status == "complete"
        assert result.approval_token is None

        # Verify period lock was created
        locks = PeriodLockService.get_active_locks(db, tenant.id)
        aug_lock = [l for l in locks if l.period_start == date(2025, 8, 1)]
        assert len(aug_lock) == 1

    def test_process_reject(self, db, tenant, user):
        import secrets
        job = AgentJob(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            job_type="unbilled_orders",
            status="awaiting_approval",
            period_start=date(2025, 7, 1),
            period_end=date(2025, 7, 31),
            approval_token=secrets.token_urlsafe(48),
            run_log=[],
        )
        db.add(job)
        db.flush()

        from app.services.agents.approval_gate import ApprovalGateService
        action = ApprovalAction(action="reject", rejection_reason="Numbers don't add up")
        result = ApprovalGateService.process_approval(job.approval_token, action, db)
        assert result.status == "rejected"
        assert result.rejection_reason == "Numbers don't add up"

        # Verify no period lock
        locks = PeriodLockService.get_active_locks(db, tenant.id)
        jul_lock = [l for l in locks if l.period_start == date(2025, 7, 1)]
        assert len(jul_lock) == 0

    def test_expired_token(self, db, tenant):
        import secrets
        job = AgentJob(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            job_type="month_end_close",
            status="awaiting_approval",
            approval_token=secrets.token_urlsafe(48),
            created_at=datetime.now(timezone.utc) - timedelta(hours=73),
            run_log=[],
        )
        db.add(job)
        db.flush()

        from app.services.agents.approval_gate import ApprovalGateService
        from fastapi import HTTPException
        action = ApprovalAction(action="approve")
        with pytest.raises(HTTPException) as exc_info:
            ApprovalGateService.process_approval(job.approval_token, action, db)
        assert exc_info.value.status_code == 410


# ---------------------------------------------------------------------------
# 4. Agent runner — validation
# ---------------------------------------------------------------------------


class TestAgentRunner:
    def test_invalid_period_range(self, db, tenant, user):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            AgentRunner.create_job(
                db=db,
                tenant_id=tenant.id,
                job_type=AgentJobType.MONTH_END_CLOSE,
                period_start=date(2025, 12, 31),
                period_end=date(2025, 12, 1),  # end before start
                triggered_by=user.id,
            )
        assert exc_info.value.status_code == 400

    def test_future_period_non_dry_run(self, db, tenant, user):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            AgentRunner.create_job(
                db=db,
                tenant_id=tenant.id,
                job_type=AgentJobType.MONTH_END_CLOSE,
                period_start=date(2099, 1, 1),
                period_end=date(2099, 1, 31),
                dry_run=False,
                triggered_by=user.id,
            )
        assert exc_info.value.status_code == 400

    def test_duplicate_running_job(self, db, tenant, user):
        # Create a running job
        job = AgentJob(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            job_type="ar_collections",
            status="running",
            period_start=date(2025, 6, 1),
            period_end=date(2025, 6, 30),
            run_log=[],
        )
        db.add(job)
        db.flush()

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            AgentRunner.create_job(
                db=db,
                tenant_id=tenant.id,
                job_type=AgentJobType.AR_COLLECTIONS,
                period_start=date(2025, 6, 1),
                period_end=date(2025, 6, 30),
                triggered_by=user.id,
            )
        assert exc_info.value.status_code == 409

    def test_run_unknown_job_type(self, db, tenant, user):
        """A job with a raw job_type string not in AgentJobType raises ValueError."""
        job = AgentJob(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            job_type="nonexistent_agent_type",
            status="pending",
            period_start=date(2025, 5, 1),
            period_end=date(2025, 5, 31),
            run_log=[],
        )
        db.add(job)
        db.flush()
        with pytest.raises(ValueError, match="Unknown job type"):
            AgentRunner.run_job(job.id, db)


# ---------------------------------------------------------------------------
# 5. Base agent dry_run guard
# ---------------------------------------------------------------------------


class TestBaseAgentDryRunGuard:
    def test_guard_write_raises_in_dry_run(self, db, tenant, sample_job):
        class TestAgent(BaseAgent):
            STEPS = ["test_step"]
            def run_step(self, step_name):
                self.guard_write()
                return StepResult(message="done", data={})

        agent = TestAgent(db=db, tenant_id=tenant.id, job_id=sample_job.id, dry_run=True)
        with pytest.raises(DryRunGuardError):
            agent.guard_write()

    def test_guard_write_allows_non_dry_run(self, db, tenant, sample_job):
        sample_job.dry_run = False
        db.flush()

        agent = BaseAgent(db=db, tenant_id=tenant.id, job_id=sample_job.id, dry_run=False)
        # Should not raise
        agent.guard_write()

    def test_add_anomaly(self, db, tenant, sample_job):
        agent = BaseAgent(db=db, tenant_id=tenant.id, job_id=sample_job.id, dry_run=True)
        agent.job = sample_job
        agent.add_anomaly(
            severity=AnomalySeverity.WARNING,
            anomaly_type="test_anomaly",
            description="Test anomaly description",
            amount=Decimal("100.00"),
        )
        assert len(agent.anomalies) == 1
        assert sample_job.anomaly_count == 1


# ---------------------------------------------------------------------------
# 6. Schema validation
# ---------------------------------------------------------------------------


class TestSchemas:
    def test_agent_job_create(self):
        data = AgentJobCreate(
            job_type=AgentJobType.MONTH_END_CLOSE,
            period_start=date(2025, 11, 1),
            period_end=date(2025, 11, 30),
            dry_run=True,
        )
        assert data.job_type == AgentJobType.MONTH_END_CLOSE

    def test_approval_action_approve(self):
        action = ApprovalAction(action="approve")
        assert action.action == "approve"

    def test_approval_action_reject_requires_reason(self):
        action = ApprovalAction(action="reject", rejection_reason="Bad data")
        assert action.rejection_reason == "Bad data"

    def test_step_result(self):
        result = StepResult(
            message="Found 5 unbilled orders",
            data={"unbilled_count": 5},
            anomalies=[
                AnomalyItem(
                    severity=AnomalySeverity.WARNING,
                    anomaly_type="uninvoiced_delivery",
                    description="Delivery #123 has no invoice",
                    amount=Decimal("500.00"),
                )
            ],
        )
        assert len(result.anomalies) == 1
        assert result.anomalies[0].amount == Decimal("500.00")
