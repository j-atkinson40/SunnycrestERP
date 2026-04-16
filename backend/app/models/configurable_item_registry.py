"""ConfigurableItemRegistry — platform-wide master list of configurable items."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ConfigurableItemRegistry(Base):
    __tablename__ = "configurable_item_registry"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    registry_type: Mapped[str] = mapped_column(String(100), nullable=False)
    item_key: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tier: Mapped[int] = mapped_column(Integer, nullable=False)
    vertical: Mapped[str] = mapped_column(String(50), nullable=False)
    tags: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    default_config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
