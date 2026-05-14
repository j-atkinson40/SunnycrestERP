"""Tenant-realm edge-panel endpoint tests (B-2 rewrite).

The legacy R-5.0 suite covered:
  - Migration schema invariants → now covered by Tier 2 / Tier 3
    schema in `test_edge_panel_inheritance_service.py` + admin-API
    coverage in `test_edge_panel_inheritance_admin_api.py`.
  - Service-layer kind/pages validation → ditto.
  - Inheritance walk (platform → vertical → tenant_override → user) →
    exhaustively covered in `test_edge_panel_inheritance_service.py`
    `TestResolver` and again in the admin-API integration tests.
  - Cross-realm boundary at admin routes → covered in
    `test_edge_panel_inheritance_admin_api.py`.

What remains uncovered elsewhere is the **tenant-realm
`/api/v1/edge-panel/*`** surface — the one consumed by the live
edge panel mounted in the tenant app. B-2 ported these endpoints
from the old `composition_service.resolve_edge_panel(user_overrides=...)`
call shape onto B-1.5's `edge_panel_inheritance.resolve_edge_panel(
user_id=...)` shape. This file regresses that port end-to-end.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.database import SessionLocal
from app.models.company import Company
from app.models.edge_panel_composition import EdgePanelComposition
from app.models.edge_panel_template import EdgePanelTemplate
from app.models.role import Role
from app.models.user import User
from app.services.edge_panel_inheritance import create_template


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


@pytest.fixture(autouse=True)
def _cleanup():
    def _wipe():
        s = SessionLocal()
        try:
            s.query(EdgePanelComposition).delete()
            s.query(EdgePanelTemplate).delete()
            s.commit()
        finally:
            s.close()

    _wipe()
    yield
    _wipe()


def _label(pid: str) -> dict:
    return {
        "placement_id": pid,
        "component_kind": "edge-panel-label",
        "component_name": "default",
        "starting_column": 0,
        "column_span": 12,
        "prop_overrides": {"text": "QUICK"},
        "display_config": {},
    }


def _button(pid: str, name: str = "navigate-to-pulse") -> dict:
    return {
        "placement_id": pid,
        "component_kind": "button",
        "component_name": name,
        "starting_column": 0,
        "column_span": 12,
        "prop_overrides": {},
        "display_config": {},
    }


def _row(*, row_id: str, placements: list[dict]) -> dict:
    return {
        "row_id": row_id,
        "column_count": 12,
        "row_height": "auto",
        "column_widths": None,
        "nested_rows": None,
        "placements": placements,
    }


def _page(*, page_id: str, name: str, rows: list[dict]) -> dict:
    return {
        "page_id": page_id,
        "name": name,
        "rows": rows,
        "canvas_config": {"gap_size": 10},
    }


def _make_tenant_and_user(vertical: str = "funeral_home") -> dict:
    s = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"EPR {suffix}",
            slug=f"epr-{suffix}",
            is_active=True,
            vertical=vertical,
        )
        s.add(co)
        s.flush()

        role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name="Admin",
            slug="admin",
            is_system=True,
        )
        s.add(role)
        s.flush()

        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"epr-{suffix}@epr.test",
            hashed_password="x",
            first_name="E",
            last_name="P",
            role_id=role.id,
            is_active=True,
            preferences={},
        )
        s.add(user)
        s.commit()
        token = create_access_token(
            {"sub": user.id, "company_id": co.id}, realm="tenant"
        )
        return {
            "company_id": co.id,
            "user_id": user.id,
            "role_id": role.id,
            "token": token,
            "slug": co.slug,
        }
    finally:
        s.close()


def _cleanup_tenant(ids: dict) -> None:
    s = SessionLocal()
    try:
        s.query(User).filter(User.id == ids["user_id"]).delete()
        s.query(Role).filter(Role.id == ids["role_id"]).delete()
        s.query(Company).filter(Company.id == ids["company_id"]).delete()
        s.commit()
    finally:
        s.close()


def _headers(ctx: dict) -> dict:
    return {
        "Authorization": f"Bearer {ctx['token']}",
        "X-Company-Slug": ctx["slug"],
    }


def _seed_vertical_default(vertical: str) -> EdgePanelTemplate:
    s = SessionLocal()
    try:
        return create_template(
            s,
            scope="vertical_default",
            vertical=vertical,
            panel_key="default",
            display_name=f"{vertical} default",
            description=None,
            pages=[
                _page(
                    page_id="quick-actions",
                    name="Quick Actions",
                    rows=[
                        _row(
                            row_id="qa-r0",
                            placements=[_label("lbl-qa")],
                        ),
                        _row(
                            row_id="qa-r1",
                            placements=[_button("btn-pulse")],
                        ),
                    ],
                )
            ],
            canvas_config={"default_page_index": 0},
        )
    finally:
        s.close()


class TestResolveEndpoint:
    def test_resolve_returns_vertical_default(self, client):
        _seed_vertical_default("funeral_home")
        ctx = _make_tenant_and_user("funeral_home")
        try:
            r = client.get(
                "/api/v1/edge-panel/resolve?panel_key=default",
                headers=_headers(ctx),
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["panel_key"] == "default"
            assert body["vertical"] == "funeral_home"
            assert body["tenant_id"] == ctx["company_id"]
            assert body["source"] == "vertical_default"
            assert len(body["pages"]) == 1
            assert body["pages"][0]["page_id"] == "quick-actions"
        finally:
            _cleanup_tenant(ctx)

    def test_resolve_missing_panel_key_404(self, client):
        ctx = _make_tenant_and_user("funeral_home")
        try:
            r = client.get(
                "/api/v1/edge-panel/resolve?panel_key=does-not-exist",
                headers=_headers(ctx),
            )
            assert r.status_code == 404
        finally:
            _cleanup_tenant(ctx)

    def test_resolve_unauth_rejects(self, client):
        _seed_vertical_default("funeral_home")
        r = client.get("/api/v1/edge-panel/resolve?panel_key=default")
        assert r.status_code in (401, 403)

    def test_resolve_applies_user_overrides(self, client):
        _seed_vertical_default("funeral_home")
        ctx = _make_tenant_and_user("funeral_home")
        try:
            # Stash a user override that hides the only page.
            s = SessionLocal()
            try:
                u = s.query(User).filter(User.id == ctx["user_id"]).one()
                u.preferences = {
                    "edge_panel_overrides": {
                        "default": {
                            "hidden_page_ids": ["quick-actions"],
                        }
                    }
                }
                from sqlalchemy.orm.attributes import flag_modified

                flag_modified(u, "preferences")
                s.commit()
            finally:
                s.close()

            r = client.get(
                "/api/v1/edge-panel/resolve?panel_key=default",
                headers=_headers(ctx),
            )
            assert r.status_code == 200
            body = r.json()
            assert body["pages"] == []

            # ignore_user_overrides bypasses the user layer
            r2 = client.get(
                "/api/v1/edge-panel/resolve?panel_key=default"
                "&ignore_user_overrides=true",
                headers=_headers(ctx),
            )
            assert r2.status_code == 200
            assert len(r2.json()["pages"]) == 1
        finally:
            _cleanup_tenant(ctx)


class TestPreferencesEndpoint:
    def test_get_empty_preferences(self, client):
        ctx = _make_tenant_and_user("funeral_home")
        try:
            r = client.get(
                "/api/v1/edge-panel/preferences", headers=_headers(ctx)
            )
            assert r.status_code == 200
            assert r.json()["edge_panel_overrides"] == {}
        finally:
            _cleanup_tenant(ctx)

    def test_patch_then_get_roundtrip(self, client):
        ctx = _make_tenant_and_user("funeral_home")
        try:
            blob = {
                "default": {
                    "hidden_page_ids": ["quick-actions"],
                    "additional_pages": [],
                }
            }
            r = client.patch(
                "/api/v1/edge-panel/preferences",
                json={"edge_panel_overrides": blob},
                headers=_headers(ctx),
            )
            assert r.status_code == 200, r.text
            assert r.json()["edge_panel_overrides"] == blob

            r2 = client.get(
                "/api/v1/edge-panel/preferences", headers=_headers(ctx)
            )
            assert r2.status_code == 200
            assert r2.json()["edge_panel_overrides"] == blob
        finally:
            _cleanup_tenant(ctx)


class TestTenantConfigEndpoint:
    def test_defaults_when_unconfigured(self, client):
        ctx = _make_tenant_and_user("funeral_home")
        try:
            r = client.get(
                "/api/v1/edge-panel/tenant-config", headers=_headers(ctx)
            )
            assert r.status_code == 200
            body = r.json()
            assert body["enabled"] is True
            assert body["width"] == 320
        finally:
            _cleanup_tenant(ctx)
