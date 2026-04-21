"""Phase 8e.2.1 — portal completion tests.

Covers the endpoints + service-layer additions that landed on top of
Phase 8e.2's reconnaissance:

  - Tenant-admin CRUD at /api/v1/portal/admin/*:
      list / invite / edit / deactivate / reactivate / unlock /
      reset-password / resend-invite.
  - Tenant-admin branding GET/PATCH + logo upload validation.
  - Auto-create Driver row when inviting into a driver-space.
  - Portal driver data mirror endpoints at /api/v1/portal/drivers/me/*:
      /route, /stops/{id}, /stops/{id}/exception,
      /stops/{id}/status, /mileage.
  - Legacy tenant-admin POST /delivery/drivers returns 404 (retired).

Fixtures piggyback on test_portal_phase8e2.py's patterns — same
`_make_tenant`, same `_make_portal_user` approach. Inlined here
rather than cross-imported to keep the two phases independently
deletable.
"""

from __future__ import annotations

import io
import uuid
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_rate_limit():
    from app.services.portal.auth import _clear_rate_limit_for_tests

    _clear_rate_limit_for_tests()
    yield
    _clear_rate_limit_for_tests()


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


def _make_tenant_with_admin_preferences_space(driver_space: bool = False):
    """Create a tenant + admin user. Optionally seeds a 'Driver'
    named space in the admin's preferences so invites into that
    space trigger auto-create Driver. Returns ctx dict."""
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User
    from sqlalchemy.orm.attributes import flag_modified

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"Portal8e21 {suffix}",
            slug=f"p821-{suffix}",
            is_active=True,
            vertical="manufacturing",
        )
        db.add(co)
        db.flush()
        admin_role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name="Admin",
            slug="admin",
            is_system=True,
        )
        db.add(admin_role)
        db.flush()
        admin = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"admin-{suffix}@p821.co",
            first_name="Admin",
            last_name="User",
            hashed_password="x",
            is_active=True,
            role_id=admin_role.id,
        )
        db.add(admin)
        db.flush()

        space_id = f"sp_drv_{suffix}"
        other_space_id = f"sp_oth_{suffix}"
        admin.preferences = {
            "spaces": [
                {
                    "space_id": space_id,
                    "name": "Driver" if driver_space else "Drive Board",
                    "icon": "truck",
                    "accent": "industrial",
                    "display_order": 0,
                    "is_default": True,
                    "density": "comfortable",
                    "pins": [],
                    "access_mode": "portal_partner",
                    "tenant_branding": True,
                    "write_mode": "limited",
                    "session_timeout_minutes": 12 * 60,
                },
                {
                    "space_id": other_space_id,
                    "name": "Dispatch",
                    "icon": "layers",
                    "accent": "neutral",
                    "display_order": 1,
                    "is_default": False,
                    "density": "comfortable",
                    "pins": [],
                    # No portal modifiers → platform default.
                },
            ],
        }
        flag_modified(admin, "preferences")
        db.commit()

        tenant_token = create_access_token(
            {"sub": admin.id, "company_id": co.id},
            realm="tenant",
        )
        return {
            "company_id": co.id,
            "slug": co.slug,
            "admin_id": admin.id,
            "tenant_token": tenant_token,
            "driver_space_id": space_id,
            "other_space_id": other_space_id,
        }
    finally:
        db.close()


