import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("sku", "company_id", name="uq_product_sku_company"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=False, index=True
    )
    category_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("product_categories.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    cost_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    unit_of_measure: Mapped[str | None] = mapped_column(String(50), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Catalog builder fields
    pricing_type: Mapped[str] = mapped_column(String(20), default="sale")  # sale, rental
    rental_unit: Mapped[str | None] = mapped_column(String(30), nullable=True)  # service, set, day
    default_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(30), default="manual")  # manual, catalog_builder, csv_import
    is_inventory_tracked: Mapped[bool] = mapped_column(Boolean, default=True)
    product_line: Mapped[str | None] = mapped_column(String(100), nullable=True)  # e.g. "Monticello"
    variant_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # e.g. "STD-1P"

    # Conditional pricing
    price_without_our_product: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    has_conditional_pricing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    is_call_office: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")

    # Direct ship flag
    is_direct_ship_product: Mapped[bool] = mapped_column(Boolean, default=False)

    # Urn catalog / Wilbert import fields
    wilbert_sku: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    wholesale_cost: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    markup_percent: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    modified_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    company = relationship("Company")
    category = relationship("ProductCategory", back_populates="products")
    price_tiers = relationship(
        "ProductPriceTier",
        back_populates="product",
        order_by="ProductPriceTier.min_quantity",
    )
