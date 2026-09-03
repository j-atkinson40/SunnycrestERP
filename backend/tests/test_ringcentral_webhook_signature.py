"""S-3a Part 1 — the RingCentral webhook signature check FAILS CLOSED.

⚠️ WHY THIS FILE EXISTS. `_verify_webhook_signature` failed open twice from
2026-04-08 (`1e48454b`) to 2026-09-03: it returned True unconditionally outside
production, and returned True IN production whenever the client secret was
unset. The endpoint writes to `ringcentral_call_log`, so any environment
reporting a non-production `ENVIRONMENT` — staging reports `"dev"` — was an
unauthenticated public writer for that window.

These tests assert REFUSAL. Each was break-tested by reverting the fix and
confirming THAT test goes red, not merely something.

No DB, no fixtures, no network: this is a pure function over (body, signature)
plus two settings values.
"""
import hashlib
import hmac

import pytest

from app.api.routes.ringcentral import _verify_webhook_signature
from app.config import settings


BODY = b'{"event":"/restapi/v1.0/account/~/extension/~/telephony/sessions"}'


def _sign(secret: str, body: bytes = BODY) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture
def _restore():
    env, sec = settings.ENVIRONMENT, settings.RINGCENTRAL_CLIENT_SECRET
    yield
    settings.ENVIRONMENT, settings.RINGCENTRAL_CLIENT_SECRET = env, sec


@pytest.mark.parametrize("environment", ["dev", "staging", "production"])
def test_unset_secret_rejects_in_every_environment(_restore, environment):
    """An unconfigured integration REFUSES traffic. This is the half that used
    to fail open in production too, where 'the secret is set' was an expired
    premise enforced by nothing."""
    settings.ENVIRONMENT = environment
    settings.RINGCENTRAL_CLIENT_SECRET = ""
    assert _verify_webhook_signature(BODY, _sign("anything")) is False
    assert _verify_webhook_signature(BODY, None) is False


@pytest.mark.parametrize("environment", ["dev", "staging", "production"])
def test_bad_signature_rejects_in_every_environment(_restore, environment):
    """No environment gets an unconditional pass. Before the fix, every
    non-production environment returned True without inspecting anything."""
    settings.ENVIRONMENT = environment
    settings.RINGCENTRAL_CLIENT_SECRET = "s3a-test-secret"
    assert _verify_webhook_signature(BODY, "not-the-signature") is False
    assert _verify_webhook_signature(BODY, None) is False
    # right secret, wrong body — the signature must cover the payload
    assert _verify_webhook_signature(b'{"tampered":true}', _sign("s3a-test-secret")) is False


@pytest.mark.parametrize("environment", ["dev", "staging", "production"])
def test_correct_signature_is_accepted(_restore, environment):
    """POSITIVE CONTROL. Without this, the two refusal tests above would pass
    against a function that rejects everything — including a correctly signed
    request — and the check would be a wall rather than a guard."""
    settings.ENVIRONMENT = environment
    settings.RINGCENTRAL_CLIENT_SECRET = "s3a-test-secret"
    assert _verify_webhook_signature(BODY, _sign("s3a-test-secret")) is True
