"""Platform notification model — operator dashboard alerts."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PlatformNotification(Base):
    __tablename__ = "platform_notifications"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )
    incident_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("platform_incidents.id"),
        nullable=True,
    )

    level: Mapped[str] = mapped_column(
        String(20), nullable=False, default="info"
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_dismissed: Mapped[bool] = mapped_column(Boolean, default=False)
    dismissed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index(
            "idx_platform_notif_dismissed",
            "is_dismissed",
            postgresql_where=(is_dismissed.is_(False)),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<PlatformNotification {self.id[:8]} "
            f"level={self.level} dismissed={self.is_dismissed}>"
        )
