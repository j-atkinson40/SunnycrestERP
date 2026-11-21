"""Recording a copy that left, and telling a reader whether it is still true.

Three jobs, and the third is the one worth the table:

  * **record** a copy, freezing its data and stamping who/when/how;
  * **list** the copies of one document, newest first, area-filtered;
  * **say whether today's figures still match** the copy — which is what
    turns "a form was printed in December" into "the form that was printed in
    December no longer says what the data says".
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.outgoing_copy import LEFT_AS, OutgoingCopy
from app.services.outgoing_copies.registry import kind_for


class OutgoingCopyError(ValueError):
    """A copy could not be recorded as asked."""


def record_copy(
    db: Session,
    *,
    tenant_id: str,
    document_kind: str,
    subject: str,
    content: dict,
    left_as: str,
    made_by_user_id: str | None,
    sent_how: str | None = None,
    email_to: str | None = None,
) -> OutgoingCopy:
    """Freeze a copy of a document as it leaves.

    ⚠️ **THE CALLER SUPPLIES THE CONTENT IT ACTUALLY SHOWED.** This does not
    recompute the document — recomputing it here would freeze what the data
    says NOW, not what the page said, and the difference between those two is
    the entire reason for the record.
    """
    if left_as not in LEFT_AS:
        raise OutgoingCopyError(
            f"{left_as!r} is not a way a document can leave; expected one of "
            f"{list(LEFT_AS)}"
        )
    if left_as == "marked_sent" and not (sent_how or "").strip():
        raise OutgoingCopyError(
            "marking a document sent requires saying HOW it was sent — "
            "'sent' with no method is a claim nobody can follow up, which is "
            "the whole value of recording it."
        )
    if sent_how and left_as != "marked_sent":
        raise OutgoingCopyError(
            f"sent_how belongs to marked_sent, not to {left_as!r}"
        )
    if (email_to is None) != (left_as != "emailed"):
        raise OutgoingCopyError(
            "email_to is required for emailed and refused for everything else"
        )
    if not content:
        # ⚠️ An empty copy is worse than no copy: it records that something
        # left and loses what it said, which is the one thing the row exists
        # to keep.
        raise OutgoingCopyError(
            "a copy with no content records that a document left and loses "
            "what it said"
        )

    spec = kind_for(document_kind)
    copy = OutgoingCopy(
        tenant_id=tenant_id,
        document_kind=spec.kind,
        subject=subject,
        content=content,
        renderer=spec.renderer,
        renderer_version=spec.renderer_version,
        made_by_user_id=made_by_user_id,
        made_at=datetime.now(timezone.utc),
        left_as=left_as,
        sent_how=(sent_how or "").strip() or None,
        email_to=email_to,
    )
    db.add(copy)
    db.flush()
    return copy


def copies_for(db: Session, *, tenant_id: str, document_kind: str,
               subject: str) -> list[OutgoingCopy]:
    """Every copy of one document, newest first.

    ⚠️ **THE AREA CHECK IS NOT HERE.** It belongs at the boundary, where the
    caller's grants are known; a service that took grants would be a second
    place the rule lives. The route applies `registry.readable_kinds`, and
    `tests/test_outgoing_copies.py` holds the route to it.
    """
    kind_for(document_kind)  # refuse an unregistered kind even on read
    return (
        db.query(OutgoingCopy)
        .filter(OutgoingCopy.tenant_id == tenant_id,
                OutgoingCopy.document_kind == document_kind,
                OutgoingCopy.subject == subject)
        .order_by(OutgoingCopy.made_at.desc())
        .all()
    )


def _comparable(content: dict) -> Any:
    """What two versions of a document are compared ON.

    ⚠️ **THE FIGURES, NOT THE WHOLE PAYLOAD.** A copy carries the header too,
    and a header holds `completed_by` and the plant — change the person who
    signs the form and every past copy would suddenly "differ from today's
    figures", which is false and would train the reader to ignore the notice.

    Lines only, as `(number, key, value, blank)`. Labels and rates are
    excluded for the same reason: re-wording a label does not change what the
    form claims.
    """
    out = []
    for line in content.get("lines") or []:
        out.append((line.get("number"), line.get("key"),
                    line.get("value"), bool(line.get("blank"))))
    return out


def differs_from(copy: OutgoingCopy, current: dict) -> bool:
    """Do today's figures disagree with what this copy says?

    Returns False when the copy carries no comparable lines — an honest
    "cannot tell" rather than a confident "no". ⚠️ A copy frozen by an older
    renderer may not be comparable at all; `renderer_version` is stamped so a
    future reader can tell, and this function does not pretend otherwise.
    """
    frozen = _comparable(copy.content or {})
    if not frozen:
        return False
    return frozen != _comparable(current or {})


def shape(copy: OutgoingCopy, *, current: dict | None = None,
          made_by_name: str | None = None) -> dict:
    """One copy, as a screen needs it.

    The WORDING is the client's; this serves the facts it needs to word
    honestly — including `left_as`, which is what separates "printed, where it
    went after isn't known" from "marked sent, mailed with check 4521".
    """
    return {
        "id": copy.id,
        "document_kind": copy.document_kind,
        "subject": copy.subject,
        "left_as": copy.left_as,
        "sent_how": copy.sent_how,
        "email_to": copy.email_to,
        "email_status": copy.email_status,
        "made_at": copy.made_at.isoformat() if copy.made_at else None,
        "made_by_user_id": copy.made_by_user_id,
        "made_by_name": made_by_name,
        "renderer": copy.renderer,
        "renderer_version": copy.renderer_version,
        #: ⚠️ `null` WHEN THERE IS NOTHING TO COMPARE AGAINST, never `false`.
        #: A caller that did not supply today's figures has not established
        #: that they match, and "no difference" is a different claim from
        #: "not checked".
        "differs_from_today": (None if current is None
                               else differs_from(copy, current)),
    }
