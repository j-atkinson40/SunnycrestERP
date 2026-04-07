"""KB extension notification — tracks extension installs that need KB recommendations."""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class KBExtensionNotification(Base):
    __tablename__ = "kb_extension_notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    extension_slug: Mapped[str] = mapped_column(String(100), nullable=False)
    extension_name: Mapped[str] = mapped_column(String(200), nullable=False)
    notified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    briefing_date: Mapped[date] = mapped_column(Date, nullable=False)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
