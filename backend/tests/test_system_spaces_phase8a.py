"""Workflow Arc Phase 8a — tests for system spaces + role decoupling.

Covers:
  - SYSTEM_SPACE_TEMPLATES registry contains Settings
  - get_system_space_templates_for_user gates by permission
  - seed_for_user appends Settings to admin users' preferences.spaces
  - seed_for_user skips Settings for non-admin users
  - SpaceConfig.is_system roundtrips through to_dict/from_dict
  - delete_space rejects system spaces with informative error
  - Role decoupling: ROLE_CHANGE_RESEED_ENABLED=False means role
    change does NOT append saved views / briefing preferences
  - Role decoupling: spaces seed STILL runs on role change (so
    admin grant surfaces Settings in dot nav)
  - reapply_role_defaults_for_user restores full role seeding on
    demand
"""

from __future__ import annotations

import uuid

import pytest


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


def _make_tenant_user(
    *, role_slug: str = "admin", vertical: str = "manufacturing"
):
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"SYS-{suffix}",
            slug=f"sys-{suffix}",
            is_active=True,
            vertical=vertical,
        )
        db.add(co)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name=role_slug.title(),
            slug=role_slug,
            is_system=True,
        )
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"u-{suffix}@sys.co",
            first_name="Sys",
            last_name="User",
            hashed_password="x",
            is_active=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        return user.id, role.slug
    finally:
        db.close()


@pytest.fixture
def admin_user(db_session):
    from app.models.user import User

    uid, _ = _make_tenant_user(role_slug="admin", vertical="manufacturing")
    return db_session.query(User).filter(User.id == uid).one()


@pytest.fixture
def office_user(db_session):
    from app.models.user import User

    uid, _ = _make_tenant_user(role_slug="office", vertical="manufacturing")
    return db_session.query(User).filter(User.id == uid).one()


@pytest.fixture
def director_user(db_session):
    from app.models.user import User

    uid, _ = _make_tenant_user(role_slug="director", vertical="funeral_home")
    return db_session.query(User).filter(User.id == uid).one()


# ── Registry ──────────────────────────────────────────────────────


class TestSystemSpaceRegistry:
    def test_settings_template_registered(self):
        from app.services.spaces.registry import SYSTEM_SPACE_TEMPLATES

        settings = next(
            (t for t in SYSTEM_SPACE_TEMPLATES if t.template_id == "settings"),
            None,
        )
        assert settings is not None
        assert settings.required_permission == "admin"
        assert settings.display_order == -1000  # leftmost
        # 4 pins per Phase 8a rollout decision C.
        assert len(settings.pins) == 4

    def test_admin_user_sees_settings_template(self, db_session, admin_user):
        from app.services.spaces.registry import (
            get_system_space_templates_for_user,
        )

        templates = get_system_space_templates_for_user(db_session, admin_user)
        template_ids = [t.template_id for t in templates]
        assert "settings" in template_ids

    def test_office_user_does_not_see_settings(self, db_session, office_user):
        from app.services.spaces.registry import (
            get_system_space_templates_for_user,
        )

        templates = get_system_space_templates_for_user(db_session, office_user)
        template_ids = [t.template_id for t in templates]
        assert "settings" not in template_ids


# ── SpaceConfig is_system field ───────────────────────────────────


class TestSpaceConfigIsSystem:
    def test_is_system_defaults_false(self):
        from app.services.spaces.types import SpaceConfig

        sp = SpaceConfig(
            space_id="x",
            name="Test",
            icon="home",
            accent="neutral",
            display_order=0,
            is_default=False,
        )
        assert sp.is_system is False

    def test_is_system_roundtrips(self):
        from app.services.spaces.types import SpaceConfig

        sp = SpaceConfig(
            space_id="x",
            name="Test",
            icon="home",
            accent="neutral",
            display_order=0,
            is_default=False,
            is_system=True,
        )
        data = sp.to_dict()
        assert data["is_system"] is True
        sp2 = SpaceConfig.from_dict(data)
        assert sp2.is_system is True


# ── Seed behavior ─────────────────────────────────────────────────


