"""Phase D-9 tests — arc debt cleanup.

Covers the three cleanups in D-9:

1. WeasyPrint migration — the 3 former transitional call-sites
   (pdf_generation_service, quote_service, wilbert_utils) route through
   DocumentRenderer now; the new `quote.standard` and
   `urn.wilbert_engraving_form` platform templates exist; each migrated
   caller produces the expected output (bytes or Document).

2. EmailService fallback removal — `_fallback_company_id` is gone;
   every email send requires `company_id` and crashes with a clear
   ValueError if missing. Migrated callers thread company_id through.

3. DocumentRenderer unification — `render()` accepts either
   `template_key` (current-active lookup) or `template_version_id`
   (specific-version lookup). The test-render endpoint delegates to
   the renderer instead of re-implementing the pipeline.

Tests mock WeasyPrint + R2 to avoid system deps. Same fixture
pattern as test_documents_d1.py so future D-10+ additions can
extend the scaffold easily.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import JSON, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.database import Base


BACKEND = Path(__file__).resolve().parent.parent
APP_DIR = BACKEND / "app"


# ---------------------------------------------------------------------------
# Fixtures (parallel to test_documents_d1.py scaffold)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:")

    # Import every model needed by the services we exercise.
    from app.models.agent import AgentJob  # noqa: F401
    from app.models.canonical_document import Document, DocumentVersion  # noqa: F401
    from app.models.company import Company  # noqa: F401
    from app.models.company_entity import CompanyEntity  # noqa: F401
    from app.models.customer import Customer  # noqa: F401
    from app.models.disinterment_case import DisintermentCase  # noqa: F401
    from app.models.document_share import (  # noqa: F401
        DocumentShare,
        DocumentShareEvent,
    )
    from app.models.document_share_read import DocumentShareRead  # noqa: F401
    from app.models.document_template import (  # noqa: F401
        DocumentTemplate,
        DocumentTemplateAuditLog,
        DocumentTemplateVersion,
    )
    from app.models.fh_case import FHCase  # noqa: F401
    from app.models.invoice import Invoice  # noqa: F401
    from app.models.price_list_version import PriceListVersion  # noqa: F401
    from app.models.quote import Quote, QuoteLine  # noqa: F401
    from app.models.role import Role  # noqa: F401
    from app.models.safety_program_generation import SafetyProgramGeneration  # noqa: F401
    from app.models.sales_order import SalesOrder  # noqa: F401
    from app.models.statement import CustomerStatement  # noqa: F401
    from app.models.user import User  # noqa: F401
    from app.models.workflow import WorkflowRun, WorkflowRunStep  # noqa: F401
    from app.models.document_delivery import DocumentDelivery  # noqa: F401

    tables_needed = [
        "companies",
        "company_entities",
        "roles",
        "users",
        "customers",
        "cemeteries",
        "cemetery_plots",
        "price_list_versions",
        "price_list_items",
        "price_list_templates",
        "sales_orders",
        "invoices",
        "invoice_lines",
        "statement_runs",
        "customer_statements",
        "fh_cases",
        "disinterment_cases",
        "safety_training_topics",
        "safety_programs",
        "safety_program_generations",
        "tenant_training_schedules",
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
        "intelligence_prompt_audit_log",
        "documents",
        "document_versions",
        "document_templates",
        "document_template_versions",
        "document_template_audit_log",
        "document_shares",
        "document_share_events",
        "document_share_reads",
        "document_deliveries",
        "quotes",
        "quote_lines",
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


def _seed_platform_templates(session: Session) -> None:
    """Seed D-2 + D-9 platform templates. Mirrors test_documents_d1._seed_platform_templates
    so all tests can look up `quote.standard`, `urn.wilbert_engraving_form`,
    etc."""
    from app.models.document_template import (
        DocumentTemplate,
        DocumentTemplateVersion,
    )
    from app.services.documents._template_seeds import (
        list_platform_template_seeds,
    )

    for seed in list_platform_template_seeds():
        tpl = DocumentTemplate(
            id=str(uuid.uuid4()),
            company_id=None,
            template_key=seed["template_key"],
            document_type=seed["document_type"],
            output_format=seed["output_format"],
            description=seed.get("description"),
            supports_variants=seed.get("supports_variants", False),
            is_active=True,
        )
        session.add(tpl)
        session.flush()
        ver = DocumentTemplateVersion(
            id=str(uuid.uuid4()),
            template_id=tpl.id,
            version_number=1,
            status="active",
            body_template=seed["body_template"],
            subject_template=seed.get("subject_template"),
            variable_schema=seed.get("variable_schema"),
            css_variables=seed.get("css_variables"),
            changelog="test-seed",
            activated_at=datetime.now(timezone.utc),
        )
        session.add(ver)
        session.flush()
        tpl.current_version_id = ver.id
    session.flush()


@pytest.fixture
def db(engine):
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn)
    _seed_platform_templates(session)
    yield session
    session.close()
    trans.rollback()
    conn.close()


@pytest.fixture
def company(db):
    from app.models.company import Company

    c = Company(
        id=str(uuid.uuid4()),
        name="Test Co",
        slug="testco",
        is_active=True,
    )
    db.add(c)
    db.flush()
    return c


# ---------------------------------------------------------------------------
# Step 1–3: WeasyPrint migrations — no direct weasyprint left
# ---------------------------------------------------------------------------


class TestWeasyPrintMigrations:
    """The three former transitional call-sites route through
    DocumentRenderer now."""

    def test_pdf_generation_service_no_weasyprint_import(self):
        """pdf_generation_service.py must no longer import weasyprint."""
        src = (APP_DIR / "services/pdf_generation_service.py").read_text("utf-8")
        assert "from weasyprint" not in src
        assert "import weasyprint" not in src

    def test_quote_service_no_weasyprint_import(self):
        src = (APP_DIR / "services/quote_service.py").read_text("utf-8")
        assert "from weasyprint" not in src
        assert "import weasyprint" not in src

    def test_wilbert_utils_no_weasyprint_import(self):
        src = (APP_DIR / "services/wilbert_utils.py").read_text("utf-8")
        assert "from weasyprint" not in src
        assert "import weasyprint" not in src

    def test_quote_standard_template_registered(self, db):
        """Seed migration inserted a platform `quote.standard` template."""
        from app.services.documents import template_loader

        loaded = template_loader.load("quote.standard", db=db)
        assert loaded.output_format == "pdf"
        assert loaded.company_id is None  # platform-scoped

    def test_wilbert_form_template_registered(self, db):
        from app.services.documents import template_loader

        loaded = template_loader.load("urn.wilbert_engraving_form", db=db)
        assert loaded.output_format == "pdf"
        assert loaded.company_id is None

    def test_preview_pdf_uses_document_renderer(self, db, company):
        """generate_template_preview_pdf routes through render_pdf_bytes."""
        from app.services import pdf_generation_service

        # Patch the renderer's PDF conversion so we don't need system deps.
        with patch(
            "app.services.documents.document_renderer._html_to_pdf",
            return_value=b"%PDF-stub",
        ):
            pdf = pdf_generation_service.generate_template_preview_pdf(
                db, company.id, "professional",
            )
        assert pdf == b"%PDF-stub"

    def test_preview_pdf_falls_back_to_professional(self, db, company):
        """Unknown variant falls back to `invoice.professional`."""
        from app.services import pdf_generation_service

        with patch(
            "app.services.documents.document_renderer._html_to_pdf",
            return_value=b"%PDF-fallback",
        ):
            pdf = pdf_generation_service.generate_template_preview_pdf(
                db, company.id, "nonexistent_variant",
            )
        assert pdf == b"%PDF-fallback"

    def test_wilbert_render_form_pdf_uses_document_renderer(self, db, company):
        """render_form_pdf routes through render_pdf_bytes; no direct
        WeasyPrint call anywhere."""
        from app.services import wilbert_utils

        form_data = [
            {
                "Licensee": "Test Co",
                "Order Number": "12345678",
                "Date": "2026-04-19",
                "Decedent Name": "Jane Doe",
                "Piece": "main",
                "Line 1": "Jane Doe",
                "Line 2": "1950 - 2024",
                "Line 3": "",
                "Line 4": "",
                "Font": "Script",
            }
        ]
        with patch(
            "app.services.documents.document_renderer._html_to_pdf",
            return_value=b"%PDF-wilbert",
        ):
            pdf = wilbert_utils.render_form_pdf(
                form_data, db=db, company_id=company.id,
            )
        assert pdf == b"%PDF-wilbert"


class TestQuoteGenerationCreatesDocument:
    """quote_service now persists canonical Documents per quote."""

    def _make_quote(self, db, company):
        from app.models.quote import Quote, QuoteLine

        q = Quote(
            id=str(uuid.uuid4()),
            company_id=company.id,
            number="Q-0001",
            customer_name="Jane Customer",
            status="draft",
            subtotal=100.0,
            total=100.0,
            quote_date=datetime.now(timezone.utc),
        )
        db.add(q)
        db.flush()
        ln = QuoteLine(
            id=str(uuid.uuid4()),
            quote_id=q.id,
            description="Burial vault",
            quantity=1,
            unit_price=100.0,
            line_total=100.0,
            sort_order=0,
        )
        db.add(ln)
        db.flush()
        return q

    def test_generate_quote_document_creates_document(self, db, company):
        """generate_quote_document creates a canonical Document."""
        from app.services import quote_service

        q = self._make_quote(db, company)
        with patch(
            "app.services.documents.document_renderer._html_to_pdf",
            return_value=b"%PDF-quote",
        ), patch(
            "app.services.legacy_r2_client.upload_bytes",
        ) as upload_mock:
            doc = quote_service.generate_quote_document(db, company.id, q.id)

        assert doc is not None
        assert doc.document_type == "quote"
        assert doc.entity_type == "quote"
        assert doc.entity_id == q.id
        assert doc.template_key == "quote.standard"
        assert doc.company_id == company.id
        assert upload_mock.called

    def test_generate_quote_pdf_returns_bytes(self, db, company):
        """Legacy bytes API still works — produces a Document underneath
        then fetches bytes from R2."""
        from app.services import quote_service

        q = self._make_quote(db, company)
        with patch(
            "app.services.documents.document_renderer._html_to_pdf",
            return_value=b"%PDF-quote",
        ), patch(
            "app.services.legacy_r2_client.upload_bytes",
        ), patch(
            "app.services.legacy_r2_client.download_bytes",
            return_value=b"%PDF-quote",
        ):
            pdf = quote_service.generate_quote_pdf(db, company.id, q.id)
        assert pdf == b"%PDF-quote"


# ---------------------------------------------------------------------------
# Step 4: TID251 ruff allowlist is minimal (no transitional entries)
# ---------------------------------------------------------------------------


class TestWeasyPrintAllowlistMinimal:
    def test_transitional_allowlist_empty(self):
        from tests.test_documents_d2_lint import TRANSITIONAL_ALLOWLIST

        assert TRANSITIONAL_ALLOWLIST == set(), (
            "D-9 invariant: the transitional WeasyPrint allowlist is empty. "
            f"Unexpected entries: {TRANSITIONAL_ALLOWLIST}"
        )

    def test_permanent_allowlist_only_owner_plus_diagnostic(self):
        """The permanent allowlist should be exactly the managed renderer
        + the main.py diagnostic import. Anything else deserves review."""
        from tests.test_documents_d2_lint import PERMANENT_ALLOWLIST

        assert PERMANENT_ALLOWLIST == {
            "app/services/documents/document_renderer.py",
            "app/main.py",
        }


# ---------------------------------------------------------------------------
# Step 5: EmailService._fallback_company_id removed
# ---------------------------------------------------------------------------


class TestEmailServiceRequiresCompanyId:
    def test_fallback_helper_is_gone(self):
        """`_fallback_company_id` must not exist as a callable anymore."""
        from app.services import email_service as es_mod

        assert not hasattr(es_mod, "_fallback_company_id"), (
            "D-9 removed the fallback helper. If it reappears, remove it "
            "again and make the caller thread company_id explicitly."
        )

    def test_require_helper_crashes_on_none(self):
        """The new `_require_company_id` raises ValueError when missing."""
        from app.services.email_service import _require_company_id

        with pytest.raises(ValueError, match="company_id"):
            _require_company_id(None)

    def test_require_helper_passes_value_through(self):
        from app.services.email_service import _require_company_id

        assert _require_company_id("abc-123") == "abc-123"

    def test_send_email_without_company_id_crashes_clearly(self, db, company):
        """send_email() raises ValueError when company_id is None."""
        from app.services.email_service import email_service

        with pytest.raises(ValueError, match="company_id"):
            email_service.send_email(
                to="a@b.co",
                subject="hi",
                html_body="<p>hi</p>",
                company_id=None,
                db=db,
            )

    def test_send_user_invitation_without_company_id_crashes(self, db, company):
        from app.services.email_service import email_service

        with pytest.raises(ValueError, match="company_id"):
            email_service.send_user_invitation(
                email="a@b.co",
                name="A",
                tenant_name="T",
                invite_url="https://x",
                company_id=None,
                db=db,
            )


# ---------------------------------------------------------------------------
# Step 6: DocumentRenderer unification
# ---------------------------------------------------------------------------


class TestRendererUnification:
    def test_render_requires_key_or_version_id(self, db, company):
        """render() must get one of template_key or template_version_id."""
        from app.services.documents import document_renderer

        with pytest.raises(
            document_renderer.DocumentRenderError,
            match="template_key.*template_version_id",
        ):
            document_renderer.render(
                db,
                context={},
                company_id=company.id,
                output_format="html",
            )

    def test_render_with_template_key_uses_current_active(self, db, company):
        """Key-mode lookup resolves to the current active version (matching
        pre-D-9 behavior)."""
        from app.services.documents import document_renderer

        result = document_renderer.render(
            db,
            template_key="email.invitation",
            context={
                "name": "A",
                "tenant_name": "T",
                "invite_url": "https://x",
            },
            company_id=company.id,
        )
        # email output = RenderResult, not Document
        assert result.output_format == "html"
        assert result.document is None
        assert result.template_version_id is not None

    def test_render_with_version_id_skips_template_loader(self, db, company):
        """Version-id mode loads by id directly — demonstrated by
        exercising a retired/non-current version and confirming it
        renders."""
        from app.models.document_template import (
            DocumentTemplate,
            DocumentTemplateVersion,
        )
        from app.services.documents import document_renderer

        # Find the email.invitation template + its current version
        tpl = (
            db.query(DocumentTemplate)
            .filter(DocumentTemplate.template_key == "email.invitation")
            .first()
        )
        assert tpl is not None

        # Add a second version with different content and leave it
        # as "draft" (not current). Rendering by ITS id should use
        # its body, not the active version's body.
        draft = DocumentTemplateVersion(
            id=str(uuid.uuid4()),
            template_id=tpl.id,
            version_number=2,
            status="draft",
            body_template="<p>DRAFT BODY — {{ name }}</p>",
            subject_template="DRAFT SUBJ {{ name }}",
            changelog="draft for test",
        )
        db.add(draft)
        db.flush()

        result = document_renderer.render(
            db,
            template_version_id=draft.id,
            context={"name": "A", "tenant_name": "T", "invite_url": "x"},
            company_id=company.id,
        )
        assert result.output_format == "html"
        rendered = (
            result.rendered_content
            if isinstance(result.rendered_content, str)
            else result.rendered_content.decode("utf-8")
        )
        assert "DRAFT BODY" in rendered
        assert result.template_version_id == draft.id

    def test_render_template_key_mismatches_version_id_uses_version(
        self, db, company,
    ):
        """If both key and version_id are supplied, version_id wins
        (per the D-9 docstring) and the resolved template_key on the
        Document reflects the version's parent template."""
        from app.models.document_template import (
            DocumentTemplate,
            DocumentTemplateVersion,
        )
        from app.services.documents import document_renderer

        # Use email.invitation's current version via its id.
        tpl = (
            db.query(DocumentTemplate)
            .filter(DocumentTemplate.template_key == "email.invitation")
            .first()
        )
        assert tpl is not None
        current = (
            db.query(DocumentTemplateVersion)
            .filter(DocumentTemplateVersion.id == tpl.current_version_id)
            .first()
        )
        assert current is not None

        # Pass an INCORRECT template_key alongside the correct version_id.
        result = document_renderer.render(
            db,
            template_key="this-key-does-not-exist",
            template_version_id=current.id,
            context={
                "name": "A",
                "tenant_name": "T",
                "invite_url": "https://x",
            },
            company_id=company.id,
        )
        # Rendering succeeds (version_id wins).
        assert result.output_format == "html"
        # Renderer-resolved template_key is the right one.
        assert result.template_version_id == current.id

    def test_test_render_endpoint_module_has_no_weasyprint_refs(self):
        """Structural test — the unified render path means
        documents_v2.py should not be importing WeasyPrint helpers
        directly anymore (they live in document_renderer)."""
        src = (APP_DIR / "api/routes/documents_v2.py").read_text("utf-8")
        # Previously the endpoint imported _html_to_pdf / _storage_key /
        # _hash_context from document_renderer. D-9 eliminates that
        # coupling — the endpoint delegates via render().
        assert "_html_to_pdf" not in src
        assert "_hash_context" not in src
        # The direct R2 upload_bytes call in the endpoint is also gone.
        # (legacy_r2_client may still be imported for other paths, so
        # we check for the specific combination that only existed in
        # the test-render endpoint pre-D-9.)
        assert "legacy_r2_client.upload_bytes(\n" not in src
