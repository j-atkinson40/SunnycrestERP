"""Write one row per bar interpretation. Never break the request to do it.

James's dispatch of 2026-10-20, step 4. The log is the evidence the rulebook will come
from, and it is how the test set grows: the 59 phrasings scored on 2026-10-20 were
drafted from the repo's own tests and alias tables — the half the rules were written for.
`input_text` is what somebody actually typed.

⚠️ A LOGGING FAILURE MUST NEVER COST AN ANSWER, and that is the one hard rule here.
Every function in this module swallows its own exceptions and returns `None`. A director
asking "what's going out Friday" must get the answer whether or not the row landed —
which is also why the write happens AFTER the answer has been computed.

⚠️ IT IS CALLED FROM THE ROUTE, NOT FROM `ask`. `ask` is reached by the probes and
scripts that verify production behaviour under a read-only guard, and a write inside it
would make those raise. The route is a POST and owns the commit.

⚠️ WHAT IS AND IS NOT COVERED, stated because "one row per bar interpretation" sounds
total and this is two endpoints:

    /order-list/ask       covered — every list question, every order opened by name or
                          number, and every phrase the rules decline
    /catalog-pane/resolve covered — every product phrase, including the ones that match
                          nothing, which is the typo surface
    capture               NOT covered here, and already recorded: the whole typed
                          sentence is `capture_sessions.full_text`, which is where the
                          8 production phrasings in the test set came from
    context phrases       NOT covered. `context-phrases.ts` is an exact 35-entry table;
                          a hit teaches nothing and a miss never reaches the server
    "close"               NOT covered. An exact phrase list with nothing to learn
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

#: What the bar was showing. See `OpasDecision.surface`.
SURFACE_BAR = "bar"
SURFACE_WITH_LIST = "bar_with_list"
SURFACE_WITH_ORDER = "bar_with_order"
SURFACE_CATALOG = "catalog"


def surface_for(question: Any | None, front: str | None) -> str:
    """Which surface the phrase was typed on.

    ⚠️ DERIVED FROM WHAT THE REQUEST CARRIED rather than reported by the client. A client
    that said "bar" while sending an open question would put a wrong answer in the
    evidence, and the evidence is the one thing here that has to be right.
    """
    if front == "catalog":
        return SURFACE_CATALOG
    if front == "sales-order":
        return SURFACE_WITH_ORDER
    if question is not None:
        return SURFACE_WITH_LIST
    return SURFACE_BAR


def _outcome_for(body: dict) -> tuple[str, dict | None]:
    """`(outcome, proposed_request)` from what `ask` returned."""
    kind = body.get("kind")
    if kind == "unrecognized":
        return "refused", None
    if kind == "picks":
        return "asked", {"picks": [p.get("label") for p in (body.get("picks") or [])]}
    if kind == "open_order":
        return "executed", {"open_order_id": body.get("open_order_id")}
    if kind == "total":
        return "executed", {"total": True}
    question = body.get("question")
    return "executed", ({"question": question} if question else None)


def record_ask(
    db: Session,
    *,
    company_id: str,
    user_id: str | None,
    phrase: str | None,
    body: dict,
    surface: str,
    proposed_by: str = "rules",
    model_latency_ms: int | None = None,
    model_accepted: bool | None = None,
    model_refused_reason: str | None = None,
) -> str | None:
    """One row for one `/order-list/ask` interpretation. Returns the row id, or None.

    ⚠️ A PHRASE-LESS CALL IS NOT AN INTERPRETATION AND IS NOT LOGGED. The bar re-asks the
    same question when a pill is removed and when a pick is chosen, both with
    `phrase=None`; logging those would fill the evidence with rows nobody typed.
    """
    if not phrase or not phrase.strip():
        return None
    try:
        from app.models.opas_decision import OpasDecision

        outcome, proposed = _outcome_for(body)
        row = OpasDecision(
            company_id=company_id,
            actor_user_id=user_id,
            input_text=phrase,
            surface=surface,
            proposed_by=proposed_by,
            proposed_request=proposed,
            outcome=outcome,
            model_latency_ms=model_latency_ms,
            # ⚠️ THE CHECK CONSTRAINT REQUIRES A VERDICT ON A MODEL ROW, so a caller that
            # says `proposed_by="model"` and forgets the verdict is refused by the
            # database rather than writing a row that cannot answer the one question
            # this table exists to answer about the model.
            model_accepted=model_accepted,
            model_refused_reason=model_refused_reason,
        )
        db.add(row)
        db.commit()
        return row.id
    except Exception:
        # ⚠️ ROLLBACK, THEN CARRY ON. Without the rollback the caller's session is left
        # in a failed transaction and the NEXT thing it does raises — a logging failure
        # becoming a request failure one step later, which is the shape this whole
        # module is written to avoid.
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("opas decision log write failed for %r", phrase[:60], exc_info=True)
        return None


def record_resolve(
    db: Session,
    *,
    company_id: str,
    user_id: str | None,
    phrase: str,
    candidate_count: int,
) -> str | None:
    """One row for one `/catalog-pane/resolve` interpretation.

    ⚠️ THE CANDIDATE COUNT IS THE OUTCOME. One is an answer, several is a question, none
    is a miss — and the misses are the typo surface pg_trgm is for, which is why this
    endpoint is logged at all.
    """
    if not phrase or not phrase.strip():
        return None
    try:
        from app.models.opas_decision import OpasDecision

        outcome = (
            "executed" if candidate_count == 1
            else "asked" if candidate_count > 1
            else "refused"
        )
        row = OpasDecision(
            company_id=company_id,
            actor_user_id=user_id,
            input_text=phrase,
            surface=SURFACE_CATALOG,
            proposed_by="rules",
            proposed_request={"candidates": candidate_count},
            outcome=outcome,
        )
        db.add(row)
        db.commit()
        return row.id
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("opas decision log write failed for %r", phrase[:60], exc_info=True)
        return None
