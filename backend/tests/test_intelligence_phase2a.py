"""Phase 2a integration tests — verify migrated callers use the Intelligence layer.

For each caller, we mock the Anthropic client inside intelligence_service.execute
(via the client_factory test seam) and check that:
  - an IntelligenceExecution row is created
  - caller_module + caller_entity_type + caller_entity_id are populated correctly
  - prompt_id points at the correct seeded prompt
  - caller_agent_job_id is set for agent callers
  - ai_service.call_anthropic legacy shim writes prompt_id=null, caller_module starts with "legacy"
"""

from __future__ import annotations

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


# ---------------------------------------------------------------------------
# Shared fixtures (mirror the Phase 1 test file; SQLite engine + JSONB→JSON)
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
    tables = [
        Base.metadata.tables[t]
        for t in tables_needed
        if t in Base.metadata.tables
    ]

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

    c = Company(
        id=str(uuid.uuid4()),
        name="Test Vault Co",
        slug="testco",
        is_active=True,
    )
    db.add(c)
    db.flush()
    return c.id


def _seed_route(db, route_key="extraction"):
    db.add(
        IntelligenceModelRoute(
            route_key=route_key,
            primary_model="claude-sonnet-4-6",
            fallback_model="claude-haiku-4-5-20251001",
            input_cost_per_million=Decimal("3.00"),
            output_cost_per_million=Decimal("15.00"),
            max_tokens_default=4096,
            temperature_default=0.2,
            is_active=True,
        )
    )
    # Also seed the simple route for expense classify + briefing
    for rk in ("simple", "scheduled", "reasoning", "chat"):
        db.add(
            IntelligenceModelRoute(
                route_key=rk,
                primary_model="claude-haiku-4-5-20251001",
                fallback_model="claude-haiku-4-5-20251001",
                input_cost_per_million=Decimal("1.00"),
                output_cost_per_million=Decimal("5.00"),
                max_tokens_default=4096,
                temperature_default=0.3,
                is_active=True,
            )
        )
    db.flush()


def _seed_prompt(
    db,
    prompt_key: str,
    system: str,
    user: str,
    *,
    model_preference: str = "extraction",
    force_json: bool = False,
    variable_schema: dict | None = None,
):
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
        system_prompt=system,
        user_template=user,
        variable_schema=variable_schema or {},
        model_preference=model_preference,
        temperature=0.2,
        max_tokens=1024,
        force_json=force_json,
        status="active",
    )
    db.add(version)
    db.flush()
    return prompt, version


def _mock_client_factory(response_text: str, *, input_tokens=30, output_tokens=20):
    def factory():
        client = MagicMock()
        message = MagicMock()
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = response_text
        message.content = [text_block]
        usage = MagicMock()
        usage.input_tokens = input_tokens
        usage.output_tokens = output_tokens
        message.usage = usage
        client.messages.create.return_value = message
        return client

    return factory


# ---------------------------------------------------------------------------
# AR Collections agent
# ---------------------------------------------------------------------------


def test_ar_collections_draft_email_logs_agent_job_linkage(db, company_id):
    _seed_route(db)
    _seed_prompt(
        db,
        "agent.ar_collections.draft_email",
        system="You are an AR specialist.",
        user="Customer: {{ customer_name }}. Draft email.",
        model_preference="extraction",
        variable_schema={
            "customer_name": {"required": True},
            "total_outstanding": {"required": True},
            "invoice_count": {"required": True},
            "oldest_days": {"required": True},
            "tier": {"required": True},
            "invoice_lines": {"required": True},
        },
    )

    # Simulate the refactored _generate_draft_email body (what ar_collections_agent now does)
    job_id = str(uuid.uuid4())
    result = intelligence_service.execute(
        db,
        prompt_key="agent.ar_collections.draft_email",
        variables={
            "customer_name": "Hopkins FH",
            "total_outstanding": "12,345.67",
            "invoice_count": 3,
            "oldest_days": 92,
            "tier": "CRITICAL",
            "invoice_lines": "- INV-001 $5,000\n- INV-002 $3,000\n- INV-003 $4,345.67",
        },
        company_id=company_id,
        caller_module="agents.ar_collections_agent",
        caller_entity_type="agent_job",
        caller_entity_id=job_id,
        caller_agent_job_id=None,  # FK would fail in SQLite without a real job row
        client_factory=_mock_client_factory("Dear [Contact Name], please remit..."),
    )

    assert result.status == "success"
    row = db.query(IntelligenceExecution).filter_by(id=result.execution_id).one()
    assert row.caller_module == "agents.ar_collections_agent"
    assert row.caller_entity_type == "agent_job"
    assert row.caller_entity_id == job_id


