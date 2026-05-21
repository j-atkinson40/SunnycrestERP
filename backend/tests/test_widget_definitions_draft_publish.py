"""Tests for the WB-4a draft + publish API.

Endpoints under test:
  • POST /api/v1/widget-definitions
  • PUT  /api/v1/widget-definitions/{slug}/draft
  • POST /api/v1/widget-definitions/{slug}/publish
  • GET  /api/v1/widget-definitions/{slug}

Per investigation Area 2 (draft-then-publish) + Area 5 (permissive
auto-save; strict publish).
"""

from __future__ import annotations

import uuid
import json
from typing import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    from app.main import app
    return TestClient(app)


def _make_tenant_token(*, vertical: str = "funeral_home") -> dict:
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"WB4a-{suffix}",
            slug=f"wb4a-{suffix}",
            is_active=True,
            vertical=vertical,
            timezone="America/New_York",
        )
        db.add(co)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name="Admin",
            slug="admin",
            is_system=False,
        )
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"u-{suffix}@wb4a.test",
            first_name="W",
            last_name="B",
            hashed_password="x",
            is_active=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        token = create_access_token(
            {"sub": user.id, "company_id": co.id, "realm": "tenant"}
        )
        return {"slug": co.slug, "token": token}
    finally:
        db.close()


def _headers(ctx: dict) -> dict:
    return {
        "Authorization": f"Bearer {ctx['token']}",
        "X-Company-Slug": ctx["slug"],
    }


def _valid_blob() -> dict:
    root = str(uuid.uuid4())
    return {
        "schema_version": 1,
        "root_atom_id": root,
        "atom_tree": {
            root: {
                "atom_id": root,
                "atom_type": "conditional_container",
                "config": {
                    "direction": "column",
                    "gap_token": "sm",
                },
                "children": [],
            }
        },
        "variants": [],
        "bindings_catalog": {},
    }


# ── POST / ─────────────────────────────────────────────────────────────


