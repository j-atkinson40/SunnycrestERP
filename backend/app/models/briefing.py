"""Phase 6 — Briefing ORM model.

Lives alongside the legacy `employee_briefings` table + model per the
approved coexist strategy. This table holds morning + evening narrative
briefings produced by the new `app.services.briefings` package.

Semantics differ from `employee_briefings`:
  - This table is (user_id, briefing_type, DATE(generated_at)) unique,
    so morning + evening coexist same day.
  - Content is narrative-first (`narrative_text`) with `structured_sections`
    JSONB for machine-readable UI rendering.
  - No `primary_area` / `tier` columns — Phase 6's "section emphasis" is
    driven by active_space + prompt branching, not a discrete tier.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


BRIEFING_TYPES = ("morning", "evening")


class Briefing(Base):
    __tablename__ = "briefings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    briefing_type: Mapped[str] = mapped_column(String(16), nullable=False)

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivery_channels: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )

    # Content
    narrative_text: Mapped[str] = mapped_column(Text, nullable=False)
    structured_sections: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    # Generation context
    active_space_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    active_space_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    role_slug: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    generation_context: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Metrics
    generation_duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    intelligence_cost_usd: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 6), nullable=True
    )
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    company = relationship("Company")
    user = relationship("User")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "company_id": self.company_id,
            "user_id": self.user_id,
            "briefing_type": self.briefing_type,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "delivery_channels": self.delivery_channels or [],
            "narrative_text": self.narrative_text,
            "structured_sections": self.structured_sections or {},
            "active_space_id": self.active_space_id,
            "active_space_name": self.active_space_name,
            "role_slug": self.role_slug,
            "generation_duration_ms": self.generation_duration_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "intelligence_cost_usd": (
                str(self.intelligence_cost_usd)
                if self.intelligence_cost_usd is not None
                else None
            ),
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


__all__ = ["Briefing", "BRIEFING_TYPES"]
