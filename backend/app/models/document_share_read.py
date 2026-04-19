"""Per-user inbox read tracking for cross-tenant document shares.

Phase D-8 polish of D-6's DocumentShare model. Each admin tracks their
own unread inbox state — first-read wins; re-reading never un-marks.

Composite PK (share_id, user_id). No surrogate id, no separate index
on share_id (PK covers it). Extra index on user_id for the common
"mark all read" / "get my read set" queries.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class DocumentShareRead(Base):
    __tablename__ = "document_share_reads"

    share_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_shares.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    read_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentShareRead share={self.share_id[:8]} "
            f"user={self.user_id[:8]} at={self.read_at.isoformat()}>"
        )
