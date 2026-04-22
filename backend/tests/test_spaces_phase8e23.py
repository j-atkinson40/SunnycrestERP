"""Phase 8e.2.3 — invariant widening + cap-breach + retrofit + icon default.

Scope:
  - `_apply_templates` cap-breach guard skips overflow templates with
    structured warning, allows partial seed, emits end-of-pass summary.
  - `_apply_system_spaces` mirrors the cap-breach guard.
  - Login defensive re-seed fires when `spaces_seeded_for_roles` is
    empty even if `spaces` is populated (James-shape).
  - r47 migration semantics exercised via direct seed_for_user call
    on a James-shape user (populated manual spaces, null seed marker).
  - Backend icon default flipped `layers` → `""` in crud.create_space.
  - Invariant sub-shape: platform-wide check uses both `spaces` AND
    `spaces_seeded_for_roles` simultaneously.

Fixture pattern mirrors test_spaces_invariant.py (dev-DB tenant +
role + user with best-effort cleanup).
"""

from __future__ import annotations

import logging
import uuid

import pytest


# ── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


def _make_tenant(*, vertical: str = "manufacturing") -> dict:
    from app.database import SessionLocal
    from app.models.company import Company
    from app.services.module_service import seed_company_modules
    from app.services.role_service import seed_default_roles

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"P8E23-{suffix}",
            slug=f"p8e23-{suffix}",
            is_active=True,
            vertical=vertical,
        )
        db.add(co)
        db.flush()
        admin_role, _ = seed_default_roles(db, co.id)
        seed_company_modules(db, co.id)
        db.commit()
        return {
            "company_id": co.id,
            "company_slug": co.slug,
            "admin_role_id": admin_role.id,
        }
    finally:
        db.close()


