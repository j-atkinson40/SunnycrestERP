"""Cemetery Directory Fetch Log — audit trail for Google Places API calls."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CemeteryDirectoryFetchLog(Base):
    __tablename__ = "cemetery_directory_fetch_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    search_radius_miles: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    center_lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    center_lng: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)

    # Relationships
    company = relationship("Company")
