"""A past-tense record on a settled note. Generated once; never re-worded.

Per DECISIONS 2026-09-04 ("The note has a live phase and a settled phase"): at
the settling hour, consumed prompts are replaced by past-tense records of the
action taken. The past-tense form is a DISTINCT fragment generated from events
that occurred — not the live fragment relabelled.

──────────────────────────────────────────────────────────────────────────
⚠️ ONE ROW PER (NOTE, IDENTITY, OUTCOME), AND THE OUTCOME IS PART OF IT

A prompt can end more than one way on the same day. Three tasks due today: two
done, one cancelled. That is TWO records — "you completed 2 tasks due today" and
"you cancelled 1 task due today" — not one row that has to pick.

The uniqueness therefore includes `outcome_key`. Keyed on the SUBJECT and the
outcome, never on the run: settling twice produces the same two rows, which is
the anomaly arc's rule applied to a job that fires on a */15 sweep and will
evaluate the same day many times.

⚠️ `text` AND `spans` ARE FROZEN AT GENERATION

A settled note that re-words itself is worse than one that says nothing. The
settled note is what "what did I decide Tuesday" reads, so its sentence is
written once and stored, not recomputed from a template that may change.

The spans are frozen for a second reason: links on a settled note carry THAT
note's date. A span re-serialised next week would resolve against next week's
world, which is a link quietly showing today's data under yesterday's sentence —
the worst available outcome for a surface whose premise is that links are
provenance marks.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NoteSettledRecord(Base):
    __tablename__ = "note_settled_records"
    __table_args__ = (
        UniqueConstraint(
            "daily_note_id", "fragment_id", "instance_key", "outcome_key",
            name="uq_note_settled_records_identity",
        ),
        Index(
            "ix_note_settled_records_lookup",
            "user_id", "note_date",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    daily_note_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("daily_notes.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    #: The tenant-local day this record belongs to.
    note_date: Mapped[date] = mapped_column(Date, nullable=False)

    fragment_id: Mapped[str] = mapped_column(String(100), nullable=False)
    instance_key: Mapped[str] = mapped_column(String(255), nullable=False)
    #: Which ENDING this record is about — matches an `Outcome.key` on the
    #: fragment's end transition, and the structured field the resolving act
    #: recorded. Never derived from prose.
    outcome_key: Mapped[str] = mapped_column(String(40), nullable=False)

    #: How many of this outcome occurred. Interpolated into the past tense.
    count: Mapped[int] = mapped_column(Integer, nullable=False)

    #: The sentence, frozen. Never regenerated.
    text: Mapped[str] = mapped_column(Text, nullable=False)
    #: The spans, frozen as JSON — see the module docstring on why re-serialising
    #: them later would be a link showing today's data under yesterday's sentence.
    spans: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: ⚠️ THE VISIBLE TIMESTAMP. The settled note is APPEND-ONLY, not immutable:
    #: an 11pm action lands in the correct day's summary even when settling has
    #: already run, and it arrives with a time so a reader can see it was added
    #: after the fact rather than silently rewriting the day.
    occurred_through: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
