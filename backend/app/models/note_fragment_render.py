"""What a note actually SAID, per identity — the composition gate's memory.

⚠️ THIS EXISTS SO A NON-PROMPT CAN BE WITHHELD. Per the session-2 dispatch, a
non-prompt renders only on CHANGE against the previous note's state for that
IDENTITY. "The same true thing, unchanged" is only expressible if something
remembers what was said and what it was said about, and `daily_notes` records
that a day existed, not what it contained.

⚠️ AND IT IS ONLY IMPLEMENTABLE BECAUSE IDENTITY EXISTS. The key stored here is
`EmittedFragment.instance_key`, derived from the declared subject and never from
the evaluation. A run-scoped key would make every day's evaluation a new
identity, every non-prompt would look new, and the gate would pass everything
through while appearing to work. That is the defect the anomaly arc closed one
layer down, and this table is the first consumer that depends on it being closed.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime, ForeignKey, Index, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NoteFragmentRender(Base):
    __tablename__ = "note_fragment_renders"
    __table_args__ = (
        # One record per identity per note. A second render of the same
        # identity on the same note is a bug, not a second occurrence, so it
        # is refused rather than accumulated -- the anomaly arc's lesson
        # applied at declaration time instead of after 1,825 rows.
        UniqueConstraint(
            "daily_note_id", "fragment_id", "instance_key",
            name="uq_note_fragment_renders_identity",
        ),
        # The gate's read path: "what did this user last say about this
        # identity?" ordered by note date.
        Index(
            "ix_note_fragment_renders_lookup",
            "user_id", "fragment_id", "instance_key", "note_date",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    daily_note_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("daily_notes.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    #: Denormalised so the gate's lookup does not join daily_notes, and so a
    #: tenant scope exists on the row itself. NOT NULL from the start: this is
    #: a new table with no existing writer, so the expand/contract sequencing
    #: r176 needed does not apply -- there is no old code to break.
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    #: Denormalised from the note for the ordering the gate reads on.
    note_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    fragment_id: Mapped[str] = mapped_column(String(100), nullable=False)
    #: `EmittedFragment.instance_key` -- "{fragment_id}:{subject_kind}:{subject_id}".
    #: 255 rather than 36: subjects are composites now, not UUIDs. r176 widened
    #: `agent_anomalies.entity_id` for exactly this reason after a phase-2 subject
    #: landed at 36 characters exactly.
    instance_key: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)

    #: A stable digest of the state the change test compares. NOT the prose:
    #: wording must be stable across refreshes, so comparing wording would make
    #: the gate depend on the synthesiser rather than on the world.
    change_digest: Mapped[str] = mapped_column(String(64), nullable=False)

    #: Kept for diagnosis: what the digest was computed FROM. A digest that
    #: never matches is indistinguishable from a world that keeps changing
    #: unless the inputs are recoverable.
    change_inputs: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
