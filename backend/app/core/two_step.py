"""Two-step sign-in: who needs it, and the TOTP / recovery-code primitives.

Payroll 2. Any user whose effective permissions include a payroll key must pass
a second step before holding a token that reaches payroll.

⚠️ **THE REQUIREMENT FOLLOWS THE PERMISSION, NOT A ROLE LIST.** `requires_two_step`
is a prefix match over `get_user_permissions`, so:

  - a `payroll.timesheets.view` key added next year extends the requirement to
    everyone holding it, with no code change here;
  - a single per-user override granting `payroll.view` makes two-step required
    for that one person;
  - there is no `("admin", "accountant", "payroll")` tuple to drift — which is
    precisely the mistake `ACCOUNTING_ROLES` made and Payroll 1 had to undo.

Measured on production 2026-11-03: 5 of 18 users match, four of them admins by
the `get_user_permissions` wildcard (`permission_service.py:43`) and one by
explicit grant.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone

import pyotp
from sqlalchemy.orm import Session

from app.core.security import (
    decrypt_totp_secret,
    encrypt_totp_secret,
    hash_password,
    verify_password,
)
from app.models.user_two_step import UserRecoveryCode, UserTwoStep

#: The prefix that makes two-step required. One string, read by the predicate
#: and by its tests.
PAYROLL_PERMISSION_PREFIX = "payroll."

#: TOTP window: pyotp's default is a 30s step. `valid_window=1` accepts the
#: adjacent steps, which covers ordinary clock skew between her phone and the
#: server. Wider would mean a stolen code stays usable longer.
TOTP_VALID_WINDOW = 1

RECOVERY_CODE_COUNT = 10
#: 10 chars of base32, grouped for reading aloud over the phone. ~50 bits —
#: far beyond guessing for a single-use code behind a login.
_RECOVERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # no I, O, 0, 1
_RECOVERY_LEN = 10

ISSUER_NAME = "Bridgeable"

logger = logging.getLogger(__name__)


# ───────────────────────────────────────────────────────── the predicate


#: The emergency off switch. A Railway variable, so it is flipped WITHOUT a
#: code deploy — James's ruling of 2026-11-04, on the grounds that his first
#: test of two-step is on production and a bug in enrolment would otherwise
#: lock the only admin out of Sunnycrest until a fix ships.
TWO_STEP_ENFORCED_ENV = "TWO_STEP_ENFORCED"

#: ⚠️ **FAIL SECURE, AND THE SET IS A WHITELIST OF DISABLING VALUES RATHER THAN
#: A TRUTHINESS TEST.** Enforcement is skipped ONLY when the variable reads
#: exactly one of these, case- and space-insensitively. Absent, empty, `"true"`,
#: a typo, `"flase"`, `"disabled"`, anything else at all → ENFORCED. The
#: opposite default would mean a misspelled variable silently turns the
#: requirement off, which is the one failure this switch must not have.
_DISABLING_VALUES = frozenset({"false", "0", "no", "off"})


def two_step_enforcement_disabled() -> bool:
    """Is the emergency off switch flipped?

    ⚠️ **READ FROM THE ENVIRONMENT AT CALL TIME, NOT FROM `settings`.** A
    Railway variable change restarts the service, so `settings` would normally
    pick it up — but the whole point of this switch is that it works when
    something is already wrong, and a partial or failed restart is exactly that
    situation. `os.getenv` is correct here for the same reason the switch
    exists.
    """
    import os

    return os.getenv(TWO_STEP_ENFORCED_ENV, "").strip().lower() in _DISABLING_VALUES


def requires_two_step(user, db: Session) -> bool:
    """Does this user hold any payroll permission?

    Reads the real permission resolver, so the admin wildcard and per-user
    overrides are both honoured without being reimplemented here.

    ⚠️ **THE OFF SWITCH IS CHECKED HERE, IN THE PREDICATE, NOT IN THE GUARD.**
    One place, and everything downstream follows consistently: the guard stops
    confining, `/two-step/status` reports `required: false` so the frontend
    stops routing to enrolment, and the invite response stops promising a second
    step that will not be asked for. Putting it in `enforce_area_limit` instead
    would have disabled the refusal while leaving three surfaces still telling
    users two-step was required.
    """
    if two_step_enforcement_disabled():
        # ⚠️ EVERY REQUEST SERVED WHILE THE SWITCH IS OFF SAYS SO, per James's
        # ruling. One line per request is deliberate: this is an emergency
        # state, the volume IS the signal, and a quiet bypass is how a
        # temporary switch becomes a permanent one nobody remembers flipping.
        logger.warning(
            "TWO-STEP ENFORCEMENT DISABLED by %s — serving user=%s without a "
            "second step. This is an emergency switch; unset the variable to "
            "restore enforcement.",
            TWO_STEP_ENFORCED_ENV, getattr(user, "id", None),
        )
        return False

    from app.services.permission_service import get_user_permissions

    return any(
        p.startswith(PAYROLL_PERMISSION_PREFIX) for p in get_user_permissions(user, db)
    )


def get_two_step(db: Session, user_id: str) -> UserTwoStep | None:
    return db.query(UserTwoStep).filter(UserTwoStep.user_id == user_id).first()


def is_enrolled(db: Session, user_id: str) -> bool:
    """Enrolled means a CONFIRMED row. A half-finished enrolment is not one."""
    row = get_two_step(db, user_id)
    return row is not None and row.enrolled_at is not None


# ──────────────────────────────────────────────────────────── enrolment


def begin_enrolment(db: Session, user) -> tuple[UserTwoStep, str, str]:
    """Issue (or re-issue) an unconfirmed secret. Returns (row, secret, uri).

    ⚠️ RE-ISSUING REPLACES AN UNCONFIRMED SECRET AND REFUSES A CONFIRMED ONE. A
    user who starts enrolment twice should get a fresh secret, not a conflict —
    but once enrolled, re-issuing would be a way to swap a second factor using
    only the first, so it is refused and goes through reset instead.
    """
    row = get_two_step(db, user.id)
    if row is not None and row.enrolled_at is not None:
        raise ValueError(
            "already enrolled in two-step sign-in; an enrolled secret cannot be "
            "replaced from a signed-in session — use recovery, or an admin reset"
        )

    secret = pyotp.random_base32()
    if row is None:
        row = UserTwoStep(user_id=user.id,
                          totp_secret_encrypted=encrypt_totp_secret(secret))
        db.add(row)
    else:
        row.totp_secret_encrypted = encrypt_totp_secret(secret)
    db.flush()

    uri = pyotp.TOTP(secret).provisioning_uri(
        name=getattr(user, "email", None) or user.id, issuer_name=ISSUER_NAME
    )
    return row, secret, uri


def verify_totp(db: Session, user_id: str, code: str) -> bool:
    """Check a TOTP code against the stored secret. Does not stamp anything."""
    row = get_two_step(db, user_id)
    if row is None:
        return False
    try:
        secret = decrypt_totp_secret(row.totp_secret_encrypted)
    except Exception:
        # A secret that cannot be decrypted is a secret nobody can use. Fail
        # closed and let recovery or an admin reset sort it out, rather than
        # raising a 500 into a login form.
        return False
    code = (code or "").strip().replace(" ", "")
    if not code:
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=TOTP_VALID_WINDOW)


def confirm_enrolment(db: Session, user, code: str) -> list[str]:
    """Stamp enrolment and return the ten recovery codes, ONCE.

    The plaintext codes exist only in this return value — they are stored
    hashed, so this is the only moment they can be shown.
    """
    row = get_two_step(db, user.id)
    if row is None:
        raise ValueError("no enrolment in progress; call begin first")
    if row.enrolled_at is not None:
        raise ValueError("already enrolled")
    if not verify_totp(db, user.id, code):
        raise ValueError("that code did not match")

    now = datetime.now(timezone.utc)
    row.enrolled_at = now
    row.last_verified_at = now
    codes = _issue_recovery_codes(db, user.id)
    db.flush()
    return codes


# ───────────────────────────────────────────────────── recovery codes


def _generate_recovery_code() -> str:
    raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(_RECOVERY_LEN))
    return f"{raw[:5]}-{raw[5:]}"


def _issue_recovery_codes(db: Session, user_id: str) -> list[str]:
    """Replace any existing codes with a fresh set of ten.

    ⚠️ OLD CODES ARE DELETED HERE, not left alongside. Two live sets would mean
    a code the user believes they destroyed still works.
    """
    db.query(UserRecoveryCode).filter(UserRecoveryCode.user_id == user_id).delete()
    plaintext = [_generate_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
    for code in plaintext:
        db.add(UserRecoveryCode(user_id=user_id, code_hash=hash_password(code)))
    db.flush()
    return plaintext


def consume_recovery_code(db: Session, user_id: str, code: str) -> bool:
    """Spend one unused recovery code. Returns False if none matches.

    ⚠️ COMPARES AGAINST EVERY UNUSED HASH, because bcrypt hashes are salted and
    cannot be looked up by value. That is O(unused codes) bcrypt checks — ten at
    most, which is why the count is ten.
    """
    code = (code or "").strip().upper().replace(" ", "")
    if not code:
        return False
    rows = (
        db.query(UserRecoveryCode)
        .filter(UserRecoveryCode.user_id == user_id,
                UserRecoveryCode.used_at.is_(None))
        .all()
    )
    for row in rows:
        if verify_password(code, row.code_hash):
            row.used_at = datetime.now(timezone.utc)
            db.flush()
            return True
    return False


def unused_recovery_code_count(db: Session, user_id: str) -> int:
    return (
        db.query(UserRecoveryCode)
        .filter(UserRecoveryCode.user_id == user_id,
                UserRecoveryCode.used_at.is_(None))
        .count()
    )


# ───────────────────────────────────────────────────────────── reset


def clear_two_step(db: Session, user_id: str) -> bool:
    """Remove a user's second factor entirely. Returns True if there was one.

    The caller is responsible for the authorization check and the audit row —
    this function deliberately knows nothing about who is asking, so the refusal
    to clear your own cannot be bypassed by calling it directly from somewhere
    that forgot.
    """
    row = get_two_step(db, user_id)
    db.query(UserRecoveryCode).filter(UserRecoveryCode.user_id == user_id).delete()
    if row is not None:
        db.delete(row)
    db.flush()
    return row is not None


# ─────────────────────────────────── the non-production seed path (ruling 5)

#: The fixed secret seeded demo and test users enrol with. **PUBLIC AND
#: WORTHLESS BY DESIGN** — it is in the repository, so anyone can compute a
#: valid code for any account enrolled through it. That is exactly why
#: `enrol_for_non_production` refuses to run in production: the secret's
#: disclosure is the feature, and the guard is the only thing keeping it off
#: real accounts.
#:
#: Base32, 32 chars, which is what `pyotp` accepts as a secret.
NON_PRODUCTION_TOTP_SECRET = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"


class ProductionEnrolmentRefused(RuntimeError):
    """`enrol_for_non_production` was called with ENVIRONMENT=production."""


def _is_production() -> bool:
    """True if EITHER environment source says production.

    ⚠️ **A DENY-UNION, NOT TWO SOURCES OF TRUTH FOR ONE VALUE.** `settings` is
    read once at import, so a process that had ENVIRONMENT set before start
    sees it there and a later `os.environ` write does not reach it; the raw
    env var is the more current reading and the one the existing seed guards
    use (`seed_staging.py:99`). Taking the union means the STRICTER reading
    wins, which is the correct asymmetry for a refusal: disagreement between
    the two refuses rather than permits.
    """
    import os

    from app.config import settings

    return "production" in (
        os.getenv("ENVIRONMENT", "").lower(),
        str(getattr(settings, "ENVIRONMENT", "")).lower(),
    )


def enrol_for_non_production(db: Session, user) -> UserTwoStep:
    """Enrol `user` on the fixed known secret. Non-production only.

    James's ruling of 2026-11-03: *"demo-tenant admins are required like anyone
    else. In non-production only, seeds may enrol with a fixed known secret so
    tests and demos keep working."*

    ⚠️ **THIS DOES NOT LET AN ENROLLED USER PAST THE GUARD, AND THAT IS NOT A
    GAP.** `enforce_area_limit` reads the `mfa` CLAIM ON THE TOKEN, never the
    enrolment row — because the point of a second step is that it was passed
    THIS SESSION, not that it was once set up. So a seeded demo admin still
    signs in, still gets a claimless token, and is still confined to
    `mfa_enroll` until they post a code. What this buys them is that the code
    they must post is computable (`pyotp.TOTP(NON_PRODUCTION_TOTP_SECRET).now()`)
    rather than locked in an authenticator app nobody has.

    Returns the row. Idempotent: re-enrolling replaces the secret with the same
    constant and re-stamps `enrolled_at`.
    """
    if _is_production():
        raise ProductionEnrolmentRefused(
            "enrol_for_non_production writes a secret that is published in the "
            "repository. It must never run against production accounts."
        )

    row = get_two_step(db, user.id)
    if row is None:
        row = UserTwoStep(user_id=user.id)
        db.add(row)
    row.totp_secret_encrypted = encrypt_totp_secret(NON_PRODUCTION_TOTP_SECRET)
    row.enrolled_at = datetime.now(timezone.utc)
    db.flush()
    return row


def non_production_totp_code() -> str:
    """The code that is valid right now for a `enrol_for_non_production` user.

    Here rather than in each caller so a demo script and a test cannot disagree
    about which secret they are computing against.
    """
    return pyotp.TOTP(NON_PRODUCTION_TOTP_SECRET).now()
