"""PulseSignal model — Phase W-4a Pulse Tier 2 signal-driven intelligence.

Persists user interaction signals from the Home Pulse surface
(dismiss + navigation) per BRIDGEABLE_MASTER §3.26.2.5 Tier 2.

**Why a dedicated table** (per D3 resolution):
  • Pulse signals are first-class platform data — audit trail, future
    analytics, cross-tenant aggregation for Mutual underwriting per
    BRIDGEABLE_MASTER §1.7.
  • Distinct semantically from `user_space_affinity` (which is
    command-bar ranking).
  • TTL-cleanup-friendly (90-day retention contemplated).
  • Bounded per-user volume (~hundreds/week) but queryable across
    users for analytics.

**Standardized JSONB metadata shapes** (per user direction):
  Dismiss signals: {component_key, time_of_day, work_areas_at_dismiss}
  Navigation signals: {from_component_key, to_route, dwell_time_seconds}

**Tenant isolation:** every row carries `company_id` so cross-user
analytics queries can be tenant-scoped end-to-end.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PulseSignal(Base):
    __tablename__ = "pulse_signals"
    __table_args__ = (
        Index(
            "ix_pulse_signals_user_timestamp",
            "user_id",
            "timestamp",
            postgresql_using="btree",
        ),
        Index(
            "ix_pulse_signals_company_timestamp",
            "company_id",
            "timestamp",
            postgresql_using="btree",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    # signal_type ∈ {"dismiss", "navigate"} (extensible)
    signal_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # layer ∈ {"personal", "operational", "anomaly", "activity"}
    layer: Mapped[str] = mapped_column(String(32), nullable=False)
    # component_key — widget_id for pinable widgets, stream key for
    # intelligence streams.
    component_key: Mapped[str] = mapped_column(String(128), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    # Standardized per signal_type — see module docstring.
    signal_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )

    user = relationship("User", foreign_keys=[user_id])
    company = relationship("Company", foreign_keys=[company_id])
