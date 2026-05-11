"""Notification category registry tests (R-8.1).

Verifies the canonical Notification category registry shipped at
`app.services.notifications.category_types`. Closed-vocabulary
platform-owned catalog; no frontend-backend symmetry test because
frontend dispatches on `type` (info/success/warning/error) rather
than `category`.
"""

from __future__ import annotations

import pytest

from app.services.notifications.category_types import (
    NOTIFICATION_CATEGORIES,
    NOTIFICATION_CATEGORY_REGISTRY,
    UnknownNotificationCategoryError,
    assert_valid_notification_category,
    validate_notification_category,
)


class TestRegistryShape:
    """Registry exposes canonical categories with required metadata."""

    def test_registry_is_frozen_set(self) -> None:
        assert isinstance(NOTIFICATION_CATEGORIES, frozenset)
        # 19 canonical categories at R-8.1 ship (18 actively written +
        # safety_alert read-only legacy).
        assert len(NOTIFICATION_CATEGORIES) >= 18

    def test_every_entry_has_required_metadata(self) -> None:
        required_fields = {"description", "default_icon", "default_color_token"}
        for key, meta in NOTIFICATION_CATEGORY_REGISTRY.items():
            missing = required_fields - meta.keys()
            assert not missing, f"{key} missing required fields: {missing}"
            for field in required_fields:
                assert meta[field], f"{key}.{field} is empty"

    def test_registry_keys_match_categories_set(self) -> None:
        assert NOTIFICATION_CATEGORIES == frozenset(
            NOTIFICATION_CATEGORY_REGISTRY.keys()
        )


class TestValidation:
    """validate_notification_category + assert_valid_notification_category behavior."""

    def test_validate_accepts_known_category(self) -> None:
        assert validate_notification_category("employee") is True
        assert validate_notification_category("delivery_failed") is True
        assert validate_notification_category(
            "calendar_consent_upgrade_request"
        ) is True

    def test_validate_accepts_none_category(self) -> None:
        # Many notifications carry no category — `None` is canonical valid.
        assert validate_notification_category(None) is True

    def test_validate_rejects_unknown_category(self) -> None:
        assert validate_notification_category("totally_made_up") is False
        assert validate_notification_category("") is False

    def test_assert_accepts_known_category(self) -> None:
        # No exception
        assert_valid_notification_category("share_granted")
        assert_valid_notification_category("safety_alert")

    def test_assert_accepts_none(self) -> None:
        # No exception — None is canonical valid.
        assert_valid_notification_category(None)

    def test_assert_raises_on_unknown(self) -> None:
        with pytest.raises(UnknownNotificationCategoryError) as exc_info:
            assert_valid_notification_category("ghost_category")
        assert "ghost_category" in str(exc_info.value)
        assert "Valid categories:" in str(exc_info.value)
        assert "app.services.notifications.category_types" in str(
            exc_info.value
        )

    def test_unknown_error_is_value_error(self) -> None:
        # Inherits from ValueError so existing handlers work.
        assert issubclass(UnknownNotificationCategoryError, ValueError)


class TestRuntimeCanonicalStrings:
    """All hardcoded category strings used at runtime write sites
    validate against the registry.

    Pre-flight cataloged 18 write-site categories via:
        for f in $(grep -rln 'create_notification\\|notify_tenant_admins' \
                   backend/app/); do grep '^\\s+category=' "$f"; done

    Plus `safety_alert` — written by the r29 V-1d data migration as a
    one-shot backfill and still read by safety_service.list_alerts.
    Every category MUST be registered, or the corresponding write-site
    call would crash at runtime post-R-8.1.
    """

    RUNTIME_WRITTEN_CATEGORIES: frozenset[str] = frozenset({
        # Domain
        "employee",
        "user",
        "pricing",
        "inventory",
        # V-1d notification sources
        "share_granted",
        "delivery_failed",
        "signature_requested",
        "compliance_expiry",
        "account_at_risk",
        # Calendar primitive (Step 4.1 + 5)
        "calendar_consent_upgrade_request",
        "calendar_consent_upgrade_accepted",
        "calendar_consent_upgrade_revoked",
        "calendar_attendee_responded",
        # Personalization Studio
        "personalization_studio_consent_upgrade_request",
        "personalization_studio_consent_upgrade_accepted",
        "personalization_studio_consent_revoked",
        "personalization_studio_mfg_reviewed",
        "personalization_studio_share_failed",
    })

    # Read-only legacy category — written by r29 backfill, read by
    # safety_service.list_alerts / acknowledge_alert. MUST be in the
    # registry so the read path validation (if any future code path
    # validates) doesn't reject canonical legacy rows.
    RUNTIME_READ_ONLY_CATEGORIES: frozenset[str] = frozenset({
        "safety_alert",
    })

    def test_every_runtime_written_category_validates(self) -> None:
        for category in self.RUNTIME_WRITTEN_CATEGORIES:
            assert validate_notification_category(category), (
                f"Runtime category {category!r} not in registry — "
                f"write site will crash post-R-8.1"
            )

    def test_every_read_only_legacy_category_registered(self) -> None:
        for category in self.RUNTIME_READ_ONLY_CATEGORIES:
            assert validate_notification_category(category), (
                f"Read-only legacy category {category!r} not in "
                f"registry — safety_service.list_alerts queries would "
                f"silently exclude these rows if reader-side validation "
                f"is ever added"
            )


class TestServiceLayerEnforcement:
    """Notification service-layer entry points reject unknown categories.

    Verifies the wiring at notification_service.create_notification +
    notify_tenant_admins call assert_valid_notification_category before
    INSERT.
    """

    def test_create_notification_rejects_unknown_category(self) -> None:
        from app.services import notification_service

        # No DB needed — validation runs before any session work.
        with pytest.raises(UnknownNotificationCategoryError):
            notification_service.create_notification(
                db=None,  # type: ignore[arg-type]
                company_id="c1",
                user_id="u1",
                title="t",
                message="m",
                category="ghost",
            )

    def test_notify_tenant_admins_rejects_unknown_category(self) -> None:
        from app.services import notification_service

        with pytest.raises(UnknownNotificationCategoryError):
            notification_service.notify_tenant_admins(
                db=None,  # type: ignore[arg-type]
                company_id="c1",
                title="t",
                message="m",
                category="ghost",
            )
