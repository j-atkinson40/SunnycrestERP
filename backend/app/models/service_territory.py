"""Manufacturer service territories — counties served by a manufacturer."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ManufacturerServiceTerritory(Base):
    __tablename__ = "manufacturer_service_territories"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    state_code: Mapped[str] = mapped_column(String(2), nullable=False)
    county_name: Mapped[str] = mapped_column(String(100), nullable=False)
    county_fips: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    company = relationship("Company")
