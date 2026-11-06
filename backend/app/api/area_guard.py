"""One central check: an area-limited role reaches only its own areas.

⚠️ **WHY ONE DEPENDENCY AND NOT 886 EDITS.** Measured 2026-11-03: 1063 of 1920
tenant endpoints had no per-user authorization, 886 of them with no check in the
handler either. Gating them individually is 886 chances to forget one, and every
NEW endpoint would be another. This closes all of them for a limited role in a
single place, and closes a new untagged endpoint on the day it is written.

### Why a router dependency rather than middleware

Middleware runs before routing, so `scope["route"]` is not yet set and the check
could only match on the raw URL — which means path parameters, trailing slashes
and the `/api` alias all become its problem, and a near-miss silently fails
OPEN. A dependency attached to `v1_router` runs after routing, so it reads the
matched route's path TEMPLATE and its tags. Verified: a dependency declared on an
outer `APIRouter` sees `scope["route"].path` as the full template and
`scope["route"].tags` as the tags given at `include_router()`.

It is attached in exactly one place — `app/api/v1.py`, on the `v1_router`
constructor — so it cannot be forgotten on a new router.

### Three ways this deliberately does NOT fire

1. **No authenticated tenant user** → returns. The guard is an ADDITIONAL
   restriction on top of authentication, never a replacement for it. An
   unauthenticated request must still be refused by the endpoint's own
   dependencies (401), not by this (403), or `/auth/login` would answer 403 and
   nobody could sign in.
2. **The role's `limited_to_areas` is NULL** → returns. Every existing role is
   NULL and keeps behaving exactly as before.
3. **The route is in the common set** → returns. See `app/core/areas.py`.

⚠️ **IT READS THE TOKEN ITSELF RATHER THAN DEPENDING ON `get_current_user`.**
That dependency raises — 401 on a missing token, 404 when no company slug
resolves — and this guard must be silent in both cases. Depending on it would
convert every unauthenticated request on every endpoint into an error raised
from the guard instead of from the endpoint. So the token is decoded here,
non-raising, for identity only; all real authentication remains the endpoint's.
"""
from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.areas import (
    CHANGE,
    area_for_tags,
    grant_admits,
    is_common,
    parse_area_grant,
)
from app.core.security import decode_token
from app.core.two_step import requires_two_step
from app.database import get_db
from app.models.role import Role
from app.models.user import User

logger = logging.getLogger(__name__)


#: The area a user is confined to when they owe a second step. Not a role
#: property — see app/core/areas.py.
MFA_ENROLL_AREA = "mfa_enroll"


def _tenant_user_from_request(request: Request, db: Session) -> tuple[User | None, bool]:
    """The calling tenant user and whether their token passed a second step.

    Returns (user, mfa_claim). Never raises.
    """
    header = request.headers.get("authorization") or ""
    if not header.lower().startswith("bearer "):
        return None, False
    token = header[7:].strip()
    if not token:
        return None, False
    try:
        payload = decode_token(token)
    except JWTError:
        return None, False
    except Exception:  # pragma: no cover - defensive; decode must never 500 here
        return None, False

    if payload.get("type") != "access":
        return None, False
    # Only tenant roles carry areas. Platform and portal identities are governed
    # by their own realms and must not be touched by this guard.
    if payload.get("realm") not in (None, "tenant"):
        return None, False
    user_id = payload.get("sub")
    if not user_id:
        return None, False
    user = db.query(User).filter(
        User.id == user_id, User.is_active.is_(True)
    ).first()
    # ⚠️ `is True`, NOT TRUTHINESS. A token carrying `mfa: "no"` or `mfa: 0`
    # must not satisfy a second step by being a non-empty string or an int.
    return user, payload.get("mfa") is True


