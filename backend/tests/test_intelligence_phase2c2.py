"""Phase 2c-2 integration tests — 9 Tier 2 caller migrations (10 tests).

Each test mocks `intelligence_service.execute` and verifies the caller threads
the right `prompt_key` + caller linkage through. Full execute() semantics are
covered by Phase 2c-0b tests; here we're verifying the migration contract.
"""

from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════════
# Shared helpers
# ═══════════════════════════════════════════════════════════════════════


def _intel_result(
    *,
    status: str = "success",
    response_parsed=None,
    response_text: str = "ok",
    execution_id: str = "exec-1",
    model_used: str = "claude-haiku-4-5-20251001",
    input_tokens: int = 100,
    output_tokens: int = 50,
    error_message: str | None = None,
):
    return SimpleNamespace(
        execution_id=execution_id,
        prompt_id="prompt-1",
        prompt_version_id="ver-1",
        model_used=model_used,
        status=status,
        response_text=response_text,
        response_parsed=response_parsed,
        rendered_system_prompt="(mocked)",
        rendered_user_prompt="(mocked)",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=42,
        cost_usd=Decimal("0.0005"),
        experiment_variant=None,
        fallback_used=False,
        error_message=error_message,
    )


# ═══════════════════════════════════════════════════════════════════════
# Migration 1 — first_call_extraction_service.extract_first_call
# ═══════════════════════════════════════════════════════════════════════


def test_first_call_extraction_uses_scribe_prompt_without_case_id():
    """Pre-creation call — caller_fh_case_id stays null."""
    from app.services.first_call_extraction_service import extract_first_call

    extracted = {"extracted": {"deceased_first_name": {"value": "John", "confidence": 0.95}}}

    fake_db = MagicMock()
    with (
        patch("app.config.settings.ANTHROPIC_API_KEY", "test-key"),
        patch(
            "app.services.intelligence.intelligence_service.execute",
            return_value=_intel_result(response_parsed=extracted),
        ) as mock_execute,
    ):
        result = extract_first_call(
            fake_db,
            "John Smith died this morning at Mercy Hospital",
            None,
            company_id="T-1",
        )

    mock_execute.assert_called_once()
    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "scribe.extract_first_call"
    assert ck["company_id"] == "T-1"
    assert ck["caller_module"] == "first_call_extraction_service.extract_first_call"
    assert ck["caller_entity_type"] == "funeral_case"
    assert ck["caller_entity_id"] is None
    assert ck["caller_fh_case_id"] is None
    assert "text" in ck["variables"]
    assert "existing_values" in ck["variables"]
    assert "today" in ck["variables"]
    # The result.fields_updated computation should reflect the confidence
    assert result["fields_updated"] == 1


# ═══════════════════════════════════════════════════════════════════════
# Migration 2 — website_analysis_service.analyze_website_content
# ═══════════════════════════════════════════════════════════════════════


def test_website_analysis_returns_token_usage():
    """Token usage flows from IntelligenceResult into the return shape."""
    from app.services.website_analysis_service import analyze_website_content

    analysis_dict = {"business_name": "ACME Vaults", "industry": "burial_vaults"}
    with (
        patch("app.config.settings.ANTHROPIC_API_KEY", "test-key"),
        patch(
            "app.services.intelligence.intelligence_service.execute",
            return_value=_intel_result(
                response_parsed=analysis_dict,
                input_tokens=450,
                output_tokens=120,
            ),
        ) as mock_execute,
    ):
        out = analyze_website_content(
            MagicMock(),
            "<html>...</html>",
            company_id="T-1",
            company_entity_id="CE-7",
        )

    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "onboarding.analyze_website"
    assert ck["company_id"] == "T-1"
    assert ck["caller_entity_type"] == "company_entity"
    assert ck["caller_entity_id"] == "CE-7"
    assert out["input_tokens"] == 450
    assert out["output_tokens"] == 120
    assert out["analysis"] == analysis_dict


# ═══════════════════════════════════════════════════════════════════════
# Migration 3 — customer_classification_service._classify_batch_with_ai
# ═══════════════════════════════════════════════════════════════════════


