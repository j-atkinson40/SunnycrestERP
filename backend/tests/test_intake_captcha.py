"""Phase R-6.2b — CAPTCHA verification module coverage.

Covers app/services/intake/captcha.py + the integration sites in
app/api/routes/intake_adapters.py at /submit, /presign, /complete.

Graceful-degradation pattern (CLAUDE.md §4):
  - non-production + missing secret → log warning + allow (return True)
  - production + missing secret → CaptchaConfigurationError (500)
  - missing token + secret present → CaptchaVerificationError (403)
  - Cloudflare rejects → CaptchaVerificationError (403)
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, require_admin
from app.api.routes.intake_adapters import router
from app.database import get_db
from app.services.intake.captcha import (
    CaptchaConfigurationError,
    CaptchaVerificationError,
    verify_turnstile_token,
)
from tests._classification_fixtures import (  # noqa: F401
    admin_user,
    db,
    tenant_pair,
)


def _client(test_db):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/intake-adapters")

    def override_db():
        yield test_db

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


# ── Module-level unit tests ─────────────────────────────────────────


def test_missing_secret_in_dev_returns_true_and_logs():
    """Non-production + missing secret = graceful degradation."""
    with patch("app.services.intake.captcha.settings") as fake_settings:
        fake_settings.TURNSTILE_SECRET_KEY = ""
        fake_settings.ENVIRONMENT = "dev"
        assert (
            verify_turnstile_token("anything", environment="dev")
            is True
        )


def test_missing_secret_in_production_raises_configuration_error():
    """Production + missing secret = explicit 500 (no silent insecurity)."""
    with patch("app.services.intake.captcha.settings") as fake_settings:
        fake_settings.TURNSTILE_SECRET_KEY = ""
        fake_settings.ENVIRONMENT = "production"
        with pytest.raises(CaptchaConfigurationError) as exc_info:
            verify_turnstile_token("anything", environment="production")
        assert exc_info.value.http_status == 500


def test_missing_token_with_secret_raises_verification_error():
    """Secret configured + no token = 403 (user didn't complete challenge)."""
    with patch("app.services.intake.captcha.settings") as fake_settings:
        fake_settings.TURNSTILE_SECRET_KEY = "secret"
        fake_settings.ENVIRONMENT = "production"
        with pytest.raises(CaptchaVerificationError) as exc_info:
            verify_turnstile_token(None, environment="production")
        assert exc_info.value.http_status == 403


def test_cloudflare_success_response_returns_true():
    """Cloudflare returns {success: true} = allow."""
    fake_response = MagicMock()
    fake_response.json.return_value = {"success": True}
    fake_response.raise_for_status.return_value = None

    fake_client = MagicMock()
    fake_client.__enter__.return_value.post.return_value = fake_response
    fake_client.__exit__.return_value = None

    with patch("app.services.intake.captcha.settings") as fake_settings, patch(
        "app.services.intake.captcha.httpx.Client", return_value=fake_client
    ):
        fake_settings.TURNSTILE_SECRET_KEY = "secret"
        fake_settings.ENVIRONMENT = "production"
        assert (
            verify_turnstile_token("token", environment="production")
            is True
        )


def test_cloudflare_failure_response_raises():
    """Cloudflare returns {success: false} = 403."""
    fake_response = MagicMock()
    fake_response.json.return_value = {
        "success": False,
        "error-codes": ["invalid-input-response"],
    }
    fake_response.raise_for_status.return_value = None

    fake_client = MagicMock()
    fake_client.__enter__.return_value.post.return_value = fake_response
    fake_client.__exit__.return_value = None

    with patch("app.services.intake.captcha.settings") as fake_settings, patch(
        "app.services.intake.captcha.httpx.Client", return_value=fake_client
    ):
        fake_settings.TURNSTILE_SECRET_KEY = "secret"
        fake_settings.ENVIRONMENT = "production"
        with pytest.raises(CaptchaVerificationError):
            verify_turnstile_token("bad_token", environment="production")


def test_environment_defaults_from_settings_when_kwarg_omitted():
    """environment kwarg defaults to settings.ENVIRONMENT."""
    with patch("app.services.intake.captcha.settings") as fake_settings:
        fake_settings.TURNSTILE_SECRET_KEY = ""
        fake_settings.ENVIRONMENT = "staging"
        # staging != production → graceful degrade.
        assert verify_turnstile_token("anything") is True


# ── Integration: /submit endpoint ───────────────────────────────────


def test_submit_endpoint_passes_in_dev_without_captcha_token(
    db, tenant_pair, monkeypatch
):
    """R-6.2a regression: dev environment + no token = allow."""
    a, _ = tenant_pair
    a.vertical = "funeral_home"
    db.commit()

    from app.services.classification import dispatch as dispatch_mod

    monkeypatch.setattr(
        dispatch_mod,
        "classify_and_fire_form",
        lambda db, *, submission, config: {"tier": None},
        raising=True,
    )

    client = _client(db)
    body = {
        "submitted_data": {
            "deceased_name": "Test",
            "family_contact_email": "t@example.com",
            "relationship_to_deceased": "spouse",
            "preferred_personalization": "Loved gardening.",
            "family_contact_name": "Test",
        }
    }
    r = client.post(
        f"/api/v1/intake-adapters/forms/{a.slug}/personalization-request/submit",
        json=body,
    )
    # Should succeed via graceful-degradation (env=dev, no secret).
    assert r.status_code == 201, r.text


def test_submit_endpoint_rejects_in_production_without_secret(
    db, tenant_pair
):
    """Production + missing secret = 500 surfaces."""
    a, _ = tenant_pair
    a.vertical = "funeral_home"
    db.commit()

    with patch("app.services.intake.captcha.settings") as fake_settings:
        fake_settings.TURNSTILE_SECRET_KEY = ""
        fake_settings.ENVIRONMENT = "production"
        client = _client(db)
        body = {
            "submitted_data": {
                "deceased_name": "Test",
                "family_contact_email": "t@example.com",
                "relationship_to_deceased": "spouse",
                "preferred_personalization": "Loved gardening.",
                "family_contact_name": "Test",
            }
        }
        r = client.post(
            f"/api/v1/intake-adapters/forms/{a.slug}/personalization-request/submit",
            json=body,
        )
        assert r.status_code == 500
