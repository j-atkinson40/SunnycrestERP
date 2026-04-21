"""Unit tests — Spaces registry + crud + seed + pins.

Scope: pure service-layer with a real DB session (the crud layer
writes JSONB + reads VaultItems). No HTTP.

Covers:
  - Registry: templates exist per seeded role, fallback returns
    General template, static nav label lookup
  - CRUD: create/update/delete/reorder, 5-space cap, default
    reassignment on delete, active-space clearing on delete
  - Seed: idempotency via spaces_seeded_for_roles, no-role fallback,
    saved-view seed-key resolution to actual view ids, template
    additions don't backfill
  - Pins: add/remove/reorder, de-dupe on add, unavailable
    resolution when saved-view missing
"""

from __future__ import annotations

import uuid

import pytest

from app.services.spaces import (
    MAX_SPACES_PER_USER,
    SpaceLimitExceeded,
    SpaceNotFound,
    add_pin,
    create_space,
    delete_space,
    get_active_space_id,
    get_spaces_for_user,
    remove_pin,
    reorder_pins,
    reorder_spaces,
    seed_for_user,
    set_active_space,
    update_space,
)
from app.services.spaces import registry as reg
from app.services.spaces.types import PinNotFound, SpaceError


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


def _make_tenant_user(
    *,
    role_slug: str = "admin",
    vertical: str = "manufacturing",
):
    """Spin up a tenant + role + user + return the User ORM."""
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"SP-{suffix}",
            slug=f"sp-{suffix}",
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
            email=f"u-{suffix}@sp.co",
            first_name="SP",
            last_name="User",
            hashed_password="x",
            is_active=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        return user.id, co.id, role.slug
    finally:
        db.close()


@pytest.fixture
def fresh_user(db_session):
    user_id, company_id, role_slug = _make_tenant_user(
        role_slug="director", vertical="funeral_home"
    )
    from app.models.user import User

    return db_session.query(User).filter(User.id == user_id).one()


@pytest.fixture
def fresh_admin_mfg(db_session):
    user_id, _, _ = _make_tenant_user(role_slug="admin", vertical="manufacturing")
    from app.models.user import User

    return db_session.query(User).filter(User.id == user_id).one()


# ── Registry tests ──────────────────────────────────────────────────


class TestRegistry:
    def test_templates_exist_for_seeded_roles(self):
        pairs = reg.all_template_pairs()
        assert ("funeral_home", "director") in pairs
        assert ("manufacturing", "production") in pairs
        assert ("manufacturing", "admin") in pairs

    def test_fh_director_has_arrangement_as_default(self):
        templates = reg.get_templates("funeral_home", "director")
        defaults = [t for t in templates if t.is_default]
        assert len(defaults) == 1
        assert defaults[0].name == "Arrangement"

    def test_unknown_pair_returns_fallback(self):
        templates = reg.get_templates("funeral_home", "xyz_nonexistent")
        assert len(templates) == 1
        assert templates[0].name == "General"
        assert templates[0].is_default is True

    def test_none_vertical_returns_fallback(self):
        templates = reg.get_templates(None, "director")
        assert templates == [reg.FALLBACK_TEMPLATE]

    def test_nav_label_lookup_known(self):
        out = reg.get_nav_label("/cases")
        assert out is not None
        assert out[0] == "Active Cases"

    def test_nav_label_lookup_unknown_returns_none(self):
        assert reg.get_nav_label("/zzzz-does-not-exist") is None

    def test_is_seed_key(self):
        assert reg.is_seed_key("saved_view_seed:director:my_active_cases")
        assert not reg.is_seed_key("/cases")


# ── Seed tests ──────────────────────────────────────────────────────


