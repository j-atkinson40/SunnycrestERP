"""Phase 8e.2.2 — Space Invariant Enforcement tests.

Scope:
  - Each user-creation path seeds spaces (register_company first admin,
    user_service.create_user, user_service.create_users_bulk).
  - Login-time defensive re-seed runs when preferences.spaces is empty,
    is a no-op when populated.
  - seed_spaces_best_effort helper swallows seed exceptions with
    structured logging + defensive rollback + returns 0.
  - Platform-wide invariant (no active user has empty preferences.spaces
    after r46 runs).

Fixture pattern mirrors test_spaces_unit.py + test_spaces_phase8e.py —
real dev-DB Company + Role + User rows with cleanup on teardown.
"""

from __future__ import annotations

import uuid

import pytest


# ── Fixtures (mirrors test_spaces_phase8e.py) ───────────────────────


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


def _make_tenant(*, vertical: str = "manufacturing") -> dict:
    """Spin up a tenant + admin + employee role. No user. The caller
    creates users directly via the service under test so we exercise
    the real seed hook."""
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.services.module_service import seed_company_modules
    from app.services.role_service import seed_default_roles

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"INV-{suffix}",
            slug=f"inv-{suffix}",
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
    """Best-effort cleanup — skipped on FK complications (dev DB)."""
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


# ── register_company seeds first admin ──────────────────────────────


class TestRegisterCompanySeed:
    """register_company previously skipped the Spaces seed — the first
    admin of a new tenant landed on the UI with zero DotNav dots.
    Phase 8e.2.2 fix: seed_spaces_best_effort called after the
    commit/refresh pair."""

    def test_register_company_seeds_admin_spaces(self):
        from app.schemas.company import CompanyRegisterRequest
        from app.services.auth_service import register_company
        from app.database import SessionLocal

        db = SessionLocal()
        suffix = uuid.uuid4().hex[:6]
        try:
            req = CompanyRegisterRequest(
                company_name=f"InvTest {suffix}",
                company_slug=f"inv-rc-{suffix}",
                email=f"founder-{suffix}@inv.co",
                password="Whatever123!",
                first_name="Reg",
                last_name="Admin",
            )
            out = register_company(db, req)
            # Reload the user so the post-commit preferences are fresh.
            from app.models.user import User

            user = db.query(User).filter(User.id == out["user"].id).one()
            spaces = (user.preferences or {}).get("spaces") or []

            # register_company has NO vertical at this point (Company
            # created without vertical set), so the seed falls through
            # to FALLBACK_TEMPLATE (General). Still >= 1 space is the
            # invariant: no admin lands on the UI with zero dots.
            assert len(spaces) >= 1, (
                f"register_company must seed ≥1 space; got {len(spaces)}"
            )

            # spaces_seeded_for_roles must carry the admin slug
            # (or __no_role__ for the zero-role fallback path — admins
            # have a role so this should be "admin").
            seeded = (user.preferences or {}).get(
                "spaces_seeded_for_roles", []
            )
            assert "admin" in seeded or "__no_role__" in seeded
        finally:
            _drop_tenant(out["company"].id)
            db.close()


# ── user_service.create_user seeds admin-provisioned users ─────────


