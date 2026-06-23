"""Maps of Content — page model (Phase 1, migration r111).

An authored, artifact-first navigation page. `sections` is an ordered
JSONB array; each section holds an ordered array of typed
artifact-reference rows. The reference shape (validated/resolved in the
service, not enforced at the column level — JSONB stays flexible):

    section := {
        "section_id": str,
        "title": str,
        "description": str | None,
        "order": int,
        "rows": [ row, ... ],
    }
    row := {
        "row_id": str,
        "builder": str,        # one of the 4 wired builders
        "artifact_id": str,    # id in that builder's owning table
        "label": str,          # authored label (resolver refreshes/validates)
        "icon": str | None,
        "order": int,
    }

Three-tier scope shape (platform_default → vertical_default →
tenant_override); ships with the vertical tier populated, the tenant tier
empty-but-reachable. Actor columns are FK-less (cross-realm — a value may
be a tenant User id or a platform PlatformUser id).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MoCPage(Base):
    __tablename__ = "moc_pages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    # platform_default | vertical_default | tenant_override
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    vertical: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("verticals.slug"), nullable=True, index=True
    )
    tenant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=True, index=True
    )
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    sections: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, default=True
    )
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_now,
        onupdate=_now,
    )
