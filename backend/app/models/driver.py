import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Driver(Base):
    """Driver profile linked to a user/employee."""

    __tablename__ = "drivers"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    employee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    # Phase 8e.2 — optional parallel link for portal-authed drivers.
    # Business-logic invariant: exactly one of employee_id or
    # portal_user_id is populated per Driver row in production.
    # NOT enforced as a DB CHECK constraint — allows migration
    # windows where a driver transitions between tenant-user and
    # portal-user identities. Service layer + tests enforce.
    portal_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("portal_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    license_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    license_class: Mapped[str | None] = mapped_column(String(10), nullable=True)
    license_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    preferred_vehicle_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("vehicles.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    modified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    company = relationship("Company")
    employee = relationship("User")
    preferred_vehicle = relationship("Vehicle")
    portal_user = relationship("PortalUser", foreign_keys=[portal_user_id])
