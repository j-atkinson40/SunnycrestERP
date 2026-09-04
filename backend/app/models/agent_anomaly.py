"""Agent anomaly — normalized anomaly records for accounting agent jobs."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Numeric, String, Text,
    and_, event, select, update,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.agent import AgentJob


class AgentAnomaly(Base):
    __tablename__ = "agent_anomalies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_job_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    #: Denormalised from the job. A partial unique index cannot span tables, and
    #: after the anomaly-subject arc subjects are deliberately NOT globally
    #: unique — `fiscal_year:2026` is byte-identical across tenants, which is
    #: what makes it a stable subject. Without this column the supersede key
    #: would collapse two tenants' anomalies into one row.
    #: ⚠️ DERIVED, NOT SUPPLIED — see the before_insert listener below.
    #: Nullable until phase 5c -- see r176's expand/contract note. The
    #: before_insert listener fills it on every insert regardless.
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    agent_run_step_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agent_run_steps.id"), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    anomaly_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolved_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Set when a later run produced the same subject+type for this tenant.
    #: ⚠️ DELIBERATELY NOT `resolved=True`. Marking a duplicate resolved claims a
    #: HUMAN acted on it — a false statement in the audit trail, and one that
    #: biases every "what did operators decide" query toward overstating
    #: engagement. A superseded row was replaced by the machine, not decided by
    #: a person, and the two must stay distinguishable.
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    @classmethod
    def open_filter(cls):
        """The predicate for "this still needs an operator's attention".

        ⚠️ USE THIS RATHER THAN `resolved.is_(False)` AT EVERY READ SITE.
        Adding `superseded_at` silently changed what a bare `resolved == False`
        filter means: it now includes rows the machine replaced. Every count,
        badge and queue built on the bare filter would overstate by the size of
        the duplicate backlog — 240 rows in production at the time this landed.

        Single-sourced so the two conditions cannot drift apart, and pinned by
        `tests/test_anomaly_supersede.py::test_no_read_site_filters_on_resolved_alone`,
        which is a scanner rather than a convention.
        """
        return and_(cls.resolved.is_(False), cls.superseded_at.is_(None))

    # Relationships
    job = relationship("AgentJob", foreign_keys=[agent_job_id])
    step = relationship("AgentRunStep", foreign_keys=[agent_run_step_id])
    resolver = relationship("User", foreign_keys=[resolved_by])


@event.listens_for(AgentAnomaly, "before_insert")
def _derive_tenant_from_job(mapper, connection, target: AgentAnomaly) -> None:
    """Fill `tenant_id` from the owning job.

    ⚠️ DERIVED RATHER THAN ASKED FOR, deliberately. Six production call sites
    and thirteen test/seed sites construct `AgentAnomaly`, and a `tenant_id`
    each of them supplies is a value each of them can get WRONG — and wrong here
    means a row filed under the wrong tenant, which the supersede key would then
    treat as another tenant's decision. A field nobody sets is not a field
    anybody can set inconsistently.

    A caller that supplies one is not silently overridden: a value that
    disagrees with the job raises, because that disagreement is a real bug and
    the quiet fix would hide it.
    """
    job_tenant = connection.execute(
        select(AgentJob.tenant_id).where(AgentJob.id == target.agent_job_id)
    ).scalar_one_or_none()

    if job_tenant is None:
        raise ValueError(
            f"AgentAnomaly references agent_job_id={target.agent_job_id!r}, "
            "which does not exist; tenant cannot be derived."
        )
    if target.tenant_id is not None and target.tenant_id != job_tenant:
        raise ValueError(
            f"AgentAnomaly.tenant_id={target.tenant_id!r} disagrees with its "
            f"job's tenant {job_tenant!r}. One of them is wrong, and guessing "
            "which would file the row under the wrong tenant."
        )
    target.tenant_id = job_tenant


@event.listens_for(AgentAnomaly, "before_insert")
def _supersede_the_open_row_for_this_subject(mapper, connection, target: AgentAnomaly) -> None:
    """Phase 5b — supersede on write.

    When an agent writes an anomaly whose key already has an OPEN row, that row
    is superseded rather than a duplicate appended. This is what closes the
    2026-09-01 canon requirement; phases 1-5a were precondition.

    ⚠️ A NEW ROW IS WRITTEN AND THE PRIOR ROW IS NOT REOPENED. The subject is
    what the end transition acts on; that act happened and completed, and a
    later occurrence is a different decision on a different day. Reopening would
    record "this category has been a problem since August" when the truth is it
    was a problem, was fixed, and RECURRED — and recurrence is the more useful
    fact, since a subject that keeps returning is a signal about the classifier
    or about vendor coding. It would also break the settled note's "what did I
    resolve on this day", because a resolved row would be open again.

    ⚠️ ONLY OPEN ROWS ARE SUPERSEDED, via `open_filter()` rather than a
    predicate written here. A row a human RESOLVED keeps its resolution — the
    recurrence is a new row beside it, not an erasure of the decision. Enumerated
    per-row against production 2026-09-04: 2,289 rows hold exactly two state
    combinations (fully open, or resolved with `resolved_at` + note), zero
    half-resolved, so `open_filter()` is complete rather than merely plausible.

    ⚠️ THIS LIVES ON THE MODEL, NOT IN `BaseAgent`, BECAUSE BaseAgent IS ONE
    WRITER OF SIX. The others are ar_payment_posting (x2), ar_invoice_posting,
    proactive_agents and the aftercare adapter — none of which inherit from
    BaseAgent. Putting supersede in the agent base class would have been a guard
    reasoned from one caller, leaving five writers duplicating exactly as before.

    `IS NOT DISTINCT FROM` on the subject columns keeps subjectless anomalies
    supersedable. `= NULL` never matches, so a key that reached SQL as plain
    equality would leave the two deliberately-held subjectless types unable to
    supersede and therefore able to grow without bound — the exact condition
    they were flagged for. They are per-tenant singletons, so keying them on
    (tenant, type) is correct.

    ⚠️ AND THIS OPERATOR IS DEFENSIVE, NOT LOAD-BEARING — I claimed otherwise
    and the break test disproved it. SQLAlchemy compiles `col == None` to
    `col IS NULL`, which matches NULLs too, so today the two forms behave
    identically and no test can tell them apart. What this form buys is
    independence from that coercion: rewritten as raw SQL or with a bound
    parameter, `= NULL` silently matches nothing and subjectless rows would
    duplicate forever with every check still green. Keep the explicit form;
    do not believe a test is watching it.
    """
    now = datetime.now(timezone.utc)
    t = AgentAnomaly.__table__
    connection.execute(
        update(t)
        .where(
            t.c.tenant_id == target.tenant_id,
            t.c.anomaly_type == target.anomaly_type,
            t.c.entity_type.is_not_distinct_from(target.entity_type),
            t.c.entity_id.is_not_distinct_from(target.entity_id),
            AgentAnomaly.open_filter(),
        )
        .values(superseded_at=now)
    )
