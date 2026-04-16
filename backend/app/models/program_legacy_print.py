"""Program Legacy Print — per-tenant catalog of Wilbert standard + custom Legacy print designs.

Families select a Legacy print when personalizing a burial vault or urn. Each tenant
can enable/disable which prints they offer, upload their own custom prints, and set
per-print pricing (only used in per_option pricing mode).
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProgramLegacyPrint(Base):
    __tablename__ = "program_legacy_prints"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False)
    program_code: Mapped[str] = mapped_column(String(50), nullable=False)  # 'vault' | 'urn'
    wilbert_catalog_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_custom: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    price_addition: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
