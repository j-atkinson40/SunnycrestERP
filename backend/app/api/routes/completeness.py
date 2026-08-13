"""The completeness review + the nil-claim pattern. CR-2 A-3.

Three endpoints, two audiences:

  GET  /review          the accountant's bounded decision — run-collapsed,
                        exception-shaped. Powers the Pulse widget + command bar.
  GET  /my-obligations  the SAME service filtered to the caller's own role.
                        This is what makes the prompt ARRIVE rather than wait.
  POST /nil-claim       "nothing happened", signed.

⚠️ THE NIL-CLAIM ENDPOINT IS THE PATTERN, NOT ONE SURFACE. Three obligations
need the affordance and each belongs to a different person in a different place:
production log (production, at a terminal), deliveries (driver, on a phone),
toolbox talk (safety_trainer, weekly). "The nil claim page" would be a page
nobody visits. The endpoint is expectation-keyed and role-checked, so the
driver's and the safety trainer's versions are WIRING, not design.

⚠️ AND IT MUST BE PROMPTED, NOT REMEMBERED. A quiet day produces no reason to
open anything. If the only way to say "nothing to log" is on the log page, the
obligation is satisfied only by people who were going to satisfy it anyway —
which is everyone except the ones the review exists to catch. Hence
`/my-obligations`: the prompt is delivered to where that person already is.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.completeness.collapse import collapse, summarise
from app.services.completeness.expectations import for_tenant
from app.services.completeness.review import review

router = APIRouter()


def _vertical(db: Session, company_id: str) -> str:
    got = db.execute(
        text("SELECT vertical FROM companies WHERE id = :c"), {"c": company_id}
    ).scalar()
    return got or "manufacturing"


def _role_slug(db: Session, user: User) -> str | None:
    return db.execute(
        text("SELECT slug FROM roles WHERE id = :r"), {"r": user.role_id}
    ).scalar()


def _serialise(runs, closing: str) -> dict:
    return {
        "rows": [
            {
                "key": r.key, "label": r.label, "role_slug": r.role_slug,
                "verdict": r.verdict, "actionable": r.actionable,
                "first": r.first.isoformat(), "last": r.last.isoformat(),
                "periods": r.periods, "detail": r.detail,
            }
            for r in runs
        ],
        # Counted, never enumerated. Silence is what a reader fills in with an
        # assumption; "3 obligations current" is a statement.
        "quiet_summary": closing,
        "actionable_count": sum(1 for r in runs if r.actionable),
    }


@router.get("/review")
def get_review(
    as_of: date | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Are the books complete through this date. Bounded, and it exits."""
    rows = review(db, current_user.company_id, _vertical(db, current_user.company_id), as_of)
    shown, closing = summarise(collapse(rows))
    return _serialise(shown, closing)


@router.get("/my-obligations")
def my_obligations(
    as_of: date | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """What THIS person owes. The prompt's data source.

    Returns the same runs, filtered to the caller's role — so a production
    manager's Pulse can say "you haven't logged 11 Aug" without them going
    looking for it.
    """
    slug = _role_slug(db, current_user)
    rows = review(
        db, current_user.company_id, _vertical(db, current_user.company_id),
        as_of, role_slug=slug,
    )
    shown, closing = summarise(collapse(rows))
    return {**_serialise(shown, closing), "role_slug": slug}


class NilClaim(BaseModel):
    expectation_key: str
    period_start: date
    period_end: date
    note: str | None = None


@router.post("/nil-claim")
def file_nil_claim(
    body: NilClaim,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """State that nothing happened, signed.

    ⚠️ ONLY THE ROLE THAT OWES IT MAY CLAIM IT. This is the one place assertion
    substitutes for evidence, and what makes the claim worth anything is that a
    named person HOLDING THE OBLIGATION stood behind it. A claim from anyone
    else is an opinion.
    """
    exps = {e.key: e for e in for_tenant(current_user.company_id,
                                         _vertical(db, current_user.company_id))}
    exp = exps.get(body.expectation_key)
    if exp is None:
        raise HTTPException(404, f"No such expectation: {body.expectation_key}")

    slug = _role_slug(db, current_user)
    if slug != exp.role_slug:
        raise HTTPException(
            403,
            f"'{exp.label}' is the {exp.role_slug} role's obligation; "
            f"you hold '{slug}'. A nil claim is only evidence when it comes "
            f"from whoever owes it.",
        )

    now = datetime.now(timezone.utc)
    name = f"{current_user.first_name} {current_user.last_name}".strip() or current_user.email
    try:
        db.execute(
            text(
                "INSERT INTO completeness_nil_claims (id, tenant_id, expectation_key, "
                "period_start, period_end, claimed_by, claimed_by_name, "
                "claimed_by_role_slug, claimed_at, note, created_at) VALUES "
                "(:i, :t, :k, :s, :e, :u, :n, :r, :a, :note, :a)"
            ),
            {
                "i": str(uuid.uuid4()), "t": current_user.company_id,
                "k": body.expectation_key, "s": body.period_start,
                "e": body.period_end, "u": current_user.id, "n": name,
                # Snapshotted — a later join answers "what role NOW", which is a
                # different question from what they held when they claimed.
                "r": slug, "a": now, "note": body.note,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        # The unique index. Re-stating "nothing happened" is not an error worth
        # failing on, but it must not mint a second row — a count of claims
        # would then read as a count of quiet days.
        raise HTTPException(409, "Already reported for this period.")

    return {"status": "recorded", "claimed_by": name, "role_slug": slug}
