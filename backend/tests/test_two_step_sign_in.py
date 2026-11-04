"""Two-step sign-in: required by permission, enforced on every token path.

⚠️ **ENFORCEMENT IS ON USE, NOT ISSUANCE, AND THAT IS WHAT MAKES ONE CHECK
ENOUGH.** Four paths mint a tenant token — login, the production-track login,
refresh, and impersonation's raw `jwt.encode` — and a fifth added later would
escape an issuance-side guard silently. These tests therefore attack the token,
not the login form: a token that has not passed a second step must be unusable
for payroll no matter how it was made.

Measured on production 2026-11-03: 5 of 18 users hold a payroll permission, four
of them admins by the `get_user_permissions` wildcard. So the required set is
mostly people with unlimited roles — which is why the guard checks two-step
BEFORE its unlimited-role early return, and why that ordering has its own test.
"""
from __future__ import annotations

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core import two_step
from app.core.security import create_access_token, create_refresh_token
from app.main import app
from app.models.user import User
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

_canonical_tenant = make_canonical_tenant_fixture()

H = {"X-Company-Slug": "testco"}
PAYROLL_EP = "/api/v1/payroll-reports/formats"
ENROL_EP = "/api/v1/two-step/status"
PROBE = [
    "/api/v1/journal-entries/entries",
    "/api/v1/price-management/versions",
    "/api/v1/companies",
    "/api/v1/fh/cases",
    "/api/v1/email/threads",
]

REQUIRED_UID = "ts-required-user"      # on the payroll role -> requires two-step
OPTIONAL_UID = "ts-optional-user"      # on office -> does not


def _auth(token):
    return {"Authorization": f"Bearer {token}", **H}


@pytest.fixture(scope="module")
def users():
    from app.database import SessionLocal
    from app.services.role_service import seed_default_roles

    db = SessionLocal()
    try:
        seed_default_roles(db, TESTCO_ID)
        db.commit()
        ids = {}
        for slug, uid in (("payroll", REQUIRED_UID), ("office", OPTIONAL_UID)):
            rid = db.execute(text(
                "SELECT id FROM roles WHERE company_id=:c AND slug=:s LIMIT 1"
            ), {"c": TESTCO_ID, "s": slug}).scalar()
            if rid is None:
                pytest.skip(f"testco has no '{slug}' role")
            db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM user_recovery_codes WHERE user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM user_two_step WHERE user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
            db.add(User(id=uid, email=f"{uid}@testco.example.com",
                        hashed_password="not-a-credential", first_name="Two",
                        last_name="Step", role_id=rid, company_id=TESTCO_ID))
            ids[slug] = uid
        db.commit()
        yield ids
    finally:
        for uid in (REQUIRED_UID, OPTIONAL_UID):
            db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM user_recovery_codes WHERE user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM user_two_step WHERE user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
        db.commit()
        db.close()


def _set_tenant_two_step(on: bool):
    """Turn the per-tenant payroll two-step requirement on or off for testco."""
    from app.database import SessionLocal
    from app.models.company import Company
    db = SessionLocal()
    try:
        co = db.query(Company).filter(Company.id == TESTCO_ID).first()
        co.set_setting(two_step.TWO_STEP_TENANT_SETTING, on)
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _unenrol(users):
    """Each test starts un-enrolled AND with the requirement ON.

    ⚠️ **THE MODULE'S BASELINE IS "REQUIREMENT ON", WHICH IS NOT THE PRODUCT
    DEFAULT.** James's ruling of 2026-11-04 made it OFF by default per tenant —
    optional for everyone. But this file exists to test the enforcement
    machinery, and machinery switched off cannot be tested; a baseline of "off"
    would have turned 16 real assertions into vacuous passes. So enforcement is
    on here, and the tests that pin the NEW default call
    `_set_tenant_two_step(False)` IN THE BODY rather than through a fixture —
    explicitly, because fixture ordering between an autouse and a named one at
    the same scope is not something to rely on for a value that decides whether
    an assertion means anything.
    """
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        for uid in (REQUIRED_UID, OPTIONAL_UID):
            db.execute(text("DELETE FROM user_recovery_codes WHERE user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM user_two_step WHERE user_id=:u"), {"u": uid})
        db.commit()
    finally:
        db.close()
    _set_tenant_two_step(True)
    yield
    _set_tenant_two_step(False)   # leave the tenant in the product default


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _tok(uid, *, mfa=False):
    data = {"sub": uid, "company_id": TESTCO_ID}
    if mfa:
        data["mfa"] = True
    return create_access_token(data)


# ───────────────────────────────── the predicate follows the permission


def test_the_requirement_is_a_permission_prefix_not_a_role_list(users):
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        req = db.query(User).filter(User.id == REQUIRED_UID).first()
        opt = db.query(User).filter(User.id == OPTIONAL_UID).first()
        assert two_step.requires_two_step(req, db) is True
        assert two_step.requires_two_step(opt, db) is False
    finally:
        db.close()


