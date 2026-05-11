"""Phase R-6.2a — Intake adapter API endpoint coverage.

Public endpoints + admin CRUD. Tenant isolation verified via
cross-tenant 404 + tenant-scope admin endpoints.
"""

from __future__ import annotations

import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, require_admin
from app.api.routes.intake_adapters import router
from app.database import get_db
from app.models.intake_file_configuration import IntakeFileConfiguration
from app.models.intake_form_configuration import IntakeFormConfiguration
from app.services.intake import resolve_form_config
from tests._classification_fixtures import (  # noqa: F401
    admin_user,
    db,
    tenant_pair,
)


def _make_client(test_db, current_user=None):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/intake-adapters")

    def override_db():
        yield test_db

    app.dependency_overrides[get_db] = override_db
    if current_user is not None:
        app.dependency_overrides[get_current_user] = lambda: current_user
        app.dependency_overrides[require_admin] = lambda: current_user
    return TestClient(app)


# ── Public form endpoints ───────────────────────────────────────────


def test_get_form_config_public_unknown_returns_404(db):
    client = _make_client(db)
    r = client.get(
        "/api/v1/intake-adapters/forms/unknown-tenant/unknown-form"
    )
    assert r.status_code == 404


def test_get_form_config_public_returns_seeded_funeral_form(db, tenant_pair):
    a, _ = tenant_pair
    a.vertical = "funeral_home"
    db.commit()
    client = _make_client(db)
    r = client.get(
        f"/api/v1/intake-adapters/forms/{a.slug}/personalization-request"
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["slug"] == "personalization-request"
    assert "form_schema" in data
    assert "fields" in data["form_schema"]


def test_submit_form_public_persists_submission(db, tenant_pair, monkeypatch):
    a, _ = tenant_pair
    a.vertical = "funeral_home"
    db.commit()

    # Stub cascade.
    from app.services.classification import dispatch as dispatch_mod

    monkeypatch.setattr(
        dispatch_mod,
        "classify_and_fire_form",
        lambda db, *, submission, config: {"tier": None},
        raising=True,
    )

    client = _make_client(db)
    body = {
        "submitted_data": {
            "deceased_name": "John Smith",
            "family_contact_email": "mary@hopkins.example.com",
            "relationship_to_deceased": "spouse",
            "preferred_personalization": "Loved gardening.",
            "family_contact_name": "Mary Hopkins",
        }
    }
    r = client.post(
        f"/api/v1/intake-adapters/forms/{a.slug}/personalization-request/submit",
        json=body,
    )
    assert r.status_code == 201, r.text
    payload = r.json()
    assert payload["submission_id"]
    assert payload["success_message"]


def test_submit_form_public_validation_error_400(db, tenant_pair):
    a, _ = tenant_pair
    a.vertical = "funeral_home"
    db.commit()
    client = _make_client(db)
    body = {
        "submitted_data": {
            # Missing required fields.
            "deceased_name": "John Smith",
        }
    }
    r = client.post(
        f"/api/v1/intake-adapters/forms/{a.slug}/personalization-request/submit",
        json=body,
    )
    assert r.status_code == 400


def test_submit_form_public_unknown_tenant_404(db):
    client = _make_client(db)
    r = client.post(
        "/api/v1/intake-adapters/forms/unknown/unknown/submit",
        json={"submitted_data": {}},
    )
    assert r.status_code == 404


# ── Public file endpoints ───────────────────────────────────────────


def test_get_file_config_public_returns_seeded(db, tenant_pair):
    a, _ = tenant_pair
    a.vertical = "funeral_home"
    db.commit()
    client = _make_client(db)
    r = client.get(
        f"/api/v1/intake-adapters/uploads/{a.slug}/death-certificate"
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["slug"] == "death-certificate"
    assert "application/pdf" in data["allowed_content_types"]
    assert data["max_file_size_bytes"] == 10485760


def test_presign_upload_public_happy_path(db, tenant_pair, monkeypatch):
    a, _ = tenant_pair
    a.vertical = "funeral_home"
    db.commit()

    from app.services import legacy_r2_client

    def _fake_presign(r2_key, *, content_type, expires_in, max_size_bytes=None):
        return {
            "url": f"https://r2.test/{r2_key}",
            "method": "PUT",
            "headers": {"Content-Type": content_type},
            "key": r2_key,
        }

    monkeypatch.setattr(
        legacy_r2_client,
        "generate_presigned_upload_url",
        _fake_presign,
        raising=True,
    )

    client = _make_client(db)
    r = client.post(
        f"/api/v1/intake-adapters/uploads/{a.slug}/death-certificate/presign",
        json={
            "original_filename": "smith.pdf",
            "content_type": "application/pdf",
            "size_bytes": 500_000,
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["upload_id"]
    assert data["url"].startswith("https://r2.test/")


def test_presign_rejects_disallowed_type_400(db, tenant_pair):
    a, _ = tenant_pair
    a.vertical = "funeral_home"
    db.commit()
    client = _make_client(db)
    r = client.post(
        f"/api/v1/intake-adapters/uploads/{a.slug}/death-certificate/presign",
        json={
            "original_filename": "evil.exe",
            "content_type": "application/x-msdownload",
            "size_bytes": 1000,
        },
    )
    assert r.status_code == 400


def test_complete_upload_public_persists(db, tenant_pair, monkeypatch):
    a, _ = tenant_pair
    a.vertical = "funeral_home"
    db.commit()

    from app.services.classification import dispatch as dispatch_mod

    monkeypatch.setattr(
        dispatch_mod,
        "classify_and_fire_file",
        lambda db, *, upload, config: {"tier": None},
        raising=True,
    )

    client = _make_client(db)
    canonical_key = (
        f"tenants/{a.id}/intake/death-certificate/"
        f"{uuid.uuid4()}/smith.pdf"
    )
    r = client.post(
        f"/api/v1/intake-adapters/uploads/{a.slug}/death-certificate/complete",
        json={
            "r2_key": canonical_key,
            "original_filename": "smith.pdf",
            "content_type": "application/pdf",
            "size_bytes": 500_000,
            "uploader_metadata": {"uploader_email": "mary@hopkins.example.com"},
        },
    )
    assert r.status_code == 201, r.text
    payload = r.json()
    assert payload["upload_id"]


# ── Admin form CRUD ─────────────────────────────────────────────────


def test_admin_list_form_configurations_empty(db, admin_user):
    client = _make_client(db, admin_user)
    r = client.get("/api/v1/intake-adapters/admin/form-configurations")
    assert r.status_code == 200
    data = r.json()
    assert data["tenant_overrides"] == []


def test_admin_create_form_configuration(db, admin_user):
    client = _make_client(db, admin_user)
    body = {
        "name": "Custom form",
        "slug": "custom-form",
        "description": "Tenant-specific form.",
        "form_schema": {"version": "1.0", "fields": []},
    }
    r = client.post(
        "/api/v1/intake-adapters/admin/form-configurations", json=body
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["slug"] == "custom-form"
    assert data["scope"] == "tenant_override"
    assert data["tenant_id"] == admin_user.company_id


def test_admin_update_form_configuration(db, admin_user):
    client = _make_client(db, admin_user)
    r = client.post(
        "/api/v1/intake-adapters/admin/form-configurations",
        json={
            "name": "Custom form",
            "slug": "another-custom",
            "form_schema": {"version": "1.0", "fields": []},
        },
    )
    cfg_id = r.json()["id"]
    r2 = client.patch(
        f"/api/v1/intake-adapters/admin/form-configurations/{cfg_id}",
        json={"name": "Renamed form"},
    )
    assert r2.status_code == 200
    assert r2.json()["name"] == "Renamed form"


def test_admin_delete_form_configuration_soft_deletes(db, admin_user):
    client = _make_client(db, admin_user)
    r = client.post(
        "/api/v1/intake-adapters/admin/form-configurations",
        json={
            "name": "doomed",
            "slug": "doomed-form",
            "form_schema": {"version": "1.0", "fields": []},
        },
    )
    cfg_id = r.json()["id"]
    r2 = client.delete(
        f"/api/v1/intake-adapters/admin/form-configurations/{cfg_id}"
    )
    assert r2.status_code == 204
    # Soft-deleted — still in DB, is_active=False.
    cfg = (
        db.query(IntakeFormConfiguration)
        .filter(IntakeFormConfiguration.id == cfg_id)
        .first()
    )
    assert cfg is not None
    assert cfg.is_active is False


def test_admin_cross_tenant_404(db, admin_user, tenant_pair):
    """Admin in tenant A cannot read/mutate tenant B's configs."""
    a, b = tenant_pair
    other_cfg = IntakeFormConfiguration(
        id=str(uuid.uuid4()),
        tenant_id=b.id,
        vertical=None,
        scope="tenant_override",
        name="Other tenant form",
        slug="other-form",
        form_schema={"version": "1.0", "fields": []},
        is_active=True,
    )
    db.add(other_cfg)
    db.commit()

    client = _make_client(db, admin_user)
    r = client.get(
        f"/api/v1/intake-adapters/admin/form-configurations/{other_cfg.id}"
    )
    assert r.status_code == 404


# ── Admin file CRUD ─────────────────────────────────────────────────


def test_admin_create_file_configuration(db, admin_user):
    client = _make_client(db, admin_user)
    body = {
        "name": "Custom upload",
        "slug": "custom-upload",
        "allowed_content_types": ["application/pdf"],
        "max_file_size_bytes": 5 * 1024 * 1024,
        "max_file_count": 1,
        "metadata_schema": {"version": "1.0", "fields": []},
    }
    r = client.post(
        "/api/v1/intake-adapters/admin/file-configurations", json=body
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["slug"] == "custom-upload"
    assert data["scope"] == "tenant_override"
    assert data["max_file_size_bytes"] == 5 * 1024 * 1024


def test_admin_list_file_configurations_with_inherited(db, admin_user):
    """include_inherited=true returns vertical_default + platform_default
    rows whose slugs aren't overridden by the tenant."""
    # Configure tenant vertical so funeral_home seeds inherit.
    admin_tenant_id = admin_user.company_id
    from app.models.company import Company

    tenant = (
        db.query(Company).filter(Company.id == admin_tenant_id).first()
    )
    tenant.vertical = "funeral_home"
    db.commit()

    client = _make_client(db, admin_user)
    r = client.get(
        "/api/v1/intake-adapters/admin/file-configurations?include_inherited=true"
    )
    assert r.status_code == 200, r.text
    data = r.json()
    inherited_slugs = {row["slug"] for row in data["inherited"]}
    # Should include both seeded vertical_default funeral_home files.
    assert "death-certificate" in inherited_slugs
    assert "personalization-documents" in inherited_slugs


def test_admin_endpoints_require_auth(db):
    """Unauth client gets 401/403 on admin routes."""
    client = _make_client(db)
    r = client.get("/api/v1/intake-adapters/admin/form-configurations")
    assert r.status_code in (401, 403, 422)
