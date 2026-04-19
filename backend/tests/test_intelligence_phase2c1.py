"""Phase 2c-1 integration tests — 5 Tier 1 caller migrations.

Each test verifies the MIGRATION INVARIANT: the caller now invokes
`intelligence_service.execute(...)` with the right prompt_key and caller
linkage. We mock `intelligence_service.execute` because the full caller
integration chains through many unrelated services; the migration contract
is about WHAT the caller asks the Intelligence layer to do.

End-to-end execute() semantics are covered by tests/test_intelligence_phase2c0b.py.
"""

from __future__ import annotations

import asyncio
import base64
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════════
# Shared helpers
# ═══════════════════════════════════════════════════════════════════════


def _intel_result(
    *,
    status: str = "success",
    response_parsed: dict | list | None = None,
    response_text: str = "ok",
    execution_id: str = "exec-1",
    model_used: str = "claude-sonnet-4-6",
    input_tokens: int = 100,
    output_tokens: int = 50,
    error_message: str | None = None,
):
    """Build a realistic IntelligenceResult mock value."""
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
        cost_usd=Decimal("0.001"),
        experiment_variant=None,
        fallback_used=False,
        error_message=error_message,
    )


# ═══════════════════════════════════════════════════════════════════════
# Migration 1 — accounting_analysis_service.run_ai_analysis
# ═══════════════════════════════════════════════════════════════════════


def test_accounting_analysis_calls_coa_classify_with_linkage():
    """run_ai_analysis invokes accounting.coa_classify with analysis_run_id linkage."""
    import app.services.accounting_analysis_service as svc

    parsed_response = {
        "gl_mappings": [],
        "stale_accounts": [],
        "customer_analysis": [],
        "vendor_analysis": [],
        "product_matches": [],
        "network_flags": [],
    }

    # Fake DB session: only needs the query methods the caller touches
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.first.return_value = None  # no conn
    # Staged rows query returns one fake row
    staged_row = MagicMock(data_type="gl_accounts", raw_data={}, status="extracted")
    fake_db.query.return_value.filter.return_value.all.return_value = [staged_row]

    with patch(
        "app.services.intelligence.intelligence_service.execute",
        return_value=_intel_result(response_parsed=parsed_response),
    ) as mock_execute:
        run_id = asyncio.run(svc.run_ai_analysis(fake_db, tenant_id="T-1"))

    assert run_id is not None
    mock_execute.assert_called_once()
    call_kwargs = mock_execute.call_args.kwargs
    assert call_kwargs["prompt_key"] == "accounting.coa_classify"
    assert call_kwargs["company_id"] == "T-1"
    assert call_kwargs["caller_module"] == "accounting_analysis_service.run_ai_analysis"
    assert call_kwargs["caller_entity_type"] == "company"
    assert call_kwargs["caller_entity_id"] == "T-1"
    # The new 2c-0a linkage column must carry the run_id
    assert call_kwargs["caller_accounting_analysis_run_id"] == run_id
    # user_data variable set and is a JSON-serialized string
    assert "user_data" in call_kwargs["variables"]


def test_accounting_analysis_failure_marks_connection_failed():
    """Intelligence failure → conn.ai_analysis_status='failed', no write-back."""
    import app.services.accounting_analysis_service as svc

    conn = MagicMock()
    fake_db = MagicMock()
    # First .first() returns the connection; staged query returns one row
    fake_db.query.return_value.filter.return_value.first.return_value = conn
    staged_row = MagicMock(data_type="gl_accounts", raw_data={}, status="extracted")
    fake_db.query.return_value.filter.return_value.all.return_value = [staged_row]

    with patch(
        "app.services.intelligence.intelligence_service.execute",
        return_value=_intel_result(status="api_error", response_parsed=None, response_text=""),
    ):
        asyncio.run(svc.run_ai_analysis(fake_db, tenant_id="T-2"))

    assert conn.ai_analysis_status == "failed"
    assert staged_row.status == "extracted"  # reset so manual mapping can proceed


