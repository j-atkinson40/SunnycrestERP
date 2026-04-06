"""WidgetDefinition — platform-wide widget catalog.

Each row describes a widget that can appear on one or more dashboard pages.
Visibility is gated by extension, permission, and preset.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WidgetDefinition(Base):
    __tablename__ = "widget_definitions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    widget_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Page contexts this widget can appear on (JSON array of slugs)
    page_contexts: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Size constraints
    default_size: Mapped[str] = mapped_column(String(10), default="1x1")
    min_size: Mapped[str] = mapped_column(String(10), default="1x1")
    max_size: Mapped[str] = mapped_column(String(10), default="4x4")
    supported_sizes: Mapped[list] = mapped_column(JSONB, default=lambda: ["1x1"])

    # Visibility rules
    required_extension: Mapped[str | None] = mapped_column(String(100), nullable=True)
    required_permission: Mapped[str | None] = mapped_column(String(100), nullable=True)
    required_preset: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Defaults
    default_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    default_position: Mapped[int] = mapped_column(Integer, default=99)

    # Metadata
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