class TestSystemSpaceSeed:
    def test_admin_seed_appends_settings_space(self, db_session, admin_user):
        """Phase W-4a — Home system space added for ALL users; admin
        sees Home + Settings (2 system spaces). Settings still admin-
        gated; Home is gate-less."""
        from app.services.spaces import seed_for_user
        from app.services.spaces.types import SpaceConfig

        created = seed_for_user(db_session, user=admin_user)
        db_session.refresh(admin_user)
        prefs = dict(admin_user.preferences or {})
        spaces = [SpaceConfig.from_dict(s) for s in prefs.get("spaces", [])]
        system = [s for s in spaces if s.is_system]
        # Phase W-4a — Home + Settings for admin
        assert len(system) == 2
        system_names = {s.name for s in system}
        assert system_names == {"Home", "Settings"}
        system_ids = {s.space_id for s in system}
        assert system_ids == {"sys_home", "sys_settings"}
        # Tracked via system_spaces_seeded idempotency array.
        seeded = prefs.get("system_spaces_seeded", [])
        assert "home" in seeded
        assert "settings" in seeded
        # Total `created` count includes system + role-based spaces.
        assert created >= 1

    def test_office_seed_skips_settings_space(self, db_session, office_user):
        """Phase W-4a — Home is gate-less so office still gets Home;
        Settings remains admin-gated and is NOT seeded for office."""
        from app.services.spaces import seed_for_user
        from app.services.spaces.types import SpaceConfig

        seed_for_user(db_session, user=office_user)
        db_session.refresh(office_user)
        prefs = dict(office_user.preferences or {})
        spaces = [SpaceConfig.from_dict(s) for s in prefs.get("spaces", [])]
        system = [s for s in spaces if s.is_system]
        # Phase W-4a — Home (gate-less) but NOT Settings (admin-gated)
        assert len(system) == 1
        assert system[0].name == "Home"
        seeded = prefs.get("system_spaces_seeded", [])
        assert "home" in seeded
        assert "settings" not in seeded

    def test_seed_is_idempotent_for_settings(self, db_session, admin_user):
        from app.services.spaces import seed_for_user
        from app.services.spaces.types import SpaceConfig

        seed_for_user(db_session, user=admin_user)
        db_session.refresh(admin_user)
        first_count = len(admin_user.preferences["spaces"])
        seed_for_user(db_session, user=admin_user)
        db_session.refresh(admin_user)
        assert len(admin_user.preferences["spaces"]) == first_count

    def test_director_seed_includes_role_spaces_but_no_settings(
        self, db_session, director_user
    ):
        """Phase W-4a — director (non-admin) gets Home (gate-less) +
        role-template spaces, but NOT Settings (admin-gated)."""
        from app.services.spaces import seed_for_user
        from app.services.spaces.types import SpaceConfig

        seed_for_user(db_session, user=director_user)
        db_session.refresh(director_user)
        prefs = dict(director_user.preferences or {})
        spaces = [SpaceConfig.from_dict(s) for s in prefs.get("spaces", [])]
        assert any(s.name == "Arrangement" for s in spaces)
        # Phase W-4a — Home is the only system space for non-admin.
        system = [s for s in spaces if s.is_system]
        assert len(system) == 1
        assert system[0].name == "Home"
        # Settings explicitly absent.
        assert not any(s.name == "Settings" for s in spaces)


# ── Delete protection ─────────────────────────────────────────────


class TestDeleteSystemSpaceBlocked:
    def test_delete_rejects_system_space(self, db_session, admin_user):
        from app.services.spaces import delete_space, seed_for_user
        from app.services.spaces.types import SpaceError

        seed_for_user(db_session, user=admin_user)
        db_session.refresh(admin_user)
        with pytest.raises(SpaceError, match="System spaces"):
            delete_space(
                db_session, user=admin_user, space_id="sys_settings"
            )

    def test_delete_user_space_still_works(self, db_session, admin_user):
        from app.services.spaces import (
            create_space,
            delete_space,
            seed_for_user,
        )

        seed_for_user(db_session, user=admin_user)
        db_session.refresh(admin_user)
        sp = create_space(db_session, user=admin_user, name="User Owned")
        delete_space(db_session, user=admin_user, space_id=sp.space_id)


# ── Role decoupling ───────────────────────────────────────────────


class TestRoleDecoupling:
    def test_reseed_flag_defaults_false(self):
        from app.services.user_service import ROLE_CHANGE_RESEED_ENABLED

        assert ROLE_CHANGE_RESEED_ENABLED is False

    def test_reapply_role_defaults_available(self, db_session, admin_user):
        from app.services.user_service import reapply_role_defaults_for_user

        counts = reapply_role_defaults_for_user(db_session, admin_user)
        assert "saved_views" in counts
        assert "spaces" in counts
        assert "briefings" in counts

    def test_role_change_does_not_reseed_saved_views(
        self, db_session, office_user
    ):
        """Upgrade office → director. Without Phase 8a decoupling,
        the director's saved views would append. With decoupling
        (ROLE_CHANGE_RESEED_ENABLED=False), they don't."""
        from app.models.role import Role
        from app.services.spaces import seed_for_user
        from app.services.saved_views.seed import (
            seed_for_user as sv_seed,
        )
        from app.services.user_service import update_user
        from app.schemas.user import UserUpdate

        # Initial seed as office.
        sv_seed(db_session, user=office_user)
        seed_for_user(db_session, user=office_user)
        db_session.refresh(office_user)
        initial_saved_views_roles = list(
            office_user.preferences.get("saved_views_seeded_for_roles", [])
        )
        assert "office" in initial_saved_views_roles

        # Create a director role in the same company.
        director_role = Role(
            id=str(uuid.uuid4()),
            company_id=office_user.company_id,
            name="Director",
            slug="director",
            is_system=True,
        )
        db_session.add(director_role)
        db_session.commit()

        # Change role to director.
        update_user(
            db_session,
            user_id=office_user.id,
            company_id=office_user.company_id,
            data=UserUpdate(role_id=director_role.id),
            actor_id=office_user.id,
        )
        db_session.refresh(office_user)
        post_saved_views_roles = list(
            office_user.preferences.get("saved_views_seeded_for_roles", [])
        )
        # With Phase 8a decoupling, director was NOT appended.
        assert "director" not in post_saved_views_roles
