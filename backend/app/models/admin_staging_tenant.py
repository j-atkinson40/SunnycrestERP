"""Admin staging tenant — seeded tenant created for testing/demos."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AdminStagingTenant(Base):
    __tablename__ = "admin_staging_tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    created_by_admin_id: Mapped[str] = mapped_column(String(36), ForeignKey("platform_users.id"), nullable=False)
    vertical: Mapped[str] = mapped_column(String(50), nullable=False)
    preset: Mapped[str] = mapped_column(String(100), nullable=False)
    temp_admin_email: Mapped[str] = mapped_column(String(255), nullable=False)
    temp_admin_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
