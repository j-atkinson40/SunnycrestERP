"""Personalization Studio Phase 1C — canonical AI-extraction-review pipeline tests.

Per Phase 1C build prompt closing standards: covers canonical 3 managed
Intelligence prompt registrations + canonical service layer + canonical
3-endpoint API surface + canonical anti-pattern guards.

**Canonical anti-pattern guards explicit at test substrate**:

- §3.26.11.12.16 Anti-pattern 1 (auto-commit on extraction confidence
  rejected): canonical service returns canonical line items only;
  canonical canvas state mutation does NOT occur at canonical service-
  layer call boundary. Canonical Confirm action canonical at chrome
  substrate (verified at frontend test substrate; backend canonical
  guard verified by absence of canonical canvas-state-write-side
  effect at canonical AI-extraction-review service substrate).

- §3.26.11.12.16 Anti-pattern 11 (UI-coupled Generation Focus design
  rejected): canonical structured output schema independent from
  canonical interactive UI; canonical line items canonical at canonical
  Intelligence prompt substrate.

- §3.26.11.12.16 Anti-pattern 12 (parallel architectures for differently-
  sourced Generation Focus inputs rejected): canonical AI-extraction-
  review pipeline single canonical architecture across canonical
  adapter source categories. Canonical multimodal content_blocks
  canonical at canonical extraction adapter category.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.database import SessionLocal
from app.main import app
from app.models import Company, Role, User
from app.models.canonical_document import DocumentVersion
from app.models.intelligence import IntelligencePrompt, IntelligencePromptVersion
from app.services.personalization_studio import (
    ai_extraction_review,
    instance_service,
)
from app.services.intelligence.intelligence_service import IntelligenceResult


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


@pytest.fixture
def fake_intelligence_layout():
    """Canonical Intelligence response stub for canonical layout suggestions."""
    canned = {
        "line_items": [
            {
                "line_item_key": "name_text_position",
                "value": {"x": 200, "y": 150, "width": 400, "height": 60},
                "confidence": 0.92,
                "rationale": "Centered upper-third placement matches canonical product geometry.",
            },
            {
                "line_item_key": "date_text_position",
                "value": {"x": 200, "y": 220, "width": 400, "height": 30},
                "confidence": 0.78,
                "rationale": "Below name, common canonical placement.",
            },
            {
                "line_item_key": "emblem_position",
                "value": {"x": 350, "y": 320, "width": 100, "height": 100},
                "confidence": 0.55,
                "rationale": "Limited info; family preferences may override.",
            },
        ]
    }
    yield from _stub_intelligence(canned)


@pytest.fixture
def fake_intelligence_text_style():
    canned = {
        "line_items": [
            {
                "line_item_key": "name_text_font",
                "value": {"font": "serif", "size": 42, "color": "#1A1715"},
                "confidence": 0.88,
                "rationale": "Family preference 'traditional' implies serif.",
            },
            {
                "line_item_key": "date_text_font",
                "value": {"font": "sans", "size": 18},
                "confidence": 0.72,
                "rationale": "Common canonical date treatment.",
            },
        ]
    }
    yield from _stub_intelligence(canned)


@pytest.fixture
def fake_intelligence_decedent_info():
    canned = {
        "line_items": [
            {
                "line_item_key": "decedent_first_name",
                "value": "John",
                "confidence": 0.96,
                "rationale": "Explicit text match in death certificate.",
            },
            {
                "line_item_key": "decedent_last_name",
                "value": "Smith",
                "confidence": 0.96,
                "rationale": "Explicit text match.",
            },
            {
                "line_item_key": "birth_date",
                "value": "1945-03-12",
                "confidence": 0.90,
                "rationale": "ISO date inferred from canonical 03/12/1945.",
            },
            {
                "line_item_key": "death_date",
                "value": "2024-08-22",
                "confidence": 0.94,
                "rationale": "ISO date from canonical death certificate.",
            },
            {
                "line_item_key": "emblem_hint",
                "value": "cross",
                "confidence": 0.65,
                "rationale": "Religious imagery in obituary context.",
            },
        ]
    }
    yield from _stub_intelligence(canned)


def _stub_intelligence(canned_response: dict[str, Any]):
    """Yield-helper for canonical intelligence_service.execute stub."""

    def fake_execute(db, prompt_key, **kwargs):
        return IntelligenceResult(
            execution_id=str(uuid.uuid4()),
            prompt_id="prompt-stub",
            prompt_version_id="version-stub",
            model_used="claude-haiku-4-5-20250514",
            status="success",
            response_text=str(canned_response),
            response_parsed=canned_response,
            rendered_system_prompt="(stub)",
            rendered_user_prompt="(stub)",
            input_tokens=100,
            output_tokens=200,
            latency_ms=350,
            cost_usd=None,
        )

    with patch(
        "app.services.personalization_studio.ai_extraction_review.intelligence_service.execute",
        side_effect=fake_execute,
    ):
        yield


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _make_tenant(db_session, vertical="manufacturing"):
    co = Company(
        id=str(uuid.uuid4()),
        name=f"P1C-{uuid.uuid4().hex[:8]}",
        slug=f"p1c{uuid.uuid4().hex[:8]}",
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
        email=f"u-{uuid.uuid4().hex[:8]}@p1c.test",
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
# 1. Canonical 3 managed Intelligence prompt seed registrations
# ─────────────────────────────────────────────────────────────────────


class TestPromptSeedRegistrations:
    def test_three_canonical_prompts_seeded(self, db_session):
        """Canonical Phase 1C prompts canonical at canonical Intelligence
        backbone substrate."""
        canonical_keys = {
            "burial_vault_personalization.suggest_layout",
            "burial_vault_personalization.suggest_text_style",
            "burial_vault_personalization.extract_decedent_info",
        }
        seeded = (
            db_session.query(IntelligencePrompt)
            .filter(IntelligencePrompt.prompt_key.in_(canonical_keys))
            .all()
        )
        assert {p.prompt_key for p in seeded} == canonical_keys
        for prompt in seeded:
            # Canonical platform-global per canonical idempotent seed pattern.
            assert prompt.company_id is None
            assert prompt.domain == "burial_vault_personalization"

    def test_canonical_prompts_have_active_v1(self, db_session):
        keys = [
            "burial_vault_personalization.suggest_layout",
            "burial_vault_personalization.suggest_text_style",
            "burial_vault_personalization.extract_decedent_info",
        ]
        for key in keys:
            prompt = (
                db_session.query(IntelligencePrompt)
                .filter(
                    IntelligencePrompt.company_id.is_(None),
                    IntelligencePrompt.prompt_key == key,
                )
                .first()
            )
            assert prompt is not None
            active = (
                db_session.query(IntelligencePromptVersion)
                .filter(
                    IntelligencePromptVersion.prompt_id == prompt.id,
                    IntelligencePromptVersion.status == "active",
                )
                .first()
            )
            assert active is not None
            assert active.version_number == 1
            assert active.force_json is True
            assert active.response_schema is not None

    def test_canonical_extract_decedent_info_supports_vision(self, db_session):
        """Phase 2c-0b canonical multimodal canonical."""
        prompt = (
            db_session.query(IntelligencePrompt)
            .filter(
                IntelligencePrompt.company_id.is_(None),
                IntelligencePrompt.prompt_key
                == "burial_vault_personalization.extract_decedent_info",
            )
            .first()
        )
        active = (
            db_session.query(IntelligencePromptVersion)
            .filter(
                IntelligencePromptVersion.prompt_id == prompt.id,
                IntelligencePromptVersion.status == "active",
            )
            .first()
        )
        assert active.supports_vision is True
        assert active.model_preference == "vision"

    def test_canonical_layout_and_text_style_prompts_are_text_only(
        self, db_session
    ):
        """Canonical text-only prompts (non-multimodal) per Phase 1C spec."""
        for key in [
            "burial_vault_personalization.suggest_layout",
            "burial_vault_personalization.suggest_text_style",
        ]:
            prompt = (
                db_session.query(IntelligencePrompt)
                .filter(
                    IntelligencePrompt.company_id.is_(None),
                    IntelligencePrompt.prompt_key == key,
                )
                .first()
            )
            active = (
                db_session.query(IntelligencePromptVersion)
                .filter(
                    IntelligencePromptVersion.prompt_id == prompt.id,
                    IntelligencePromptVersion.status == "active",
                )
                .first()
            )
            assert active.supports_vision is False
            assert active.model_preference == "simple"

    def test_canonical_response_schemas_require_confidence_per_line_item(
        self, db_session
    ):
        """§3.26.11.12.16 Anti-pattern 1 guard at schema substrate:
        canonical confidence per line item is canonically REQUIRED."""
        keys = [
            "burial_vault_personalization.suggest_layout",
            "burial_vault_personalization.suggest_text_style",
            "burial_vault_personalization.extract_decedent_info",
        ]
        for key in keys:
            prompt = (
                db_session.query(IntelligencePrompt)
                .filter(
                    IntelligencePrompt.company_id.is_(None),
                    IntelligencePrompt.prompt_key == key,
                )
                .first()
            )
            active = (
                db_session.query(IntelligencePromptVersion)
                .filter(
                    IntelligencePromptVersion.prompt_id == prompt.id,
                    IntelligencePromptVersion.status == "active",
                )
                .first()
            )
            schema = active.response_schema
            line_items_schema = schema["properties"]["line_items"]
            item_schema = line_items_schema["items"]
            assert "confidence" in item_schema["required"]
            assert "line_item_key" in item_schema["required"]


# ─────────────────────────────────────────────────────────────────────
# 2. Canonical service layer — confidence_tier helper
# ─────────────────────────────────────────────────────────────────────


class TestConfidenceTier:
    def test_high_threshold(self):
        assert ai_extraction_review.confidence_tier(0.95) == "high"
        assert ai_extraction_review.confidence_tier(0.85) == "high"

    def test_medium_threshold(self):
        assert ai_extraction_review.confidence_tier(0.84) == "medium"
        assert ai_extraction_review.confidence_tier(0.70) == "medium"

    def test_low_threshold(self):
        assert ai_extraction_review.confidence_tier(0.69) == "low"
        assert ai_extraction_review.confidence_tier(0.0) == "low"

    def test_canonical_thresholds_match_visual_canon(self):
        """§14.14.3 canonical thresholds: ≥0.85 success / 0.70-0.85 warning / <0.70 error."""
        assert ai_extraction_review.CONFIDENCE_THRESHOLD_HIGH == 0.85
        assert ai_extraction_review.CONFIDENCE_THRESHOLD_MEDIUM == 0.70


# ─────────────────────────────────────────────────────────────────────
# 3. Canonical service layer — suggest_layout
# ─────────────────────────────────────────────────────────────────────


class TestSuggestLayout:
    def test_returns_canonical_confidence_scored_line_items(
        self, db_session, fake_r2, fake_intelligence_layout
    ):
        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
        instance = instance_service.open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
            opened_by_user_id=user.id,
        )
        db_session.commit()

        payload = ai_extraction_review.suggest_layout(
            db_session,
            instance_id=instance.id,
            company_id=tenant.id,
        )

        assert "line_items" in payload
        assert len(payload["line_items"]) == 3
        # Canonical confidence_tier annotation per §14.14.3.
        tiers = {item["confidence_tier"] for item in payload["line_items"]}
        assert tiers == {"high", "medium", "low"}

    def test_canonical_anti_pattern_1_guard_no_canvas_state_mutation(
        self, db_session, fake_r2, fake_intelligence_layout
    ):
        """§3.26.11.12.16 Anti-pattern 1 guard: canonical service returns
        canonical line items WITHOUT canonical canvas-state mutation.
        Canonical operator agency canonical at canonical Confirm action
        canonical at chrome substrate."""
        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
        instance = instance_service.open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
            opened_by_user_id=user.id,
        )
        # Commit canonical initial empty canvas state.
        from app.services.personalization_studio.instance_service import (
            _empty_canvas_state,
            commit_canvas_state,
        )
        commit_canvas_state(
            db_session,
            instance_id=instance.id,
            canvas_state=_empty_canvas_state(
                "burial_vault_personalization_studio"
            ),
        )
        db_session.commit()

        # Pre-suggestion DocumentVersion count.
        pre_versions = (
            db_session.query(DocumentVersion)
            .filter(DocumentVersion.document_id == instance.document_id)
            .count()
        )
        assert pre_versions == 1

        # Invoke canonical suggest_layout — canonical Anti-pattern 1
        # guard: canonical service returns canonical line items only;
        # canonical canvas state must NOT mutate.
        ai_extraction_review.suggest_layout(
            db_session,
            instance_id=instance.id,
            company_id=tenant.id,
        )
        db_session.commit()

        post_versions = (
            db_session.query(DocumentVersion)
            .filter(DocumentVersion.document_id == instance.document_id)
            .count()
        )
        # Canonical anti-pattern 1 verified: NO new DocumentVersion
        # created at canonical service-call boundary.
        assert post_versions == pre_versions

    def test_cross_tenant_returns_404(
        self, db_session, fake_r2, fake_intelligence_layout
    ):
        tenant_a = _make_tenant(db_session)
        tenant_b = _make_tenant(db_session)
        instance = instance_service.open_instance(
            db_session,
            company_id=tenant_a.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
        )
        db_session.commit()

        from app.services.personalization_studio.instance_service import (
            PersonalizationStudioNotFound,
        )
        with pytest.raises(PersonalizationStudioNotFound):
            ai_extraction_review.suggest_layout(
                db_session,
                instance_id=instance.id,
                company_id=tenant_b.id,
            )


# ─────────────────────────────────────────────────────────────────────
# 4. Canonical service layer — suggest_text_style
# ─────────────────────────────────────────────────────────────────────


class TestSuggestTextStyle:
    def test_returns_canonical_confidence_scored_line_items(
        self, db_session, fake_r2, fake_intelligence_text_style
    ):
        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
        instance = instance_service.open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
            opened_by_user_id=user.id,
        )
        db_session.commit()

        payload = ai_extraction_review.suggest_text_style(
            db_session,
            instance_id=instance.id,
            company_id=tenant.id,
            family_preferences="traditional, classic serif fonts preferred",
        )
        assert len(payload["line_items"]) == 2
        # Canonical font + size + color per §14.14.4.
        first = payload["line_items"][0]
        assert first["line_item_key"] == "name_text_font"
        assert isinstance(first["value"], dict)


# ─────────────────────────────────────────────────────────────────────
# 5. Canonical service layer — extract_decedent_info (multimodal)
# ─────────────────────────────────────────────────────────────────────


class TestExtractDecedentInfo:
    def _canonical_image_block(self) -> dict[str, Any]:
        """Canonical Phase 2c-0b multimodal content_block — minimal valid
        canonical base64-image-block fixture."""
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                # 1x1 transparent JPEG canonical fixture.
                "data": (
                    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEB"
                    "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEB"
                    "AQEB/8AAEQgAAQABAwEiAAIRAQMRAf/EAB8AAAEFAQEBAQEBAAAAAAAAAA"
                    "ABAgMEBQYHCAkKC//EALUQAAIBAwMCBAMFBQQEAAABfQECAwAEEQUSITFB"
                    "BhNRYQcicRQygZGhCCNCscEVUtHwJDNicoIJChYXGBkaJSYnKCkqNDU2Nz"
                    "g5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6g4SFhoeIiYqS"
                    "k5SVlpeYmZqio6Slpqeoqaqys7S1tre4ubrCw8TFxsfIycrS09TV1tfY2drh"
                    "4uPk5ebn6Onq8fLz9PX29/j5+v/aAAwDAQACEQMRAD8A/v4ooooA//9k="
                ),
            },
        }

    def test_returns_canonical_decedent_extraction_line_items(
        self, db_session, fake_r2, fake_intelligence_decedent_info
    ):
        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
        instance = instance_service.open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
            opened_by_user_id=user.id,
        )
        db_session.commit()

        payload = ai_extraction_review.extract_decedent_info(
            db_session,
            instance_id=instance.id,
            company_id=tenant.id,
            content_blocks=[self._canonical_image_block()],
            context_summary="Death certificate from County clerk",
        )
        assert len(payload["line_items"]) == 5
        keys = [item["line_item_key"] for item in payload["line_items"]]
        assert "decedent_first_name" in keys
        assert "birth_date" in keys
        assert "death_date" in keys
        assert "emblem_hint" in keys

    def test_empty_content_blocks_rejected(
        self, db_session, fake_r2
    ):
        """Canonical extraction adapter requires canonical multimodal
        content_blocks per Phase 2c-0b substrate."""
        tenant = _make_tenant(db_session)
        instance = instance_service.open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
        )
        db_session.commit()

        from app.services.personalization_studio.instance_service import (
            PersonalizationStudioError,
        )
        with pytest.raises(PersonalizationStudioError):
            ai_extraction_review.extract_decedent_info(
                db_session,
                instance_id=instance.id,
                company_id=tenant.id,
                content_blocks=[],
            )


# ─────────────────────────────────────────────────────────────────────
# 6. Canonical 3-endpoint API surface
# ─────────────────────────────────────────────────────────────────────


class TestSuggestLayoutEndpoint:
    def test_post_suggest_layout_returns_canonical_payload(
        self, db_session, fake_r2, fake_intelligence_layout
    ):
        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
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
                f"/api/v1/personalization-studio/instances/{instance.id}/suggest-layout",
                headers=_auth_headers(db_session, user),
            )
        assert r.status_code == 200
        body = r.json()
        assert "line_items" in body
        assert len(body["line_items"]) == 3
        # Canonical confidence_tier annotation surfaces canonically.
        first = body["line_items"][0]
        assert first["confidence_tier"] == "high"
        assert first["line_item_key"] == "name_text_position"
        assert first["confidence"] == 0.92

    def test_post_suggest_layout_cross_tenant_404(
        self, db_session, fake_r2, fake_intelligence_layout
    ):
        tenant_a = _make_tenant(db_session)
        tenant_b = _make_tenant(db_session)
        user_b = _make_user(db_session, tenant_b)
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
                f"/api/v1/personalization-studio/instances/{instance.id}/suggest-layout",
                headers=_auth_headers(db_session, user_b),
            )
        assert r.status_code == 404


class TestSuggestTextStyleEndpoint:
    def test_post_suggest_text_style_with_family_preferences(
        self, db_session, fake_r2, fake_intelligence_text_style
    ):
        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
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
                f"/api/v1/personalization-studio/instances/{instance.id}/suggest-text-style",
                json={"family_preferences": "traditional serif"},
                headers=_auth_headers(db_session, user),
            )
        assert r.status_code == 200
        body = r.json()
        assert len(body["line_items"]) == 2

    def test_post_suggest_text_style_without_body(
        self, db_session, fake_r2, fake_intelligence_text_style
    ):
        """Canonical body optional per canonical SuggestTextStyleRequest shape."""
        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
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
                f"/api/v1/personalization-studio/instances/{instance.id}/suggest-text-style",
                json={},
                headers=_auth_headers(db_session, user),
            )
        assert r.status_code == 200


class TestExtractDecedentInfoEndpoint:
    def _canonical_image_block(self) -> dict[str, Any]:
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": (
                    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEB"
                    "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEB"
                    "AQEB/8AAEQgAAQABAwEiAAIRAQMRAf/EAB8AAAEFAQEBAQEBAAAAAAAAAA"
                    "ABAgMEBQYHCAkKC//EALUQAAIBAwMCBAMFBQQEAAABfQECAwAEEQUSITFB"
                    "BhNRYQcicRQygZGhCCNCscEVUtHwJDNicoIJChYXGBkaJSYnKCkqNDU2Nz"
                    "g5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6g4SFhoeIiYqS"
                    "k5SVlpeYmZqio6Slpqeoqaqys7S1tre4ubrCw8TFxsfIycrS09TV1tfY2drh"
                    "4uPk5ebn6Onq8fLz9PX29/j5+v/aAAwDAQACEQMRAD8A/v4ooooA//9k="
                ),
            },
        }

    def test_post_extract_decedent_info_with_canonical_multimodal_block(
        self, db_session, fake_r2, fake_intelligence_decedent_info
    ):
        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
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
                f"/api/v1/personalization-studio/instances/{instance.id}/extract-decedent-info",
                json={
                    "content_blocks": [self._canonical_image_block()],
                    "context_summary": "Death certificate from County clerk",
                },
                headers=_auth_headers(db_session, user),
            )
        assert r.status_code == 200
        body = r.json()
        assert len(body["line_items"]) == 5

    def test_post_extract_decedent_info_empty_content_blocks_422(
        self, db_session, fake_r2
    ):
        """Pydantic min_length=1 canonical at canonical content_blocks."""
        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
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
                f"/api/v1/personalization-studio/instances/{instance.id}/extract-decedent-info",
                json={"content_blocks": []},
                headers=_auth_headers(db_session, user),
            )
        assert r.status_code == 422

    def test_post_extract_decedent_info_invalid_block_type_422(
        self, db_session, fake_r2
    ):
        """Canonical content_block.type must be 'image' or 'document'."""
        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
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
                f"/api/v1/personalization-studio/instances/{instance.id}/extract-decedent-info",
                json={
                    "content_blocks": [
                        {
                            "type": "audio",  # canonical invalid
                            "source": {
                                "type": "base64",
                                "media_type": "audio/mp3",
                                "data": "...",
                            },
                        }
                    ],
                },
                headers=_auth_headers(db_session, user),
            )
        assert r.status_code == 422


# ─────────────────────────────────────────────────────────────────────
# 7. Canonical anti-pattern 11 guard — output schema independent from UI
# ─────────────────────────────────────────────────────────────────────


class TestAntiPattern11Guard:
    """§3.26.11.12.16 Anti-pattern 11 guard at substrate level: canonical
    structured output schema canonical at canonical Intelligence prompt
    substrate; canonical chrome substrate consumes canonical line items
    via canonical Pattern 2 sub-cards. Canonical service substrate does
    NOT couple canonical line item shape to canonical interactive UI
    state."""

    def test_canonical_service_returns_pure_data_payload_no_ui_coupling(
        self, db_session, fake_r2, fake_intelligence_layout
    ):
        """Canonical payload contains canonical line items + canonical
        execution metadata — NO canonical interactive UI state coupling
        per §3.26.11.12.16 Anti-pattern 11."""
        tenant = _make_tenant(db_session)
        instance = instance_service.open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
        )
        db_session.commit()

        payload = ai_extraction_review.suggest_layout(
            db_session,
            instance_id=instance.id,
            company_id=tenant.id,
        )

        canonical_keys = {"line_items", "execution_id", "model_used", "latency_ms"}
        assert set(payload.keys()) == canonical_keys
        # Canonical UI-coupling forbidden at service substrate per
        # §3.26.11.12.16 Anti-pattern 11.
        forbidden_ui_keys = {
            "selected_line_item",
            "is_editing",
            "operator_decision",
            "chrome_state",
            "viewport_state",
        }
        assert not (set(payload.keys()) & forbidden_ui_keys)

    def test_canonical_line_items_are_pure_data(
        self, db_session, fake_r2, fake_intelligence_layout
    ):
        """Canonical line item shape canonical at canonical schema substrate;
        canonical line items canonical do NOT carry canonical interactive
        UI state per §3.26.11.12.16 Anti-pattern 11."""
        tenant = _make_tenant(db_session)
        instance = instance_service.open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
        )
        db_session.commit()

        payload = ai_extraction_review.suggest_layout(
            db_session,
            instance_id=instance.id,
            company_id=tenant.id,
        )

        canonical_line_item_keys = {
            "line_item_key",
            "value",
            "confidence",
            "rationale",
            "confidence_tier",
        }
        for item in payload["line_items"]:
            assert set(item.keys()) <= canonical_line_item_keys
            assert "selected" not in item
            assert "is_editing" not in item


# ─────────────────────────────────────────────────────────────────────
# 8. Canonical-pattern-establisher discipline — Step 2 inheritance
# ─────────────────────────────────────────────────────────────────────


class TestStrictLineItemValidation:
    """Phase 1C Anti-pattern 1 schema substrate guard at service layer.

    The Intelligence backbone validator (`prompt_renderer.validate_response_against_schema`)
    is permissive by design — top-level `required` only; nested `items.required`
    NOT enforced. This service-layer guard surfaces malformed line items
    rather than silently dropping them.
    """

    def _seed_instance(self, db_session):
        tenant = _make_tenant(db_session)
        instance = instance_service.open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
        )
        db_session.commit()
        return tenant, instance

    def _stub_response(self, response_payload):
        def fake_execute(db, prompt_key, **kwargs):
            return IntelligenceResult(
                execution_id=str(uuid.uuid4()),
                prompt_id="p", prompt_version_id="v",
                model_used="claude-haiku-4-5-20250514",
                status="success",
                response_text=str(response_payload),
                response_parsed=response_payload,
                rendered_system_prompt="",
                rendered_user_prompt="",
                input_tokens=10, output_tokens=20, latency_ms=50,
                cost_usd=None,
            )
        return fake_execute

    def test_missing_line_items_array_rejected(self, db_session, fake_r2):
        tenant, instance = self._seed_instance(db_session)
        from app.services.personalization_studio.instance_service import (
            PersonalizationStudioError,
        )
        with patch(
            "app.services.personalization_studio.ai_extraction_review.intelligence_service.execute",
            side_effect=self._stub_response({}),
        ):
            with pytest.raises(PersonalizationStudioError, match="missing 'line_items'"):
                ai_extraction_review.suggest_layout(
                    db_session, instance_id=instance.id, company_id=tenant.id,
                )

    def test_missing_confidence_field_rejected(self, db_session, fake_r2):
        tenant, instance = self._seed_instance(db_session)
        from app.services.personalization_studio.instance_service import (
            PersonalizationStudioError,
        )
        with patch(
            "app.services.personalization_studio.ai_extraction_review.intelligence_service.execute",
            side_effect=self._stub_response({
                "line_items": [
                    {"line_item_key": "name_text_position", "value": {"x": 1, "y": 2}},
                ]
            }),
        ):
            with pytest.raises(
                PersonalizationStudioError, match="missing required 'confidence'"
            ):
                ai_extraction_review.suggest_layout(
                    db_session, instance_id=instance.id, company_id=tenant.id,
                )

    def test_missing_line_item_key_rejected(self, db_session, fake_r2):
        tenant, instance = self._seed_instance(db_session)
        from app.services.personalization_studio.instance_service import (
            PersonalizationStudioError,
        )
        with patch(
            "app.services.personalization_studio.ai_extraction_review.intelligence_service.execute",
            side_effect=self._stub_response({
                "line_items": [
                    {"value": {"x": 1, "y": 2}, "confidence": 0.9},
                ]
            }),
        ):
            with pytest.raises(
                PersonalizationStudioError, match="missing required 'line_item_key'"
            ):
                ai_extraction_review.suggest_layout(
                    db_session, instance_id=instance.id, company_id=tenant.id,
                )

    def test_missing_value_field_rejected(self, db_session, fake_r2):
        tenant, instance = self._seed_instance(db_session)
        from app.services.personalization_studio.instance_service import (
            PersonalizationStudioError,
        )
        with patch(
            "app.services.personalization_studio.ai_extraction_review.intelligence_service.execute",
            side_effect=self._stub_response({
                "line_items": [
                    {"line_item_key": "name_text_position", "confidence": 0.9},
                ]
            }),
        ):
            with pytest.raises(
                PersonalizationStudioError, match="missing required 'value'"
            ):
                ai_extraction_review.suggest_layout(
                    db_session, instance_id=instance.id, company_id=tenant.id,
                )

    def test_non_numeric_confidence_rejected(self, db_session, fake_r2):
        tenant, instance = self._seed_instance(db_session)
        from app.services.personalization_studio.instance_service import (
            PersonalizationStudioError,
        )
        with patch(
            "app.services.personalization_studio.ai_extraction_review.intelligence_service.execute",
            side_effect=self._stub_response({
                "line_items": [
                    {
                        "line_item_key": "name_text_position",
                        "value": {"x": 1, "y": 2},
                        "confidence": "high",  # canonical-violation: string not number
                    },
                ]
            }),
        ):
            with pytest.raises(
                PersonalizationStudioError, match="confidence is not a number"
            ):
                ai_extraction_review.suggest_layout(
                    db_session, instance_id=instance.id, company_id=tenant.id,
                )

    def test_boolean_confidence_rejected(self, db_session, fake_r2):
        """Python `bool` is subclass of `int` — explicit guard rejects it."""
        tenant, instance = self._seed_instance(db_session)
        from app.services.personalization_studio.instance_service import (
            PersonalizationStudioError,
        )
        with patch(
            "app.services.personalization_studio.ai_extraction_review.intelligence_service.execute",
            side_effect=self._stub_response({
                "line_items": [
                    {
                        "line_item_key": "name_text_position",
                        "value": {"x": 1, "y": 2},
                        "confidence": True,
                    },
                ]
            }),
        ):
            with pytest.raises(
                PersonalizationStudioError, match="confidence is not a number"
            ):
                ai_extraction_review.suggest_layout(
                    db_session, instance_id=instance.id, company_id=tenant.id,
                )

    def test_confidence_above_one_rejected(self, db_session, fake_r2):
        tenant, instance = self._seed_instance(db_session)
        from app.services.personalization_studio.instance_service import (
            PersonalizationStudioError,
        )
        with patch(
            "app.services.personalization_studio.ai_extraction_review.intelligence_service.execute",
            side_effect=self._stub_response({
                "line_items": [
                    {
                        "line_item_key": "name_text_position",
                        "value": {"x": 1, "y": 2},
                        "confidence": 1.5,
                    },
                ]
            }),
        ):
            with pytest.raises(
                PersonalizationStudioError, match=r"confidence 1\.5 outside"
            ):
                ai_extraction_review.suggest_layout(
                    db_session, instance_id=instance.id, company_id=tenant.id,
                )

    def test_confidence_below_zero_rejected(self, db_session, fake_r2):
        tenant, instance = self._seed_instance(db_session)
        from app.services.personalization_studio.instance_service import (
            PersonalizationStudioError,
        )
        with patch(
            "app.services.personalization_studio.ai_extraction_review.intelligence_service.execute",
            side_effect=self._stub_response({
                "line_items": [
                    {
                        "line_item_key": "name_text_position",
                        "value": {"x": 1, "y": 2},
                        "confidence": -0.1,
                    },
                ]
            }),
        ):
            with pytest.raises(
                PersonalizationStudioError, match=r"confidence -0\.1 outside"
            ):
                ai_extraction_review.suggest_layout(
                    db_session, instance_id=instance.id, company_id=tenant.id,
                )

    def test_non_dict_line_item_rejected(self, db_session, fake_r2):
        tenant, instance = self._seed_instance(db_session)
        from app.services.personalization_studio.instance_service import (
            PersonalizationStudioError,
        )
        with patch(
            "app.services.personalization_studio.ai_extraction_review.intelligence_service.execute",
            side_effect=self._stub_response({
                "line_items": ["not a dict"],
            }),
        ):
            with pytest.raises(
                PersonalizationStudioError, match="is not a dict"
            ):
                ai_extraction_review.suggest_layout(
                    db_session, instance_id=instance.id, company_id=tenant.id,
                )

    def test_well_formed_response_accepted(self, db_session, fake_r2):
        """Sanity: well-formed response passes the strict guard."""
        tenant, instance = self._seed_instance(db_session)
        with patch(
            "app.services.personalization_studio.ai_extraction_review.intelligence_service.execute",
            side_effect=self._stub_response({
                "line_items": [
                    {
                        "line_item_key": "name_text_position",
                        "value": {"x": 1, "y": 2},
                        "confidence": 0.85,
                        "rationale": "OK",
                    },
                ]
            }),
        ):
            payload = ai_extraction_review.suggest_layout(
                db_session, instance_id=instance.id, company_id=tenant.id,
            )
        assert len(payload["line_items"]) == 1
        assert payload["line_items"][0]["confidence"] == 0.85
        assert payload["line_items"][0]["confidence_tier"] == "high"


class TestCanonicalPatternEstablisherDiscipline:
    def test_unknown_template_type_canonically_rejected(
        self, db_session, fake_r2
    ):
        """Pattern-establisher: prompt key dispatch is the extension point
        per template_type discriminator. Step 2 extended with
        `urn_vault_personalization_studio` per Phase 2B substrate-
        consumption-follower; future templates extend identically.
        """
        from app.services.personalization_studio.ai_extraction_review import (
            _resolve_prompt_key,
        )
        from app.services.personalization_studio.instance_service import (
            PersonalizationStudioError,
        )

        # Phase 1B + 1C pattern-establisher value.
        assert (
            _resolve_prompt_key(
                "burial_vault_personalization_studio", "suggest_layout"
            )
            == "burial_vault_personalization.suggest_layout"
        )

        # Step 2 substrate-consumption-follower value resolves to the
        # urn-prefixed prompt key per Phase 2B _PROMPT_KEY_DISPATCH
        # extension.
        assert (
            _resolve_prompt_key(
                "urn_vault_personalization_studio", "suggest_layout"
            )
            == "urn_vault_personalization.suggest_layout"
        )

        # Unknown template_type raises — extension-point discipline
        # preserved for future Step 3+.
        with pytest.raises(PersonalizationStudioError):
            _resolve_prompt_key(
                "future_unknown_template", "suggest_layout"
            )

    def test_unknown_suggestion_type_canonically_rejected(self):
        from app.services.personalization_studio.ai_extraction_review import (
            _resolve_prompt_key,
        )
        from app.services.personalization_studio.instance_service import (
            PersonalizationStudioError,
        )

        with pytest.raises(PersonalizationStudioError):
            _resolve_prompt_key(
                "burial_vault_personalization_studio", "bogus_suggestion_type"
            )
