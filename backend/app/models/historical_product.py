"""HistoricalProduct — products from import not in current catalog."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class HistoricalProduct(Base):
    __tablename__ = "historical_products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    original_name: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(500), nullable=False)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    canonical_product_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("products.id"), nullable=True
    )
    equivalency_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_orderable: Mapped[bool] = mapped_column(Boolean, default=False)
    import_session_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    company = relationship("Company", foreign_keys=[company_id])
    canonical_product = relationship("Product", foreign_keys=[canonical_product_id])
