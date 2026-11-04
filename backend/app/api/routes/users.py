from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database import get_db
from app.models.role import Role
from app.models.user import User
from app.schemas.password import ResetPasswordRequest
from app.schemas.role import UserPermissionOverrideRequest, UserPermissionOverridesResponse
from app.schemas.user import (
    PinResetRequest,
    PinRetrieveResponse,
    UserBulkCreate,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.services import audit_service
from app.services.permission_service import get_user_permissions
from app.services.role_service import get_user_permission_overrides, set_user_permission_overrides
from app.services.user_service import (
    create_user,
    create_users_bulk,
    deactivate_user,
    get_user,
    get_user_pin,
    get_users,
    reset_user_password,
    reset_user_pin,
    suggest_username,
    update_user,
)

router = APIRouter()


def _user_to_response(user: User) -> dict:
    """Convert a User model to a response dict with role info."""
    data = UserResponse.model_validate(user).model_dump()
    if user.role_obj:
        data["role_name"] = user.role_obj.name
        data["role_slug"] = user.role_obj.slug
    # ⚠️ **THE PENDING-INVITE FLAG, BECAUSE WITHOUT IT RESEND AND CANCEL HAVE NO
    # ENTRANCE.** A pending invitee renders in the user list identically to a
    # colleague who signed in last year: same row, same actions, nothing saying
    # she has never arrived. So the two endpoints would be complete, correct,
    # audited machinery that no admin could reach — which is the shape CLAUDE.md
    # §11 names *complete machinery behind an unprovisioned entrance*.
    #
    # Derived, never stored: `has_outstanding_invite` reads the hash's presence.
    # ⚠️ **THE DIGEST ITSELF IS NOT IN THE RESPONSE AND MUST NOT BE.** It is not
    # the token, but it is enough to confirm a guessed token against, and a user
    # list is the widest-read surface in the app.
    from app.services.tenant_invite import has_outstanding_invite

    data["has_outstanding_invite"] = has_outstanding_invite(user)
    data["invite_expires_at"] = (
        user.invite_token_expires_at.isoformat()
        if user.invite_token_hash is not None and user.invite_token_expires_at
        else None
    )

    # Include profile summary if loaded
    if hasattr(user, "profile") and user.profile:
        data["phone"] = user.profile.phone
        data["position"] = user.profile.position
        data["department"] = (
            user.profile.department_obj.name
            if user.profile.department_obj
            else None
        )
    return data


@router.get("")
def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.view")),
):
    result = get_users(db, current_user.company_id, page, per_page, search)
    return {
        "items": [_user_to_response(u) for u in result["items"]],
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
    }


@router.get("/suggest-username")
def suggest_uname(
    first_name: str = Query(...),
    last_name: str = Query(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.create")),
):
    username = suggest_username(db, first_name, last_name, current_user.company_id)
    return {"username": username}


@router.get("/{user_id}")
def read_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.view")),
):
    user = get_user(db, user_id, current_user.company_id)
    return _user_to_response(user)


@router.post("/bulk", status_code=201)
def create_bulk(
    data: UserBulkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.create")),
):
    result = create_users_bulk(
        db, data.users, current_user.company_id, actor_id=current_user.id
    )
    return result


@router.post("", status_code=201)
def create(
    data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.create")),
):
    user = create_user(db, data, current_user.company_id, actor_id=current_user.id)
    db.refresh(user)
    return _user_to_response(user)


@router.patch("/{user_id}")
def update(
    user_id: str,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.edit")),
):
    user = update_user(db, user_id, data, current_user.company_id, actor_id=current_user.id)
    db.refresh(user)
    return _user_to_response(user)


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: str,
    data: ResetPasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.edit")),
):
    reset_user_password(
        db, user_id, data.new_password, current_user.company_id, actor_id=current_user.id
    )
    return {"detail": "Password reset successfully"}


@router.delete("/{user_id}")
def delete(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.delete")),
):
    deactivate_user(db, user_id, current_user.company_id, actor_id=current_user.id)
    return {"detail": "User deactivated"}


@router.get("/{user_id}/permissions", response_model=UserPermissionOverridesResponse)
def get_user_perms(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.view")),
):
    user = get_user(db, user_id, current_user.company_id)
    effective = sorted(get_user_permissions(user, db))
    overrides = get_user_permission_overrides(db, user_id)
    return {
        "effective_permissions": effective,
        "overrides": [
            {"permission_key": o.permission_key, "granted": o.granted}
            for o in overrides
        ],
    }


@router.put("/{user_id}/permissions")
def set_user_perms(
    user_id: str,
    data: list[UserPermissionOverrideRequest],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.edit")),
):
    overrides = [{"permission_key": d.permission_key, "granted": d.granted} for d in data]
    set_user_permission_overrides(db, user_id, overrides, current_user.company_id)
    return {"detail": "Permission overrides updated"}


