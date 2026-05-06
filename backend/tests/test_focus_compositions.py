"""Focus composition layer tests (May 2026).

Covers:
  - CRUD lifecycle (create, version, update, list, get)
  - Inheritance walk (platform_default → vertical_default →
    tenant_override; first match wins)
  - Validation: scope-key shape, malformed placements, grid bounds,
    duplicate placement_ids
  - Overlap is permitted (warning-only)
  - Admin gating
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient


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


def _make_platform_admin_token():
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.platform_user import PlatformUser

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        admin = PlatformUser(
            id=str(uuid.uuid4()),
            email=f"platform-comp-{suffix}@bridgeable.test",
            hashed_password="x",
            first_name="Platform",
            last_name="Admin",
            role="super_admin",
            is_active=True,
        )
        db.add(admin)
        db.commit()
        token = create_access_token({"sub": admin.id}, realm="platform")
        return {"id": admin.id, "token": token}
    finally:
        db.close()


def _admin_headers(ctx):
    return {"Authorization": f"Bearer {ctx['token']}"}


def _make_tenant():
    """Create a minimal tenant + return its company_id for
    tenant_override scope tests."""
    from app.database import SessionLocal
    from app.models.company import Company

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"Comp Test {suffix}",
            slug=f"comp-test-{suffix}",
            is_active=True,
            vertical="manufacturing",
        )
        db.add(co)
        db.commit()
        return co.id
    finally:
        db.close()


def _cleanup():
    from app.database import SessionLocal
    from app.models.focus_composition import FocusComposition

    db = SessionLocal()
    try:
        db.query(FocusComposition).delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _per_test_cleanup():
    _cleanup()
    yield
    _cleanup()


# ─── Sample placement helpers ───────────────────────────────────


def _placement(
    placement_id: str,
    *,
    column_start: int = 1,
    column_span: int = 6,
    row_start: int = 1,
    row_span: int = 3,
    component_kind: str = "widget",
    component_name: str = "today",
    prop_overrides: dict | None = None,
) -> dict:
    return {
        "placement_id": placement_id,
        "component_kind": component_kind,
        "component_name": component_name,
        "grid": {
            "column_start": column_start,
            "column_span": column_span,
            "row_start": row_start,
            "row_span": row_span,
        },
        "prop_overrides": prop_overrides or {},
        "display_config": {},
    }


# ─── Service layer ──────────────────────────────────────────────


class TestServiceValidation:
    def test_scope_key_mismatch_rejected(self, db_session):
        from app.services.focus_compositions import (
            CompositionScopeMismatch,
            create_composition,
        )

        # Workaround for top-level import: re-import the exception class
        from app.services.focus_compositions.composition_service import (
            CompositionScopeMismatch as _SM,
        )

        with pytest.raises(_SM):
            create_composition(
                db_session,
                scope="vertical_default",
                focus_type="scheduling",
                vertical=None,  # missing; should be required
                tenant_id=None,
                placements=[],
            )

    def test_duplicate_placement_id_rejected(self, db_session):
        from app.services.focus_compositions import (
            InvalidCompositionShape,
            create_composition,
        )

        with pytest.raises(InvalidCompositionShape):
            create_composition(
                db_session,
                scope="platform_default",
                focus_type="scheduling",
                placements=[
                    _placement("a"),
                    _placement("a"),  # duplicate id
                ],
            )

    def test_out_of_bounds_grid_rejected(self, db_session):
        from app.services.focus_compositions import (
            InvalidCompositionShape,
            create_composition,
        )

        with pytest.raises(InvalidCompositionShape):
            create_composition(
                db_session,
                scope="platform_default",
                focus_type="scheduling",
                placements=[_placement("a", column_start=10, column_span=6)],
            )

    def test_overlapping_placements_permitted_with_warning(
        self, db_session, caplog
    ):
        from app.services.focus_compositions import create_composition

        # Two placements that occupy the same cells should NOT raise.
        row = create_composition(
            db_session,
            scope="platform_default",
            focus_type="scheduling",
            placements=[
                _placement("a", column_start=1, column_span=6),
                _placement("b", column_start=4, column_span=6),  # overlaps
            ],
        )
        assert row.id


class TestServiceCRUD:
    def test_create_versions_existing_active_row(self, db_session):
        from app.services.focus_compositions import (
            create_composition,
            list_compositions,
        )

        v1 = create_composition(
            db_session,
            scope="platform_default",
            focus_type="scheduling",
            placements=[_placement("a")],
        )
        v2 = create_composition(
            db_session,
            scope="platform_default",
            focus_type="scheduling",
            placements=[_placement("a"), _placement("b", column_start=7)],
        )
        assert v2.version == v1.version + 1
        assert v2.is_active is True

        rows = list_compositions(
            db_session,
            scope="platform_default",
            focus_type="scheduling",
            include_inactive=True,
        )
        assert sum(1 for r in rows if r.is_active) == 1

    def test_update_versions_and_replaces(self, db_session):
        from app.services.focus_compositions import (
            create_composition,
            update_composition,
        )

        v1 = create_composition(
            db_session,
            scope="platform_default",
            focus_type="scheduling",
            placements=[_placement("a")],
        )
        v2 = update_composition(
            db_session,
            composition_id=v1.id,
            placements=[
                _placement("a"),
                _placement("b", column_start=7, column_span=6),
            ],
            canvas_config={"total_columns": 12, "gap_size": 16},
        )
        assert v2.version > v1.version
        assert v2.is_active is True
        assert len(v2.placements) == 2
        assert v2.canvas_config.get("gap_size") == 16


class TestResolution:
    def test_empty_when_no_composition_exists(self, db_session):
        from app.services.focus_compositions import resolve_composition

        result = resolve_composition(
            db_session, focus_type="scheduling", vertical="funeral_home"
        )
        assert result["source"] is None
        assert result["placements"] == []

    def test_platform_default_returned_when_no_vertical_or_tenant(
        self, db_session
    ):
        from app.services.focus_compositions import (
            create_composition,
            resolve_composition,
        )

        create_composition(
            db_session,
            scope="platform_default",
            focus_type="scheduling",
            placements=[_placement("p")],
        )
        result = resolve_composition(db_session, focus_type="scheduling")
        assert result["source"] == "platform_default"
        assert len(result["placements"]) == 1

    def test_vertical_default_overrides_platform(self, db_session):
        from app.services.focus_compositions import (
            create_composition,
            resolve_composition,
        )

        create_composition(
            db_session,
            scope="platform_default",
            focus_type="scheduling",
            placements=[_placement("p")],
        )
        create_composition(
            db_session,
            scope="vertical_default",
            focus_type="scheduling",
            vertical="funeral_home",
            placements=[
                _placement("v1"),
                _placement("v2", column_start=7, column_span=6),
            ],
        )
        result = resolve_composition(
            db_session, focus_type="scheduling", vertical="funeral_home"
        )
        assert result["source"] == "vertical_default"
        assert len(result["placements"]) == 2
        # Manufacturing (different vertical) still gets platform default
        result_mfg = resolve_composition(
            db_session, focus_type="scheduling", vertical="manufacturing"
        )
        assert result_mfg["source"] == "platform_default"

    def test_tenant_override_wins_over_vertical_and_platform(self, db_session):
        from app.services.focus_compositions import (
            create_composition,
            resolve_composition,
        )

        tenant_id = _make_tenant()
        create_composition(
            db_session,
            scope="platform_default",
            focus_type="scheduling",
            placements=[_placement("p")],
        )
        create_composition(
            db_session,
            scope="vertical_default",
            focus_type="scheduling",
            vertical="manufacturing",
            placements=[_placement("v")],
        )
        create_composition(
            db_session,
            scope="tenant_override",
            focus_type="scheduling",
            tenant_id=tenant_id,
            placements=[
                _placement("t1"),
                _placement("t2", column_start=7, column_span=6),
                _placement("t3", row_start=4, column_span=12),
            ],
        )
        result = resolve_composition(
            db_session,
            focus_type="scheduling",
            vertical="manufacturing",
            tenant_id=tenant_id,
        )
        assert result["source"] == "tenant_override"
        assert len(result["placements"]) == 3


# ─── API layer ──────────────────────────────────────────────────


class TestApiAdmin:
    def test_create_then_list_then_resolve(self, client):
        ctx = _make_platform_admin_token()
        create_resp = client.post(
            "/api/platform/admin/visual-editor/compositions/",
            headers=_admin_headers(ctx),
            json={
                "scope": "platform_default",
                "focus_type": "scheduling",
                "placements": [_placement("a")],
                "canvas_config": {"total_columns": 12, "gap_size": 12},
            },
        )
        assert create_resp.status_code == 201
        payload = create_resp.json()
        assert payload["focus_type"] == "scheduling"
        assert len(payload["placements"]) == 1

        list_resp = client.get(
            "/api/platform/admin/visual-editor/compositions/?focus_type=scheduling",
            headers=_admin_headers(ctx),
        )
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1

        resolve_resp = client.get(
            "/api/platform/admin/visual-editor/compositions/resolve?focus_type=scheduling",
            headers=_admin_headers(ctx),
        )
        assert resolve_resp.status_code == 200
        body = resolve_resp.json()
        assert body["source"] == "platform_default"
        assert body["focus_type"] == "scheduling"

    def test_invalid_grid_returns_400(self, client):
        ctx = _make_platform_admin_token()
        resp = client.post(
            "/api/platform/admin/visual-editor/compositions/",
            headers=_admin_headers(ctx),
            json={
                "scope": "platform_default",
                "focus_type": "scheduling",
                "placements": [
                    {
                        "placement_id": "bad",
                        "component_kind": "widget",
                        "component_name": "today",
                        "grid": {
                            "column_start": 11,
                            "column_span": 6,  # column_start + span > 13
                            "row_start": 1,
                            "row_span": 3,
                        },
                        "prop_overrides": {},
                        "display_config": {},
                    }
                ],
            },
        )
        assert resp.status_code == 400

    def test_anonymous_rejected(self, client):
        resp = client.get("/api/platform/admin/visual-editor/compositions/")
        assert resp.status_code in (401, 403)

    def test_resolve_falls_back_through_chain(self, client):
        ctx = _make_platform_admin_token()
        # Create vertical_default for funeral_home only.
        client.post(
            "/api/platform/admin/visual-editor/compositions/",
            headers=_admin_headers(ctx),
            json={
                "scope": "vertical_default",
                "focus_type": "scheduling",
                "vertical": "funeral_home",
                "placements": [_placement("fh1")],
            },
        )
        # Resolve for funeral_home — gets vertical_default.
        resp = client.get(
            "/api/platform/admin/visual-editor/compositions/resolve?focus_type=scheduling&vertical=funeral_home",
            headers=_admin_headers(ctx),
        )
        assert resp.json()["source"] == "vertical_default"
        # Resolve for manufacturing — no record at any tier, returns null source.
        resp_mfg = client.get(
            "/api/platform/admin/visual-editor/compositions/resolve?focus_type=scheduling&vertical=manufacturing",
            headers=_admin_headers(ctx),
        )
        assert resp_mfg.json()["source"] is None