# ═══════════════════════════════════════════════════════════════════════
# Migration 2 — price_list_analysis_service.analyze_price_list
# ═══════════════════════════════════════════════════════════════════════


def test_price_list_analyze_calls_managed_prompt_with_import_linkage():
    """analyze_price_list invokes pricing.analyze_price_list with caller_price_list_import_id."""
    import app.services.price_list_analysis_service as svc

    imp = MagicMock()
    imp.id = "PLI-1"
    imp.tenant_id = "T-1"
    imp.raw_extracted_text = "fake price list text"
    imp.status = "extracting"

    fake_db = MagicMock()

    # The real function does: db.query(PriceListImport).filter(...).first()
    # followed by db.query(ProductCatalogTemplate).filter(...).all()
    # Return the mock import from the first .first() call, empty templates
    # from the first .all() call.
    def _query(model):
        from app.models.price_list_import import PriceListImport
        from app.models.product_catalog_template import ProductCatalogTemplate

        q = MagicMock()
        if model is PriceListImport:
            q.filter.return_value.first.return_value = imp
        elif model is ProductCatalogTemplate:
            q.filter.return_value.all.return_value = []  # empty catalog
        else:
            # PriceListImportItem.add() goes through db.add, not db.query
            q.filter.return_value.first.return_value = None
            q.filter.return_value.all.return_value = []
        return q

    fake_db.query.side_effect = _query

    parsed = {
        "items": [
            {
                "extracted_name": f"Item {i}",
                "match_status": "unmatched",
                "unit_price": 100.0 + i,
                "match": {},
            }
            for i in range(10)
        ],
        "billing_terms": None,
    }

    with patch(
        "app.services.intelligence.intelligence_service.execute",
        return_value=_intel_result(response_parsed=parsed),
    ) as mock_execute:
        svc.analyze_price_list(fake_db, "PLI-1")

    mock_execute.assert_called_once()
    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "pricing.analyze_price_list"
    assert ck["company_id"] == "T-1"
    assert ck["caller_module"] == "price_list_analysis_service.analyze_price_list"
    assert ck["caller_entity_type"] == "price_list_import"
    assert ck["caller_entity_id"] == "PLI-1"
    assert ck["caller_price_list_import_id"] == "PLI-1"
    for var in ("catalog_ref", "wilbert_variations", "text"):
        assert var in ck["variables"], f"missing variable: {var}"


# ═══════════════════════════════════════════════════════════════════════
# Migration 3 — agent_service collections collapse
# ═══════════════════════════════════════════════════════════════════════


