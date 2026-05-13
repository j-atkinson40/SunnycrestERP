"""Verticals-lite precursor arc — tests for the `verticals` table.

Covers:
  - Migration: head advances to r95_verticals_table; table exists;
    4 seed rows correct; status CHECK enforces canonical 3-value
    enum. (Spec named r92; per CLAUDE.md §12 Spec-Override the
    revision id moved to r95 because r92-r94 already existed.)
  - Service: list ordering, archived exclusion + inclusion, get
    happy + miss, update partial + invalid status + immutable
    slug + bumps updated_at.
  - API: list auth + 200; get 200 + 404; patch 200 + 400 invalid
    status + 404 unknown slug + 422 on slug-in-body
    (Pydantic extra='forbid').
"""

from __future__ import annotations

import time
import uuid

import pytest
from fastapi.testclient import TestClient


# ─── Fixtures ──────────────────────────────────────────────────


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


def _make_platform_admin() -> dict:
    """Create a PlatformUser; return ctx dict with platform token."""
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.platform_user import PlatformUser

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        platform_admin = PlatformUser(
            id=str(uuid.uuid4()),
            email=f"platform-{suffix}@verticals.test",
            hashed_password="x",
            first_name="Platform",
            last_name="Admin",
            role="super_admin",
            is_active=True,
        )
        db.add(platform_admin)
        db.commit()
        platform_token = create_access_token(
            {"sub": platform_admin.id},
            realm="platform",
        )
        return {
            "platform_id": platform_admin.id,
            "platform_token": platform_token,
        }
    finally:
        db.close()


def _admin_headers(ctx: dict) -> dict:
    return {"Authorization": f"Bearer {ctx['platform_token']}"}


def _reset_verticals_to_canonical_seeds() -> None:
    """Restore the 4 canonical seeds to their starting state.

    Tests in this file mutate verticals (status, sort_order, etc).
    Reset between tests so each starts from a known baseline. Does
    NOT delete rows — only restores canonical column values.
    """
    from app.database import SessionLocal
    from app.models.vertical import Vertical

    canonical = {
        "manufacturing": ("Manufacturing", "published", 10),
        "funeral_home": ("Funeral Home", "published", 20),
        "cemetery": ("Cemetery", "published", 30),
        "crematory": ("Crematory", "published", 40),
    }

    db = SessionLocal()
    try:
        for slug, (display_name, status, sort_order) in canonical.items():
            row = db.query(Vertical).filter(Vertical.slug == slug).first()
            if row is not None:
                row.display_name = display_name
                row.description = None
                row.status = status
                row.icon = None
                row.sort_order = sort_order
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _reset_seeds_each_test():
    _reset_verticals_to_canonical_seeds()
    yield
    _reset_verticals_to_canonical_seeds()


# ─── Migration / schema tests ──────────────────────────────────


class TestMigration:
    def test_alembic_head_is_r95(self):
        """Alembic chain advances to r95_verticals_table."""
        import os
        from pathlib import Path

        from alembic.config import Config
        from alembic.script import ScriptDirectory

        backend_root = Path(__file__).resolve().parent.parent
        cfg = Config(str(backend_root / "alembic.ini"))
        # Point script_location to absolute path so test works from any cwd.
        cfg.set_main_option(
            "script_location", str(backend_root / "alembic")
        )
        script = ScriptDirectory.from_config(cfg)
        heads = script.get_heads()
        assert "r95_verticals_table" in heads, (
            f"r95_verticals_table not in heads: {heads}"
        )

    def test_verticals_table_exists(self, db_session):
        """`verticals` is a real table after migration."""
        from sqlalchemy import inspect

        bind = db_session.get_bind()
        inspector = inspect(bind)
        assert "verticals" in inspector.get_table_names()

    def test_four_canonical_seeds(self, db_session):
        """Migration seeds manufacturing/funeral_home/cemetery/crematory."""
        from app.models.vertical import Vertical

        rows = (
            db_session.query(Vertical).order_by(Vertical.sort_order.asc()).all()
        )
        slugs = [r.slug for r in rows]
        assert "manufacturing" in slugs
        assert "funeral_home" in slugs
        assert "cemetery" in slugs
        assert "crematory" in slugs

    def test_seed_display_names(self, db_session):
        from app.models.vertical import Vertical

        mapping = {r.slug: r.display_name for r in db_session.query(Vertical).all()}
        assert mapping["manufacturing"] == "Manufacturing"
        assert mapping["funeral_home"] == "Funeral Home"
        assert mapping["cemetery"] == "Cemetery"
        assert mapping["crematory"] == "Crematory"

    def test_seed_sort_order(self, db_session):
        from app.models.vertical import Vertical

        mapping = {r.slug: r.sort_order for r in db_session.query(Vertical).all()}
        assert mapping["manufacturing"] == 10
        assert mapping["funeral_home"] == 20
        assert mapping["cemetery"] == 30
        assert mapping["crematory"] == 40

    def test_check_constraint_rejects_invalid_status(self, db_session):
        """CHECK enforces canonical 3-value status enum."""
        from sqlalchemy.exc import IntegrityError

        from app.models.vertical import Vertical

        bad = Vertical(
            slug=f"bad-{uuid.uuid4().hex[:6]}",
            display_name="Bad",
            status="invalid_status_value",
            sort_order=999,
        )
        db_session.add(bad)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


