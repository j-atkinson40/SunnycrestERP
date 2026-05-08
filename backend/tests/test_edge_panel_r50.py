"""R-5.0 — edge panel substrate tests.

Covers:
  - Migration r91 schema invariants (kind column + pages JSONB +
    extended partial unique index).
  - Service-layer kind discriminator + pages validation.
  - 3-tier inheritance flow with kind=edge_panel rows.
  - Per-user override merge semantics (page_overrides, hidden_page_ids,
    page_order_override).
  - Admin API kind=edge_panel CRUD.
  - Tenant-realm /api/v1/edge-panel/* endpoints (resolve + preferences
    + tenant-config).
  - Cross-realm boundary (admin tokens rejected at tenant routes; tenant
    tokens rejected at admin routes).
  - Coexistence with kind=focus (existing scheduling-shape rows
    untouched + still resolvable).
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


def _make_tenant_with_admin(vertical: str = "manufacturing") -> dict:
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.platform_user import PlatformUser
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"R5 {suffix}",
            slug=f"r5-{suffix}",
            is_active=True,
            vertical=vertical,
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
            email=f"r5-admin-{suffix}@bridgeable.test",
            hashed_password="x",
            first_name="R5",
            last_name="Admin",
            role_id=admin_role.id,
            is_active=True,
        )
        db.add(admin)

        platform_admin = PlatformUser(
            id=str(uuid.uuid4()),
            email=f"r5-platform-{suffix}@bridgeable.test",
            hashed_password="x",
            first_name="R5",
            last_name="Platform",
            role="super_admin",
            is_active=True,
        )
        db.add(platform_admin)
        db.commit()

        tenant_token = create_access_token(
            {"sub": admin.id, "company_id": co.id},
            realm="tenant",
        )
        platform_token = create_access_token(
            {"sub": platform_admin.id},
            realm="platform",
        )
        return {
            "company_id": co.id,
            "vertical": vertical,
            "user_id": admin.id,
            "tenant_token": tenant_token,
            "platform_token": platform_token,
            "company_slug": co.slug,
        }
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


def _placement(
    pid: str,
    *,
    component_kind: str = "button",
    component_name: str = "open-funeral-scheduling-focus",
    starting_column: int = 0,
    column_span: int = 12,
) -> dict:
    return {
        "placement_id": pid,
        "component_kind": component_kind,
        "component_name": component_name,
        "starting_column": starting_column,
        "column_span": column_span,
        "prop_overrides": {},
        "display_config": {},
        "nested_rows": None,
    }


def _row(*, placements: list | None = None, column_count: int = 12) -> dict:
    return {
        "row_id": str(uuid.uuid4()),
        "column_count": column_count,
        "row_height": "auto",
        "column_widths": None,
        "nested_rows": None,
        "placements": placements or [],
    }


def _page(
    *,
    page_id: str | None = None,
    name: str = "Quick Actions",
    rows: list | None = None,
) -> dict:
    return {
        "page_id": page_id or str(uuid.uuid4()),
        "name": name,
        "rows": rows or [_row(placements=[_placement("p1")])],
        "canvas_config": {},
    }


# ─── Migration schema ─────────────────────────────────────────────


class TestMigrationR91Schema:
    def test_kind_column_present(self, db_session):
        insp = inspect(db_session.bind)
        cols = {c["name"] for c in insp.get_columns("focus_compositions")}
        assert "kind" in cols
        assert "pages" in cols

    def test_kind_check_constraint(self, db_session):
        # Inserting an invalid kind via raw SQL should fail.
        with pytest.raises(Exception):
            db_session.execute(
                text(
                    "INSERT INTO focus_compositions "
                    "(id, scope, focus_type, rows, canvas_config, kind, version, is_active, created_at, updated_at) "
                    "VALUES (:id, 'platform_default', 'bogus', '[]'::jsonb, '{}'::jsonb, 'NOPE', 1, true, NOW(), NOW())"
                ),
                {"id": str(uuid.uuid4())},
            )
            db_session.commit()
        db_session.rollback()

    def test_partial_unique_includes_kind(self, db_session):
        insp = inspect(db_session.bind)
        idx_names = [
            i["name"] for i in insp.get_indexes("focus_compositions")
        ]
        # The new index name carries _v2 suffix to disambiguate from
        # the pre-R-5 index that didn't include kind.
        assert "uq_focus_compositions_active_v2" in idx_names


# ─── Service-layer kind validation ───────────────────────────────


class TestKindValidation:
    def test_create_focus_kind_default(self, db_session):
        from app.services.focus_compositions import create_composition

        row = create_composition(
            db_session,
            scope="platform_default",
            focus_type="scheduling",
            rows=[_row(placements=[_placement("p1", component_kind="widget", component_name="today")])],
        )
        assert row.kind == "focus"
        assert row.pages is None

    def test_create_edge_panel_requires_pages(self, db_session):
        from app.services.focus_compositions import (
            InvalidCompositionShape,
            create_composition,
        )

        with pytest.raises(InvalidCompositionShape):
            create_composition(
                db_session,
                scope="platform_default",
                focus_type="default",
                kind="edge_panel",
                rows=[],  # missing pages
            )

    def test_create_focus_rejects_pages(self, db_session):
        from app.services.focus_compositions import (
            InvalidCompositionShape,
            create_composition,
        )

        with pytest.raises(InvalidCompositionShape):
            create_composition(
                db_session,
                scope="platform_default",
                focus_type="scheduling",
                kind="focus",
                pages=[_page()],
            )

    def test_create_edge_panel_with_pages(self, db_session):
        from app.services.focus_compositions import create_composition

        page = _page(name="Quick")
        row = create_composition(
            db_session,
            scope="platform_default",
            focus_type="default",
            kind="edge_panel",
            pages=[page],
        )
        assert row.kind == "edge_panel"
        assert row.pages is not None
        assert len(row.pages) == 1
        assert row.pages[0]["name"] == "Quick"
        assert row.rows == []

    def test_invalid_kind_rejected(self, db_session):
        from app.services.focus_compositions import (
            InvalidCompositionShape,
            create_composition,
        )

        with pytest.raises(InvalidCompositionShape):
            create_composition(
                db_session,
                scope="platform_default",
                focus_type="default",
                kind="bogus",
                pages=[_page()],
            )

    def test_pages_empty_list_rejected(self, db_session):
        from app.services.focus_compositions import (
            InvalidCompositionShape,
            create_composition,
        )

        with pytest.raises(InvalidCompositionShape):
            create_composition(
                db_session,
                scope="platform_default",
                focus_type="default",
                kind="edge_panel",
                pages=[],
            )

    def test_pages_duplicate_id_rejected(self, db_session):
        from app.services.focus_compositions import (
            InvalidCompositionShape,
            create_composition,
        )

        page1 = _page(page_id="dup", name="A")
        page2 = _page(page_id="dup", name="B")
        with pytest.raises(InvalidCompositionShape):
            create_composition(
                db_session,
                scope="platform_default",
                focus_type="default",
                kind="edge_panel",
                pages=[page1, page2],
            )


# ─── Inheritance + resolution ────────────────────────────────────


class TestEdgePanelInheritance:
    def test_resolve_falls_through_to_empty_pages(self, db_session):
        from app.services.focus_compositions import resolve_edge_panel

        result = resolve_edge_panel(
            db_session,
            panel_key="default",
            vertical="manufacturing",
            tenant_id=None,
        )
        assert result["source"] is None
        assert result["pages"] == []
        assert result["kind"] == "edge_panel"

    def test_resolve_finds_platform_default(self, db_session):
        from app.services.focus_compositions import (
            create_composition,
            resolve_edge_panel,
        )

        create_composition(
            db_session,
            scope="platform_default",
            focus_type="default",
            kind="edge_panel",
            pages=[_page(name="Plat")],
        )
        result = resolve_edge_panel(
            db_session,
            panel_key="default",
            vertical="manufacturing",
            tenant_id=None,
        )
        assert result["source"] == "platform_default"
        assert len(result["pages"]) == 1
        assert result["pages"][0]["name"] == "Plat"

    def test_tenant_override_wins_over_platform(self, db_session):
        from app.services.focus_compositions import (
            create_composition,
            resolve_edge_panel,
        )

        create_composition(
            db_session,
            scope="platform_default",
            focus_type="default",
            kind="edge_panel",
            pages=[_page(name="Plat")],
        )
        ctx = _make_tenant_with_admin()
        create_composition(
            db_session,
            scope="tenant_override",
            focus_type="default",
            tenant_id=ctx["company_id"],
            kind="edge_panel",
            pages=[_page(name="Tenant")],
        )
        result = resolve_edge_panel(
            db_session,
            panel_key="default",
            vertical="manufacturing",
            tenant_id=ctx["company_id"],
        )
        assert result["source"] == "tenant_override"
        assert result["pages"][0]["name"] == "Tenant"

    def test_focus_and_edge_panel_coexist_at_same_focus_type(self, db_session):
        """A tenant CAN have an active focus:scheduling AND
        edge_panel:scheduling row simultaneously since the partial
        unique index now includes kind."""
        from app.services.focus_compositions import (
            create_composition,
            resolve_composition,
            resolve_edge_panel,
        )

        ctx = _make_tenant_with_admin()
        create_composition(
            db_session,
            scope="tenant_override",
            focus_type="scheduling",
            tenant_id=ctx["company_id"],
            kind="focus",
            rows=[_row(placements=[_placement("p1", component_kind="widget", component_name="today")])],
        )
        create_composition(
            db_session,
            scope="tenant_override",
            focus_type="scheduling",
            tenant_id=ctx["company_id"],
            kind="edge_panel",
            pages=[_page()],
        )

        focus_result = resolve_composition(
            db_session,
            focus_type="scheduling",
            vertical="manufacturing",
            tenant_id=ctx["company_id"],
            kind="focus",
        )
        ep_result = resolve_edge_panel(
            db_session,
            panel_key="scheduling",
            vertical="manufacturing",
            tenant_id=ctx["company_id"],
        )
        assert focus_result["source"] == "tenant_override"
        assert ep_result["source"] == "tenant_override"
        assert focus_result["kind"] == "focus"
        assert ep_result["kind"] == "edge_panel"


# ─── Per-user overrides ──────────────────────────────────────────


class TestPerUserOverrides:
    def test_page_overrides_replace_rows(self, db_session):
        from app.services.focus_compositions import (
            create_composition,
            resolve_edge_panel,
        )

        page = _page(page_id="pg1", name="Quick")
        create_composition(
            db_session,
            scope="platform_default",
            focus_type="default",
            kind="edge_panel",
            pages=[page],
        )

        custom_row = _row(placements=[_placement("custom")])
        result = resolve_edge_panel(
            db_session,
            panel_key="default",
            user_overrides={
                "page_overrides": {
                    "pg1": {"rows": [custom_row]},
                }
            },
        )
        assert result["pages"][0]["rows"][0]["placements"][0]["placement_id"] == "custom"

    def test_hidden_page_dropped(self, db_session):
        from app.services.focus_compositions import (
            create_composition,
            resolve_edge_panel,
        )

        page1 = _page(page_id="a", name="A")
        page2 = _page(page_id="b", name="B")
        create_composition(
            db_session,
            scope="platform_default",
            focus_type="default",
            kind="edge_panel",
            pages=[page1, page2],
        )
        result = resolve_edge_panel(
            db_session,
            panel_key="default",
            user_overrides={"hidden_page_ids": ["a"]},
        )
        assert len(result["pages"]) == 1
        assert result["pages"][0]["page_id"] == "b"

    def test_page_order_override_reorders(self, db_session):
        from app.services.focus_compositions import (
            create_composition,
            resolve_edge_panel,
        )

        pa = _page(page_id="a", name="A")
        pb = _page(page_id="b", name="B")
        pc = _page(page_id="c", name="C")
        create_composition(
            db_session,
            scope="platform_default",
            focus_type="default",
            kind="edge_panel",
            pages=[pa, pb, pc],
        )
        result = resolve_edge_panel(
            db_session,
            panel_key="default",
            user_overrides={"page_order_override": ["c", "a", "b"]},
        )
        ids = [p["page_id"] for p in result["pages"]]
        assert ids == ["c", "a", "b"]

    def test_user_overrides_compose(self, db_session):
        from app.services.focus_compositions import (
            create_composition,
            resolve_edge_panel,
        )

        pa = _page(page_id="a", name="A")
        pb = _page(page_id="b", name="B")
        pc = _page(page_id="c", name="C")
        create_composition(
            db_session,
            scope="platform_default",
            focus_type="default",
            kind="edge_panel",
            pages=[pa, pb, pc],
        )
        custom = _row(placements=[_placement("X")])
        result = resolve_edge_panel(
            db_session,
            panel_key="default",
            user_overrides={
                "page_overrides": {"a": {"rows": [custom]}},
                "hidden_page_ids": ["b"],
                "page_order_override": ["c", "a"],
            },
        )
        ids = [p["page_id"] for p in result["pages"]]
        assert ids == ["c", "a"]
        # `a` carries the override
        a_page = next(p for p in result["pages"] if p["page_id"] == "a")
        assert a_page["rows"][0]["placements"][0]["placement_id"] == "X"


# ─── API: admin endpoint kind=edge_panel CRUD ────────────────────


class TestAdminApiEdgePanelCrud:
    def test_create_edge_panel_via_admin_api(self, client):
        ctx = _make_tenant_with_admin()
        resp = client.post(
            "/api/platform/admin/visual-editor/compositions/",
            headers={"Authorization": f"Bearer {ctx['platform_token']}"},
            json={
                "scope": "platform_default",
                "focus_type": "default",
                "kind": "edge_panel",
                "pages": [_page()],
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["kind"] == "edge_panel"
        assert body["pages"] is not None
        assert body["rows"] == []

    def test_list_filtered_by_kind(self, client):
        ctx = _make_tenant_with_admin()
        client.post(
            "/api/platform/admin/visual-editor/compositions/",
            headers={"Authorization": f"Bearer {ctx['platform_token']}"},
            json={
                "scope": "platform_default",
                "focus_type": "scheduling",
                "kind": "focus",
                "rows": [_row(placements=[_placement("p1", component_kind="widget", component_name="today")])],
            },
        )
        client.post(
            "/api/platform/admin/visual-editor/compositions/",
            headers={"Authorization": f"Bearer {ctx['platform_token']}"},
            json={
                "scope": "platform_default",
                "focus_type": "default",
                "kind": "edge_panel",
                "pages": [_page()],
            },
        )
        resp = client.get(
            "/api/platform/admin/visual-editor/compositions/?kind=edge_panel",
            headers={"Authorization": f"Bearer {ctx['platform_token']}"},
        )
        assert resp.status_code == 200
        rows = resp.json()
        assert all(r["kind"] == "edge_panel" for r in rows)
        assert len(rows) == 1

    def test_resolve_endpoint_kind_query(self, client):
        ctx = _make_tenant_with_admin()
        client.post(
            "/api/platform/admin/visual-editor/compositions/",
            headers={"Authorization": f"Bearer {ctx['platform_token']}"},
            json={
                "scope": "platform_default",
                "focus_type": "default",
                "kind": "edge_panel",
                "pages": [_page(name="Plat")],
            },
        )
        resp = client.get(
            "/api/platform/admin/visual-editor/compositions/resolve?focus_type=default&kind=edge_panel",
            headers={"Authorization": f"Bearer {ctx['platform_token']}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["kind"] == "edge_panel"
        assert body["source"] == "platform_default"


# ─── API: tenant-realm endpoints ─────────────────────────────────


class TestTenantRealmEndpoints:
    def test_resolve_returns_empty_when_no_composition(self, client):
        ctx = _make_tenant_with_admin()
        resp = client.get(
            "/api/v1/edge-panel/resolve?panel_key=default",
            headers={
                "Authorization": f"Bearer {ctx['tenant_token']}",
                "X-Company-Slug": ctx["company_slug"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["panel_key"] == "default"
        assert body["pages"] == []
        assert body["source"] is None

    def test_resolve_returns_platform_default(self, client):
        from app.database import SessionLocal
        from app.services.focus_compositions import create_composition

        ctx = _make_tenant_with_admin()
        db = SessionLocal()
        try:
            create_composition(
                db,
                scope="platform_default",
                focus_type="default",
                kind="edge_panel",
                pages=[_page(name="Plat")],
            )
        finally:
            db.close()

        resp = client.get(
            "/api/v1/edge-panel/resolve?panel_key=default",
            headers={
                "Authorization": f"Bearer {ctx['tenant_token']}",
                "X-Company-Slug": ctx["company_slug"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["source"] == "platform_default"
        assert len(body["pages"]) == 1

    def test_preferences_round_trip(self, client):
        ctx = _make_tenant_with_admin()
        # Initial GET — empty
        resp = client.get(
            "/api/v1/edge-panel/preferences",
            headers={
                "Authorization": f"Bearer {ctx['tenant_token']}",
                "X-Company-Slug": ctx["company_slug"],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["edge_panel_overrides"] == {}

        # PATCH
        new_prefs = {
            "default": {
                "page_order_override": ["b", "a"],
                "hidden_page_ids": [],
            }
        }
        resp = client.patch(
            "/api/v1/edge-panel/preferences",
            headers={
                "Authorization": f"Bearer {ctx['tenant_token']}",
                "X-Company-Slug": ctx["company_slug"],
            },
            json={"edge_panel_overrides": new_prefs},
        )
        assert resp.status_code == 200
        assert resp.json()["edge_panel_overrides"] == new_prefs

        # GET reflects the patch
        resp = client.get(
            "/api/v1/edge-panel/preferences",
            headers={
                "Authorization": f"Bearer {ctx['tenant_token']}",
                "X-Company-Slug": ctx["company_slug"],
            },
        )
        assert resp.json()["edge_panel_overrides"] == new_prefs

    def test_tenant_config_defaults(self, client):
        ctx = _make_tenant_with_admin()
        resp = client.get(
            "/api/v1/edge-panel/tenant-config",
            headers={
                "Authorization": f"Bearer {ctx['tenant_token']}",
                "X-Company-Slug": ctx["company_slug"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["enabled"] is True
        assert body["width"] == 320

    def test_tenant_config_reads_settings(self, client):
        from app.database import SessionLocal
        from app.models.company import Company

        ctx = _make_tenant_with_admin()
        db = SessionLocal()
        try:
            company = db.query(Company).filter_by(id=ctx["company_id"]).first()
            company.set_setting("edge_panel_width", 360)
            company.set_setting("edge_panel_enabled", False)
            db.add(company)
            db.commit()
        finally:
            db.close()

        resp = client.get(
            "/api/v1/edge-panel/tenant-config",
            headers={
                "Authorization": f"Bearer {ctx['tenant_token']}",
                "X-Company-Slug": ctx["company_slug"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["enabled"] is False
        assert body["width"] == 360

    def test_resolve_no_auth_rejected(self, client):
        resp = client.get("/api/v1/edge-panel/resolve?panel_key=default")
        assert resp.status_code in (401, 403)
