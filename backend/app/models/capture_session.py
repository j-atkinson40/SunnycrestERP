"""An order being captured by typing, between requests.

⚠️ E2 (2026-10-07): ITS OWN TABLE, NOT SYNTHETIC CALL-LOG ROWS. The call path persists
to `ringcentral_call_extractions`, which requires a `call_log_id` FK
(`ringcentral_call_extraction.py`), so reusing it for a typed order would mean writing a
fake phone call into the call log for every order someone types. The call log is an
operational record of calls that happened.

⚠️ `typed_lines` IS THE RECORD OF WHAT WAS SAID, AND `values` IS WHAT WAS UNDERSTOOD.
Both are kept, deliberately. `values` alone would lose the director's words the moment
the extractor improved, and the lines are the only evidence of what a future extractor
should have understood — including the lines it did not understand at all.

⚠️ NO ORDER IS WRITTEN FROM THIS TABLE IN THIS SLICE. E5 ends the slice at a read-only
summary. There is deliberately no `sales_order_id` column and no `approved_at`: adding
them would declare an intention the slice does not carry out, and the next reader would
take their presence as evidence the write path exists.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

#: The stages a typed capture moves through. ⚠️ `review` is as far as this slice goes.
STATUS_CAPTURING = "capturing"
STATUS_REVIEW = "review"
STATUS_ABANDONED = "abandoned"
#: ⚠️ TERMINAL, AND THE ONLY STATUS THAT MEANS A SALES ORDER EXISTS. Paired with
#: `sales_order_id`: `approved` without the link, or the link without `approved`,
#: is a half-written approval and `approve()` sets both inside one transaction.
STATUS_APPROVED = "approved"
CAPTURE_STATUSES: tuple[str, ...] = (
    STATUS_CAPTURING,
    STATUS_REVIEW,
    STATUS_ABANDONED,
    STATUS_APPROVED,
)


class CaptureSession(Base):
    __tablename__ = "capture_sessions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    #: ⚠️ `company_id` NOT `tenant_id`. CLAUDE.md §5 records that this codebase uses
    #: both names and that assuming one costs a probe; `companies.id` is the FK target
    #: and `company_id` is what every tenant-scoped table here calls it.
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    #: ⚠️ WHOSE SESSION. Tenant scoping alone is not enough — two users in one tenant
    #: must not see each other's half-typed orders, and the read endpoint filters on
    #: both. `ondelete=CASCADE` matches `company_id`: see CLAUDE.md §5 on a second FK
    #: over the same parent REVOKING the first one's cascade by taking NO ACTION.
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    #: The capture template this session is against — `capture.SALES_ORDER` today.
    #: Stored rather than assumed so a second object type is a value, not a migration.
    object_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=STATUS_CAPTURING
    )

    #: ⚠️ AN ORDERED LIST OF WHAT WAS TYPED, APPEND-ONLY. A JSONB array of
    #: `{"line": str, "at": iso8601}`. Order is the array's order; there is no
    #: sequence column, because a line's position IS its index and a second
    #: representation of the same fact can disagree with the first.
    typed_lines: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    #: field_id -> value, as understood so far. The input to `capture.evaluate`.
    values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    #: ⚠️ TEXT THE EXTRACTOR COULD NOT PLACE, CARRIED ACROSS REQUESTS. Without this the
    #: pane would lose its "not understood" rows on a reload, and the whole point of
    #: E1's never-dropped rule is that the director can see them.
    unrecognized: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    #: Ambiguous resolutions awaiting a numbered pick.
    pending_picks: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    #: ⚠️ THE WHOLE TYPED TEXT, AND IN THE TYPED PANE IT IS THE SOURCE. Typed capture
    #: re-reads this from scratch on every pause rather than appending — so deleting a
    #: word un-captures what it said, which is the behaviour a bar the director can
    #: edit has to have. `typed_lines` is kept alongside as history: it is what the
    #: CALL pipeline still produces, and it is all a session captured before r208 has.
    #:
    #: ⚠️ NULL IS NOT THE EMPTY STRING HERE. NULL means "this session has no whole-text
    #: record" — true of every row that predates r208 — and "" means the director
    #: cleared the bar. `read_state` branches on `is not None`, never on truthiness.
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: ⚠️ field_id -> the value the director CHOSE, and it outranks re-extraction.
    #: Without this, every re-read would raise a settled question again on the next
    #: keystroke: the text that was ambiguous is still on screen and still ambiguous.
    #: Applied LAST, after extraction. Durable, so a reload restores the picks too.
    resolutions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    #: ⚠️ VALUES CHOSEN FOR THE DIRECTOR, EACH WITH ITS ONE ALTERNATIVE. A switch is
    #: NOT a pick: the field is captured and the order can be completed without
    #: touching it. Ruled 2026-10-13 for a vault ambiguous only by form — the burial
    #: vault is taken and the urn vault offered, because a pick there asks a question
    #: the office already knows the answer to.
    #:
    #: ⚠️ NULLABLE, NO DEFAULT IN EITHER LAYER. A non-null value would assert
    #: something about every session row that predates r209, and nothing measured one.
    switches: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    #: The sales order this session was approved into. ⚠️ NULLABLE AND WITHOUT A
    #: MODEL DEFAULT — a session that has not been approved has not established an
    #: order, which is different from having none. Reading it inside the approving
    #: transaction is what makes a double click produce ONE order.
    sales_order_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sales_orders.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        # ⚠️ THE READ PATH'S INDEX, AND IT IS COMPOSITE FOR THE REASON THE READ PATH
        # FILTERS ON BOTH. An index on company_id alone would serve a query that
        # another tenant's user could also satisfy.
        Index("ix_capture_sessions_company_user", "company_id", "user_id"),
    )