def test_collections_sequence_calls_managed_prompt_once_per_invoice():
    """The collapse eliminates the duplicate draft helper — exactly one
    intelligence_service.execute call per due sequence, all using the
    shared agent.ar_collections.draft_email prompt."""
    import app.services.agent_service as svc
    from datetime import date

    fake_db = MagicMock()

    # Mock the sequence query
    seq1 = MagicMock(
        id="SEQ-1",
        invoice_id="INV-1",
        customer_id="CUST-1",
        sequence_step=1,
    )
    seq2 = MagicMock(
        id="SEQ-2",
        invoice_id="INV-2",
        customer_id="CUST-2",
        sequence_step=3,
    )

    invoice1 = MagicMock(
        id="INV-1",
        invoice_number="1001",
        due_date=date(2026, 1, 1),
        total=Decimal("500"),
        amount_paid=Decimal("0"),
    )
    invoice2 = MagicMock(
        id="INV-2",
        invoice_number="1002",
        due_date=date(2025, 12, 1),
        total=Decimal("1200"),
        amount_paid=Decimal("0"),
    )
    customer1 = MagicMock(id="CUST-1", name="Hopkins FH")
    customer2 = MagicMock(id="CUST-2", name="Oakwood Chapel")

    # Query router: AgentCollectionSequence → [seq1, seq2]; Invoice → by id; Customer → by id
    def _query(model):
        q = MagicMock()
        from app.models.agent import AgentCollectionSequence
        from app.models.customer import Customer
        from app.models.invoice import Invoice

        if model is AgentCollectionSequence:
            q.filter.return_value.all.return_value = [seq1, seq2]
            return q
        if model is Invoice:
            def invoice_filter(cond):
                r = MagicMock()
                r.first.return_value = invoice1 if "INV-1" in str(cond) else invoice2
                return r
            q.filter.side_effect = invoice_filter
            return q
        if model is Customer:
            def cust_filter(cond):
                r = MagicMock()
                r.first.return_value = customer1 if "CUST-1" in str(cond) else customer2
                return r
            q.filter.side_effect = cust_filter
            return q
        # _create_job / _complete_job / create_alert / log_activity hit the db
        return q

    fake_db.query.side_effect = _query

    # Stub out the job + alert side effects so we don't need full infra
    with (
        patch.object(svc, "_create_job", return_value=MagicMock(id="JOB-1")),
        patch.object(svc, "_complete_job"),
        patch.object(svc, "create_alert"),
        patch.object(svc, "log_activity"),
        patch(
            "app.services.intelligence.intelligence_service.execute",
            return_value=_intel_result(response_text="Dear [Contact Name], please remit..."),
        ) as mock_execute,
    ):
        result = svc.run_collections_sequence(fake_db, tenant_id="T-1")

    # ONE call per sequence — the collapse invariant
    assert mock_execute.call_count == 2, (
        f"Expected 1 intelligence call per invoice (collapse); got {mock_execute.call_count}"
    )
    # Every call targets the managed AR collections prompt with correct linkage
    seen_tiers: set[str] = set()
    for call in mock_execute.call_args_list:
        ck = call.kwargs
        assert ck["prompt_key"] == "agent.ar_collections.draft_email"
        assert ck["caller_module"] == "agent_service.run_collections_sequence"
        assert ck["caller_agent_job_id"] == "JOB-1"
        assert ck["caller_entity_type"] == "customer"
        assert ck["variables"]["tier"] in {"FOLLOW_UP", "ESCALATE", "CRITICAL"}
        seen_tiers.add(ck["variables"]["tier"])

    # Across the two sequences (steps 1 and 3), we must see FOLLOW_UP + CRITICAL
    assert seen_tiers == {"FOLLOW_UP", "CRITICAL"}, (
        f"Expected tier mapping step 1→FOLLOW_UP and step 3→CRITICAL; saw {seen_tiers}"
    )


def test_generate_collections_draft_function_deleted():
    """The legacy duplicate function must be gone entirely."""
    import app.services.agent_service as svc

    assert not hasattr(svc, "_generate_collections_draft"), (
        "_generate_collections_draft must be deleted as part of the Phase 2c-1 collapse"
    )


# ═══════════════════════════════════════════════════════════════════════
# Migration 4 — sales_service.scan_check_image (VISION)
# ═══════════════════════════════════════════════════════════════════════


def test_scan_check_image_uses_vision_prompt_with_image_block():
    """Check scan routes through accounting.extract_check_image with image content_block."""
    import app.services.sales_service as svc

    # Async FastAPI UploadFile shim
    fake_file = MagicMock()
    fake_file.read = AsyncMock(return_value=b"fake-check-image-bytes")
    fake_file.content_type = "image/jpeg"

    extracted = {
        "payer_name": "ACME Corp",
        "amount": 1234.56,
        "check_number": "4321",
        "check_date": "2026-04-18",
        "memo": None,
        "bank_name": "First Bank",
    }

    fake_db = MagicMock()
    # customers query + invoices query for match/apply logic — return empty
    fake_db.query.return_value.filter.return_value.all.return_value = []
    fake_db.query.return_value.filter.return_value.first.return_value = None

    with patch(
        "app.services.intelligence.intelligence_service.execute",
        return_value=_intel_result(response_parsed=extracted),
    ) as mock_execute:
        result = asyncio.run(svc.scan_check_image(fake_db, fake_file, company_id="T-1"))

    mock_execute.assert_called_once()
    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "accounting.extract_check_image"
    assert ck["company_id"] == "T-1"
    assert ck["caller_module"] == "sales_service.scan_check_image"
    assert ck["caller_entity_type"] == "customer_payment_draft"

    # content_blocks: one image block with base64 data
    blocks = ck["content_blocks"]
    assert len(blocks) == 1
    assert blocks[0]["type"] == "image"
    assert blocks[0]["source"]["type"] == "base64"
    assert blocks[0]["source"]["media_type"] == "image/jpeg"
    expected_b64 = base64.b64encode(b"fake-check-image-bytes").decode()
    assert blocks[0]["source"]["data"] == expected_b64

    # Result propagates
    assert result["extracted"]["payer_name"] == "ACME Corp"