def test_a_per_user_override_alone_makes_it_required(users):
    """⚠️ The point of a prefix match over `get_user_permissions`: one grant to
    one person, no role change, and the requirement follows."""
    from app.database import SessionLocal
    from app.models.user_permission_override import UserPermissionOverride
    db = SessionLocal()
    try:
        opt = db.query(User).filter(User.id == OPTIONAL_UID).first()
        assert two_step.requires_two_step(opt, db) is False
        db.add(UserPermissionOverride(
            user_id=OPTIONAL_UID, permission_key="payroll.view", granted=True))
        db.commit()
        db.expire_all()
        opt = db.query(User).filter(User.id == OPTIONAL_UID).first()
        assert two_step.requires_two_step(opt, db) is True
    finally:
        db.execute(text("DELETE FROM user_permission_overrides WHERE user_id=:u"),
                   {"u": OPTIONAL_UID})
        db.commit()
        db.close()


# ─────────────────────────────────────────────── BREAK TEST 1: password-only


def test_password_only_token_is_refused_payroll_and_allowed_enrolment(client, users):
    """⚠️ BREAK TEST. Without the guard's two-step branch this returned 200."""
    t = _tok(REQUIRED_UID, mfa=False)

    r = client.get(PAYROLL_EP, headers=_auth(t))
    assert r.status_code == 403, f"payroll reachable without a second step: {r.text[:200]}"
    detail = r.json()["detail"]
    assert detail["code"] == "two_step_required", (
        f"refused, but not for the two-step reason: {detail}"
    )
    assert detail["allowed_areas"] == ["mfa_enroll"]

    # ...and enrolment IS reachable, or she could never finish.
    e = client.get(ENROL_EP, headers=_auth(t))
    assert e.status_code == 200, f"enrolment unreachable: {e.text[:200]}"
    assert e.json() == {"required": True, "enrolled": False, "unused_recovery_codes": 0}


def test_a_required_user_is_confined_even_on_an_unlimited_role(client, users):
    """⚠️ THE ORDERING TEST. Four of the five required users on production hold
    UNLIMITED roles, so a guard that returned early for `limited_to_areas IS
    NULL` before checking two-step would exempt exactly them."""
    from app.database import SessionLocal
    from app.models.user_permission_override import UserPermissionOverride
    db = SessionLocal()
    try:
        # office is unlimited; grant it a payroll key so it is required too.
        db.add(UserPermissionOverride(
            user_id=OPTIONAL_UID, permission_key="payroll.view", granted=True))
        db.commit()
        assert db.execute(text(
            "SELECT limited_to_areas IS NULL FROM roles r JOIN users u "
            "ON u.role_id=r.id WHERE u.id=:u"), {"u": OPTIONAL_UID}).scalar() is True

        r = client.get(PROBE[0], headers=_auth(_tok(OPTIONAL_UID, mfa=False)))
        assert r.status_code == 403, "an unlimited role escaped the two-step check"
        assert r.json()["detail"]["code"] == "two_step_required"
    finally:
        db.execute(text("DELETE FROM user_permission_overrides WHERE user_id=:u"),
                   {"u": OPTIONAL_UID})
        db.commit()
        db.close()


# ────────────────────────────────────────── BREAK TEST 2: the refresh path


def test_a_pre_enrolment_refresh_token_cannot_mint_payroll_reach(client, users):
    """⚠️ BREAK TEST, AND THE SUBTLEST OF THEM. Refresh mints a full access
    token from no credential at all. A refresh token issued BEFORE two-step was
    required must never yield an access token that reaches payroll, or the
    second step is decorative for everyone already signed in."""
    pre = create_refresh_token({"sub": REQUIRED_UID, "company_id": TESTCO_ID})

    r = client.post("/api/v1/auth/refresh", headers=H, json={"refresh_token": pre})
    assert r.status_code == 200, f"refresh failed outright: {r.status_code} {r.text[:200]}"
    new_access = r.json()["access_token"]

    p = client.get(PAYROLL_EP, headers=_auth(new_access))
    assert p.status_code == 403, (
        "a pre-two-step refresh token minted an access token with payroll reach"
    )
    assert p.json()["detail"]["code"] == "two_step_required"


def test_refresh_carries_the_claim_forward_when_it_has_it(client, users):
    """The other half: once she has passed a second step, an ordinary refresh
    must not throw her back to enrolment on every token rotation."""
    post = create_refresh_token({"sub": REQUIRED_UID, "company_id": TESTCO_ID,
                                 "mfa": True})
    r = client.post("/api/v1/auth/refresh", headers=H, json={"refresh_token": post})
    assert r.status_code == 200, r.text[:200]
    from app.core.security import decode_token
    assert decode_token(r.json()["access_token"]).get("mfa") is True
    assert decode_token(r.json()["refresh_token"]).get("mfa") is True


def test_a_truthy_non_boolean_mfa_claim_does_not_satisfy(client, users):
    """`is True`, not truthiness — so `mfa: "yes"` cannot smuggle payroll reach."""
    for bad in ("yes", 1, "true", [1]):
        t = create_access_token({"sub": REQUIRED_UID, "company_id": TESTCO_ID,
                                 "mfa": bad})
        r = client.get(PAYROLL_EP, headers=_auth(t))
        assert r.status_code == 403, f"mfa={bad!r} satisfied the second step"


