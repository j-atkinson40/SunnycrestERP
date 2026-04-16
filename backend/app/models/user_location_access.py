"""UserLocationAccess — controls which locations a user can see and operate within."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserLocationAccess(Base):
    __tablename__ = "user_location_access"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    location_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("locations.id", ondelete="CASCADE"), nullable=True)
    access_level: Mapped[str] = mapped_column(String(50), default="operator")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User")
    company = relationship("Company")
    location = relationship("Location")
