"""The rulebook: sentences the office wrote, drafted from a change they explained.

James's dispatch of 2026-10-26, "Opas asks why?", first slice.

⚠️ NOTHING READS THIS YET, AND THAT IS THE DESIGN RATHER THAN AN UNFINISHED EDGE.
"nothing uses the rulebook in this slice. It records and shows, and the model starts
reading it in the next step. I'd rather the first rules be ones you've seen go in"
(James, 2026-10-26). The pane says so in its own footer, so the office is not left to
infer that a rule they can see is a rule that is acting.

⚠️ THIS IS AN UNPROVISIONED-ENTRANCE SHAPE HELD DELIBERATELY, which CLAUDE.md §11 says
to name rather than discover later. Normally a table with writers and no readers is the
defect; here the reader is the next slice and the absence is stated in three places —
this docstring, the pane's footer, and the dispatch. What would make it the defect is the
footer going away while the reader still does not exist.

⚠️ AND `text` IS A SENTENCE, NOT A STRUCTURE. A schema for conditions and actions would
be a guess about a rule engine nobody has written; the sentence is what the office
confirmed, word for word, and it is what the model will be shown next. When the engine
arrives it can add columns beside this one rather than reinterpreting it.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    text as sa_text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class OpasRule(Base):
    __tablename__ = "opas_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    #: The one plain sentence, as the office confirmed it.
    text: Mapped[str] = mapped_column(Text, nullable=False)
    #: The decision this rule came from, so the pane can link to that order.
    #:
    #: ⚠️ `SET NULL`, NOT `CASCADE`. The rule outlives its provenance: a rule whose log
    #: row was purged is still a rule the office wrote, and deleting it because the log
    #: was tidied would let the log decide what the rulebook says.
    source_decision_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("opas_decisions.id", ondelete="SET NULL"), nullable=True,
    )
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc), server_default=sa_text("now()"),
    )
    #: Switched off rather than deleted, so the pane can say a rule was withdrawn.
    #:
    #: ⚠️ SAFE AS NOT NULL BECAUSE THE TABLE IS NEW. CLAUDE.md §5's trap needs rows that
    #: already exist for a default to mis-describe; there are none.
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=sa_text("true"),
    )
