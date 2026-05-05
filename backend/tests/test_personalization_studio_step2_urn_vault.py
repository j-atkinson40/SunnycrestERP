"""Personalization Studio Step 2 — Urn Vault Personalization Studio
substrate-consumption-follower tests.

Per Step 2 build prompt closing standards: tests covering Phase 2A
entity model + Document discriminator extension, Phase 2B Intelligence
prompts + _PROMPT_KEY_DISPATCH extension, Phase 2C Workshop registry,
Phase 2D demo seed extension, Phase 2E end-to-end demo path mirroring
Phase 1G structure, and pattern-establisher inheritance verification.

Anti-pattern guard tests covered:
  - §3.26.11.12.16 Anti-pattern 4 (primitive count expansion against
    fifth Focus type rejected) — Step 2 extends Generation Focus
    template registry via discriminator; does not introduce new Focus
    type.
  - §2.4.4 Anti-pattern 9 (primitive proliferation under composition
    pressure) — Step 2 reuses Personalization Studio category substrate.
  - Substrate-consumption-follower scope discipline — Step 2 ships only
    enumerated net-new substrate.
  - §3.26.11.12.16 Anti-pattern 1 schema substrate guard preserved at
    Phase 2B Intelligence prompts.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest

from app.database import SessionLocal
from app.models import Company, Role, User
from app.models.canonical_document import Document
from app.models.document_share import DocumentShare, DocumentShareEvent
from app.models.fh_case import FHCase
from app.models.funeral_case import FuneralCase
from app.models.generation_focus_instance import (
    CANONICAL_TEMPLATE_TYPES,
    GenerationFocusInstance,
)
from app.models.platform_tenant_relationship import (
    PlatformTenantRelationship,
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


@pytest.fixture
def fake_r2():
    storage: dict[str, bytes] = {}

    def fake_upload(
        data: bytes,
        r2_key: str,
        content_type: str = "application/octet-stream",
    ):
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


def _make_tenant(db_session, *, slug, vertical, name):
    co = Company(
        id=str(uuid.uuid4()),
        slug=slug,
        name=name,
        vertical=vertical,
        is_active=True,
    )
    db_session.add(co)
    db_session.flush()
    return co


def _make_user(db_session, tenant, *, email_prefix="user"):
    role = (
        db_session.query(Role)
        .filter(Role.company_id == tenant.id, Role.slug == "admin")
        .first()
    )
    if role is None:
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
        email=f"{email_prefix}-{uuid.uuid4().hex[:6]}@step2.test",
        hashed_password="x",
        first_name="Test",
        last_name="User",
        company_id=tenant.id,
        role_id=role.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _make_fh_case(db_session, tenant, *, case_number=None):
    case = FHCase(
        id=str(uuid.uuid4()),
        company_id=tenant.id,
        case_number=case_number or f"C-{uuid.uuid4().hex[:6]}",
        deceased_first_name="Robert",
        deceased_last_name="Harris",
        deceased_date_of_death=date(2026, 4, 15),
    )
    db_session.add(case)
    db_session.flush()
    return case


def _ensure_ptr(db_session, fh, mfg, consent="active"):
    forward = PlatformTenantRelationship(
        id=str(uuid.uuid4()),
        tenant_id=fh.id,
        supplier_tenant_id=mfg.id,
        relationship_type="fh_manufacturer",
        status="active",
        personalization_studio_cross_tenant_sharing_consent=consent,
    )
    reverse = PlatformTenantRelationship(
        id=str(uuid.uuid4()),
        tenant_id=mfg.id,
        supplier_tenant_id=fh.id,
        relationship_type="fh_manufacturer",
        status="active",
        personalization_studio_cross_tenant_sharing_consent=consent,
    )
    db_session.add(forward)
    db_session.add(reverse)
    db_session.flush()
    return forward, reverse


# ─────────────────────────────────────────────────────────────────────
# Phase 2A — Entity model + Document discriminator extension
# ─────────────────────────────────────────────────────────────────────


class TestPhase2AEntityModelExtension:
    def test_canonical_template_types_extended_with_urn(self):
        assert "urn_vault_personalization_studio" in CANONICAL_TEMPLATE_TYPES
        # Step 1 Burial Vault preserved.
        assert "burial_vault_personalization_studio" in CANONICAL_TEMPLATE_TYPES

    def test_document_type_for_template_extended_with_urn(self):
        from app.services.personalization_studio.instance_service import (
            DOCUMENT_TYPE_FOR_TEMPLATE,
        )

        assert (
            DOCUMENT_TYPE_FOR_TEMPLATE["urn_vault_personalization_studio"]
            == "urn_vault_personalization_studio"
        )
        # Step 1 mapping preserved.
        assert (
            DOCUMENT_TYPE_FOR_TEMPLATE["burial_vault_personalization_studio"]
            == "burial_vault_personalization_studio"
        )

    def test_empty_canvas_state_factory_dispatches_urn_shape(self):
        from app.services.personalization_studio.instance_service import (
            _empty_canvas_state,
        )

        state = _empty_canvas_state("urn_vault_personalization_studio")
        assert state["template_type"] == "urn_vault_personalization_studio"
        # Urn product replaces vault product slot per Phase 2A shape.
        assert "urn_product" in state
        assert "vault_product" not in state
        # Canonical 4-options vocabulary preserved per scope freeze.
        assert sorted(state["options"].keys()) == [
            "legacy_print",
            "physical_emblem",
            "physical_nameplate",
            "vinyl",
        ]

    def test_empty_canvas_state_burial_vault_unchanged(self):
        """Pattern-establisher inheritance: Step 2 extension does not
        regress Step 1 canvas state shape."""
        from app.services.personalization_studio.instance_service import (
            _empty_canvas_state,
        )

        state = _empty_canvas_state("burial_vault_personalization_studio")
        assert state["template_type"] == "burial_vault_personalization_studio"
        assert "vault_product" in state
        assert "urn_product" not in state

    def test_unknown_template_type_rejected(self):
        from app.services.personalization_studio.instance_service import (
            _empty_canvas_state,
            PersonalizationStudioError,
        )

        with pytest.raises(PersonalizationStudioError):
            _empty_canvas_state("monument_personalization_studio")

    def test_open_instance_creates_urn_template(self, db_session, fake_r2):
        from app.services.personalization_studio import instance_service

        hopkins = _make_tenant(
            db_session,
            slug=f"hop{uuid.uuid4().hex[:6]}",
            vertical="funeral_home",
            name="Hopkins Test",
        )
        director = _make_user(db_session, hopkins)
        case = _make_fh_case(db_session, hopkins)
        db_session.commit()

        # Phase 2A canonical urn template_type passes CHECK constraint
        # (r80 extends r76 enum).
        instance = instance_service.open_instance(
            db_session,
            company_id=hopkins.id,
            template_type="urn_vault_personalization_studio",
            authoring_context="funeral_home_with_family",
            linked_entity_id=case.id,
            opened_by_user_id=director.id,
        )
        db_session.commit()

        assert instance.template_type == "urn_vault_personalization_studio"
        # Q3 pairing preserved: funeral_home_with_family ↔ fh_case.
        assert instance.linked_entity_type == "fh_case"
        assert instance.lifecycle_state == "active"


# ─────────────────────────────────────────────────────────────────────
# Phase 2B — Intelligence prompts + _PROMPT_KEY_DISPATCH extension
# ─────────────────────────────────────────────────────────────────────


class TestPhase2BIntelligencePrompts:
    def test_prompt_key_dispatch_extended_with_urn(self):
        from app.services.personalization_studio.ai_extraction_review import (
            _PROMPT_KEY_DISPATCH,
            _resolve_prompt_key,
        )

        assert "urn_vault_personalization_studio" in _PROMPT_KEY_DISPATCH
        urn_dispatch = _PROMPT_KEY_DISPATCH["urn_vault_personalization_studio"]
        assert (
            urn_dispatch["suggest_layout"]
            == "urn_vault_personalization.suggest_layout"
        )
        assert (
            urn_dispatch["suggest_text_style"]
            == "urn_vault_personalization.suggest_text_style"
        )
        assert (
            urn_dispatch["extract_decedent_info"]
            == "urn_vault_personalization.extract_decedent_info"
        )

    def test_resolve_prompt_key_dispatches_urn_template(self):
        from app.services.personalization_studio.ai_extraction_review import (
            _resolve_prompt_key,
        )

        key = _resolve_prompt_key(
            "urn_vault_personalization_studio", "suggest_layout"
        )
        assert key == "urn_vault_personalization.suggest_layout"

    def test_step2_prompts_seeded_at_intelligence_substrate(
        self, db_session
    ):
        from scripts.seed_personalization_studio_step2_intelligence import (
            seed,
        )
        from app.models.intelligence import (
            IntelligencePrompt,
            IntelligencePromptVersion,
        )

        seed(db_session)

        for prompt_key in (
            "urn_vault_personalization.suggest_layout",
            "urn_vault_personalization.suggest_text_style",
            "urn_vault_personalization.extract_decedent_info",
        ):
            prompt = (
                db_session.query(IntelligencePrompt)
                .filter(IntelligencePrompt.prompt_key == prompt_key)
                .first()
            )
            assert prompt is not None
            active_version = (
                db_session.query(IntelligencePromptVersion)
                .filter(
                    IntelligencePromptVersion.prompt_id == prompt.id,
                    IntelligencePromptVersion.status == "active",
                )
                .first()
            )
            assert active_version is not None

    def test_step2_seed_idempotent(self, db_session):
        """Pattern-establisher inheritance: idempotent seed pattern from
        Phase 1C / Phase 6 / Phase 8b / Step 5.1 preserved at Phase 2B."""
        from scripts.seed_personalization_studio_step2_intelligence import (
            seed,
        )

        first_p, first_v = seed(db_session)
        second_p, second_v = seed(db_session)
        # Second pass: existing prompt with active version → no-op.
        assert second_p == 0
        assert second_v == 0

    def test_anti_pattern_1_schema_guard_at_step2_response_schemas(self):
        """§3.26.11.12.16 Anti-pattern 1 schema substrate guard:
        confidence required + type number + range 0-1 at Step 2 line
        item schemas."""
        from scripts.seed_personalization_studio_step2_intelligence import (
            _LAYOUT_SUGGESTION_RESPONSE_SCHEMA,
            _TEXT_STYLE_RESPONSE_SCHEMA,
            _DECEDENT_INFO_RESPONSE_SCHEMA,
        )

        for schema in (
            _LAYOUT_SUGGESTION_RESPONSE_SCHEMA,
            _TEXT_STYLE_RESPONSE_SCHEMA,
            _DECEDENT_INFO_RESPONSE_SCHEMA,
        ):
            line_items_schema = schema["properties"]["line_items"]
            item_schema = line_items_schema["items"]
            # Confidence required per Anti-pattern 1 guard.
            assert "confidence" in item_schema["required"]
            confidence_schema = item_schema["properties"]["confidence"]
            assert confidence_schema["type"] == "number"
            assert confidence_schema["minimum"] == 0
            assert confidence_schema["maximum"] == 1


# ─────────────────────────────────────────────────────────────────────
# Phase 2C — Workshop registry
# ─────────────────────────────────────────────────────────────────────


class TestPhase2CWorkshopRegistry:
    def test_urn_template_registered_at_workshop_substrate(self):
        from app.services.workshop import registry

        registry._seeded = False
        registry.reset_registry()
        registry._ensure_seeded()

        descriptor = registry.get_template_type(
            "urn_vault_personalization_studio"
        )
        assert descriptor is not None
        assert descriptor.template_type == "urn_vault_personalization_studio"
        assert "funeral_home" in descriptor.applicable_verticals
        assert "manufacturing" in descriptor.applicable_verticals

    def test_urn_tune_mode_dimensions_inherit_category_scope(self):
        """§3.26.11.12.19.6 scope freeze: urn vault inherits canonical
        4-options vocabulary at category scope; Tune mode dimensions
        parallel Step 1."""
        from app.services.workshop.registry import (
            CANONICAL_TUNE_DIMENSIONS_BURIAL_VAULT,
            CANONICAL_TUNE_DIMENSIONS_URN_VAULT,
        )

        assert (
            tuple(CANONICAL_TUNE_DIMENSIONS_URN_VAULT)
            == tuple(CANONICAL_TUNE_DIMENSIONS_BURIAL_VAULT)
        )

    def test_urn_per_tenant_tune_mode_resolves(self, db_session):
        from app.services.workshop import registry, tenant_config

        registry._seeded = False
        registry.reset_registry()
        registry._ensure_seeded()

        hopkins = _make_tenant(
            db_session,
            slug=f"hop{uuid.uuid4().hex[:6]}",
            vertical="funeral_home",
            name="Hopkins Test",
        )
        db_session.commit()

        config = tenant_config.get_tenant_personalization_config(
            db_session,
            company_id=hopkins.id,
            template_type="urn_vault_personalization_studio",
        )
        assert config["template_type"] == "urn_vault_personalization_studio"
        # Default catalogs surface when no tenant override applied.
        assert len(config["font_catalog"]) > 0
        assert len(config["emblem_catalog"]) > 0

    def test_urn_per_tenant_override_applies_within_boundary(
        self, db_session
    ):
        """Tune mode boundary discipline preserved: urn-specific
        override canonically-operates within canonical 4-options
        vocabulary boundary."""
        from app.services.workshop import registry, tenant_config

        registry._seeded = False
        registry.reset_registry()
        registry._ensure_seeded()

        hopkins = _make_tenant(
            db_session,
            slug=f"hop{uuid.uuid4().hex[:6]}",
            vertical="funeral_home",
            name="Hopkins Test",
        )
        db_session.commit()

        # Apply per-tenant urn vault override.
        tenant_config.update_tenant_personalization_config(
            db_session,
            company_id=hopkins.id,
            template_type="urn_vault_personalization_studio",
            updates={"font_catalog": ["serif", "italic"]},
        )
        db_session.commit()

        config = tenant_config.get_tenant_personalization_config(
            db_session,
            company_id=hopkins.id,
            template_type="urn_vault_personalization_studio",
        )
        assert config["font_catalog"] == ["serif", "italic"]


# ─────────────────────────────────────────────────────────────────────
# Phase 2D — Demo seed extension
# ─────────────────────────────────────────────────────────────────────


class TestPhase2DDemoSeed:
    def test_seed_personalization_studio_step2_creates_state(
        self, db_session, fake_r2
    ):
        from scripts.seed_fh_demo import _seed_personalization_studio_step2
        from app.services import personalization_studio  # noqa: F401
        from app.services.workshop import registry

        registry._seeded = False
        registry.reset_registry()
        registry._ensure_seeded()

        hopkins = _make_tenant(
            db_session,
            slug=f"hop{uuid.uuid4().hex[:6]}",
            vertical="funeral_home",
            name="Hopkins Test",
        )
        sunnycrest = _make_tenant(
            db_session,
            slug=f"sun{uuid.uuid4().hex[:6]}",
            vertical="manufacturing",
            name="Sunnycrest Test",
        )
        # Director with canonical email per Phase 1G discipline.
        director_role = Role(
            id=str(uuid.uuid4()),
            company_id=hopkins.id,
            name="Director",
            slug="director1",
        )
        db_session.add(director_role)
        db_session.flush()
        director = User(
            id=str(uuid.uuid4()),
            email="director1@hopkinsfh.test",
            hashed_password="x",
            first_name="Michael",
            last_name="Torres",
            company_id=hopkins.id,
            role_id=director_role.id,
            is_active=True,
        )
        db_session.add(director)
        db_session.flush()
        _ensure_ptr(db_session, hopkins, sunnycrest)
        db_session.commit()

        summary = _seed_personalization_studio_step2(
            db_session, hopkins, sunnycrest
        )

        assert summary["hopkins_urn_overrides"] in ("applied", "noop_matched")
        assert summary["sunnycrest_urn_overrides"] in ("applied", "noop_matched")
        assert summary["step2_case"] in ("created", "noop_matched")
        assert summary["step2_ps_instance"] in ("created", "noop_matched")
        assert summary["step2_documentshare"] in ("created", "noop_matched")

        # Step 2 cremation case at canonical FH-canon FuneralCase shape
        # (seed_fh_demo uses case_service which writes FuneralCase rows).
        case = (
            db_session.query(FuneralCase)
            .filter(
                FuneralCase.company_id == hopkins.id,
                FuneralCase.case_number == "FC-2026-0002",
            )
            .first()
        )
        assert case is not None

        # Step 2 GenerationFocusInstance canonical-shape.
        ps_instance = (
            db_session.query(GenerationFocusInstance)
            .filter(
                GenerationFocusInstance.company_id == hopkins.id,
                GenerationFocusInstance.template_type
                == "urn_vault_personalization_studio",
            )
            .first()
        )
        assert ps_instance is not None
        assert ps_instance.lifecycle_state == "committed"
        assert ps_instance.family_approval_status == "approved"
        assert ps_instance.linked_entity_id == case.id

        # Pre-shared DocumentShare Hopkins → Sunnycrest at Step 2 scope.
        share = (
            db_session.query(DocumentShare)
            .filter(
                DocumentShare.document_id == ps_instance.document_id,
                DocumentShare.target_company_id == sunnycrest.id,
                DocumentShare.revoked_at.is_(None),
            )
            .first()
        )
        assert share is not None

    def test_step2_seed_idempotent(self, db_session, fake_r2):
        from scripts.seed_fh_demo import _seed_personalization_studio_step2
        from app.services import personalization_studio  # noqa: F401
        from app.services.workshop import registry

        registry._seeded = False
        registry.reset_registry()
        registry._ensure_seeded()

        hopkins = _make_tenant(
            db_session,
            slug=f"hop{uuid.uuid4().hex[:6]}",
            vertical="funeral_home",
            name="Hopkins Test",
        )
        sunnycrest = _make_tenant(
            db_session,
            slug=f"sun{uuid.uuid4().hex[:6]}",
            vertical="manufacturing",
            name="Sunnycrest Test",
        )
        director_role = Role(
            id=str(uuid.uuid4()),
            company_id=hopkins.id,
            name="Director",
            slug="director1",
        )
        db_session.add(director_role)
        db_session.flush()
        director = User(
            id=str(uuid.uuid4()),
            email="director1@hopkinsfh.test",
            hashed_password="x",
            first_name="Michael",
            last_name="Torres",
            company_id=hopkins.id,
            role_id=director_role.id,
            is_active=True,
        )
        db_session.add(director)
        db_session.flush()
        _ensure_ptr(db_session, hopkins, sunnycrest)
        db_session.commit()

        first = _seed_personalization_studio_step2(
            db_session, hopkins, sunnycrest
        )
        second = _seed_personalization_studio_step2(
            db_session, hopkins, sunnycrest
        )

        assert second["hopkins_urn_overrides"] == "noop_matched"
        assert second["sunnycrest_urn_overrides"] == "noop_matched"
        assert second["step2_case"] == "noop_matched"
        assert second["step2_ps_instance"] == "noop_matched"
        assert second["step2_documentshare"] == "noop_matched"

        # Single Step 2 GenerationFocusInstance for FC-2026-0002.
        instance_count = (
            db_session.query(GenerationFocusInstance)
            .filter(
                GenerationFocusInstance.company_id == hopkins.id,
                GenerationFocusInstance.template_type
                == "urn_vault_personalization_studio",
            )
            .count()
        )
        assert instance_count == 1


# ─────────────────────────────────────────────────────────────────────
# Phase 2E — End-to-end Step 2 demo path
# ─────────────────────────────────────────────────────────────────────


class TestPhase2EEndToEndDemoPath:
    def test_step2_demo_path_canonical_complete(self, db_session, fake_r2):
        """Step 2 6-step demo path mirrors Phase 1G structure:
          1. Hopkins authors urn canvas (Phase 2D demo seed)
          2. Family approves (demo seed pre-stamps)
          3. Hopkins → Sunnycrest DocumentShare fires (demo seed pre-shares)
          4. Sunnycrest opens from-share instance
          5. Sunnycrest "Mark reviewed" commit
          6. Post-commit cascade fires (V-1d notification + D-6 reviewed)
        """
        from scripts.seed_fh_demo import _seed_personalization_studio_step2
        from app.services import personalization_studio  # noqa: F401
        from app.services.personalization_studio import instance_service
        from app.services.workshop import registry

        registry._seeded = False
        registry.reset_registry()
        registry._ensure_seeded()

        hopkins = _make_tenant(
            db_session,
            slug=f"hop{uuid.uuid4().hex[:6]}",
            vertical="funeral_home",
            name="Hopkins Test",
        )
        sunnycrest = _make_tenant(
            db_session,
            slug=f"sun{uuid.uuid4().hex[:6]}",
            vertical="manufacturing",
            name="Sunnycrest Test",
        )
        director_role = Role(
            id=str(uuid.uuid4()),
            company_id=hopkins.id,
            name="Director",
            slug="director1",
        )
        db_session.add(director_role)
        db_session.flush()
        director = User(
            id=str(uuid.uuid4()),
            email="director1@hopkinsfh.test",
            hashed_password="x",
            first_name="Michael",
            last_name="Torres",
            company_id=hopkins.id,
            role_id=director_role.id,
            is_active=True,
        )
        db_session.add(director)
        db_session.flush()
        mfg_admin = _make_user(db_session, sunnycrest)
        _ensure_ptr(db_session, hopkins, sunnycrest)
        db_session.commit()

        # Steps 1-3: demo seed pre-stamps state.
        summary = _seed_personalization_studio_step2(
            db_session, hopkins, sunnycrest
        )
        assert summary["step2_ps_instance"] == "created"
        assert summary["step2_documentshare"] == "created"

        # Resolve Step 2 share for Mfg-side open.
        ps_instance = (
            db_session.query(GenerationFocusInstance)
            .filter(
                GenerationFocusInstance.company_id == hopkins.id,
                GenerationFocusInstance.template_type
                == "urn_vault_personalization_studio",
            )
            .first()
        )
        share = (
            db_session.query(DocumentShare)
            .filter(
                DocumentShare.document_id == ps_instance.document_id,
                DocumentShare.target_company_id == sunnycrest.id,
            )
            .first()
        )

        # Step 4: Mfg-side open.
        mfg_instance = instance_service.open_instance_from_share(
            db_session,
            document_share_id=share.id,
            mfg_company_id=sunnycrest.id,
            opened_by_user_id=mfg_admin.id,
        )
        db_session.commit()
        assert mfg_instance.template_type == "urn_vault_personalization_studio"
        assert mfg_instance.authoring_context == "manufacturer_from_fh_share"

        # Step 5: "Mark reviewed" commit.
        committed = instance_service.commit_instance(
            db_session,
            instance_id=mfg_instance.id,
            committed_by_user_id=mfg_admin.id,
        )
        db_session.commit()
        assert committed.lifecycle_state == "committed"

        # Step 6: post-commit cascade fires (Phase 1G hook canonical-shared
        # across template_types via Pattern A).
        outcome = instance_service.manufacturer_from_fh_share_post_commit_cascade(
            db_session, instance=committed
        )
        db_session.commit()
        assert outcome["cascade_fired"] is True

        # D-6 'reviewed' event canonical at audit ledger.
        reviewed = (
            db_session.query(DocumentShareEvent)
            .filter(
                DocumentShareEvent.share_id == share.id,
                DocumentShareEvent.event_type == "reviewed",
            )
            .first()
        )
        assert reviewed is not None


# ─────────────────────────────────────────────────────────────────────
# Pattern-establisher inheritance verification
# ─────────────────────────────────────────────────────────────────────


class TestPatternEstablisherInheritance:
    """Verify Step 2 inherits Phase 1A-1G patterns at canonical
    pattern-establisher boundary. Failures here surface canonical
    pattern gap at Step 1 substrate (canonical revision targets Step 1,
    not Step 2)."""

    def test_action_type_descriptor_pattern_a_template_type_agnostic(
        self,
    ):
        """Pattern A canonical: ActionTypeDescriptor is template_type-
        agnostic; Step 2 reuses ``personalization_studio_family_approval``
        descriptor at canonical Personalization Studio category scope."""
        from app.services.platform.action_registry import get_action_type

        descriptor = get_action_type(
            "personalization_studio_family_approval"
        )
        # Step 2 inherits: descriptor primitive + target_entity_type
        # are template_type-agnostic.
        assert descriptor.primitive == "generation_focus"
        assert descriptor.target_entity_type == "generation_focus_instance"
        # Pattern A canonical: outcome vocabulary preserved across
        # canonical Step 1 + Step 2.
        assert descriptor.outcomes == ("approve", "request_changes", "decline")

    def test_q3_pairing_dict_inherits_step2_template_type(self):
        """Q3 canonical pairing (authoring_context ↔ linked_entity_type)
        canonical-applies to Step 2 via canonical Phase 1A entity model
        inheritance."""
        from app.models.generation_focus_instance import (
            AUTHORING_CONTEXT_TO_LINKED_ENTITY_TYPE,
        )

        # All 3 authoring contexts canonical-applicable to Step 2 +
        # canonical pairing dict canonical-shared.
        assert (
            AUTHORING_CONTEXT_TO_LINKED_ENTITY_TYPE[
                "funeral_home_with_family"
            ]
            == "fh_case"
        )
        assert (
            AUTHORING_CONTEXT_TO_LINKED_ENTITY_TYPE[
                "manufacturer_from_fh_share"
            ]
            == "document_share"
        )

    def test_anti_pattern_4_no_new_focus_type(self):
        """Anti-pattern 4: Step 2 extends Generation Focus template
        registry via discriminator; does not introduce new Focus type."""
        from app.services.workshop import registry

        registry._seeded = False
        registry.reset_registry()
        registry._ensure_seeded()

        # Both Step 1 + Step 2 templates registered at single Workshop
        # registry; no parallel Focus type registry introduced.
        templates = registry.list_template_types()
        template_types = [t.template_type for t in templates]
        assert "burial_vault_personalization_studio" in template_types
        assert "urn_vault_personalization_studio" in template_types

    def test_substrate_consumption_follower_no_new_migrations_beyond_r80(
        self,
    ):
        """Substrate-consumption-follower discipline: Personalization
        Studio Step 2 migrations bounded to r80 CHECK constraint
        extension. No Step-2-specific entity tables, no new junction
        tables, no new action token substrate.

        Pattern matches ``step2_urn_vault`` specifically (Personalization
        Studio arc Step 2 prefix) — does NOT collide with Email Step 2
        (``step2_credentials``) or Calendar Step 2 (``step2_credentials``)
        from earlier implementation arcs.
        """
        import os

        migrations_dir = os.path.join(
            os.path.dirname(__file__),
            "..",
            "alembic",
            "versions",
        )
        migrations = os.listdir(migrations_dir)
        # Personalization Studio Step 2 migrations carry ``step2_urn_vault``
        # naming per arc convention. Email + Calendar arcs use unrelated
        # ``step2_credentials`` naming and are excluded.
        ps_step2_migrations = [
            m for m in migrations if "step2_urn_vault" in m.lower()
        ]
        # Single Step 2 migration: r80_step2_urn_vault_template_type.
        assert len(ps_step2_migrations) == 1
        assert "r80_step2_urn_vault_template_type" in ps_step2_migrations[0]
