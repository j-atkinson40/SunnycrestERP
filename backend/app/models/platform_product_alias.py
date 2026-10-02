"""A platform-level alias: one alias text, N candidate variants.

`product_aliases` is `company_id NOT NULL` and cannot hold these. This table has
no tenant column because Wilbert's names are platform facts; a licensee's own
shorthand stays in `product_aliases`.
"""
import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

#: Where an alias came from. An alias with unknown provenance is one nobody can
#: later judge, so this is constrained rather than free text.
SOURCES = ("production_catalog", "spec_sheet", "wilbert_store", "manual")


class PlatformProductAlias(Base):
    __tablename__ = "platform_product_aliases"
    __table_args__ = (
        #: ⚠️ THE PAIR, NOT THE TEXT. Unique on alias text alone would force one
        #: winner per alias — the elimination-where-a-label-exists error that
        #: dropped a real product from r188's first draft. The schema must permit
        #: the ambiguity for the resolver to be able to report it.
        UniqueConstraint(
            "variant_template_id", "alias_text_normalized",
            name="uq_platform_product_aliases_variant_text",
        ),
        CheckConstraint(
            "source IN ('" + "', '".join(SOURCES) + "')",
            name="ck_platform_product_aliases_source",
        ),
        Index("ix_platform_product_aliases_normalized", "alias_text_normalized"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    #: Resolves to a VARIANT because that is the billable thing. Several rows
    #: sharing one normalized text is how "Veteran" names both a burial vault and
    #: an urn vault.
    variant_template_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("product_variant_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    alias_text: Mapped[str] = mapped_column(String(500), nullable=False)
    #: ⚠️ ALWAYS via `ImportAliasService._normalize_text`. It is a pure
    #: staticmethod over a string with no tenant scope, so one normalisation
    #: serves both alias tables; a second would drift invisibly.
    alias_text_normalized: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    #: Curated versus learned. Kept from `product_aliases` because a future
    #: Wilbert catalog import could propose aliases nobody has accepted yet.
    is_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