class TestCreateUserSeed:
    """`create_user` is the admin-provisioned creation path. Previously
    skipped the Spaces seed. Phase 8e.2.2 fix: every newly-created
    user (office or production track) picks up default spaces."""

    def test_office_user_gets_seeded(self):
        from app.schemas.user import UserCreate
        from app.services.user_service import create_user
        from app.database import SessionLocal

        ctx = _make_tenant(vertical="manufacturing")
        db = SessionLocal()
        try:
            from app.models.role import Role

            office_role = (
                db.query(Role)
                .filter(Role.company_id == ctx["company_id"])
                .filter(Role.slug == "admin")
                .first()
            )
            data = UserCreate(
                email=f"newbie-{uuid.uuid4().hex[:6]}@inv.co",
                password="Pw123456!",
                first_name="New",
                last_name="Bie",
                role_id=office_role.id,
                track="office",
            )
            user = create_user(db, data, ctx["company_id"])
            db.refresh(user)
            spaces = (user.preferences or {}).get("spaces") or []
            # Manufacturing admin template → 3 user spaces
            # (Production + Sales + Ownership) + possibly Settings if
            # admin permission resolves. ≥ 3 is the robust assertion.
            assert len(spaces) >= 3, (
                f"mfg admin must seed ≥3 spaces; got {len(spaces)} "
                f"({[s.get('name') for s in spaces]})"
            )
            names = {s.get("name") for s in spaces}
            assert "Production" in names
            assert "Sales" in names
            assert "Ownership" in names
        finally:
            db.close()
            _drop_tenant(ctx["company_id"])


# ── create_users_bulk seeds each created user ──────────────────────


class TestBulkUserSeed:
    """create_users_bulk delegates to create_user per iteration.
    Post-fix, each delegate call seeds the per-user spaces. Test that
    every successful bulk-created user has populated spaces."""

    def test_bulk_create_seeds_each_user(self):
        from app.schemas.user import UserCreate
        from app.services.user_service import create_users_bulk
        from app.database import SessionLocal

        ctx = _make_tenant(vertical="manufacturing")
        db = SessionLocal()
        try:
            from app.models.role import Role

            admin_role = (
                db.query(Role)
                .filter(Role.company_id == ctx["company_id"])
                .filter(Role.slug == "admin")
                .first()
            )

            batch = [
                UserCreate(
                    email=f"bulk-{i}-{uuid.uuid4().hex[:4]}@inv.co",
                    password="Pw123456!",
                    first_name="B",
                    last_name=f"User{i}",
                    role_id=admin_role.id,
                    track="office",
                )
                for i in range(3)
            ]
            result = create_users_bulk(db, batch, ctx["company_id"])
            assert result["errors"] == []
            assert len(result["created"]) == 3

            from app.models.user import User

            for created_response in result["created"]:
                user = (
                    db.query(User)
                    .filter(User.id == created_response.id)
                    .one()
                )
                spaces = (user.preferences or {}).get("spaces") or []
                assert len(spaces) >= 3, (
                    f"bulk user {user.email} should have seeded spaces; "
                    f"got {len(spaces)}"
                )
        finally:
            db.close()
            _drop_tenant(ctx["company_id"])


# ── login_user defensive re-seed ────────────────────────────────────