def enforce_area_limit(
    request: Request,
    db: Session = Depends(get_db),
) -> None:
    """Refuse a limited role any tenant endpoint outside its areas."""
    user, mfa_claim = _tenant_user_from_request(request, db)
    if user is None:
        return  # (1) not an authenticated tenant user — not this guard's business

    role = db.query(Role).filter(Role.id == user.role_id).first()

    # ⚠️ **THE SECOND STEP IS ENFORCED HERE, IN THE SAME GUARD, BY ONE MORE
    # AREA — NOT BY A SECOND GUARD.** James's ruling of 2026-11-03: a required
    # user whose token has not passed a second step is confined to
    # `mfa_enroll` plus the common shell set, and the frontend routes them
    # straight to enrolment. It is not a time window and there is no grace
    # period to expire.
    #
    # This is checked BEFORE the unlimited-role early return, because the users
    # who most need it hold unlimited roles: four of the five on production are
    # admins. An `if role.limited_to_areas is None: return` placed first would
    # have exempted exactly them.
    #
    # Guarding USE rather than issuance is what makes one check enough. Four
    # paths mint a tenant token — login, the production-track login, refresh,
    # and impersonation's raw `jwt.encode` — and a fifth added later would
    # escape an issuance-side guard silently. A token that cannot be USED for
    # payroll does not care how it was made.
    owes_second_step = requires_two_step(user, db) and not mfa_claim
    grants: dict[str, str] = {}
    if owes_second_step:
        allowed = declared = {MFA_ENROLL_AREA}
    elif role is None or role.limited_to_areas is None:
        return  # (2) unlimited role, second step satisfied — unchanged
    else:
        # ⚠️ `| {MFA_ENROLL_AREA}` — HER OWN SECOND FACTOR IS ALWAYS HERS TO
        # MANAGE. Without this union the area was reachable exactly while she
        # was CONFINED (the first branch grants it) and became unreachable the
        # moment she complied, because the payroll role is area-limited —
        # `r223` ships it with `limited_to_areas = ['payroll']`, which does not
        # contain `mfa_enroll`. So a verified accountant could not read how many
        # recovery codes she had left, and could not re-enrol on a new phone.
        #
        # It is not a widening of her reach: the `mfa_enroll` area holds only
        # the five `/two-step/*` endpoints, and `begin_enrolment` already
        # refuses to replace a confirmed secret from a signed-in session
        # (tested). A limited user's probe results are otherwise unchanged,
        # which has its own control test.
        # ⚠️ TWO SETS, NOT ONE, AND THE SPLIT IS THE POINT.
        #
        #   declared  what an admin configured on the role. This is what the
        #             refusal body and the log line report.
        #   allowed   what she can actually reach: `declared` plus her own
        #             second factor.
        #
        # My first draft used one set for both and leaked `mfa_enroll` into
        # the user-facing message — three existing tests caught it, correctly.
        # `mfa_enroll` is not an administrable area (it appears in no role's
        # `limited_to_areas` and cannot be set through the areas endpoint), so
        # reporting it would tell an admin her role grants something they
        # cannot see or change, and would make `limited_to_areas = []` report
        # as non-empty.
        # ⚠️ **GRANTS CARRY A LEVEL AS OF 2026-11-06, AND A BARE NAME STILL MEANS
        # `change`.** James's ruling: all-or-nothing forced over-granting —
        # production needs to SEE an order without being able to rewrite one.
        # `"orders:view"` admits GET; `"orders"` admits everything, which is
        # why the live `["payroll"]` role is completely unaffected.
        grants = dict(parse_area_grant(g) for g in (role.limited_to_areas or ()))
        declared = set(grants)
        allowed = declared | {MFA_ENROLL_AREA}

    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if path is None:
        # ⚠️ FAIL CLOSED. No matched route means this guard cannot tell what the
        # caller reached, and a limited role is exactly the caller for whom
        # "unknown" must not mean "allowed". In practice a router dependency
        # always has a matched route; if that ever stops being true the refusal
        # is loud rather than a silent hole.
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={
                "code": "area_restricted",
                "message": "This account is limited to specific areas and the "
                           "requested route could not be identified.",
            },
        )

    # ⚠️ THE METHOD IS PART OF THE MATCH AS OF 2026-11-06. The common set is
    # exact (method, path) pairs, not prefixes — a prefix admitted every sibling
    # route anyone added under it later, including 17 unreviewed writes, and
    # that is how `GET /locations/users` came to disclose another user's
    # access level to a payroll-limited user.
    if is_common(request.method, path):
        return  # (3) the shell's common set

    area = area_for_tags(getattr(route, "tags", None))

    if area is not None and area in allowed:
        # ⚠️ The LEVEL decides, not just membership. `mfa_enroll` is unioned in
        # rather than granted, so it has no level and is always full — her own
        # second factor is hers to manage, including the writes that enrol her.
        level = CHANGE if area == MFA_ENROLL_AREA else grants.get(area, CHANGE)
        if grant_admits(level, request.method, path):
            return
        # Fall through to the refusal below, which reports the declared areas.
        # ⚠️ A view-level user hitting a write gets `area_restricted`, not a
        # 405: the route exists and she may read it, she just may not change
        # it, and telling her the route is absent would be a lie.

    # ⚠️ A NAMED CODE, NOT A BARE 403. An untagged endpoint and an
    # out-of-area endpoint are the same refusal to the caller but different
    # findings to us: the first means somebody shipped a route without an area
    # tag, the second means she asked for someone else's area. The log line
    # distinguishes them so a missing tag surfaces as a bug report rather than
    # as a user complaining the app is broken.
    reason = "untagged" if area is None else "out_of_area"
    # The two refusal-code discriminators read the CONDITION, not the set.
    # Since the enrolment area is unioned into every limited role, comparing
    # the set to it is now ALSO true of a role with `limited_to_areas = []` —
    # someone who owes no second step and must not be told to go and enrol.
    # The set stopped being a discriminator the moment it stopped being
    # exclusive to one branch. ⚠️ Untested before this change: the empty-list
    # test asserts the reported areas and not the code, so nothing was red.
    if owes_second_step:
        reason = f"two_step_required/{reason}"
    logger.info(
        "area_guard refused user=%s role=%s areas=%s path=%s reason=%s area=%s",
        user.id, getattr(role, "slug", None), sorted(declared), path, reason, area,
    )
    raise HTTPException(
        status.HTTP_403_FORBIDDEN,
        detail=(
            {
                # A distinct code, because the remedy is completely different: this
                # one is "finish enrolling", not "you do not have access". A single
                # `area_restricted` for both would send her to an admin instead of
                # to the enrolment page.
                "code": "two_step_required",
                "message": (
                    "Two-step sign-in is required for this account because it can "
                    "reach payroll. Finish setting it up to continue."
                ),
                "allowed_areas": sorted(declared),
                "requested_area": area,
            }
            if owes_second_step
            else {
                "code": "area_restricted",
                "message": (
                    f"This account is limited to: {', '.join(sorted(declared)) or '(none)'}. "
                    f"The requested feature is not part of "
                    f"{'any area' if area is None else f'the {area} area'}."
                ),
                "allowed_areas": sorted(declared),
                "requested_area": area,
            }
        ),
    )