# ─── Service-layer tests ──────────────────────────────────────


class TestService:
    def test_list_returns_four_ordered_by_sort_order(self, db_session):
        from app.services.verticals_service import list_verticals

        rows = list_verticals(db_session)
        assert len(rows) >= 4
        slugs = [r.slug for r in rows if r.slug in {
            "manufacturing", "funeral_home", "cemetery", "crematory",
        }]
        # Order: manufacturing (10), funeral_home (20), cemetery (30), crematory (40).
        assert slugs[:4] == [
            "manufacturing",
            "funeral_home",
            "cemetery",
            "crematory",
        ]

    def test_list_excludes_archived_by_default(self, db_session):
        from app.services.verticals_service import (
            list_verticals,
            update_vertical,
        )

        update_vertical(db_session, "crematory", status="archived")
        rows = list_verticals(db_session)
        assert "crematory" not in [r.slug for r in rows]

    def test_list_includes_archived_when_flag_true(self, db_session):
        from app.services.verticals_service import (
            list_verticals,
            update_vertical,
        )

        update_vertical(db_session, "crematory", status="archived")
        rows = list_verticals(db_session, include_archived=True)
        assert "crematory" in [r.slug for r in rows]

    def test_get_returns_row(self, db_session):
        from app.services.verticals_service import get_vertical

        row = get_vertical(db_session, "manufacturing")
        assert row.slug == "manufacturing"
        assert row.display_name == "Manufacturing"

    def test_get_raises_on_unknown(self, db_session):
        from app.services.verticals_service import (
            VerticalNotFound,
            get_vertical,
        )

        with pytest.raises(VerticalNotFound):
            get_vertical(db_session, "does-not-exist")

    def test_update_partial_only_specified_fields(self, db_session):
        from app.services.verticals_service import (
            get_vertical,
            update_vertical,
        )

        # Update only display_name; description/status/icon/sort_order
        # untouched.
        updated = update_vertical(
            db_session, "manufacturing", display_name="Manufacturing (Custom)"
        )
        assert updated.display_name == "Manufacturing (Custom)"
        assert updated.status == "published"  # unchanged
        assert updated.sort_order == 10  # unchanged

        # Re-fetch to confirm persisted.
        row = get_vertical(db_session, "manufacturing")
        assert row.display_name == "Manufacturing (Custom)"

    def test_update_rejects_invalid_status(self, db_session):
        from app.services.verticals_service import update_vertical

        with pytest.raises(ValueError):
            update_vertical(db_session, "manufacturing", status="not_a_status")

    def test_update_signature_has_no_slug_kwarg(self, db_session):
        """Slug is immutable (PK). Passing slug=... must raise TypeError."""
        from app.services.verticals_service import update_vertical

        with pytest.raises(TypeError):
            update_vertical(  # type: ignore[call-arg]
                db_session,
                "manufacturing",
                slug="renamed-slug",
            )

    def test_update_bumps_updated_at(self, db_session):
        from app.services.verticals_service import (
            get_vertical,
            update_vertical,
        )

        before = get_vertical(db_session, "manufacturing").updated_at
        time.sleep(0.05)  # ensure clock advances
        update_vertical(db_session, "manufacturing", icon="factory")
        after = get_vertical(db_session, "manufacturing").updated_at
        assert after > before

    def test_update_unknown_slug_raises(self, db_session):
        from app.services.verticals_service import (
            VerticalNotFound,
            update_vertical,
        )

        with pytest.raises(VerticalNotFound):
            update_vertical(db_session, "does-not-exist", display_name="X")