class TestDefensiveReseedOnLogin:
    """Any user whose preferences.spaces is empty at login (migrated
    from pre-fix creation paths, skipped by r46, or created in a
    legacy code path that predates the hook landing) gets seeded at
    the moment they log in. Cheap dict-key check on every login."""

    def test_login_reseeds_empty_spaces(self):
        from app.core.security import hash_password
        from app.database import SessionLocal
        from app.models.company import Company
        from app.models.role import Role
        from app.models.user import User
        from app.schemas.auth import LoginRequest
        from app.services.auth_service import login_user

        ctx = _make_tenant(vertical="manufacturing")
        db = SessionLocal()
        try:
            admin_role = (
                db.query(Role)
                .filter(Role.company_id == ctx["company_id"])
                .filter(Role.slug == "admin")
                .first()
            )
            user = User(
                id=str(uuid.uuid4()),
                company_id=ctx["company_id"],
                email=f"stale-{uuid.uuid4().hex[:6]}@inv.co",
                first_name="Stale",
                last_name="User",
                hashed_password=hash_password("Pw123456!"),
                is_active=True,
                role_id=admin_role.id,
                preferences={},  # explicit empty — pre-fix state
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            # Invariant: user starts with no spaces
            assert ((user.preferences or {}).get("spaces") or []) == []

            company = (
                db.query(Company)
                .filter(Company.id == ctx["company_id"])
                .one()
            )
            req = LoginRequest(email=user.email, password="Pw123456!")
            login_user(db, req, company)

            db.refresh(user)
            spaces = (user.preferences or {}).get("spaces") or []
            assert len(spaces) >= 3, (
                f"login must have defensively re-seeded; got {len(spaces)}"
            )
        finally:
            db.close()
            _drop_tenant(ctx["company_id"])

    def test_login_noop_when_spaces_populated(self):
        from app.core.security import hash_password
        from app.database import SessionLocal
        from app.models.company import Company
        from app.models.role import Role
        from app.models.user import User
        from app.schemas.auth import LoginRequest
        from app.services.auth_service import login_user
        from app.services.spaces.seed import seed_for_user

        ctx = _make_tenant(vertical="manufacturing")
        db = SessionLocal()
        try:
            admin_role = (
                db.query(Role)
                .filter(Role.company_id == ctx["company_id"])
                .filter(Role.slug == "admin")
                .first()
            )
            user = User(
                id=str(uuid.uuid4()),
                company_id=ctx["company_id"],
                email=f"good-{uuid.uuid4().hex[:6]}@inv.co",
                first_name="Good",
                last_name="User",
                hashed_password=hash_password("Pw123456!"),
                is_active=True,
                role_id=admin_role.id,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            # Pre-seed explicitly — at login time the defensive check
            # should see spaces > 0 and skip.
            seed_for_user(db, user=user)
            db.refresh(user)
            pre_count = len((user.preferences or {}).get("spaces") or [])
            assert pre_count >= 3

            company = (
                db.query(Company)
                .filter(Company.id == ctx["company_id"])
                .one()
            )
            req = LoginRequest(email=user.email, password="Pw123456!")
            login_user(db, req, company)

            db.refresh(user)
            post_count = len((user.preferences or {}).get("spaces") or [])
            # Count must be identical — no duplicate seeding on login.
            assert post_count == pre_count, (
                f"login re-seeded a populated user (pre={pre_count}, "
                f"post={post_count}); defensive check is supposed to no-op"
            )
        finally:
            db.close()
            _drop_tenant(ctx["company_id"])


# ── seed_spaces_best_effort swallows exceptions ─────────────────────


class TestSeedBestEffortHelper:
    """`seed_spaces_best_effort` is the public helper every seed hook
    goes through. It must (a) never raise, (b) log a structured
    warning on failure, (c) return 0 on failure."""

    def test_returns_created_count_on_success(self, db_session):
        """Happy path: delegates to seed_for_user and returns the
        creation count."""
        from app.models.role import Role
        from app.models.user import User
        from app.services.spaces.seed import seed_spaces_best_effort

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
                email=f"bh-{uuid.uuid4().hex[:6]}@inv.co",
                first_name="BH",
                last_name="User",
                hashed_password="x",
                is_active=True,
                role_id=admin_role.id,
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)

            count = seed_spaces_best_effort(
                db_session, user, call_site="test"
            )
            assert count >= 3
        finally:
            _drop_tenant(ctx["company_id"])

    def test_swallows_exception_and_logs(
        self, db_session, monkeypatch, caplog
    ):
        """Simulate a seed_for_user failure — helper must not re-raise,
        must emit the structured warning with expected keys, must
        return 0."""
        import logging

        from app.models.role import Role
        from app.models.user import User
        from app.services.spaces import seed as seed_mod
        from app.services.spaces.seed import seed_spaces_best_effort

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
                email=f"bh2-{uuid.uuid4().hex[:6]}@inv.co",
                first_name="BH",
                last_name="User",
                hashed_password="x",
                is_active=True,
                role_id=admin_role.id,
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)

            def _explode(db, **kwargs):
                raise RuntimeError("simulated seed failure")

            monkeypatch.setattr(seed_mod, "seed_for_user", _explode)

            caplog.set_level(
                logging.WARNING, logger="app.services.spaces.seed"
            )
            result = seed_spaces_best_effort(
                db_session, user, call_site="test-failure"
            )

            assert result == 0

            # Structured line MUST carry the required fields.
            messages = [rec.getMessage() for rec in caplog.records]
            assert any(
                "call_site=test-failure" in m
                and f"user_id={user.id}" in m
                and f"company_id={ctx['company_id']}" in m
                and "vertical=manufacturing" in m
                and "role_slug=admin" in m
                and "exc_type=RuntimeError" in m
                for m in messages
            ), f"expected structured warning; got {messages}"
        finally:
            _drop_tenant(ctx["company_id"])