def test_customer_classification_passes_tenant_name_variable():
    """Phase 2c-2 parameterized tenant_name — verify it flows through."""
    from app.services.customer_classification_service import _classify_batch_with_ai

    batch = [
        {"index": 0, "name": "Hopkins Funeral Home", "city": "Auburn", "state": "NY"},
        {"index": 1, "name": "Elm Grove Cemetery", "city": None, "state": None},
    ]
    ai_response = [
        {"index": 0, "customer_type": "funeral_home", "confidence": 0.95, "reasoning": "Name"},
        {"index": 1, "customer_type": "cemetery", "confidence": 0.92, "reasoning": "Name"},
    ]

    with (
        patch("app.config.settings.ANTHROPIC_API_KEY", "test-key"),
        patch(
            "app.services.intelligence.intelligence_service.execute",
            return_value=_intel_result(response_parsed=ai_response),
        ) as mock_execute,
    ):
        results = _classify_batch_with_ai(
            batch,
            db=MagicMock(),
            company_id="T-1",
            tenant_name="Sunnycrest Precast",
        )

    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "onboarding.classify_customer_batch"
    assert ck["company_id"] == "T-1"
    # The managed prompt now takes tenant_name as a variable (genericized from
    # the audit-captured "Sunnycrest Precast" hardcoding)
    assert ck["variables"]["tenant_name"] == "Sunnycrest Precast"
    assert "unclassified" in ck["variables"]
    # Response shape preserved
    assert len(results) == 2
    assert results[0]["customer_type"] == "funeral_home"
    assert results[1]["customer_type"] == "cemetery"


# ═══════════════════════════════════════════════════════════════════════
# Migration 4 — training_content_generation_service (2 prompts)
# ═══════════════════════════════════════════════════════════════════════


def test_training_generate_procedure_uses_procedure_prompt():
    """Procedure generation routes through training.generate_procedure."""
    from app.services import training_content_generation_service as svc

    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.first.return_value = None  # no existing proc

    procedure_payload = {
        "overview": "Monthly close process...",
        "steps": [{"step_number": 1, "title": "Start"}],
        "related_procedure_keys": [],
    }

    with (
        patch("app.config.settings.ANTHROPIC_API_KEY", "test-key"),
        patch(
            "app.services.intelligence.intelligence_service.execute",
            return_value=_intel_result(response_parsed=procedure_payload),
        ) as mock_execute,
    ):
        # Call the helper directly with a simulated PROCEDURE_DEFINITIONS entry
        parsed, error = svc._generate_procedure_via_intel(
            fake_db,
            title="Month-End Close Process",
            roles=["accounting", "manager"],
            category="accounting",
            custom_instructions=None,
        )

    assert error is None
    assert parsed == procedure_payload
    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "training.generate_procedure"
    assert ck["company_id"] is None  # platform-level content
    assert ck["caller_module"] == "training_content_generation_service.generate_procedures"
    assert ck["variables"]["title"] == "Month-End Close Process"
    assert ck["variables"]["roles"] == "accounting, manager"
    assert ck["variables"]["category"] == "accounting"
    assert ck["variables"]["custom_instructions"] == ""


def test_training_generate_curriculum_uses_curriculum_prompt():
    """Curriculum generation routes through training.generate_curriculum_track."""
    from app.services import training_content_generation_service as svc

    curriculum_payload = {
        "track_name": "Accounting Onboarding",
        "description": "4-week track",
        "estimated_weeks": 4,
        "modules": [{"week": 1, "module_key": "ai_orientation", "title": "AI Intro"}],
    }
    with (
        patch("app.config.settings.ANTHROPIC_API_KEY", "test-key"),
        patch(
            "app.services.intelligence.intelligence_service.execute",
            return_value=_intel_result(response_parsed=curriculum_payload),
        ) as mock_execute,
    ):
        parsed, error = svc._generate_curriculum_via_intel(
            MagicMock(), role_label="Accounting"
        )

    assert error is None
    assert parsed == curriculum_payload
    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "training.generate_curriculum_track"
    assert ck["company_id"] is None
    assert ck["caller_module"] == "training_content_generation_service.generate_curriculum_tracks"
    assert ck["variables"]["role_label"] == "Accounting"


