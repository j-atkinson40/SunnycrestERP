"""UrnProduct model — urn catalog items (stocked or drop-shipped from Wilbert)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UrnProduct(Base):
    __tablename__ = "urn_products"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Fulfillment source
    source_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="drop_ship"
    )  # stocked | drop_ship

    # Attributes
    material: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # wood | metal | ceramic | biodegradable | composite | other
    style: Mapped[str | None] = mapped_column(String(200), nullable=True)
    available_colors: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # JSON array of color strings

    # Keepsake sets
    is_keepsake_set: Mapped[bool] = mapped_column(Boolean, default=False)
    companion_skus: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # JSON array of companion SKU strings

    # Engraving capabilities
    engravable: Mapped[bool] = mapped_column(Boolean, default=True)
    photo_etch_capable: Mapped[bool] = mapped_column(Boolean, default=False)
    available_fonts: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # JSON array of font name strings

    # Pricing
    base_cost: Mapped[float | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    retail_price: Mapped[float | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )

    # Catalog references
    image_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    wilbert_catalog_url: Mapped[str | None] = mapped_column(
        String(2000), nullable=True
    )

    # Status
    discontinued: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    tenant = relationship("Company", foreign_keys=[tenant_id])
    inventory = relationship(
        "UrnInventory", back_populates="urn_product", uselist=False
    )

    __table_args__ = (
        Index("ix_urn_products_tenant_sku", "tenant_id", "sku"),
        Index("ix_urn_products_tenant_source", "tenant_id", "source_type"),
    )
