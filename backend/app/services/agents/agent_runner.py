"""Agent runner — factory/dispatcher that creates jobs and routes them to the correct agent class.

The API endpoints call this service. It handles job creation with validation,
instantiation of the correct agent subclass, and background execution.
"""

import logging
import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.agent import AgentJob
from app.schemas.agent import AgentJobStatus, AgentJobType

logger = logging.getLogger(__name__)


class AgentRunner:
    """Factory for creating and dispatching accounting agent jobs."""

    # Registry of job_type → agent class. Populated as phases are built.
    # Phase 2 will add: AgentJobType.MONTH_END_CLOSE: MonthEndCloseAgent
    AGENT_REGISTRY: dict[AgentJobType, type] = {}

    @staticmethod
    def create_job(
        db: Session,
        tenant_id: str,
        job_type: AgentJobType,
        period_start: date,
        period_end: date,
        dry_run: bool = True,
        triggered_by: str | None = None,
        trigger_type: str = "manual",
    ) -> AgentJob:
        """Create an agent_jobs record with validation.

        Does NOT start execution — call run_job() separately
        (typically via BackgroundTasks).
        """
        # Validate period
        if period_end < period_start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="period_end must be >= period_start",
            )

        if not dry_run and period_end > date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot close a period that hasn't ended yet (period_end is in the future)",
            )

        # Check no duplicate running job for same type + period
        existing = (
            db.query(AgentJob)
            .filter(
                AgentJob.tenant_id == tenant_id,
                AgentJob.job_type == job_type.value,
                AgentJob.period_start == period_start,
                AgentJob.period_end == period_end,
                AgentJob.status.in_(["pending", "running", "awaiting_approval"]),
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A {job_type.value} job for this period is already {existing.status}",
            )

        # Check period lock (unless dry_run)
        if not dry_run:
            from app.services.agents.period_lock import PeriodLockService

            if PeriodLockService.is_period_locked(db, tenant_id, period_start, period_end):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This period is already locked. Unlock it before running a non-dry-run job.",
                )

        job = AgentJob(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            job_type=job_type.value,
            status="pending",
            period_start=period_start,
            period_end=period_end,
            dry_run=dry_run,
            triggered_by=triggered_by,
            trigger_type=trigger_type,
            run_log=[],
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        logger.info(
            "Agent job created: %s type=%s period=%s–%s dry_run=%s",
            job.id, job_type.value, period_start, period_end, dry_run,
        )
        return job

    @staticmethod
    def run_job(job_id: str, db: Session) -> AgentJob:
        """Look up job, instantiate the correct agent, execute.

        Called from a background task so the API returns immediately.
        """
        job = db.query(AgentJob).filter(AgentJob.id == job_id).first()
        if not job:
            raise ValueError(f"AgentJob {job_id} not found")

        try:
            job_type_enum = AgentJobType(job.job_type)
        except ValueError:
            job.status = "failed"
            job.error_message = f"Unknown job type: {job.job_type}"
            db.commit()
            raise ValueError(f"Unknown job type: {job.job_type}")

        agent_class = AgentRunner.AGENT_REGISTRY.get(job_type_enum)
        if not agent_class:
            job.status = "failed"
            job.error_message = f"No agent registered for {job.job_type}. This agent type is not yet implemented."
            db.commit()
            logger.warning("No agent class registered for %s", job.job_type)
            return job

        agent = agent_class(
            db=db,
            tenant_id=job.tenant_id,
            job_id=job_id,
            dry_run=job.dry_run,
        )
        return agent.execute()

    @staticmethod
    def get_job_status(db: Session, job_id: str, tenant_id: str) -> AgentJob:
        """Return current job with run_log and anomalies."""
        job = (
            db.query(AgentJob)
            .filter(AgentJob.id == job_id, AgentJob.tenant_id == tenant_id)
            .first()
        )
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent job not found",
            )
        return job
