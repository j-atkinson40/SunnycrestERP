"""TemplateSeason — date-range-based visibility rules for quick order templates."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TemplateSeason(Base):
    __tablename__ = "template_seasons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    season_name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_month: Mapped[int] = mapped_column(Integer, nullable=False)
    start_day: Mapped[int] = mapped_column(Integer, nullable=False)
    end_month: Mapped[int] = mapped_column(Integer, nullable=False)
    end_day: Mapped[int] = mapped_column(Integer, nullable=False)
    # Array of quick_quote_template IDs active during this season
    active_template_ids: Mapped[list] = mapped_column(JSONB, server_default="[]")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    company = relationship("Company", foreign_keys=[company_id])