def test_training_call_claude_helper_removed():
    """The legacy _call_claude helper must be gone."""
    from app.services import training_content_generation_service as svc

    assert not hasattr(svc, "_call_claude"), (
        "_call_claude must be removed as part of the Phase 2c-2 migration"
    )


# ═══════════════════════════════════════════════════════════════════════
# Migration 5 — journal_entries.parse_entry
# ═══════════════════════════════════════════════════════════════════════


def test_journal_entry_parse_uses_managed_prompt():
    """NL journal entry parsing routes through accounting.parse_journal_entry."""
    from app.api.routes.journal_entries import parse_entry, ParseRequest

    parsed_je = {
        "description": "Office supplies",
        "entry_date": "2026-04-18",
        "entry_type": "standard",
        "lines": [
            {
                "gl_account_id": "gl-1",
                "gl_account_number": "6100",
                "gl_account_name": "Office Supplies",
                "side": "debit",
                "amount": 50.00,
                "description": None,
            }
        ],
        "confidence": 0.9,
        "clarification_needed": None,
    }

    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.all.return_value = []  # no accounts
    current_user = MagicMock(id="U-1", company_id="T-1")

    with patch(
        "app.services.intelligence.intelligence_service.execute",
        return_value=_intel_result(response_parsed=parsed_je),
    ) as mock_execute:
        result = parse_entry(
            ParseRequest(input="Office supplies $50 to petty cash"),
            current_user=current_user,
            db=fake_db,
        )

    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "accounting.parse_journal_entry"
    assert ck["company_id"] == "T-1"
    assert ck["caller_module"] == "journal_entries.parse_entry"
    assert ck["caller_entity_type"] == "journal_entry"
    assert ck["caller_entity_id"] is None
    assert result == parsed_je


# ═══════════════════════════════════════════════════════════════════════
# Migration 6 — accounting_connection.sage_analyze_csv
# ═══════════════════════════════════════════════════════════════════════


def test_sage_analyze_csv_uses_map_sage_csv_prompt():
    from app.api.routes.accounting_connection import sage_analyze_csv, SageAnalyzeCsvRequest
    from app.api.routes.accounting_connection import EXPECTED_FIELDS

    export_type = next(iter(EXPECTED_FIELDS.keys()))  # any valid export type
    body = SageAnalyzeCsvRequest(
        export_type=export_type,
        csv_headers=["Account", "Name", "Type"],
        sample_rows=[["1000", "Cash", "Asset"]],
    )

    fake_db = MagicMock()
    # Return a fake AccountingConnection row for linkage
    fake_connection = MagicMock(id="AC-42")
    fake_db.query.return_value.filter.return_value.first.return_value = fake_connection
    current_user = MagicMock(id="U-1", company_id="T-1")

    mappings_response = {
        "mappings": {"account_number": {"csv_column": "Account", "confidence": 0.95}},
        "unmapped_csv_columns": [],
    }

    with (
        patch("app.config.settings.ANTHROPIC_API_KEY", "test-key"),
        patch(
            "app.services.intelligence.intelligence_service.execute",
            return_value=_intel_result(response_parsed=mappings_response),
        ) as mock_execute,
    ):
        result = sage_analyze_csv(body=body, current_user=current_user, db=fake_db)

    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "accounting.map_sage_csv"
    assert ck["company_id"] == "T-1"
    assert ck["caller_entity_type"] == "accounting_connection"
    assert ck["caller_entity_id"] == "AC-42"
    assert "sample_display" in ck["variables"]
    assert "expected" in ck["variables"]
    assert result["mappings"] == mappings_response["mappings"]


# ═══════════════════════════════════════════════════════════════════════
# Migration 7 — reports.parse_package_request
# ═══════════════════════════════════════════════════════════════════════


