"""Tenant user invites: no password in a request body, no link in a response.

Payroll 2, ruling 4. The goal sentence is *"no tenant user's password ever
passes through a request body or a session"*, and these tests attack the two
ways that can fail: a password arriving in a body, and the INVITE LINK — which
is the same power as a password — leaving through a response, a log, or the
stored row.

⚠️ **THE HARDEST ASSERTION HERE IS AN ABSENCE, SO IT CARRIES A POSITIVE
CONTROL.** `test_the_token_is_nowhere_in_the_row` proves the plaintext token is
not stored. An absence check over a row is satisfied just as well by a search
that cannot see — so the same test first asserts the DIGEST *is* present, which
is the value the search would have to find if it worked.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.models.user import User
from app.services import tenant_invite
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture
from tests._two_step import tenant_token

_canonical_tenant = make_canonical_tenant_fixture()

H = {"X-Company-Slug": "testco"}

ADMIN_UID = "inv-admin-user"
OFFICE_UID = "inv-office-user"
INVITEE_EMAIL = "invitee@testco.example.com"
PAYROLL_INVITEE_EMAIL = "payroll-invitee@testco.example.com"


def _auth(token):
    return {"Authorization": f"Bearer {token}", **H}


def _cleanup(db):
    """Remove every row these tests create, in FK-safe order.

    ⚠️ INCLUDING THE DELIVERY ROWS, AND THAT IS NOT TIDINESS. Without it
    `test_the_invite_email_is_actually_dispatched` finds a `users.invite`
    delivery row left by an EARLIER run and passes on residue — I proved that
    by removing the `db.commit()` it exists to check and watching the test stay
    green. An assertion satisfied by a previous run's state cannot fail, which
    makes it documentation rather than a check.
    """
    db.execute(text(
        "DELETE FROM document_deliveries "
        "WHERE company_id = :c AND caller_module = 'users.invite'"),
        {"c": TESTCO_ID})
    for email in (INVITEE_EMAIL, PAYROLL_INVITEE_EMAIL):
        ids = [r[0] for r in db.execute(
            text("SELECT id FROM users WHERE email=:e AND company_id=:c"),
            {"e": email, "c": TESTCO_ID}).fetchall()]
        for uid in ids:
            db.execute(text("DELETE FROM audit_logs WHERE user_id=:u OR entity_id=:u"),
                       {"u": uid})
            db.execute(text("DELETE FROM employee_profiles WHERE user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
    db.commit()


@pytest.fixture(scope="module")
def actors():
    """An admin who may invite, and an office user who may not."""
    from app.database import SessionLocal
    from app.services.role_service import seed_default_roles

    db = SessionLocal()
    try:
        seed_default_roles(db, TESTCO_ID)
        db.commit()
        out = {}
        for slug, uid in (("admin", ADMIN_UID), ("office", OFFICE_UID)):
            rid = db.execute(text(
                "SELECT id FROM roles WHERE company_id=:c AND slug=:s LIMIT 1"
            ), {"c": TESTCO_ID, "s": slug}).scalar()
            if rid is None:
                pytest.skip(f"testco has no '{slug}' role")
            db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
            db.add(User(id=uid, email=f"{uid}@testco.example.com",
                        hashed_password="not-a-credential", first_name="Inv",
                        last_name=slug.title(), role_id=rid,
                        company_id=TESTCO_ID))
            out[slug] = uid
        db.commit()
        _cleanup(db)
        yield out
    finally:
        _cleanup(db)
        for uid in (ADMIN_UID, OFFICE_UID):
            db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
        db.commit()
        db.close()


@pytest.fixture(autouse=True)
def _clean_invitees(actors):
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        _cleanup(db)
    finally:
        db.close()
    yield


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture
def db():
    from app.database import SessionLocal
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _role_id(db, slug):
    return db.execute(text(
        "SELECT id FROM roles WHERE company_id=:c AND slug=:s LIMIT 1"
    ), {"c": TESTCO_ID, "s": slug}).scalar()


def _invite(db, slug="office", email=INVITEE_EMAIL):
    """Issue an invite through the service. Returns (user, token)."""
    from app.models.company import Company
    company = db.query(Company).filter(Company.id == TESTCO_ID).first()
    inviter = db.query(User).filter(User.id == ADMIN_UID).first()
    return tenant_invite.invite_user(
        db, company=company, inviter=inviter, email=email,
        first_name="Pat", last_name="Invitee", role_id=_role_id(db, slug),
    )


# ── the row the invite leaves behind ─────────────────────────────────────

def test_an_invited_user_has_no_password(actors, db):
    user, _ = _invite(db)
    db.expire_all()
    row = db.execute(text(
        "SELECT hashed_password, invite_token_hash, invite_accepted_at, "
        "invited_by_user_id FROM users WHERE id=:u"), {"u": user.id}).first()
    assert row[0] is None, "an invited user must have NO password, not a random one"
    assert row[1] is not None, "the invite hash must be stored"
    assert row[2] is None, "nothing has been accepted yet"
    assert row[3] == ADMIN_UID


def test_the_token_is_nowhere_in_the_row(actors, db):
    """The stored value is the digest. The token itself is unrecoverable.

    ⚠️ Positive control FIRST: the digest IS found. Without it, a query that
    could not see any column would satisfy the absence assertion below and read
    as proof.
    """
    user, token = _invite(db)
    digest = hashlib.sha256(token.encode()).hexdigest()

    row = db.execute(text(
        "SELECT * FROM users WHERE id=:u"), {"u": user.id}).mappings().first()
    values = [str(v) for v in row.values() if v is not None]

    # CONTROL: the instrument can see the column we care about.
    assert digest in values, "the digest should be stored — if not, this test is blind"
    assert len(values) > 5, f"suspiciously few readable columns: {len(values)}"

    # THE CLAIM.
    assert token not in values, "the plaintext invite token must never be stored"
    assert not any(token in v for v in values), "no column may embed the token"


def test_the_digest_is_sha256_of_the_token(actors, db):
    user, token = _invite(db)
    assert user.invite_token_hash == hashlib.sha256(token.encode()).hexdigest()


def test_the_expiry_is_72_hours(actors, db):
    user, _ = _invite(db)
    assert tenant_invite.INVITE_TTL_HOURS == 72
    delta = user.invite_token_expires_at - datetime.now(timezone.utc)
    assert timedelta(hours=71) < delta <= timedelta(hours=72)


# ── the admin endpoint ───────────────────────────────────────────────────

def test_the_response_carries_no_link_and_no_token(actors, client, db):
    r = client.post("/api/v1/users/invite", headers=_auth(tenant_token(ADMIN_UID, TESTCO_ID)),
                    json={"email": INVITEE_EMAIL, "first_name": "Pat",
                          "last_name": "Invitee", "role_id": _role_id(db, "office")})
    assert r.status_code == 201, r.text
    body = r.json()
    assert set(body) == {"user_id", "email", "expires_at", "email_sent",
                         "two_step_will_be_required"}, body
    blob = r.text.lower()
    for forbidden in ("token", "invite_url", "accept-invite", "password"):
        assert forbidden not in blob, f"the response leaks {forbidden!r}: {r.text}"


def test_a_supplied_password_is_refused_not_ignored(actors, client, db):
    """⚠️ REFUSED, AND THE DIFFERENCE MATTERS.

    My first version of this test accepted EITHER a 422 or a silent ignore, on
    the grounds that a password must only never reach the row. That is the
    weaker claim: a caller who POSTs a password, gets a 201 and is never told
    it was dropped has every reason to believe the account has that password.
    `extra="forbid"` on the request model makes it a 422 naming the field, and
    this test now pins the loud behaviour rather than tolerating both.
    """
    r = client.post("/api/v1/users/invite", headers=_auth(tenant_token(ADMIN_UID, TESTCO_ID)),
                    json={"email": INVITEE_EMAIL, "first_name": "Pat",
                          "last_name": "Invitee", "role_id": _role_id(db, "office"),
                          "password": "SomethingTheAdminChose123!"})
    assert r.status_code == 422, r.text
    assert "password" in r.text, f"the refusal does not name the field: {r.text}"

    # And nothing was created.
    n = db.execute(text(
        "SELECT count(*) FROM users WHERE email=:e AND company_id=:c"),
        {"e": INVITEE_EMAIL, "c": TESTCO_ID}).scalar()
    assert n == 0, "a refused invite still created a user"


def test_an_office_user_cannot_invite(actors, client, db):
    r = client.post("/api/v1/users/invite", headers=_auth(tenant_token(OFFICE_UID, TESTCO_ID)),
                    json={"email": INVITEE_EMAIL, "first_name": "Pat",
                          "last_name": "Invitee", "role_id": _role_id(db, "office")})
    assert r.status_code == 403, r.text


def test_a_role_from_another_tenant_is_refused(actors, client, db):
    other = db.execute(text(
        "SELECT id FROM roles WHERE company_id <> :c LIMIT 1"), {"c": TESTCO_ID}).scalar()
    if other is None:
        pytest.skip("no foreign role available to test with")
    r = client.post("/api/v1/users/invite", headers=_auth(tenant_token(ADMIN_UID, TESTCO_ID)),
                    json={"email": INVITEE_EMAIL, "first_name": "Pat",
                          "last_name": "Invitee", "role_id": other})
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["code"] == "unknown_role"


def test_invite_is_not_shadowed_by_the_user_id_route(client):
    """`POST /users/invite` must reach the invite handler, not `{user_id}`.

    ⚠️ It is declared AFTER `/users/{user_id}`, so it survives only because no
    `POST /users/{user_id}` exists. This asserts that empirically rather than by
    reading the file — adding one later would silently route invites into it,
    the same hazard CLAUDE.md records for the spaces `/affinity/*` routes.
    """
    posts = {r.path for r in app.routes
             if "POST" in (getattr(r, "methods", None) or set())
             and getattr(r, "path", "") == "/api/v1/users/{user_id}"}
    assert not posts, (
        "a POST /users/{user_id} now exists and shadows POST /users/invite — "
        "move /invite above the parameterised routes"
    )
    # And the route itself resolves.
    r = client.post("/api/v1/users/invite", headers=H, json={})
    assert r.status_code != 404, "the invite route is unreachable"


# ── the public accept flow ───────────────────────────────────────────────

def test_preview_greets_her(actors, client, db):
    _, token = _invite(db)
    r = client.get(f"/api/v1/invites/{token}", headers=H)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == INVITEE_EMAIL
    assert set(body) == {"email", "first_name", "last_name", "company_name"}
    # Nothing about the tenant's shape.
    assert "role" not in r.text.lower()


def test_accept_sets_her_password_and_consumes_the_invite(actors, client, db):
    user, token = _invite(db)
    r = client.post(f"/api/v1/invites/{token}/accept", headers=H,
                    json={"password": "SheChoseThisOne123"})
    assert r.status_code == 200, r.text

    db.expire_all()
    row = db.execute(text(
        "SELECT hashed_password, invite_token_hash, invite_accepted_at "
        "FROM users WHERE id=:u"), {"u": user.id}).first()
    assert row[0] is not None, "her password was not set"
    assert row[1] is None, "the invite hash must be CLEARED, not flagged"
    assert row[2] is not None, "acceptance was not stamped"


def test_the_link_works_once(actors, client, db):
    _, token = _invite(db)
    first = client.post(f"/api/v1/invites/{token}/accept", headers=H,
                        json={"password": "SheChoseThisOne123"})
    assert first.status_code == 200, first.text
    replay = client.post(f"/api/v1/invites/{token}/accept", headers=H,
                         json={"password": "SomebodyElseChoseThis123"})
    assert replay.status_code == 400, replay.text
    assert replay.json()["detail"]["code"] == "invite_invalid"


def test_an_expired_link_is_refused(actors, client, db):
    user, token = _invite(db)
    db.execute(text("UPDATE users SET invite_token_expires_at = :t WHERE id=:u"),
               {"t": datetime.now(timezone.utc) - timedelta(minutes=1), "u": user.id})
    db.commit()
    r = client.post(f"/api/v1/invites/{token}/accept", headers=H,
                    json={"password": "TooLateForThis123"})
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["code"] == "invite_invalid"


def test_every_bad_link_reads_the_same(actors, client, db):
    """Unknown, expired and consumed must be indistinguishable.

    The accept page is public, so a difference between them is an oracle for
    whether an address has an account.
    """
    user, consumed = _invite(db)
    client.post(f"/api/v1/invites/{consumed}/accept", headers=H,
                json={"password": "SheChoseThisOne123"})

    user2, expired = _invite(db, email=PAYROLL_INVITEE_EMAIL)
    db.execute(text("UPDATE users SET invite_token_expires_at = :t WHERE id=:u"),
               {"t": datetime.now(timezone.utc) - timedelta(minutes=1), "u": user2.id})
    db.commit()

    bodies = set()
    for tok in ("a-token-that-never-existed", consumed, expired):
        r = client.post(f"/api/v1/invites/{tok}/accept", headers=H,
                        json={"password": "WhateverGoesHere123"})
        assert r.status_code == 400, (tok, r.text)
        bodies.add(r.text)
    assert len(bodies) == 1, f"the three refusals differ: {bodies}"


def test_a_short_password_is_refused_on_its_own_terms(actors, client, db):
    _, token = _invite(db)
    r = client.post(f"/api/v1/invites/{token}/accept", headers=H, json={"password": "short"})
    assert r.status_code == 422, r.text   # the Field(min_length=...) refuses first
    # and the invite survives, so she can try again
    r2 = client.get(f"/api/v1/invites/{token}", headers=H)
    assert r2.status_code == 200, "a weak password must not burn the invite"


# ── the login seam: the None-password read ───────────────────────────────

def test_an_invited_user_cannot_sign_in_yet_and_does_not_500(actors, client, db):
    """⚠️ THE GUARD THAT COST A 500 IF MISSED.

    `verify_password(plain, None)` raises. Before r226 no user could have a NULL
    password, so the three tenant read sites never had to consider it. A 500 on
    a known email is also an existence oracle, so the status matters as much as
    the refusal.
    """
    _invite(db)
    r = client.post("/api/v1/auth/login", headers=H,
                    json={"email": INVITEE_EMAIL, "password": "anything-at-all"})
    assert r.status_code == 401, f"expected a refusal, got {r.status_code}: {r.text}"


def test_she_can_sign_in_after_accepting(actors, client, db):
    _, token = _invite(db)
    client.post(f"/api/v1/invites/{token}/accept", headers=H,
                json={"password": "SheChoseThisOne123"})
    r = client.post("/api/v1/auth/login", headers=H,
                    json={"email": INVITEE_EMAIL, "password": "SheChoseThisOne123"})
    assert r.status_code == 200, r.text
    assert "access_token" in r.json()


def test_the_login_refusal_is_the_same_as_a_wrong_password(actors, client, db):
    _invite(db)
    invited = client.post("/api/v1/auth/login", headers=H,
                          json={"email": INVITEE_EMAIL, "password": "anything"})
    unknown = client.post("/api/v1/auth/login", headers=H,
                          json={"email": "nobody-here@testco.example.com",
                                "password": "anything"})
    assert invited.status_code == unknown.status_code == 401
    assert invited.text == unknown.text, (
        f"invited-not-accepted is distinguishable from unknown: "
        f"{invited.text} vs {unknown.text}")


# ── the database guard behind the nullable column ────────────────────────

def test_a_user_with_neither_password_nor_invite_is_refused_by_the_database(actors, db):
    """`ck_users_password_or_invite` keeps the nullable column from being a hole.

    ⚠️ This is the control on the loud-to-quiet trade r226 makes. Without it, a
    code path that forgot a password would create an account nobody can sign in
    to and nothing would say so.
    """
    from sqlalchemy.exc import IntegrityError

    rid = _role_id(db, "office")
    db.execute(text("DELETE FROM users WHERE id='inv-constraint-probe'"))
    db.commit()
    with pytest.raises(IntegrityError) as exc:
        db.execute(text(
            "INSERT INTO users (id, company_id, email, hashed_password, "
            "first_name, last_name, role_id, is_active, created_at, updated_at) "
            "VALUES ('inv-constraint-probe', :c, 'probe@testco.example.com', "
            "NULL, 'No', 'Credential', :r, TRUE, NOW(), NOW())"),
            {"c": TESTCO_ID, "r": rid})
    db.rollback()
    assert "ck_users_password_or_invite" in str(exc.value), str(exc.value)


def test_clearing_the_hash_on_a_passwordless_row_is_refused(actors, db):
    """Which is why `revoke_invite` deletes rather than clears.

    A CHECK is evaluated on UPDATE too. My first draft of `revoke_invite` set
    the hash to NULL and documented the opposite; this pins the real behaviour.
    """
    from sqlalchemy.exc import IntegrityError

    user, _ = _invite(db)
    with pytest.raises(IntegrityError):
        db.execute(text("UPDATE users SET invite_token_hash = NULL WHERE id=:u"),
                   {"u": user.id})
        db.commit()
    db.rollback()


def test_revoke_removes_the_pending_row(actors, db):
    user, token = _invite(db)
    actor = db.query(User).filter(User.id == ADMIN_UID).first()
    assert tenant_invite.revoke_invite(db, actor=actor, user=user) is True
    gone = db.execute(text("SELECT count(*) FROM users WHERE id=:u"),
                      {"u": user.id}).scalar()
    assert gone == 0
    # and the link stops working
    assert tenant_invite.resolve_invite.__name__  # sanity
    with pytest.raises(tenant_invite.InviteError):
        tenant_invite.resolve_invite(db, token)


def test_revoke_returns_false_for_an_accepted_user(actors, client, db):
    user, token = _invite(db)
    client.post(f"/api/v1/invites/{token}/accept", headers=H,
                json={"password": "SheChoseThisOne123"})
    db.expire_all()
    fresh = db.query(User).filter(User.id == user.id).first()
    actor = db.query(User).filter(User.id == ADMIN_UID).first()
    assert tenant_invite.revoke_invite(db, actor=actor, user=fresh) is False
    assert db.execute(text("SELECT count(*) FROM users WHERE id=:u"),
                      {"u": user.id}).scalar() == 1, "an accepted user must survive"


# ── two-step hand-off ────────────────────────────────────────────────────

def test_accepting_tells_a_payroll_user_she_must_enrol(actors, client, db):
    _, token = _invite(db, slug="payroll", email=PAYROLL_INVITEE_EMAIL)
    r = client.post(f"/api/v1/invites/{token}/accept", headers=H,
                    json={"password": "SheChoseThisOne123"})
    assert r.status_code == 200, r.text
    assert r.json()["two_step_required"] is True


def test_accepting_does_not_tell_an_office_user_to_enrol(actors, client, db):
    _, token = _invite(db, slug="office")
    r = client.post(f"/api/v1/invites/{token}/accept", headers=H,
                    json={"password": "SheChoseThisOne123"})
    assert r.status_code == 200, r.text
    assert r.json()["two_step_required"] is False


def test_accepting_returns_no_token_pair(actors, client, db):
    _, token = _invite(db)
    r = client.post(f"/api/v1/invites/{token}/accept", headers=H,
                    json={"password": "SheChoseThisOne123"})
    assert "access_token" not in r.text and "refresh_token" not in r.text, r.text


# ── the audit trail ──────────────────────────────────────────────────────

def test_the_invite_and_the_acceptance_are_audited_without_the_token(actors, client, db):
    user, token = _invite(db)
    client.post(f"/api/v1/invites/{token}/accept", headers=H,
                json={"password": "SheChoseThisOne123"})
    rows = db.execute(text(
        "SELECT action, user_id, entity_id, changes::text FROM audit_logs "
        "WHERE entity_id=:u ORDER BY created_at"), {"u": user.id}).fetchall()
    actions = [r[0] for r in rows]
    assert "user.invited" in actions, actions
    assert "user.invite_accepted" in actions, actions
    for r in rows:
        assert token not in (r[3] or ""), "the audit log records the invite token"


# ── the email path ───────────────────────────────────────────────────────

def test_the_invite_email_template_exists(actors, db):
    """⚠️ WITHOUT THIS, EVERY TEST ABOVE PASSES ON THE DEGRADED PATH.

    `_send_invite_email` catches everything and reports `email_sent: False`, so
    a missing template is indistinguishable from unconfigured SMTP — and the
    whole suite would still be green while the invite link reached nobody. This
    asserts `r227` actually seeded the template the flow names.

    Measured 2026-11-03: the first full run of this suite happened before r227
    was applied, and all 26 tests passed against zero templates. That is the
    reason this test exists.
    """
    row = db.execute(text(
        "SELECT t.id, v.subject_template FROM document_templates t "
        "JOIN document_template_versions v ON v.id = t.current_version_id "
        "WHERE t.template_key = 'email.tenant_user_invite' "
        "AND t.company_id IS NULL AND t.deleted_at IS NULL"
    )).first()
    assert row is not None, (
        "email.tenant_user_invite is not seeded — r227 has not been applied, "
        "so every invite silently reports email_sent=False"
    )
    assert "{{ tenant_name }}" in (row[1] or ""), row[1]


def test_the_template_declares_every_variable_the_sender_passes(actors, db):
    """The sender and the template must agree, or rendering fails at send time.

    Compared as SETS, not counts — five against five passes while one is
    misspelled.
    """
    import json
    row = db.execute(text(
        "SELECT v.variable_schema::text FROM document_templates t "
        "JOIN document_template_versions v ON v.id = t.current_version_id "
        "WHERE t.template_key = 'email.tenant_user_invite' AND t.company_id IS NULL"
    )).first()
    if row is None:
        pytest.skip("r227 not applied; covered by the test above")
    declared = set(json.loads(row[0]).keys())
    passed = {"first_name", "inviter_name", "tenant_name", "invite_url", "expires_in"}
    assert declared == passed, (
        f"the template and the sender disagree.\n  declared only: {declared - passed}"
        f"\n  passed only:   {passed - declared}"
    )


def test_the_invite_reaches_the_delivery_layer(actors, client, db):
    """⚠️ THE TEST THAT CATCHES A SWALLOWED ImportError.

    `_send_invite_email` wraps everything in `try/except Exception` so a
    delivery failure cannot roll back the user row. That is the right trade and
    it is also a place where a BROKEN CALL is indistinguishable from
    unconfigured email — both end up reporting `email_sent: false`.

    My first draft copied the import from `portal_admin._send_invite_email`
    (`:159`): `from app.services.delivery_service import ...`, the wrong one of
    two modules with similar names, which raises ImportError on the name. The
    portal swallows it identically, so **every portal invite and
    password-recovery email has silently failed since Phase 8e.2.1**. None of
    my other tests could see it, because none asserted anything positive about
    the send.

    ⚠️ IT ASSERTS THE DELIVERY ROW, NOT `email_sent`. The flag is
    config-dependent — dev has no `RESEND_API_KEY`, so the channel runs in test
    mode and the flag is correctly False here. What is environment-independent
    is that the call REACHED the delivery layer and a row was written; that is
    what a wrong import or a wrong kwarg name destroys. `email_sent`'s honesty
    has its own test below.
    """
    r = client.post("/api/v1/users/invite", headers=_auth(tenant_token(ADMIN_UID, TESTCO_ID)),
                    json={"email": INVITEE_EMAIL, "first_name": "Pat",
                          "last_name": "Invitee", "role_id": _role_id(db, "office")})
    assert r.status_code == 201, r.text

    row = db.execute(text(
        "SELECT template_key, status, caller_module FROM document_deliveries "
        "WHERE company_id = :c AND caller_module = 'users.invite' "
        "ORDER BY created_at DESC LIMIT 1"), {"c": TESTCO_ID}).first()
    assert row is not None, (
        "no document_deliveries row was written — the call into the delivery "
        "layer failed and was swallowed. Check the import module and the kwarg "
        "names against "
        "app/services/delivery/delivery_service.py::send_email_with_template"
    )
    assert row[0] == "email.tenant_user_invite", row
    assert row[1] == "sent", f"the delivery did not succeed: {row}"


def test_the_portal_invite_email_import_is_broken(actors):
    """⚠️ A REGRESSION PIN ON SOMEBODY ELSE'S BUG, DELIBERATELY WRITTEN TO FAIL
    WHEN IT IS FIXED.

    `portal_admin._send_invite_email` and `_send_reset_email` import
    `send_email_with_template` from `app.services.delivery_service`, which does
    not define it. Both swallow the ImportError. This test asserts the import
    is STILL broken, so that whoever fixes the portal flow gets a red test
    pointing at this comment rather than a silent behaviour change — and so
    that the finding cannot be quietly lost.

    When the portal is fixed: delete this test and the STATE.md item with it.
    """
    import pytest as _pytest
    with _pytest.raises(ImportError):
        from app.services.delivery_service import (  # noqa: F401
            send_email_with_template,
        )


def test_an_unconfigured_mailer_reports_not_sent(actors, client, db, monkeypatch):
    """⚠️ TEST MODE MUST NOT READ AS DELIVERED.

    `EmailChannel._is_test_mode()` returns success with
    `provider_message_id='test-mode'` when `RESEND_API_KEY` is empty — so the
    delivery row says `sent` and nothing left the building. Measured on dev:
    69,623 of 69,637 `sent` rows are test-mode.

    Without the second clause in `_send_invite_email`, an admin on an
    unconfigured tenant is told the invitation went out and the invitee waits
    for an email that does not exist. The whole flow's guarantee rests on this
    flag being honest, so it gets its own test rather than riding on the
    happy path.
    """
    from app.config import settings
    monkeypatch.setattr(settings, "RESEND_API_KEY", "", raising=False)

    r = client.post("/api/v1/users/invite", headers=_auth(tenant_token(ADMIN_UID, TESTCO_ID)),
                    json={"email": INVITEE_EMAIL, "first_name": "Pat",
                          "last_name": "Invitee", "role_id": _role_id(db, "office")})
    assert r.status_code == 201, r.text
    assert r.json()["email_sent"] is False, (
        "an unconfigured mailer reported the invite as sent"
    )

    # The user still exists — the account is created and re-invitable, which is
    # the documented degradation rather than a rollback.
    n = db.execute(text(
        "SELECT count(*) FROM users WHERE email=:e AND company_id=:c"),
        {"e": INVITEE_EMAIL, "c": TESTCO_ID}).scalar()
    assert n == 1, "the invited user should still exist for a re-invite"
