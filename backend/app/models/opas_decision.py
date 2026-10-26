"""One row per Opas bar interpretation. The evidence the rulebook will come from.

⚠️ READ-MOSTLY AND APPEND-ONLY IN SPIRIT. Rows are written once and updated once at most
— when an `asked` question is resolved. Nothing deletes them: a phrasing the bar got
wrong in October is exactly what a test set written in November needs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
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


#: Who produced the request.
PROPOSED_BY = ("rules", "model", "rulebook")
#: What happened to it immediately.
OUTCOMES = ("executed", "asked", "refused")
#: What became of a question that was asked.
RESOLUTIONS = ("answered", "replaced", "cancelled")

#: Where the bar was when the phrase was typed.
#:
#: ⚠️ IT IS PART OF THE REQUEST, NOT METADATA. "only hopkins" is a refinement with a list
#: open and nothing at all in a cold bar; a log that could not tell them apart would
#: produce a test set whose cases have no single right answer.
SURFACES = ("bar", "bar_with_list", "bar_with_order", "catalog")


class OpasDecision(Base):
    __tablename__ = "opas_decisions"
    __table_args__ = (
        CheckConstraint(
            "proposed_by IN ('rules', 'model', 'rulebook')",
            name="ck_opas_decisions_proposed_by",
        ),
        CheckConstraint(
            "outcome IN ('executed', 'asked', 'refused')",
            name="ck_opas_decisions_outcome",
        ),
        CheckConstraint(
            "resolution IS NULL OR resolution IN ('answered', 'replaced', 'cancelled')",
            name="ck_opas_decisions_resolution",
        ),
        CheckConstraint(
            "proposed_by <> 'model' OR model_accepted IS NOT NULL",
            name="ck_opas_decisions_model_has_verdict",
        ),
        CheckConstraint(
            "reason_scope IS NULL OR reason_scope IN ('today', 'always', 'skipped')",
            name="ck_opas_decisions_reason_scope",
        ),
        #: ⚠️ ONE-DIRECTIONAL ON PURPOSE. A reason with no scope is a half-answered
        #: question that would read as a deliberate record; a SCOPE with no reason is
        #: exactly what a skip is.
        CheckConstraint(
            "reason IS NULL OR reason_scope IS NOT NULL",
            name="ck_opas_decisions_reason_has_scope",
        ),
        Index("ix_opas_decisions_company_created", "company_id", "created_at"),
        Index(
            "ix_opas_decisions_misses",
            "company_id",
            "created_at",
            postgresql_where=__import__("sqlalchemy").text("outcome = 'refused'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
    )
    actor_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now,
    )
    #: ⚠️ VERBATIM. See the migration — a normalised copy would be the rules' view of the
    #: phrase rather than the person's, and the rules' view is what we are improving.
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    surface: Mapped[str] = mapped_column(String(24), nullable=False, default="bar")
    proposed_by: Mapped[str] = mapped_column(String(16), nullable=False)
    proposed_request: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    resolution: Mapped[str | None] = mapped_column(String(16), nullable=True)
    resolved_option: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    #: ⚠️ THE MODEL'S NUMBERS LIVE HERE BECAUSE `proposal.py` CALLS INTELLIGENCE WITH
    #: `persist=False` — asking is a read, and an audit row would commit the caller's
    #: session. So there is no `intelligence_executions` row to point at, and tokens and
    #: cost are not recorded anywhere for this path. Latency and the verdict are what a
    #: non-persisting caller can observe.
    model_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_accepted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    model_refused_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)

    #: Why the person changed what Opas had filled in. Their own words.
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: `today` | `always` | `skipped`. NULL means they were never asked.
    #:
    #: ⚠️ NULL IS NOT 'skipped'. Every row written before 2026-10-26 was never asked
    #: anything, and recording those as skips would be a claim that somebody declined.
    reason_scope: Mapped[str | None] = mapped_column(String(8), nullable=True)
    #: The one change asked about — field, and the values either side of it.
    changed_field: Mapped[str | None] = mapped_column(String(40), nullable=True)
    changed_from: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_to: Mapped[str | None] = mapped_column(Text, nullable=True)
