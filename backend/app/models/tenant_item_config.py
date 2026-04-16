"""TenantItemConfig — per-tenant item configuration overrides."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TenantItemConfig(Base):
    __tablename__ = "tenant_item_config"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False
    )
    registry_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("configurable_item_registry.id"), nullable=True
    )
    item_key: Mapped[str] = mapped_column(String(200), nullable=False)
    registry_type: Mapped[str] = mapped_column(String(100), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    company = relationship("Company", foreign_keys=[company_id])
    registry_item = relationship("ConfigurableItemRegistry", foreign_keys=[registry_id])