# ──────────────────────────────────── BREAK TEST 3: enrolment unlocks payroll


def test_completed_enrolment_makes_payroll_reachable(client, users):
    """⚠️ THE ALLOW PATH. Without it the guard could be a blanket deny and every
    refusal test above would still pass — which is an outage, not a feature."""
    t = _tok(REQUIRED_UID, mfa=False)

    begun = client.post("/api/v1/two-step/begin", headers=_auth(t))
    assert begun.status_code == 200, begun.text[:300]
    secret = begun.json()["secret"]
    assert begun.json()["provisioning_uri"].startswith("otpauth://totp/")

    code = pyotp.TOTP(secret).now()
    done = client.post("/api/v1/two-step/confirm", headers=_auth(t),
                       json={"code": code})
    assert done.status_code == 200, done.text[:300]
    body = done.json()
    assert len(body["recovery_codes"]) == two_step.RECOVERY_CODE_COUNT
    assert len(set(body["recovery_codes"])) == two_step.RECOVERY_CODE_COUNT, "duplicates"

    # The token returned by confirm carries the claim, and reaches payroll.
    p = client.get(PAYROLL_EP, headers=_auth(body["access_token"]))
    assert p.status_code == 200, f"still refused after enrolling: {p.text[:300]}"

    # And the OLD password-only token still does not.
    assert client.get(PAYROLL_EP, headers=_auth(t)).status_code == 403, (
        "enrolling retroactively upgraded a token that never passed a second step"
    )


def test_verify_exchanges_a_first_step_token_for_a_second_step_one(client, users):
    t = _tok(REQUIRED_UID, mfa=False)
    secret = client.post("/api/v1/two-step/begin", headers=_auth(t)).json()["secret"]
    client.post("/api/v1/two-step/confirm", headers=_auth(t),
                json={"code": pyotp.TOTP(secret).now()})

    v = client.post("/api/v1/two-step/verify", headers=_auth(t),
                    json={"code": pyotp.TOTP(secret).now()})
    assert v.status_code == 200, v.text[:300]
    assert client.get(PAYROLL_EP, headers=_auth(v.json()["access_token"])).status_code == 200

    bad = client.post("/api/v1/two-step/verify", headers=_auth(t),
                      json={"code": "000000"})
    assert bad.status_code == 401


def test_an_enrolled_secret_cannot_be_replaced_from_a_signed_in_session(client, users):
    """Re-issuing an enrolled secret would be a way to swap the second factor
    using only the first."""
    t = _tok(REQUIRED_UID, mfa=False)
    secret = client.post("/api/v1/two-step/begin", headers=_auth(t)).json()["secret"]
    client.post("/api/v1/two-step/confirm", headers=_auth(t),
                json={"code": pyotp.TOTP(secret).now()})
    again = client.post("/api/v1/two-step/begin", headers=_auth(t))
    assert again.status_code == 409, again.text[:200]


# ───────────────────────────────── BREAK TEST 4: recovery codes, single use


def test_a_recovery_code_works_once_and_the_second_use_is_refused(client, users):
    t = _tok(REQUIRED_UID, mfa=False)
    secret = client.post("/api/v1/two-step/begin", headers=_auth(t)).json()["secret"]
    codes = client.post("/api/v1/two-step/confirm", headers=_auth(t),
                        json={"code": pyotp.TOTP(secret).now()}).json()["recovery_codes"]

    first = client.post("/api/v1/two-step/recovery", headers=_auth(t),
                        json={"code": codes[0]})
    assert first.status_code == 200, first.text[:300]
    assert first.json()["recovery_codes_remaining"] == 9
    assert client.get(PAYROLL_EP,
                      headers=_auth(first.json()["access_token"])).status_code == 200

    second = client.post("/api/v1/two-step/recovery", headers=_auth(t),
                         json={"code": codes[0]})
    assert second.status_code == 401, "a recovery code was accepted twice"

    # A different, unused code still works — the first's consumption is specific.
    other = client.post("/api/v1/two-step/recovery", headers=_auth(t),
                        json={"code": codes[1]})
    assert other.status_code == 200
    assert other.json()["recovery_codes_remaining"] == 8


def test_recovery_codes_are_stored_hashed(client, users):
    """They are shown once and never again, so the stored form must not be the
    shown form."""
    from app.database import SessionLocal
    t = _tok(REQUIRED_UID, mfa=False)
    secret = client.post("/api/v1/two-step/begin", headers=_auth(t)).json()["secret"]
    codes = client.post("/api/v1/two-step/confirm", headers=_auth(t),
                        json={"code": pyotp.TOTP(secret).now()}).json()["recovery_codes"]
    db = SessionLocal()
    try:
        stored = [r[0] for r in db.execute(text(
            "SELECT code_hash FROM user_recovery_codes WHERE user_id=:u"
        ), {"u": REQUIRED_UID}).fetchall()]
    finally:
        db.close()
    assert len(stored) == 10
    for plain in codes:
        assert plain not in stored, "a recovery code is stored in plaintext"
    assert all(h.startswith("$2") for h in stored), "not bcrypt"


