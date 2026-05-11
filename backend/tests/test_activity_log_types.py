"""Activity log type registry tests (R-8.2).

Verifies the canonical ActivityLog activity_type registry shipped at
`app.services.crm.activity_log_types`. Mirrors the frontend
RecentActivityWidget.activityVerb vocabulary.
"""

from __future__ import annotations

import pytest

from app.services.crm.activity_log_types import (
    ACTIVITY_TYPE_REGISTRY,
    ACTIVITY_TYPES,
    UnknownActivityTypeError,
    assert_valid_activity_type,
    validate_activity_type,
)


class TestRegistryShape:
    """Registry exposes canonical activity types with required metadata."""

    def test_registry_is_frozen_set(self) -> None:
        assert isinstance(ACTIVITY_TYPES, frozenset)
        assert len(ACTIVITY_TYPES) >= 14  # 14 frontend keys + legacy_proof synonym

    def test_every_entry_has_display_label_and_description(self) -> None:
        for key, meta in ACTIVITY_TYPE_REGISTRY.items():
            assert "display_label" in meta, f"{key} missing display_label"
            assert "description" in meta, f"{key} missing description"
            assert meta["display_label"], f"{key} display_label is empty"
            assert meta["description"], f"{key} description is empty"

    def test_registry_keys_match_activity_types_set(self) -> None:
        assert ACTIVITY_TYPES == frozenset(ACTIVITY_TYPE_REGISTRY.keys())


class TestFrontendBackendSymmetry:
    """Every key in the backend registry MUST mirror a frontend activityVerb key.

    Lockstep contract documented in `activity_log_types.py` module docstring.
    """

    # Canonical frontend keys captured from RecentActivityWidget.activityVerb at R-8.2 ship.
    # When backend or frontend adds a new key, BOTH sides update in the same commit.
    FRONTEND_VERB_KEYS: frozenset[str] = frozenset({
        "note", "call", "email", "calendar", "meeting", "document",
        "follow_up", "status_change", "delivery", "invoice", "order",
        "payment", "proof", "case",
    })

    def test_all_frontend_keys_present_in_backend_registry(self) -> None:
        missing = self.FRONTEND_VERB_KEYS - ACTIVITY_TYPES
        assert not missing, f"Backend registry missing frontend keys: {missing}"


class TestValidation:
    """validate_activity_type + assert_valid_activity_type behavior."""

    def test_validate_accepts_known_type(self) -> None:
        assert validate_activity_type("payment") is True
        assert validate_activity_type("email") is True
        assert validate_activity_type("calendar") is True

    def test_validate_rejects_unknown_type(self) -> None:
        assert validate_activity_type("totally_made_up") is False
        assert validate_activity_type("") is False

    def test_assert_accepts_known_type(self) -> None:
        # No exception
        assert_valid_activity_type("invoice")
        assert_valid_activity_type("legacy_proof")

    def test_assert_raises_unknown_activity_type_error_on_unknown(self) -> None:
        with pytest.raises(UnknownActivityTypeError) as exc_info:
            assert_valid_activity_type("ghost_type")
        assert "ghost_type" in str(exc_info.value)
        assert "Valid types:" in str(exc_info.value)

    def test_unknown_activity_type_error_is_value_error(self) -> None:
        # Inherits from ValueError so existing handlers work.
        assert issubclass(UnknownActivityTypeError, ValueError)


class TestRuntimeCanonicalStrings:
    """All hardcoded activity_type strings used at runtime write sites
    validate against the registry.

    Pre-flight cataloged 6 system-event strings + 4+ manual-event strings.
    Each MUST be registered, or the write-site call would crash at runtime
    post-R-8.2.
    """

    # System-event strings cataloged during R-8.2 pre-flight via:
    #   grep 'activity_type="..."' backend/app/services/ backend/app/api/
    RUNTIME_SYSTEM_EVENT_TYPES: frozenset[str] = frozenset({
        "calendar",      # calendar/activity_feed_integration.py
        "email",         # email/activity_feed_integration.py
        "invoice",       # draft_invoice_service.py
        "legacy_proof",  # legacy_email_service.py
        "order",         # order_station.py route
        "payment",       # sales_service.py
    })

    # Manual-event vocabulary surfaced via /company-entities activity create
    # endpoint + ai_command voice memo path.
    RUNTIME_MANUAL_EVENT_TYPES: frozenset[str] = frozenset({
        "note", "call", "meeting", "follow_up",
    })

    def test_every_runtime_system_event_type_validates(self) -> None:
        for activity_type in self.RUNTIME_SYSTEM_EVENT_TYPES:
            assert validate_activity_type(activity_type), (
                f"Runtime system-event type {activity_type!r} not in registry — "
                f"write site will crash post-R-8.2"
            )

    def test_every_runtime_manual_event_type_validates(self) -> None:
        for activity_type in self.RUNTIME_MANUAL_EVENT_TYPES:
            assert validate_activity_type(activity_type), (
                f"Runtime manual-event type {activity_type!r} not in registry"
            )
