import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ApiKeyUsage(Base):
    """Hourly usage aggregation for API key analytics."""

    __tablename__ = "api_key_usage"
    __table_args__ = (
        Index("ix_api_key_usage_key_hour", "api_key_id", "hour_bucket"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    api_key_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("api_keys.id", ondelete="CASCADE"), nullable=False
    )
    hour_bucket: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
