"""The way back in when the phone AND the recovery codes are gone.

James's question of 2026-11-04. Traced, the answer without this script was
"you can't": recovery codes gone means no second factor; sole admin means the
self-clear refusal has nobody to appeal to; and `TWO_STEP_ENFORCED=false` gets
you signed in but `begin_enrolment` raises `already enrolled` against the dead
row, so you can never re-enrol and therefore never turn enforcement back ON.

⚠️ **THAT LAST STEP IS WHY THIS IS TESTED RATHER THAN DOCUMENTED.** The
emergency switch is meant to be temporary. Without a way to clear a dead
enrolment, the only way to stay signed in would be to leave sign-in protection
off permanently — the switch becoming the state.

The script runs via `railway run`, outside the application, because the
situation it exists for is one where the application is what you cannot reach.
"""
from __future__ import annotations

import subprocess
import sys

import pytest
from sqlalchemy import text

from app.core import two_step
from app.models.user import User
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

_canonical_tenant = make_canonical_tenant_fixture()

UID = "recov-script-user"
EMAIL = "recov-script-user@testco.example.com"
SCRIPT = ["python", "-m", "scripts.clear_two_step"]


def _run(*args):
    return subprocess.run([sys.executable, "-m", "scripts.clear_two_step", *args],
                          capture_output=True, text=True)


@pytest.fixture
def db():
    from app.database import SessionLocal
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def enrolled_user(db, monkeypatch):
    from app.services.role_service import seed_default_roles

    seed_default_roles(db, TESTCO_ID)
    db.commit()
    rid = db.execute(text(
        "SELECT id FROM roles WHERE company_id=:c AND slug='payroll' LIMIT 1"
    ), {"c": TESTCO_ID}).scalar()
    if rid is None:
        pytest.skip("testco has no payroll role")
    for t in ("user_recovery_codes", "user_two_step"):
        db.execute(text(f"DELETE FROM {t} WHERE user_id=:u"), {"u": UID})
    db.execute(text("DELETE FROM audit_logs WHERE entity_id=:u"), {"u": UID})
    db.execute(text("DELETE FROM users WHERE id=:u"), {"u": UID})
    db.add(User(id=UID, email=EMAIL, hashed_password="not-a-credential",
                first_name="Recovery", last_name="Script", role_id=rid,
                company_id=TESTCO_ID))
    db.commit()
    monkeypatch.setenv("ENVIRONMENT", "dev")
    user = db.query(User).filter(User.id == UID).first()
    two_step.enrol_for_non_production(db, user)
    two_step._issue_recovery_codes(db, UID)
    db.commit()
    assert two_step.is_enrolled(db, UID), "fixture failed to enrol"
    assert two_step.unused_recovery_code_count(db, UID) > 0
    yield user
    for t in ("user_recovery_codes", "user_two_step"):
        db.execute(text(f"DELETE FROM {t} WHERE user_id=:u"), {"u": UID})
    db.execute(text("DELETE FROM audit_logs WHERE entity_id=:u"), {"u": UID})
    db.execute(text("DELETE FROM users WHERE id=:u"), {"u": UID})
    db.commit()


def test_the_dead_end_is_real_without_the_script(enrolled_user, db):
    """⚠️ THE PREMISE, PINNED. If this stops being true the script may be
    unnecessary — and nothing else would tell us."""
    with pytest.raises(ValueError) as exc:
        two_step.begin_enrolment(db, enrolled_user)
    assert "enrol" in str(exc.value).lower(), str(exc.value)


def test_the_script_clears_a_dead_enrolment(enrolled_user, db):
    r = _run("--email", EMAIL, "--company-slug", "testco")
    assert r.returncode == 0, f"stdout={r.stdout}\nstderr={r.stderr}"
    db.expire_all()
    assert not two_step.is_enrolled(db, UID), "the enrolment survived"
    assert two_step.unused_recovery_code_count(db, UID) == 0, "codes survived"


def test_after_clearing_she_can_enrol_again(enrolled_user, db, monkeypatch):
    """The point of the whole exercise: enforcement can be turned back ON."""
    assert _run("--email", EMAIL, "--company-slug", "testco").returncode == 0
    db.expire_all()
    fresh = db.query(User).filter(User.id == UID).first()
    row, secret, uri = two_step.begin_enrolment(db, fresh)   # no longer raises
    db.commit()
    assert secret and uri