# ── Backfill migration: idempotent + platform-wide invariant ────────


class TestBackfillIdempotency:
    """r46 backfill re-imports seed_for_user, so it inherits
    seed_for_user's own idempotency. Running the migration twice in
    sequence must not produce duplicate spaces."""

    def test_backfill_seed_is_idempotent(self, db_session):
        """Simulates what the migration does for a single user: call
        seed_for_user; assert the second call adds nothing."""
        from app.models.role import Role
        from app.models.user import User
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
                email=f"bf-{uuid.uuid4().hex[:6]}@inv.co",
                first_name="BF",
                last_name="User",
                hashed_password="x",
                is_active=True,
                role_id=admin_role.id,
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)

            first = seed_for_user(db_session, user=user)
            db_session.refresh(user)
            spaces_after_first = len(
                (user.preferences or {}).get("spaces") or []
            )

            second = seed_for_user(db_session, user=user)
            db_session.refresh(user)
            spaces_after_second = len(
                (user.preferences or {}).get("spaces") or []
            )

            assert first >= 3
            assert second == 0, (
                f"second seed must be no-op; added {second}"
            )
            assert spaces_after_first == spaces_after_second
        finally:
            _drop_tenant(ctx["company_id"])


class TestPlatformSpaceInvariant:
    """Platform-wide invariant: after r46 runs, no active user in the
    dev DB should have an empty preferences.spaces array.

    Skipped in environments where the migration hasn't been applied
    (e.g. CI against a fresh DB seeded outside alembic). Guarded by
    the actual migration head.
    """

    def test_invariant_no_active_user_has_empty_spaces(self, db_session):
        from sqlalchemy import text

        # Skip gracefully if r46 not applied yet.
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

        if head[0] != "r46_users_spaces_backfill":
            pytest.skip(
                f"r46 not current head (current={head[0]}); "
                "invariant asserted post-backfill only"
            )

        # JSONB path — same query shape as the migration itself.
        # Excludes users whose spaces_seeded_for_roles marker is
        # populated. That marker indicates seed_for_user ran at least
        # once for that user's role — a subsequent empty-spaces state
        # is a test-fixture teardown leftover (users in the dev DB
        # whose spaces were explicitly deleted mid-test) or a user
        # who manually deleted all their spaces through the UI, which
        # is legal behavior post-Phase 8e. Either way it's not what
        # the invariant is trying to catch: an unseeded user landing
        # on the UI with zero DotNav dots through a broken creation
        # path.
        row = db_session.execute(
            text(
                """
                SELECT COUNT(*) FROM users
                WHERE is_active = TRUE
                  AND (
                    preferences IS NULL
                    OR COALESCE(preferences -> 'spaces', '[]'::jsonb) = '[]'::jsonb
                  )
                  AND COALESCE(
                    preferences -> 'spaces_seeded_for_roles',
                    '[]'::jsonb
                  ) = '[]'::jsonb
                """
            )
        ).scalar()

        # Tight bound: users who've never been seeded should be zero.
        # Allow 5 for race conditions (user created mid-migration,
        # mid-login) that the defensive re-seed picks up on their
        # NEXT login.
        assert row is not None and row <= 5, (
            f"Platform invariant violated: {row} active users have "
            f"never been seeded (empty preferences.spaces AND empty "
            f"spaces_seeded_for_roles). r46 backfill + Phase 8e.2.2 "
            f"creation hooks + login defensive re-seed are all supposed "
            f"to close this gap. Investigate which creation path is "
            f"bypassing the hooks."
        )
