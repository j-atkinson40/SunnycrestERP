import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProductBundle(Base):
    __tablename__ = "product_bundles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sku: Mapped[str | None] = mapped_column(String(50), nullable=True)
    price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(30), default="manual")

    # Conditional pricing
    has_conditional_pricing: Mapped[bool] = mapped_column(Boolean, default=False)
    standalone_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    with_vault_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    vault_qualifier_categories: Mapped[str] = mapped_column(
        Text, default='["burial_vault","urn_vault"]'
    )

    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    modified_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    @property
    def vault_qualifier_list(self) -> list[str]:
        """Parse vault_qualifier_categories JSON text into a list."""
        if not self.vault_qualifier_categories:
            return ["burial_vault", "urn_vault"]
        return json.loads(self.vault_qualifier_categories)

    company = relationship("Company")
    components = relationship("ProductBundleComponent", back_populates="bundle", order_by="ProductBundleComponent.sort_order", cascade="all, delete-orphan")


class ProductBundleComponent(Base):
    __tablename__ = "product_bundle_components"
    __table_args__ = (
        UniqueConstraint("bundle_id", "product_id", name="uq_bundle_product"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    bundle_id: Mapped[str] = mapped_column(String(36), ForeignKey("product_bundles.id"), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    bundle = relationship("ProductBundle", back_populates="components")
    product = relationship("Product")