def test_reports_parse_package_request_uses_managed_prompt():
    from app.api.routes.reports import parse_package_request, ParsePackageRequest

    parsed_request = {
        "package_name": "Q1 Audit",
        "period_start": "2026-01-01",
        "period_end": "2026-03-31",
        "reports": ["income_statement", "balance_sheet"],
        "confidence": 0.9,
    }
    current_user = MagicMock(id="U-1", company_id="T-1")
    fake_db = MagicMock()

    with patch(
        "app.services.intelligence.intelligence_service.execute",
        return_value=_intel_result(response_parsed=parsed_request),
    ) as mock_execute:
        result = parse_package_request(
            ParsePackageRequest(input="Q1 audit package with income statement and balance sheet"),
            current_user=current_user,
            db=fake_db,
        )

    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "reports.parse_audit_package_request"
    assert ck["company_id"] == "T-1"
    assert ck["caller_module"] == "reports.parse_package_request"
    assert result == parsed_request


# ═══════════════════════════════════════════════════════════════════════
# Migration 8 — order_station.parse_order
# ═══════════════════════════════════════════════════════════════════════


def test_order_station_parse_order_uses_voice_order_prompt():
    from app.api.routes.order_station import parse_order

    parsed_order = {
        "vault_product": "Monticello",
        "equipment": "standard",
        "cemetery_name": "Oakwood",
        "service_date": "2026-04-25",
        "confidence": 0.9,
    }
    current_user = MagicMock(id="U-1", company_id="T-1")
    fake_db = MagicMock()

    with (
        patch("app.config.settings.ANTHROPIC_API_KEY", "test-key"),
        patch(
            "app.services.intelligence.intelligence_service.execute",
            return_value=_intel_result(response_parsed=parsed_order),
        ) as mock_execute,
    ):
        result = parse_order(
            {"input": "Monticello vault for Oakwood cemetery Friday"},
            current_user=current_user,
            db=fake_db,
        )

    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "orderstation.parse_voice_order"
    assert ck["company_id"] == "T-1"
    assert ck["caller_entity_type"] == "sales_order_draft"
    # today should flow in as a Jinja variable (not string-replaced)
    assert "today" in ck["variables"]
    assert "input_text" in ck["variables"]
    assert result == parsed_order


# ═══════════════════════════════════════════════════════════════════════
# Migration 9 — financials_board.get_briefing
# ═══════════════════════════════════════════════════════════════════════


def test_financial_board_briefing_uses_plain_text_prompt():
    """briefing.financial_board is force_json=false — use response_text, not response_parsed."""
    from app.api.routes import financials_board as fb

    # Stub the cache so we definitely hit the AI path
    fb._briefing_cache.clear()

    current_user = MagicMock(id="U-1", company_id="T-1")
    fake_db = MagicMock()

    # Stub the summary queries so we reach the AI call
    # get_board_summary.__wrapped__ is used if present; we take the fallback path
    fake_invoice = MagicMock(total=Decimal("500"), amount_paid=Decimal("0"))
    fake_db.query.return_value.filter.return_value.all.return_value = [fake_invoice]
    fake_db.query.return_value.filter.return_value.limit.return_value.all.return_value = []
    fake_db.query.return_value.join.return_value.filter.return_value.group_by.return_value.order_by.return_value.first.return_value = None

    briefing_text = "You have 1 overdue invoice totaling $500. Focus on collections today."

    with patch(
        "app.services.intelligence.intelligence_service.execute",
        return_value=_intel_result(response_text=briefing_text, response_parsed=None),
    ) as mock_execute:
        result = fb.get_briefing(current_user=current_user, db=fake_db)

    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "briefing.financial_board"
    assert ck["company_id"] == "T-1"
    assert ck["caller_entity_type"] == "user"
    assert ck["caller_entity_id"] == "U-1"
    # All 7 summary vars present
    for var in (
        "ar_overdue_count", "ar_overdue_total", "ap_due_this_week",
        "payments_today_total", "payments_today_count", "alerts_text", "largest_overdue",
    ):
        assert var in ck["variables"], f"missing variable: {var}"
    assert result["briefing"] == briefing_text
    assert result["cached"] is False