def _portal_login(client: TestClient, slug: str, email: str, password: str) -> str:
    resp = client.post(
        f"/api/v1/portal/{slug}/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _admin_headers(ctx: dict) -> dict:
    return {
        "Authorization": f"Bearer {ctx['tenant_token']}",
        "X-Company-Slug": ctx["slug"],
    }


def _seed_portal_user_with_password(
    company_id: str,
    *,
    email: str,
    password: str = "goodpass123",
    assigned_space_id: str | None = None,
) -> str:
    from app.core.security import hash_password
    from app.database import SessionLocal
    from app.models.portal_user import PortalUser

    db = SessionLocal()
    try:
        pu = PortalUser(
            id=str(uuid.uuid4()),
            company_id=company_id,
            email=email,
            hashed_password=hash_password(password),
            first_name="First",
            last_name="Last",
            assigned_space_id=assigned_space_id,
            is_active=True,
        )
        db.add(pu)
        db.commit()
        return pu.id
    finally:
        db.close()


# ── Admin CRUD: list + invite ────────────────────────────────────────


class TestAdminListAndInvite:
    def test_list_empty_for_new_tenant(self, client):
        ctx = _make_tenant_with_admin_preferences_space()
        resp = client.get(
            "/api/v1/portal/admin/users", headers=_admin_headers(ctx)
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["users"] == []

    def test_invite_creates_pending_user(self, client, monkeypatch):
        # Don't actually send the invite email during tests.
        import app.api.routes.portal_admin as mod

        monkeypatch.setattr(mod, "_send_invite_email", lambda *a, **kw: None)

        ctx = _make_tenant_with_admin_preferences_space()
        resp = client.post(
            "/api/v1/portal/admin/users",
            headers=_admin_headers(ctx),
            json={
                "email": "newdriver@test.co",
                "first_name": "New",
                "last_name": "Driver",
                "assigned_space_id": ctx["driver_space_id"],
            },
        )
        assert resp.status_code == 201, resp.text
        user = resp.json()["user"]
        assert user["email"] == "newdriver@test.co"
        assert user["status"] == "pending"
        assert user["last_login_at"] is None

    def test_invite_duplicate_email_409(self, client, monkeypatch):
        import app.api.routes.portal_admin as mod

        monkeypatch.setattr(mod, "_send_invite_email", lambda *a, **kw: None)

        ctx = _make_tenant_with_admin_preferences_space()
        body = {
            "email": "dup@test.co",
            "first_name": "A",
            "last_name": "B",
            "assigned_space_id": ctx["driver_space_id"],
        }
        r1 = client.post(
            "/api/v1/portal/admin/users", headers=_admin_headers(ctx), json=body
        )
        assert r1.status_code == 201
        r2 = client.post(
            "/api/v1/portal/admin/users", headers=_admin_headers(ctx), json=body
        )
        assert r2.status_code == 409

    def test_list_filters_by_status(self, client, monkeypatch):
        import app.api.routes.portal_admin as mod

        monkeypatch.setattr(mod, "_send_invite_email", lambda *a, **kw: None)

        ctx = _make_tenant_with_admin_preferences_space()
        # One pending (via invite) + one active (direct DB insert with
        # hashed password).
        client.post(
            "/api/v1/portal/admin/users",
            headers=_admin_headers(ctx),
            json={
                "email": "pending@test.co",
                "first_name": "P",
                "last_name": "U",
                "assigned_space_id": ctx["driver_space_id"],
            },
        )
        _seed_portal_user_with_password(
            ctx["company_id"],
            email="active@test.co",
            assigned_space_id=ctx["driver_space_id"],
        )
        resp_pending = client.get(
            "/api/v1/portal/admin/users?status=pending",
            headers=_admin_headers(ctx),
        )
        resp_active = client.get(
            "/api/v1/portal/admin/users?status=active",
            headers=_admin_headers(ctx),
        )
        assert resp_pending.status_code == 200
        assert resp_active.status_code == 200
        pending_emails = {u["email"] for u in resp_pending.json()["users"]}
        active_emails = {u["email"] for u in resp_active.json()["users"]}
        assert pending_emails == {"pending@test.co"}
        assert active_emails == {"active@test.co"}

    def test_non_admin_rejected(self, client):
        """A tenant user without admin role → 403 on portal admin."""
        from app.core.security import create_access_token
        from app.database import SessionLocal
        from app.models.company import Company
        from app.models.role import Role
        from app.models.user import User

        ctx = _make_tenant_with_admin_preferences_space()
        # Add a non-admin user to the same tenant.
        db = SessionLocal()
        try:
            office_role = Role(
                id=str(uuid.uuid4()),
                company_id=ctx["company_id"],
                name="Office",
                slug="office",
                is_system=False,
            )
            db.add(office_role)
            db.flush()
            u = User(
                id=str(uuid.uuid4()),
                company_id=ctx["company_id"],
                email="office@p821.co",
                first_name="Off",
                last_name="Ice",
                hashed_password="x",
                is_active=True,
                role_id=office_role.id,
            )
            db.add(u)
            db.commit()
            token = create_access_token(
                {"sub": u.id, "company_id": ctx["company_id"]},
                realm="tenant",
            )
        finally:
            db.close()
        resp = client.get(
            "/api/v1/portal/admin/users",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Company-Slug": ctx["slug"],
            },
        )
        assert resp.status_code == 403


# ── Auto-create Driver on invite ────────────────────────────────────


class TestAutoCreateDriverOnInvite:
    def test_driver_row_created_for_driver_space(
        self, client, db_session, monkeypatch
    ):
        """Inviting a portal user into a space named 'Driver' should
        create a Driver row linked via portal_user_id."""
        import app.api.routes.portal_admin as mod
        from app.models.driver import Driver

        monkeypatch.setattr(mod, "_send_invite_email", lambda *a, **kw: None)

        ctx = _make_tenant_with_admin_preferences_space(driver_space=True)
        resp = client.post(
            "/api/v1/portal/admin/users",
            headers=_admin_headers(ctx),
            json={
                "email": "autodriver@test.co",
                "first_name": "Auto",
                "last_name": "Driver",
                "assigned_space_id": ctx["driver_space_id"],
            },
        )
        assert resp.status_code == 201
        pu_id = resp.json()["user"]["id"]
        driver = (
            db_session.query(Driver)
            .filter(Driver.portal_user_id == pu_id)
            .first()
        )
        assert driver is not None
        assert driver.employee_id is None
        assert driver.active is True

    def test_no_driver_for_non_driver_space(
        self, client, db_session, monkeypatch
    ):
        """A space NOT named 'Driver' must not trigger auto-create.
        Protects yard-operator / removal-staff / family / supplier
        portals from being accidentally treated as drivers."""
        import app.api.routes.portal_admin as mod
        from app.models.driver import Driver

        monkeypatch.setattr(mod, "_send_invite_email", lambda *a, **kw: None)

        # driver_space=False gives a space named "Drive Board" — close
        # but not an exact name match.
        ctx = _make_tenant_with_admin_preferences_space(driver_space=False)
        resp = client.post(
            "/api/v1/portal/admin/users",
            headers=_admin_headers(ctx),
            json={
                "email": "notdriver@test.co",
                "first_name": "Not",
                "last_name": "Driver",
                "assigned_space_id": ctx["driver_space_id"],
            },
        )
        assert resp.status_code == 201
        pu_id = resp.json()["user"]["id"]
        driver = (
            db_session.query(Driver)
            .filter(Driver.portal_user_id == pu_id)
            .first()
        )
        assert driver is None


# ── Admin edit / deactivate / reactivate / unlock ───────────────────


class TestAdminLifecycleActions:
    def test_edit_portal_user(self, client, monkeypatch):
        import app.api.routes.portal_admin as mod

        monkeypatch.setattr(mod, "_send_invite_email", lambda *a, **kw: None)
        ctx = _make_tenant_with_admin_preferences_space()
        pu_id = _seed_portal_user_with_password(
            ctx["company_id"], email="edit@test.co"
        )
        resp = client.patch(
            f"/api/v1/portal/admin/users/{pu_id}",
            headers=_admin_headers(ctx),
            json={"first_name": "Renamed"},
        )
        assert resp.status_code == 200
        assert resp.json()["first_name"] == "Renamed"

    def test_deactivate_then_reactivate(self, client, db_session):
        from app.models.portal_user import PortalUser

        ctx = _make_tenant_with_admin_preferences_space()
        pu_id = _seed_portal_user_with_password(
            ctx["company_id"], email="toggle@test.co"
        )
        r1 = client.post(
            f"/api/v1/portal/admin/users/{pu_id}/deactivate",
            headers=_admin_headers(ctx),
        )
        assert r1.status_code == 200
        assert r1.json()["status"] == "inactive"
        pu = db_session.query(PortalUser).filter(PortalUser.id == pu_id).first()
        assert pu.is_active is False
        r2 = client.post(
            f"/api/v1/portal/admin/users/{pu_id}/reactivate",
            headers=_admin_headers(ctx),
        )
        assert r2.status_code == 200
        assert r2.json()["status"] == "active"

    def test_unlock_clears_lockout(self, client, db_session):
        from datetime import timedelta
        from app.models.portal_user import PortalUser

        ctx = _make_tenant_with_admin_preferences_space()
        pu_id = _seed_portal_user_with_password(
            ctx["company_id"], email="lock@test.co"
        )
        pu = db_session.query(PortalUser).filter(PortalUser.id == pu_id).first()
        pu.locked_until = datetime.now(timezone.utc) + timedelta(hours=1)
        pu.failed_login_count = 5
        db_session.commit()

        resp = client.post(
            f"/api/v1/portal/admin/users/{pu_id}/unlock",
            headers=_admin_headers(ctx),
        )
        assert resp.status_code == 200
        db_session.refresh(pu)
        assert pu.locked_until is None
        assert pu.failed_login_count == 0

    def test_reset_password_issues_token(
        self, client, db_session, monkeypatch
    ):
        """Admin reset-password stamps a recovery_token on the user.
        Email send is stubbed; token presence on the row is the
        assertion."""
        import app.api.routes.portal_admin as mod
        from app.models.portal_user import PortalUser

        monkeypatch.setattr(mod, "_send_reset_email", lambda *a, **kw: None)
        ctx = _make_tenant_with_admin_preferences_space()
        pu_id = _seed_portal_user_with_password(
            ctx["company_id"], email="resetme@test.co"
        )
        resp = client.post(
            f"/api/v1/portal/admin/users/{pu_id}/reset-password",
            headers=_admin_headers(ctx),
        )
        assert resp.status_code == 204
        pu = db_session.query(PortalUser).filter(PortalUser.id == pu_id).first()
        assert pu.recovery_token is not None
        assert pu.recovery_token_expires_at is not None

    def test_resend_invite_pending_only(
        self, client, db_session, monkeypatch
    ):
        """resend_invite is valid only while hashed_password is None."""
        import app.api.routes.portal_admin as mod
        from app.models.portal_user import PortalUser
        from app.services.portal import invite_portal_user
        from app.database import SessionLocal

        monkeypatch.setattr(mod, "_send_invite_email", lambda *a, **kw: None)
        ctx = _make_tenant_with_admin_preferences_space()

        # Create a pending user via the service layer directly so we
        # can also resend a user that already has a password to prove
        # the 409.
        db2 = SessionLocal()
        try:
            from app.models.company import Company
            from app.models.user import User

            company = (
                db2.query(Company).filter(Company.id == ctx["company_id"]).one()
            )
            admin = db2.query(User).filter(User.id == ctx["admin_id"]).one()
            pending_user, _ = invite_portal_user(
                db2,
                company=company,
                inviter=admin,
                email="pending2@test.co",
                first_name="Pending",
                last_name="Two",
                assigned_space_id=ctx["driver_space_id"],
            )
            pending_id = pending_user.id
        finally:
            db2.close()

        r_ok = client.post(
            f"/api/v1/portal/admin/users/{pending_id}/resend-invite",
            headers=_admin_headers(ctx),
        )
        assert r_ok.status_code == 204

        # Now try resend on an already-active user → 409.
        active_id = _seed_portal_user_with_password(
            ctx["company_id"], email="active2@test.co"
        )
        r_fail = client.post(
            f"/api/v1/portal/admin/users/{active_id}/resend-invite",
            headers=_admin_headers(ctx),
        )
        assert r_fail.status_code == 409


# ── Branding admin GET / PATCH ──────────────────────────────────────


class TestBrandingAdmin:
    def test_read_branding(self, client):
        ctx = _make_tenant_with_admin_preferences_space()
        resp = client.get(
            "/api/v1/portal/admin/branding", headers=_admin_headers(ctx)
        )
        assert resp.status_code == 200, resp.json()
        body = resp.json()
        assert body["slug"] == ctx["slug"]
        assert body["brand_color"].startswith("#")

    def test_update_branding(self, client):
        ctx = _make_tenant_with_admin_preferences_space()
        resp = client.patch(
            "/api/v1/portal/admin/branding",
            headers=_admin_headers(ctx),
            json={"brand_color": "#1E40AF", "footer_text": "Test footer"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["brand_color"] == "#1E40AF"
        assert body["footer_text"] == "Test footer"

    def test_update_branding_invalid_hex_422(self, client):
        ctx = _make_tenant_with_admin_preferences_space()
        resp = client.patch(
            "/api/v1/portal/admin/branding",
            headers=_admin_headers(ctx),
            json={"brand_color": "red"},
        )
        assert resp.status_code == 422


# ── Branding logo upload validation ─────────────────────────────────


def _png_bytes(width: int = 200, height: int = 200) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buf, format="PNG")
    return buf.getvalue()


def _jpg_bytes(width: int = 200, height: int = 200) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buf, format="JPEG")
    return buf.getvalue()


class TestLogoUpload:
    def test_rejects_svg_content_type(self, client):
        ctx = _make_tenant_with_admin_preferences_space()
        resp = client.post(
            "/api/v1/portal/admin/branding/logo",
            headers=_admin_headers(ctx),
            files={
                "file": ("logo.svg", b"<svg/>", "image/svg+xml"),
            },
        )
        assert resp.status_code == 400
        assert "SVG" in resp.json()["detail"]

    def test_rejects_empty_file(self, client):
        ctx = _make_tenant_with_admin_preferences_space()
        resp = client.post(
            "/api/v1/portal/admin/branding/logo",
            headers=_admin_headers(ctx),
            files={"file": ("blank.png", b"", "image/png")},
        )
        assert resp.status_code == 400

    def test_rejects_too_small(self, client):
        ctx = _make_tenant_with_admin_preferences_space()
        data = _png_bytes(width=10, height=10)
        resp = client.post(
            "/api/v1/portal/admin/branding/logo",
            headers=_admin_headers(ctx),
            files={"file": ("tiny.png", data, "image/png")},
        )
        assert resp.status_code == 400
        assert "too small" in resp.json()["detail"].lower()

    def test_rejects_too_large_dimensions(self, client):
        ctx = _make_tenant_with_admin_preferences_space()
        data = _png_bytes(width=2000, height=2000)
        resp = client.post(
            "/api/v1/portal/admin/branding/logo",
            headers=_admin_headers(ctx),
            files={"file": ("huge.png", data, "image/png")},
        )
        assert resp.status_code == 400
        assert "too large" in resp.json()["detail"].lower()

    def test_rejects_corrupt_image(self, client):
        """Bytes with PNG content-type but not a real PNG payload →
        Pillow decode fails → 400."""
        ctx = _make_tenant_with_admin_preferences_space()
        resp = client.post(
            "/api/v1/portal/admin/branding/logo",
            headers=_admin_headers(ctx),
            files={
                "file": ("notreal.png", b"definitely not a png", "image/png")
            },
        )
        assert resp.status_code == 400

    def test_accepts_jpg_passes_validation(self, client, monkeypatch):
        """JPG at 200×200 passes validation. R2 upload is monkey-
        patched — we test the validation path + response shape, not
        the actual R2 integration."""
        import app.api.routes.portal_admin as mod

        def _fake_upload(data, key, content_type):
            return f"https://cdn.test/{key}"

        monkeypatch.setattr(mod, "upload_bytes", _fake_upload, raising=False)
        # Also patch the inner import site via direct module lookup.
        import app.services.legacy_r2_client as r2

        monkeypatch.setattr(r2, "upload_bytes", _fake_upload)
        monkeypatch.setattr(
            r2, "get_public_url", lambda k: f"https://cdn.test/{k}"
        )

        ctx = _make_tenant_with_admin_preferences_space()
        data = _jpg_bytes()
        resp = client.post(
            "/api/v1/portal/admin/branding/logo",
            headers=_admin_headers(ctx),
            files={"file": ("logo.jpg", data, "image/jpeg")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["logo_url"].endswith("logo.jpg")


# ── Legacy tenant-admin POST /delivery/drivers retired ──────────────


class TestLegacyCreateDriverRetired:
    def test_post_delivery_drivers_retired(self, client):
        """Phase 8e.2.1 removed the tenant-admin POST /delivery/drivers
        route. The portal invite flow is the only path for creating a
        driver going forward.

        Expect either 404 (no route at all) or 405 (GET /drivers
        exists but POST is not registered). Either answer enforces
        the same contract: POST is not accepted."""
        ctx = _make_tenant_with_admin_preferences_space()
        resp = client.post(
            "/api/v1/delivery/drivers",
            headers=_admin_headers(ctx),
            json={"employee_id": "whatever", "active": True},
        )
        assert resp.status_code in (404, 405)


# ── Portal driver data mirror endpoints ─────────────────────────────


def _seed_linked_portal_driver(ctx: dict) -> dict:
    """Create an active portal user + Driver row linked via
    portal_user_id. Returns {pu_id, driver_id, email, password}."""
    from app.database import SessionLocal
    from app.models.driver import Driver

    email = f"drv-{uuid.uuid4().hex[:6]}@test.co"
    password = "drvpass123"
    pu_id = _seed_portal_user_with_password(
        ctx["company_id"], email=email, password=password
    )
    db = SessionLocal()
    try:
        driver = Driver(
            id=str(uuid.uuid4()),
            company_id=ctx["company_id"],
            employee_id=None,
            portal_user_id=pu_id,
            license_number="TEST-001",
            active=True,
        )
        db.add(driver)
        db.commit()
        driver_id = driver.id
    finally:
        db.close()
    return {"pu_id": pu_id, "driver_id": driver_id, "email": email, "password": password}


class TestPortalDriverDataMirror:
    def test_today_route_no_route_returns_shell(self, client):
        """Portal driver with no scheduled route → 200 with empty
        shell (not 404) so the mobile UI can render 'no route today'."""
        ctx = _make_tenant_with_admin_preferences_space()
        seed = _seed_linked_portal_driver(ctx)
        token = _portal_login(client, ctx["slug"], seed["email"], seed["password"])
        resp = client.get(
            "/api/v1/portal/drivers/me/route",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_stops"] == 0
        assert body["driver_id"] == seed["driver_id"]

    def test_today_route_with_route_returns_route(self, client, db_session):
        from app.models.delivery_route import DeliveryRoute

        ctx = _make_tenant_with_admin_preferences_space()
        seed = _seed_linked_portal_driver(ctx)
        route = DeliveryRoute(
            id=str(uuid.uuid4()),
            company_id=ctx["company_id"],
            driver_id=seed["driver_id"],
            route_date=date.today(),
            status="dispatched",
            total_stops=3,
        )
        db_session.add(route)
        db_session.commit()

        token = _portal_login(client, ctx["slug"], seed["email"], seed["password"])
        resp = client.get(
            "/api/v1/portal/drivers/me/route",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == route.id
        assert body["total_stops"] == 3

    def test_route_404_for_unlinked_portal_user(self, client):
        """Portal user without a linked Driver → 404 on /route."""
        ctx = _make_tenant_with_admin_preferences_space()
        # Seed a portal user with NO linked driver.
        email = "nolink@test.co"
        _seed_portal_user_with_password(ctx["company_id"], email=email)
        token = _portal_login(client, ctx["slug"], email, "goodpass123")
        resp = client.get(
            "/api/v1/portal/drivers/me/route",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_stop_detail_cross_driver_404(self, client, db_session):
        """Driver A cannot read Driver B's stop — 404 on cross-driver
        access enforces route-scoped isolation."""
        from app.models.delivery_route import DeliveryRoute
        from app.models.delivery_stop import DeliveryStop
        from app.models.delivery import Delivery
        from app.models.driver import Driver

        ctx = _make_tenant_with_admin_preferences_space()

        # Driver A — the portal-authed user.
        seed_a = _seed_linked_portal_driver(ctx)
        # Driver B — belongs to same tenant but unrelated.
        drv_b = Driver(
            id=str(uuid.uuid4()),
            company_id=ctx["company_id"],
            employee_id=None,
            portal_user_id=None,
            active=True,
        )
        db_session.add(drv_b)
        db_session.flush()

        # Create a route + stop for Driver B.
        route_b = DeliveryRoute(
            id=str(uuid.uuid4()),
            company_id=ctx["company_id"],
            driver_id=drv_b.id,
            route_date=date.today(),
            status="dispatched",
            total_stops=1,
        )
        db_session.add(route_b)
        db_session.flush()
        # Need a delivery row to satisfy FK.
        delivery_b = Delivery(
            id=str(uuid.uuid4()),
            company_id=ctx["company_id"],
            delivery_type="standard",
            status="scheduled",
        )
        db_session.add(delivery_b)
        db_session.flush()
        stop_b = DeliveryStop(
            id=str(uuid.uuid4()),
            route_id=route_b.id,
            delivery_id=delivery_b.id,
            sequence_number=1,
            status="pending",
        )
        db_session.add(stop_b)
        db_session.commit()

        token = _portal_login(
            client, ctx["slug"], seed_a["email"], seed_a["password"]
        )
        resp = client.get(
            f"/api/v1/portal/drivers/me/stops/{stop_b.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_update_stop_status_writes(self, client, db_session):
        """PATCH /stops/{id}/status updates the stop's status field."""
        from app.models.delivery import Delivery
        from app.models.delivery_route import DeliveryRoute
        from app.models.delivery_stop import DeliveryStop

        ctx = _make_tenant_with_admin_preferences_space()
        seed = _seed_linked_portal_driver(ctx)
        route = DeliveryRoute(
            id=str(uuid.uuid4()),
            company_id=ctx["company_id"],
            driver_id=seed["driver_id"],
            route_date=date.today(),
            status="dispatched",
            total_stops=1,
        )
        delivery = Delivery(
            id=str(uuid.uuid4()),
            company_id=ctx["company_id"],
            delivery_type="standard",
            status="scheduled",
        )
        db_session.add_all([route, delivery])
        db_session.flush()
        stop = DeliveryStop(
            id=str(uuid.uuid4()),
            route_id=route.id,
            delivery_id=delivery.id,
            sequence_number=1,
            status="pending",
        )
        db_session.add(stop)
        db_session.commit()

        token = _portal_login(
            client, ctx["slug"], seed["email"], seed["password"]
        )
        resp = client.patch(
            f"/api/v1/portal/drivers/me/stops/{stop.id}/status",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "delivered"},
        )
        assert resp.status_code == 200
        db_session.refresh(stop)
        assert stop.status == "delivered"

    def test_mark_stop_exception(self, client, db_session):
        from app.models.delivery import Delivery
        from app.models.delivery_route import DeliveryRoute
        from app.models.delivery_stop import DeliveryStop

        ctx = _make_tenant_with_admin_preferences_space()
        seed = _seed_linked_portal_driver(ctx)
        route = DeliveryRoute(
            id=str(uuid.uuid4()),
            company_id=ctx["company_id"],
            driver_id=seed["driver_id"],
            route_date=date.today(),
            status="dispatched",
            total_stops=1,
        )
        delivery = Delivery(
            id=str(uuid.uuid4()),
            company_id=ctx["company_id"],
            delivery_type="standard",
            status="scheduled",
        )
        db_session.add_all([route, delivery])
        db_session.flush()
        stop = DeliveryStop(
            id=str(uuid.uuid4()),
            route_id=route.id,
            delivery_id=delivery.id,
            sequence_number=1,
            status="pending",
        )
        db_session.add(stop)
        db_session.commit()

        token = _portal_login(
            client, ctx["slug"], seed["email"], seed["password"]
        )
        resp = client.post(
            f"/api/v1/portal/drivers/me/stops/{stop.id}/exception",
            headers={"Authorization": f"Bearer {token}"},
            json={"reason_code": "access_blocked", "note": "Gate locked"},
        )
        assert resp.status_code == 204
        db_session.refresh(stop)
        assert stop.status == "exception"

    def test_mileage_submit_happy_path(self, client, db_session):
        from app.models.delivery_route import DeliveryRoute

        ctx = _make_tenant_with_admin_preferences_space()
        seed = _seed_linked_portal_driver(ctx)
        route = DeliveryRoute(
            id=str(uuid.uuid4()),
            company_id=ctx["company_id"],
            driver_id=seed["driver_id"],
            route_date=date.today(),
            status="dispatched",
            total_stops=0,
        )
        db_session.add(route)
        db_session.commit()

        token = _portal_login(
            client, ctx["slug"], seed["email"], seed["password"]
        )
        resp = client.post(
            "/api/v1/portal/drivers/me/mileage",
            headers={"Authorization": f"Bearer {token}"},
            json={"start_mileage": 100000, "end_mileage": 100087, "notes": "Route done"},
        )
        assert resp.status_code == 204
        db_session.refresh(route)
        assert float(route.total_mileage) == 87.0

    def test_mileage_submit_rejects_end_below_start(self, client, db_session):
        from app.models.delivery_route import DeliveryRoute

        ctx = _make_tenant_with_admin_preferences_space()
        seed = _seed_linked_portal_driver(ctx)
        route = DeliveryRoute(
            id=str(uuid.uuid4()),
            company_id=ctx["company_id"],
            driver_id=seed["driver_id"],
            route_date=date.today(),
            status="dispatched",
            total_stops=0,
        )
        db_session.add(route)
        db_session.commit()

        token = _portal_login(
            client, ctx["slug"], seed["email"], seed["password"]
        )
        resp = client.post(
            "/api/v1/portal/drivers/me/mileage",
            headers={"Authorization": f"Bearer {token}"},
            json={"start_mileage": 100050, "end_mileage": 100000},
        )
        assert resp.status_code == 400


# ── Cross-realm isolation holds on the new admin routes ─────────────


class TestAdminRoutesCrossRealm:
    def test_portal_token_rejected_on_admin_list(self, client):
        """Portal token must NOT grant access to tenant-admin portal
        admin routes. Protects against an attacker using a portal
        driver token to enumerate other portal users."""
        ctx = _make_tenant_with_admin_preferences_space()
        # Seed a portal user + log in via portal.
        email = "rogue@test.co"
        _seed_portal_user_with_password(ctx["company_id"], email=email)
        portal_token = _portal_login(
            client, ctx["slug"], email, "goodpass123"
        )
        resp = client.get(
            "/api/v1/portal/admin/users",
            headers={
                "Authorization": f"Bearer {portal_token}",
                "X-Company-Slug": ctx["slug"],
            },
        )
        # Tenant auth rejects portal-realm tokens with 401.
        assert resp.status_code == 401
