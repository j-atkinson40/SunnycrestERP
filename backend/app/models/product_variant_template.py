"""The PLATFORM VARIANT — the row a billed line will eventually point at.

Thin by design: a variant differs from its siblings on one axis (a finish, a
model, a height) plus tier, and everything else is the product's. It has to be a
row rather than a JSON member because `products.variant_template_id` points at
it, and in time a line's identity resolves through it.
"""
import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProductVariantTemplate(Base):
    __tablename__ = "product_variant_templates"
    __table_args__ = (
        UniqueConstraint("sku", name="uq_product_variant_templates_sku"),
        Index("ix_product_variant_templates_product", "product_template_id"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    product_template_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("product_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    #: Unique platform-wide. Phase 2 carries the existing 37 SKUs across verbatim —
    #: they are cited in investigation documents and in this week's analysis, so a
    #: regenerated SKU would break those references silently.
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    #: ⚠️ THE EXACT SOURCE NAME, NOT A COMPOSED ONE. "Bronze" + "Triune Burial
    #: Vault" composes plausibly, which is the trap — `"19 inch"` +
    #: `"Loved & Cherished"` is not `Loved & Cherished 19"`, and "Universal" +
    #: "Universal Urn Vault" is nonsense. This is also the string that lands on
    #: an invoice and that the resolver has to match.
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    #: Per-row in the source, which is what makes it variant-level rather than
    #: the product's. The product's description stays null rather than invented.
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    #: The variant's value on its product's axis — a finish, a model, a height.
    option_label: Mapped[str] = mapped_column(String(100), nullable=False)
    #: The only attribute that varies WITHIN a product rather than across one.
    tier: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    #: Wilbert publishes these. The product image shows the shell; the
    #: variant image shows the finish — which is the Universal / Basic Gray
    #: case exactly: one product, two variant images.
    image_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
