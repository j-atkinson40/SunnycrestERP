"""Vertical model — first-class registry for platform verticals.

Verticals-lite precursor arc. The `verticals` table is the canonical
first-class registry for platform verticals (today expressed as
scattered `vertical` String(32) columns across 16+ tables). Going
forward, any new column referring to a vertical must reference
`verticals.slug` as a foreign key. The existing String columns are
preserved for backward compatibility per CLAUDE.md §5 schema
patterns.

See migration `r92_verticals_table` for the upgrade path + seeded
canonical rows.

Status enum:
    'draft'      — vertical authored but not yet published
    'published'  — visible to operators (canonical default)
    'archived'   — retired vertical, excluded from default lists
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


STATUS_DRAFT = "draft"
STATUS_PUBLISHED = "published"
STATUS_ARCHIVED = "archived"

VALID_STATUSES: tuple[str, ...] = (
    STATUS_DRAFT,
    STATUS_PUBLISHED,
    STATUS_ARCHIVED,
)


class Vertical(Base):
    """Canonical platform vertical registry row.

    Slug is the immutable identifier (matches the convention used by
    existing String(32) `vertical` columns scattered across the
    schema; future FK migrations will reference `verticals.slug`).
    """

    __tablename__ = "verticals"

    slug: Mapped[str] = mapped_column(String(32), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=STATUS_PUBLISHED
    )
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="ck_verticals_status",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Vertical(slug={self.slug}, display_name={self.display_name!r}, "
            f"status={self.status}, sort_order={self.sort_order})>"
        )
