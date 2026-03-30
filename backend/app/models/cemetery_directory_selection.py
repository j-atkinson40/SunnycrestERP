"""Cemetery Directory Selection — tracks which directory entries a tenant has actioned."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CemeteryDirectorySelection(Base):
    __tablename__ = "cemetery_directory_selections"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )

    # Google Places ID of the cemetery that was actioned
    place_id: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # 'added' = created a Cemetery record; 'skipped' = user dismissed
    action: Mapped[str] = mapped_column(String(20), nullable=False, default="skipped")

    # FK to Cemetery record created (only set when action = 'added')
    cemetery_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("cemeteries.id"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    company = relationship("Company")
    cemetery = relationship("Cemetery")
