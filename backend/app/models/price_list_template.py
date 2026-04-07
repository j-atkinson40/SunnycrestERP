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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PriceListTemplate(Base):
    """PDF layout template for generating price list documents."""

    __tablename__ = "price_list_templates"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    layout_type: Mapped[str] = mapped_column(String(50), default="grouped")
    columns: Mapped[int] = mapped_column(Integer, default=1)
    show_product_codes: Mapped[bool] = mapped_column(Boolean, default=True)
    show_descriptions: Mapped[bool] = mapped_column(Boolean, default=True)
    show_notes: Mapped[bool] = mapped_column(Boolean, default=True)
    show_category_headers: Mapped[bool] = mapped_column(Boolean, default=True)
    logo_position: Mapped[str] = mapped_column(String(50), default="top-left")
    primary_color: Mapped[str] = mapped_column(String(7), default="#000000")
    font_family: Mapped[str] = mapped_column(String(100), default="helvetica")
    header_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    footer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    show_effective_date: Mapped[bool] = mapped_column(Boolean, default=True)
    show_page_numbers: Mapped[bool] = mapped_column(Boolean, default=True)
    show_contractor_price: Mapped[bool] = mapped_column(Boolean, default=False)
    show_homeowner_price: Mapped[bool] = mapped_column(Boolean, default=False)
    source_pdf_document_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("kb_documents.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    source_pdf_document = relationship("KBDocument", foreign_keys=[source_pdf_document_id])
