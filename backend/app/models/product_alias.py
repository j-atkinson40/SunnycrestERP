"""ProductAlias — resolve variant names to canonical products."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProductAlias(Base):
    __tablename__ = "product_aliases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False
    )
    alias_text: Mapped[str] = mapped_column(String(500), nullable=False)
    alias_text_normalized: Mapped[str] = mapped_column(String(500), nullable=False)
    canonical_product_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("products.id"), nullable=True
    )
    historical_product_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("historical_products.id"), nullable=True
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    company = relationship("Company", foreign_keys=[company_id])
    canonical_product = relationship("Product", foreign_keys=[canonical_product_id])
    historical_product = relationship("HistoricalProduct", foreign_keys=[historical_product_id])
