"""Single end-to-end integration test for intelligence_service.execute().

Uses a mocked Anthropic client so no real API call is made. Verifies the full
pipeline: prompt lookup → render → route → call → parse → persist.
"""

import json
import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy import JSON, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.database import Base
from app.models.intelligence import (
    IntelligenceExecution,
    IntelligenceModelRoute,
    IntelligencePrompt,
    IntelligencePromptVersion,
)
from app.services.intelligence import intelligence_service


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

    c = Company(id=str(uuid.uuid4()), name="Test", slug="test", is_active=True)
    db.add(c)
    db.flush()
    return c.id


def _seed_route_and_prompt(db):
    db.add(
        IntelligenceModelRoute(
            route_key="extraction",
            primary_model="claude-sonnet-4-6",
            fallback_model="claude-haiku-4-5-20251001",
            input_cost_per_million=Decimal("3.00"),
            output_cost_per_million=Decimal("15.00"),
            max_tokens_default=4096,
            temperature_default=0.2,
            is_active=True,
        )
    )
    prompt = IntelligencePrompt(
        id=str(uuid.uuid4()),
        company_id=None,
        prompt_key="test.extract",
        display_name="Test extract",
        domain="extraction",
    )
    db.add(prompt)
    db.flush()
    version = IntelligencePromptVersion(
        id=str(uuid.uuid4()),
        prompt_id=prompt.id,
        version_number=1,
        system_prompt="You are a test extractor for {{ subject }}.",
        user_template="Extract from: {{ transcript }}",
        variable_schema={
            "subject": {"required": True, "type": "string"},
            "transcript": {"required": True, "type": "string"},
        },
        response_schema={"required": ["name", "age"]},
        model_preference="extraction",
        temperature=0.2,
        max_tokens=1024,
        force_json=True,
        status="active",
    )
    db.add(version)
    db.flush()
    return prompt, version


def _mock_client_factory(response_json: dict, *, input_tokens=45, output_tokens=12):
    """Build a client factory that returns a stub whose messages.create returns
    an object mimicking anthropic.types.Message."""

    def factory():
        client = MagicMock()

        message = MagicMock()
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = json.dumps(response_json)
        message.content = [text_block]

        usage = MagicMock()
        usage.input_tokens = input_tokens
        usage.output_tokens = output_tokens
        message.usage = usage

        client.messages.create.return_value = message
        return client

    return factory


def test_execute_end_to_end_records_full_audit_row(db, company_id):
    """End-to-end: render, call (mocked), parse, persist, cost-compute."""
    prompt, version = _seed_route_and_prompt(db)

    result = intelligence_service.execute(
        db,
        prompt_key="test.extract",
        variables={"subject": "funeral case", "transcript": "John Doe, 72 years old."},
        company_id=company_id,
        caller_module="test_integration",
        caller_entity_type="funeral_case",
        caller_entity_id="FC-2026-0001",
        client_factory=_mock_client_factory({"name": "John Doe", "age": 72}),
    )

    # ── result object ─────────────────────────────────────────────────
    assert result.status == "success"
    assert result.response_parsed == {"name": "John Doe", "age": 72}
    assert result.prompt_id == prompt.id
    assert result.prompt_version_id == version.id
    assert result.model_used == "claude-sonnet-4-6"
    assert result.input_tokens == 45
    assert result.output_tokens == 12
    assert result.fallback_used is False
    # Cost: 3.00 * 45/1M + 15.00 * 12/1M = 0.000135 + 0.00018 = 0.000315
    assert result.cost_usd == Decimal("0.000315")

    # ── rendered prompts reflect variable substitution ───────────────
    assert "funeral case" in result.rendered_system_prompt
    assert "John Doe" in result.rendered_user_prompt

    # ── audit row persisted with full caller linkage ─────────────────
    row = db.query(IntelligenceExecution).filter_by(id=result.execution_id).first()
    assert row is not None
    assert row.company_id == company_id
    assert row.prompt_id == prompt.id
    assert row.prompt_version_id == version.id
    assert row.model_used == "claude-sonnet-4-6"
    assert row.model_preference == "extraction"
    assert row.response_parsed == {"name": "John Doe", "age": 72}
    assert row.caller_module == "test_integration"
    assert row.caller_entity_type == "funeral_case"
    assert row.caller_entity_id == "FC-2026-0001"
    assert row.input_hash is not None
    assert len(row.input_hash) == 64  # SHA-256 hex
    assert row.cost_usd == Decimal("0.000315")
    assert row.status == "success"
    assert row.latency_ms is not None
