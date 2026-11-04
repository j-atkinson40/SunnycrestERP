"""Tenant user invites: admin sends a link, she sets her own password.

Payroll 2, ruling 4 (James, 2026-11-03): *"Invite: admin enters name, email and
role; she gets a single-use, expiring link; first visit sets her password. Admin
never sees or sets it."*

⚠️ **THIS IS ADDITIVE. NO PASSWORD-IN-BODY PATH IS REMOVED, AND THAT IS
DELIBERATE.** Six callers take a password in a request body — `create_user`,
`reset_user_password`, `register_company`, `register_user`, platform tenant
creation, and `change_password` — three of them reached by seeds that build the
canonical tenants. CLAUDE.md §11 is explicit that removal is the LAST step:
enforce direction, fill the callers, then remove. The direction enforced here is
that the ADMIN UI offers invite only; the parameters stay for the seeds and for
`change_password`, which is a user setting her own password and is the thing
invites exist to enable rather than something to replace.

### What "hashed, single-use, expiring" each mean here

    hashed       sha256 of the token is stored; the token itself never is.
                 A read of `users` yields no working link.
    single-use   accepting CLEARS `invite_token_hash`. Not "marks used" —
                 cleared, so a replayed link cannot resolve a row at all.
    expiring     72h, checked at resolve time against the stored timestamp.

⚠️ **AND THE PORTAL DOES NONE OF THE THREE, WHICH IS WHY THE SHAPE WAS COPIED
AND THE CODE WAS NOT.** `invite_portal_user` writes `recovery_token=invite_token`
in plaintext (`app/services/portal/user_service.py:182`), leaving `portal_users.invite_token` a dead column with a unique
index on it. Recorded as a separate cleanup item — its flow is outside this
dispatch and changing it needs its own break tests.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.company import Company
from app.models.user import User
from app.services import audit_service

#: James's ruling. One constant, read by the issuer and by its tests.
INVITE_TTL_HOURS = 72

#: 32 bytes from `secrets.token_urlsafe` → 43 url-safe chars, ~256 bits.
_TOKEN_BYTES = 32

#: Matches the portal's floor. No complexity rules: a rule that forces a
#: pattern pushes people to write the password down, and the second step is
#: what carries the strength for a payroll account.
PASSWORD_MIN_LENGTH = 8


class InviteError(ValueError):
    """Any refusal from this module. The API layer maps it to a status."""


def _hash_token(token: str) -> str:
    """sha256 hex of the token.

    ⚠️ **NOT bcrypt, AND THE REASON IS THE INPUT, NOT CONVENIENCE.** bcrypt's
    cost factor buys resistance to guessing a LOW-ENTROPY secret. This input is
    256 bits of CSPRNG output, so there is nothing to guess; what is needed is
    to find one row from the token in a link, and a deterministic digest is
    indexable where bcrypt is not. `r225`'s recovery codes are bcrypt for the
    mirror-image reason: short enough to read aloud, and looked up inside one
    already-identified user, so a scan costs nothing.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def validate_password_strength(password: str) -> None:
    if not password or len(password) < PASSWORD_MIN_LENGTH:
        raise InviteError(
            f"Password must be at least {PASSWORD_MIN_LENGTH} characters."
        )


def invite_user(
    db: Session,
    *,
    company: Company,
    inviter: User,
    email: str,
    first_name: str,
    last_name: str,
    role_id: str,
    ttl_hours: int = INVITE_TTL_HOURS,
) -> tuple[User, str]:
    """Create a user with NO password and an outstanding invite.

    Returns `(user, token)`. **The token is returned once and never stored** —
    the caller emails it. Nothing in this module can recover it afterwards,
    which is the point of storing the digest.
    """
    email_clean = (email or "").lower().strip()
    if not email_clean:
        raise InviteError("An email address is required to invite a user.")

    existing = (
        db.query(User)
        .filter(User.email == email_clean, User.company_id == company.id)
        .first()
    )
    if existing is not None:
        raise InviteError(
            f"A user with email {email_clean!r} already exists for this tenant."
        )

    token = secrets.token_urlsafe(_TOKEN_BYTES)
    now = datetime.now(timezone.utc)
    user = User(
        email=email_clean,
        # ⚠️ NO PASSWORD. Not a random one — NULL. r226 made the column
        # nullable and added `ck_users_password_or_invite` so that this row is
        # permitted precisely because it carries an invite, and a row with
        # neither is still refused by the database.
        hashed_password=None,
        first_name=(first_name or "").strip(),
        last_name=(last_name or "").strip(),
        role_id=role_id,
        company_id=company.id,
        created_by=inviter.id,
        invite_token_hash=_hash_token(token),
        invite_token_expires_at=now + timedelta(hours=ttl_hours),
        invited_by_user_id=inviter.id,
    )
    db.add(user)
    db.flush()

    # Same two lines `create_user` runs (`user_service.py:222-228`), with the
    # same signature — (db, user_id, role_slug) — and the same None-guard on
    # the role lookup.
    from app.models.role import Role
    from app.services.role_service import sync_functional_areas_for_role

    role_obj = db.query(Role).filter(Role.id == role_id).first()
    if role_obj:
        sync_functional_areas_for_role(db, user.id, role_obj.slug)

    audit_service.log_action(
        db,
        user_id=inviter.id,
        company_id=company.id,
        action="user.invited",
        entity_type="user",
        entity_id=user.id,
        # ⚠️ The token is NOT in the audit row. An audit log that records
        # invite links is a second place they can be read from.
        changes={
            "email": email_clean,
            "role_id": role_id,
            "expires_at": user.invite_token_expires_at.isoformat(),
        },
    )
    db.commit()
    return user, token