# ─── API tests ─────────────────────────────────────────────────


class TestApi:
    def test_list_returns_200_with_platform_user_auth(self, client):
        ctx = _make_platform_admin()
        resp = client.get(
            "/api/platform/admin/verticals/",
            headers=_admin_headers(ctx),
        )
        assert resp.status_code == 200
        rows = resp.json()
        slugs = [r["slug"] for r in rows]
        for canonical in ("manufacturing", "funeral_home", "cemetery", "crematory"):
            assert canonical in slugs

    def test_list_without_auth_returns_401_or_403(self, client):
        resp = client.get("/api/platform/admin/verticals/")
        assert resp.status_code in (401, 403)

    def test_list_include_archived_query(self, client):
        ctx = _make_platform_admin()
        # First archive crematory via PATCH.
        client.patch(
            "/api/platform/admin/verticals/crematory",
            json={"status": "archived"},
            headers=_admin_headers(ctx),
        )
        # Default list excludes.
        resp = client.get(
            "/api/platform/admin/verticals/",
            headers=_admin_headers(ctx),
        )
        slugs = [r["slug"] for r in resp.json()]
        assert "crematory" not in slugs
        # include_archived=true includes.
        resp2 = client.get(
            "/api/platform/admin/verticals/?include_archived=true",
            headers=_admin_headers(ctx),
        )
        slugs2 = [r["slug"] for r in resp2.json()]
        assert "crematory" in slugs2

    def test_get_returns_200(self, client):
        ctx = _make_platform_admin()
        resp = client.get(
            "/api/platform/admin/verticals/manufacturing",
            headers=_admin_headers(ctx),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["slug"] == "manufacturing"
        assert body["display_name"] == "Manufacturing"

    def test_get_404_on_unknown_slug(self, client):
        ctx = _make_platform_admin()
        resp = client.get(
            "/api/platform/admin/verticals/does-not-exist",
            headers=_admin_headers(ctx),
        )
        assert resp.status_code == 404

    def test_patch_updates_fields(self, client):
        ctx = _make_platform_admin()
        resp = client.patch(
            "/api/platform/admin/verticals/funeral_home",
            json={"display_name": "Funeral Home (Edited)", "icon": "heart"},
            headers=_admin_headers(ctx),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["display_name"] == "Funeral Home (Edited)"
        assert body["icon"] == "heart"
        # Verify persistence via GET.
        resp2 = client.get(
            "/api/platform/admin/verticals/funeral_home",
            headers=_admin_headers(ctx),
        )
        assert resp2.json()["display_name"] == "Funeral Home (Edited)"

    def test_patch_invalid_status_returns_400(self, client):
        ctx = _make_platform_admin()
        resp = client.patch(
            "/api/platform/admin/verticals/manufacturing",
            json={"status": "not_a_status"},
            headers=_admin_headers(ctx),
        )
        assert resp.status_code == 400

    def test_patch_unknown_slug_returns_404(self, client):
        ctx = _make_platform_admin()
        resp = client.patch(
            "/api/platform/admin/verticals/does-not-exist",
            json={"display_name": "X"},
            headers=_admin_headers(ctx),
        )
        assert resp.status_code == 404

    def test_patch_rejects_slug_in_body(self, client):
        """Pydantic VerticalUpdate has extra='forbid'; a body that
        includes `slug` must 422 — slug is immutable."""
        ctx = _make_platform_admin()
        resp = client.patch(
            "/api/platform/admin/verticals/manufacturing",
            json={"slug": "renamed-slug", "display_name": "X"},
            headers=_admin_headers(ctx),
        )
        assert resp.status_code == 422
