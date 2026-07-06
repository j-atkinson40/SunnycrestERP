"""MoC domain-event outbox row (Canvas↔Runtime Bridge T-2.2a, migration r119).

One durable row per emitted domain event — written by `emit_event()` IN THE
SAME TRANSACTION as the mutation it records (transactional outbox: the event
commits iff the mutation commits). `payload` carries the catalog's filterable-
field values snapshotted at emit; the T-2.2b matcher evaluates trigger
conditions against it and marks `processed_at`. T-2.2a ships this inert —
nothing consumes the rows yet.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MoCDomainEvent(Base):
    __tablename__ = "moc_domain_event"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    # ON DELETE CASCADE — a deleted tenant's events go with it (and emitted
    # rows never block a company delete; existing test teardowns depend on it).
    company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # The catalog key ("case.opened") — moc_trigger_event_catalog.event_key.
    event_key: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # Filterable-field values at emit time (the condition-evaluation snapshot).
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    emitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    # NULL = awaiting the T-2.2b matcher (the partial-index work queue).
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
