"""Base accounting agent class.

All 13 accounting agents extend this class. Subclasses implement:
  - STEPS: list[str]  — ordered step names
  - run_step(step_name: str) -> StepResult

The base class handles:
  - Job record creation and lifecycle management
  - Per-step logging with timing
  - Anomaly collection and normalization
  - Dry-run enforcement (read-only guard)
  - Error recovery and status transitions
  - Report payload assembly
  - Approval gate triggering
"""

import logging
import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import ClassVar

from sqlalchemy.orm import Session

from app.models.agent import AgentJob
from app.models.agent_anomaly import AgentAnomaly
from app.models.agent_run_step import AgentRunStep
from app.schemas.agent import (
    AgentJobStatus,
    AnomalyItem,
    AnomalySeverity,
    StepResult,
)

logger = logging.getLogger(__name__)


class AgentStepError(Exception):
    """Raised when a step fails during execution."""

    def __init__(self, step_name: str, cause: Exception):
        self.step_name = step_name
        self.cause = cause
        super().__init__(f"Step '{step_name}' failed: {cause}")


class DryRunGuardError(Exception):
    """Raised when a write operation is attempted in dry_run mode."""
    pass


class BaseAgent:
    """Base class for all Bridgeable accounting agents."""

    # Subclasses must define these
    STEPS: ClassVar[list[str]] = []

    def __init__(
        self,
        db: Session,
        tenant_id: str,
        job_id: str,
        dry_run: bool = True,
    ):
        self.db = db
        self.tenant_id = tenant_id
        self.job_id = job_id
        self.dry_run = dry_run
        self.job: AgentJob | None = None
        self.current_step: int = 0
        self.anomalies: list[AnomalyItem] = []
        self.step_results: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Abstract method — subclasses implement this
    # ------------------------------------------------------------------

    def run_step(self, step_name: str) -> StepResult:
        """Execute a single step. Must be overridden by subclasses."""
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement run_step()"
        )

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def execute(self) -> AgentJob:
        """Run all steps in sequence, handle errors, manage lifecycle."""
        try:
            self._load_job()
            self._set_status(AgentJobStatus.RUNNING)
            self.job.started_at = datetime.now(timezone.utc)
            self.db.commit()

            for i, step_name in enumerate(self.STEPS):
                self.current_step = i + 1
                self._run_step_with_logging(step_name)

            self._assemble_report()
            self._set_status(AgentJobStatus.AWAITING_APPROVAL)
            self._trigger_approval_gate()

        except AgentStepError as e:
            self._handle_step_failure(e)
        except Exception as e:
            self._handle_unexpected_failure(e)

        return self.job

    # ------------------------------------------------------------------
    # Step execution wrapper
    # ------------------------------------------------------------------

    def _run_step_with_logging(self, step_name: str) -> None:
        """Wrap each step with timing, logging, and anomaly capture."""
        step_record = self._create_step_record(step_name)
        start = datetime.now(timezone.utc)

        try:
            result = self.run_step(step_name)

            duration_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
            self._complete_step_record(step_record, result, duration_ms)
            self._save_step_anomalies(step_record, result.anomalies)
            self._append_run_log(
                step_name, "complete", result.message,
                len(result.anomalies), duration_ms,
            )
            self.step_results[step_name] = result.data

        except Exception as e:
            duration_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
            self._fail_step_record(step_record, str(e), duration_ms)
            self._append_run_log(step_name, "failed", str(e), 0, duration_ms)
            raise AgentStepError(step_name=step_name, cause=e)

    # ------------------------------------------------------------------
    # Dry-run guard
    # ------------------------------------------------------------------

    def guard_write(self) -> None:
        """Call before ANY database write in a subclass step.

        Raises DryRunGuardError if dry_run=True, ensuring dry-run mode
        is truly read-only.
        """
        if self.dry_run:
            raise DryRunGuardError(
                "Attempted write operation in dry_run mode. "
                "Remove dry_run=True or call guard_write() conditionally."
            )

    # ------------------------------------------------------------------
    # Anomaly recording
    # ------------------------------------------------------------------

    def add_anomaly(
        self,
        severity: AnomalySeverity,
        anomaly_type: str,
        description: str,
        entity_type: str | None = None,
        entity_id: str | None = None,
        amount: Decimal | None = None,
    ) -> None:
        """Record an anomaly during a step. Increments job.anomaly_count."""
        anomaly = AnomalyItem(
            severity=severity,
            anomaly_type=anomaly_type,
            description=description,
            entity_type=entity_type,
            entity_id=entity_id,
            amount=amount,
        )
        self.anomalies.append(anomaly)
        self.job.anomaly_count += 1
        self.db.flush()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_job(self) -> None:
        self.job = self.db.query(AgentJob).filter(AgentJob.id == self.job_id).first()
        if not self.job:
            raise ValueError(f"AgentJob {self.job_id} not found")

    def _set_status(self, status: AgentJobStatus) -> None:
        self.job.status = status.value
        if status in (AgentJobStatus.COMPLETE, AgentJobStatus.FAILED, AgentJobStatus.REJECTED):
            self.job.completed_at = datetime.now(timezone.utc)
        self.db.commit()

    def _create_step_record(self, step_name: str) -> AgentRunStep:
        step = AgentRunStep(
            id=str(uuid.uuid4()),
            agent_job_id=self.job_id,
            step_number=self.current_step,
            step_name=step_name,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(step)
        self.db.commit()
        return step

    def _complete_step_record(
        self, step: AgentRunStep, result: StepResult, duration_ms: int
    ) -> None:
        step.status = "complete"
        step.completed_at = datetime.now(timezone.utc)
        step.duration_ms = duration_ms
        step.output_summary = result.data
        step.anomalies = [a.model_dump(mode="json") for a in result.anomalies]
        self.db.commit()

    def _fail_step_record(
        self, step: AgentRunStep, error: str, duration_ms: int
    ) -> None:
        step.status = "failed"
        step.completed_at = datetime.now(timezone.utc)
        step.duration_ms = duration_ms
        step.error_message = error
        self.db.commit()

    def _save_step_anomalies(
        self, step: AgentRunStep, anomalies: list[AnomalyItem]
    ) -> None:
        for a in anomalies:
            record = AgentAnomaly(
                id=str(uuid.uuid4()),
                agent_job_id=self.job_id,
                agent_run_step_id=step.id,
                severity=a.severity.value,
                anomaly_type=a.anomaly_type,
                entity_type=a.entity_type,
                entity_id=a.entity_id,
                description=a.description,
                amount=a.amount,
            )
            self.db.add(record)
            self.anomalies.append(a)
            self.job.anomaly_count += 1
        if anomalies:
            self.db.commit()

    def _append_run_log(
        self,
        step_name: str,
        status: str,
        message: str,
        anomaly_count: int,
        duration_ms: int,
    ) -> None:
        log_entry = {
            "step_number": self.current_step,
            "step_name": step_name,
            "status": status,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": duration_ms,
            "message": message,
            "anomaly_count": anomaly_count,
        }
        # JSONB append — reload, append, reassign for change detection
        current_log = list(self.job.run_log or [])
        current_log.append(log_entry)
        self.job.run_log = current_log
        self.db.commit()

    def _assemble_report(self) -> None:
        """Collect all step_results into report_payload JSONB.

        Subclasses can override to customize report structure.
        """
        self.job.report_payload = {
            "job_type": self.job.job_type,
            "period_start": str(self.job.period_start) if self.job.period_start else None,
            "period_end": str(self.job.period_end) if self.job.period_end else None,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dry_run": self.dry_run,
            "anomaly_count": self.job.anomaly_count,
            "steps": {k: v for k, v in self.step_results.items()},
            "anomalies": [a.model_dump(mode="json") for a in self.anomalies],
        }
        self.db.commit()

    def _trigger_approval_gate(self) -> None:
        """Generate a secure approval token and trigger review email."""
        token = secrets.token_urlsafe(48)
        self.job.approval_token = token
        self.db.commit()

        try:
            from app.services.agents.approval_gate import ApprovalGateService
            ApprovalGateService.send_review_email(
                job=self.job,
                token=token,
                tenant_id=self.tenant_id,
                db=self.db,
            )
        except Exception as e:
            logger.error("Failed to send approval email for job %s: %s", self.job_id, e)

    def _handle_step_failure(self, e: AgentStepError) -> None:
        logger.error(
            "Agent step '%s' failed for job %s: %s",
            e.step_name, self.job_id, e.cause,
        )
        self.job.error_message = f"Step '{e.step_name}' failed: {e.cause}"
        self._set_status(AgentJobStatus.FAILED)

    def _handle_unexpected_failure(self, e: Exception) -> None:
        logger.exception("Unexpected agent failure for job %s", self.job_id)
        self.job.error_message = f"Unexpected error: {e}"
        self._set_status(AgentJobStatus.FAILED)
