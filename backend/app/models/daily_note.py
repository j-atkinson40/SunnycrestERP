"""The note's identity — one per user per day.

Per DECISIONS 2026-09-04 ("Monitor is a daily note, not a dashboard"): scope is
one note per user per day, NOT one per Space. Space selection is a filter on
which fragments appear, never a separate surface, which is why `space_id` is
absent from this model rather than nullable.

`note_date` is a date in the TENANT's local day. The tenant-configured settling
hour (session 4) moves where that boundary falls; it does not change the
identity, which is what lets "the note for 2026-09-04" stay answerable.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DailyNote(Base):
    __tablename__ = "daily_notes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    note_date: Mapped[date] = mapped_column(Date, nullable=False)

    #: Session 4 sets this at the tenant's settling hour. Present now because
    #: the day identity that will settle must exist now.
    settled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @property
    def subject_id(self) -> str:
        """The `user_day` subject the fragment contract already declares.

        `tasks_due_today` declares `subject_kind="user_day"` and builds exactly
        this string. Exposed here so the two cannot drift into two spellings of
        one key — which is the `complete`/`completed` failure, prevented rather
        than named.
        """
        return f"{self.user_id}:{self.note_date.isoformat()}"
