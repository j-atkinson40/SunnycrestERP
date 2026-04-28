"""Phase W-4a Commit 1 — schema + Home system space + operator onboarding.

Verifies:
  • Migration r61 schema landed (work_areas, responsibilities_description,
    pulse_signals)
  • PulseSignal model writes/reads correctly
  • Home system space template registered + seeded for users
  • Login defensive re-seed gate widened to detect missing system
    templates (so existing users get Home on next login without a
    backfill migration)
  • Operator profile service: validation, partial-update semantics,
    onboarding-touches flag
  • Operator profile API: GET + PATCH + canonical work-area vocab
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


@pytest.fixture
def db_session() -> Iterator:
    from app.database import SessionLocal

    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def _make_tenant_user_token(
    *,
    vertical: str = "manufacturing",
    permissions: list[str] | None = None,
) -> dict:
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.role_permission import RolePermission
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"W4a-{suffix}",
            slug=f"w4a-{suffix}",
            is_active=True,
            vertical=vertical,
            timezone="America/New_York",
        )
        db.add(co)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name="Test",
            slug="test",
            is_system=False,
        )
        db.add(role)
        db.flush()
        for p in permissions or []:
            db.add(RolePermission(role_id=role.id, permission_key=p))
        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"u-{suffix}@w4a.test",
            first_name="W4a",
            last_name="Test",
            hashed_password="x",
            is_active=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        token = create_access_token(
            {"sub": user.id, "company_id": co.id, "realm": "tenant"}
        )
        return {
            "company_id": co.id,
            "slug": co.slug,
            "user_id": user.id,
            "token": token,
        }
    finally:
        db.close()


def _auth_headers(ctx: dict) -> dict:
    return {
        "Authorization": f"Bearer {ctx['token']}",
        "X-Company-Slug": ctx["slug"],
    }


# ── Schema ──────────────────────────────────────────────────────────


class TestSchema:
    def test_user_has_work_areas_and_responsibilities_columns(
        self, db_session
    ):
        from app.models.user import User

        # ORM-level: columns are defined on the model
        assert hasattr(User, "work_areas")
        assert hasattr(User, "responsibilities_description")

    def test_pulse_signals_table_exists(self, db_session):
        from sqlalchemy import inspect

        i = inspect(db_session.get_bind())
        cols = {c["name"] for c in i.get_columns("pulse_signals")}
        # Per migration r61 schema
        assert {
            "id",
            "user_id",
            "company_id",
            "signal_type",
            "layer",
            "component_key",
            "timestamp",
            "metadata",
        }.issubset(cols)

    def test_pulse_signals_has_user_timestamp_index(self, db_session):
        from sqlalchemy import inspect

        i = inspect(db_session.get_bind())
        idx_names = {ix["name"] for ix in i.get_indexes("pulse_signals")}
        assert "ix_pulse_signals_user_timestamp" in idx_names
        assert "ix_pulse_signals_company_timestamp" in idx_names


class TestPulseSignalModel:
    def test_round_trip(self, db_session):
        from app.models.pulse_signal import PulseSignal

        ctx = _make_tenant_user_token()
        sig = PulseSignal(
            id=str(uuid.uuid4()),
            user_id=ctx["user_id"],
            company_id=ctx["company_id"],
            signal_type="dismiss",
            layer="anomaly",
            component_key="anomalies",
            timestamp=datetime.now(timezone.utc),
            signal_metadata={
                "component_key": "anomalies",
                "time_of_day": "morning",
                "work_areas_at_dismiss": ["Production Scheduling"],
            },
        )
        db_session.add(sig)
        db_session.commit()
        # Re-read from DB
        row = db_session.query(PulseSignal).filter_by(id=sig.id).one()
        assert row.signal_type == "dismiss"
        assert row.layer == "anomaly"
        assert row.signal_metadata["time_of_day"] == "morning"


# ── Home system space ───────────────────────────────────────────────


class TestHomeSystemSpace:
    def test_home_template_registered(self):
        from app.services.spaces.registry import SYSTEM_SPACE_TEMPLATES

        ids = {t.template_id for t in SYSTEM_SPACE_TEMPLATES}
        assert "home" in ids, (
            "Home system space template missing — Phase W-4a §3.26.1.1 "
            "requires Home as always-first system space"
        )

    def test_home_template_has_no_required_permission(self):
        """Home is for ALL users (unlike Settings which is admin-gated)."""
        from app.services.spaces.registry import SYSTEM_SPACE_TEMPLATES

        home = next(
            t for t in SYSTEM_SPACE_TEMPLATES if t.template_id == "home"
        )
        assert home.required_permission is None

    def test_home_template_routes_to_pulse_surface(self):
        from app.services.spaces.registry import SYSTEM_SPACE_TEMPLATES

        home = next(
            t for t in SYSTEM_SPACE_TEMPLATES if t.template_id == "home"
        )
        assert home.default_home_route == "/home"

    def test_home_template_displays_leftmost_of_system_spaces(self):
        """Home display_order < Settings display_order so Home is leftmost."""
        from app.services.spaces.registry import SYSTEM_SPACE_TEMPLATES

        home = next(
            t for t in SYSTEM_SPACE_TEMPLATES if t.template_id == "home"
        )
        settings = next(
            t for t in SYSTEM_SPACE_TEMPLATES if t.template_id == "settings"
        )
        assert home.display_order < settings.display_order

    def test_home_seeded_for_new_user(self, db_session):
        """seed_for_user with new user yields Home in their spaces array."""
        from app.models.user import User
        from app.services.spaces.seed import seed_for_user

        ctx = _make_tenant_user_token(vertical="manufacturing")
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        seed_for_user(db_session, user=user)
        prefs = user.preferences or {}
        spaces = prefs.get("spaces", [])
        space_names = {s.get("name", "").lower() for s in spaces}
        assert "home" in space_names, (
            f"Home space not seeded for new user; got names={space_names}"
        )

    def test_home_seeded_for_non_admin_user(self, db_session):
        """Non-admin users still get Home (Settings would be hidden)."""
        from app.models.user import User
        from app.services.spaces.seed import seed_for_user

        ctx = _make_tenant_user_token(
            vertical="funeral_home", permissions=[]
        )
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        seed_for_user(db_session, user=user)
        prefs = user.preferences or {}
        spaces = prefs.get("spaces", [])
        space_names = {s.get("name", "").lower() for s in spaces}
        assert "home" in space_names
        # Non-admin should NOT have Settings
        assert "settings" not in space_names


class TestLoginDefensiveReseedWidening:
    """Phase W-4a widens the auth_service login re-seed gate to detect
    missing system templates so existing users get Home on next login
    without requiring a backfill migration. The gate now checks: empty
    spaces OR empty roles-tracker OR missing system templates."""

    def test_user_with_full_seed_but_missing_home_gets_reseeded(
        self, db_session
    ):
        """Simulate an existing user (pre-W-4a): spaces array populated,
        spaces_seeded_for_roles populated, system_spaces_seeded
        contains only "settings" (no "home"). On next login the
        defensive re-seed runs and adds Home."""
        from app.models.user import User
        from app.services.spaces.seed import seed_spaces_best_effort

        ctx = _make_tenant_user_token(vertical="manufacturing")
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        # Simulate pre-W-4a state: spaces populated, roles tracker
        # populated, system_spaces_seeded missing "home"
        user.preferences = {
            "spaces": [
                {
                    "space_id": "user_existing",
                    "name": "Pre-existing",
                    "icon": "home",
                    "accent": "warm",
                    "display_order": 0,
                    "is_default": True,
                    "is_system": False,
                    "pins": [],
                    "density": "comfortable",
                    "default_home_route": None,
                    "access_mode": "platform",
                    "tenant_branding": False,
                    "write_mode": "full",
                    "session_timeout_minutes": None,
                    "created_at": "2026-04-27T00:00:00Z",
                    "updated_at": "2026-04-27T00:00:00Z",
                }
            ],
            "spaces_seeded_for_roles": ["test"],
            "system_spaces_seeded": [],  # no home, no settings
        }
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(user, "preferences")
        db_session.commit()

        # Run the seed-best-effort path (what login does defensively).
        seed_spaces_best_effort(db_session, user, call_site="test")
        db_session.refresh(user)
        prefs = user.preferences or {}
        seeded = set(prefs.get("system_spaces_seeded", []))
        assert "home" in seeded, (
            f"Home should be added on login re-seed; got seeded={seeded}"
        )
        space_names = {
            s.get("name", "").lower() for s in prefs.get("spaces", [])
        }
        assert "home" in space_names

    def test_login_endpoint_widens_gate(self, client):
        """End-to-end: simulate a user without Home in their seeded
        templates. Hit the login endpoint. Verify Home appears in
        their spaces post-login."""
        from app.core.security import hash_password
        from app.database import SessionLocal
        from app.models.company import Company
        from app.models.role import Role
        from app.models.user import User

        db = SessionLocal()
        try:
            suffix = uuid.uuid4().hex[:6]
            co = Company(
                id=str(uuid.uuid4()),
                name=f"W4aLogin-{suffix}",
                slug=f"w4al-{suffix}",
                is_active=True,
                vertical="manufacturing",
                timezone="America/New_York",
            )
            db.add(co)
            db.flush()
            role = Role(
                id=str(uuid.uuid4()),
                company_id=co.id,
                name="Test",
                slug="test",
                is_system=False,
            )
            db.add(role)
            db.flush()
            password = "ProsperousMantle9$"
            user = User(
                id=str(uuid.uuid4()),
                company_id=co.id,
                email=f"u-{suffix}@example.com",
                first_name="W4a",
                last_name="Test",
                hashed_password=hash_password(password),
                is_active=True,
                role_id=role.id,
                # Pre-W-4a state: populated spaces but no system templates
                preferences={
                    "spaces": [
                        {
                            "space_id": "user_existing",
                            "name": "Pre-existing",
                            "icon": "home",
                            "accent": "warm",
                            "display_order": 0,
                            "is_default": True,
                            "is_system": False,
                            "pins": [],
                            "density": "comfortable",
                            "default_home_route": None,
                            "access_mode": "platform",
                            "tenant_branding": False,
                            "write_mode": "full",
                            "session_timeout_minutes": None,
                            "created_at": "2026-04-27T00:00:00Z",
                            "updated_at": "2026-04-27T00:00:00Z",
                        }
                    ],
                    "spaces_seeded_for_roles": ["test"],
                    "system_spaces_seeded": [],
                },
            )
            db.add(user)
            db.commit()
            user_id = user.id
            slug = co.slug
        finally:
            db.close()

        r = client.post(
            "/api/v1/auth/login",
            json={"email": f"u-{suffix}@example.com", "password": password},
            headers={"X-Company-Slug": slug},
        )
        assert r.status_code == 200, r.text

        # Verify Home was added during login defensive re-seed
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).one()
            prefs = user.preferences or {}
            seeded = set(prefs.get("system_spaces_seeded", []))
            assert "home" in seeded
            names = {
                s.get("name", "").lower() for s in prefs.get("spaces", [])
            }
            assert "home" in names
        finally:
            db.close()


# ── Operator profile service ────────────────────────────────────────


class TestOperatorProfileService:
    def test_get_returns_canonical_defaults_for_unset_user(
        self, db_session
    ):
        from app.models.user import User
        from app.services.operator_profile_service import (
            get_operator_profile,
            WORK_AREAS,
        )

        ctx = _make_tenant_user_token()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        prof = get_operator_profile(user)
        assert prof["work_areas"] == []
        assert prof["responsibilities_description"] is None
        assert prof["onboarding_completed"] is False
        # Available work areas surfaced for the frontend multi-select
        assert prof["available_work_areas"] == list(WORK_AREAS)

    def test_set_work_areas_validated_and_sorted(self, db_session):
        from app.models.user import User
        from app.services.operator_profile_service import (
            update_operator_profile,
        )

        ctx = _make_tenant_user_token()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        out = update_operator_profile(
            db_session,
            user=user,
            work_areas=[
                "Inventory Management",
                "Production Scheduling",
                "Production Scheduling",  # de-dupe
            ],
        )
        # De-duped + sorted alphabetically
        assert out["work_areas"] == [
            "Inventory Management",
            "Production Scheduling",
        ]
        # onboarding_completed flips to True because work_areas is set
        assert out["onboarding_completed"] is True

    def test_unknown_work_area_rejected(self, db_session):
        from app.models.user import User
        from app.services.operator_profile_service import (
            OperatorProfileError,
            update_operator_profile,
        )

        ctx = _make_tenant_user_token()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        with pytest.raises(OperatorProfileError):
            update_operator_profile(
                db_session, user=user, work_areas=["Bogus Area"]
            )

    def test_responsibilities_max_length_enforced(self, db_session):
        from app.models.user import User
        from app.services.operator_profile_service import (
            OperatorProfileError,
            update_operator_profile,
            RESPONSIBILITIES_MAX_LENGTH,
        )

        ctx = _make_tenant_user_token()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        with pytest.raises(OperatorProfileError):
            update_operator_profile(
                db_session,
                user=user,
                responsibilities_description="x" * (RESPONSIBILITIES_MAX_LENGTH + 1),
            )

    def test_empty_responsibilities_normalizes_to_null(self, db_session):
        from app.models.user import User
        from app.services.operator_profile_service import (
            update_operator_profile,
        )

        ctx = _make_tenant_user_token()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        # Set a value first
        update_operator_profile(
            db_session,
            user=user,
            responsibilities_description="initial value",
        )
        # Then "clear" via empty string
        out = update_operator_profile(
            db_session, user=user, responsibilities_description="   "
        )
        assert out["responsibilities_description"] is None

    def test_mark_onboarding_complete_sets_touch_flag(self, db_session):
        from app.models.user import User
        from app.services.operator_profile_service import (
            update_operator_profile,
        )

        ctx = _make_tenant_user_token()
        user = (
            db_session.query(User).filter(User.id == ctx["user_id"]).one()
        )
        update_operator_profile(
            db_session,
            user=user,
            mark_onboarding_complete=True,
        )
        prefs = user.preferences or {}
        touches = prefs.get("onboarding_touches", {})
        assert touches.get("operator_profile") is True


# ── Operator profile API ────────────────────────────────────────────


class TestOperatorProfileAPI:
    def test_get_returns_default_state_for_new_user(self, client):
        ctx = _make_tenant_user_token()
        r = client.get(
            "/api/v1/operator-profile", headers=_auth_headers(ctx)
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["work_areas"] == []
        assert body["responsibilities_description"] is None
        assert body["onboarding_completed"] is False
        assert "Production Scheduling" in body["available_work_areas"]

    def test_patch_partial_update_work_areas(self, client):
        ctx = _make_tenant_user_token()
        r = client.patch(
            "/api/v1/operator-profile",
            headers=_auth_headers(ctx),
            json={"work_areas": ["Production Scheduling"]},
        )
        assert r.status_code == 200, r.text
        assert r.json()["work_areas"] == ["Production Scheduling"]

    def test_patch_partial_update_responsibilities_only(self, client):
        ctx = _make_tenant_user_token()
        # First set work_areas
        client.patch(
            "/api/v1/operator-profile",
            headers=_auth_headers(ctx),
            json={"work_areas": ["Inventory Management"]},
        )
        # Then patch only responsibilities — work_areas should remain
        r = client.patch(
            "/api/v1/operator-profile",
            headers=_auth_headers(ctx),
            json={"responsibilities_description": "I track stock levels."},
        )
        body = r.json()
        assert body["work_areas"] == ["Inventory Management"]
        assert body["responsibilities_description"] == "I track stock levels."

    def test_patch_clear_work_areas_via_empty_list(self, client):
        ctx = _make_tenant_user_token()
        client.patch(
            "/api/v1/operator-profile",
            headers=_auth_headers(ctx),
            json={"work_areas": ["Inventory Management"]},
        )
        r = client.patch(
            "/api/v1/operator-profile",
            headers=_auth_headers(ctx),
            json={"work_areas": []},
        )
        body = r.json()
        assert body["work_areas"] == []

    def test_patch_invalid_work_area_returns_400(self, client):
        ctx = _make_tenant_user_token()
        r = client.patch(
            "/api/v1/operator-profile",
            headers=_auth_headers(ctx),
            json={"work_areas": ["Bogus"]},
        )
        assert r.status_code == 400

    def test_patch_mark_onboarding_complete(self, client):
        ctx = _make_tenant_user_token()
        r = client.patch(
            "/api/v1/operator-profile",
            headers=_auth_headers(ctx),
            json={"mark_onboarding_complete": True},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["onboarding_completed"] is True

    def test_get_requires_auth(self, client):
        r = client.get("/api/v1/operator-profile")
        assert r.status_code in (401, 403)
