import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DirectoryFetchLog(Base):
    __tablename__ = "directory_fetch_log"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    fetch_type: Mapped[str] = mapped_column(String(20), nullable=False)
    county_fips: Mapped[str | None] = mapped_column(String(5), nullable=True)
    center_lat: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    center_lng: Mapped[Decimal | None] = mapped_column(Numeric(11, 7), nullable=True)
    radius_miles: Mapped[int | None] = mapped_column(Integer, nullable=True)
    results_count: Mapped[int] = mapped_column(Integer, default=0)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    fetched_for_tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False
    )

    tenant = relationship("Company", foreign_keys=[fetched_for_tenant_id])