# ═══════════════════════════════════════════════════════════════════════
# Migration 5 — price_list_extraction_service._extract_pdf_via_claude (VISION)
# ═══════════════════════════════════════════════════════════════════════


def test_pdf_extract_uses_vision_prompt_with_document_block():
    """PDF fallback routes through pricing.extract_pdf_text with document content_block."""
    from app.services.price_list_extraction_service import _extract_pdf_via_claude

    pdf_bytes = b"%PDF-1.4 fake content"

    with (
        patch("app.config.settings.ANTHROPIC_API_KEY", "test-key"),
        patch(
            "app.services.intelligence.intelligence_service.execute",
            return_value=_intel_result(
                response_text="Line 1\nLine 2\nLine 3",
                response_parsed=None,  # force_json=false for this prompt
            ),
        ) as mock_execute,
    ):
        fake_db = MagicMock()
        extracted = _extract_pdf_via_claude(
            pdf_bytes, db=fake_db, company_id="T-1", import_id=None
        )

    assert extracted == "Line 1\nLine 2\nLine 3"
    mock_execute.assert_called_once()
    ck = mock_execute.call_args.kwargs
    assert ck["prompt_key"] == "pricing.extract_pdf_text"
    assert ck["company_id"] == "T-1"
    assert ck["caller_module"] == "price_list_extraction_service._extract_pdf_via_claude"
    # import_id is None at extraction time (PriceListImport is created after)
    assert ck["caller_entity_id"] is None
    assert ck["caller_price_list_import_id"] is None

    blocks = ck["content_blocks"]
    assert len(blocks) == 1
    assert blocks[0]["type"] == "document"
    assert blocks[0]["source"]["media_type"] == "application/pdf"
    expected_b64 = base64.b64encode(pdf_bytes).decode()
    assert blocks[0]["source"]["data"] == expected_b64


def test_pdf_extract_returns_empty_when_no_api_key():
    """Graceful fallback when key is missing (same as pre-migration behavior)."""
    from app.services.price_list_extraction_service import _extract_pdf_via_claude

    with patch("app.config.settings.ANTHROPIC_API_KEY", ""):
        result = _extract_pdf_via_claude(b"%PDF fake", db=MagicMock(), company_id="T-1")
    assert result == ""


def test_pdf_extract_accepts_import_id_when_known():
    """Callers that DO have the import_id should see it flow through to linkage."""
    from app.services.price_list_extraction_service import _extract_pdf_via_claude

    with (
        patch("app.config.settings.ANTHROPIC_API_KEY", "test-key"),
        patch(
            "app.services.intelligence.intelligence_service.execute",
            return_value=_intel_result(response_text="extracted text"),
        ) as mock_execute,
    ):
        _extract_pdf_via_claude(
            b"%PDF fake",
            db=MagicMock(),
            company_id="T-1",
            import_id="PLI-2",
        )

    ck = mock_execute.call_args.kwargs
    assert ck["caller_entity_type"] == "price_list_import"
    assert ck["caller_entity_id"] == "PLI-2"
    assert ck["caller_price_list_import_id"] == "PLI-2"
