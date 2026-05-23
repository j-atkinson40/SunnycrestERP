"""(c) build arc Phase A — substrate regression gates.

Verifies:
1. 9 new §19 categories landed in NOTIFICATION_CATEGORY_REGISTRY.
2. assert_valid_notification_category accepts each new key.
3. fh_cases.aftercare permission slug landed in PERMISSION_CATEGORIES.
4. FH-director (and manager) role's seeded permissions include
   fh_cases.aftercare via the MANAGER_DEFAULT_PERMISSIONS dynamic
   computation (extends to every role binding MANAGER_DEFAULT_PERMISSIONS).
5. Display-name registered for fh_cases.aftercare.

Phase B will add producer-site parity tests + backfill regression tests
in a separate file.
"""

from __future__ import annotations

from app.core.permissions import (
    PERMISSION_CATEGORIES,
    PERMISSION_DISPLAY_NAMES,
    MANAGER_DEFAULT_PERMISSIONS,
    get_all_permission_keys,
)
from app.services.notifications.category_types import (
    NOTIFICATION_CATEGORIES,
    NOTIFICATION_CATEGORY_REGISTRY,
    assert_valid_notification_category,
)


# ── 9 new categories present + valid ──

CBUILD_NEW_CATEGORIES = frozenset({
    "task_assigned",
    "ss_cert_pending_approval",
    "agent_anomaly_pending",
    "agent_job_awaiting_approval",
    "funeral_followup_pending",
    "catalog_sync_pending_review",
    "safety_program_pending_review",
    "workflow_review_pending",
    "email_unclassified_pending",
})


class TestNewCategoriesPresent:
    def test_all_nine_categories_in_registry(self):
        missing = CBUILD_NEW_CATEGORIES - NOTIFICATION_CATEGORIES
        assert not missing, f"Missing (c) build arc categories: {missing}"

    def test_registry_count_at_least_twenty_eight(self):
        # 19 pre-existing + 9 new = 28 minimum
        assert len(NOTIFICATION_CATEGORIES) >= 28

    def test_each_new_category_has_required_metadata(self):
        required_fields = {"description", "default_icon", "default_color_token"}
        for key in CBUILD_NEW_CATEGORIES:
            meta = NOTIFICATION_CATEGORY_REGISTRY[key]
            missing = required_fields - meta.keys()
            assert not missing, f"{key} missing required fields: {missing}"
            for field in required_fields:
                assert meta[field], f"{key}.{field} is empty"

    def test_assert_valid_accepts_each_new_key(self):
        for key in CBUILD_NEW_CATEGORIES:
            # No exception
            assert_valid_notification_category(key)


# ── fh_cases.aftercare permission slug ──


class TestFhCasesAftercarePermission:
    def test_fh_cases_includes_aftercare_action(self):
        fh_cases = PERMISSION_CATEGORIES["other"]["fh_cases"]
        assert "aftercare" in fh_cases, (
            "fh_cases.aftercare must be registered in PERMISSION_CATEGORIES "
            "for (c) build arc Phase A — gates funeral_followup_pending dispatch"
        )

    def test_aftercare_emitted_in_all_permission_keys(self):
        all_keys = get_all_permission_keys()
        assert "fh_cases.aftercare" in all_keys

    def test_display_name_registered(self):
        assert "fh_cases.aftercare" in PERMISSION_DISPLAY_NAMES
        assert PERMISSION_DISPLAY_NAMES["fh_cases.aftercare"]

    def test_aftercare_in_manager_defaults(self):
        """MANAGER_DEFAULT_PERMISSIONS = get_all_permission_keys() minus
        users.delete + roles.delete. fh_cases.aftercare inherits via the
        dynamic computation — this is the canonical FH-director grant path
        (director role binds to MANAGER_DEFAULT_PERMISSIONS per
        role_service._SYSTEM_ROLES)."""
        assert "fh_cases.aftercare" in MANAGER_DEFAULT_PERMISSIONS

    def test_director_role_definition_uses_manager_defaults(self):
        """Director role binds to MANAGER_DEFAULT_PERMISSIONS. This test
        documents the canonical FH-director grant path so that future
        refactors of role_service._SYSTEM_ROLES that decouple director
        from manager would surface here and re-trigger this audit.
        """
        from app.services.role_service import _SYSTEM_ROLES

        director_def = next(
            (r for r in _SYSTEM_ROLES if r["slug"] == "director"), None
        )
        assert director_def is not None, (
            "director role must be defined in _SYSTEM_ROLES "
            "(Phase 8e canonical FH role)"
        )
        assert director_def["permissions"] is MANAGER_DEFAULT_PERMISSIONS, (
            "director role currently binds to MANAGER_DEFAULT_PERMISSIONS. "
            "If this changes (decoupling director from manager), ensure "
            "fh_cases.aftercare remains in director's permission set."
        )


# ── Seeded role binding — FH-director users receive fh_cases.aftercare ──


class TestSeededDirectorReceivesAftercare:
    """End-to-end seed-roundtrip check: when seed_default_roles runs on a
    fresh tenant, the director role's RolePermission rows include
    fh_cases.aftercare."""

    def test_seeded_director_has_aftercare(self, db_session):
        import uuid

        from app.models.company import Company
        from app.models.role import Role
        from app.models.role_permission import RolePermission
        from app.services.role_service import seed_default_roles

        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"seedtest-{suffix}",
            slug=f"seedtest-{suffix}",
            is_active=True,
        )
        db_session.add(co)
        db_session.flush()
        seed_default_roles(db_session, co.id)
        db_session.commit()

        director_role = (
            db_session.query(Role)
            .filter(Role.company_id == co.id, Role.slug == "director")
            .first()
        )
        assert director_role is not None

        granted = {
            rp.permission_key
            for rp in db_session.query(RolePermission)
            .filter(RolePermission.role_id == director_role.id)
            .all()
        }
        assert "fh_cases.aftercare" in granted, (
            "FH-director role seed must include fh_cases.aftercare "
            "(via MANAGER_DEFAULT_PERMISSIONS dynamic computation)"
        )


# ── db_session fixture ──


import pytest  # noqa: E402


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()
