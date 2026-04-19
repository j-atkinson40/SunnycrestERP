"""Phase 2c-0b tests — multimodal (vision) support in the Intelligence layer.

Covers:
  Migration shape — new columns on intelligence_prompt_versions
  Renderer — text vs vision return shapes
  Hashing — deterministic for same image+text, different for different images
  Content block validation — malformed blocks raise IntelligenceError
  execute() — vision prompt with image/document, guards for wrong-mode calls
  Model router — is_vision_route helper
  Rendered user serialization — vision payload redacted for storage
"""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy import JSON, create_engine, inspect
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.database import Base
from app.models.intelligence import (
    IntelligenceExecution,
    IntelligenceModelRoute,
    IntelligencePrompt,
    IntelligencePromptVersion,
)
from app.services.intelligence import intelligence_service, model_router, prompt_renderer
from app.services.intelligence.intelligence_service import (
    IntelligenceError,
    _validate_content_blocks,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:")

    from app.models.agent import AgentJob  # noqa: F401
    from app.models.company import Company  # noqa: F401
    from app.models.role import Role  # noqa: F401
    from app.models.user import User  # noqa: F401
    from app.models.workflow import WorkflowRun, WorkflowRunStep  # noqa: F401

    tables_needed = [
        "companies",
        "roles",
        "users",
        "agent_jobs",
        "workflows",
        "workflow_runs",
        "workflow_run_steps",
        "intelligence_prompts",
        "intelligence_prompt_versions",
        "intelligence_model_routes",
        "intelligence_experiments",
        "intelligence_conversations",
        "intelligence_executions",
        "intelligence_messages",
    ]
    for name in ("price_list_imports", "fh_cases", "ringcentral_call_log", "kb_documents"):
        if name in Base.metadata.tables:
            tables_needed.append(name)
    tables = [Base.metadata.tables[t] for t in tables_needed if t in Base.metadata.tables]

    jsonb_swaps: list[tuple] = []
    for t in tables:
        for col in t.columns:
            if isinstance(col.type, JSONB):
                jsonb_swaps.append((col, col.type))
                col.type = JSON()

    Base.metadata.create_all(eng, tables=tables)
    for col, original in jsonb_swaps:
        col.type = original
    return eng


@pytest.fixture
def db(engine):
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn)
    yield session
    session.close()
    trans.rollback()
    conn.close()


@pytest.fixture
def company_id(db):
    from app.models.company import Company

    c = Company(id=str(uuid.uuid4()), name="T", slug="t", is_active=True)
    db.add(c)
    db.flush()
    return c.id


def _seed_routes(db):
    db.add(
        IntelligenceModelRoute(
            route_key="simple",
            primary_model="claude-haiku-4-5-20251001",
            fallback_model="claude-haiku-4-5-20251001",
            input_cost_per_million=Decimal("1.00"),
            output_cost_per_million=Decimal("5.00"),
            max_tokens_default=1024,
            temperature_default=0.2,
            is_active=True,
        )
    )
    db.add(
        IntelligenceModelRoute(
            route_key="vision",
            primary_model="claude-sonnet-4-6",
            fallback_model="claude-sonnet-4-6",
            input_cost_per_million=Decimal("3.00"),
            output_cost_per_million=Decimal("15.00"),
            max_tokens_default=8192,
            temperature_default=0.3,
            is_active=True,
        )
    )
    db.flush()


def _seed_vision_prompt(db, prompt_key="test.vision", content_type="image"):
    prompt = IntelligencePrompt(
        id=str(uuid.uuid4()),
        company_id=None,
        prompt_key=prompt_key,
        display_name=prompt_key,
        domain="test",
    )
    db.add(prompt)
    db.flush()
    version = IntelligencePromptVersion(
        id=str(uuid.uuid4()),
        prompt_id=prompt.id,
        version_number=1,
        system_prompt="You extract fields from an image.",
        user_template="Extract payer and amount.",
        variable_schema={},
        model_preference="vision",
        temperature=0.3,
        max_tokens=500,
        force_json=False,
        supports_vision=True,
        vision_content_type=content_type,
        status="active",
    )
    db.add(version)
    db.flush()
    return prompt, version


def _seed_text_prompt(db, prompt_key="test.text"):
    prompt = IntelligencePrompt(
        id=str(uuid.uuid4()),
        company_id=None,
        prompt_key=prompt_key,
        display_name=prompt_key,
        domain="test",
    )
    db.add(prompt)
    db.flush()
    version = IntelligencePromptVersion(
        id=str(uuid.uuid4()),
        prompt_id=prompt.id,
        version_number=1,
        system_prompt="Hello",
        user_template="Hi",
        variable_schema={},
        model_preference="simple",
        status="active",
    )
    db.add(version)
    db.flush()
    return prompt, version


def _fake_image_block(payload: bytes = b"fake-image-bytes", media_type: str = "image/jpeg") -> dict:
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": base64.b64encode(payload).decode("ascii"),
        },
    }


def _fake_pdf_block(payload: bytes = b"%PDF-1.4 fake") -> dict:
    return {
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": "application/pdf",
            "data": base64.b64encode(payload).decode("ascii"),
        },
    }


