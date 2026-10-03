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
    # Product taxability axis (sales-tax arc): 'inherit' = not yet
    # reviewed (resolves TAXABLE — the default law); 'taxable'/'exempt'
    # are the operator's explicit marks. Nothing is guessed exempt.
    tax_class: Mapped[str] = mapped_column(String(20), nullable=False, server_default="inherit")
    variant_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # e.g. "STD-1P"

    # Conditional pricing
    price_without_our_product: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    has_conditional_pricing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    is_call_office: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")

    # Direct ship flag
    is_direct_ship_product: Mapped[bool] = mapped_column(Boolean, default=False)

    # Placer / lowering device flags (used for funeral home preference auto-add)
    is_placer: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )  # True only on the Vault Placer product
    is_lowering_device: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )  # True on Full Equipment, Lowering Device & Grass, Lowering Device Only

    # Extension visibility
    visibility_requires_extension: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )  # 'wastewater', 'redi_rock', 'rosetta', null = always visible
    is_extension_hidden: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )  # true = hidden until extension enabled

    # Personalization
    has_personalization: Mapped[bool] = mapped_column(Boolean, server_default="false")
    personalization_tier: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # 'wilbert_standard', 'continental', 'salute', 'urn_vault'

    # Urn catalog / Wilbert import fields
    wilbert_sku: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    wholesale_cost: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    markup_percent: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    #: ⚠️ NULL MEANS NOT ESTABLISHED. Declared here for the first time at r196 —
    #: `u3v4w5x6y7z8` added the column and nothing ever declared it, so it was
    #: structurally unreachable rather than merely unread.
    #:
    #: It carried `server_default=false` on an already-populated table, so every
    #: product asserted "we do not make this" without anyone deciding it. Measured
    #: in production 2026-10-03: 33 rows, ZERO true. Wilbert's model is licensed
    #: local manufacture, so most licensees POUR — the tenant tier defaulted to the
    #: uncommon answer, and the only tenant available to check it against reality
    #: (Sunnycrest, which buys) is the exception that made it look right.
    #:
    #: r196 dropped the default and nulled every row. It is populated at
    #: onboarding, by asking the licensee which products they make.
    is_manufactured: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    #: ⚠️ THE LINK FROM A TENANT PRODUCT TO ITS PLATFORM DEFINITION, added by
    #: r186 and NOT declared here until 2026-10-03. The column existed with no
    #: ORM attribute, so nothing could resolve through it — and the whole
    #: platform-catalog design turns on that resolution.
    #:
    #: NULL means TENANT OWNERSHIP: the product was authored by the tenant and has
    #: no platform definition. It is an ABSENCE, not a third ownership value —
    #: r186 declares `_OWNERSHIP = ("wilbert", "licensee_common")` and notes that a
    #: third value would let a row claim tenant ownership while pointing at a
    #: platform variant, which is a state with no meaning.
    #:
    #: ⚠️ `assert_no_schema_drift` DID NOT AND CANNOT CATCH THIS. It is model→DB
    #: only, and its own docstring declares DB-extra columns to be noise — so every
    #: column a migration adds and nobody declares is invisible to it by design.
    #: Three more such columns remain on this table; see
    #: `docs/investigations/2026-10-03-price-list-reconciliation.md` §1.
    variant_template_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("product_variant_templates.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

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
