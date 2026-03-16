import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DeliveryRoute(Base):
    """A driver's route for a given day — contains ordered stops."""

    __tablename__ = "delivery_routes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    driver_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("drivers.id"), nullable=False
    )
    vehicle_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("vehicles.id"), nullable=True
    )
    route_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="draft"
    )  # draft, dispatched, in_progress, completed, cancelled
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    total_mileage: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 1), nullable=True
    )
    total_stops: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    modified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    company = relationship("Company")
    driver = relationship("Driver")
    vehicle = relationship("Vehicle")
    stops = relationship(
        "DeliveryStop", back_populates="route", order_by="DeliveryStop.sequence_number"
    )