class TestCreateWidget:
    def test_create_with_defaults(self, client: TestClient):
        ctx = _make_tenant_token()
        r = client.post(
            "/api/v1/widget-definitions",
            json={"title": "Test widget"},
            headers=_headers(ctx),
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["title"] == "Test widget"
        assert body["composition_blob"] is not None
        assert body["composition_blob"]["schema_version"] == 1
        assert body["composition_blob"]["root_atom_id"] in body["composition_blob"]["atom_tree"]
        assert body["composition_version"] == 1
        assert body["published_composition_blob"] is None
        assert body["tier_scope"] == "vertical"

    def test_create_slug_collision_disambiguates(self, client: TestClient):
        ctx = _make_tenant_token()
        unique = f"slug-{uuid.uuid4().hex[:6]}"
        r1 = client.post(
            "/api/v1/widget-definitions",
            json={"title": "A", "slug": unique},
            headers=_headers(ctx),
        )
        assert r1.status_code == 201, r1.text
        assert r1.json()["widget_id"] == unique
        r2 = client.post(
            "/api/v1/widget-definitions",
            json={"title": "B", "slug": unique},
            headers=_headers(ctx),
        )
        assert r2.status_code == 201, r2.text
        # Disambiguated.
        assert r2.json()["widget_id"] == f"{unique}-2"

    def test_create_rejects_bad_tier_scope(self, client: TestClient):
        ctx = _make_tenant_token()
        r = client.post(
            "/api/v1/widget-definitions",
            json={"title": "Bad", "tier_scope": "tenant"},
            headers=_headers(ctx),
        )
        assert r.status_code == 400

    def test_create_requires_auth(self, client: TestClient):
        r = client.post("/api/v1/widget-definitions", json={"title": "x"})
        assert r.status_code in (401, 403)


# ── PUT /{slug}/draft ─────────────────────────────────────────────────


class TestSaveDraft:
    def test_draft_updates_composition_blob(self, client: TestClient):
        ctx = _make_tenant_token()
        r = client.post(
            "/api/v1/widget-definitions",
            json={"title": "Draft test"},
            headers=_headers(ctx),
        )
        slug = r.json()["widget_id"]
        new_blob = _valid_blob()
        new_blob["atom_tree"][new_blob["root_atom_id"]]["config"]["gap_token"] = "lg"

        session_id = str(uuid.uuid4())
        r2 = client.put(
            f"/api/v1/widget-definitions/{slug}/draft",
            json={
                "composition_blob": new_blob,
                "edit_session_id": session_id,
            },
            headers=_headers(ctx),
        )
        assert r2.status_code == 200, r2.text
        body = r2.json()
        # Draft updated.
        root = body["composition_blob"]["root_atom_id"]
        assert (
            body["composition_blob"]["atom_tree"][root]["config"]["gap_token"]
            == "lg"
        )
        # Edit session recorded.
        assert body["last_edit_session_id"] == session_id
        assert body["last_edit_session_at"] is not None

    def test_draft_preserves_published(self, client: TestClient):
        """Saving draft must NOT mutate published_composition_blob."""
        ctx = _make_tenant_token()
        r_create = client.post(
            "/api/v1/widget-definitions",
            json={"title": "Preserve test"},
            headers=_headers(ctx),
        )
        slug = r_create.json()["widget_id"]
        # Publish once so there's a published blob.
        r_pub = client.post(
            f"/api/v1/widget-definitions/{slug}/publish",
            headers=_headers(ctx),
        )
        assert r_pub.status_code == 200, r_pub.text
        published = r_pub.json()["published_composition_blob"]
        assert published is not None

        # Save a new draft with a different shape.
        new_blob = _valid_blob()
        new_blob["atom_tree"][new_blob["root_atom_id"]]["config"]["gap_token"] = "lg"
        r_draft = client.put(
            f"/api/v1/widget-definitions/{slug}/draft",
            json={"composition_blob": new_blob, "edit_session_id": None},
            headers=_headers(ctx),
        )
        assert r_draft.status_code == 200, r_draft.text
        body = r_draft.json()
        # Published unchanged.
        assert body["published_composition_blob"] == published
        # Draft changed.
        assert body["composition_blob"] != published

    def test_draft_permissive_invalid_blob_ok(self, client: TestClient):
        """Permissive — invalid intermediate states must save (Area 5)."""
        ctx = _make_tenant_token()
        r = client.post(
            "/api/v1/widget-definitions",
            json={"title": "Permissive test"},
            headers=_headers(ctx),
        )
        slug = r.json()["widget_id"]
        # Drop a malformed blob — atom_tree refers to a missing atom_id
        # in children. Pydantic structural pass succeeds; validator at
        # publish time would reject. Permissive draft accepts.
        broken = {
            "schema_version": 1,
            "root_atom_id": "ghost",
            "atom_tree": {},
            "variants": [],
            "bindings_catalog": {},
        }
        r2 = client.put(
            f"/api/v1/widget-definitions/{slug}/draft",
            json={"composition_blob": broken, "edit_session_id": None},
            headers=_headers(ctx),
        )
        assert r2.status_code == 200, r2.text

    def test_draft_rejects_non_dict(self, client: TestClient):
        ctx = _make_tenant_token()
        r = client.post(
            "/api/v1/widget-definitions",
            json={"title": "x"},
            headers=_headers(ctx),
        )
        slug = r.json()["widget_id"]
        r2 = client.put(
            f"/api/v1/widget-definitions/{slug}/draft",
            json={"composition_blob": "not a dict", "edit_session_id": None},
            headers=_headers(ctx),
        )
        assert r2.status_code == 400

    def test_draft_404_on_unknown_slug(self, client: TestClient):
        ctx = _make_tenant_token()
        r = client.put(
            "/api/v1/widget-definitions/nonexistent-slug-xyz/draft",
            json={"composition_blob": _valid_blob(), "edit_session_id": None},
            headers=_headers(ctx),
        )
        assert r.status_code == 404


# ── POST /{slug}/publish ──────────────────────────────────────────────


class TestPublish:
    def test_publish_copies_draft_to_published(self, client: TestClient):
        ctx = _make_tenant_token()
        r = client.post(
            "/api/v1/widget-definitions",
            json={"title": "Publish test"},
            headers=_headers(ctx),
        )
        slug = r.json()["widget_id"]
        draft_blob = r.json()["composition_blob"]

        r_pub = client.post(
            f"/api/v1/widget-definitions/{slug}/publish",
            headers=_headers(ctx),
        )
        assert r_pub.status_code == 200, r_pub.text
        body = r_pub.json()
        assert body["published_composition_blob"] == draft_blob

    def test_publish_increments_version(self, client: TestClient):
        ctx = _make_tenant_token()
        r = client.post(
            "/api/v1/widget-definitions",
            json={"title": "Version test"},
            headers=_headers(ctx),
        )
        slug = r.json()["widget_id"]
        assert r.json()["composition_version"] == 1
        r_pub = client.post(
            f"/api/v1/widget-definitions/{slug}/publish",
            headers=_headers(ctx),
        )
        assert r_pub.status_code == 200
        assert r_pub.json()["composition_version"] == 2
        r_pub2 = client.post(
            f"/api/v1/widget-definitions/{slug}/publish",
            headers=_headers(ctx),
        )
        assert r_pub2.status_code == 200
        assert r_pub2.json()["composition_version"] == 3

    def test_publish_rejects_invalid_blob(self, client: TestClient):
        ctx = _make_tenant_token()
        r = client.post(
            "/api/v1/widget-definitions",
            json={"title": "Invalid pub"},
            headers=_headers(ctx),
        )
        slug = r.json()["widget_id"]
        # Save an invalid draft.
        broken = {
            "schema_version": 1,
            "root_atom_id": "ghost-id",
            "atom_tree": {},
            "variants": [],
            "bindings_catalog": {},
        }
        client.put(
            f"/api/v1/widget-definitions/{slug}/draft",
            json={"composition_blob": broken, "edit_session_id": None},
            headers=_headers(ctx),
        )
        r_pub = client.post(
            f"/api/v1/widget-definitions/{slug}/publish",
            headers=_headers(ctx),
        )
        assert r_pub.status_code == 422
        body = r_pub.json()
        assert body["detail"]["code"] == "composition_invalid"
        assert isinstance(body["detail"]["errors"], list)
        assert len(body["detail"]["errors"]) >= 1

    def test_publish_404_on_unknown(self, client: TestClient):
        ctx = _make_tenant_token()
        r = client.post(
            "/api/v1/widget-definitions/missing-xyz/publish",
            headers=_headers(ctx),
        )
        assert r.status_code == 404


# ── GET /{slug} ────────────────────────────────────────────────────────


class TestGetWidget:
    def test_get_returns_full_shape(self, client: TestClient):
        ctx = _make_tenant_token()
        r = client.post(
            "/api/v1/widget-definitions",
            json={"title": "Read test"},
            headers=_headers(ctx),
        )
        slug = r.json()["widget_id"]
        r_get = client.get(
            f"/api/v1/widget-definitions/{slug}",
            headers=_headers(ctx),
        )
        assert r_get.status_code == 200, r_get.text
        body = r_get.json()
        assert body["widget_id"] == slug
        assert "composition_blob" in body
        assert "published_composition_blob" in body
        assert "composition_version" in body
        assert "tier_scope" in body


# ── Existing endpoints unchanged ──────────────────────────────────────


class TestExistingEndpointsUnchanged:
    def test_composed_definitions_includes_published(self, client: TestClient):
        """The WB-3 /widgets/composed-definitions endpoint still works.

        We don't assert it includes published_composition_blob — WB-3
        endpoint shape stays unchanged for backward compat (the new
        endpoint at /widget-definitions/{slug} carries the full shape).
        """
        ctx = _make_tenant_token()
        r = client.get(
            "/api/v1/widgets/composed-definitions",
            headers=_headers(ctx),
        )
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)
