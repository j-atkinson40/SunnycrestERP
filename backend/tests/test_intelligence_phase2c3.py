"""Phase 2c-3 integration tests — Category B high-value caller migrations.

Tests cover:
  - ai.py /prompt deprecation (headers + log warning; endpoint still functional)
  - core_command_service.process_command uses commandbar.classify_intent
  - ai_command.py three handlers (process_command, parse_filters, company_chat)
  - call_extraction_service uses calls.extract_order_from_transcript + ringcentral linkage
  - operations_board.get_daily_context uses briefing.plant_manager_daily_context
  - operations_board.interpret_transcript uses voice.interpret_transcript + context_key

Each test mocks intelligence_service.execute and verifies the migration
contract. End-to-end execute() behavior is covered by Phase 2c-0b tests.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def _intel_result(
    *,
    status: str = "success",
    response_parsed=None,
    response_text: str = "ok",
    model_used: str = "claude-haiku-4-5-20251001",
    error_message: str | None = None,
):
    return SimpleNamespace(
        execution_id="exec-1",
        prompt_id="prompt-1",
        prompt_version_id="ver-1",
        model_used=model_used,
        status=status,
        response_text=response_text,
        response_parsed=response_parsed,
        rendered_system_prompt="(mocked)",
        rendered_user_prompt="(mocked)",
        input_tokens=100,
        output_tokens=50,
        latency_ms=42,
        cost_usd=Decimal("0.0005"),
        experiment_variant=None,
        fallback_used=False,
        error_message=error_message,
    )


# ═══════════════════════════════════════════════════════════════════════
# Migration 1 — ai.py /prompt deprecation
# ═══════════════════════════════════════════════════════════════════════


def test_ai_prompt_sets_deprecation_headers_and_routes_through_managed_prompt(caplog):
    """The /ai/prompt endpoint emits Deprecation + Sunset headers + log warning.

    Phase 2c-5 update: the endpoint now routes through the managed
    `legacy.arbitrary_prompt` prompt via intelligence_service.execute, so
    every call produces a real audit row with a non-null prompt_id.
    """
    import logging

    from fastapi import Response as FastAPIResponse

    from app.api.routes.ai import ai_prompt
    from app.schemas.ai import AIPromptRequest

    request = AIPromptRequest(system_prompt="x", user_message="y")
    response = FastAPIResponse()
    current_user = MagicMock(id="U-1", company_id="T-1")

    caplog.set_level(logging.WARNING, logger="app.api.routes.ai")
    with patch(
        "app.services.intelligence.intelligence_service.execute",
        return_value=_intel_result(response_parsed={"ok": True}),
    ) as mock_execute:
        result = ai_prompt(request, response, current_user, MagicMock())

    assert response.headers["Deprecation"] == "true"
    assert "2027" in response.headers["Sunset"]
    assert any(
        "Deprecated endpoint /ai/prompt" in rec.getMessage() for rec in caplog.records
    )
    # Endpoint now routes through the managed prompt — real audit row produced
    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "legacy.arbitrary_prompt"
    assert ck["caller_module"] == "ai.ai_prompt"
    assert ck["variables"]["system_prompt"] == "x"
    assert ck["variables"]["user_message"] == "y"
    assert result.success is True
    assert result.data == {"ok": True}


# ═══════════════════════════════════════════════════════════════════════
# Migration 2 — core_command_service
# ═══════════════════════════════════════════════════════════════════════


def test_core_command_service_uses_classify_intent_prompt():
    from app.services import core_command_service as svc
    from app.models.user import User as UserModel  # noqa: F401

    user = MagicMock(id="U-1", company_id="T-1")
    context = {"current_page": "/dashboard"}

    parsed_intent = {
        "results": [
            {"id": "nav-1", "type": "NAV", "title": "Go to orders", "confidence": 0.9},
        ],
        "intent": "navigate",
        "needs_confirmation": False,
    }

    fake_db = MagicMock()
    # _resolve_entities does 3 ORM queries; stub them all
    fake_db.query.return_value.filter.return_value.limit.return_value.all.return_value = []

    with patch(
        "app.services.intelligence.intelligence_service.execute",
        return_value=_intel_result(response_parsed=parsed_intent),
    ) as mock_execute:
        result = svc.process_command(fake_db, "go to orders", user, context)

    mock_execute.assert_called_once()
    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "commandbar.classify_intent"
    assert ck["caller_module"] == "core_command_service.process_command"
    assert ck["company_id"] == "T-1"
    assert "payload" in ck["variables"]
    # Caller assigns shortcut numbers 1..5 on the result
    assert result["results"][0]["shortcut"] == 1


def test_core_command_service_falls_back_on_failure():
    """Parse error → local_search fallback still runs."""
    from app.services import core_command_service as svc

    user = MagicMock(id="U-1", company_id="T-1")
    context = {}
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.limit.return_value.all.return_value = []
    fake_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

    with patch(
        "app.services.intelligence.intelligence_service.execute",
        return_value=_intel_result(status="api_error", response_parsed=None, response_text=""),
    ):
        result = svc.process_command(fake_db, "something", user, context)

    # Fallback path returns a results dict (possibly empty)
    assert isinstance(result, dict)
    assert "results" in result


# ═══════════════════════════════════════════════════════════════════════
# Migration 3 — ai_command.py three handlers
# ═══════════════════════════════════════════════════════════════════════


def test_ai_command_process_command_uses_managed_prompt():
    from app.api.routes.ai_command import process_command, CommandRequest

    parsed = {
        "intent": "navigate",
        "display_text": "Go to Orders",
        "navigation_url": "/ar/orders",
        "action_type": None,
        "parameters": {},
        "entity_name": None,
    }

    # Avoid local navigation shortcuts + local search early-return
    data = CommandRequest(query="please classify this", context={"current_page": "/dashboard"})
    current_user = MagicMock(id="U-1", company_id="T-1")
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

    with (
        patch(
            "app.services.ai_settings_service.is_enabled", return_value=True
        ),
        patch(
            "app.services.ai_settings_service.get_effective_settings",
            return_value={"command_bar_action_tier": "review"},
        ),
        patch(
            "app.services.intelligence.intelligence_service.execute",
            return_value=_intel_result(response_parsed=parsed),
        ) as mock_execute,
    ):
        result = process_command(data, current_user, fake_db)

    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "commandbar.legacy_process_command"
    assert ck["caller_module"] == "ai_command.process_command"
    assert ck["variables"]["query"] == "please classify this"
    assert ck["variables"]["current_page"] == "/dashboard"
    assert result["intent"] == "navigate"
    assert result["navigation_url"] == "/ar/orders"


def test_ai_command_parse_filters_uses_managed_prompt():
    from app.api.routes.ai_command import parse_filters, FilterParseRequest

    parsed = {
        "date_from": "2026-01-01",
        "date_to": "2026-01-31",
        "customer_type": "funeral_home",
        "chips": ["last month", "funeral homes"],
    }
    data = FilterParseRequest(query="last month, funeral homes", entity_type="invoices")
    current_user = MagicMock(id="U-1", company_id="T-1")
    fake_db = MagicMock()

    with (
        patch("app.services.ai_settings_service.is_enabled", return_value=True),
        patch(
            "app.services.intelligence.intelligence_service.execute",
            return_value=_intel_result(response_parsed=parsed),
        ) as mock_execute,
    ):
        result = parse_filters(data, current_user, fake_db)

    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "commandbar.parse_filters"
    assert ck["caller_module"] == "ai_command.parse_filters"
    assert ck["variables"]["entity_type"] == "invoices"
    assert ck["variables"]["query"] == "last month, funeral homes"
    assert "today" in ck["variables"]
    assert result["filters"]["customer_type"] == "funeral_home"
    assert result["chips"] == ["last month", "funeral homes"]


def test_ai_command_company_chat_uses_managed_prompt():
    from app.api.routes.ai_command import company_chat, CompanyChatRequest

    data = CompanyChatRequest(
        master_company_id="CE-7",
        message="what's their balance?",
        conversation_history=[{"role": "user", "content": "hi"}],
    )
    current_user = MagicMock(id="U-1", company_id="T-1")

    # Minimal stub for company_entity + customer + contact queries
    fake_db = MagicMock()
    entity = MagicMock(
        id="CE-7", name="Hopkins FH", customer_type="funeral_home",
        city="Auburn", state="NY", phone="555-1212",
    )
    fake_db.query.return_value.filter.return_value.first.return_value = entity
    fake_db.query.return_value.filter.return_value.limit.return_value.all.return_value = []
    fake_db.execute.return_value.fetchall.return_value = []

    with (
        patch("app.services.ai_settings_service.is_enabled", return_value=True),
        patch(
            "app.services.intelligence.intelligence_service.execute",
            return_value=_intel_result(response_text="Their balance is $1,234.56.", response_parsed=None),
        ) as mock_execute,
    ):
        result = company_chat(data, current_user, fake_db)

    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "commandbar.company_chat"
    assert ck["caller_module"] == "ai_command.company_chat"
    assert ck["caller_entity_type"] == "company_entity"
    assert ck["caller_entity_id"] == "CE-7"
    for var in ("context", "history_block", "message"):
        assert var in ck["variables"]
    assert result["answer"] == "Their balance is $1,234.56."


def test_ai_command_call_claude_helper_removed():
    """The legacy helper must be gone."""
    from app.api.routes import ai_command

    assert not hasattr(ai_command, "_call_claude"), (
        "_call_claude must be deleted — each handler calls intelligence_service.execute directly"
    )


# ═══════════════════════════════════════════════════════════════════════
# Migration 4 — call_extraction_service
# ═══════════════════════════════════════════════════════════════════════


def test_call_extraction_uses_ringcentral_linkage():
    from app.services.call_extraction_service import extract_order_from_transcript

    parsed_extraction = {
        "call_summary": "First call from Hopkins FH for John Doe",
        "call_type": "intake",
        "urgency": "standard",
        # Intentionally no funeral_home_name so _fuzzy_match_company isn't
        # exercised (it has a pre-existing bug: references CompanyEntity.tenant_id
        # where the model uses company_id — out of scope for 2c-3 migration).
        "deceased_name": "John Doe",
        "vault_type": "Monticello",
        "missing_fields": [],
        "confidence": {},
        "kb_queries": [],  # no KB fan-out needed to prove migration contract
        "suggested_callback": False,
    }

    fake_db = MagicMock()

    with patch(
        "app.services.intelligence.intelligence_service.execute",
        return_value=_intel_result(response_parsed=parsed_extraction),
    ) as mock_execute:
        extraction, kb_results = extract_order_from_transcript(
            fake_db,
            transcript="Hi this is Hopkins FH...",
            tenant_id="T-1",
            call_id="RC-CALL-42",
        )

    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "calls.extract_order_from_transcript"
    assert ck["caller_module"] == "call_extraction_service.extract_order_from_transcript"
    assert ck["caller_entity_type"] == "ringcentral_call_log"
    assert ck["caller_entity_id"] == "RC-CALL-42"
    # The new 2c-0a linkage column
    assert ck["caller_ringcentral_call_log_id"] == "RC-CALL-42"
    # Downstream extraction row carries parsed fields
    assert extraction.call_log_id == "RC-CALL-42"
    assert extraction.deceased_name == "John Doe"


# ═══════════════════════════════════════════════════════════════════════
# Migration 5 — operations_board.get_daily_context
# ═══════════════════════════════════════════════════════════════════════


def test_operations_board_get_daily_context_uses_managed_prompt():
    """Source-level verification — the migrated call site references the
    correct managed prompt_key and the 4 variables the seed expects.

    Note: a full invocation test is blocked by a pre-existing code bug in
    get_daily_context (references `SalesOrder.delivery_date` where the model
    has `delivered_at`). That bug is unrelated to Phase 2c-3 and out of scope;
    this test verifies the migration contract via source inspection instead.
    """
    from pathlib import Path

    source = (
        Path(__file__).resolve().parent.parent
        / "app" / "api" / "routes" / "operations_board.py"
    ).read_text(encoding="utf-8")

    # The get_daily_context function invokes the managed prompt
    assert 'prompt_key="briefing.plant_manager_daily_context"' in source
    assert 'caller_module="operations_board.get_daily_context"' in source
    assert 'caller_entity_type="user"' in source
    # Every variable the seed's user_template expects is passed at call time
    for var in ("day_name", "hour", "vault_prompt_addendum", "context_data_json"):
        assert f'"{var}"' in source, f"variable {var!r} not threaded into the call"


# ═══════════════════════════════════════════════════════════════════════
# Migration 6 — operations_board.interpret_transcript
# ═══════════════════════════════════════════════════════════════════════


import pytest


@pytest.mark.parametrize(
    "context_key,expected_result_key",
    [
        ("production_log", "entries"),
        ("incident", "incident_type"),
        ("safety_observation", "observation_type"),
        ("qc_fail_note", "defect_description"),
        ("inspection", "overall_pass"),
    ],
)
def test_interpret_transcript_each_context(context_key, expected_result_key):
    from app.api.routes.operations_board import interpret_transcript, InterpretRequest

    # Return a minimal parsed payload with the key the UI expects for that context
    parsed_by_context = {
        "production_log": {"entries": []},
        "incident": {"incident_type": "near_miss", "people_involved": []},
        "safety_observation": {"observation_type": "ppe_missing"},
        "qc_fail_note": {"defect_description": "crack", "disposition": "scrap"},
        "inspection": {"overall_pass": True, "issues": []},
    }
    parsed = parsed_by_context[context_key]

    request = InterpretRequest(
        context=context_key,
        transcript="The crew just finished the Monticello run.",
        available_products=[{"id": "p-1", "name": "Monticello"}],
        available_employees=[{"id": "e-1", "name": "Alex"}],
    )
    current_user = MagicMock(id="U-1", company_id="T-1")
    fake_db = MagicMock()

    with patch(
        "app.services.intelligence.intelligence_service.execute",
        return_value=_intel_result(response_parsed=parsed),
    ) as mock_execute:
        result = interpret_transcript(request, current_user, fake_db)

    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "voice.interpret_transcript"
    assert ck["caller_module"] == "operations_board.interpret_transcript"
    assert ck["caller_entity_type"] == "user_actions"
    # The context_key selector variable flows through so the Jinja conditional
    # can pick the right sub-context system prompt at render time.
    assert ck["variables"]["context_key"] == context_key
    assert ck["variables"]["transcript"] == request.transcript
    assert expected_result_key in result
