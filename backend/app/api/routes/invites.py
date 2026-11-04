"""The public half of the invite flow: she opens the link and sets a password.

Payroll 2, ruling 4. Two endpoints, both **UNAUTHENTICATED** — she has no
credential yet, which is the whole point of the flow.

⚠️ **UNAUTHENTICATED IS NOT UNGUARDED, AND THE DISTINCTION MATTERS HERE BECAUSE
PAYROLL 1 SHIPPED A GUARD THAT COULD HAVE MADE THIS WORSE.** `enforce_area_limit`
runs on every `/api/v1` route and returns early when no tenant user is
authenticated — deliberately, so that `/auth/login` cannot answer 403 and lock
everyone out (see `app/api/area_guard.py`'s point 1). These two routes rely on
that early return. What gates them instead is the TOKEN: a 256-bit single-use
secret that expires in 72 hours, which is the same shape as the portal's
`/proof-approval/{token}` precedent.

⚠️ **ONE HARMLESS WRINKLE, NAMED SO IT IS NOT MISTAKEN FOR A BUG.** A user who
is ALREADY signed in and owes a second step is confined to `mfa_enroll`, so if
she opens an invite link in that same browser session these two routes answer
403 rather than rendering. The real path — an invitee with no credential at all,
in a browser with no token — is unaffected, because the guard early-returns for
her. It is left alone deliberately: adding `/invites` to `COMMON_PREFIXES` would
make it an 8th entry, and ruling 2 names "the 7-entry shell allowlist" as a
figure. Changing a figure James ruled on is not a silent edit.

⚠️ **AND EVERY FAILURE RETURNS THE SAME MESSAGE.** Unknown token, expired token,
already-accepted token and deactivated user are one refusal from outside. A
flow that distinguished them would let anyone with a URL determine whether an
email address has an account — and the accept page is public, so "anyone" is
anyone.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.company import Company
from app.services import tenant_invite

router = APIRouter()


class InvitePreview(BaseModel):
    """What the accept page may show before she has authenticated.

    ⚠️ Deliberately thin. Her own name and email are things she already knows —
    they confirm the link is hers rather than disclosing anything. The role, the
    tenant's user list, her permissions and whether two-step will be required
    are all absent: an unauthenticated caller holding a leaked link must not
    learn the shape of the tenant from it.
    """
    email: str
    first_name: str
    last_name: str
    company_name: str


class AcceptInviteRequest(BaseModel):
    password: str = Field(min_length=tenant_invite.PASSWORD_MIN_LENGTH)


class AcceptInviteResponse(BaseModel):
    email: str
    company_slug: str
    #: True when she holds a payroll permission and must enrol in two-step
    #: before her token reaches anything. The accept page reads this to send
    #: her straight to enrolment instead of to a sign-in form she would
    #: immediately be bounced out of.
    two_step_required: bool


def _refusal() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "code": "invite_invalid",
            "message": (
                "This invitation link is not valid. It may have expired or "
                "already been used. Ask an administrator to send a new one."
            ),
        },
    )


@router.get("/{token}", response_model=InvitePreview)
def preview_invite(token: str, db: Session = Depends(get_db)) -> InvitePreview:
    """Confirm a link is live, so the page can greet her instead of a form."""
    try:
        user = tenant_invite.resolve_invite(db, token)
    except tenant_invite.InviteError:
        raise _refusal()

    company = db.query(Company).filter(Company.id == user.company_id).first()
    return InvitePreview(
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        company_name=company.name if company else "",
    )


@router.post("/{token}/accept", response_model=AcceptInviteResponse)
def accept_invite(
    token: str,
    data: AcceptInviteRequest,
    db: Session = Depends(get_db),
) -> AcceptInviteResponse:
    """Set her password and consume the invite.

    ⚠️ **RETURNS NO TOKEN PAIR, AND THAT IS NOT AN OVERSIGHT.** Signing her in
    here would hand out a tenant access token on a request whose only credential
    was a link from an inbox — and for a payroll user that token would then need
    the second step anyway. She signs in at the normal sign-in page, by typing
    the password she just chose, which is also the fastest way for her to find
    out she remembers it.
    """
    try:
        user = tenant_invite.accept_invite(db, token, data.password)
    except tenant_invite.InviteError as exc:
        # Strength failures carry their own text — it is about the password she
        # just typed, not about whether the link exists.
        msg = str(exc)
        if msg.startswith("Password must"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "password_too_weak", "message": msg},
            )
        raise _refusal()

    from app.core.two_step import requires_two_step

    company = db.query(Company).filter(Company.id == user.company_id).first()
    return AcceptInviteResponse(
        email=user.email,
        company_slug=company.slug if company else "",
        two_step_required=requires_two_step(user, db),
    )
