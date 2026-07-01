"""MoC witness marker (Canvas↔Runtime Bridge T-2.1b-WITNESS, migration r118).

The benign-but-real effect row. The ONLY writer is the engine's `record_marker`
action handler (`_handle_record_marker`). A marker row means one thing: "a
COMPILED MoC task fired LIVE at `fired_at`, from `moc_task_trigger_id`, in run
`run_id`, for `company_id`." Real (persisted, attributable → proves live firing)
but benign (nothing reads it → safe to delete). This table is the deliberate,
isolated target for the platform's first autonomous real scheduled fire; it is
NOT a business hub and MUST NOT accrete business meaning.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MoCWitnessMarker(Base):
    __tablename__ = "moc_witness_marker"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    # Attribution breadcrumbs (no FK — the marker table stays decoupled).
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    moc_task_trigger_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    fired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
