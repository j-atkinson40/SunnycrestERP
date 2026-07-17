"""The JOB entity + its polymorphic reference spine (Reframe R-1, r132).

DISPLAY vs CODE (the honest divergence, tasks_reframe_investigation.md §3):
this entity DISPLAYS as **Task** everywhere users read; its code name is
`moc_job` because the old entity (`moc_task_catalog` — now displayed as
**Automation**) owns the `task` code surface too deeply to evict (routes,
services, DATA: engagement keys `task:<id>`, offer artifact_types). The
divergence is deliberate and documented — never "cleaned up" casually.

`MoCJobRef` — kind+key, lineage-stable keys per kind:
  automation    → moc_task_catalog.id (row id; boot seeds preserve ids —
                  the mirrors-suite teardown re-attaches, see landmine #2)
  triage_queue  → the stable TriageQueueConfig queue_id string
  focus         → focus_template.template_slug (row ids decay on version
                  bumps; slugs are the lineage handle)
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MoCJob(Base):
    __tablename__ = "moc_job"
    __table_args__ = (
        CheckConstraint(
            "scope IN ('platform_default', 'vertical_default')",
            name="ck_moc_job_scope",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scope: Mapped[str] = mapped_column(String(24), nullable=False, default="vertical_default")
    vertical: Mapped[str | None] = mapped_column(String(32), ForeignKey("verticals.slug"), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ponder: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    refs = relationship(
        "MoCJobRef", cascade="all, delete-orphan",
        order_by="MoCJobRef.display_order", lazy="selectin",
    )


class MoCJobRef(Base):
    __tablename__ = "moc_job_ref"
    __table_args__ = (
        CheckConstraint(
            "ref_kind IN ('automation', 'triage_queue', 'focus')",
            name="ck_moc_job_ref_kind",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("moc_job.id", ondelete="CASCADE"), nullable=False,
    )
    ref_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    ref_key: Mapped[str] = mapped_column(String(120), nullable=False)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=_now)
