"""Cemetery Directory model — Google Places-sourced cemetery entries."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CemeteryDirectory(Base):
    __tablename__ = "cemetery_directory"
    __table_args__ = (
        UniqueConstraint("company_id", "place_id", name="uq_cemetery_directory_company_place"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # Scoped per company — each manufacturer builds their own local directory
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )

    # Google Places identifier — upsert key within company scope
    place_id: Mapped[str] = mapped_column(String(200), nullable=False)

    # Identity
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Location
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    county: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Geocoordinates
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)

    # Google Places metadata
    google_rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 1), nullable=True)
    google_review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Lifecycle
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    first_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    company = relationship("Company")