def test_the_totp_secret_is_stored_encrypted_not_plaintext(client, users):
    from app.database import SessionLocal
    t = _tok(REQUIRED_UID, mfa=False)
    secret = client.post("/api/v1/two-step/begin", headers=_auth(t)).json()["secret"]
    db = SessionLocal()
    try:
        stored = db.execute(text(
            "SELECT totp_secret_encrypted FROM user_two_step WHERE user_id=:u"
        ), {"u": REQUIRED_UID}).scalar()
    finally:
        db.close()
    assert stored != secret, "the TOTP secret is stored in plaintext"
    from app.core.security import decrypt_totp_secret
    assert decrypt_totp_secret(stored) == secret, "round trip broken"


# ──────────────────────────────── BREAK TEST 5: reset rules and auditing


def test_clearing_your_own_two_step_is_refused(client, users):
    """⚠️ Otherwise the requirement is optional for exactly the people who hold
    every permission — four of the five required on production are admins."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        admin_rid = db.execute(text(
            "SELECT id FROM roles WHERE company_id=:c AND slug='admin' LIMIT 1"
        ), {"c": TESTCO_ID}).scalar()
        db.execute(text("DELETE FROM audit_logs WHERE user_id='ts-admin'"))
        db.execute(text("DELETE FROM users WHERE id='ts-admin'"))
        db.add(User(id="ts-admin", email="ts-admin@testco.example.com",
                    hashed_password="x", first_name="TS", last_name="Admin",
                    role_id=admin_rid, company_id=TESTCO_ID))
        db.commit()
        admin_t = _tok("ts-admin", mfa=True)
        r = client.post("/api/v1/users/ts-admin/two-step/reset", headers=_auth(admin_t))
        assert r.status_code == 400, r.text[:200]
        assert "cannot reset your own" in r.text
    finally:
        db.execute(text("DELETE FROM audit_logs WHERE user_id='ts-admin'"))
        db.execute(text("DELETE FROM user_two_step WHERE user_id='ts-admin'"))
        db.execute(text("DELETE FROM users WHERE id='ts-admin'"))
        db.commit()
        db.close()


def test_admin_reset_of_another_user_clears_it_and_is_audited(client, users):
    import json as _json
    from app.database import SessionLocal

    t = _tok(REQUIRED_UID, mfa=False)
    secret = client.post("/api/v1/two-step/begin", headers=_auth(t)).json()["secret"]
    client.post("/api/v1/two-step/confirm", headers=_auth(t),
                json={"code": pyotp.TOTP(secret).now()})

    db = SessionLocal()
    try:
        admin_rid = db.execute(text(
            "SELECT id FROM roles WHERE company_id=:c AND slug='admin' LIMIT 1"
        ), {"c": TESTCO_ID}).scalar()
        db.execute(text("DELETE FROM audit_logs WHERE user_id='ts-admin2'"))
        db.execute(text("DELETE FROM users WHERE id='ts-admin2'"))
        db.add(User(id="ts-admin2", email="ts-admin2@testco.example.com",
                    hashed_password="x", first_name="TS", last_name="Admin2",
                    role_id=admin_rid, company_id=TESTCO_ID))
        db.commit()

        r = client.post(f"/api/v1/users/{REQUIRED_UID}/two-step/reset",
                        headers=_auth(_tok("ts-admin2", mfa=True)))
        assert r.status_code == 200, r.text[:300]
        assert r.json()["had_enrolment"] is True
        assert two_step.is_enrolled(db, REQUIRED_UID) is False
        assert two_step.unused_recovery_code_count(db, REQUIRED_UID) == 0, (
            "reset left recovery codes behind — they would still unlock payroll"
        )

        rows = db.execute(text(
            "SELECT changes, user_id FROM audit_logs WHERE action='two_step_reset' "
            "AND entity_id=:e ORDER BY created_at DESC LIMIT 1"
        ), {"e": REQUIRED_UID}).fetchall()
        assert rows, "the reset left no audit row"
        ch = rows[0][0]
        if isinstance(ch, str):
            ch = _json.loads(ch)
        assert ch["reset_by"] == "ts-admin2" and ch["reset_for"] == REQUIRED_UID, (
            "actor and subject must be recorded separately"
        )
        assert rows[0][1] == "ts-admin2"
    finally:
        db.execute(text("DELETE FROM audit_logs WHERE user_id='ts-admin2'"))
        db.execute(text("DELETE FROM users WHERE id='ts-admin2'"))
        db.commit()
        db.close()


# ─────────────────────────────── BREAK TEST 6: the optional users are untouched


def test_an_optional_user_is_completely_unaffected(client, users):
    """⚠️ SETS, NOT COUNTS. 13 of 18 production users hold no payroll permission
    and must see no change at all — not a prompt, not a refusal, nothing."""
    t = _tok(OPTIONAL_UID, mfa=False)
    results = {p: client.get(p, headers=_auth(t)).status_code for p in PROBE}

    for path, code in results.items():
        if code != 403:
            continue
        body = client.get(path, headers=_auth(t)).json()
        detail = body.get("detail") if isinstance(body, dict) else None
        assert not (isinstance(detail, dict)
                    and detail.get("code") in ("two_step_required", "area_restricted")), (
            f"{path} was refused by the two-step/area guard for an optional user"
        )

    assert any(c == 200 for c in results.values()), (
        f"the optional user reaches nothing, so this proves nothing: {results}"
    )
    # And status reports her as not required, so the frontend will not nag her.
    s = client.get(ENROL_EP, headers=_auth(t))
    assert s.status_code == 200
    assert s.json()["required"] is False


def test_impersonation_tokens_are_marked_and_recorded(users):
    """Approved bypass, written down. The claim is on the token AND the fact is
    on the session row, so a payroll-reaching token that skipped a second step
    is answerable later."""
    import inspect
    from app.services.admin import impersonation_service as imp
    src = inspect.getsource(imp)
    assert '"mfa": True' in src, "impersonation no longer marks the token"
    assert "session.mfa_satisfied_by_admin = True" in src, (
        "the bypass is no longer recorded on the session row"
    )
    from app.models.admin_impersonation_session import AdminImpersonationSession
    assert "mfa_satisfied_by_admin" in AdminImpersonationSession.__table__.columns


# ── ruling 5: the non-production seed enrolment ──────────────────────────

def test_the_seed_enrolment_refuses_when_the_env_var_says_production(users, monkeypatch):
    """⚠️ THE GUARD THE RULING NAMES.

    James, 2026-11-03: *"In non-production only, seeds may enrol with a fixed
    known secret so tests and demos keep working; a test asserts that path
    cannot run when ENVIRONMENT is production."*

    The secret is published in the repository, so this refusal is the only thing
    standing between a committed string and a real payroll account.
    """
    from app.database import SessionLocal

    monkeypatch.setenv("ENVIRONMENT", "production")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == REQUIRED_UID).first()
        with pytest.raises(two_step.ProductionEnrolmentRefused):
            two_step.enrol_for_non_production(db, user)
    finally:
        db.rollback()
        db.close()


def test_the_refusal_is_case_insensitive(users, monkeypatch):
    from app.database import SessionLocal

    monkeypatch.setenv("ENVIRONMENT", "PRODUCTION")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == REQUIRED_UID).first()
        with pytest.raises(two_step.ProductionEnrolmentRefused):
            two_step.enrol_for_non_production(db, user)
    finally:
        db.rollback()
        db.close()


def test_the_refusal_also_reads_settings_not_only_the_env_var(users, monkeypatch):
    """The second half of the deny-union.

    `settings` is read once at import, so a process started with ENVIRONMENT
    already set sees it there and a later `os.environ` write does not reach it.
    Either source saying production must refuse — the stricter reading wins.
    """
    from app.config import settings
    from app.database import SessionLocal

    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setattr(settings, "ENVIRONMENT", "production", raising=False)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == REQUIRED_UID).first()
        with pytest.raises(two_step.ProductionEnrolmentRefused):
            two_step.enrol_for_non_production(db, user)
    finally:
        db.rollback()
        db.close()


def test_the_seed_enrolment_works_outside_production(users, monkeypatch):
    """Positive control: the refusal above is a refusal, not a dead function.

    ⚠️ Without this, `test_..._refuses_when_...production` is satisfied just as
    well by a function that raises unconditionally — which would pass the
    ruling's test and break every demo.
    """
    from app.database import SessionLocal

    monkeypatch.setenv("ENVIRONMENT", "dev")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == REQUIRED_UID).first()
        row = two_step.enrol_for_non_production(db, user)
        db.commit()
        assert row.enrolled_at is not None
        assert two_step.is_enrolled(db, REQUIRED_UID)
        # The code the seed publishes actually verifies.
        code = two_step.non_production_totp_code()
        assert two_step.verify_totp(db, REQUIRED_UID, code) is True
    finally:
        db.close()


def test_the_published_secret_is_the_one_the_helper_computes(monkeypatch):
    """One secret, not two that happen to agree today."""
    expected = pyotp.TOTP(two_step.NON_PRODUCTION_TOTP_SECRET).now()
    assert two_step.non_production_totp_code() == expected


def test_a_seeded_enrolment_still_does_not_get_her_past_the_guard(
    users, client, monkeypatch
):
    """⚠️ ENROLMENT IS NOT A PASS. THE CLAIM ON THE TOKEN IS.

    This pins the sentence in `enrol_for_non_production`'s docstring. A demo
    admin enrolled by a seed still signs in, still gets a claimless token, and
    is still confined to `mfa_enroll` — because the guard reads the token, not
    the row. What the seed buys is a COMPUTABLE code, not an exemption.

    If this ever goes green the other way, the guard has started trusting
    enrolment state and a stolen password is once again sufficient.
    """
    from app.database import SessionLocal

    monkeypatch.setenv("ENVIRONMENT", "dev")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == REQUIRED_UID).first()
        two_step.enrol_for_non_production(db, user)
        db.commit()
    finally:
        db.close()

    r = client.get(PAYROLL_EP, headers=_auth(_tok(REQUIRED_UID, mfa=False)))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["code"] == "two_step_required", r.text

    # And with the claim, through.
    ok = client.get(PAYROLL_EP, headers=_auth(_tok(REQUIRED_UID, mfa=True)))
    assert ok.status_code != 403, ok.text


def test_an_optional_users_probe_results_are_identical_with_and_without_the_claim(
    client, users
):
    """⚠️ THE DISPATCH'S BREAK TEST, AS A SET COMPARISON.

    James: *"Optional users (the 13): login and probe results identical before
    and after, compared as sets."*

    "Before and after" needs no A/B for an optional user, because the `mfa`
    claim is the ONLY variable two-step introduces into her requests. If the
    requirement leaked onto her by any route — a role list, a default, a
    mis-ordered branch — the claimless set and the claimed set would differ.
    Identical sets is the whole claim.

    ⚠️ Compared as SETS of `(path, status)` pairs, not as counts. Equal
    cardinalities pass while membership is wrong, which is exactly how a
    guard that refuses one endpoint and starts permitting another would slip
    through a count comparison.

    ⚠️ AND IT CARRIES A NON-ZERO CONTROL. Two empty sets are identical, and a
    probe list that reached nothing would satisfy this test perfectly while
    proving nothing at all.
    """
    without = {(p, client.get(p, headers=_auth(_tok(OPTIONAL_UID, mfa=False))).status_code)
               for p in PROBE}
    with_claim = {(p, client.get(p, headers=_auth(_tok(OPTIONAL_UID, mfa=True))).status_code)
                  for p in PROBE}

    # CONTROL: she must actually reach something, or both sets are vacuous.
    assert any(code == 200 for _, code in without), (
        f"the optional user reaches nothing, so identity proves nothing: {without}"
    )
    assert len(without) == len(PROBE), (
        f"the probe list has duplicate paths, so the set is smaller than it looks: {without}"
    )

    assert without == with_claim, (
        "an optional user's reach changed with the mfa claim, so the "
        f"requirement has leaked onto her.\n  only without: {without - with_claim}"
        f"\n  only with:    {with_claim - without}"
    )


def test_an_optional_user_can_still_sign_in_with_only_a_password(client, users):
    """The login half of the same break test.

    Her password alone must still produce a usable token — no second step, no
    enrolment detour. Uses the real login endpoint rather than a minted token,
    because the claim is issued there and this is the path that must not have
    acquired a step.
    """
    from app.core.security import hash_password
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == OPTIONAL_UID).first()
        user.hashed_password = hash_password("OptionalUserPassword123")
        db.commit()
        email = user.email
    finally:
        db.close()

    r = client.post("/api/v1/auth/login", headers=H,
                    json={"email": email, "password": "OptionalUserPassword123"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]

    # ⚠️ The token from a plain password login carries NO claim — verified
    # directly, so this test cannot pass because login started adding one.
    from app.core.security import decode_token
    assert decode_token(token).get("mfa") is not True, (
        "login minted a token carrying the mfa claim; the second step is no "
        "longer a second step"
    )

    # And it reaches what she could always reach.
    reached = {p: client.get(p, headers=_auth(token)).status_code for p in PROBE}
    assert any(c == 200 for c in reached.values()), reached


def test_a_verified_limited_user_can_still_manage_her_own_two_step(client, users):
    """⚠️ THE ENROLMENT AREA MUST STAY REACHABLE AFTER SHE PASSES THE STEP.

    Found by reading the allowed-set computation rather than by a failure, then
    confirmed here. The payroll role is area-limited (`r223` ships it with
    `limited_to_areas = ['payroll']`), so once she holds the claim the guard
    takes the third branch and `allowed` is exactly `{'payroll'}` — which does
    NOT contain `mfa_enroll`. Before the fix, verifying locked her out of the
    endpoints that report her remaining recovery codes and would let her
    re-enrol on a new phone.

    Note the shape: the FIRST branch grants `mfa_enroll` to someone who owes a
    step, so the area was reachable exactly while she was confined and became
    unreachable the moment she complied. That is the kind of gap a happy-path
    test walks straight past, because the happy path reloads onto `/` and never
    asks again.
    """
    r = client.get(ENROL_EP, headers=_auth(_tok(REQUIRED_UID, mfa=True)))
    assert r.status_code == 200, (
        "a verified payroll-limited user cannot reach her own two-step "
        f"settings: {r.status_code} {r.text}"
    )
    body = r.json()
    assert body["required"] is True
    assert "unused_recovery_codes" in body


def test_the_enrolment_area_does_not_widen_her_reach(client, users):
    """The control on the fix above: granting `mfa_enroll` grants ONLY that.

    ⚠️ Without this, the fix could have been "add `mfa_enroll`" written as
    "stop restricting her", and a test asserting she reaches her settings
    would pass under both.
    """
    t = _tok(REQUIRED_UID, mfa=True)
    for path in PROBE:
        code = client.get(path, headers=_auth(t)).status_code
        if code == 403:
            continue
        body = client.get(path, headers=_auth(t)).json()
        detail = body.get("detail") if isinstance(body, dict) else None
        assert not (isinstance(detail, dict) and detail.get("code") == "area_restricted"), path
    # She is on a limited role, so at least one probe must still be refused —
    # otherwise this test is vacuous and the fix did widen her reach.
    codes = [client.get(p, headers=_auth(t)).status_code for p in PROBE]
    assert 403 in codes, (
        f"a payroll-limited user now reaches every probe path: {dict(zip(PROBE, codes))}"
    )


# ── the emergency off switch (James, 2026-11-04) ─────────────────────────

def test_the_off_switch_lets_a_required_user_through(client, users, monkeypatch):
    """⚠️ THE WAY BACK IN IF ENROLMENT BREAKS ON PRODUCTION.

    James's ruling of 2026-11-04: his first use of two-step is on production,
    and a bug in enrolment would lock out Sunnycrest's only admin until a fix
    deployed. So there is a Railway variable that skips the requirement with
    **no code deploy**, and this test is the thing that says it works.

    If this test ever fails, the recovery path is gone and the change should
    not ship.
    """
    monkeypatch.setenv(two_step.TWO_STEP_ENFORCED_ENV, "false")
    r = client.get(PAYROLL_EP, headers=_auth(_tok(REQUIRED_UID, mfa=False)))
    assert r.status_code != 403, (
        f"the off switch did not restore access: {r.status_code} {r.text}"
    )


def test_the_off_switch_is_reported_consistently_everywhere(client, users, monkeypatch):
    """⚠️ Not just the refusal — the three surfaces that TELL users about it.

    The switch is read in `requires_two_step`, the single predicate, so
    `/two-step/status` stops saying `required` too. Had it been put in
    `enforce_area_limit` instead, the guard would have stopped refusing while
    the status endpoint still sent her to an enrolment page she did not need.
    """
    monkeypatch.setenv(two_step.TWO_STEP_ENFORCED_ENV, "false")
    s = client.get(ENROL_EP, headers=_auth(_tok(REQUIRED_UID, mfa=False)))
    assert s.status_code == 200, s.text
    assert s.json()["required"] is False


def test_every_request_served_with_the_switch_off_is_logged(client, users, monkeypatch, caplog):
    """⚠️ A SILENT BYPASS IS HOW A TEMPORARY SWITCH BECOMES A PERMANENT ONE.

    James required that every request served while it is off says so. One line
    per request is deliberate: the volume is the signal that an emergency state
    is still in force.
    """
    import logging as _logging

    monkeypatch.setenv(two_step.TWO_STEP_ENFORCED_ENV, "false")
    with caplog.at_level(_logging.WARNING, logger="app.core.two_step"):
        client.get(PAYROLL_EP, headers=_auth(_tok(REQUIRED_UID, mfa=False)))
    hits = [r for r in caplog.records if "TWO-STEP ENFORCEMENT DISABLED" in r.getMessage()]
    assert hits, (
        "a request was served without a second step and nothing was logged; "
        f"records seen: {[r.getMessage()[:60] for r in caplog.records]}"
    )
    assert two_step.TWO_STEP_ENFORCED_ENV in hits[0].getMessage()


@pytest.mark.parametrize("value", ["", "true", "TRUE", "flase", "disabled", "xyz", "1", "yes"])
def test_anything_but_an_explicit_disabling_value_still_enforces(
    client, users, monkeypatch, value
):
    """⚠️ FAIL SECURE. A typo must not turn the requirement off.

    The parse is a whitelist of disabling values, not a truthiness test, and
    this is the control that proves it. `"flase"` is in the list on purpose:
    it is the misspelling someone types at 2am during the incident the switch
    exists for.
    """
    monkeypatch.setenv(two_step.TWO_STEP_ENFORCED_ENV, value)
    r = client.get(PAYROLL_EP, headers=_auth(_tok(REQUIRED_UID, mfa=False)))
    assert r.status_code == 403, f"{value!r} disabled enforcement: {r.status_code}"
    assert r.json()["detail"]["code"] == "two_step_required"


def test_with_the_variable_absent_the_requirement_is_enforced(client, users, monkeypatch):
    """The default, stated as a test rather than left to the declaration."""
    monkeypatch.delenv(two_step.TWO_STEP_ENFORCED_ENV, raising=False)
    r = client.get(PAYROLL_EP, headers=_auth(_tok(REQUIRED_UID, mfa=False)))
    assert r.status_code == 403, r.text


def test_the_off_switch_changes_nothing_else(client, users, monkeypatch):
    """⚠️ "Everything else unchanged" is a claim, so it gets a test.

    With the switch off, an AREA-limited user must still be confined to her
    areas — the switch suspends the two-step requirement, not the area guard.
    A switch that quietly disabled both would be a far larger hole than the
    one it was opened to fix.
    """
    monkeypatch.setenv(two_step.TWO_STEP_ENFORCED_ENV, "false")
    t = _tok(REQUIRED_UID, mfa=False)
    codes = [client.get(p, headers=_auth(t)).status_code for p in PROBE]
    assert 403 in codes, (
        "with two-step off, the payroll-limited user now reaches every probe "
        f"path — the area guard was disabled too: {dict(zip(PROBE, codes))}"
    )
    for p, c in zip(PROBE, codes):
        if c != 403:
            continue
        d = client.get(p, headers=_auth(t)).json().get("detail")
        if isinstance(d, dict):
            assert d.get("code") == "area_restricted", (
                f"{p} refused for the wrong reason with the switch off: {d}"
            )


# ── optional for everyone, sticky for the enrolled (James, 2026-11-04) ───

def test_a_payroll_user_signs_in_with_a_password_only(client, users):
    """⚠️ JAMES'S BREAK TEST FOR THE 2026-11-04 RULING.

    *"Two-step is optional for everyone, including payroll users. Nobody is
    forced to enrol."* So a payroll-limited user with no enrolment and a
    claimless token must REACH payroll, not be sent to enrolment.

    The reasoning he gave: the same names, hours, rates and dues already sit
    behind one password in Payentry, so a second factor here was protecting a
    copy more carefully than the original.
    """
    _set_tenant_two_step(False)   # the product default, set in-body deliberately
    r = client.get(PAYROLL_EP, headers=_auth(_tok(REQUIRED_UID, mfa=False)))
    assert r.status_code != 403, (
        f"a payroll user was still refused without a second step: {r.text}"
    )


def test_status_reports_not_required_so_the_frontend_does_not_nag(client, users):
    _set_tenant_two_step(False)
    s = client.get(ENROL_EP, headers=_auth(_tok(REQUIRED_UID, mfa=False)))
    assert s.status_code == 200, s.text
    assert s.json()["required"] is False


def test_an_enrolled_user_is_still_asked_even_though_nobody_is_required(
    client, users, monkeypatch
):
    """⚠️ THE CLAUSE THAT KEEPS JAMES'S OWN ACCOUNT PROTECTED.

    His ruling has two halves — "nobody is forced to enrol" AND "users already
    enrolled keep using it" — and a predicate reading only the tenant switch
    honours the first while silently breaking the second: his token would carry
    no `mfa` claim, status would answer `required: false`, nothing would ask
    for a code, and his enrolment would be decorative while his account went
    back to password-only. That is the opposite of one of the three
    compensating controls he named for making two-step optional.

    So enrolment is STICKY: not required of anyone, used by anyone who has it.
    """
    _set_tenant_two_step(False)
    from app.database import SessionLocal

    monkeypatch.setenv("ENVIRONMENT", "dev")
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == REQUIRED_UID).first()
        two_step.enrol_for_non_production(db, user)
        db.commit()
    finally:
        db.close()

    # claimless token: he must be confined to enrolment despite the switch
    r = client.get(PAYROLL_EP, headers=_auth(_tok(REQUIRED_UID, mfa=False)))
    assert r.status_code == 403, (
        "an ENROLLED user was served without his second step — his enrolment "
        f"has become decorative: {r.status_code}"
    )
    assert r.json()["detail"]["code"] == "two_step_required"
    # and with the claim, through
    assert client.get(PAYROLL_EP, headers=_auth(_tok(REQUIRED_UID, mfa=True))).status_code != 403


def test_turning_the_tenant_switch_on_requires_it_again(client, users):
    """The requirement is not deleted, only switched off — it can come back."""
    try:
        _set_tenant_two_step(True)
        r = client.get(PAYROLL_EP, headers=_auth(_tok(REQUIRED_UID, mfa=False)))
        assert r.status_code == 403, r.text
        assert r.json()["detail"]["code"] == "two_step_required"
    finally:
        _set_tenant_two_step(False)


def test_the_tenant_switch_does_not_reach_a_non_payroll_user(client, users):
    """⚠️ The tenant decides WHETHER; the PERMISSION still decides WHO.

    This is why the setting is per-tenant rather than per-role: a role flag
    would compete with the permission prefix, and the two would disagree the
    first time somebody held a payroll key through a per-user override.
    """
    try:
        _set_tenant_two_step(True)
        t = _tok(OPTIONAL_UID, mfa=False)
        codes = {p: client.get(p, headers=_auth(t)).status_code for p in PROBE}
        assert any(c == 200 for c in codes.values()), f"vacuous: {codes}"
        for p, c in codes.items():
            if c != 403:
                continue
            d = client.get(p, headers=_auth(t)).json().get("detail")
            if isinstance(d, dict):
                assert d.get("code") != "two_step_required", f"{p} caught a non-payroll user"
    finally:
        _set_tenant_two_step(False)


def test_the_emergency_switch_beats_sticky_enrolment(client, users, monkeypatch):
    """⚠️ ORDERING, AND IT IS LOAD-BEARING.

    An admin locked out by a broken second step cannot be told "but you
    enrolled". So `TWO_STEP_ENFORCED=false` is checked BEFORE the enrolment
    check, not after.
    """
    from app.database import SessionLocal

    monkeypatch.setenv("ENVIRONMENT", "dev")
    db = SessionLocal()
    try:
        two_step.enrol_for_non_production(
            db, db.query(User).filter(User.id == REQUIRED_UID).first())
        db.commit()
    finally:
        db.close()
    monkeypatch.setenv(two_step.TWO_STEP_ENFORCED_ENV, "false")
    r = client.get(PAYROLL_EP, headers=_auth(_tok(REQUIRED_UID, mfa=False)))
    assert r.status_code != 403, (
        "the emergency switch did not override an existing enrolment — an "
        f"admin with a broken second step would stay locked out: {r.text}"
    )
