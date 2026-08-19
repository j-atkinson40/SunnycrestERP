"""The completeness review + the nil-claim pattern. CR-2 A-3.

Six endpoints, three audiences:

  GET  /review          the accountant's bounded decision — run-collapsed,
                        exception-shaped. Powers the Pulse widget + command bar.
  GET  /my-obligations  the SAME service filtered to the caller's own role.
                        This is what makes the prompt ARRIVE rather than wait.
  POST /nil-claim       "nothing happened", signed.
  GET  /obligations     the full declared set with its current state (CR-3 D-2).
  POST /decline         "we don't do that", signed (CR-3 D-2).
  POST /declinations/{id}/revoke   "we do this again" (CR-3 D-2).

⚠️ THE DECLINING ENDPOINTS ARE ROLE-CHECKED IN THE HANDLER. The read endpoints
here gate on `get_current_user` only — any authenticated user can pull the whole
tenant's review by API while the UI is role-gated. That is a known CR-2-shaped
gap, flagged rather than fixed. A WRITE inheriting it would not be a gap: it
would let any user silence any obligation for the whole tenant.

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
from app.services.completeness.declinations import live_for_tenant
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


# ── CR-3 D-2: the authoring surface's data ────────────────────────────
#
# ⚠️ WHO MAY DECLINE IS A DIFFERENT QUESTION FROM WHO MAY NIL-CLAIM, AND THE
# ANSWERS DIVERGE ON PURPOSE. A nil claim is an OBSERVATION about one period, so
# only the role that owes it may make one — a claim from anyone else is an
# opinion. A declination is a STANDING DECISION about what the business does, so
# the person who holds the obligation is exactly the wrong authority: the driver
# does not decide whether the company runs a delivery fleet.
#
# Accounting responsibility decides. The same list the route gate uses, because a
# UI-only restriction on a write is not a restriction.
DECLINING_ROLES = ("admin", "accountant")


def _require_declining_role(slug: str | None) -> None:
    """⚠️ ENFORCED HERE, NOT ONLY IN THE ROUTER. The read endpoints in this file
    gate on `get_current_user` and are reachable by any authenticated user while
    the UI is role-gated — a known gap, flagged and out of CR-3's scope. A WRITE
    inheriting that would not be a gap, it would be a hole: any user could
    silence any obligation for the whole tenant.
    """
    if slug not in DECLINING_ROLES:
        raise HTTPException(
            403,
            f"Declining an obligation is a standing decision about the "
            f"business; you hold '{slug}'. It belongs to "
            f"{' or '.join(DECLINING_ROLES)}.",
        )


@router.get("/obligations")
def list_obligations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Every obligation declared for this tenant and its current state.

    ⚠️ THE AUTHORING SURFACE READS THIS, NOT THE REVIEW. `/review` is
    exception-shaped — it answers "what needs attention" and deliberately does
    not enumerate what is fine. Declining is performed against the OBLIGATION,
    which means the surface needs the full declared set including the quiet ones,
    and a control derived from a review row would only ever be able to decline
    things that were already red.
    """
    exps = for_tenant(current_user.company_id, _vertical(db, current_user.company_id))
    live = live_for_tenant(db, current_user.company_id)
    return {
        "obligations": [
            {
                "key": e.key,
                "label": e.label,
                "role_slug": e.role_slug,
                "cadence": e.cadence,
                "matters_because": e.matters_because,
                "declination": _serialise_declination(live.get(e.key)),
            }
            for e in exps
        ],
        "may_decline": _role_slug(db, current_user) in DECLINING_ROLES,
    }


def _serialise_declination(d: dict | None) -> dict | None:
    if d is None:
        return None
    return {
        "id": d["id"],
        "declined_on": d["declined_on"].isoformat(),
        "reason": d["reason"],
        # Snapshotted at write time — this says who answered THEN, which is a
        # different fact from what they hold now.
        "declined_by_name": d["declined_by_name"],
        "declined_by_role_slug": d["declined_by_role_slug"],
    }


class DeclineRequest(BaseModel):
    expectation_key: str
    reason: str


class RevokeRequest(BaseModel):
    reason: str