def resolve_invite(db: Session, token: str) -> User:
    """The user an unexpired, unaccepted invite token names.

    Raises `InviteError` for every failure — unknown, expired, already
    accepted — with the SAME message, because the accept page is public and
    the differences are not its visitor's business.
    """
    if not token:
        raise InviteError("This invitation link is not valid.")

    user = (
        db.query(User)
        .filter(User.invite_token_hash == _hash_token(token))
        .first()
    )
    # A cleared hash is what acceptance leaves behind, so "already accepted"
    # arrives here as "no such row" and needs no separate branch.
    if user is None or not user.is_active:
        raise InviteError("This invitation link is not valid.")

    expires = user.invite_token_expires_at
    if expires is None:
        raise InviteError("This invitation link is not valid.")
    # Stored timezone-aware; be defensive about a naive read from a driver
    # that dropped the tzinfo rather than comparing a naive to an aware.
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= datetime.now(timezone.utc):
        raise InviteError("This invitation link is not valid.")

    return user


def accept_invite(db: Session, token: str, password: str) -> User:
    """Set her password and consume the invite. Returns the user."""
    user = resolve_invite(db, token)
    validate_password_strength(password)

    user.hashed_password = hash_password(password)
    # Single-use: CLEARED, not flagged. A replay cannot find the row.
    user.invite_token_hash = None
    user.invite_token_expires_at = None
    user.invite_accepted_at = datetime.now(timezone.utc)

    audit_service.log_action(
        db,
        user_id=user.id,
        company_id=user.company_id,
        action="user.invite_accepted",
        entity_type="user",
        entity_id=user.id,
        changes={"email": user.email},
    )
    db.commit()
    return user


def revoke_invite(db: Session, *, actor: User, user: User) -> bool:
    """Cancel an outstanding invite by DELETING the pending user row.

    False if there was no invite to revoke.

    ⚠️ **DELETE, NOT "CLEAR THE HASH", AND THE CONSTRAINT IS WHY.** A CHECK is
    evaluated on UPDATE as well as INSERT, so `SET invite_token_hash = NULL` on
    a row whose `hashed_password` is also NULL violates
    `ck_users_password_or_invite` and raises. My first draft of this function
    did exactly that and documented the opposite — the constraint refuses it,
    which is the constraint doing its job: there is no valid state in which a
    user has neither a password nor an invite.

    Deactivating instead does not help; `is_active` is not in the constraint and
    the row would still have neither credential nor invite.

    So the honest operation is to remove the row. A revoked invite is a person
    who never signed in: nothing references her, she has no history, and
    `created_by` / `invited_by_user_id` point AT the inviter rather than at her.
    An accepted user is never reachable here — acceptance clears the hash and
    sets the password, so this returns False for her.
    """
    if user.invite_token_hash is None:
        return False

    email, company_id, user_id = user.email, user.company_id, user.id
    db.delete(user)
    # Logged after the delete and against the ACTOR, so the row survives the
    # user it describes. `entity_id` deliberately keeps the departed id — the
    # audit trail's job is to say which invite was cancelled.
    audit_service.log_action(
        db,
        user_id=actor.id,
        company_id=company_id,
        action="user.invite_revoked",
        entity_type="user",
        entity_id=user_id,
        changes={"email": email, "disposition": "pending_user_row_deleted"},
    )
    db.commit()
    return True


def has_outstanding_invite(user: User) -> bool:
    return user.invite_token_hash is not None