class TestSeed:
    def test_fh_director_seeds_three_spaces(self, db_session, fresh_user):
        created = seed_for_user(db_session, user=fresh_user)
        assert created == 3  # Arrangement + Administrative + Ownership
        spaces = get_spaces_for_user(db_session, user=fresh_user)
        names = {s.name for s in spaces}
        assert {"Arrangement", "Administrative", "Ownership"} == names

    def test_seed_records_role_in_preferences(self, db_session, fresh_user):
        seed_for_user(db_session, user=fresh_user)
        db_session.refresh(fresh_user)
        seeded = fresh_user.preferences.get("spaces_seeded_for_roles", [])
        assert "director" in seeded

    def test_seed_is_idempotent(self, db_session, fresh_user):
        first = seed_for_user(db_session, user=fresh_user)
        db_session.refresh(fresh_user)
        second = seed_for_user(db_session, user=fresh_user)
        assert first == 3
        assert second == 0

    def test_seed_sets_active_space_id(self, db_session, fresh_user):
        seed_for_user(db_session, user=fresh_user)
        db_session.refresh(fresh_user)
        active = get_active_space_id(fresh_user)
        assert active is not None
        # Should be the default (Arrangement for FH director)
        spaces = get_spaces_for_user(db_session, user=fresh_user)
        default = next(s for s in spaces if s.is_default)
        assert active == default.space_id

    def test_unknown_role_slug_seeds_fallback(self, db_session):
        # Custom role that doesn't have a template — e.g. a tenant
        # defines an "intern" role. Registry returns the fallback,
        # seed creates exactly one "General" space.
        user_id, _, _ = _make_tenant_user(
            role_slug="intern", vertical="manufacturing"
        )
        from app.models.user import User

        user = db_session.query(User).filter(User.id == user_id).one()
        created = seed_for_user(db_session, user=user)
        assert created == 1
        spaces = get_spaces_for_user(db_session, user=user)
        assert len(spaces) == 1
        assert spaces[0].name == "General"
        assert spaces[0].is_default is True

    def test_saved_view_seed_key_resolves_after_phase2_seed(
        self, db_session, fresh_user
    ):
        """Integration with Phase 2: if the Phase 2 saved-view seed
        already ran, Phase 3 pin resolution should find the view."""
        from app.services.saved_views.seed import seed_for_user as sv_seed

        sv_seed(db_session, user=fresh_user)
        seed_for_user(db_session, user=fresh_user)
        spaces = get_spaces_for_user(db_session, user=fresh_user)
        arrangement = next(s for s in spaces if s.name == "Arrangement")
        # The "my active cases" saved view pin should resolve
        resolved = [p for p in arrangement.pins if p.pin_type == "saved_view"]
        assert len(resolved) >= 1
        hit = next(
            (p for p in resolved if p.saved_view_title == "My active cases"),
            None,
        )
        assert hit is not None, f"resolved pins: {[(p.label, p.unavailable) for p in resolved]}"
        assert hit.unavailable is False
        assert hit.saved_view_id is not None

    def test_saved_view_pin_marked_unavailable_when_view_missing(
        self, db_session, fresh_user
    ):
        """If Phase 2 seed did NOT run, the saved-view pins are still
        stored but render unavailable."""
        # Don't call sv_seed — go straight to Phase 3 seed.
        seed_for_user(db_session, user=fresh_user)
        spaces = get_spaces_for_user(db_session, user=fresh_user)
        arrangement = next(s for s in spaces if s.name == "Arrangement")
        sv_pins = [p for p in arrangement.pins if p.pin_type == "saved_view"]
        # All saved-view pins should be unavailable since we skipped
        # the Phase 2 seed.
        assert len(sv_pins) >= 1
        for pin in sv_pins:
            assert pin.unavailable is True
            assert pin.href is None


# ── CRUD tests ──────────────────────────────────────────────────────


