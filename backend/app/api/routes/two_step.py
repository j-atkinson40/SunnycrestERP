"""Two-step sign-in: enrolment, verification, recovery.

⚠️ **THIS ROUTER IS TAGGED `area:mfa_enroll`, WHICH IS THE WHOLE MECHANISM.** A
user who requires two-step and holds a token that has not passed it is confined
by `enforce_area_limit` to that one area plus the 7-entry shell allowlist — so
these endpoints are reachable, and nothing else is. There is no second guard and
no grace window to expire (James's ruling, 2026-11-03).

The flow:

    POST /two-step/begin      issue an unconfirmed secret + otpauth:// URI
    POST /two-step/confirm    prove a code -> enrolled, returns the 10 recovery
                              codes ONCE, and a token pair that carries `mfa`
    POST /two-step/verify     an already-enrolled user proves a code at sign-in
    POST /two-step/recovery   spend one recovery code instead of a code
    GET  /two-step/status     required? enrolled? codes left?

`begin` and `confirm` are the only pair that issues recovery codes, and they are
shown in `confirm`'s response and never again — they are stored hashed.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.company_resolver import get_current_company
from app.api.deps import get_current_user, get_db
from app.core import two_step
from app.models.company import Company
from app.models.user import User
from app.services import audit_service
from app.services.auth_service import issue_two_step_tokens

router = APIRouter()


class CodeRequest(BaseModel):
    code: str


class BeginResponse(BaseModel):
    secret: str
    provisioning_uri: str
    issuer: str


@router.get("/status")
def status_(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Is two-step required for me, am I enrolled, how many codes are left?

    The frontend reads this to decide whether to route straight to enrolment.
    """
    return {
        "required": two_step.requires_two_step(current_user, db),
        "enrolled": two_step.is_enrolled(db, current_user.id),
        "unused_recovery_codes": two_step.unused_recovery_code_count(
            db, current_user.id
        ),
    }


@router.post("/begin", response_model=BeginResponse)
def begin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Issue an unconfirmed TOTP secret.

    ⚠️ THE SECRET IS RETURNED IN PLAINTEXT, ONCE, AND THAT IS THE POINT — she
    has to get it into her authenticator. It is stored encrypted, not hashed,
    because TOTP verifies against the secret itself.
    """
    try:
        _row, secret, uri = two_step.begin_enrolment(db, current_user)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    db.commit()
    return BeginResponse(
        secret=secret, provisioning_uri=uri, issuer=two_step.ISSUER_NAME
    )


@router.post("/confirm")
def confirm(
    body: CodeRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Prove a code, finish enrolment, and receive the recovery codes once."""
    try:
        codes = two_step.confirm_enrolment(db, current_user, body.code)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    audit_service.log_action(
        db, current_user.company_id, "two_step_enrolled", "user", current_user.id,
        user_id=current_user.id,
        changes={"recovery_codes_issued": len(codes)},
    )
    db.commit()
    tokens = issue_two_step_tokens(current_user, company)
    return {
        # ⚠️ THE ONLY TIME THESE EXIST IN PLAINTEXT. Stored hashed; there is no
        # endpoint that can show them again, by design.
        "recovery_codes": codes,
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "token_type": "bearer",
    }


@router.post("/verify")
def verify(
    body: CodeRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Exchange a first-step token for one that has passed the second step."""
    if not two_step.is_enrolled(db, current_user.id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Not enrolled in two-step sign-in. Start at /two-step/begin.",
        )
    if not two_step.verify_totp(db, current_user.id, body.code):
        audit_service.log_action(
            db, current_user.company_id, "two_step_failed", "user", current_user.id,
            user_id=current_user.id,
        )
        db.commit()
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "That code did not match."
        )
    row = two_step.get_two_step(db, current_user.id)
    from datetime import datetime, timezone
    row.last_verified_at = datetime.now(timezone.utc)
    db.commit()
    tokens = issue_two_step_tokens(current_user, company)
    return {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "token_type": "bearer",
    }


@router.post("/recovery")
def recovery(
    body: CodeRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    """Spend one single-use recovery code instead of a TOTP code.

    ⚠️ AUDITED EVERY TIME, SUCCESS OR FAILURE, AND IT REPORTS HOW MANY ARE LEFT.
    Recovery-code use is the signal that someone has lost a device — a silent
    one is a lost opportunity to notice an account being taken over.
    """
    if not two_step.consume_recovery_code(db, current_user.id, body.code):
        audit_service.log_action(
            db, current_user.company_id, "two_step_recovery_failed", "user",
            current_user.id, user_id=current_user.id,
        )
        db.commit()
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "That recovery code is not valid or is used."
        )
    remaining = two_step.unused_recovery_code_count(db, current_user.id)
    audit_service.log_action(
        db, current_user.company_id, "two_step_recovery_used", "user",
        current_user.id, user_id=current_user.id,
        changes={"recovery_codes_remaining": remaining},
    )
    db.commit()
    tokens = issue_two_step_tokens(current_user, company)
    return {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "token_type": "bearer",
        "recovery_codes_remaining": remaining,
    }