@router.post("/{user_id}/reset-pin")
def reset_pin(
    user_id: str,
    data: PinResetRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.edit")),
):
    reset_user_pin(
        db, user_id, data.new_pin, current_user.company_id, actor_id=current_user.id
    )
    return {"detail": "PIN reset successfully"}


@router.get("/{user_id}/pin", response_model=PinRetrieveResponse)
def retrieve_pin(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users.edit")),
):
    pin = get_user_pin(db, user_id, current_user.company_id)
    return {"pin": pin}


@router.post("/{user_id}/two-step/reset")
def reset_two_step(
    user_id: str,
    current_user: User = Depends(require_permission("users.edit")),
    db: Session = Depends(get_db),
):
    """Clear another user's two-step enrolment so they can re-enrol. Audited.

    ⚠️ **CLEARING YOUR OWN IS REFUSED, AND THAT IS THE POINT OF THE ENDPOINT'S
    EXISTENCE RATHER THAN A DETAIL OF IT.** An admin who could clear their own
    second factor could remove it the moment it inconvenienced them, which makes
    the requirement optional for exactly the people who hold every permission —
    four of the five users required to enrol on production are admins. Refusing
    self-clear means losing a device always takes a second person: recovery codes
    first, then another admin.

    ⚠️ **SOLE-ADMIN CASE.** Sunnycrest has ONE admin today, so there is no second
    person. The ladder is: her ten recovery codes, then a platform-admin reset.
    The platform path is reported in STATE rather than built here — see the
    report — because it needs a platform-realm endpoint and its own audit trail,
    which is more than this dispatch's scope.
    """
    from app.core import two_step

    if user_id == current_user.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "You cannot reset your own two-step sign-in. Use a recovery code, or "
            "ask another administrator — losing a device should always take a "
            "second person.",
        )

    target = get_user(db, user_id, current_user.company_id)
    had = two_step.clear_two_step(db, target.id)

    audit_service.log_action(
        db,
        current_user.company_id,
        "two_step_reset",
        "user",
        target.id,
        user_id=current_user.id,
        changes={
            # Actor and subject recorded separately: `user_id` is who DID it,
            # `entity_id` is who it was done TO. A single field would make an
            # admin resetting themselves indistinguishable from this.
            "reset_by": current_user.id,
            "reset_for": target.id,
            "had_enrolment": had,
        },
    )
    db.commit()
    return {"user_id": target.id, "had_enrolment": had, "enrolled": False}


# ── Invites (Payroll 2, ruling 4) ────────────────────────────────────────

class InviteUserRequest(BaseModel):
    """Name, email and role. **No password field, deliberately.**

    James's ruling: *"admin enters name, email and role; she gets a single-use,
    expiring link; first visit sets her password. Admin never sees or sets
    it."* There is nowhere in this shape to put a password, which is stronger
    than validating that one was not supplied.
    """
    # ⚠️ `extra="forbid"` — A SUPPLIED PASSWORD IS REFUSED, NOT IGNORED.
    # Pydantic's default is to drop unknown fields, which here would mean a
    # caller could POST `{"password": ...}`, receive a 201, and believe it took
    # effect. Silently ignoring a credential is the loud-to-quiet shape; this
    # makes it a 422 that names the field.
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    role_id: str


class InviteUserResponse(BaseModel):
    user_id: str
    email: str
    expires_at: datetime
    #: Whether the invite email was handed to the delivery layer. False means
    #: she has no link and the invite must be re-sent once email is configured.
    email_sent: bool
    #: Surfaced so the admin screen can tell her, in advance, that this person
    #: will have to set up two-step at first sign-in.
    two_step_will_be_required: bool


@router.post("/invite", response_model=InviteUserResponse,
             status_code=status.HTTP_201_CREATED)