@router.post("/decline")
def decline_obligation(
    body: DeclineRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """"We don't do that", recorded — with who, when and why.

    ⚠️ THE REASON IS REQUIRED AND EMPTY IS NOT A REASON. "We don't do that" with
    no reason is the weak assertion this arc rejected everywhere else, and unlike
    a nil claim a declination stands until someone revokes it. Pydantic accepts
    `""` for a `str`, so the check is here rather than assumed.
    """
    reason = body.reason.strip()
    if not reason:
        raise HTTPException(
            422,
            "A declination needs a reason. It silences this obligation until "
            "someone revokes it, and a future reader has only this sentence.",
        )

    exps = {e.key: e for e in for_tenant(current_user.company_id,
                                         _vertical(db, current_user.company_id))}
    exp = exps.get(body.expectation_key)
    if exp is None:
        raise HTTPException(404, f"No such obligation: {body.expectation_key}")

    slug = _role_slug(db, current_user)
    _require_declining_role(slug)

    now = datetime.now(timezone.utc)
    name = f"{current_user.first_name} {current_user.last_name}".strip() or current_user.email
    try:
        db.execute(
            text(
                "INSERT INTO completeness_declinations (id, tenant_id, "
                "expectation_key, declined_on, reason, declined_by, "
                "declined_by_name, declined_by_role_slug, created_at) "
                "VALUES (:i, :t, :k, :d, :reason, :u, :n, :r, :c)"
            ),
            {
                "i": str(uuid.uuid4()), "t": current_user.company_id,
                "k": body.expectation_key,
                # ⚠️ TODAY, NOT A DATE THE CALLER PICKS. A back-dated declination
                # would erase periods that were genuinely missed — the retroactive
                # rewrite D-3 was spent removing, handed back as a parameter.
                "d": now.date(), "reason": reason, "u": current_user.id,
                "n": name, "r": slug, "c": now,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        # `ux_completeness_declination_live`. Declining twice is not an error
        # worth failing loudly on, but a second live episode must not exist —
        # "is this declined now" would stop being a question with one answer.
        raise HTTPException(409, "This obligation is already declined.")

    return {"status": "declined", "declined_by": name, "role_slug": slug}


@router.post("/declinations/{declination_id}/revoke")
def revoke_declination(
    declination_id: str,
    body: RevokeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """"We do this again" — the obligation resumes.

    ⚠️ NOT A DELETE. The episode keeps its dates, so the review still renders the
    months the tenant was not doing it as `declined` rather than reporting them as
    gaps. A delete would erase the answer to "when did we start doing this again"
    AND retroactively accuse the tenant of every period they had already accounted
    for.

    Scoped by tenant in the UPDATE itself, not checked and then written — the
    check-then-act version has a window and this has none.
    """
    reason = body.reason.strip()
    if not reason:
        raise HTTPException(422, "Resuming an obligation needs a reason too.")

    slug = _role_slug(db, current_user)
    _require_declining_role(slug)

    now = datetime.now(timezone.utc)
    name = f"{current_user.first_name} {current_user.last_name}".strip() or current_user.email
    result = db.execute(
        text(
            "UPDATE completeness_declinations SET "
            # Both columns, together. `ck_completeness_declination_revocation_
            # coherent` refuses the row otherwise — the effective date and the
            # recorded time are different facts that must agree one happened.
            "  revoked_on = :d, revoked_at = :at, revoked_reason = :reason, "
            "  revoked_by = :u, revoked_by_name = :n, revoked_by_role_slug = :r "
            "WHERE id = :i AND tenant_id = :t AND revoked_at IS NULL"
        ),
        {
            "i": declination_id, "t": current_user.company_id,
            # Today, for the same reason declining is: a back-dated revocation
            # would turn already-answered periods into gaps.
            "d": now.date(), "at": now, "reason": reason,
            "u": current_user.id, "n": name, "r": slug,
        },
    )
    if result.rowcount == 0:
        db.rollback()
        # One 404 for three causes — wrong id, another tenant's row, already
        # revoked — because distinguishing them would confirm to a caller that
        # somebody else's declination id exists.
        raise HTTPException(404, "No live declination with that id.")
    db.commit()
    return {"status": "revoked", "revoked_by": name, "role_slug": slug}


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
