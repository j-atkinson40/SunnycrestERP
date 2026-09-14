import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class JobRun(Base):
    """Audit log for SOME scheduled/manual job executions.

    ⚠️ NOT EVERY SCHEDULED JOB. Measured 2026-09-11: 37 scheduled
    registrations, 27 of which route through a wrapper that writes here. Ten do
    not, and NOTHING IN THIS TABLE SAYS WHICH — a job_type's absence from a
    night is indistinguishable from a job that never logs. The wrapper
    population is enumerated in `tests/test_scheduler_wrapper_ratchet.py`.

    ⚠️ BOUNDARY — `status` GAINED A FOURTH VALUE ON 2026-09-14.

        before 2026-09-14:  running | completed | failed
        from   2026-09-14:  running | completed | completed_with_errors | failed

    `completed_with_errors` means the run finished and some ITEMS inside it
    failed. Before this date no row could carry it, so its ABSENCE on an older
    row is not evidence the run was clean — it is evidence the state did not
    exist. Any query comparing rows across that date must treat `completed`
    before it as `completed OR completed_with_errors`, or it will read the
    introduction of the state as a change in job health.

    The first writers are (c) commit 2b's targets. `error_count` on a
    `completed_with_errors` row counts FAILED ITEMS; on a per-tenant job
    `error_count` at the `failed` level counts TENANTS. Two units, and the
    column does not say which — read `status` first.
    """

    __tablename__ = "job_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    job_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    trigger: Mapped[str] = mapped_column(
        String(20), nullable=False, default="scheduled"
    )  # "scheduled" | "manual"
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="running"
    )  # "running" | "completed" | "completed_with_errors" | "failed"
    #    ⚠️ completed_with_errors exists only from 2026-09-14 — see the
    #    class docstring before comparing rows across that date.
    tenant_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
