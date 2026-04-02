import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LegacySettings(Base):
    __tablename__ = "legacy_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, unique=True)
    print_deadline_days_before: Mapped[int] = mapped_column(Integer, server_default="1")
    watermark_enabled: Mapped[bool] = mapped_column(Boolean, server_default="false")
    watermark_text: Mapped[str] = mapped_column(String(200), server_default="PROOF")
    watermark_opacity: Mapped[Decimal] = mapped_column(Numeric(3, 2), server_default="0.30")
    watermark_position: Mapped[str] = mapped_column(String(20), server_default="center")
    tif_filename_template: Mapped[str] = mapped_column(String(500), server_default="'{print_name} - {name}.tif'")
    dropbox_connected: Mapped[bool] = mapped_column(Boolean, server_default="false")
    dropbox_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    dropbox_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    dropbox_target_folder: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dropbox_auto_save: Mapped[bool] = mapped_column(Boolean, server_default="false")
    gdrive_connected: Mapped[bool] = mapped_column(Boolean, server_default="false")
    gdrive_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    gdrive_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    gdrive_folder_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    gdrive_folder_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    gdrive_auto_save: Mapped[bool] = mapped_column(Boolean, server_default="false")
    print_shop_delivery: Mapped[str] = mapped_column(String(20), server_default="link")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    company = relationship("Company")


class LegacyPrintShopContact(Base):
    __tablename__ = "legacy_print_shop_contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(500), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