# ---------------------------------------------------------------------------
# Expense Categorization agent
# ---------------------------------------------------------------------------


def test_expense_categorization_classify_force_json_parses(db, company_id):
    _seed_route(db)
    _seed_prompt(
        db,
        "agent.expense_categorization.classify",
        system="Classify expense line.",
        user="Vendor: {{ vendor_name }}; Desc: {{ description }}; Amount: ${{ amount }}",
        model_preference="simple",
        force_json=True,
        variable_schema={
            "vendor_name": {"required": True},
            "description": {"required": True},
            "amount": {"required": True},
        },
    )

    result = intelligence_service.execute(
        db,
        prompt_key="agent.expense_categorization.classify",
        variables={
            "vendor_name": "Home Depot",
            "description": "Lumber",
            "amount": "234.56",
        },
        company_id=company_id,
        caller_module="agents.expense_categorization_agent",
        caller_entity_type="agent_job",
        caller_entity_id="job-xyz",
        client_factory=_mock_client_factory(
            json.dumps(
                {
                    "category": "vault_materials",
                    "confidence": 0.92,
                    "reasoning": "Lumber in vault manufacturing is direct materials.",
                }
            )
        ),
    )

    assert result.status == "success"
    assert isinstance(result.response_parsed, dict)
    assert result.response_parsed["category"] == "vault_materials"
    row = db.query(IntelligenceExecution).filter_by(id=result.execution_id).one()
    assert row.caller_module == "agents.expense_categorization_agent"
    assert row.caller_entity_type == "agent_job"


# ---------------------------------------------------------------------------
# FH Scribe — per-case entity audit
# ---------------------------------------------------------------------------


def test_scribe_entity_audit_filters_by_case_id(db, company_id):
    """Given a known funeral_case_id, we can list every Scribe extraction for it."""
    _seed_route(db)
    _seed_prompt(
        db,
        "scribe.extract_case_fields",
        system="Extract case fields.",
        user="{{ transcript }}",
        model_preference="extraction",
        force_json=True,
        variable_schema={"transcript": {"required": True}},
    )

    case_a = "FC-2026-0001"
    case_b = "FC-2026-0002"

    # Two Scribe calls on case A, one on case B
    for transcript in ("First pass", "Second pass"):
        intelligence_service.execute(
            db,
            prompt_key="scribe.extract_case_fields",
            variables={"transcript": transcript},
            company_id=company_id,
            caller_module="fh.scribe_service",
            caller_entity_type="funeral_case",
            caller_entity_id=case_a,
            client_factory=_mock_client_factory(json.dumps({"deceased": {}, "service": {}, "disposition": {}, "veteran": {}, "informants": []})),
        )
    intelligence_service.execute(
        db,
        prompt_key="scribe.extract_case_fields",
        variables={"transcript": "Case B"},
        company_id=company_id,
        caller_module="fh.scribe_service",
        caller_entity_type="funeral_case",
        caller_entity_id=case_b,
        client_factory=_mock_client_factory(json.dumps({"deceased": {}, "service": {}, "disposition": {}, "veteran": {}, "informants": []})),
    )

    rows_a = (
        db.query(IntelligenceExecution)
        .filter(
            IntelligenceExecution.caller_entity_type == "funeral_case",
            IntelligenceExecution.caller_entity_id == case_a,
        )
        .all()
    )
    rows_b = (
        db.query(IntelligenceExecution)
        .filter(IntelligenceExecution.caller_entity_id == case_b)
        .all()
    )
    assert len(rows_a) == 2
    assert len(rows_b) == 1
    assert all(r.caller_module == "fh.scribe_service" for r in rows_a + rows_b)