class TestCrud:
    def test_create_space_roundtrip(self, db_session, fresh_user):
        sp = create_space(
            db_session, user=fresh_user, name="Test Space", icon="home",
            accent="warm", is_default=False,
        )
        assert sp.space_id.startswith("sp_")
        assert sp.name == "Test Space"
        assert sp.icon == "home"
        assert sp.accent == "warm"
        # First space is always forced default regardless of flag.
        assert sp.is_default is True

    def test_first_space_always_default(self, db_session, fresh_user):
        sp = create_space(
            db_session, user=fresh_user, name="Only", is_default=False
        )
        assert sp.is_default is True

    def test_promoting_new_default_demotes_previous(self, db_session, fresh_user):
        a = create_space(db_session, user=fresh_user, name="A")
        b = create_space(
            db_session, user=fresh_user, name="B", is_default=True
        )
        spaces = get_spaces_for_user(db_session, user=fresh_user)
        a_after = next(s for s in spaces if s.space_id == a.space_id)
        b_after = next(s for s in spaces if s.space_id == b.space_id)
        assert a_after.is_default is False
        assert b_after.is_default is True

    def test_five_space_cap(self, db_session, fresh_user):
        for i in range(MAX_SPACES_PER_USER):
            create_space(db_session, user=fresh_user, name=f"S{i}")
        with pytest.raises(SpaceLimitExceeded):
            create_space(db_session, user=fresh_user, name="Overflow")

    def test_update_name_and_accent(self, db_session, fresh_user):
        sp = create_space(db_session, user=fresh_user, name="Original")
        updated = update_space(
            db_session, user=fresh_user, space_id=sp.space_id,
            name="Renamed", accent="industrial",
        )
        assert updated.name == "Renamed"
        assert updated.accent == "industrial"

    def test_update_unsetting_only_default_rejected(
        self, db_session, fresh_user
    ):
        sp = create_space(db_session, user=fresh_user, name="Only")
        with pytest.raises(SpaceError):
            update_space(
                db_session, user=fresh_user, space_id=sp.space_id,
                is_default=False,
            )

    def test_delete_promotes_new_default(self, db_session, fresh_user):
        a = create_space(db_session, user=fresh_user, name="A")  # default
        b = create_space(db_session, user=fresh_user, name="B")
        delete_space(db_session, user=fresh_user, space_id=a.space_id)
        spaces = get_spaces_for_user(db_session, user=fresh_user)
        assert len(spaces) == 1
        assert spaces[0].space_id == b.space_id
        assert spaces[0].is_default is True

    def test_delete_clears_active_space(self, db_session, fresh_user):
        a = create_space(db_session, user=fresh_user, name="A")
        set_active_space(db_session, user=fresh_user, space_id=a.space_id)
        delete_space(db_session, user=fresh_user, space_id=a.space_id)
        assert get_active_space_id(fresh_user) is None

    def test_delete_missing_raises_404(self, db_session, fresh_user):
        with pytest.raises(SpaceNotFound):
            delete_space(db_session, user=fresh_user, space_id="sp_nonexistent")

    def test_reorder_spaces(self, db_session, fresh_user):
        a = create_space(db_session, user=fresh_user, name="A")
        b = create_space(db_session, user=fresh_user, name="B")
        c = create_space(db_session, user=fresh_user, name="C")
        reorder_spaces(
            db_session, user=fresh_user,
            space_ids_in_order=[c.space_id, a.space_id, b.space_id],
        )
        out = get_spaces_for_user(db_session, user=fresh_user)
        assert [s.space_id for s in out] == [c.space_id, a.space_id, b.space_id]
        assert [s.display_order for s in out] == [0, 1, 2]

    def test_reorder_wrong_set_rejected(self, db_session, fresh_user):
        a = create_space(db_session, user=fresh_user, name="A")
        with pytest.raises(SpaceError):
            reorder_spaces(
                db_session, user=fresh_user,
                space_ids_in_order=[a.space_id, "sp_fake"],
            )

    def test_set_active_space_updates_prefs(self, db_session, fresh_user):
        a = create_space(db_session, user=fresh_user, name="A")
        b = create_space(db_session, user=fresh_user, name="B")
        set_active_space(db_session, user=fresh_user, space_id=b.space_id)
        db_session.refresh(fresh_user)
        assert get_active_space_id(fresh_user) == b.space_id

    def test_set_active_space_missing_raises(self, db_session, fresh_user):
        with pytest.raises(SpaceNotFound):
            set_active_space(
                db_session, user=fresh_user, space_id="sp_missing"
            )


# ── Pin tests ───────────────────────────────────────────────────────


