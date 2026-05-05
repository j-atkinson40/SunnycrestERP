"""Personalization Studio Phase 1D — Workshop template-type registration +
per-tenant Tune mode customization tests.

Per Phase 1D build prompt closing standards: covers
- Workshop template-type registration at canonical Workshop substrate
- Per-tenant Tune mode storage substrate consumption
- Service layer Tune mode operations (get + update)
- 2-endpoint API surface (GET + PATCH) + admin gating
- Tune mode boundary discipline (canonical 4-options vocabulary
  enforcement) + Anti-pattern guards (9 + 4 + 8)
- Pattern-establisher discipline for Step 2 Workshop registration
"""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.database import SessionLocal
from app.main import app
from app.models import Company, Role, User
from app.services.workshop import registry as workshop_registry
from app.services.workshop import tenant_config as workshop_tenant_config
from app.services.workshop.registry import (
    CANONICAL_AUTHORING_CONTEXTS,
    CANONICAL_TUNE_DIMENSIONS_BURIAL_VAULT,
    TemplateTypeDescriptor,
    TUNE_DIMENSION_DISPLAY_LABELS,
    TUNE_DIMENSION_EMBLEM_CATALOG,
    TUNE_DIMENSION_FONT_CATALOG,
    TUNE_DIMENSION_LEGACY_PRINT_CATALOG,
)
from app.services.workshop.tenant_config import (
    DEFAULT_EMBLEM_CATALOG,
    DEFAULT_FONT_CATALOG,
    DEFAULT_LEGACY_PRINT_CATALOG,
    WorkshopTuneModeBoundaryViolation,
    WorkshopTuneModeNotFound,
)


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


def _make_tenant(db_session, vertical="manufacturing"):
    co = Company(
        id=str(uuid.uuid4()),
        name=f"P1D-{uuid.uuid4().hex[:8]}",
        slug=f"p1d{uuid.uuid4().hex[:8]}",
        vertical=vertical,
    )
    db_session.add(co)
    db_session.flush()
    return co


def _make_admin_user(db_session, tenant):
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
        email=f"u-{uuid.uuid4().hex[:8]}@p1d.test",
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


