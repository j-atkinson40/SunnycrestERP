"""One row per act of deferring a prompt. APPEND-ONLY.

Per DECISIONS 2026-09-04 ("Prompts leave the note by resolution or dated
deferral, never silently"): a prompt has no dismiss. It leaves by its declared
end transition occurring, or by the reader naming a date to see it again.

──────────────────────────────────────────────────────────────────────────
WHY APPEND-ONLY RATHER THAN ONE MUTABLE ROW PER IDENTITY

"Deferred three times" is the only signal that would reveal a badly designed
prompt — someone repeatedly pushing something is usually blocked on something
else. A mutable row would overwrite that history on the second deferral and the
count would have to be maintained as a number, which is a thing that can drift
from the acts it claims to summarise.

So the count is `SELECT count(*)` over the acts. The record of what someone
chose NOT to do is often more informative than the record of what they did, and
it is only a record if each act survives the next one.

⚠️ NO UNIQUE CONSTRAINT ON THE IDENTITY, DELIBERATELY — and that is the
opposite of `note_fragment_renders`, which refuses a second render of the same
identity on the same note. There, a second row is a bug. Here, a second row is
the second deferral. The two tables encode different claims about what
repetition means.

──────────────────────────────────────────────────────────────────────────
WHAT THE SNAPSHOT IS FOR

`condition_digest` is taken at the moment of deferral, over the same
`condition_inputs` the composition gate digests. Deferral does not survive
material change: the reader deferred a decision with a KNOWN SHAPE, and if the
shape changes the deferral was made about a different question.

The digest is computed by `composition.change_digest`, not re-implemented here.
Two digests of the same inputs must be the same value or the wake is nonsense.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NoteFragmentDeferral(Base):
    __tablename__ = "note_fragment_deferrals"
    __table_args__ = (
        #: The read path: "is this identity deferred right now, and how often
        #: has it been?" Both questions are the same scan.
        Index(
            "ix_note_fragment_deferrals_lookup",
            "user_id", "fragment_id", "instance_key", "deferred_at",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    #: Tenant scope on the row itself. NOT NULL from the start — new table, no
    #: existing writer, so r176's expand/contract sequencing does not apply.
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
    )
    #: ⚠️ THE ACTOR, AND IT IS NEVER NULL. The note surface is the writer of
    #: this row and the acting user is on the request, so a deferral record can
    #: always say who deferred. That is not true of every event in the platform
    #: — `agent_anomalies.resolved_by` is correctly NULL for machine
    #: resolutions — which is exactly why this one is required rather than
    #: nullable: there is no machine path to deferral.
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )

    fragment_id: Mapped[str] = mapped_column(String(100), nullable=False)
    #: `EmittedFragment.instance_key` — "{fragment_id}:{subject_kind}:{subject_id}".
    #: 255 to match `note_fragment_renders`; subjects are composites, not UUIDs.
    instance_key: Mapped[str] = mapped_column(String(255), nullable=False)

    #: The note the deferral was made FROM. The record lands on the live note.
    daily_note_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("daily_notes.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    deferred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    #: ⚠️ A DATE, NOT A TIMESTAMP. "Presets plus a date picker, no finer
    #: granularity" is enforced by the column type rather than by validation —
    #: an unexpressible 3:15pm deferral needs no guard.
    deferred_until: Mapped[date] = mapped_column(Date, nullable=False)

    #: Which affordance produced this date. Recorded so "everyone picks
    #: tomorrow" is answerable without inferring it from the dates.
    preset: Mapped[str] = mapped_column(String(20), nullable=False)

    #: Snapshot of the condition inputs at the moment of deferral.
    condition_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    #: What the digest was computed FROM. Without this a deferral that keeps
    #: waking is indistinguishable from a world that keeps moving.
    condition_inputs: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Set when divergence woke this deferral. A woken deferral is spent: it
    #: stops suppressing, and it stays as the record that it existed.
    woken_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
