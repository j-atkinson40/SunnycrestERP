"""The controlled set of product lines — the `verticals` lookup shape.

CLAUDE.md §5 requires a controlled reference to be a slug-keyed lookup table with
a real foreign key, not a String column with a convention. `product_categories`
could not serve: it is `company_id NOT NULL`, so a platform-level family cannot
live there without changing what every existing row means.

A LOOKUP TABLE, NOT A LEVEL OF THE HIERARCHY. The hierarchy is
product_templates -> product_variant_templates. A family is an attribute of a
template, and it exists as a table so that a report slice by product line groups
correctly — free text splits "Triune" from "triune" silently and the grouping is
wrong with nothing raised.
"""
import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProductFamily(Base):
    __tablename__ = "product_families"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_product_families_status",
        ),
    )

    slug: Mapped[str] = mapped_column(String(32), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    #: Wilbert discontinues lines, so a family needs a lifecycle rather than a
    #: delete — a discontinued family still has history pointing at it.
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="published")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