def test_it_is_audited(enrolled_user, db):
    assert _run("--email", EMAIL, "--company-slug", "testco").returncode == 0
    row = db.execute(text(
        "SELECT user_id, changes::text FROM audit_logs "
        "WHERE action='two_step_cleared_by_script' AND entity_id=:u "
        "ORDER BY created_at DESC LIMIT 1"), {"u": UID}).first()
    assert row is not None, "the clear was not audited"
    assert row[0] is None, "audit_logs.user_id is FK'd to users.id; must be NULL"
    assert "clear_two_step.py" in row[1], row[1]
    assert "recovery_codes_destroyed" in row[1], row[1]


def test_dry_run_changes_nothing(enrolled_user, db):
    r = _run("--email", EMAIL, "--company-slug", "testco", "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "nothing changed" in r.stdout
    db.expire_all()
    assert two_step.is_enrolled(db, UID), "--dry-run cleared the enrolment"


# ── the refusals. A tool that cannot refuse is a tool that clears strangers ──

def test_an_unknown_email_refuses_and_clears_nothing(enrolled_user, db):
    r = _run("--email", "nobody-here@testco.example.com", "--company-slug", "testco")
    assert r.returncode == 2, f"expected refusal, got {r.returncode}: {r.stdout}"
    db.expire_all()
    assert two_step.is_enrolled(db, UID), "a miss cleared somebody else"


def test_an_unknown_slug_refuses(enrolled_user, db):
    r = _run("--email", EMAIL, "--company-slug", "no-such-tenant")
    assert r.returncode == 2, r.stdout
    db.expire_all()
    assert two_step.is_enrolled(db, UID)


def test_the_same_email_in_another_tenant_is_not_touched(enrolled_user, db):
    """⚠️ `users` is unique on (email, company_id), NOT on email.

    This is why there is no email-only mode: one address can exist in several
    tenants, and an email-only lookup would clear a stranger's second factor
    in the same breath as your own.
    """
    other_id = "recov-other-tenant-co"
    other_uid = "recov-other-tenant-user"
    try:
        db.execute(text(
            # `companies.updated_at` is NOT NULL — omitting it aborted the
            # transaction and cascaded into this test's own teardown.
            "INSERT INTO companies (id, name, slug, created_at, updated_at) "
            "VALUES (:i,'Recov Other','recov-other',NOW(),NOW()) "
            "ON CONFLICT DO NOTHING"),
            {"i": other_id})
        rid = db.execute(text("SELECT role_id FROM users WHERE id=:u"), {"u": UID}).scalar()
        db.execute(text("DELETE FROM users WHERE id=:u"), {"u": other_uid})
        db.execute(text(
            "INSERT INTO users (id, company_id, email, hashed_password, first_name, "
            "last_name, role_id, is_active, created_at, updated_at) "
            "VALUES (:u,:c,:e,'x','Other','Tenant',:r,TRUE,NOW(),NOW())"),
            {"u": other_uid, "c": other_id, "e": EMAIL, "r": rid})
        db.commit()

        # clearing in testco must leave the same email in the other tenant alone
        assert _run("--email", EMAIL, "--company-slug", "testco").returncode == 0
        still = db.execute(text("SELECT count(*) FROM users WHERE id=:u"),
                           {"u": other_uid}).scalar()
        assert still == 1, "the other tenant's user was removed"
    finally:
        # ⚠️ roll back first: if the body aborted the transaction, every
        # cleanup statement would fail too and the error would be reported
        # against the teardown rather than the cause.
        db.rollback()
        db.execute(text("DELETE FROM users WHERE id=:u"), {"u": other_uid})
        db.execute(text("DELETE FROM companies WHERE id=:i"), {"i": other_id})
        db.commit()


def test_there_is_no_bulk_mode(enrolled_user):
    """The absent flag IS the guard. A validated `--all` would be a hole with
    a check on it; an absent one is not a hole."""
    for flag in ("--all", "--everyone", "--all-users"):
        r = _run(flag, "--company-slug", "testco")
        assert r.returncode != 0, f"{flag} was accepted"
