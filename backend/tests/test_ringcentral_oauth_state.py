"""S-3c Part 1 — RingCentral OAuth `state` is a nonce, not a tenant selector.

⚠️ WHY THIS FILE EXISTS. From `1e48454b` (2026-04-08) until 2026-09-03,
`GET /api/v1/integrations/ringcentral/oauth/callback` did this:

    company_id = state
    company = db.query(Company).filter(Company.id == company_id).first()
    ...
    company.set_setting("ringcentral_access_token", encrypt_secret(...))

`state` is a CSRF parameter on a public unauthenticated GET — attacker-supplied
by construction — and it was the tenant selector for a settings write. Anyone
with a RingCentral authorization code from their own free RC account could name
another tenant's `company_id` and write their tokens into it.

THE DECISIVE TEST IS `test_state_naming_tenant_b_writes_nothing`. Every other
test here would also pass against the ORIGINAL code: the old callback rejected
an empty state, and it 404'd on an unknown one, so "unknown state rejected"
certifies the defect rather than the fix. The test that separates them is the
one where the request NAMES a tenant it should not reach. That is the break
test applied to test SELECTION rather than to the assertion — when a check
replaces one that conflated two things, the cases that matter are the ones
where the two disagree.

Each test below was break-tested by reverting the fix (restoring
`company_id = state`) and confirming THAT test goes red, not merely something.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from cryptography.fernet import Fernet

from app.database import SessionLocal
from app.services.ringcentral_oauth_state import (
    PROVIDER_TYPE,
    RingCentralOAuthStateInvalid,
    issue_state_nonce,
    validate_and_consume_state_nonce,
)
from tests._cleanup import purge_companies_by_slug

_SLUG_PREFIX = "rcoauth-"


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def world():
    """Two tenants, each with a user. Tenant B is the one nobody may reach."""
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    ids = {}
    try:
        for key in ("a", "b"):
            suffix = uuid.uuid4().hex[:8]
            co = Company(
                id=str(uuid.uuid4()),
                name=f"RC OAuth {key.upper()}",
                slug=f"{_SLUG_PREFIX}{suffix}",
                is_active=True,
            )
            db.add(co)
            db.flush()
            role = Role(
                id=str(uuid.uuid4()),
                company_id=co.id,
                name="Admin",
                slug=f"rcoauth-admin-{suffix}",
            )
            db.add(role)
            db.flush()
            user = User(
                id=str(uuid.uuid4()),
                company_id=co.id,
                email=f"rcoauth-{suffix}@example.com",
                first_name="RC",
                last_name="Tester",
                hashed_password="x",
                role_id=role.id,
            )
            db.add(user)
            db.flush()
            ids[key] = {"company": co.id, "user": user.id}
        db.commit()
    finally:
        db.close()

    yield ids

    db = SessionLocal()
    try:
        purge_companies_by_slug(db, f"{_SLUG_PREFIX}%")
    finally:
        db.close()


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture
def rc_configured():
    """RC client credentials present, so the handler reaches the state check.

    Without this the route short-circuits at the 500 "not configured" branch
    and every assertion below would pass for the wrong reason.
    """
    from app.config import settings

    cid, csec = settings.RINGCENTRAL_CLIENT_ID, settings.RINGCENTRAL_CLIENT_SECRET
    settings.RINGCENTRAL_CLIENT_ID = "s3c-test-client"
    settings.RINGCENTRAL_CLIENT_SECRET = "s3c-test-secret"

    # RC tokens are encrypted at the write site (`encrypt_secret`), which is a
    # hard dependency on this key — without it the handler raises before it
    # reaches any settings write, and the negative tests below would go green
    # for the wrong reason.
    prior_key = os.environ.get("CREDENTIAL_ENCRYPTION_KEY")
    os.environ["CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
    yield
    settings.RINGCENTRAL_CLIENT_ID, settings.RINGCENTRAL_CLIENT_SECRET = cid, csec
    if prior_key is None:
        os.environ.pop("CREDENTIAL_ENCRYPTION_KEY", None)
    else:
        os.environ["CREDENTIAL_ENCRYPTION_KEY"] = prior_key


def _token_response():
    """A successful RC token exchange, mocked at the httpx boundary."""
    resp = AsyncMock()
    resp.status_code = 200
    resp.json = lambda: {
        "access_token": "rc-access-token",
        "refresh_token": "rc-refresh-token",
        "expires_in": 3600,
        "owner_id": "400144455008",
    }
    ctx = AsyncMock()
    ctx.__aenter__.return_value.post = AsyncMock(return_value=resp)
    return ctx


def _settings_of(company_id: str) -> dict:
    from app.models.company import Company

    s = SessionLocal()
    try:
        co = s.query(Company).filter(Company.id == company_id).first()
        return dict(co.settings or {}) if co else {}
    finally:
        s.close()


# ── The service: the rejection ladder ────────────────────────────────


def test_unknown_nonce_rejected(db):
    with pytest.raises(RingCentralOAuthStateInvalid):
        validate_and_consume_state_nonce(db, nonce=uuid.uuid4().hex)


def test_empty_nonce_rejected(db):
    with pytest.raises(RingCentralOAuthStateInvalid):
        validate_and_consume_state_nonce(db, nonce="")


def test_raw_company_id_is_not_a_nonce(db, world):
    """The exact old attack, at the service layer: a real `company_id` in the
    state slot resolves to nothing."""
    with pytest.raises(RingCentralOAuthStateInvalid):
        validate_and_consume_state_nonce(db, nonce=world["b"]["company"])


def test_valid_nonce_is_accepted_and_yields_its_tenant(db, world):
    """POSITIVE CONTROL. Without this the rejections above would all pass
    against a function that rejects everything, and the arc's authorize
    endpoint would have nothing that works."""
    nonce = issue_state_nonce(
        db,
        tenant_id=world["a"]["company"],
        user_id=world["a"]["user"],
        redirect_uri="https://example.invalid/cb",
    )
    row = validate_and_consume_state_nonce(db, nonce=nonce)
    assert row.tenant_id == world["a"]["company"]
    assert row.consumed_at is not None


def test_replayed_nonce_rejected(db, world):
    nonce = issue_state_nonce(
        db,
        tenant_id=world["a"]["company"],
        user_id=world["a"]["user"],
        redirect_uri="https://example.invalid/cb",
    )
    validate_and_consume_state_nonce(db, nonce=nonce)  # first use succeeds
    with pytest.raises(RingCentralOAuthStateInvalid):
        validate_and_consume_state_nonce(db, nonce=nonce)


def test_expired_nonce_rejected(db, world):
    from app.models.email_primitive import OAuthStateNonce

    nonce = issue_state_nonce(
        db,
        tenant_id=world["a"]["company"],
        user_id=world["a"]["user"],
        redirect_uri="https://example.invalid/cb",
    )
    row = db.query(OAuthStateNonce).filter(OAuthStateNonce.nonce == nonce).first()
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.flush()
    with pytest.raises(RingCentralOAuthStateInvalid):
        validate_and_consume_state_nonce(db, nonce=nonce)


def test_foreign_provider_nonce_rejected(db, world):
    """A nonce minted for the Gmail flow must not redeem at RingCentral's
    callback. The `oauth_state_nonces` table is platform-shared, so without
    this check any provider's live nonce would be a valid RC state."""
    from app.models.email_primitive import OAuthStateNonce

    nonce = "s3c-foreign-" + uuid.uuid4().hex
    db.add(
        OAuthStateNonce(
            nonce=nonce,
            tenant_id=world["a"]["company"],
            user_id=world["a"]["user"],
            provider_type="gmail",
            redirect_uri="https://example.invalid/cb",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
    )
    db.flush()
    with pytest.raises(RingCentralOAuthStateInvalid):
        validate_and_consume_state_nonce(db, nonce=nonce)


# ── The route: which tenant actually gets written ────────────────────


def test_state_naming_tenant_b_writes_nothing(client, world, rc_configured):
    """⚠️ THE DECISIVE CASE — the crossed one.

    A request that names tenant B's `company_id` in `state`, exactly as the
    old code expected it. Under the old code this succeeded and wrote B's
    RingCentral tokens. It must now be rejected, and B's settings must be
    untouched.
    """
    before = _settings_of(world["b"]["company"])

    with patch("httpx.AsyncClient", return_value=_token_response()):
        r = client.get(
            "/api/v1/integrations/ringcentral/oauth/callback",
            params={"code": "rc-auth-code", "state": world["b"]["company"]},
            follow_redirects=False,
        )

    assert r.status_code == 400, r.text
    after = _settings_of(world["b"]["company"])
    assert after == before
    assert "ringcentral_access_token" not in after
    assert after.get("ringcentral_connected") is not True


def test_nonce_minted_for_a_writes_only_to_a(client, world, rc_configured):
    """The other half of the crossed pair. A nonce minted for tenant A writes
    to A — and B is untouched by the same request, which is what proves the
    binding follows the nonce rather than merely being narrow."""
    db = SessionLocal()
    try:
        nonce = issue_state_nonce(
            db,
            tenant_id=world["a"]["company"],
            user_id=world["a"]["user"],
            redirect_uri="https://example.invalid/cb",
        )
        db.commit()
    finally:
        db.close()

    b_before = _settings_of(world["b"]["company"])

    with patch("httpx.AsyncClient", return_value=_token_response()):
        r = client.get(
            "/api/v1/integrations/ringcentral/oauth/callback",
            params={"code": "rc-auth-code", "state": nonce},
            follow_redirects=False,
        )

    assert r.status_code == 302, r.text
    a_after = _settings_of(world["a"]["company"])
    assert a_after.get("ringcentral_connected") is True
    assert a_after.get("ringcentral_access_token")  # encrypted; presence only
    assert a_after.get("ringcentral_owner_id") == "400144455008"

    assert _settings_of(world["b"]["company"]) == b_before


def test_callback_nonce_is_single_use_at_the_route(client, world, rc_configured):
    """Single-use survives a full round trip through the route.

    ⚠️ THIS DOES NOT PROVE THE POST-CONSUMPTION `db.commit()` IS LOAD-BEARING,
    and an earlier draft of this docstring claimed it did. Break-testing showed
    the claim was false: deleting that commit leaves this test green, because
    on the happy path the handler's later commit flushes `consumed_at` along
    with the token writes. The success condition is invariant under the failure
    it named (CLAUDE.md §11, shape 7). The commit's real job is the FAILURE
    path — covered by the next test, which is where it goes red.
    """
    db = SessionLocal()
    try:
        nonce = issue_state_nonce(
            db,
            tenant_id=world["a"]["company"],
            user_id=world["a"]["user"],
            redirect_uri="https://example.invalid/cb",
        )
        db.commit()
    finally:
        db.close()

    params = {"code": "rc-auth-code", "state": nonce}
    with patch("httpx.AsyncClient", return_value=_token_response()):
        first = client.get(
            "/api/v1/integrations/ringcentral/oauth/callback",
            params=params,
            follow_redirects=False,
        )
        second = client.get(
            "/api/v1/integrations/ringcentral/oauth/callback",
            params=params,
            follow_redirects=False,
        )

    assert first.status_code == 302, first.text
    assert second.status_code == 400, second.text


def test_nonce_is_burned_even_when_the_token_exchange_fails(
    client, world, rc_configured
):
    """A nonce consumed and then abandoned by a failed exchange stays consumed.

    Without the post-consumption commit, the `consumed_at` flip is only
    flushed; the HTTPException raised on a failed exchange unwinds the request
    and `get_db` closes the session without committing, so the flip is rolled
    back and the nonce is replayable. An attacker who can make the exchange
    fail — RingCentral 4xx, a network error, an expired code — gets unlimited
    retries on a nonce that is supposed to be single-use.
    """
    db = SessionLocal()
    try:
        nonce = issue_state_nonce(
            db,
            tenant_id=world["a"]["company"],
            user_id=world["a"]["user"],
            redirect_uri="https://example.invalid/cb",
        )
        db.commit()
    finally:
        db.close()

    failed = AsyncMock()
    failed.status_code = 400
    failed.text = "invalid_grant"
    failing_ctx = AsyncMock()
    failing_ctx.__aenter__.return_value.post = AsyncMock(return_value=failed)

    with patch("httpx.AsyncClient", return_value=failing_ctx):
        first = client.get(
            "/api/v1/integrations/ringcentral/oauth/callback",
            params={"code": "bad-code", "state": nonce},
            follow_redirects=False,
        )
    assert first.status_code == 400, first.text

    # Now retry the SAME nonce with an exchange that would succeed. Compare
    # settings before/after rather than asserting "not connected" — an earlier
    # test in this module legitimately connects tenant A, so an absolute claim
    # would be testing test order. Fernet ciphertext is non-deterministic, so a
    # successful replay would visibly change the stored token.
    before = _settings_of(world["a"]["company"])
    with patch("httpx.AsyncClient", return_value=_token_response()):
        second = client.get(
            "/api/v1/integrations/ringcentral/oauth/callback",
            params={"code": "rc-auth-code", "state": nonce},
            follow_redirects=False,
        )
    assert second.status_code == 400, second.text
    assert _settings_of(world["a"]["company"]) == before


def test_provider_type_is_disjoint_from_the_siblings():
    """Guards the one line that keeps calendar/email nonces out of RC's flow.
    A rename to a value either sibling already uses would silently make their
    live nonces valid RingCentral states."""
    from app.services.calendar import oauth_service as cal

    assert PROVIDER_TYPE == "ringcentral"
    assert PROVIDER_TYPE not in cal._PROVIDER_TYPES
    # Email's set is a literal inside `issue_state_nonce`, not a module
    # constant — read it back off the source rather than restating it here,
    # so a change there fails this instead of drifting past it.
    import inspect

    from app.services.email import oauth_service as mail

    assert f'"{PROVIDER_TYPE}"' not in inspect.getsource(mail.issue_state_nonce)
