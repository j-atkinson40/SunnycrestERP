import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Cemetery(Base):
    __tablename__ = "cemeteries"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_cemetery_company_name"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )

    # Identity
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Location
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    county: Mapped[str | None] = mapped_column(String(100), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Contact
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Equipment — what the cemetery provides themselves
    cemetery_provides_lowering_device: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    cemetery_provides_grass: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    cemetery_provides_tent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    cemetery_provides_chairs: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # Notes
    equipment_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status / metadata
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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
    fh_history = relationship(
        "FuneralHomeCemeteryHistory",
        back_populates="cemetery",
        cascade="all, delete-orphan",
    )