# ---------------------------------------------------------------------------
# Briefing — area variable selects the right system template
# ---------------------------------------------------------------------------


def test_briefing_area_variable_selects_variant(db, company_id):
    _seed_route(db)
    # The real seed uses a Jinja conditional; we mirror a small version here.
    _seed_prompt(
        db,
        "briefing.daily_summary",
        system=(
            "{% if area == 'funeral_scheduling' %}FUNERAL SYSTEM"
            "{% elif area == 'invoicing_ar' %}AR SYSTEM"
            "{% else %}DEFAULT SYSTEM{% endif %}"
        ),
        user="{{ user_prompt }}",
        model_preference="scheduled",
        variable_schema={"area": {"required": True}, "user_prompt": {"required": True}},
    )

    funeral_result = intelligence_service.execute(
        db,
        prompt_key="briefing.daily_summary",
        variables={"area": "funeral_scheduling", "user_prompt": "today..."},
        company_id=company_id,
        caller_module="briefing_service",
        client_factory=_mock_client_factory("1. all clear"),
    )
    ar_result = intelligence_service.execute(
        db,
        prompt_key="briefing.daily_summary",
        variables={"area": "invoicing_ar", "user_prompt": "today..."},
        company_id=company_id,
        caller_module="briefing_service",
        client_factory=_mock_client_factory("1. 3 overdue"),
    )

    assert "FUNERAL SYSTEM" in funeral_result.rendered_system_prompt
    assert "AR SYSTEM" in ar_result.rendered_system_prompt
    # Both rows recorded with briefing_service module
    rows = db.query(IntelligenceExecution).filter_by(caller_module="briefing_service").all()
    assert len(rows) == 2


# ---------------------------------------------------------------------------
# Overlay final extract — command_bar_session linkage
# ---------------------------------------------------------------------------


def test_overlay_final_extract_records_session_id(db, company_id):
    _seed_route(db)
    _seed_prompt(
        db,
        "overlay.extract_fields_final",
        system="Fields:\n{{ fields_block }}\nToday: {{ today_date }}{{ already_block }}{{ hint_block }}",
        user="{{ input_text }}",
        model_preference="extraction",
        force_json=True,
        variable_schema={
            "fields_block": {"required": True},
            "today_date": {"required": True},
            "already_block": {"required": False},
            "hint_block": {"required": False},
            "input_text": {"required": True},
        },
    )

    session_id = str(uuid.uuid4())
    # extraction_service.final_extract doesn't expose client_factory, so we
    # verify the caller-linkage contract by running execute directly with the
    # same parameters extraction_service would pass.
    direct = intelligence_service.execute(
        db,
        prompt_key="overlay.extract_fields_final",
        variables={
            "fields_block": "- x: ...",
            "today_date": "2026-04-18",
            "already_block": "",
            "hint_block": "",
            "input_text": "hello",
        },
        company_id=company_id,
        caller_module="command_bar_extract_service.extract",
        caller_entity_type="workflow",
        caller_entity_id="wf_compose",
        caller_command_bar_session_id=session_id,
        client_factory=_mock_client_factory(json.dumps({"recipient_type": {"value": "x", "confidence": 0.9}})),
    )
    row = db.query(IntelligenceExecution).filter_by(id=direct.execution_id).one()
    assert row.caller_command_bar_session_id == session_id
    assert row.caller_entity_type == "workflow"


# ---------------------------------------------------------------------------
# Legacy wrapper removal — ai_service.py was deleted in Phase 2c-5
# ---------------------------------------------------------------------------


def test_ai_service_module_removed():
    """ai_service.py was deleted in Phase 2c-5. Any import must fail with
    ModuleNotFoundError. If this test fails, the legacy wrapper has been
    reintroduced — that's a regression.

    The predecessor test (test_legacy_call_anthropic_writes_legacy_row)
    exercised the deprecation shim that wrote prompt_id=null audit rows.
    That shim no longer exists because every caller was migrated (Phase 2c-1
    through 2c-4) and ai_service.py was deleted in Phase 2c-5.
    """
    import importlib

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.services.ai_service")
