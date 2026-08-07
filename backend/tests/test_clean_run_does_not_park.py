"""A run that found nothing does not ask anyone to approve nothing.

Pre-fix EVERY agent run parked in `awaiting_approval` unconditionally, minted an
approval token, and emailed a review request — so the 15-minute
`expense_categorization` cron asked for a decision on an empty result every time
it fired. Dev carries 5,167 such jobs (366 tenants × 28 periods, one per tenant
per period — the duplicate guard working, not a runaway cron). On production the
volume is small; the defect is not the volume. A queue whose items are all empty
teaches the operator to ignore the queue.

⚠️ THE TRAP, and it is why this is not a one-line "0 anomalies → complete":
`month_end_close`'s approval is NOT about its anomalies. The close ITSELF is the
decision, and `approval_gate` writes the PeriodLock on approve. Auto-completing a
clean close would skip both the human and the lock — turning a noise fix into a
financial-control hole. Per-JOB agents park however quiet the run, and
`test_a_clean_MONTH_END_CLOSE_still_parks` is the assertion that keeps a later
simplification from removing the distinction.

Cleans up its own `cln-` tenants (COMPANY-LITTER ratchet).
"""
from __future__ import annotations

import uuid

import pytest

from app.database import SessionLocal
from app.models.agent import AgentJob
from app.models.company import Company
from app.schemas.agent import AgentJobStatus, AnomalyItem, AnomalySeverity, StepResult
from app.services.agents.base_agent import BaseAgent
from tests._cleanup import purge_companies_by_slug

_SLUG = "cln-"


@pytest.fixture(autouse=True)
def _purge():
    yield
    s = SessionLocal()
    try:
        purge_companies_by_slug(s, f"{_SLUG}%")
    finally:
        s.close()


@pytest.fixture
def env():
    s = SessionLocal()
    yield _Env(s)
    s.rollback()
    s.close()


class _Env:
    def __init__(self, s):
        self.s = s
        sfx = uuid.uuid4().hex[:8]
        self.company = Company(
            id=str(uuid.uuid4()), name=f"CLN {sfx}", slug=f"{_SLUG}{sfx}",
            is_active=True, vertical="manufacturing",
        )
        s.add(self.company); s.flush()
        self.co = self.company.id
        s.commit()

    def job(self, job_type: str) -> AgentJob:
        j = AgentJob(
            id=str(uuid.uuid4()), tenant_id=self.co, job_type=job_type,
            status="pending", anomaly_count=0,
        )
        self.s.add(j); self.s.commit()
        return j


class _QuietAgent(BaseAgent):
    """Completes one step and finds nothing."""
    STEPS = ["look"]

    def run_step(self, step_name: str) -> StepResult:
        return StepResult(message="nothing found", data={}, anomalies=[])


class _NoisyAgent(BaseAgent):
    """Completes one step and finds one thing."""
    STEPS = ["look"]

    def run_step(self, step_name: str) -> StepResult:
        return StepResult(
            message="found one", data={},
            anomalies=[AnomalyItem(
                severity=AnomalySeverity.WARNING,
                anomaly_type="something",
                description="a thing that needs a person",
            )],
        )


def _run(agent_cls, env, job) -> AgentJob:
    return agent_cls(
        db=env.s, tenant_id=env.co, job_id=job.id, dry_run=True
    ).execute()


class TestPerAnomalyAgentsCompleteWhenQuiet:
    """These agents' approval is about the anomalies. No anomalies, no decision."""

    @pytest.mark.parametrize("job_type", [
        "expense_categorization", "cash_receipts_matching", "ar_collections",
    ])
    def test_a_clean_run_COMPLETES(self, env, job_type):
        job = env.job(job_type)

        result = _run(_QuietAgent, env, job)

        assert result.status == AgentJobStatus.COMPLETE.value
        assert result.anomaly_count == 0

    def test_a_clean_run_MINTS_NO_APPROVAL_TOKEN(self, env):
        """The token IS the auth on the review link. Minting one for a run with
        nothing to review creates a live credential pointing at an empty
        decision."""
        job = env.job("expense_categorization")

        result = _run(_QuietAgent, env, job)

        assert result.approval_token is None

    @pytest.mark.parametrize("job_type", [
        "expense_categorization", "cash_receipts_matching", "ar_collections",
    ])
    def test_a_run_THAT_FOUND_SOMETHING_still_parks(self, env, job_type):
        """The other half. Completing a run that DID find something would lose
        the decision entirely — a far worse failure than the noise this fixes."""
        job = env.job(job_type)

        result = _run(_NoisyAgent, env, job)

        assert result.status == AgentJobStatus.AWAITING_APPROVAL.value
        assert result.anomaly_count == 1
        assert result.approval_token is not None


class TestPerJobAgentsAlwaysPark:
    """⚠️ THE TRAP. A blanket '0 anomalies → complete' walks straight into it."""

    def test_a_clean_MONTH_END_CLOSE_still_parks(self, env):
        """The close ITSELF is the decision — its anomalies are context, not the
        thing being approved — and `approval_gate` writes the PeriodLock on
        approve. Auto-completing a quiet close would skip the human AND leave
        the period unlocked while the job read as done."""
        job = env.job("month_end_close")

        result = _run(_QuietAgent, env, job)

        assert result.status == AgentJobStatus.AWAITING_APPROVAL.value
        assert result.anomaly_count == 0

    def test_an_UNKNOWN_job_type_parks(self, env):
        """Fail-closed on the classification: an agent nobody has classified
        keeps the old behaviour rather than silently auto-completing. A new
        agent that should complete-when-quiet opts IN by joining the set."""
        job = env.job("some_future_agent")

        result = _run(_QuietAgent, env, job)

        assert result.status == AgentJobStatus.AWAITING_APPROVAL.value


class TestTheSplitIsStatedOnce:
    def test_both_readers_share_one_definition(self, env):
        """The terminal-state branch and the notification branch make the SAME
        split. Stated twice they would be free to drift — which is how four AR
        balance formulas happened — so both read this constant.

        If a future agent joins the set, its notification cohort follows
        automatically; that coupling is the point, not a side effect.
        """
        assert BaseAgent.PER_ANOMALY_APPROVAL_JOB_TYPES == frozenset({
            "cash_receipts_matching", "ar_collections", "expense_categorization",
        })
        assert "month_end_close" not in BaseAgent.PER_ANOMALY_APPROVAL_JOB_TYPES
