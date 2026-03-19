import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PriceListImport(Base):
    __tablename__ = "price_list_imports"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="uploaded"
    )
    raw_extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    claude_analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extraction_token_usage: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    items_extracted: Mapped[int] = mapped_column(Integer, default=0)
    items_matched_high_confidence: Mapped[int] = mapped_column(Integer, default=0)
    items_matched_low_confidence: Mapped[int] = mapped_column(Integer, default=0)
    items_unmatched: Mapped[int] = mapped_column(Integer, default=0)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    confirmed_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    items = relationship(
        "PriceListImportItem", back_populates="price_list_import", cascade="all, delete-orphan"
    )


class PriceListImportItem(Base):
    __tablename__ = "price_list_import_items"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    import_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("price_list_imports.id"), nullable=False, index=True
    )
    raw_text: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    extracted_name: Mapped[str] = mapped_column(String(255), nullable=False)
    extracted_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    extracted_sku: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    match_status: Mapped[str] = mapped_column(String(20), nullable=False)
    matched_template_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True
    )
    matched_template_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    match_confidence: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2), nullable=True
    )
    match_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    final_product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    final_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    final_sku: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    action: Mapped[str] = mapped_column(
        String(20), nullable=False, default="create_product"
    )
    product_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    price_list_import = relationship("PriceListImport", back_populates="items")
