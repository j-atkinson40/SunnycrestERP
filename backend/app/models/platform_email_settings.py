import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PlatformEmailSettings(Base):
    """Per-tenant email sending configuration — platform Resend or custom SMTP."""

    __tablename__ = "platform_email_settings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, unique=True
    )
    sending_mode: Mapped[str] = mapped_column(String(50), default="platform")
    from_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reply_to_email: Mapped[str | None] = mapped_column(String(500), nullable=True)
    smtp_host: Mapped[str | None] = mapped_column(String(500), nullable=True)
    smtp_port: Mapped[int] = mapped_column(Integer, default=587)
    smtp_username: Mapped[str | None] = mapped_column(String(500), nullable=True)
    smtp_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    smtp_use_tls: Mapped[bool] = mapped_column(Boolean, default=True)
    smtp_from_email: Mapped[str | None] = mapped_column(String(500), nullable=True)
    smtp_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    smtp_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    invoice_bcc_email: Mapped[str | None] = mapped_column(String(500), nullable=True)
    price_list_bcc_email: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
