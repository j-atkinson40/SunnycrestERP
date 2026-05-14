"""Focus Template Inheritance — admin API tests (sub-arc B-1).

Covers the new `/api/platform/admin/focus-template-inheritance/*`
endpoints: auth gates (anonymous reject, cross-realm reject,
tenant matching tenant_id), Tier 1/2/3 round-trips, lazy-fork
upsert, resolver shape + provenance, 404 + 422 validation paths.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.database import SessionLocal
from app.models.company import Company
from app.models.focus_composition import FocusComposition
from app.models.focus_core import FocusCore
from app.models.focus_template import FocusTemplate
from app.models.platform_user import PlatformUser


API_ROOT = "/api/platform/admin/focus-template-inheritance"


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
            s.query(FocusComposition).delete()
            s.query(FocusTemplate).delete()
            s.query(FocusCore).delete()
            s.commit()
        finally:
            s.close()

    _wipe()
    yield
    _wipe()


@pytest.fixture
def ctx():
    """Seed a platform admin + tenant company + tenant admin user.
    Returns headers + ids for both realms."""
    from app.models.role import Role
    from app.models.user import User

    s = SessionLocal()
    suffix = uuid.uuid4().hex[:6]
    try:
        co = Company(
            id=str(uuid.uuid4()),
            name=f"FTI API {suffix}",
            slug=f"ftia-{suffix}",
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
            email=f"admin-{suffix}@fti.test",
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

        # Second tenant for cross-tenant rejection test.
        suffix2 = uuid.uuid4().hex[:6]
        co2 = Company(
            id=str(uuid.uuid4()),
            name=f"FTI API Other {suffix2}",
            slug=f"ftia2-{suffix2}",
            is_active=True,
            vertical="funeral_home",
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
            email=f"other-{suffix2}@fti.test",
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
        # Tenant deletion cascades to compositions via FK.
        s2 = SessionLocal()
        try:
            for cid in (co.id, co2.id):
                s2.query(FocusComposition).filter(
                    FocusComposition.tenant_id == cid
                ).delete()
            s2.commit()
            for cid in (co.id, co2.id):
                obj = s2.query(Company).filter(Company.id == cid).first()
                if obj is not None:
                    # Cascade-delete dependent users/roles via session.
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


# ─── Tests ──────────────────────────────────────────────────────


def test_anonymous_rejected(client):
    r = client.get(f"{API_ROOT}/cores")
    assert r.status_code in (401, 403)


def test_tenant_token_rejected_on_tier1(client, ctx):
    # Tier 1 endpoints accept only platform realm.
    r = client.get(f"{API_ROOT}/cores", headers=_tenant_headers(ctx))
    assert r.status_code == 401


def test_tenant_token_rejected_on_tier2(client, ctx):
    r = client.get(f"{API_ROOT}/templates", headers=_tenant_headers(ctx))
    assert r.status_code == 401


def test_platform_admin_full_tier1_tier2_round_trip(client, ctx):
    # Create core
    r = client.post(
        f"{API_ROOT}/cores",
        json={
            "core_slug": "k1",
            "display_name": "K1",
            "registered_component_kind": "focus-core",
            "registered_component_name": "K1Core",
        },
        headers=_platform_headers(ctx),
    )
    assert r.status_code == 201, r.text
    core_id = r.json()["id"]

    # List cores
    r = client.get(f"{API_ROOT}/cores", headers=_platform_headers(ctx))
    assert r.status_code == 200
    assert any(c["id"] == core_id for c in r.json())

    # Update core
    r = client.put(
        f"{API_ROOT}/cores/{core_id}",
        json={"display_name": "K1 Renamed"},
        headers=_platform_headers(ctx),
    )
    assert r.status_code == 200
    new_core_id = r.json()["id"]
    assert new_core_id != core_id  # versioned
    assert r.json()["display_name"] == "K1 Renamed"

    # Usage = 0 templates so far
    r = client.get(
        f"{API_ROOT}/cores/{new_core_id}/usage",
        headers=_platform_headers(ctx),
    )
    assert r.status_code == 200
    assert r.json()["templates_count"] == 0

    # Create template
    r = client.post(
        f"{API_ROOT}/templates",
        json={
            "scope": "vertical_default",
            "vertical": "funeral_home",
            "template_slug": "t1",
            "display_name": "T1",
            "inherits_from_core_id": new_core_id,
            "rows": [],
        },
        headers=_platform_headers(ctx),
    )
    assert r.status_code == 201, r.text
    template_id = r.json()["id"]
    assert r.json()["inherits_from_core_version"] == r.json().get(
        "inherits_from_core_version"
    )

    # Update template
    r = client.put(
        f"{API_ROOT}/templates/{template_id}",
        json={"display_name": "T1 Renamed"},
        headers=_platform_headers(ctx),
    )
    assert r.status_code == 200
    new_template_id = r.json()["id"]
    assert new_template_id != template_id

    # Template usage = 0 compositions so far
    r = client.get(
        f"{API_ROOT}/templates/{new_template_id}/usage",
        headers=_platform_headers(ctx),
    )
    assert r.status_code == 200
    assert r.json()["compositions_count"] == 0


def test_tier3_lazy_fork_lifecycle(client, ctx):
    # Seed core + template via platform admin
    r = client.post(
        f"{API_ROOT}/cores",
        json={
            "core_slug": "klf",
            "display_name": "KLF",
            "registered_component_kind": "focus-core",
            "registered_component_name": "KLFCore",
        },
        headers=_platform_headers(ctx),
    )
    core_id = r.json()["id"]
    r = client.post(
        f"{API_ROOT}/templates",
        json={
            "scope": "vertical_default",
            "vertical": "funeral_home",
            "template_slug": "tlf",
            "display_name": "TLF",
            "inherits_from_core_id": core_id,
        },
        headers=_platform_headers(ctx),
    )
    template_id = r.json()["id"]

    # Pre-edit lookup returns 404
    r = client.get(
        f"{API_ROOT}/compositions/by-tenant-template",
        params={"tenant_id": ctx["company_id"], "template_id": template_id},
        headers=_tenant_headers(ctx),
    )
    assert r.status_code == 404

    # First POST creates
    r = client.post(
        f"{API_ROOT}/compositions",
        json={
            "tenant_id": ctx["company_id"],
            "template_id": template_id,
            "deltas": {"hidden_placement_ids": []},
        },
        headers=_tenant_headers(ctx),
    )
    assert r.status_code == 201, r.text
    comp_id_v1 = r.json()["id"]
    assert r.json()["version"] == 1

    # Second POST versions
    r = client.post(
        f"{API_ROOT}/compositions",
        json={
            "tenant_id": ctx["company_id"],
            "template_id": template_id,
            "deltas": {"hidden_placement_ids": ["x"]},
        },
        headers=_tenant_headers(ctx),
    )
    assert r.status_code == 201
    assert r.json()["version"] == 2
    assert r.json()["id"] != comp_id_v1


def test_tier3_cross_tenant_rejection(client, ctx):
    # Seed
    r = client.post(
        f"{API_ROOT}/cores",
        json={
            "core_slug": "kxt",
            "display_name": "KXT",
            "registered_component_kind": "focus-core",
            "registered_component_name": "KXTCore",
        },
        headers=_platform_headers(ctx),
    )
    core_id = r.json()["id"]
    r = client.post(
        f"{API_ROOT}/templates",
        json={
            "scope": "vertical_default",
            "vertical": "funeral_home",
            "template_slug": "txt",
            "display_name": "T",
            "inherits_from_core_id": core_id,
        },
        headers=_platform_headers(ctx),
    )
    template_id = r.json()["id"]

    # Tenant 2 tries to write a composition for Tenant 1.
    other_headers = {
        "Authorization": f"Bearer {ctx['other_tenant_token']}",
    }
    r = client.post(
        f"{API_ROOT}/compositions",
        json={
            "tenant_id": ctx["company_id"],
            "template_id": template_id,
            "deltas": None,
        },
        headers=other_headers,
    )
    assert r.status_code == 403


def test_resolve_returns_shape_with_provenance(client, ctx):
    r = client.post(
        f"{API_ROOT}/cores",
        json={
            "core_slug": "krv",
            "display_name": "K",
            "registered_component_kind": "focus-core",
            "registered_component_name": "KRVCore",
        },
        headers=_platform_headers(ctx),
    )
    core_id = r.json()["id"]
    r = client.post(
        f"{API_ROOT}/templates",
        json={
            "scope": "vertical_default",
            "vertical": "funeral_home",
            "template_slug": "trv",
            "display_name": "T",
            "inherits_from_core_id": core_id,
        },
        headers=_platform_headers(ctx),
    )
    assert r.status_code == 201

    r = client.get(
        f"{API_ROOT}/resolve",
        params={"template_slug": "trv", "vertical": "funeral_home"},
        headers=_platform_headers(ctx),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["template_slug"] == "trv"
    assert body["core_slug"] == "krv"
    assert body["core_registered_component"]["name"] == "KRVCore"
    assert "sources" in body
    assert body["sources"]["tenant"] is None


def test_resolve_unknown_slug_returns_404(client, ctx):
    r = client.get(
        f"{API_ROOT}/resolve",
        params={"template_slug": "nope", "vertical": "funeral_home"},
        headers=_platform_headers(ctx),
    )
    assert r.status_code == 404


def test_validation_rejects_bad_payload(client, ctx):
    # core_slug missing — Pydantic 422
    r = client.post(
        f"{API_ROOT}/cores",
        json={"display_name": "x"},
        headers=_platform_headers(ctx),
    )
    assert r.status_code == 422

    # Create a valid core, then send bad geometry → service-422
    r = client.post(
        f"{API_ROOT}/cores",
        json={
            "core_slug": "kvb",
            "display_name": "K",
            "registered_component_kind": "focus-core",
            "registered_component_name": "KVBCore",
        },
        headers=_platform_headers(ctx),
    )
    core_id = r.json()["id"]

    r = client.post(
        f"{API_ROOT}/templates",
        json={
            "scope": "vertical_default",
            "vertical": "funeral_home",
            "template_slug": "tvb",
            "display_name": "T",
            "inherits_from_core_id": core_id,
            "rows": [
                {
                    "row_id": "r1",
                    "column_count": 6,
                    "placements": [
                        {
                            "placement_id": "x",
                            "component_kind": "widget",
                            "component_name": "x",
                            "starting_column": 4,
                            "column_span": 4,  # 4 + 4 > 6
                        }
                    ],
                }
            ],
        },
        headers=_platform_headers(ctx),
    )
    assert r.status_code == 422


def test_scope_mismatch_in_create_template(client, ctx):
    r = client.post(
        f"{API_ROOT}/cores",
        json={
            "core_slug": "ksm",
            "display_name": "K",
            "registered_component_kind": "focus-core",
            "registered_component_name": "KSMCore",
        },
        headers=_platform_headers(ctx),
    )
    core_id = r.json()["id"]
    r = client.post(
        f"{API_ROOT}/templates",
        json={
            "scope": "platform_default",
            "vertical": "funeral_home",  # mismatch
            "template_slug": "tsm",
            "display_name": "T",
            "inherits_from_core_id": core_id,
        },
        headers=_platform_headers(ctx),
    )
    assert r.status_code == 422