class TestPins:
    def test_add_nav_pin(self, db_session, fresh_user):
        sp = create_space(db_session, user=fresh_user, name="S")
        pin = add_pin(
            db_session, user=fresh_user, space_id=sp.space_id,
            pin_type="nav_item", target_id="/cases",
        )
        assert pin.pin_id.startswith("pn_")
        assert pin.pin_type == "nav_item"
        assert pin.href == "/cases"
        # Label comes from the static label table
        assert pin.label == "Active Cases"
        assert pin.icon == "FolderOpen"

    def test_add_pin_is_idempotent(self, db_session, fresh_user):
        sp = create_space(db_session, user=fresh_user, name="S")
        p1 = add_pin(
            db_session, user=fresh_user, space_id=sp.space_id,
            pin_type="nav_item", target_id="/cases",
        )
        p2 = add_pin(
            db_session, user=fresh_user, space_id=sp.space_id,
            pin_type="nav_item", target_id="/cases",
        )
        # Same pin returned, not a duplicate.
        assert p1.pin_id == p2.pin_id
        space = next(
            s for s in get_spaces_for_user(db_session, user=fresh_user)
            if s.space_id == sp.space_id
        )
        assert len([p for p in space.pins if p.target_id == "/cases"]) == 1

    def test_add_pin_with_label_override(self, db_session, fresh_user):
        sp = create_space(db_session, user=fresh_user, name="S")
        pin = add_pin(
            db_session, user=fresh_user, space_id=sp.space_id,
            pin_type="nav_item", target_id="/financials",
            label_override="$$$",
        )
        assert pin.label == "$$$"

    def test_remove_pin(self, db_session, fresh_user):
        sp = create_space(db_session, user=fresh_user, name="S")
        pin = add_pin(
            db_session, user=fresh_user, space_id=sp.space_id,
            pin_type="nav_item", target_id="/cases",
        )
        remove_pin(
            db_session, user=fresh_user, space_id=sp.space_id,
            pin_id=pin.pin_id,
        )
        space = next(
            s for s in get_spaces_for_user(db_session, user=fresh_user)
            if s.space_id == sp.space_id
        )
        assert space.pins == []

    def test_remove_missing_pin_raises(self, db_session, fresh_user):
        sp = create_space(db_session, user=fresh_user, name="S")
        with pytest.raises(PinNotFound):
            remove_pin(
                db_session, user=fresh_user, space_id=sp.space_id,
                pin_id="pn_missing",
            )

    def test_reorder_pins(self, db_session, fresh_user):
        sp = create_space(db_session, user=fresh_user, name="S")
        p1 = add_pin(
            db_session, user=fresh_user, space_id=sp.space_id,
            pin_type="nav_item", target_id="/cases",
        )
        p2 = add_pin(
            db_session, user=fresh_user, space_id=sp.space_id,
            pin_type="nav_item", target_id="/financials",
        )
        reorder_pins(
            db_session, user=fresh_user, space_id=sp.space_id,
            pin_ids_in_order=[p2.pin_id, p1.pin_id],
        )
        space = next(
            s for s in get_spaces_for_user(db_session, user=fresh_user)
            if s.space_id == sp.space_id
        )
        assert [p.pin_id for p in space.pins] == [p2.pin_id, p1.pin_id]

    def test_unknown_nav_href_gets_fallback_label(self, db_session, fresh_user):
        sp = create_space(db_session, user=fresh_user, name="S")
        pin = add_pin(
            db_session, user=fresh_user, space_id=sp.space_id,
            pin_type="nav_item", target_id="/some-unknown-path",
        )
        # Unknown href → label falls back to the href string, icon "Link"
        assert pin.label == "/some-unknown-path"
        assert pin.icon == "Link"

    def test_unknown_pin_type_rejected(self, db_session, fresh_user):
        sp = create_space(db_session, user=fresh_user, name="S")
        with pytest.raises(SpaceError):
            add_pin(
                db_session, user=fresh_user, space_id=sp.space_id,
                pin_type="mystery",  # type: ignore[arg-type]
                target_id="/cases",
            )


# ── Manufacturing admin role seeding ────────────────────────────────


class TestManufacturingAdminSeeding:
    def test_seeds_production_sales_ownership(
        self, db_session, fresh_admin_mfg
    ):
        seed_for_user(db_session, user=fresh_admin_mfg)
        spaces = get_spaces_for_user(db_session, user=fresh_admin_mfg)
        names = {s.name for s in spaces}
        # Phase 8a: admin users also receive the Settings system space
        # alongside their role-template seeds. The role-template output
        # is still Production + Sales + Ownership; assert is_system=False
        # for those three and the default is still Production.
        role_names = {s.name for s in spaces if not s.is_system}
        assert {"Production", "Sales", "Ownership"} == role_names
        assert "Settings" in names
        default = next(s for s in spaces if s.is_default)
        assert default.name == "Production"
