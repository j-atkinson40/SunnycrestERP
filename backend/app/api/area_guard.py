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

from app.core.areas import area_for_tags, is_common
from app.core.security import decode_token
from app.database import get_db
from app.models.role import Role
from app.models.user import User

logger = logging.getLogger(__name__)


def _tenant_user_from_request(request: Request, db: Session) -> User | None:
    """The calling tenant user, or None. Never raises."""
    header = request.headers.get("authorization") or ""
    if not header.lower().startswith("bearer "):
        return None
    token = header[7:].strip()
    if not token:
        return None
    try:
        payload = decode_token(token)
    except JWTError:
        return None
    except Exception:  # pragma: no cover - defensive; decode must never 500 here
        return None

    if payload.get("type") != "access":
        return None
    # Only tenant roles carry areas. Platform and portal identities are governed
    # by their own realms and must not be touched by this guard.
    if payload.get("realm") not in (None, "tenant"):
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()


def enforce_area_limit(
    request: Request,
    db: Session = Depends(get_db),
) -> None:
    """Refuse a limited role any tenant endpoint outside its areas."""
    user = _tenant_user_from_request(request, db)
    if user is None:
        return  # (1) not an authenticated tenant user — not this guard's business

    role = db.query(Role).filter(Role.id == user.role_id).first()
    if role is None or role.limited_to_areas is None:
        return  # (2) unlimited role — today's behaviour, unchanged

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

    if is_common(path):
        return  # (3) the shell's common set

    allowed = set(role.limited_to_areas or ())
    area = area_for_tags(getattr(route, "tags", None))

    if area is not None and area in allowed:
        return

    # ⚠️ A NAMED CODE, NOT A BARE 403. An untagged endpoint and an
    # out-of-area endpoint are the same refusal to the caller but different
    # findings to us: the first means somebody shipped a route without an area
    # tag, the second means she asked for someone else's area. The log line
    # distinguishes them so a missing tag surfaces as a bug report rather than
    # as a user complaining the app is broken.
    reason = "untagged" if area is None else "out_of_area"
    logger.info(
        "area_guard refused user=%s role=%s areas=%s path=%s reason=%s area=%s",
        user.id, role.slug, sorted(allowed), path, reason, area,
    )
    raise HTTPException(
        status.HTTP_403_FORBIDDEN,
        detail={
            "code": "area_restricted",
            "message": (
                f"This account is limited to: {', '.join(sorted(allowed)) or '(none)'}. "
                f"The requested feature is not part of "
                f"{'any area' if area is None else f'the {area} area'}."
            ),
            "allowed_areas": sorted(allowed),
            "requested_area": area,
        },
    )
