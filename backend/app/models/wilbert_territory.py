"""WilbertTerritory — shared territory definitions for Wilbert licensee coverage areas."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class WilbertTerritory(Base):
    __tablename__ = "wilbert_territories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    territory_code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    counties: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    zip_codes: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    lat_bounds: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    lng_bounds: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    confirmed_by_company_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=True
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    confirmed_by_company = relationship("Company", foreign_keys=[confirmed_by_company_id])
