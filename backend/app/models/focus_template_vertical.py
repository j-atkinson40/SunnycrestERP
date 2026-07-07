"""FocusTemplateVertical — the multi-vertical homes join (r120).

One variation (a Tier 2 focus template), several vertical homes. The
template row's `vertical` column stays the HOME vertical; this join
carries the FULL set (home included — uniform reads, no special case).

SLUG-KEYED (not row-id-keyed): template version bumps mint new row ids,
so an id-keyed join would churn on every edit. `template_slug` is the
lineage's stable identity per the C-2.1.2 canon.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FocusTemplateVertical(Base):
    __tablename__ = "focus_template_verticals"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    template_slug: Mapped[str] = mapped_column(
        String(96), nullable=False, index=True
    )
    vertical: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("verticals.slug", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "template_slug",
            "vertical",
            name="uq_focus_template_verticals_slug_vertical",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<FocusTemplateVertical(slug={self.template_slug}, "
            f"vertical={self.vertical})>"
        )