def invite_user_endpoint(
    data: InviteUserRequest,
    current_user: User = Depends(require_permission("users.create")),
    db: Session = Depends(get_db),
):
    """Create a user with no password and email them a single-use link.

    ⚠️ **THE RESPONSE CARRIES NO LINK AND NO TOKEN.** An admin holding the link
    can set her password, so returning it would be the same disclosure the
    ruling forbids wearing a different name. The link exists in exactly one
    place outside this function: her inbox.

    ⚠️ **AND A FAILED EMAIL IS REPORTED, NOT PAPERED OVER.** `email_sent=False`
    means the user row exists and no link was delivered — recoverable by
    re-inviting once delivery works, and visible rather than silent. The
    temptation here is a fallback that returns the link when email fails, which
    would mean the guarantee quietly depends on SMTP being up.
    """
    from app.models.company import Company
    from app.core.two_step import requires_two_step
    from app.services import tenant_invite

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found")

    # Validate the role belongs to this tenant before creating anything.
    role = (
        db.query(Role)
        .filter(Role.id == data.role_id, Role.company_id == company.id)
        .first()
    )
    if role is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "unknown_role",
                    "message": "That role does not exist for this tenant."},
        )

    try:
        user, token = tenant_invite.invite_user(
            db,
            company=company,
            inviter=current_user,
            email=str(data.email),
            first_name=data.first_name,
            last_name=data.last_name,
            role_id=data.role_id,
        )
    except tenant_invite.InviteError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "invite_refused", "message": str(exc)},
        )

    email_sent = _send_invite_email(db, company=company, user=user,
                                    inviter=current_user, token=token)
    # ⚠️ `token` goes out of scope here and is recoverable from nothing. The
    # stored value is a sha256 digest; there is no path back to the link.
    del token

    return InviteUserResponse(
        user_id=user.id,
        email=user.email,
        expires_at=user.invite_token_expires_at,
        email_sent=email_sent,
        two_step_will_be_required=requires_two_step(user, db),
    )


class ResendInviteResponse(BaseModel):
    user_id: str
    email: str
    expires_at: datetime
    email_sent: bool
    #: Always True on success. Stated in the response because it is the thing
    #: the admin needs to be able to tell the person on the phone: the link you
    #: were sent before no longer works, use the new one.
    previous_link_invalidated: bool


class CancelInviteResponse(BaseModel):
    email: str
    #: False when there was nothing to cancel. The endpoint still returns 200 —
    #: see the docstring on why this is not a 404.
    cancelled: bool


def _pending_invitee_or_404(db: Session, user_id: str, actor: User) -> User:
    """The named user, confined to this tenant. 404 otherwise.

    ⚠️ **`company_id` IS IN THE FILTER, NOT CHECKED AFTERWARDS.** A lookup by
    id alone followed by a comparison is the shape that leaks existence: the
    two branches are distinguishable by timing and by any later divergence in
    the handler. Filtering means another tenant's user id is simply not found.
    """
    user = (
        db.query(User)
        .filter(User.id == user_id, User.company_id == actor.company_id)
        .first()
    )
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


@router.post("/{user_id}/invite/resend", response_model=ResendInviteResponse)
def resend_invite_endpoint(
    user_id: str,
    current_user: User = Depends(require_permission("users.create")),
    db: Session = Depends(get_db),
):
    """Issue a fresh invite link and kill the previous one.

    ⚠️ **THE RESPONSE CARRIES NO LINK**, for the same reason `POST /invite`
    does not: an admin holding the link can set her password. `email_sent=False`
    means a new token was minted, the old one is dead, and nothing was
    delivered — which is worse than not having resent at all, so it is reported
    rather than smoothed over.

    Requires `users.create` rather than a narrower permission. Resending is
    inviting: it mints a credential that sets a password on an account.
    """
    from app.models.company import Company
    from app.services import tenant_invite

    user = _pending_invitee_or_404(db, user_id, current_user)
    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found")

    try:
        token = tenant_invite.resend_invite(db, actor=current_user, user=user)
    except tenant_invite.InviteError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "invite_refused", "message": str(exc)},
        )

    email_sent = _send_invite_email(db, company=company, user=user,
                                    inviter=current_user, token=token)
    del token

    return ResendInviteResponse(
        user_id=user.id,
        email=user.email,
        expires_at=user.invite_token_expires_at,
        email_sent=email_sent,
        previous_link_invalidated=True,
    )


@router.delete("/{user_id}/invite", response_model=CancelInviteResponse)
def cancel_invite_endpoint(
    user_id: str,
    current_user: User = Depends(require_permission("users.delete")),
    db: Session = Depends(get_db),
):
    """Remove a pending invitee. The row goes; the audit row stays.

    ⚠️ **`cancelled=False` RETURNS 200, NOT 404, AND THE DISTINCTION IS WHAT THE
    CALLER IS ASKING.** Two admins clicking Cancel on the same stale list is
    the ordinary case, and the second one's question — *is this invite gone?* —
    is answered yes. A 404 would say "no such user", which is false: she exists,
    or existed, and is not pending. The 404 above is reserved for a user id
    this tenant has no claim to.

    ⚠️ **AND THIS CANNOT TOUCH SOMEONE WHO HAS SIGNED IN.** `revoke_invite`
    returns False without deleting when `invite_token_hash` is None, so an
    accepted user falls into the `cancelled=False` branch rather than being
    removed. Deleting a real colleague through the Cancel-invite button is the
    failure this shape forecloses — not by remembering to check here, but
    because the service refuses.
    """
    from app.services import tenant_invite

    user = _pending_invitee_or_404(db, user_id, current_user)
    email = user.email
    cancelled = tenant_invite.revoke_invite(db, actor=current_user, user=user)
    return CancelInviteResponse(email=email, cancelled=cancelled)