def _mock_client_factory(captured_calls: list | None = None):
    """Mock Anthropic client that records the arguments of messages.create."""

    def factory():
        client = MagicMock()
        msg = MagicMock()
        block = MagicMock()
        block.type = "text"
        block.text = '{"payer_name": "ACME", "amount": 100.0, "check_number": "1234", "check_date": "2026-04-18"}'
        msg.content = [block]
        usage = MagicMock()
        usage.input_tokens = 50
        usage.output_tokens = 25
        msg.usage = usage

        def _create(**kwargs):
            if captured_calls is not None:
                captured_calls.append(kwargs)
            return msg

        client.messages.create.side_effect = _create
        return client

    return factory


# ═══════════════════════════════════════════════════════════════════════
# Migration / model shape
# ═══════════════════════════════════════════════════════════════════════


def test_model_has_vision_columns():
    """IntelligencePromptVersion declares supports_vision + vision_content_type."""
    mapper = inspect(IntelligencePromptVersion)
    names = {c.key for c in mapper.columns}
    assert "supports_vision" in names
    assert "vision_content_type" in names


# ═══════════════════════════════════════════════════════════════════════
# Renderer — vision vs text return shapes
# ═══════════════════════════════════════════════════════════════════════


def test_renderer_returns_text_for_text_prompt(db):
    _, version = _seed_text_prompt(db)
    system, user_content = prompt_renderer.render(version, {})
    assert isinstance(user_content, str)
    assert user_content == "Hi"


def test_renderer_returns_blocks_for_vision_prompt(db):
    _, version = _seed_vision_prompt(db)
    system, user_content = prompt_renderer.render(version, {})
    assert isinstance(user_content, list)
    assert user_content[0]["type"] == "text"
    assert user_content[0]["text"] == "Extract payer and amount."


def test_renderer_empty_vision_template_returns_empty_list(db):
    _, version = _seed_vision_prompt(db)
    version.user_template = ""  # edge case: prompt only has system + content blocks
    system, user_content = prompt_renderer.render(version, {})
    assert user_content == []


# ═══════════════════════════════════════════════════════════════════════
# Hash canonicalization
# ═══════════════════════════════════════════════════════════════════════


def test_input_hash_deterministic_for_vision():
    """Same image + text → same hash across calls."""
    block = _fake_image_block(b"stable-image-bytes")
    payload = [{"type": "text", "text": "caption"}, block]
    h1 = prompt_renderer.compute_input_hash("sys", payload, "vision")
    # Use a new dict with the same data to confirm dict identity doesn't matter
    payload2 = [{"type": "text", "text": "caption"}, _fake_image_block(b"stable-image-bytes")]
    h2 = prompt_renderer.compute_input_hash("sys", payload2, "vision")
    assert h1 == h2


def test_input_hash_different_for_different_images():
    payload_a = [{"type": "text", "text": "caption"}, _fake_image_block(b"image-a")]
    payload_b = [{"type": "text", "text": "caption"}, _fake_image_block(b"image-b")]
    h_a = prompt_renderer.compute_input_hash("sys", payload_a, "vision")
    h_b = prompt_renderer.compute_input_hash("sys", payload_b, "vision")
    assert h_a != h_b


def test_input_hash_text_and_vision_are_distinct():
    """Same logical caption as text vs. inside a block produces different hashes."""
    h_text = prompt_renderer.compute_input_hash("sys", "caption", "vision")
    h_blocks = prompt_renderer.compute_input_hash(
        "sys", [{"type": "text", "text": "caption"}], "vision"
    )
    assert h_text != h_blocks


# ═══════════════════════════════════════════════════════════════════════
# Content block validation
# ═══════════════════════════════════════════════════════════════════════


def test_valid_image_block_passes():
    _validate_content_blocks([_fake_image_block()])


def test_valid_document_block_passes():
    _validate_content_blocks([_fake_pdf_block()])


def test_non_list_blocks_raises():
    with pytest.raises(IntelligenceError, match="content_blocks must be a list"):
        _validate_content_blocks({"type": "image"})  # type: ignore[arg-type]


def test_wrong_block_type_raises():
    with pytest.raises(IntelligenceError, match="must be 'image' or 'document'"):
        _validate_content_blocks([{"type": "video", "source": {}}])


def test_missing_source_raises():
    with pytest.raises(IntelligenceError, match="source must be a dict"):
        _validate_content_blocks([{"type": "image"}])


def test_wrong_source_type_raises():
    with pytest.raises(IntelligenceError, match="source.type must be 'base64'"):
        _validate_content_blocks(
            [{"type": "image", "source": {"type": "url", "url": "https://..."}}]
        )


def test_disallowed_image_media_type_raises():
    with pytest.raises(IntelligenceError, match="not an allowed image type"):
        _validate_content_blocks(
            [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/tiff", "data": "abc"},
                }
            ]
        )


def test_disallowed_document_media_type_raises():
    with pytest.raises(IntelligenceError, match="not an allowed document type"):
        _validate_content_blocks(
            [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/msword",
                        "data": "abc",
                    },
                }
            ]
        )


