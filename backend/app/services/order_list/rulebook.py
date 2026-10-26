"""The rulebook: read it, add to it, edit it, switch a rule off.

James's dispatch of 2026-10-26, clause 4. "'the rulebook' / 'rules' in the bar opens a
pane listing active rules (sentence, who, when, the change it came from, linking to that
order). Each rule can be edited or switched off."

⚠️ IT LIVES BESIDE `decision_log` RATHER THAN IN `capture/`, which is a filing decision
worth one line. A rule is WRITTEN from a capture and READ as a pane, and every other
pane's read is here — `customer.py`, `cemetery.py`, `detail.py`. Putting it under
`capture/` would make the one pane whose read lives somewhere else.

⚠️ NOTHING READS THESE RULES YET, AND THE PANE SAYS SO. "nothing uses the rulebook in
this slice. It records and shows, and the model starts reading it in the next step. I'd
rather the first rules be ones you've seen go in" (James). `FOOTER` is that sentence and
it is part of the payload rather than the component, for the same reason every other
sentence on every other pane is: one place decides what something is called.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

#: ⚠️ THE PANE'S OWN DISCLAIMER, SERVER-SIDE. A reader who sees a rule they confirmed
#: would otherwise reasonably assume it is in force. It is not, yet.
FOOTER = "Opas doesn’t use these yet"

EMPTY = "No rules yet"

#: A rule sentence longer than this is not a sentence. Enforced on the way in, because
#: the office can type its own over the model's draft and the pane renders one line.
MAX_TEXT = 220


def add_rule(
    db: Session,
    *,
    company_id: str,
    user_id: str | None,
    rule_text: str,
    source_decision_id: str | None = None,
) -> str | None:
    """Store one confirmed rule. Returns its id, or None if there was nothing to store.

    ⚠️ IT DOES NOT COMMIT. The caller owns the transaction — the rule and the decision
    row's `reason_scope` have to land together or not at all, or a crash between them
    leaves a rule nobody can trace and a question that looks unanswered.
    """
    sentence = " ".join((rule_text or "").split()).strip()
    if not sentence:
        return None
    from app.models.opas_rule import OpasRule

    row = OpasRule(
        company_id=company_id,
        text=sentence[:MAX_TEXT],
        source_decision_id=source_decision_id,
        created_by=user_id,
    )
    db.add(row)
    db.flush()
    return row.id


def _actor_names(db: Session, ids: set[str]) -> dict[str, str]:
    """user_id -> a name to show. Absent ids simply do not appear.

    ⚠️ ONE QUERY, NOT ONE PER ROW. The pane lists every active rule and an N+1 here
    would be invisible at four rules and obvious at four hundred.
    """
    wanted = [i for i in ids if i]
    if not wanted:
        return {}
    rows = db.execute(
        text("SELECT id, first_name, last_name, email FROM users WHERE id = ANY(:ids)"),
        {"ids": wanted},
    ).mappings().all()
    out: dict[str, str] = {}
    for r in rows:
        name = " ".join(p for p in ((r["first_name"] or ""), (r["last_name"] or "")) if p)
        out[r["id"]] = name.strip() or (r["email"] or "")
    return out


def rulebook(db: Session, company_id: str) -> dict:
    """The pane: every active rule, newest first, with where it came from."""
    from app.models.opas_rule import OpasRule

    rows = (
        db.query(OpasRule)
        .filter(OpasRule.company_id == company_id, OpasRule.is_active.is_(True))
        .order_by(OpasRule.created_at.desc())
        .all()
    )
    names = _actor_names(db, {r.created_by for r in rows if r.created_by})

    # The change each rule came from, and the order it was on, in one query.
    provenance: dict[str, dict] = {}
    source_ids = [r.source_decision_id for r in rows if r.source_decision_id]
    if source_ids:
        for d in db.execute(
            text(
                """
                SELECT id, changed_field, changed_from, changed_to, reason
                  FROM opas_decisions
                 WHERE id = ANY(:ids) AND company_id = :t
                """
            ),
            {"ids": source_ids, "t": company_id},
        ).mappings():
            provenance[d["id"]] = dict(d)

    out: list[dict] = []
    for r in rows:
        entry: dict = {
            "id": r.id,
            "text": r.text,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        who = names.get(r.created_by or "")
        if who:
            entry["who"] = who
        src = provenance.get(r.source_decision_id or "")
        if src and src.get("changed_field"):
            # ⚠️ THE SERVER COMPOSES THE SENTENCE, as every other pane's does.
            field = (src["changed_field"] or "").replace("_", " ")
            entry["change"] = (
                f"{field} · {src.get('changed_from')} → {src.get('changed_to')}"
            )
            entry["decision_id"] = src["id"]
            if src.get("reason"):
                entry["reason"] = src["reason"]
        out.append(entry)

    detail: dict = {"rules": out, "footer": FOOTER}
    if not out:
        detail["empty"] = EMPTY
    return detail


def update_rule(
    db: Session, *, company_id: str, rule_id: str,
    rule_text: str | None = None, is_active: bool | None = None,
) -> dict | None:
    """Edit a rule's sentence or switch it off. None when it is not this tenant's.

    ⚠️ `company_id` IN THE FILTER, NOT CHECKED AFTER THE FETCH. A read that loads by id
    and then compares has already loaded another tenant's row, and the version that
    forgets to compare looks identical.
    """
    from app.models.opas_rule import OpasRule

    row = (
        db.query(OpasRule)
        .filter(OpasRule.id == rule_id, OpasRule.company_id == company_id)
        .first()
    )
    if row is None:
        return None
    if rule_text is not None:
        sentence = " ".join(rule_text.split()).strip()
        if sentence:
            row.text = sentence[:MAX_TEXT]
    if is_active is not None:
        row.is_active = bool(is_active)
    db.flush()
    return {"id": row.id, "text": row.text, "is_active": row.is_active}


#: What opens the rulebook from the bar. Exact phrases, because a stem rule would claim
#: "rule out" and "ruled".
#:
#: ⚠️ "rules" ALONE IS IN HERE AND IT IS THE RISKY ONE. The dispatch names it ("'the
#: rulebook' / 'rules' in the bar"), and the word is otherwise unclaimed by any rule or
#: pane — measured against `isOrderListPhrase`, `_ORDER_WORDS` and the catalog resolver.
#: If a product is ever called "Rules" this is the line that has to change.
_OPENERS: frozenset[str] = frozenset({
    "the rulebook", "rulebook", "rules", "the rules",
    "open the rulebook", "show the rulebook", "show me the rulebook",
    "open rules", "show rules",
})


def opens_rulebook(phrase: str) -> bool:
    """Is this phrase a request for the rulebook?"""
    return " ".join((phrase or "").split()).strip().casefold() in _OPENERS


def record_answer(
    db: Session,
    *,
    decision_id: str,
    company_id: str,
    reason: str | None,
    scope: str,
    change: dict | None,
) -> bool:
    """Write the reason, its scope and the change onto the decision row.

    ⚠️ IT DOES NOT COMMIT, for the reason `add_rule` does not: a confirmed rule and the
    scope that produced it belong to one transaction.

    ⚠️ AND IT REFUSES TO OVERWRITE AN ANSWER. "never asks twice for one order" is
    enforced where the record is, not only where the question is drawn — a retried
    request or a second tab must not replace the first answer.
    """
    from app.models.opas_decision import OpasDecision

    row = (
        db.query(OpasDecision)
        .filter(OpasDecision.id == decision_id, OpasDecision.company_id == company_id)
        .first()
    )
    if row is None or row.reason_scope is not None:
        return False
    row.reason = (reason or None) or None
    row.reason_scope = scope
    if change:
        row.changed_field = (change.get("field") or None)
        row.changed_from = (change.get("was") or None)
        row.changed_to = (change.get("now") or None)
    row.resolved_at = datetime.now(timezone.utc)
    db.flush()
    return True
