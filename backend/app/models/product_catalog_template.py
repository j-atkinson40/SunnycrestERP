import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProductCatalogTemplate(Base):
    __tablename__ = "product_catalog_templates"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    preset: Mapped[str] = mapped_column(String(30), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sku_prefix: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    default_unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    #: ⚠️ NULL IS "NOT ESTABLISHED", NOT "we do not make this". r196 dropped the
    #: server default (`true`) AND the SQLAlchemy-level `default=True` that used to
    #: sit here — a two-sided default where fixing only the database half would
    #: have left every ORM-created row still asserting True.
    #:
    #: ⚠️ EXISTING ROWS WERE NOT NULLED, deliberately. Their values VARY (15 true /
    #: 10 false on bridgeable_dev) because `catalog_template_seeder` writes True for
    #: Burial Vaults, True for Urn Vaults and False for Cemetery Equipment — vaults
    #: are poured, cemetery equipment is bought. Those are decisions, not a fill,
    #: and CLAUDE.md §5's rule is aimed at values written UNIFORMLY.
    is_manufactured: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