def test_empty_data_raises():
    with pytest.raises(IntelligenceError, match="non-empty base64 string"):
        _validate_content_blocks(
            [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": ""},
                }
            ]
        )


# ═══════════════════════════════════════════════════════════════════════
# execute() — end-to-end with content_blocks
# ═══════════════════════════════════════════════════════════════════════


def test_execute_with_image_block_routes_via_vision(db, company_id):
    _seed_routes(db)
    _, _ = _seed_vision_prompt(db)
    captured: list = []
    result = intelligence_service.execute(
        db,
        prompt_key="test.vision",
        variables={},
        company_id=company_id,
        caller_module="test",
        content_blocks=[_fake_image_block(b"check-image")],
        client_factory=_mock_client_factory(captured),
    )
    assert result.status == "success"
    assert result.model_used == "claude-sonnet-4-6"  # vision route
    # Verify the request shape passed to Anthropic
    assert len(captured) == 1
    call = captured[0]
    assert call["model"] == "claude-sonnet-4-6"
    # messages[0].content is a list with [text, image]
    content = call["messages"][0]["content"]
    assert isinstance(content, list)
    types = [b["type"] for b in content]
    assert "image" in types
    assert content[0]["type"] == "text"
    # Audit row persisted with redacted blob
    row = db.query(IntelligenceExecution).filter_by(id=result.execution_id).one()
    stored = row.rendered_user_prompt
    assert isinstance(stored, str)
    assert "data_sha256" in stored
    # The raw base64 of the fake image should NOT appear in storage
    b64 = base64.b64encode(b"check-image").decode("ascii")
    assert b64 not in stored


def test_execute_with_document_block(db, company_id):
    _seed_routes(db)
    _, _ = _seed_vision_prompt(db, prompt_key="test.pdf", content_type="document")
    captured: list = []
    result = intelligence_service.execute(
        db,
        prompt_key="test.pdf",
        variables={},
        company_id=company_id,
        caller_module="test",
        content_blocks=[_fake_pdf_block(b"%PDF fake content")],
        client_factory=_mock_client_factory(captured),
    )
    assert result.status == "success"
    content = captured[0]["messages"][0]["content"]
    assert any(b["type"] == "document" for b in content)


def test_vision_prompt_without_blocks_raises(db, company_id):
    _seed_routes(db)
    _, _ = _seed_vision_prompt(db)
    with pytest.raises(IntelligenceError, match="supports_vision=True"):
        intelligence_service.execute(
            db,
            prompt_key="test.vision",
            variables={},
            company_id=company_id,
            caller_module="test",
            # content_blocks intentionally omitted
            client_factory=_mock_client_factory(),
        )


def test_text_prompt_with_blocks_raises(db, company_id):
    _seed_routes(db)
    _, _ = _seed_text_prompt(db)
    with pytest.raises(IntelligenceError, match="supports_vision=False"):
        intelligence_service.execute(
            db,
            prompt_key="test.text",
            variables={},
            company_id=company_id,
            caller_module="test",
            content_blocks=[_fake_image_block()],
            client_factory=_mock_client_factory(),
        )


def test_execute_invalid_content_block_raises(db, company_id):
    _seed_routes(db)
    _, _ = _seed_vision_prompt(db)
    with pytest.raises(IntelligenceError, match="source must be a dict"):
        intelligence_service.execute(
            db,
            prompt_key="test.vision",
            variables={},
            company_id=company_id,
            caller_module="test",
            content_blocks=[{"type": "image"}],  # missing source
            client_factory=_mock_client_factory(),
        )


# ═══════════════════════════════════════════════════════════════════════
# Model router helper
# ═══════════════════════════════════════════════════════════════════════


def test_is_vision_route():
    assert model_router.is_vision_route("vision") is True
    assert model_router.is_vision_route("simple") is False
    assert model_router.is_vision_route("extraction") is False
    assert model_router.is_vision_route("chat") is False


# ═══════════════════════════════════════════════════════════════════════
# Rendered user serialization
# ═══════════════════════════════════════════════════════════════════════


def test_serialize_user_for_storage_text_passthrough():
    from app.services.intelligence.intelligence_service import _serialize_user_for_storage

    assert _serialize_user_for_storage("hello") == "hello"


def test_serialize_user_for_storage_redacts_image_data():
    from app.services.intelligence.intelligence_service import _serialize_user_for_storage

    img = _fake_image_block(b"very-secret-image-bytes")
    payload = [{"type": "text", "text": "caption"}, img]
    stored = _serialize_user_for_storage(payload)
    data_blob = img["source"]["data"]
    # Raw base64 data must not appear in storage
    assert data_blob not in stored
    # But the sha256 hash + media_type + bytes_len should
    parsed = json.loads(stored)
    assert parsed[0]["type"] == "text"
    assert parsed[0]["text"] == "caption"
    assert parsed[1]["type"] == "image"
    assert parsed[1]["media_type"] == "image/jpeg"
    assert parsed[1]["bytes_len"] == len(data_blob)
    expected_sha = hashlib.sha256(data_blob.encode("utf-8")).hexdigest()
    assert parsed[1]["data_sha256"] == expected_sha
