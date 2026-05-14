"""Edge Panel Inheritance — admin API tests (B-1.5).

Covers `/api/platform/admin/edge-panel-inheritance/*` endpoints: auth
gates (anonymous reject, cross-realm reject, cross-tenant reject),
Tier 2 / Tier 3 round-trips, lazy-fork upsert, resolver shape +
provenance, 404 + 422 validation paths, reset-page behavior.
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
from app.models.platform_user import PlatformUser


API_ROOT = "/api/platform/admin/edge-panel-inheritance"


# ─── Fixtures ──────────────────────────────────────────────────────


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


@pytest.fixture
def ctx():
    """Platform admin + two tenants + tenant users for cross-tenant
    isolation tests."""
    from app.models.role import Role
    from app.models.user import User

    s = SessionLocal()
    suffix = uuid.uuid4().hex[:6]
    try:
        co = Company(
            id=str(uuid.uuid4()),
            name=f"EPI API {suffix}",
            slug=f"epia-{suffix}",
            is_active=True,
            vertical="funeral_home",
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
        tenant_user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"admin-{suffix}@epi.test",
            hashed_password="x",
            first_name="T",
            last_name="A",
            role_id=role.id,
            is_active=True,
        )
        s.add(tenant_user)

        platform_admin = PlatformUser(
            id=str(uuid.uuid4()),
            email=f"platform-{suffix}@bridgeable.test",
            hashed_password="x",
            first_name="P",
            last_name="A",
            role="super_admin",
            is_active=True,
        )
        s.add(platform_admin)
        s.commit()

        tenant_token = create_access_token(
            {"sub": tenant_user.id, "company_id": co.id}, realm="tenant"
        )
        platform_token = create_access_token(
            {"sub": platform_admin.id}, realm="platform"
        )

        suffix2 = uuid.uuid4().hex[:6]
        co2 = Company(
            id=str(uuid.uuid4()),
            name=f"EPI API Other {suffix2}",
            slug=f"epia2-{suffix2}",
            is_active=True,
            vertical="manufacturing",
        )
        s.add(co2)
        s.flush()
        role2 = Role(
            id=str(uuid.uuid4()),
            company_id=co2.id,
            name="Admin",
            slug="admin",
            is_system=True,
        )
        s.add(role2)
        s.flush()
        other_user = User(
            id=str(uuid.uuid4()),
            company_id=co2.id,
            email=f"other-{suffix2}@epi.test",
            hashed_password="x",
            first_name="O",
            last_name="U",
            role_id=role2.id,
            is_active=True,
        )
        s.add(other_user)
        s.commit()
        other_tenant_token = create_access_token(
            {"sub": other_user.id, "company_id": co2.id}, realm="tenant"
        )

        ctx_data = {
            "company_id": co.id,
            "slug": co.slug,
            "other_company_id": co2.id,
            "platform_token": platform_token,
            "tenant_token": tenant_token,
            "other_tenant_token": other_tenant_token,
        }
        yield ctx_data
    finally:
        s2 = SessionLocal()
        try:
            for cid in (co.id, co2.id):
                s2.query(EdgePanelComposition).filter(
                    EdgePanelComposition.tenant_id == cid
                ).delete()
            s2.commit()
            for cid in (co.id, co2.id):
                obj = s2.query(Company).filter(Company.id == cid).first()
                if obj is not None:
                    from app.models.role import Role as _R
                    from app.models.user import User as _U

                    s2.query(_U).filter(_U.company_id == cid).delete()
                    s2.query(_R).filter(_R.company_id == cid).delete()
                    s2.delete(obj)
            s2.query(PlatformUser).filter(
                PlatformUser.id == platform_admin.id
            ).delete()
            s2.commit()
        finally:
            s2.close()
        s.close()


def _platform_headers(ctx) -> dict:
    return {"Authorization": f"Bearer {ctx['platform_token']}"}


def _tenant_headers(ctx) -> dict:
    return {
        "Authorization": f"Bearer {ctx['tenant_token']}",
        "X-Company-Slug": ctx["slug"],
    }


def _other_tenant_headers(ctx) -> dict:
    return {"Authorization": f"Bearer {ctx['other_tenant_token']}"}


def _quick_actions_page() -> dict:
    return {
        "page_id": "quick-actions",
        "name": "Quick Actions",
        "rows": [
            {
                "row_id": "r0",
                "column_count": 12,
                "row_height": "auto",
                "column_widths": None,
                "nested_rows": None,
                "placements": [
                    {
                        "placement_id": "btn-pulse",
                        "component_kind": "button",
                        "component_name": "navigate-to-pulse",
                        "starting_column": 0,
                        "column_span": 12,
                        "prop_overrides": {},
                        "display_config": {},
                    }
                ],
            }
        ],
        "canvas_config": {"gap_size": 10},
    }


# ─── Auth gates ─────────────────────────────────────────────────


def test_anonymous_rejected(client):
    r = client.get(f"{API_ROOT}/templates")
    assert r.status_code in (401, 403)


def test_tenant_token_rejected_on_tier2_create(client, ctx):
    """Tier 2 endpoints accept only platform realm."""
    r = client.post(
        f"{API_ROOT}/templates",
        headers=_tenant_headers(ctx),
        json={
            "scope": "platform_default",
            "panel_key": "test",
            "display_name": "Test",
            "pages": [],
            "canvas_config": {},
        },
    )
    assert r.status_code == 401


def test_platform_admin_lifecycle_templates(client, ctx):
    # Create.
    r = client.post(
        f"{API_ROOT}/templates",
        headers=_platform_headers(ctx),
        json={
            "scope": "platform_default",
            "vertical": None,
            "panel_key": "default",
            "display_name": "Platform default",
            "pages": [_quick_actions_page()],
            "canvas_config": {},
        },
    )
    assert r.status_code == 201, r.text
    tid = r.json()["id"]
    assert r.json()["version"] == 1

    # Get by id.
    g = client.get(
        f"{API_ROOT}/templates/{tid}", headers=_platform_headers(ctx)
    )
    assert g.status_code == 200
    assert g.json()["panel_key"] == "default"

    # List.
    lst = client.get(f"{API_ROOT}/templates", headers=_platform_headers(ctx))
    assert lst.status_code == 200
    assert any(t["id"] == tid for t in lst.json())

    # Update (version bump).
    u = client.put(
        f"{API_ROOT}/templates/{tid}",
        headers=_platform_headers(ctx),
        json={"display_name": "Renamed"},
    )
    assert u.status_code == 200
    assert u.json()["version"] == 2
    assert u.json()["display_name"] == "Renamed"

    # Usage.
    usage = client.get(
        f"{API_ROOT}/templates/{u.json()['id']}/usage",
        headers=_platform_headers(ctx),
    )
    assert usage.status_code == 200
    assert usage.json()["compositions_count"] == 0


def test_tier3_lazy_fork_lifecycle(client, ctx):
    # Seed a template via platform admin.
    r = client.post(
        f"{API_ROOT}/templates",
        headers=_platform_headers(ctx),
        json={
            "scope": "platform_default",
            "panel_key": "default",
            "display_name": "Platform default",
            "pages": [_quick_actions_page()],
            "canvas_config": {},
        },
    )
    tid = r.json()["id"]

    # Tenant upsert composition (matching company_id).
    up = client.post(
        f"{API_ROOT}/compositions",
        headers=_tenant_headers(ctx),
        json={
            "tenant_id": ctx["company_id"],
            "template_id": tid,
            "deltas": {"hidden_page_ids": []},
            "canvas_config_overrides": {},
        },
    )
    assert up.status_code == 201, up.text
    cid = up.json()["id"]
    assert up.json()["version"] == 1

    # Get by tenant+template.
    g = client.get(
        f"{API_ROOT}/compositions/by-tenant-template",
        params={"tenant_id": ctx["company_id"], "template_id": tid},
        headers=_tenant_headers(ctx),
    )
    assert g.status_code == 200
    assert g.json()["id"] == cid

    # Reset.
    rst = client.post(
        f"{API_ROOT}/compositions/{cid}/reset",
        headers=_tenant_headers(ctx),
    )
    assert rst.status_code == 200
    assert rst.json()["version"] == 2


def test_cross_tenant_tier3_rejected(client, ctx):
    r = client.post(
        f"{API_ROOT}/templates",
        headers=_platform_headers(ctx),
        json={
            "scope": "platform_default",
            "panel_key": "default",
            "display_name": "Platform default",
            "pages": [_quick_actions_page()],
            "canvas_config": {},
        },
    )
    tid = r.json()["id"]
    # Other tenant tries to upsert for the first tenant's company_id.
    bad = client.post(
        f"{API_ROOT}/compositions",
        headers=_other_tenant_headers(ctx),
        json={
            "tenant_id": ctx["company_id"],
            "template_id": tid,
            "deltas": None,
        },
    )
    assert bad.status_code == 403


def test_resolve_shape_and_provenance(client, ctx):
    r = client.post(
        f"{API_ROOT}/templates",
        headers=_platform_headers(ctx),
        json={
            "scope": "vertical_default",
            "vertical": "funeral_home",
            "panel_key": "default",
            "display_name": "FH default",
            "pages": [_quick_actions_page()],
            "canvas_config": {},
        },
    )
    assert r.status_code == 201, r.text

    # Tenant calls resolve scoped to their own tenant_id (auto-pin).
    rv = client.get(
        f"{API_ROOT}/resolve",
        params={"panel_key": "default", "vertical": "funeral_home"},
        headers=_tenant_headers(ctx),
    )
    assert rv.status_code == 200, rv.text
    body = rv.json()
    assert body["panel_key"] == "default"
    assert body["template_scope"] == "vertical_default"
    assert body["template_vertical"] == "funeral_home"
    assert "sources" in body
    assert body["sources"]["template"]["scope"] == "vertical_default"
    # Pre-fork: composition is null.
    assert body["sources"]["composition"] is None


def test_resolve_unknown_panel_key_404(client, ctx):
    rv = client.get(
        f"{API_ROOT}/resolve",
        params={"panel_key": "nonexistent"},
        headers=_platform_headers(ctx),
    )
    assert rv.status_code == 404


def test_create_validation_422_on_bad_pages(client, ctx):
    r = client.post(
        f"{API_ROOT}/templates",
        headers=_platform_headers(ctx),
        json={
            "scope": "platform_default",
            "panel_key": "bad",
            "display_name": "Bad",
            "pages": [
                {
                    "page_id": "p1",
                    "name": "P1",
                    "rows": [
                        {
                            "row_id": "r0",
                            "column_count": 12,
                            "placements": [
                                {
                                    "placement_id": "x",
                                    "component_kind": "button",
                                    "component_name": "go",
                                    "starting_column": 8,
                                    "column_span": 10,  # 8+10 > 12
                                }
                            ],
                        }
                    ],
                }
            ],
            "canvas_config": {},
        },
    )
    assert r.status_code == 422


def test_create_scope_mismatch_422(client, ctx):
    r = client.post(
        f"{API_ROOT}/templates",
        headers=_platform_headers(ctx),
        json={
            "scope": "platform_default",
            "vertical": "funeral_home",  # invalid for platform_default
            "panel_key": "bad",
            "display_name": "Bad",
            "pages": [],
            "canvas_config": {},
        },
    )
    assert r.status_code == 422


def test_reset_page_endpoint(client, ctx):
    # Seed a template w/ two pages + tenant composition w/ overrides on both.
    pages = [
        _quick_actions_page(),
        {
            "page_id": "dispatch",
            "name": "Dispatch",
            "rows": [
                {
                    "row_id": "r0",
                    "column_count": 12,
                    "row_height": "auto",
                    "column_widths": None,
                    "nested_rows": None,
                    "placements": [
                        {
                            "placement_id": "btn-cement",
                            "component_kind": "button",
                            "component_name": "trigger-cement-order-workflow",
                            "starting_column": 0,
                            "column_span": 12,
                            "prop_overrides": {},
                            "display_config": {},
                        }
                    ],
                }
            ],
            "canvas_config": {},
        },
    ]
    r = client.post(
        f"{API_ROOT}/templates",
        headers=_platform_headers(ctx),
        json={
            "scope": "platform_default",
            "panel_key": "default",
            "display_name": "Platform default",
            "pages": pages,
            "canvas_config": {},
        },
    )
    tid = r.json()["id"]
    up = client.post(
        f"{API_ROOT}/compositions",
        headers=_tenant_headers(ctx),
        json={
            "tenant_id": ctx["company_id"],
            "template_id": tid,
            "deltas": {
                "page_overrides": {
                    "quick-actions": {"hidden_placement_ids": ["btn-pulse"]},
                    "dispatch": {"hidden_placement_ids": ["btn-cement"]},
                }
            },
        },
    )
    cid = up.json()["id"]
    # Reset the dispatch page override.
    rp = client.post(
        f"{API_ROOT}/compositions/{cid}/reset-page/dispatch",
        headers=_tenant_headers(ctx),
    )
    assert rp.status_code == 200, rp.text
    body = rp.json()
    assert "dispatch" not in body["deltas"]["page_overrides"]
    assert "quick-actions" in body["deltas"]["page_overrides"]
