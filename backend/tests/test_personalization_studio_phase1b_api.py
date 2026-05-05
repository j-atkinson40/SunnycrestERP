"""Personalization Studio Phase 1B canvas implementation — API endpoint tests.

Per Phase 1B build prompt closing standards: API endpoint tests covering
canvas commit + tenant scoping + lifecycle gates + canonical Document
substrate consumption.

**Canonical-pattern-establisher discipline at API substrate**:
- Tenant-scoped per canonical multi-tenant isolation (cross-tenant
  access returns canonical existence-hiding 404)
- Canonical canvas commit boundary at canonical operator-decision
  per §3.26.11.12.16 Anti-pattern 1
- Canonical Document substrate per D-9 polymorphic substrate
- Canonical 4-options vocabulary post-r74 enforced at API substrate

**Anti-pattern guard tests**:
- Canvas commit on terminal-state instance rejected (canonical lifecycle gate)
- Cross-tenant access returns 404 (canonical existence-hiding)
- Q3 canonical authoring_context ↔ linked_entity_type pairing enforced
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.database import SessionLocal
from app.main import app
from app.models import Company, Role, User
from app.models.canonical_document import DocumentVersion
from app.models.fh_case import FHCase
from app.models.funeral_case import CaseMerchandise, FuneralCase
from app.models.generation_focus_instance import GenerationFocusInstance


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def fake_r2():
    """Mock R2 upload + download with in-memory store."""
    storage: dict[str, bytes] = {}

    def fake_upload(data: bytes, r2_key: str, content_type: str = "application/octet-stream"):
        storage[r2_key] = data
        return f"https://r2.test/{r2_key}"

    def fake_download(r2_key: str) -> bytes:
        return storage[r2_key]

    with (
        patch(
            "app.services.personalization_studio.instance_service.legacy_r2_client.upload_bytes",
            side_effect=fake_upload,
        ),
        patch(
            "app.services.personalization_studio.instance_service.legacy_r2_client.download_bytes",
            side_effect=fake_download,
        ),
    ):
        yield storage


def _make_tenant(db_session, *, vertical="manufacturing", name_prefix="P1B"):
    co = Company(
        id=str(uuid.uuid4()),
        name=f"{name_prefix} {uuid.uuid4().hex[:8]}",
        slug=f"p1b{uuid.uuid4().hex[:8]}",
        vertical=vertical,
    )
    db_session.add(co)
    db_session.flush()
    return co


def _make_user(db_session, tenant):
    role = Role(
        id=str(uuid.uuid4()),
        company_id=tenant.id,
        name="Admin",
        slug="admin",
        is_system=True,
    )
    db_session.add(role)
    db_session.flush()
    user = User(
        id=str(uuid.uuid4()),
        email=f"u-{uuid.uuid4().hex[:8]}@p1b.test",
        hashed_password="x",
        first_name="A",
        last_name="U",
        company_id=tenant.id,
        role_id=role.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _auth_headers(db_session, user) -> dict[str, str]:
    company = db_session.query(Company).filter(Company.id == user.company_id).first()
    token = create_access_token(
        data={"sub": user.id, "company_id": user.company_id}
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Company-Slug": company.slug,
    }


def _canonical_canvas_state() -> dict:
    """Canonical canvas state per Phase 1A canonical-pattern-establisher
    + canonical 4-options vocabulary post-r74."""
    return {
        "schema_version": 1,
        "template_type": "burial_vault_personalization_studio",
        "canvas_layout": {
            "elements": [
                {
                    "id": str(uuid.uuid4()),
                    "element_type": "name_text",
                    "x": 100,
                    "y": 100,
                    "config": {"name_display": "John Smith", "font": "serif"},
                }
            ],
        },
        "vault_product": {
            "vault_product_id": None,
            "vault_product_name": None,
        },
        "emblem_key": None,
        "name_display": "John Smith",
        "font": "serif",
        "birth_date_display": None,
        "death_date_display": None,
        "nameplate_text": None,
        "options": {
            "legacy_print": None,
            "physical_nameplate": None,
            "physical_emblem": None,
            "vinyl": {"symbol": "Cross"},  # canonical post-r74
        },
        "family_approval_status": "not_requested",
    }


# ─────────────────────────────────────────────────────────────────────
# 1. POST /instances — canonical open
# ─────────────────────────────────────────────────────────────────────


class TestOpenInstanceEndpoint:
    def test_post_instances_creates_canonical_instance(
        self, db_session, fake_r2
    ):
        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
        db_session.commit()

        with TestClient(app) as client:
            r = client.post(
                "/api/v1/personalization-studio/instances",
                json={
                    "template_type": "burial_vault_personalization_studio",
                    "authoring_context": "manufacturer_without_family",
                    "linked_entity_id": str(uuid.uuid4()),
                },
                headers=_auth_headers(db_session, user),
            )
        assert r.status_code == 201
        body = r.json()
        assert body["template_type"] == "burial_vault_personalization_studio"
        assert body["authoring_context"] == "manufacturer_without_family"
        assert body["linked_entity_type"] == "sales_order"  # Q3 derived
        assert body["lifecycle_state"] == "active"
        assert body["document_id"] is not None
        # Mfg-vertical canonical: family_approval_status NULL.
        assert body["family_approval_status"] is None

    def test_post_instances_fh_vertical_seeds_family_approval(
        self, db_session, fake_r2
    ):
        tenant = _make_tenant(db_session, vertical="funeral_home")
        user = _make_user(db_session, tenant)
        db_session.commit()

        with TestClient(app) as client:
            r = client.post(
                "/api/v1/personalization-studio/instances",
                json={
                    "template_type": "burial_vault_personalization_studio",
                    "authoring_context": "funeral_home_with_family",
                    "linked_entity_id": str(uuid.uuid4()),
                },
                headers=_auth_headers(db_session, user),
            )
        assert r.status_code == 201
        assert r.json()["family_approval_status"] == "not_requested"
        assert r.json()["linked_entity_type"] == "fh_case"

    def test_post_instances_invalid_authoring_context_rejected(
        self, db_session, fake_r2
    ):
        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
        db_session.commit()

        with TestClient(app) as client:
            r = client.post(
                "/api/v1/personalization-studio/instances",
                json={
                    "template_type": "burial_vault_personalization_studio",
                    "authoring_context": "bogus_context",
                    "linked_entity_id": str(uuid.uuid4()),
                },
                headers=_auth_headers(db_session, user),
            )
        # Pydantic Literal validation → 422.
        assert r.status_code == 422

    def test_post_instances_auth_required(self, db_session, fake_r2):
        with TestClient(app) as client:
            r = client.post(
                "/api/v1/personalization-studio/instances",
                json={
                    "template_type": "burial_vault_personalization_studio",
                    "authoring_context": "manufacturer_without_family",
                    "linked_entity_id": str(uuid.uuid4()),
                },
            )
        assert r.status_code in (401, 403)


# ─────────────────────────────────────────────────────────────────────
# 2. GET /instances/{id} — canonical fetch + tenant scoping
# ─────────────────────────────────────────────────────────────────────


class TestGetInstanceEndpoint:
    def test_get_instance_returns_canonical_metadata(self, db_session, fake_r2):
        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
        # Open instance via service-layer (avoid TestClient overhead).
        from app.services.personalization_studio import instance_service
        instance = instance_service.open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
            opened_by_user_id=user.id,
        )
        db_session.commit()

        with TestClient(app) as client:
            r = client.get(
                f"/api/v1/personalization-studio/instances/{instance.id}",
                headers=_auth_headers(db_session, user),
            )
        assert r.status_code == 200
        assert r.json()["id"] == instance.id

    def test_get_instance_cross_tenant_404(self, db_session, fake_r2):
        """Canonical existence-hiding: cross-tenant access returns 404."""
        tenant_a = _make_tenant(db_session, name_prefix="A")
        tenant_b = _make_tenant(db_session, name_prefix="B")
        user_b = _make_user(db_session, tenant_b)
        # Instance owned by A; B tries to fetch.
        from app.services.personalization_studio import instance_service
        instance = instance_service.open_instance(
            db_session,
            company_id=tenant_a.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
        )
        db_session.commit()

        with TestClient(app) as client:
            r = client.get(
                f"/api/v1/personalization-studio/instances/{instance.id}",
                headers=_auth_headers(db_session, user_b),
            )
        assert r.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# 3. POST /commit-canvas-state — canonical canvas commit boundary
# ─────────────────────────────────────────────────────────────────────


class TestCommitCanvasStateEndpoint:
    def test_post_commit_canvas_state_creates_v1(self, db_session, fake_r2):
        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
        from app.services.personalization_studio import instance_service
        instance = instance_service.open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
            opened_by_user_id=user.id,
        )
        db_session.commit()

        with TestClient(app) as client:
            r = client.post(
                f"/api/v1/personalization-studio/instances/{instance.id}/commit-canvas-state",
                json={"canvas_state": _canonical_canvas_state()},
                headers=_auth_headers(db_session, user),
            )
        assert r.status_code == 200
        body = r.json()
        assert body["version_number"] == 1
        assert "canvas_state_v1.json" in body["storage_key"]
        assert body["document_version_id"] is not None

    def test_post_commit_canvas_state_v2_increments_version(
        self, db_session, fake_r2
    ):
        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
        from app.services.personalization_studio import instance_service
        instance = instance_service.open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
        )
        db_session.commit()

        with TestClient(app) as client:
            r1 = client.post(
                f"/api/v1/personalization-studio/instances/{instance.id}/commit-canvas-state",
                json={"canvas_state": _canonical_canvas_state()},
                headers=_auth_headers(db_session, user),
            )
            assert r1.status_code == 200
            assert r1.json()["version_number"] == 1

            state_v2 = _canonical_canvas_state()
            state_v2["nameplate_text"] = "Updated"
            r2_resp = client.post(
                f"/api/v1/personalization-studio/instances/{instance.id}/commit-canvas-state",
                json={"canvas_state": state_v2},
                headers=_auth_headers(db_session, user),
            )
        assert r2_resp.status_code == 200
        assert r2_resp.json()["version_number"] == 2

        # Canonical D-9 versioning: v1.is_current=False, v2.is_current=True.
        all_versions = (
            db_session.query(DocumentVersion)
            .filter(DocumentVersion.document_id == instance.document_id)
            .order_by(DocumentVersion.version_number)
            .all()
        )
        assert len(all_versions) == 2
        assert all_versions[0].is_current is False
        assert all_versions[1].is_current is True

    def test_post_commit_canvas_state_rejected_on_committed_instance(
        self, db_session, fake_r2
    ):
        """Canonical lifecycle gate: terminal-state instance rejects commit."""
        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
        from app.services.personalization_studio import instance_service
        instance = instance_service.open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
        )
        instance_service.commit_instance(db_session, instance_id=instance.id)
        db_session.commit()

        with TestClient(app) as client:
            r = client.post(
                f"/api/v1/personalization-studio/instances/{instance.id}/commit-canvas-state",
                json={"canvas_state": _canonical_canvas_state()},
                headers=_auth_headers(db_session, user),
            )
        assert r.status_code == 409  # canonical InvalidTransition

    def test_post_commit_canvas_state_cross_tenant_404(self, db_session, fake_r2):
        tenant_a = _make_tenant(db_session, name_prefix="A")
        tenant_b = _make_tenant(db_session, name_prefix="B")
        user_b = _make_user(db_session, tenant_b)
        from app.services.personalization_studio import instance_service
        instance = instance_service.open_instance(
            db_session,
            company_id=tenant_a.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
        )
        db_session.commit()

        with TestClient(app) as client:
            r = client.post(
                f"/api/v1/personalization-studio/instances/{instance.id}/commit-canvas-state",
                json={"canvas_state": _canonical_canvas_state()},
                headers=_auth_headers(db_session, user_b),
            )
        assert r.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# 4. GET /canvas-state — canonical read-side
# ─────────────────────────────────────────────────────────────────────


class TestGetCanvasStateEndpoint:
    def test_get_canvas_state_returns_null_pre_first_commit(
        self, db_session, fake_r2
    ):
        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
        from app.services.personalization_studio import instance_service
        instance = instance_service.open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
        )
        db_session.commit()

        with TestClient(app) as client:
            r = client.get(
                f"/api/v1/personalization-studio/instances/{instance.id}/canvas-state",
                headers=_auth_headers(db_session, user),
            )
        assert r.status_code == 200
        assert r.json()["canvas_state"] is None

    def test_get_canvas_state_round_trips_committed_state(
        self, db_session, fake_r2
    ):
        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
        from app.services.personalization_studio import instance_service
        instance = instance_service.open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
        )
        original_state = _canonical_canvas_state()
        original_state["nameplate_text"] = "Round-trip Test"
        instance_service.commit_canvas_state(
            db_session,
            instance_id=instance.id,
            canvas_state=original_state,
        )
        db_session.commit()

        with TestClient(app) as client:
            r = client.get(
                f"/api/v1/personalization-studio/instances/{instance.id}/canvas-state",
                headers=_auth_headers(db_session, user),
            )
        assert r.status_code == 200
        canvas_state = r.json()["canvas_state"]
        assert canvas_state is not None
        assert canvas_state["nameplate_text"] == "Round-trip Test"
        # Canonical 4-options vocabulary post-r74 preserved through round-trip.
        assert set(canvas_state["options"].keys()) == {
            "legacy_print",
            "physical_nameplate",
            "physical_emblem",
            "vinyl",
        }


# ─────────────────────────────────────────────────────────────────────
# 5. POST /commit + /abandon — canonical lifecycle transitions
# ─────────────────────────────────────────────────────────────────────


class TestLifecycleTransitionEndpoints:
    def test_post_commit_transitions_to_committed(self, db_session, fake_r2):
        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
        from app.services.personalization_studio import instance_service
        instance = instance_service.open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
        )
        db_session.commit()

        with TestClient(app) as client:
            r = client.post(
                f"/api/v1/personalization-studio/instances/{instance.id}/commit",
                headers=_auth_headers(db_session, user),
            )
        assert r.status_code == 200
        body = r.json()
        assert body["lifecycle_state"] == "committed"
        assert body["committed_at"] is not None
        assert body["committed_by_user_id"] == user.id

    def test_post_abandon_transitions_to_abandoned(self, db_session, fake_r2):
        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
        from app.services.personalization_studio import instance_service
        instance = instance_service.open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
        )
        db_session.commit()

        with TestClient(app) as client:
            r = client.post(
                f"/api/v1/personalization-studio/instances/{instance.id}/abandon",
                headers=_auth_headers(db_session, user),
            )
        assert r.status_code == 200
        assert r.json()["lifecycle_state"] == "abandoned"

    def test_double_commit_returns_409(self, db_session, fake_r2):
        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
        from app.services.personalization_studio import instance_service
        instance = instance_service.open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
        )
        instance_service.commit_instance(db_session, instance_id=instance.id)
        db_session.commit()

        with TestClient(app) as client:
            r = client.post(
                f"/api/v1/personalization-studio/instances/{instance.id}/commit",
                headers=_auth_headers(db_session, user),
            )
        assert r.status_code == 409


# ─────────────────────────────────────────────────────────────────────
# 6. GET /instances — canonical query for linked entity
# ─────────────────────────────────────────────────────────────────────


class TestListInstancesEndpoint:
    def test_list_instances_for_linked_entity(self, db_session, fake_r2):
        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
        order_id = str(uuid.uuid4())
        from app.services.personalization_studio import instance_service
        # Two instances for same order.
        instance_service.open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=order_id,
        )
        instance_service.open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=order_id,
        )
        # One unrelated instance.
        instance_service.open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
        )
        db_session.commit()

        with TestClient(app) as client:
            r = client.get(
                "/api/v1/personalization-studio/instances",
                params={
                    "linked_entity_type": "sales_order",
                    "linked_entity_id": order_id,
                },
                headers=_auth_headers(db_session, user),
            )
        assert r.status_code == 200
        results = r.json()
        assert len(results) == 2
        for r_dict in results:
            assert r_dict["linked_entity_id"] == order_id

    def test_list_excludes_other_tenants(self, db_session, fake_r2):
        """Canonical multi-tenant isolation."""
        tenant_a = _make_tenant(db_session, name_prefix="A")
        tenant_b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_user(db_session, tenant_a)
        order_id = str(uuid.uuid4())
        from app.services.personalization_studio import instance_service
        # Instance in tenant B linked to same order_id.
        instance_service.open_instance(
            db_session,
            company_id=tenant_b.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=order_id,
        )
        db_session.commit()

        with TestClient(app) as client:
            r = client.get(
                "/api/v1/personalization-studio/instances",
                params={
                    "linked_entity_type": "sales_order",
                    "linked_entity_id": order_id,
                },
                headers=_auth_headers(db_session, user_a),
            )
        assert r.status_code == 200
        # A sees zero instances despite same order_id existing in B.
        assert r.json() == []


# ─────────────────────────────────────────────────────────────────────
# 7. FH-vertical canonical end-to-end via API — canonical JSONB
#    denormalization to case_merchandise.vault_personalization
# ─────────────────────────────────────────────────────────────────────


class TestFHVerticalEndToEnd:
    def test_fh_vertical_canvas_commit_denormalizes_to_case_merchandise(
        self, db_session, fake_r2
    ):
        tenant = _make_tenant(db_session, vertical="funeral_home")
        user = _make_user(db_session, tenant)

        # Create canonical FuneralCase + CaseMerchandise satellite.
        case = FuneralCase(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            case_number=f"FC-{uuid.uuid4().hex[:6].upper()}",
            status="active",
        )
        db_session.add(case)
        db_session.flush()
        merchandise = CaseMerchandise(
            id=str(uuid.uuid4()),
            case_id=case.id,
            company_id=tenant.id,
        )
        db_session.add(merchandise)
        db_session.commit()

        with TestClient(app) as client:
            # Open canonical instance.
            r_open = client.post(
                "/api/v1/personalization-studio/instances",
                json={
                    "template_type": "burial_vault_personalization_studio",
                    "authoring_context": "funeral_home_with_family",
                    "linked_entity_id": case.id,
                },
                headers=_auth_headers(db_session, user),
            )
            assert r_open.status_code == 201
            instance_id = r_open.json()["id"]

            # Commit canonical canvas state.
            state = _canonical_canvas_state()
            state["nameplate_text"] = "FH End-to-End"
            state["options"]["physical_nameplate"] = {}
            r_commit = client.post(
                f"/api/v1/personalization-studio/instances/{instance_id}/commit-canvas-state",
                json={"canvas_state": state},
                headers=_auth_headers(db_session, user),
            )
        assert r_commit.status_code == 200

        # Canonical FH-vertical denormalization: case_merchandise.vault_personalization
        # JSONB updated post-r74 canonical vocabulary.
        db_session.expire_all()
        merch = (
            db_session.query(CaseMerchandise)
            .filter(CaseMerchandise.case_id == case.id)
            .first()
        )
        assert merch is not None
        assert merch.vault_personalization is not None
        assert merch.vault_personalization["nameplate_text"] == "FH End-to-End"
        # Canonical 4-options vocabulary post-r74 preserved.
        assert set(merch.vault_personalization["options"].keys()) == {
            "legacy_print",
            "physical_nameplate",
            "physical_emblem",
            "vinyl",
        }
        # Legacy pre-r74 vocabulary canonically absent.
        for legacy in ("nameplate", "cover_emblem", "lifes_reflections"):
            assert legacy not in merch.vault_personalization["options"]
