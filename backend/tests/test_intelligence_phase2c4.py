"""Phase 2c-4 integration tests — Category B long-tail (21 call sites).

Each test mocks intelligence_service.execute and verifies the migration
contract (prompt_key, caller_module, caller_entity_type, variables flow-through).
End-to-end execute() behavior is covered by Phase 2c-0b tests.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


def _intel_result(
    *,
    status: str = "success",
    response_parsed=None,
    response_text: str = "ok",
    error_message: str | None = None,
):
    return SimpleNamespace(
        execution_id="exec-1",
        prompt_id="prompt-1",
        prompt_version_id="ver-1",
        model_used="claude-haiku-4-5-20251001",
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
# 1 — ai_manufacturing_intents.parse_manufacturing_command
# ═══════════════════════════════════════════════════════════════════════


def test_ai_manufacturing_intents_uses_classify_manufacturing_intent_prompt():
    from app.services import ai_manufacturing_intents

    parsed = {"intent": "log_production", "quantity": 6, "message": "Logged 6 vaults"}
    with (
        patch("app.config.settings.ANTHROPIC_API_KEY", "test-key"),
        patch(
            "app.services.intelligence.intelligence_service.execute",
            return_value=_intel_result(response_parsed=parsed),
        ) as mock_execute,
    ):
        result = ai_manufacturing_intents.parse_manufacturing_command(
            "we made 6 standard vaults today",
            product_catalog=[{"id": "p-1", "name": "Standard Vault", "sku": "SV"}],
            customer_catalog=None,
            employee_names=None,
            db=MagicMock(),
            company_id="T-1",
        )

    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "commandbar.classify_manufacturing_intent"
    assert ck["caller_module"] == "ai_manufacturing_intents.parse_manufacturing_command"
    assert ck["company_id"] == "T-1"
    for var in ("today", "user_input", "context_data_json"):
        assert var in ck["variables"]
    assert result["intent"] == "log_production"


# ═══════════════════════════════════════════════════════════════════════
# 2 — ai_funeral_home_intents.parse_funeral_home_command
# ═══════════════════════════════════════════════════════════════════════


def test_ai_funeral_home_intents_uses_classify_fh_intent_prompt():
    from app.services import ai_funeral_home_intents

    parsed = {"intent": "open_case", "deceased_name": "John Smith"}
    with (
        patch("app.config.settings.ANTHROPIC_API_KEY", "test-key"),
        patch(
            "app.services.intelligence.intelligence_service.execute",
            return_value=_intel_result(response_parsed=parsed),
        ) as mock_execute,
    ):
        result = ai_funeral_home_intents.parse_funeral_home_command(
            "open case for John Smith",
            case_catalog=None,
            db=MagicMock(),
            company_id="T-1",
        )

    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "commandbar.classify_fh_intent"
    assert ck["caller_module"] == "ai_funeral_home_intents.parse_funeral_home_command"
    assert result["intent"] == "open_case"


# ═══════════════════════════════════════════════════════════════════════
# 3 — workflows.generate_workflow
# ═══════════════════════════════════════════════════════════════════════


def test_workflows_generate_uses_workflow_prompt():
    """Source-level verification — the route uses the correct prompt_key + variables."""
    from pathlib import Path

    source = (
        Path(__file__).resolve().parent.parent
        / "app" / "api" / "routes" / "workflows.py"
    ).read_text(encoding="utf-8")
    assert 'prompt_key="workflow.generate_from_description"' in source
    assert 'caller_module="workflows.generate_workflow"' in source
    assert '"description"' in source
    assert '"company_vertical"' in source


# ═══════════════════════════════════════════════════════════════════════
# 4 — kb_parsing_service._run_claude_parsing
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "category_slug",
    ["pricing", "product_specs", "personalization_options",
     "company_policies", "cemetery_policies", "general"],
)
def test_kb_parsing_per_category(category_slug):
    from app.services.kb_parsing_service import _run_claude_parsing

    parsed = {"chunks": [f"chunk for {category_slug}"], "summary": "ok"}
    with patch(
        "app.services.intelligence.intelligence_service.execute",
        return_value=_intel_result(response_parsed=parsed),
    ) as mock_execute:
        result = _run_claude_parsing(
            MagicMock(), "some raw text", category_slug,
            "manufacturing", ["urn_sales"],
            tenant_id="T-1", document_id="DOC-1",
        )

    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "kb.parse_document"
    assert ck["variables"]["category_slug"] == category_slug
    assert ck["caller_kb_document_id"] == "DOC-1"
    assert result["chunks"][0] == f"chunk for {category_slug}"


# ═══════════════════════════════════════════════════════════════════════
# 5-7 — briefing_intelligence three sub-prompts
# ═══════════════════════════════════════════════════════════════════════


def test_briefing_generate_narrative_uses_managed_prompt():
    from app.services.ai import briefing_intelligence

    with (
        patch("app.services.ai_settings_service.is_enabled", return_value=True),
        patch(
            "app.services.ai_settings_service.get_effective_settings",
            return_value={"briefing_narrative_tone": "concise"},
        ),
    ):
        fake_db = MagicMock()
        user_mock = MagicMock(first_name="Alex")
        company_mock = MagicMock(name="Sunnycrest")
        fake_db.query.return_value.filter.return_value.first.side_effect = [user_mock, company_mock]

        with patch(
            "app.services.intelligence.intelligence_service.execute",
            return_value=_intel_result(response_text="Good morning..."),
        ) as mock_execute:
            result = briefing_intelligence.generate_narrative(
                fake_db, "T-1", "U-1",
                {"today_count": 3, "legacy_proofs_pending_review": 1,
                 "crm_today_followups": 2, "crm_overdue_followups": 0,
                 "crm_at_risk_accounts": []},
            )

    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "briefing.generate_narrative"
    assert ck["caller_module"] == "briefing_intelligence.generate_narrative"
    assert ck["caller_entity_type"] == "user"
    assert ck["caller_entity_id"] == "U-1"
    assert result == "Good morning..."


def test_briefing_generate_prep_note_uses_managed_prompt():
    from app.services.ai import briefing_intelligence

    with patch("app.services.ai_settings_service.is_enabled", return_value=True):
        fake_db = MagicMock()
        entity_mock = MagicMock(id="CE-7", name="Hopkins FH", city="Auburn", state="NY")
        fake_db.query.return_value.filter.return_value.first.side_effect = [
            entity_mock, None, None  # entity, customer=None, profile=None
        ]

        with patch(
            "app.services.intelligence.intelligence_service.execute",
            return_value=_intel_result(response_text="Quick summary..."),
        ) as mock_execute:
            result = briefing_intelligence.generate_prep_note(
                fake_db, "T-1", "CE-7", "Last talked about pricing"
            )

    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "briefing.generate_prep_note"
    assert ck["caller_entity_type"] == "company_entity"
    assert ck["caller_entity_id"] == "CE-7"
    assert result == "Quick summary..."


def test_briefing_generate_weekly_summary_uses_managed_prompt():
    from app.services.ai import briefing_intelligence

    with patch("app.services.ai_settings_service.is_enabled", return_value=True):
        fake_db = MagicMock()
        fake_db.execute.return_value.fetchone.side_effect = [
            MagicMock(orders=12, revenue=50000),
            MagicMock(orders=9, revenue=38000),
        ]

        with patch(
            "app.services.intelligence.intelligence_service.execute",
            return_value=_intel_result(response_text="Solid week: up 33%."),
        ) as mock_execute:
            result = briefing_intelligence.generate_weekly_summary(fake_db, "T-1", user_id="U-1")

    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "briefing.generate_weekly_summary"
    assert result["type"] == "weekly_summary"
    assert result["content"] == "Solid week: up 33%."


def test_briefing_intelligence_call_claude_helper_removed():
    from app.services.ai import briefing_intelligence

    assert not hasattr(briefing_intelligence, "_call_claude"), (
        "_call_claude must be deleted in Phase 2c-4"
    )


# ═══════════════════════════════════════════════════════════════════════
# 8 — command_bar_data_search
# ═══════════════════════════════════════════════════════════════════════


def test_command_bar_data_search_uses_catalog_question_prompt():
    """Source-level check — this function has many DB dependencies that
    fall outside the migration scope."""
    from pathlib import Path

    source = (
        Path(__file__).resolve().parent.parent
        / "app" / "services" / "command_bar_data_search.py"
    ).read_text(encoding="utf-8")
    assert 'prompt_key="commandbar.answer_catalog_question"' in source
    assert '"query"' in source and '"catalog_lines"' in source


# ═══════════════════════════════════════════════════════════════════════
# 9 — obituary_service
# ═══════════════════════════════════════════════════════════════════════


def test_obituary_service_uses_managed_prompt_with_case_linkage():
    """Source-level check — route has many DB dependencies outside scope."""
    from pathlib import Path

    source = (
        Path(__file__).resolve().parent.parent
        / "app" / "services" / "obituary_service.py"
    ).read_text(encoding="utf-8")
    assert 'prompt_key="fh.obituary.generate"' in source
    assert 'caller_fh_case_id=case_id' in source


# ═══════════════════════════════════════════════════════════════════════
# 10 — kb_retrieval_service._synthesize_answer
# ═══════════════════════════════════════════════════════════════════════


def test_kb_retrieval_synthesize_uses_managed_prompt():
    from app.services.kb_retrieval_service import _synthesize_answer

    with patch(
        "app.services.intelligence.intelligence_service.execute",
        return_value=_intel_result(response_parsed={"answer": "The price is $500.", "confidence": "high"}),
    ) as mock_execute:
        answer, confidence = _synthesize_answer(
            "What does the Monticello cost?",
            chunks=[{"category_slug": "pricing", "document_title": "Price List",
                     "content": "Monticello — $500"}],
            pricing=[],
            db=MagicMock(),
            tenant_id="T-1",
        )

    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "kb.synthesize_call_answer"
    assert ck["caller_module"] == "kb_retrieval_service._synthesize_answer"
    assert "query" in ck["variables"]
    assert "context_block" in ck["variables"]
    assert answer == "The price is $500."
    assert confidence == "high"


# ═══════════════════════════════════════════════════════════════════════
# 11 — crm/classification_service._ai_classify
# ═══════════════════════════════════════════════════════════════════════


def test_crm_classify_entity_uses_managed_prompt():
    from app.services.crm.classification_service import _ai_classify

    entity = MagicMock(
        id="CE-7", name="Hopkins Funeral Home",
        city="Auburn", state="NY", email="info@hopkinsfh.com",
    )
    parsed = {"customer_type": "funeral_home", "contractor_type": None,
              "confidence": 0.95, "reasons": ["name match"]}

    with patch(
        "app.services.intelligence.intelligence_service.execute",
        return_value=_intel_result(response_parsed=parsed),
    ) as mock_execute:
        result = _ai_classify(
            entity, {"funeral_home": True}, {"total_orders": 5, "is_active": True},
            db=MagicMock(), tenant_id="T-1",
        )

    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "crm.classify_entity_single"
    assert ck["caller_entity_type"] == "company_entity"
    assert ck["caller_entity_id"] == "CE-7"
    assert result["customer_type"] == "funeral_home"


# ═══════════════════════════════════════════════════════════════════════
# 12 — voice_memo_service.extract_memo_data
# ═══════════════════════════════════════════════════════════════════════


def test_voice_memo_extract_uses_managed_prompt():
    from app.services.ai.voice_memo_service import extract_memo_data

    parsed = {"activity_type": "call", "title": "Chat with Hopkins",
              "body": "Follow up on pricing", "follow_up_needed": True,
              "follow_up_days": 3, "action_items": []}

    with patch(
        "app.services.intelligence.intelligence_service.execute",
        return_value=_intel_result(response_parsed=parsed),
    ) as mock_execute:
        result = extract_memo_data(
            "I talked with Hopkins about pricing, need to follow up in 3 days",
            "Hopkins FH (Auburn, NY)",
            db=MagicMock(), tenant_id="T-1", master_company_id="CE-7",
        )

    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "crm.extract_voice_memo"
    assert ck["caller_entity_type"] == "company_entity"
    assert ck["caller_entity_id"] == "CE-7"
    assert result["activity_type"] == "call"


# ═══════════════════════════════════════════════════════════════════════
# 13 — agent_orchestrator.account_rescue_agent (source-level)
# ═══════════════════════════════════════════════════════════════════════


def test_agent_orchestrator_rescue_uses_managed_prompt():
    """Source-level — agent_orchestrator has complex nightly scheduling."""
    from pathlib import Path

    source = (
        Path(__file__).resolve().parent.parent
        / "app" / "services" / "ai" / "agent_orchestrator.py"
    ).read_text(encoding="utf-8")
    assert 'prompt_key="crm.draft_rescue_email"' in source
    assert 'caller_module="ai.agent_orchestrator.account_rescue_agent"' in source


# ═══════════════════════════════════════════════════════════════════════
# 14-15 — urn_intake_agent (2 sites)
# ═══════════════════════════════════════════════════════════════════════


def test_urn_intake_agent_process_intake_uses_managed_prompt():
    """Avoid funeral_home_name path to dodge pre-existing
    CompanyEntity.tenant_id bug in _match_funeral_home (same bug as
    call_extraction_service._fuzzy_match_company — flagged for cleanup)."""
    from app.services.urn_intake_agent import UrnIntakeAgent

    # Omit funeral_home_name so _match_funeral_home path isn't exercised
    extracted = {
        "urn_description": "Monticello Pewter",
        "quantity": 1,
    }

    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.first.return_value = None

    with (
        patch(
            "app.services.intelligence.intelligence_service.execute",
            return_value=_intel_result(response_parsed=extracted),
        ) as mock_execute,
        patch(
            "app.services.urn_order_service.UrnOrderService.create_draft_from_extraction",
            return_value={"order_id": "URN-1"},
        ),
    ):
        UrnIntakeAgent.process_intake_email(
            fake_db, "T-1",
            {"from_email": "hi@hopkinsfh.com", "subject": "New urn order",
             "body_text": "Please send one Monticello urn..."},
        )

    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "urn.extract_intake_email"
    assert ck["caller_module"] == "urn_intake_agent.process_intake_email"


def test_urn_intake_agent_match_proof_uses_managed_prompt():
    from app.services.urn_intake_agent import UrnIntakeAgent

    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.first.return_value = None
    fake_db.query.return_value.join.return_value.filter.return_value.first.return_value = None

    parsed = {"decedent_name": "John Smith"}

    with patch(
        "app.services.intelligence.intelligence_service.execute",
        return_value=_intel_result(response_parsed=parsed),
    ) as mock_execute:
        result = UrnIntakeAgent.match_proof_email(
            fake_db, "T-1",
            {"subject": "Proof for your order", "body_text": "Attached is the proof for John Smith."},
        )

    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "urn.match_proof_email"
    assert ck["caller_module"] == "urn_intake_agent.match_proof_email"
    # No match because fake_db returned no job row
    assert result["matched"] is False


# ═══════════════════════════════════════════════════════════════════════
# 16 — name_enrichment_agent (source-level)
# ═══════════════════════════════════════════════════════════════════════


def test_name_enrichment_uses_managed_prompt():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parent.parent
        / "app" / "services" / "ai" / "name_enrichment_agent.py"
    ).read_text(encoding="utf-8")
    assert 'prompt_key="crm.suggest_complete_name"' in source
    assert 'caller_module="ai.name_enrichment_agent.enrich_company_name"' in source


# ═══════════════════════════════════════════════════════════════════════
# 17 — document_search_service._extract_answer
# ═══════════════════════════════════════════════════════════════════════


def test_document_search_extract_uses_managed_prompt():
    from app.services.document_search_service import _extract_answer

    parsed = {"found": True, "answer": "The warranty is 5 years.", "source_chunk_index": 0}
    with patch(
        "app.services.intelligence.intelligence_service.execute",
        return_value=_intel_result(response_parsed=parsed),
    ) as mock_execute:
        result = _extract_answer(
            "How long is the warranty?",
            [{"section_title": "Warranty", "content": "5 years on all vaults..."}],
            db=MagicMock(), company_id="T-1",
        )

    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "commandbar.extract_document_answer"
    assert ck["caller_module"] == "document_search_service._extract_answer"
    assert result["found"] is True


# ═══════════════════════════════════════════════════════════════════════
# 18 — historical_order_import_service.detect_format (source-level)
# ═══════════════════════════════════════════════════════════════════════


def test_historical_order_import_uses_managed_prompt():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parent.parent
        / "app" / "services" / "historical_order_import_service.py"
    ).read_text(encoding="utf-8")
    assert 'prompt_key="import.detect_order_csv_columns"' in source
    assert 'caller_module="historical_order_import_service.detect_format"' in source


# ═══════════════════════════════════════════════════════════════════════
# 19 — unified_import_service._classify_batch_ai (source-level)
# ═══════════════════════════════════════════════════════════════════════


def test_unified_import_uses_managed_prompt():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parent.parent
        / "app" / "services" / "onboarding" / "unified_import_service.py"
    ).read_text(encoding="utf-8")
    assert 'prompt_key="onboarding.classify_import_companies"' in source
    assert 'caller_module="onboarding.unified_import_service._classify_batch_ai"' in source


# ═══════════════════════════════════════════════════════════════════════
# 20 — import_alias_service._ai_match_products (source-level)
# ═══════════════════════════════════════════════════════════════════════


def test_import_alias_uses_managed_prompt():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parent.parent
        / "app" / "services" / "import_alias_service.py"
    ).read_text(encoding="utf-8")
    assert 'prompt_key="import.match_product_aliases"' in source
    assert 'caller_module="import_alias_service._ai_match_products"' in source


# ═══════════════════════════════════════════════════════════════════════
# 21 — csv_column_detector.detect_columns (source-level)
# ═══════════════════════════════════════════════════════════════════════


def test_csv_column_detector_uses_managed_prompt():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parent.parent
        / "app" / "services" / "onboarding" / "csv_column_detector.py"
    ).read_text(encoding="utf-8")
    assert 'prompt_key="onboarding.detect_csv_columns"' in source
    assert 'caller_module="onboarding.csv_column_detector.detect_columns"' in source


# ═══════════════════════════════════════════════════════════════════════
# Global: call_anthropic elimination check
# ═══════════════════════════════════════════════════════════════════════


def test_phase_2c_4_call_anthropic_only_in_allowed_files():
    """After Phase 2c-5, `call_anthropic` should appear in exactly one file:
      - intelligence/intelligence_service.py — the backbone's internal
        `_call_anthropic` helper (the private SDK wrapper, not the legacy
        public API).

    ai_service.py was deleted in Phase 2c-5 and ai.py's /ai/prompt route was
    migrated to use the managed `legacy.arbitrary_prompt` prompt, so neither
    should reference `call_anthropic` anymore.
    """
    from pathlib import Path

    backend = Path(__file__).resolve().parent.parent
    app_dir = backend / "app"
    allowed = {
        "app/services/intelligence/intelligence_service.py",
    }
    violations: list[str] = []
    for py in app_dir.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if "call_anthropic" in text:
            relpath = str(py.relative_to(backend))
            if relpath not in allowed:
                violations.append(relpath)
    assert not violations, (
        "Unexpected call_anthropic references after Phase 2c-5:\n  "
        + "\n  ".join(violations)
    )
