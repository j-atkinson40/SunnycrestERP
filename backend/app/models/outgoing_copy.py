"""A copy of a document that left Bridgeable, and how it left.

⚠️ **THE POINT IS THE COPY, NOT THE EVENT.** An audit row saying "Susan printed
the R-115 on Dec 3" tells you something happened and not what was on the page.
This freezes the CONTENT, so a month reopened in March can be compared against
what was actually sent — and `payroll_union_forms_r115` already carries the
same reasoning for its own stored table: recomputing a filed month gives a
different answer as soon as an overlapping register is imported.

### What "frozen" means here, and what it does not

`content` holds the document's **exact data** plus the `renderer` and
`renderer_version` that turned it into a page — not the rendered bytes. That is
a deliberate limit, not an oversight:

  * there is no PDF pipeline and no object storage in this path; the R-115
    print view is the browser printing HTML, so there are no bytes to keep;
  * data plus a renderer version reproduces the page as long as that renderer
    version still exists, and says which one it needs when it does not.

⚠️ So a copy is **reproducible, not byte-identical**. A reader comparing a
reprint against the paper in the file should expect the same figures, not the
same pixels. When a real PDF renderer lands, bytes get their own column beside
this one rather than replacing it — the data is what makes a copy comparable
against today's figures, which bytes cannot do.

### How it left

Four modes, and only two have a producer today:

    printed       the print view was opened        <- R-115, this round
    marked_sent   somebody recorded sending it     <- R-115, this round
    downloaded    a file was saved                 no producer yet
    emailed       sent from Bridgeable             no producer yet

⚠️ **TWO OF THESE ARE DECLARED AND UNFED, AND THAT IS THE DANGEROUS PART.**
CLAUDE.md §11 names the shape: complete machinery behind an unprovisioned
entrance, where every read site works and nothing produces the input. An empty
`emailed` set does NOT mean no emails were sent — it means Bridgeable has never
been able to send one. Anything reporting on these modes states that, or it is
asserting an absence it has not measured.

⚠️ **AND `printed` MEANS THE PRINT VIEW WAS OPENED.** A browser cannot confirm
that paper came out, so the record says what it knows and the wording on screen
says the rest: *where it went after isn't known*. Recording "printed" as though
it were a delivery would be the strongest claim in the file resting on the
weakest evidence in it.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


#: How a copy left. ⚠️ A CLOSED SET, checked in the database as well as here —
#: a mode nobody can name is a mode no screen can word honestly.
LEFT_AS = ("printed", "downloaded", "emailed", "marked_sent")

#: The modes a producer exists for today. Named so a reader can tell a mode
#: that has never fired from one that fired and found nothing.
LEFT_AS_WITH_PRODUCERS = ("printed", "marked_sent")


class OutgoingCopy(Base):
    """One copy of one document, as it was when it left."""

    __tablename__ = "outgoing_copies"
    __table_args__ = (
        CheckConstraint(
            "left_as IN ('printed', 'downloaded', 'emailed', 'marked_sent')",
            name="ck_outgoing_copy_left_as",
        ),
        # ⚠️ **THE PER-MODE FIELDS BELONG TO THEIR MODE, ENFORCED.** Without
        # this a `printed` row can carry an email address and a `marked_sent`
        # row can carry a delivery status, and every reader then has to guess
        # whether the field means anything. The constraint makes the
        # nonsensical row unwritable rather than merely unexpected.
        CheckConstraint(
            "(left_as = 'emailed') = (email_to IS NOT NULL)",
            name="ck_outgoing_copy_email_to_only_when_emailed",
        ),
        CheckConstraint(
            "left_as = 'marked_sent' OR sent_how IS NULL",
            name="ck_outgoing_copy_sent_how_only_when_marked_sent",
        ),
        Index("ix_outgoing_copy_tenant_kind_subject",
              "tenant_id", "document_kind", "subject"),
        Index("ix_outgoing_copy_tenant_made_at", "tenant_id", "made_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    #: What kind of document this is — "r115" today. Maps to an AREA, which is
    #: what decides who may see the copy; see `outgoing_copies.registry`.
    document_kind: Mapped[str] = mapped_column(String(32), nullable=False)

    #: What it is ABOUT, in the kind's own terms: "2026-10" for an R-115
    #: period. Opaque to this table on purpose — a column that tried to be a
    #: period and an invoice number and a case id would be none of them.
    subject: Mapped[str] = mapped_column(String(64), nullable=False)

    #: The frozen data. See the module docstring on what frozen means here.
    content: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    renderer: Mapped[str] = mapped_column(String(64), nullable=False)
    renderer_version: Mapped[str] = mapped_column(String(16), nullable=False)

    #: ⚠️ NULLABLE, and null means "not established" rather than "the system".
    #: A copy made by a scheduled job would carry null here today, and a
    #: reader must not read that as nobody having been involved.
    made_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    made_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now,
    )

    left_as: Mapped[str] = mapped_column(String(16), nullable=False)

    #: `marked_sent` only — "mailed with check 4521". The whole value of the
    #: mode: "sent" without how is a claim nobody can follow up.
    sent_how: Mapped[str | None] = mapped_column(String(200), nullable=True)

    #: `emailed` only. No producer yet — see the module docstring.
    email_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