def _make_non_admin_user(db_session, tenant):
    role = Role(
        id=str(uuid.uuid4()),
        company_id=tenant.id,
        name="Office",
        slug="office",
        is_system=True,
    )
    db_session.add(role)
    db_session.flush()
    user = User(
        id=str(uuid.uuid4()),
        email=f"u-{uuid.uuid4().hex[:8]}@p1d.test",
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


# ─────────────────────────────────────────────────────────────────────
# 1. Workshop template-type registry — Phase 1D pattern-establisher
# ─────────────────────────────────────────────────────────────────────


class TestWorkshopRegistry:
    def test_burial_vault_registered_at_seed(self):
        descriptor = workshop_registry.get_template_type(
            "burial_vault_personalization_studio"
        )
        assert descriptor is not None
        assert descriptor.template_type == "burial_vault_personalization_studio"
        assert descriptor.display_name == "Burial Vault Personalization Studio"

    def test_burial_vault_applicable_verticals(self):
        descriptor = workshop_registry.get_template_type(
            "burial_vault_personalization_studio"
        )
        # Phase 1D: FH primary; mfg surfaces via cross-tenant share.
        assert "funeral_home" in descriptor.applicable_verticals
        assert "manufacturing" in descriptor.applicable_verticals

    def test_burial_vault_applicable_authoring_contexts(self):
        descriptor = workshop_registry.get_template_type(
            "burial_vault_personalization_studio"
        )
        # All 3 canonical authoring contexts permitted per Q3.
        assert set(descriptor.applicable_authoring_contexts) == {
            "funeral_home_with_family",
            "manufacturer_without_family",
            "manufacturer_from_fh_share",
        }

    def test_burial_vault_tune_mode_dimensions(self):
        descriptor = workshop_registry.get_template_type(
            "burial_vault_personalization_studio"
        )
        assert set(descriptor.tune_mode_dimensions) == set(
            CANONICAL_TUNE_DIMENSIONS_BURIAL_VAULT
        )

    def test_burial_vault_empty_canvas_factory_key(self):
        descriptor = workshop_registry.get_template_type(
            "burial_vault_personalization_studio"
        )
        # Decouples registry from instance_service _empty_canvas_state
        # factory; consumers resolve via key.
        assert (
            descriptor.empty_canvas_state_factory_key
            == "burial_vault_personalization_studio"
        )

    def test_list_template_types_returns_burial_vault(self):
        descriptors = workshop_registry.list_template_types()
        keys = {d.template_type for d in descriptors}
        assert "burial_vault_personalization_studio" in keys

    def test_list_template_types_filtered_by_vertical(self):
        fh_descriptors = workshop_registry.list_template_types(
            vertical="funeral_home"
        )
        keys = {d.template_type for d in fh_descriptors}
        assert "burial_vault_personalization_studio" in keys

        # Cross-vertical filter excludes templates that don't list the
        # vertical AND don't include "*".
        crematory_descriptors = workshop_registry.list_template_types(
            vertical="crematory"
        )
        crematory_keys = {d.template_type for d in crematory_descriptors}
        assert "burial_vault_personalization_studio" not in crematory_keys

    def test_register_template_type_validates_authoring_contexts(self):
        with pytest.raises(ValueError, match="canonical"):
            workshop_registry.register_template_type(
                TemplateTypeDescriptor(
                    template_type="bogus",
                    display_name="Bogus",
                    description="",
                    applicable_authoring_contexts=["bogus_context"],
                )
            )

    def test_register_template_type_replacement(self):
        """Registry permits replacement — extensions/test code can
        override core registrations (vault.hub_registry pattern)."""
        workshop_registry.register_template_type(
            TemplateTypeDescriptor(
                template_type="test_template",
                display_name="Test 1",
                description="first",
            )
        )
        workshop_registry.register_template_type(
            TemplateTypeDescriptor(
                template_type="test_template",
                display_name="Test 2",
                description="replacement",
            )
        )
        d = workshop_registry.get_template_type("test_template")
        assert d.display_name == "Test 2"
        # Cleanup: remove the test entry to avoid leaking into other tests.
        workshop_registry._registry.pop("test_template", None)


# ─────────────────────────────────────────────────────────────────────
# 2. Per-tenant Tune mode read substrate
# ─────────────────────────────────────────────────────────────────────


class TestGetTenantPersonalizationConfig:
    def test_default_config_no_overrides(self, db_session):
        tenant = _make_tenant(db_session)
        db_session.commit()

        config = workshop_tenant_config.get_tenant_personalization_config(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
        )
        # Display labels: canonical defaults.
        assert config["display_labels"]["vinyl"] == "Vinyl"
        assert config["display_labels"]["physical_nameplate"] == "Nameplate"
        # Catalogs: canonical defaults.
        assert config["emblem_catalog"] == list(DEFAULT_EMBLEM_CATALOG)
        assert config["font_catalog"] == list(DEFAULT_FONT_CATALOG)
        assert config["legacy_print_catalog"] == list(DEFAULT_LEGACY_PRINT_CATALOG)
        # defaults sub-dict surfaces alongside.
        assert config["defaults"]["display_labels"]["vinyl"] == "Vinyl"

    def test_wilbert_tenant_lifes_reflections_override(self, db_session):
        """Q1 r74 canonical example — Wilbert tenant overrides vinyl
        display label to 'Life's Reflections'."""
        tenant = _make_tenant(db_session)
        tenant.settings_json = json.dumps({
            "personalization_display_labels": {"vinyl": "Life's Reflections"},
        })
        db_session.commit()

        config = workshop_tenant_config.get_tenant_personalization_config(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
        )
        assert config["display_labels"]["vinyl"] == "Life's Reflections"
        # Other option types default.
        assert config["display_labels"]["physical_nameplate"] == "Nameplate"

    def test_subset_emblem_catalog_override(self, db_session):
        tenant = _make_tenant(db_session)
        tenant.settings_json = json.dumps({
            "workshop": {
                "burial_vault_personalization_studio": {
                    "emblem_catalog": ["rose", "cross"],
                }
            }
        })
        db_session.commit()

        config = workshop_tenant_config.get_tenant_personalization_config(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
        )
        assert config["emblem_catalog"] == ["rose", "cross"]
        # Other catalogs default.
        assert config["font_catalog"] == list(DEFAULT_FONT_CATALOG)

    def test_unknown_template_type_raises_404(self, db_session):
        tenant = _make_tenant(db_session)
        db_session.commit()
        with pytest.raises(WorkshopTuneModeNotFound):
            workshop_tenant_config.get_tenant_personalization_config(
                db_session,
                company_id=tenant.id,
                template_type="bogus_template",
            )

    def test_unknown_company_raises_404(self, db_session):
        with pytest.raises(WorkshopTuneModeNotFound):
            workshop_tenant_config.get_tenant_personalization_config(
                db_session,
                company_id=str(uuid.uuid4()),
                template_type="burial_vault_personalization_studio",
            )


# ─────────────────────────────────────────────────────────────────────
# 3. Per-tenant Tune mode write substrate + boundary discipline
# ─────────────────────────────────────────────────────────────────────


class TestUpdateTenantPersonalizationConfig:
    def test_update_display_labels(self, db_session):
        tenant = _make_tenant(db_session)
        db_session.commit()

        result = workshop_tenant_config.update_tenant_personalization_config(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            updates={"display_labels": {"vinyl": "Life's Reflections"}},
        )
        db_session.commit()
        assert result["display_labels"]["vinyl"] == "Life's Reflections"

        # Verify substrate write at Company.settings_json.
        db_session.refresh(tenant)
        settings = json.loads(tenant.settings_json)
        assert (
            settings["personalization_display_labels"]["vinyl"]
            == "Life's Reflections"
        )

    def test_update_emblem_catalog_subset(self, db_session):
        tenant = _make_tenant(db_session)
        db_session.commit()

        result = workshop_tenant_config.update_tenant_personalization_config(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            updates={"emblem_catalog": ["rose", "cross", "dove"]},
        )
        db_session.commit()
        assert result["emblem_catalog"] == ["rose", "cross", "dove"]

        # Verify substrate at Company.settings_json.workshop[template_type].
        db_session.refresh(tenant)
        settings = json.loads(tenant.settings_json)
        assert settings["workshop"]["burial_vault_personalization_studio"][
            "emblem_catalog"
        ] == ["rose", "cross", "dove"]

    def test_partial_update_preserves_other_dimensions(self, db_session):
        """Partial-update semantics — only present dimensions written."""
        tenant = _make_tenant(db_session)
        db_session.commit()

        # Write emblem_catalog first.
        workshop_tenant_config.update_tenant_personalization_config(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            updates={"emblem_catalog": ["rose"]},
        )
        db_session.commit()

        # Now write font_catalog only — emblem_catalog should persist.
        workshop_tenant_config.update_tenant_personalization_config(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            updates={"font_catalog": ["serif"]},
        )
        db_session.commit()

        config = workshop_tenant_config.get_tenant_personalization_config(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
        )
        assert config["emblem_catalog"] == ["rose"]
        assert config["font_catalog"] == ["serif"]


class TestTuneModeBoundaryDiscipline:
    """§3.26.11.12.19.2 + §2.4.4 Anti-pattern 9 boundary discipline."""

    def test_unknown_dimension_rejected(self, db_session):
        """Anti-pattern 9 guard — only registered Tune mode dimensions
        are writable."""
        tenant = _make_tenant(db_session)
        db_session.commit()
        with pytest.raises(WorkshopTuneModeBoundaryViolation, match="Unknown"):
            workshop_tenant_config.update_tenant_personalization_config(
                db_session,
                company_id=tenant.id,
                template_type="burial_vault_personalization_studio",
                updates={"bogus_dimension": "anything"},
            )

    def test_legacy_vocabulary_display_label_rejected(self, db_session):
        """§3.26.11.12.19.2 vocabulary scope freeze — legacy pre-r74
        vocabulary rejected at write boundary."""
        tenant = _make_tenant(db_session)
        db_session.commit()
        with pytest.raises(WorkshopTuneModeBoundaryViolation):
            workshop_tenant_config.update_tenant_personalization_config(
                db_session,
                company_id=tenant.id,
                template_type="burial_vault_personalization_studio",
                updates={
                    "display_labels": {"lifes_reflections": "Life's Reflections"},
                },
            )

    def test_emblem_outside_canonical_default_rejected(self, db_session):
        """Anti-pattern 9 guard — Tune mode cannot ADD catalog entries."""
        tenant = _make_tenant(db_session)
        db_session.commit()
        with pytest.raises(WorkshopTuneModeBoundaryViolation, match="canonical default"):
            workshop_tenant_config.update_tenant_personalization_config(
                db_session,
                company_id=tenant.id,
                template_type="burial_vault_personalization_studio",
                updates={
                    "emblem_catalog": ["rose", "fictional_emblem_not_in_canon"],
                },
            )

    def test_font_outside_canonical_default_rejected(self, db_session):
        tenant = _make_tenant(db_session)
        db_session.commit()
        with pytest.raises(WorkshopTuneModeBoundaryViolation):
            workshop_tenant_config.update_tenant_personalization_config(
                db_session,
                company_id=tenant.id,
                template_type="burial_vault_personalization_studio",
                updates={"font_catalog": ["arial_black"]},
            )

    def test_legacy_print_outside_canonical_default_rejected(self, db_session):
        tenant = _make_tenant(db_session)
        db_session.commit()
        with pytest.raises(WorkshopTuneModeBoundaryViolation):
            workshop_tenant_config.update_tenant_personalization_config(
                db_session,
                company_id=tenant.id,
                template_type="burial_vault_personalization_studio",
                updates={"legacy_print_catalog": ["Made-Up Print Name"]},
            )

    def test_non_list_catalog_rejected(self, db_session):
        tenant = _make_tenant(db_session)
        db_session.commit()
        with pytest.raises(WorkshopTuneModeBoundaryViolation, match="must be a list"):
            workshop_tenant_config.update_tenant_personalization_config(
                db_session,
                company_id=tenant.id,
                template_type="burial_vault_personalization_studio",
                updates={"emblem_catalog": "rose"},
            )

    def test_non_string_catalog_entry_rejected(self, db_session):
        tenant = _make_tenant(db_session)
        db_session.commit()
        with pytest.raises(WorkshopTuneModeBoundaryViolation, match="must be strings"):
            workshop_tenant_config.update_tenant_personalization_config(
                db_session,
                company_id=tenant.id,
                template_type="burial_vault_personalization_studio",
                updates={"emblem_catalog": [123, 456]},
            )

    def test_empty_catalog_resets_to_default_at_read(self, db_session):
        """Empty list resets to canonical default at read time per
        Tune mode discipline."""
        tenant = _make_tenant(db_session)
        db_session.commit()
        workshop_tenant_config.update_tenant_personalization_config(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            updates={"emblem_catalog": []},
        )
        db_session.commit()
        config = workshop_tenant_config.get_tenant_personalization_config(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
        )
        assert config["emblem_catalog"] == list(DEFAULT_EMBLEM_CATALOG)


# ─────────────────────────────────────────────────────────────────────
# 4. API surface — admin gating + GET + PATCH
# ─────────────────────────────────────────────────────────────────────


class TestWorkshopAPI:
    def test_get_template_types_returns_burial_vault(self, db_session):
        tenant = _make_tenant(db_session)
        user = _make_admin_user(db_session, tenant)
        db_session.commit()
        with TestClient(app) as client:
            r = client.get(
                "/api/v1/workshop/template-types",
                headers=_auth_headers(db_session, user),
            )
        assert r.status_code == 200
        body = r.json()
        keys = [d["template_type"] for d in body]
        assert "burial_vault_personalization_studio" in keys

    def test_get_template_types_filter_by_vertical(self, db_session):
        tenant = _make_tenant(db_session)
        user = _make_admin_user(db_session, tenant)
        db_session.commit()
        with TestClient(app) as client:
            r = client.get(
                "/api/v1/workshop/template-types",
                params={"vertical": "funeral_home"},
                headers=_auth_headers(db_session, user),
            )
        assert r.status_code == 200
        keys = {d["template_type"] for d in r.json()}
        assert "burial_vault_personalization_studio" in keys

    def test_get_tenant_config_returns_resolved_shape(self, db_session):
        tenant = _make_tenant(db_session)
        user = _make_admin_user(db_session, tenant)
        db_session.commit()
        with TestClient(app) as client:
            r = client.get(
                "/api/v1/workshop/personalization-studio/burial_vault_personalization_studio/tenant-config",
                headers=_auth_headers(db_session, user),
            )
        assert r.status_code == 200
        body = r.json()
        assert body["template_type"] == "burial_vault_personalization_studio"
        assert "display_labels" in body
        assert "emblem_catalog" in body
        assert "defaults" in body

    def test_get_tenant_config_admin_gated(self, db_session):
        """Non-admin user receives 403."""
        tenant = _make_tenant(db_session)
        user = _make_non_admin_user(db_session, tenant)
        db_session.commit()
        with TestClient(app) as client:
            r = client.get(
                "/api/v1/workshop/personalization-studio/burial_vault_personalization_studio/tenant-config",
                headers=_auth_headers(db_session, user),
            )
        assert r.status_code == 403

    def test_get_tenant_config_unknown_template_404(self, db_session):
        tenant = _make_tenant(db_session)
        user = _make_admin_user(db_session, tenant)
        db_session.commit()
        with TestClient(app) as client:
            r = client.get(
                "/api/v1/workshop/personalization-studio/bogus_template/tenant-config",
                headers=_auth_headers(db_session, user),
            )
        assert r.status_code == 404

    def test_patch_tenant_config_writes_display_labels(self, db_session):
        tenant = _make_tenant(db_session)
        user = _make_admin_user(db_session, tenant)
        db_session.commit()
        with TestClient(app) as client:
            r = client.patch(
                "/api/v1/workshop/personalization-studio/burial_vault_personalization_studio/tenant-config",
                json={"display_labels": {"vinyl": "Life's Reflections"}},
                headers=_auth_headers(db_session, user),
            )
        assert r.status_code == 200
        body = r.json()
        assert body["display_labels"]["vinyl"] == "Life's Reflections"

    def test_patch_tenant_config_admin_gated(self, db_session):
        tenant = _make_tenant(db_session)
        user = _make_non_admin_user(db_session, tenant)
        db_session.commit()
        with TestClient(app) as client:
            r = client.patch(
                "/api/v1/workshop/personalization-studio/burial_vault_personalization_studio/tenant-config",
                json={"emblem_catalog": ["rose"]},
                headers=_auth_headers(db_session, user),
            )
        assert r.status_code == 403

    def test_patch_tenant_config_boundary_violation_returns_422(self, db_session):
        tenant = _make_tenant(db_session)
        user = _make_admin_user(db_session, tenant)
        db_session.commit()
        with TestClient(app) as client:
            r = client.patch(
                "/api/v1/workshop/personalization-studio/burial_vault_personalization_studio/tenant-config",
                json={"emblem_catalog": ["fictional_not_in_canon"]},
                headers=_auth_headers(db_session, user),
            )
        assert r.status_code == 422
        assert "canonical default" in r.json()["detail"]

    def test_patch_tenant_config_legacy_vocabulary_rejected(self, db_session):
        tenant = _make_tenant(db_session)
        user = _make_admin_user(db_session, tenant)
        db_session.commit()
        with TestClient(app) as client:
            r = client.patch(
                "/api/v1/workshop/personalization-studio/burial_vault_personalization_studio/tenant-config",
                json={
                    "display_labels": {
                        "lifes_reflections": "Life's Reflections",
                    }
                },
                headers=_auth_headers(db_session, user),
            )
        assert r.status_code == 422

    def test_patch_empty_body_no_op_returns_current_config(self, db_session):
        tenant = _make_tenant(db_session)
        user = _make_admin_user(db_session, tenant)
        db_session.commit()
        with TestClient(app) as client:
            r = client.patch(
                "/api/v1/workshop/personalization-studio/burial_vault_personalization_studio/tenant-config",
                json={},
                headers=_auth_headers(db_session, user),
            )
        assert r.status_code == 200

    def test_patch_partial_update_preserves_other_dimensions(self, db_session):
        tenant = _make_tenant(db_session)
        user = _make_admin_user(db_session, tenant)
        db_session.commit()
        headers = _auth_headers(db_session, user)
        with TestClient(app) as client:
            client.patch(
                "/api/v1/workshop/personalization-studio/burial_vault_personalization_studio/tenant-config",
                json={"emblem_catalog": ["rose"]},
                headers=headers,
            )
            r = client.patch(
                "/api/v1/workshop/personalization-studio/burial_vault_personalization_studio/tenant-config",
                json={"font_catalog": ["serif"]},
                headers=headers,
            )
            assert r.status_code == 200
            body = r.json()
            # Both dimensions persist after partial updates.
            assert body["emblem_catalog"] == ["rose"]
            assert body["font_catalog"] == ["serif"]


# ─────────────────────────────────────────────────────────────────────
# 5. Pattern-establisher discipline — Step 2 inheritance verification
# ─────────────────────────────────────────────────────────────────────


class TestPatternEstablisherDiscipline:
    def test_registry_extension_point_for_step2(self):
        """Step 2 registers urn_vault_personalization_studio via
        the same register_template_type API. Verify the API permits
        this without code changes to registry.py."""

        # Register a Step-2-shape entry.
        step2_marker = "urn_vault_personalization_studio_test_marker"
        try:
            workshop_registry.register_template_type(
                TemplateTypeDescriptor(
                    template_type=step2_marker,
                    display_name="Urn Vault Personalization Studio (test)",
                    description="Step 2 test marker",
                    applicable_verticals=["funeral_home", "manufacturing"],
                    applicable_authoring_contexts=list(
                        CANONICAL_AUTHORING_CONTEXTS
                    ),
                    empty_canvas_state_factory_key=step2_marker,
                    tune_mode_dimensions=[
                        TUNE_DIMENSION_DISPLAY_LABELS,
                        TUNE_DIMENSION_EMBLEM_CATALOG,
                        TUNE_DIMENSION_FONT_CATALOG,
                    ],
                    sort_order=20,
                )
            )
            d = workshop_registry.get_template_type(step2_marker)
            assert d.template_type == step2_marker
            # Phase 1D's burial_vault remains registered alongside.
            phase_1d = workshop_registry.get_template_type(
                "burial_vault_personalization_studio"
            )
            assert phase_1d is not None
        finally:
            workshop_registry._registry.pop(step2_marker, None)


# ─────────────────────────────────────────────────────────────────────
# 6. Anti-pattern guards — explicit verification at Phase 1D boundary
# ─────────────────────────────────────────────────────────────────────


class TestAntiPatternGuards:
    def test_anti_pattern_9_guard_at_service_substrate(self, db_session):
        """§2.4.4 Anti-pattern 9: Tune mode is parameter overrides
        within canonical 4-options vocabulary. Verify at service
        substrate: cannot introduce new option type via display_labels."""
        tenant = _make_tenant(db_session)
        db_session.commit()
        with pytest.raises(WorkshopTuneModeBoundaryViolation):
            workshop_tenant_config.update_tenant_personalization_config(
                db_session,
                company_id=tenant.id,
                template_type="burial_vault_personalization_studio",
                updates={
                    "display_labels": {"new_option_type": "New Option"},
                },
            )

    def test_anti_pattern_8_guard_no_vertical_specific_dimensions(self):
        """§2.4.4 Anti-pattern 8: Workshop service is canonical
        substrate; per-vertical behavior dispatched via
        applicable_verticals filter, NOT vertical-specific code.
        Verify Tune mode dimension keys carry no vertical specificity."""
        descriptor = workshop_registry.get_template_type(
            "burial_vault_personalization_studio"
        )
        for dimension in descriptor.tune_mode_dimensions:
            # No vertical-specific naming in canonical Tune mode dimensions.
            assert "funeral_home" not in dimension
            assert "manufacturing" not in dimension
            assert "fh_" not in dimension
            assert "mfg_" not in dimension

    def test_anti_pattern_4_guard_template_extends_focus_not_new_focus_type(self):
        """§3.26.11.12.16 Anti-pattern 4: Workshop registry holds
        Generation Focus template-type entries; does NOT introduce
        new Focus type. Verify by asserting the registry's
        template_type values match GenerationFocusInstance.template_type
        canonical enumeration."""
        from app.models.generation_focus_instance import (
            CANONICAL_TEMPLATE_TYPES,
        )
        descriptor = workshop_registry.get_template_type(
            "burial_vault_personalization_studio"
        )
        # Phase 1D registered template_type matches Generation Focus
        # canonical template_type at substrate.
        assert descriptor.template_type in CANONICAL_TEMPLATE_TYPES
