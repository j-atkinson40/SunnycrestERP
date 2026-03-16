import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ImpersonationSession(Base):
    """Audit record for platform admin impersonation of tenant users."""

    __tablename__ = "impersonation_sessions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    platform_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("platform_users.id"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    impersonated_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    actions_performed: Mapped[int] = mapped_column(Integer, default=0)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    platform_user = relationship("PlatformUser", foreign_keys=[platform_user_id])
    tenant = relationship("Company", foreign_keys=[tenant_id])
    impersonated_user = relationship("User", foreign_keys=[impersonated_user_id])