def _drop_tenant(company_id: str) -> None:
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        db.query(User).filter(User.company_id == company_id).delete(
            synchronize_session=False
        )
        db.query(Role).filter(Role.company_id == company_id).delete(
            synchronize_session=False
        )
        db.query(Company).filter(Company.id == company_id).delete(
            synchronize_session=False
        )
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _make_user_bare(
    db_session, *, ctx: dict, preferences: dict | None = None
):
    """Create a user tied to `ctx` with optional preferences dict.
    Does NOT run the seed hooks (direct-write). Used for simulating
    James-shape state where preferences.spaces is populated but the
    seed marker is missing."""
    from app.models.role import Role
    from app.models.user import User

    admin_role = (
        db_session.query(Role)
        .filter(Role.company_id == ctx["company_id"])
        .filter(Role.slug == "admin")
        .first()
    )
    user = User(
        id=str(uuid.uuid4()),
        company_id=ctx["company_id"],
        email=f"bare-{uuid.uuid4().hex[:6]}@p8e23.co",
        first_name="Bare",
        last_name="User",
        hashed_password="x",
        is_active=True,
        role_id=admin_role.id,
        preferences=preferences or {},
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ── Cap-breach guard in _apply_templates ──────────────────────────


class TestCapBreachGuard:
    """MAX_SPACES_PER_USER = 7. Cap-breach guard prevents seed_for_user
    from breaching the cap. Skipped templates log a structured WARNING
    per-template plus an end-of-pass INFO summary.
    """

    def test_cap_breach_skips_templates_with_warning(
        self, db_session, caplog
    ):
        """User with 6 manual spaces + 3-template role → only 1
        template gets appended (total=7, MAX=7); 2 templates skipped
        with WARNING per skip."""
        from app.services.spaces.seed import seed_for_user
        from app.services.spaces.types import SpaceConfig, now_iso

        ctx = _make_tenant(vertical="manufacturing")
        try:
            # Seed 6 manual spaces directly via preferences write.
            # We can't call crud.create_space (it also enforces cap);
            # we want to set up the EXACT boundary condition.
            manual_spaces = [
                SpaceConfig(
                    space_id=SpaceConfig.new_id(),
                    name=f"Manual{i}",
                    icon="",
                    accent="neutral",
                    display_order=i,
                    is_default=(i == 0),
                    density="comfortable",
                    pins=[],
                    created_at=now_iso(),
                    updated_at=now_iso(),
                ).to_dict()
                for i in range(6)
            ]
            user = _make_user_bare(
                db_session,
                ctx=ctx,
                preferences={"spaces": manual_spaces},
            )

            caplog.set_level(
                logging.WARNING, logger="app.services.spaces.seed"
            )
            caplog.set_level(logging.INFO, logger="app.services.spaces.seed")

            created = seed_for_user(db_session, user=user)

            # Manufacturing admin templates = 3 (Production + Sales +
            # Ownership). User has 6. Cap = 7. So exactly 1 template
            # should land; 2 get skipped.
            assert created == 1, (
                f"expected 1 template to fit under cap, got {created}"
            )
            db_session.refresh(user)
            spaces_after = (user.preferences or {}).get("spaces") or []
            assert len(spaces_after) == 7

            # At least 2 cap-breach WARNING lines should appear.
            warn_msgs = [
                r.getMessage()
                for r in caplog.records
                if r.levelname == "WARNING"
                and "cap-breach skip" in r.getMessage()
            ]
            assert len(warn_msgs) >= 2, (
                f"expected ≥2 cap-breach WARNINGs; got {len(warn_msgs)} "
                f"from records: {[r.getMessage() for r in caplog.records]}"
            )
            # Each must carry the diagnostic fields.
            for msg in warn_msgs[:2]:
                assert "user_id=" in msg
                assert "company_id=" in msg
                assert "role_slug=admin" in msg
                assert "template_name=" in msg
                assert "current_spaces=" in msg
                assert "max=7" in msg

            # End-of-pass INFO summary line present.
            info_summary = [
                r.getMessage()
                for r in caplog.records
                if r.levelname == "INFO"
                and "partial-seed" in r.getMessage()
            ]
            assert len(info_summary) >= 1, (
                "expected end-of-pass partial-seed INFO line; got none"
            )
            # Summary carries "N of M templates appended" shape.
            assert "added=1/3" in info_summary[0]
        finally:
            _drop_tenant(ctx["company_id"])

    def test_cap_not_breached_no_warning(self, db_session, caplog):
        """Happy path: user has 0 manual spaces, 3 templates fit,
        cap guard never fires — no WARNING, no partial-seed INFO."""
        from app.services.spaces.seed import seed_for_user

        ctx = _make_tenant(vertical="manufacturing")
        try:
            user = _make_user_bare(db_session, ctx=ctx, preferences={})
            caplog.set_level(
                logging.WARNING, logger="app.services.spaces.seed"
            )
            caplog.set_level(logging.INFO, logger="app.services.spaces.seed")

            created = seed_for_user(db_session, user=user)

            assert created >= 3
            warn_cap = [
                r.getMessage()
                for r in caplog.records
                if r.levelname == "WARNING"
                and "cap-breach" in r.getMessage()
            ]
            info_partial = [
                r.getMessage()
                for r in caplog.records
                if r.levelname == "INFO"
                and "partial-seed" in r.getMessage()
            ]
            assert warn_cap == []
            assert info_partial == []
        finally:
            _drop_tenant(ctx["company_id"])


# ── James-shape retrofit ─────────────────────────────────────────────


class TestJamesShapeRetrofit:
    """r47 target cohort: users with non-empty spaces but empty
    spaces_seeded_for_roles marker. seed_for_user on this state should
    preserve manual spaces + append templates + populate the marker."""

    def test_james_shape_preserves_manual_and_adds_templates(
        self, db_session
    ):
        """Simulates James: 2 manually-named spaces with no seed marker.
        Post-seed: manual spaces still present + template names
        appended + marker populated with current role slug."""
        from app.services.spaces.seed import seed_for_user
        from app.services.spaces.types import SpaceConfig, now_iso

        ctx = _make_tenant(vertical="manufacturing")
        try:
            manual = [
                SpaceConfig(
                    space_id=SpaceConfig.new_id(),
                    name=n,
                    icon="",
                    accent="neutral",
                    display_order=i,
                    is_default=(i == 0),
                    density="comfortable",
                    pins=[],
                    created_at=now_iso(),
                    updated_at=now_iso(),
                ).to_dict()
                for i, n in enumerate(["Accounting", "Operations"])
            ]
            user = _make_user_bare(
                db_session, ctx=ctx, preferences={"spaces": manual}
            )
            assert (
                (user.preferences or {}).get("spaces_seeded_for_roles") is None
                or (user.preferences or {}).get("spaces_seeded_for_roles") == []
            )

            created = seed_for_user(db_session, user=user)

            # Manufacturing admin → 3 template spaces appended.
            # System Settings space (+1) adds on top if admin perm
            # resolves. Lower bound 3.
            assert created >= 3

            db_session.refresh(user)
            prefs = user.preferences or {}
            spaces = prefs.get("spaces") or []
            names = {s.get("name") for s in spaces}

            # Manual spaces preserved.
            assert "Accounting" in names
            assert "Operations" in names
            # Template spaces added.
            assert "Production" in names
            assert "Sales" in names
            assert "Ownership" in names

            # Marker populated with current role.
            assert "admin" in (prefs.get("spaces_seeded_for_roles") or [])
        finally:
            _drop_tenant(ctx["company_id"])

    def test_retrofit_is_idempotent(self, db_session):
        """Second seed on a James-shape user (now retrofitted) is
        a no-op — marker gates it."""
        from app.services.spaces.seed import seed_for_user
        from app.services.spaces.types import SpaceConfig, now_iso

        ctx = _make_tenant(vertical="manufacturing")
        try:
            user = _make_user_bare(
                db_session,
                ctx=ctx,
                preferences={
                    "spaces": [
                        SpaceConfig(
                            space_id=SpaceConfig.new_id(),
                            name="Custom",
                            icon="",
                            accent="neutral",
                            display_order=0,
                            is_default=True,
                            density="comfortable",
                            pins=[],
                            created_at=now_iso(),
                            updated_at=now_iso(),
                        ).to_dict()
                    ]
                },
            )
            first = seed_for_user(db_session, user=user)
            assert first >= 3
            db_session.refresh(user)
            count_after_first = len((user.preferences or {}).get("spaces") or [])

            second = seed_for_user(db_session, user=user)
            assert second == 0
            db_session.refresh(user)
            count_after_second = len((user.preferences or {}).get("spaces") or [])
            assert count_after_first == count_after_second
        finally:
            _drop_tenant(ctx["company_id"])


# ── Login defensive re-seed widened gate ─────────────────────────────


class TestDefensiveReseedWidenedGate:
    """Phase 8e.2.2 gate was `if not spaces` — skipped James-shape.
    Phase 8e.2.3 widens to `if not spaces OR not spaces_seeded_for_roles`
    so James-shape users get retrofitted at login."""

    def test_login_fires_for_james_shape_user(self, db_session):
        from app.core.security import hash_password
        from app.models.company import Company
        from app.models.user import User
        from app.schemas.auth import LoginRequest
        from app.services.auth_service import login_user
        from app.services.spaces.types import SpaceConfig, now_iso

        ctx = _make_tenant(vertical="manufacturing")
        try:
            # James-shape: user has 2 manual spaces but NO seed marker.
            manual = [
                SpaceConfig(
                    space_id=SpaceConfig.new_id(),
                    name=n,
                    icon="",
                    accent="neutral",
                    display_order=i,
                    is_default=(i == 0),
                    density="comfortable",
                    pins=[],
                    created_at=now_iso(),
                    updated_at=now_iso(),
                ).to_dict()
                for i, n in enumerate(["Accounting", "Operations"])
            ]
            from app.models.role import Role

            admin_role = (
                db_session.query(Role)
                .filter(Role.company_id == ctx["company_id"])
                .filter(Role.slug == "admin")
                .first()
            )
            user = User(
                id=str(uuid.uuid4()),
                company_id=ctx["company_id"],
                email=f"james-{uuid.uuid4().hex[:6]}@p8e23.co",
                first_name="James",
                last_name="Shape",
                hashed_password=hash_password("Pw123456!"),
                is_active=True,
                role_id=admin_role.id,
                preferences={"spaces": manual},  # marker absent!
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)

            # Invariant — pre-login: spaces populated, marker empty.
            assert len((user.preferences or {}).get("spaces") or []) == 2
            assert not (user.preferences or {}).get(
                "spaces_seeded_for_roles"
            )

            company = (
                db_session.query(Company)
                .filter(Company.id == ctx["company_id"])
                .one()
            )
            req = LoginRequest(email=user.email, password="Pw123456!")
            login_user(db_session, req, company)

            db_session.refresh(user)
            post_spaces = (user.preferences or {}).get("spaces") or []
            names = {s.get("name") for s in post_spaces}
            # Templates appended via login defensive re-seed.
            assert "Production" in names
            assert "Sales" in names
            assert "Ownership" in names
            # Manual spaces preserved.
            assert "Accounting" in names
            assert "Operations" in names
            # Marker now populated.
            assert "admin" in (
                (user.preferences or {}).get("spaces_seeded_for_roles") or []
            )
        finally:
            _drop_tenant(ctx["company_id"])

    def test_login_noop_for_fully_seeded_user(self, db_session):
        """User with both `spaces` populated AND `spaces_seeded_for_roles`
        populated — login gate skips re-seed."""
        from app.core.security import hash_password
        from app.models.company import Company
        from app.models.role import Role
        from app.models.user import User
        from app.schemas.auth import LoginRequest
        from app.services.auth_service import login_user
        from app.services.spaces.seed import seed_for_user

        ctx = _make_tenant(vertical="manufacturing")
        try:
            admin_role = (
                db_session.query(Role)
                .filter(Role.company_id == ctx["company_id"])
                .filter(Role.slug == "admin")
                .first()
            )
            user = User(
                id=str(uuid.uuid4()),
                company_id=ctx["company_id"],
                email=f"good-{uuid.uuid4().hex[:6]}@p8e23.co",
                first_name="Fully",
                last_name="Seeded",
                hashed_password=hash_password("Pw123456!"),
                is_active=True,
                role_id=admin_role.id,
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)

            seed_for_user(db_session, user=user)
            db_session.refresh(user)
            pre_count = len((user.preferences or {}).get("spaces") or [])
            assert pre_count >= 3

            company = (
                db_session.query(Company)
                .filter(Company.id == ctx["company_id"])
                .one()
            )
            req = LoginRequest(email=user.email, password="Pw123456!")
            login_user(db_session, req, company)

            db_session.refresh(user)
            post_count = len((user.preferences or {}).get("spaces") or [])
            assert post_count == pre_count
        finally:
            _drop_tenant(ctx["company_id"])


# ── Icon default flip ────────────────────────────────────────────────


class TestIconDefaultFlip:
    """crud.create_space default flipped `layers` → `""`. API
    _CreateRequest Pydantic schema flipped in lockstep. New user-
    created spaces have empty `icon`."""

    def test_crud_default_icon_empty(self, db_session):
        from app.services.spaces.crud import create_space

        ctx = _make_tenant(vertical="manufacturing")
        try:
            user = _make_user_bare(db_session, ctx=ctx)
            space = create_space(
                db_session, user=user, name="Test Custom"
            )
            assert space.icon == "", (
                f"expected empty icon default, got {space.icon!r}"
            )
        finally:
            _drop_tenant(ctx["company_id"])

    def test_api_schema_default_icon_empty(self):
        from app.api.routes.spaces import _CreateRequest

        req = _CreateRequest(name="Thing")
        assert req.icon == ""

    def test_explicit_icon_still_honored(self, db_session):
        from app.services.spaces.crud import create_space

        ctx = _make_tenant(vertical="manufacturing")
        try:
            user = _make_user_bare(db_session, ctx=ctx)
            space = create_space(
                db_session, user=user, name="With Icon", icon="factory"
            )
            assert space.icon == "factory"
        finally:
            _drop_tenant(ctx["company_id"])


# ── Platform-wide widened invariant ─────────────────────────────────


class TestWidenedInvariant:
    """Phase 8e.2.3 platform invariant: every active user has
    `spaces_seeded_for_roles` non-empty (not just `spaces`). This
    is the sub-shape the audit said was missing."""

    def test_invariant_no_active_user_has_empty_seed_marker(self, db_session):
        from sqlalchemy import text

        try:
            head = (
                db_session.execute(
                    text("SELECT version_num FROM alembic_version LIMIT 1")
                )
                .first()
            )
        except Exception:
            pytest.skip("alembic_version table not available")

        if head is None:
            pytest.skip("no alembic_version row")

        if head[0] != "r47_users_template_defaults_retrofit":
            pytest.skip(
                f"r47 not current head (current={head[0]}); "
                "widened invariant asserted post-retrofit only"
            )

        # How many active users have preferences.spaces_seeded_for_roles
        # empty/null? Should be 0 after r47 (or very small for fixture
        # teardown races). Test-fixture domains excluded for the same
        # reason as test_spaces_invariant.py — dev DB accumulates
        # short-lived uninitialized users from failed test runs.
        count = db_session.execute(
            text(
                """
                SELECT COUNT(*) FROM users
                WHERE is_active = TRUE
                  AND COALESCE(
                    preferences -> 'spaces_seeded_for_roles',
                    '[]'::jsonb
                  ) = '[]'::jsonb
                  AND email NOT LIKE '%@sp.co'
                  AND email NOT LIKE '%@sys.co'
                  AND email NOT LIKE '%@inv.co'
                  AND email NOT LIKE '%@p8e.co'
                  AND email NOT LIKE '%@p8e23.co'
                  AND email NOT LIKE '%@8e1.co'
                  AND email NOT LIKE '%@portal.test'
                """
            )
        ).scalar()

        assert count is not None and count <= 5, (
            f"Widened invariant violated: {count} active users have empty "
            f"spaces_seeded_for_roles after r47. Either the migration "
            f"skipped some cohort, or a creation path is still bypassing "
            f"seed hooks, or login defensive re-seed isn't firing on "
            f"the remaining cases. Investigate."
        )
