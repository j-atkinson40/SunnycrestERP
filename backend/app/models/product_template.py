"""The PLATFORM PRODUCT — one row per product-split-by-form.

Triune Burial Vault and Triune Urn Vault are two rows in one family. What lives
here is what is CONSTANT WITHIN a product, which is the whole reason the level
exists: all five Triune finishes share one weight and one set of dimensions, so a
corrected figure lands once instead of five times. That is the same argument as
products-as-reference, one level up.
"""
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

#: The five forms a product takes. Controlled because `form` is what splits one
#: family into rows, so a typo would silently create a sixth form.
FORMS = ("burial_vault", "urn_vault", "grave_liner", "infant", "equipment")

#: ⚠️ EXACTLY TWO VALUES. Tenant ownership is a `products` row whose
#: `variant_template_id` IS NULL — absence, not a third value. A third value here
#: would permit a row claiming tenant ownership while pointing at a platform
#: variant, which is a state with no meaning.
OWNERSHIP = ("wilbert", "licensee_common")


class ProductTemplate(Base):
    __tablename__ = "product_templates"
    __table_args__ = (
        CheckConstraint(
            "form IN ('" + "', '".join(FORMS) + "')",
            name="ck_product_templates_form",
        ),
        CheckConstraint(
            "ownership IN ('" + "', '".join(OWNERSHIP) + "')",
            name="ck_product_templates_ownership",
        ),
        Index("ix_product_templates_family", "family_slug"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    family_slug: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("product_families.slug", ondelete="RESTRICT"),
        nullable=False,
    )
    form: Mapped[str] = mapped_column(String(32), nullable=False)
    ownership: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reinforcement: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    #: ⚠️ NUMERIC INCHES, NOT STRINGS. Every figure on the licensee spec sheet is
    #: sixteenths-exact — 14-5/16 is exactly 14.3125 — so Numeric(8,4) is lossless
    #: and the casket-clearance check can do arithmetic. Rendering fractions is a
    #: presentation concern and does not belong in storage.
    inside_length_in: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    inside_width_in: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    inside_height_in: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    outside_length_in: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    outside_width_in: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    outside_height_in: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)

    #: ⚠️ Nullable on purpose and the nulls are KNOWN: the licensee spec sheet
    #: carries no weight for any urn vault, any Loved & Cherished, or any of the
    #: six non-manufactured vaults. A lift rating and a truck load depend on this
    #: number, so it is left absent rather than inferred from a sibling product.
    weight_lb: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    #: ⚠️ PHYSICAL CAPABILITY, NOT AVAILABILITY — two different layers. This is the
    #: set of r185 question ids the product can physically take. Whether a licensee
    #: OFFERS one lives in
    #: `wilbert_program_enrollments.personalization_config.availability`, ruled on
    #: separately (DECISIONS 2026-09-22). Capability BOUNDS availability; it does
    #: not replace it, and a question absent here cannot be offered by anyone.
    #: ⚠️ NULL IS NOT `[]`, AND r186 COULD NOT SAY SO. `[]` is a FINDING — this
    #: product physically takes no personalization. NULL is an ABSENCE — nobody
    #: has established what it takes. r186 shipped this NOT NULL with
    #: `default=list`, so all 21 rows read `[]` and asserted the finding by
    #: default for products the spec sheet says nothing about. r192 dropped NOT
    #: NULL and reset every row; r193 set the 15 the sheet covers.
    #:
    #: Same defect shape as `is_manufactured` in
    #: `docs/investigations/2026-10-02-platform-catalog-discrepancies.md` §4 — a
    #: NOT NULL column default read as a deliberate decision. Caught before a
    #: consumer trusted it rather than after.
    personalization_capability: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True
    )

    #: Where the figures came from and when. A spec Bridgeable asserts wrongly is
    #: discovered by a driver at a graveside with a family present, so the record
    #: carries its own provenance instead of relying on recall.
    #: Wilbert publishes these. The product image shows the shell; the
    #: variant image shows the finish — which is the Universal / Basic Gray
    #: case exactly: one product, two variant images.
    image_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    spec_source: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    spec_asof: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