def _send_invite_email(db: Session, *, company, user: User, inviter: User,
                       token: str) -> bool:
    """Hand the invite link to the D-7 delivery layer. True if accepted.

    Mirrors `portal_admin._send_invite_email`, including its try/except: a
    delivery failure must not roll back the user row, because re-inviting is a
    single admin action whereas a half-created user is a support call.
    """
    import logging

    try:
        from app.config import settings

        # ⚠️ `app.services.delivery.delivery_service`, NOT
        # `app.services.delivery_service`. BOTH MODULES EXIST, and only the
        # first defines this function — the second raises ImportError on the
        # name. My first draft copied the import from
        # `portal_admin._send_invite_email` (`:159`), which has the wrong one
        # and swallows the ImportError in a bare `except Exception`, so **every
        # portal invite and password-recovery email has silently failed to send
        # since Phase 8e.2.1**. Measured, not inferred:
        #
        #   from app.services.delivery_service import send_email_with_template
        #   ImportError: cannot import name 'send_email_with_template'
        #
        # Copying a call site is copying its bugs, and a try/except around the
        # import is what let this one live. Filed as a separate fix.
        from app.services.delivery.delivery_service import (
            send_email_with_template,
        )

        # ⚠️ `tenant_link_base`, NOT `settings.FRONTEND_URL`. This exact line
        # emailed `http://localhost:5173/accept-invite?token=…` to James on
        # 2026-11-04, because FRONTEND_URL's default is the developer address
        # and production does not set it. See app/core/links.py.
        from app.core.links import tenant_link_base

        invite_url = f"{tenant_link_base(company)}/accept-invite?token={token}"
        # ⚠️ Keyword names taken from the real signature, not from the portal's
        # call: `to_email` / `to_name` / `subject_override`, never
        # `recipient=` / `subject=`.
        delivery = send_email_with_template(
            db,
            template_key="email.tenant_user_invite",
            company_id=company.id,
            to_email=user.email,
            to_name=f"{user.first_name} {user.last_name}",
            subject_override=f"{company.name} — set up your account",
            template_context={
                "first_name": user.first_name,
                "inviter_name": f"{inviter.first_name} {inviter.last_name}",
                "tenant_name": company.name,
                "invite_url": invite_url,
                "expires_in": "3 days",
            },
            caller_module="users.invite",
        )
        # ⚠️ TWO BUGS MY OWN TEST CAUGHT HERE, BOTH FROM NOT READING THE
        # FUNCTION I WAS CALLING.
        #
        # 1. `send()` FLUSHES AND NEVER COMMITS — deliberately, so the audit
        #    row lands atomically with the caller's business operation (the
        #    same contract `audit_service.log_action` has). `invite_user`
        #    committed before this call, so without a commit here the
        #    `document_deliveries` row is flushed and then rolled back when the
        #    request's session closes. The email goes out; the record of it
        #    does not. Measured: 69,641 delivery rows in the table and none
        #    from `users.invite`.
        #
        # 2. ITS DOCSTRING SAYS IT "never raises on send failure — check
        #    `.status`". So returning True on "no exception raised" reports
        #    success for a send that failed. 4 of those 69,641 rows are
        #    `failed`, so this is not theoretical.
        db.commit()
        # ⚠️ AND `status == 'sent'` ALONE IS NOT PROOF OF DELIVERY.
        # `EmailChannel._is_test_mode()` returns success with
        # `provider_message_id='test-mode'` whenever `RESEND_API_KEY` is empty
        # or literally "test" — so an unconfigured environment reports EVERY
        # email as sent. Measured on the dev database: 69,623 of 69,637 `sent`
        # rows are test-mode. Without this second clause the guarantee written
        # into r227's docstring — "if email is not configured, inviting cannot
        # complete" — would be FALSE, and an admin would be told the link went
        # out when nothing left the building.
        #
        # Production is configured: 5,546 sent deliveries all carry real
        # provider ids, 2,762 of them sunnycrest's, most recent 2026-11-03
        # (read-only, 2026-11-03). This clause is what makes the flag honest
        # everywhere else.
        return delivery.status == "sent" and delivery.provider_message_id != "test-mode"
    except Exception:
        # ⚠️ Logged WITHOUT the url or the token. An exception log carrying the
        # invite link would put the credential in a second place, which is the
        # mistake this whole flow exists to avoid.
        # Roll back whatever the delivery layer flushed before failing, so a
        # half-written delivery row cannot ride along on a later commit.
        db.rollback()
        logging.getLogger(__name__).exception(
            "invite email failed to dispatch user_id=%s company_id=%s",
            user.id, company.id,
        )
        return False
