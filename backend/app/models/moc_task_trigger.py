"""Maps of Content — task TRIGGER substrate (MoC Triggers T-1a, migration r115).

DESCRIPTIVE triggers: legible/editable metadata that does NOT fire yet. A task
carries 0..N heterogeneous triggers (schedule | event | manual) — a collection
mirroring the focus join. Execution is the deferred unified canvas↔runtime
bridge (T-2); this layer is the authored spec that bridge will wire.

Two tables:
- `moc_task_trigger` — the per-task trigger collection. `kind` typed + CHECK-
  constrained (extensible, like moc_task_vocabulary.kind); `config` JSONB,
  kind-specific:
    schedule → {spec_kind: time_of_day|cron|time_after_event, ...} — the shapes
               mirror the real workflow_scheduler trigger_config 1:1 so the
               future bridge is a wiring job, not a re-model.
    event    → {event: "<catalog key>", conditions: [{field, operator, value}]}
               conditions is a LIST holding ONE element now — filtered→rich
               later is appending elements, NEVER a schema migration.
    manual   → {} (no config).
- `moc_trigger_event_catalog` — the curated, seeded, EDITABLE event vocabulary
  (the 2a vocabulary-store philosophy). Each event carries `filterable_fields`
  (the fields a condition may reference) — grounded in real domain columns.

Because no domain-event bus exists (the investigation verdict), the event
catalog is honest metadata: the menu the execution bridge will wire, not a live
hook. Scope/actor conventions mirror moc_task_catalog (three-tier, FK-less
actor).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MoCTaskTrigger(Base):
    __tablename__ = "moc_task_trigger"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_catalog_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("moc_task_catalog.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # schedule | event | manual (CHECK-constrained; extensible, like the vocab kind)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    # Kind-specific spec (schedule shape / event+conditions / {}). The
    # conditions LIST lives here so filtered→rich is data, not a migration.
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Optional human summary override; else derived (humanize_schedule / the
    # event key). Kept for legibility, not required.
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=True)
    # Live-promotion gate (T-2.1b): default FALSE = unpromoted (dry-run). The
    # schedule sweep fires LIVE only when is_live AND the task's workflow is
    # COMPILED (single-owner) — a MIRROR task never fires live (§6 double-fire
    # hazard). Promotion is a deliberate per-trigger act.
    is_live: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        CheckConstraint(
            "kind IN ('schedule', 'event', 'manual')",
            name="ck_moc_task_trigger_kind",
        ),
    )


class MoCTriggerEventCatalog(Base):
    __tablename__ = "moc_trigger_event_catalog"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    # Dotted entity.event key (aligns with the seed naming precedent).
    event_key: Mapped[str] = mapped_column(String(120), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    # The real domain entity the event fires on (e.g. "sales_order").
    entity: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # [{field, type: enum|number|string|date, values?: [...]}] — feeds the
    # condition builder; grounded in real columns.
    filterable_fields: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )
    # Three-tier scope mirrors moc_task_vocabulary (events are shared/platform
    # by default per the shared-vocabulary decision; a vertical can add its own).
    scope: Mapped[str] = mapped_column(
        String(32), nullable=False, default="platform_default"
    )
    vertical: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("verticals.slug"), nullable=True, index=True
    )
    tenant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=True)
    display_order: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        CheckConstraint(
            "scope IN ('platform_default', 'vertical_default', 'tenant_override')",
            name="ck_moc_trigger_event_catalog_scope",
        ),
    )
