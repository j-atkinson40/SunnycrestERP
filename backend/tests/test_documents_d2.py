"""Phase D-2 tests — managed template registry + HTML output + migrated
inline-HTML generators + migrated email templates + API endpoints.

Mirrors test_documents_d1.py's SQLite-in-memory pattern — creates the
subset of tables the Document + DocumentTemplate paths need, seeds the
18 platform templates, then exercises each workflow.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import JSON, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.database import Base


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:")

    # Register models needed for this suite.
    from app.models.canonical_document import Document, DocumentVersion  # noqa: F401
    from app.models.company import Company  # noqa: F401
    from app.models.customer import Customer  # noqa: F401
    from app.models.disinterment_case import DisintermentCase  # noqa: F401
    from app.models.document_template import (  # noqa: F401
        DocumentTemplate,
        DocumentTemplateVersion,
    )
    from app.models.document_delivery import DocumentDelivery  # noqa: F401
    from app.models.fh_case import FHCase  # noqa: F401
    from app.models.invoice import Invoice  # noqa: F401
    from app.models.price_list_version import PriceListVersion  # noqa: F401
    from app.models.role import Role  # noqa: F401
    from app.models.safety_program_generation import SafetyProgramGeneration  # noqa: F401
    from app.models.sales_order import SalesOrder  # noqa: F401
    from app.models.statement import CustomerStatement  # noqa: F401
    from app.models.user import User  # noqa: F401
    from app.models.workflow import WorkflowRun, WorkflowRunStep  # noqa: F401
    from app.models.company_entity import CompanyEntity  # noqa: F401
    from app.models.agent import AgentJob  # noqa: F401

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
        "document_deliveries",
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
    _seed_platform_templates(session)
    yield session
    session.close()
    trans.rollback()
    conn.close()


def _seed_platform_templates(session: Session) -> None:
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
            changelog="test-seed",
            activated_at=datetime.now(timezone.utc),
        )
        session.add(ver)
        session.flush()
        tpl.current_version_id = ver.id
    session.flush()


@pytest.fixture
def company(db):
    from app.models.company import Company

    c = Company(id=str(uuid.uuid4()), name="Test Co", slug="testco", is_active=True)
    db.add(c)
    db.flush()
    return c


# ---------------------------------------------------------------------------
# Template registry tests
# ---------------------------------------------------------------------------


class TestTemplateRegistry:
    def test_platform_seed_loads_all_expected_keys(self, db):
        """Migration seeded all 18 expected platform template keys."""
        from app.services.documents._template_seeds import (
            list_platform_template_seeds,
        )
        from app.models.document_template import DocumentTemplate

        expected = {s["template_key"] for s in list_platform_template_seeds()}
        actual = {
            row[0]
            for row in db.query(DocumentTemplate.template_key)
            .filter(DocumentTemplate.company_id.is_(None))
            .all()
        }
        assert actual == expected
        assert len(expected) >= 15  # 8 PDF + 3 inline + 7 email = 18

    def test_platform_seed_has_both_pdf_and_html_formats(self, db):
        from app.models.document_template import DocumentTemplate

        formats = {
            row[0]
            for row in db.query(DocumentTemplate.output_format).all()
        }
        assert "pdf" in formats
        assert "html" in formats

    def test_tenant_template_overrides_platform(self, db, company):
        """Creating a tenant-scoped row with the same template_key makes
        load() resolve to the tenant's version."""
        from app.models.document_template import (
            DocumentTemplate,
            DocumentTemplateVersion,
        )
        from app.services.documents import template_loader

        tpl = DocumentTemplate(
            id=str(uuid.uuid4()),
            company_id=company.id,
            template_key="invoice.professional",
            document_type="invoice",
            output_format="pdf",
            description="Tenant override",
            is_active=True,
        )
        db.add(tpl)
        db.flush()
        v = DocumentTemplateVersion(
            id=str(uuid.uuid4()),
            template_id=tpl.id,
            version_number=1,
            status="active",
            body_template="<html>TENANT_OVERRIDE</html>",
            activated_at=datetime.now(timezone.utc),
        )
        db.add(v)
        db.flush()
        tpl.current_version_id = v.id
        db.flush()

        loaded = template_loader.load(
            "invoice.professional", company_id=company.id, db=db
        )
        assert "TENANT_OVERRIDE" in loaded.body_template
        assert loaded.is_tenant_override is True
        assert loaded.company_id == company.id

    def test_tenant_falls_back_to_platform_when_no_override(self, db, company):
        """When a tenant has no override, load() returns the platform row."""
        from app.services.documents import template_loader

        loaded = template_loader.load(
            "invoice.professional", company_id=company.id, db=db
        )
        assert loaded.company_id is None  # platform
        assert loaded.is_tenant_override is False
        assert loaded.output_format == "pdf"

    def test_template_lookup_raises_on_unknown_key(self, db):
        from app.services.documents import template_loader

        with pytest.raises(template_loader.TemplateNotFoundError):
            template_loader.load("nonexistent.template", db=db)


# ---------------------------------------------------------------------------
# Renderer extension tests
# ---------------------------------------------------------------------------


class TestRendererFormats:
    def test_render_pdf_creates_document(self, db, company):
        from app.services.documents import document_renderer
        from app.models.canonical_document import Document

        with patch(
            "app.services.documents.document_renderer._html_to_pdf"
        ) as mock_pdf, patch(
            "app.services.documents.document_renderer.legacy_r2_client"
        ) as mock_r2:
            mock_pdf.return_value = b"%PDF-1.4 fake"
            mock_r2.upload_bytes = lambda *a, **kw: None

            doc = document_renderer.render(
                db,
                template_key="invoice.professional",
                context={"invoice_number": "INV-1"},
                document_type="invoice",
                title="Invoice INV-1",
                company_id=company.id,
            )
        assert isinstance(doc, Document)
        assert doc.template_key == "invoice.professional"
        assert doc.file_size_bytes == len(b"%PDF-1.4 fake")

    def test_render_html_returns_string_no_document(self, db, company):
        from app.services.documents import document_renderer
        from app.models.canonical_document import Document

        result = document_renderer.render_html(
            db,
            template_key="email.statement",
            context={
                "customer_name": "Joe",
                "tenant_name": "Wilbert",
                "statement_month": "April 2026",
            },
            company_id=company.id,
        )
        assert result.output_format == "html"
        assert result.document is None
        assert isinstance(result.rendered_content, str)
        assert "Joe" in result.rendered_content
        assert "Wilbert" in result.rendered_content
        # No Document row should be persisted
        assert (
            db.query(Document).filter(Document.title.ilike("%statement%")).count()
            == 0
        )

    def test_render_with_subject_template(self, db, company):
        from app.services.documents import document_renderer

        result = document_renderer.render_html(
            db,
            template_key="email.statement",
            context={
                "customer_name": "Joe",
                "tenant_name": "Wilbert",
                "statement_month": "April 2026",
            },
            company_id=company.id,
        )
        assert result.rendered_subject is not None
        assert "April 2026" in result.rendered_subject
        assert "Wilbert" in result.rendered_subject

    def test_render_text_output(self, db, company):
        """Create a text template + verify render_text() returns string."""
        from app.models.document_template import (
            DocumentTemplate,
            DocumentTemplateVersion,
        )
        from app.services.documents import document_renderer

        tpl = DocumentTemplate(
            id=str(uuid.uuid4()),
            company_id=None,
            template_key="test.text_only",
            document_type="test",
            output_format="text",
            is_active=True,
        )
        db.add(tpl)
        db.flush()
        v = DocumentTemplateVersion(
            id=str(uuid.uuid4()),
            template_id=tpl.id,
            version_number=1,
            status="active",
            body_template="Hello {{ name }}",
            activated_at=datetime.now(timezone.utc),
        )
        db.add(v)
        db.flush()
        tpl.current_version_id = v.id
        db.flush()

        result = document_renderer.render_text(
            db,
            template_key="test.text_only",
            context={"name": "World"},
            company_id=company.id,
        )
        assert result.output_format == "text"
        assert result.rendered_content == "Hello World"
        assert result.document is None

    def test_render_with_tenant_override_uses_tenant_version(self, db, company):
        from app.models.document_template import (
            DocumentTemplate,
            DocumentTemplateVersion,
        )
        from app.services.documents import document_renderer

        tpl = DocumentTemplate(
            id=str(uuid.uuid4()),
            company_id=company.id,
            template_key="email.statement",
            document_type="email",
            output_format="html",
            is_active=True,
        )
        db.add(tpl)
        db.flush()
        v = DocumentTemplateVersion(
            id=str(uuid.uuid4()),
            template_id=tpl.id,
            version_number=1,
            status="active",
            body_template=(
                "<html><body>CUSTOM TENANT STATEMENT for "
                "{{ customer_name }}</body></html>"
            ),
            subject_template="Custom: {{ statement_month }}",
            activated_at=datetime.now(timezone.utc),
        )
        db.add(v)
        db.flush()
        tpl.current_version_id = v.id
        db.flush()

        result = document_renderer.render_html(
            db,
            template_key="email.statement",
            context={
                "customer_name": "Joe",
                "tenant_name": "Wilbert",
                "statement_month": "April 2026",
            },
            company_id=company.id,
        )
        assert "CUSTOM TENANT STATEMENT" in result.rendered_content
        assert result.rendered_subject == "Custom: April 2026"

    def test_render_pdf_bytes_no_document_row(self, db, company):
        from app.models.canonical_document import Document
        from app.services.documents import document_renderer

        with patch(
            "app.services.documents.document_renderer._html_to_pdf"
        ) as mock_pdf:
            mock_pdf.return_value = b"%PDF fake"
            b = document_renderer.render_pdf_bytes(
                db,
                template_key="invoice.professional",
                context={"invoice_number": "X"},
                company_id=company.id,
            )
        assert b == b"%PDF fake"
        # No Document row persisted
        assert db.query(Document).count() == 0


# ---------------------------------------------------------------------------
# Migrated inline-HTML generators
# ---------------------------------------------------------------------------


class TestMigratedInlineGenerators:
    def test_social_service_cert_uses_managed_template(self, db, company):
        from decimal import Decimal

        from app.services.documents import document_renderer
        from app.utils.pdf_generators.social_service_certificate_pdf import (
            generate_social_service_certificate_pdf,
        )

        sentinel = {"n_calls": 0}

        def fake_pdf(html, base_url=None):
            sentinel["n_calls"] += 1
            # Assert Jinja actually rendered the template (look for
            # distinctive template text + the substituted certificate
            # number proving the context flowed through).
            assert "Service Delivery Certificate" in html
            assert "SO-42-SSC" in html
            return b"%PDF fake"

        with patch.object(document_renderer, "_html_to_pdf", side_effect=fake_pdf):
            result = generate_social_service_certificate_pdf(
                certificate_number="SO-42-SSC",
                deceased_name="John Doe",
                funeral_home_name="Smith FH",
                cemetery_name="Oakwood",
                product_name="Social Service Graveliner",
                product_price=Decimal("495.00"),
                delivered_at=datetime.now(timezone.utc),
                company_config={"name": "Sunnycrest"},
                db=db,
                company_id=company.id,
            )
        assert result == b"%PDF fake"
        assert sentinel["n_calls"] == 1

    def test_safety_program_wrapper_uses_managed_template(self, db, company):
        """_wrap_program_html now routes through document_renderer with the
        pdf.safety_program_base template."""
        from app.services.safety_program_generation_service import (
            _wrap_program_html,
        )

        html = _wrap_program_html(
            content="<h2>Fall Protection</h2><p>Content here.</p>",
            title="Fall Protection Program",
            company_name="Acme Precast",
            osha_standard="29 CFR 1926.501",
            db=db,
            company_id=company.id,
        )
        # Base wrapper markers
        assert "Written Safety Program" in html
        # Content passed through via ai_generated_html|safe
        assert "<h2>Fall Protection</h2>" in html
        assert "Content here." in html
        # Branding context populated
        assert "Acme Precast" in html
        assert "29 CFR 1926.501" in html

    def test_legacy_vault_print_wrapper_template(self, db, company):
        """The pdf.legacy_vault_print template renders via render_pdf_bytes
        with the expected Jinja vars."""
        from app.services.documents import document_renderer

        with patch.object(
            document_renderer, "_html_to_pdf"
        ) as mock_pdf:
            mock_pdf.return_value = b"%PDF fake"
            b = document_renderer.render_pdf_bytes(
                db,
                template_key="pdf.legacy_vault_print",
                context={
                    "fh_name": "TOWN FH",
                    "deceased_name": "JANE SMITH",
                    "life_span": "1940 — 2026",
                    "vault_product_name": "Monticello",
                    "personalization_line": "Emblem: rose",
                    "service_date_line": "Friday, May 3, 2026",
                    "service_location": "Oakwood Chapel",
                    "case_number": "CASE-1",
                    "order_ref": "abcd1234",
                },
                company_id=company.id,
            )
        assert b == b"%PDF fake"
        # The call argument (html) should contain our context
        rendered_html = mock_pdf.call_args.args[0]
        assert "TOWN FH" in rendered_html
        assert "JANE SMITH" in rendered_html
        assert "Monticello" in rendered_html


# ---------------------------------------------------------------------------
# Migrated email templates
# ---------------------------------------------------------------------------


class TestMigratedEmailTemplates:
    def test_all_email_templates_renderable(self, db, company):
        """Every platform email template must Jinja-render with a minimal
        context. This protects against template-syntax regressions."""
        from app.services.documents import document_renderer
        from app.services.documents._template_seeds import (
            list_platform_template_seeds,
        )

        email_seeds = [
            s
            for s in list_platform_template_seeds()
            if s["output_format"] == "html"
        ]
        assert len(email_seeds) >= 5

        # Minimal context covering ALL possible variables across every email
        base_context = {
            "subject": "Test",
            "header_sub": "Sub",
            "body_content": "<p>Test</p>",
            "footer_text": "Footer",
            "customer_name": "Joe",
            "tenant_name": "Wilbert",
            "statement_month": "April 2026",
            "body_paragraphs": ["One.", "Two."],
            "name": "Joe",
            "invite_url": "https://example.com/accept",
            "migration_url": "https://example.com/migrate",
            "expires_days": 7,
            "support_email": "support@example.com",
            "alerts": [{"title": "T", "summary": "S"}],
            "count": 1,
            "plural": "",
            "company_name": "Acme",
            "header_color": "#000",
            "logo_html": "<h1>Logo</h1>",
            "proof_url": "https://example.com/proof.jpg",
            "inscription_name": "John Smith",
            "inscription_dates": "1940-2026",
            "inscription_additional": "",
            "print_name": "Custom",
            "service_date": "May 1, 2026",
            "custom_notes": "",
            "watermark_enabled": False,
        }
        for seed in email_seeds:
            result = document_renderer.render_html(
                db,
                template_key=seed["template_key"],
                context=base_context,
                company_id=company.id,
            )
            assert isinstance(result.rendered_content, str)
            assert len(result.rendered_content) > 50

    def test_email_statement_uses_managed_template(self, db, company):
        """EmailService.send_statement_email routes through the managed
        email.statement template. Verify by spying on the renderer."""
        from app.services.email_service import email_service
        from app.services.documents import document_renderer

        captured = {"html": None, "subject": None}
        real_render_html = document_renderer.render_html

        def spy(db_arg, *, template_key, context, company_id=None):
            result = real_render_html(
                db_arg,
                template_key=template_key,
                context=context,
                company_id=company_id,
            )
            if template_key == "email.statement":
                captured["html"] = result.rendered_content
                captured["subject"] = result.rendered_subject
            return result

        with patch.object(
            document_renderer, "render_html", side_effect=spy
        ):
            out = email_service.send_statement_email(
                customer_email="ops@fh.com",
                customer_name="Ops Person",
                tenant_name="Wilbert Sunnycrest",
                statement_month="April 2026",
                company_id=company.id,
                db=db,
            )
        assert out.get("success") is True or out.get("message_id") == "test-mode"
        assert captured["html"] is not None
        assert "Ops Person" in captured["html"]
        assert captured["subject"] and "April 2026" in captured["subject"]

    def test_email_collections_uses_managed_template(self, db, company):
        from app.services.email_service import email_service
        from app.services.documents import document_renderer

        captured = {"html": None}
        real = document_renderer.render_html

        def spy(db_arg, *, template_key, context, company_id=None):
            res = real(
                db_arg,
                template_key=template_key,
                context=context,
                company_id=company_id,
            )
            if template_key == "email.collections":
                captured["html"] = res.rendered_content
            return res

        with patch.object(
            document_renderer, "render_html", side_effect=spy
        ):
            email_service.send_collections_email(
                customer_email="x@y.co",
                customer_name="Carol Customer",
                subject="Please pay",
                body="You owe us money.\n\nPlease send payment.",
                tenant_name="Sunnycrest",
                reply_to_email="ar@sunnycrest.com",
                company_id=company.id,
                db=db,
            )
        assert captured["html"] is not None
        assert "Carol Customer" in captured["html"]
        assert "You owe us money." in captured["html"]
        assert "Please send payment." in captured["html"]


# ---------------------------------------------------------------------------
# Template service + admin endpoints
# ---------------------------------------------------------------------------


class TestTemplateService:
    def test_list_templates_scoped_correctly(self, db, company):
        from app.services.documents import template_service

        # No scope arg → platform + tenant; tenant has no overrides so
        # only platform rows show.
        items, total = template_service.list_templates(
            db, current_company_id=company.id, limit=50
        )
        assert total >= 15
        for item in items:
            assert item["scope"] in ("platform", "tenant")

    def test_list_templates_filter_by_output_format(self, db, company):
        from app.services.documents import template_service

        items, total = template_service.list_templates(
            db,
            current_company_id=company.id,
            output_format="html",
            limit=50,
        )
        assert total >= 5
        for item in items:
            assert item["output_format"] == "html"

    def test_list_templates_platform_scope_only(self, db, company):
        from app.models.document_template import (
            DocumentTemplate,
            DocumentTemplateVersion,
        )
        from app.services.documents import template_service

        # Create a tenant override + verify scope="platform" hides it
        tpl = DocumentTemplate(
            id=str(uuid.uuid4()),
            company_id=company.id,
            template_key="tenant.custom",
            document_type="custom",
            output_format="html",
            is_active=True,
        )
        db.add(tpl)
        db.flush()
        v = DocumentTemplateVersion(
            id=str(uuid.uuid4()),
            template_id=tpl.id,
            version_number=1,
            status="active",
            body_template="<x/>",
            activated_at=datetime.now(timezone.utc),
        )
        db.add(v)
        db.flush()
        tpl.current_version_id = v.id
        db.flush()

        items, _ = template_service.list_templates(
            db,
            current_company_id=company.id,
            scope="platform",
            limit=500,
        )
        keys = {i["template_key"] for i in items}
        assert "tenant.custom" not in keys

        # Without scope filter, tenant row is visible
        items, _ = template_service.list_templates(
            db, current_company_id=company.id, limit=500
        )
        keys = {i["template_key"] for i in items}
        assert "tenant.custom" in keys

    def test_get_template_detail_includes_active_version(self, db, company):
        from app.models.document_template import DocumentTemplate
        from app.services.documents import template_service

        platform = (
            db.query(DocumentTemplate)
            .filter(
                DocumentTemplate.template_key == "invoice.professional",
                DocumentTemplate.company_id.is_(None),
            )
            .first()
        )
        detail = template_service.get_template_detail(
            db, platform.id, current_company_id=company.id
        )
        assert detail is not None
        assert detail["template_key"] == "invoice.professional"
        assert detail["current_version"] is not None
        assert detail["current_version"]["version_number"] == 1
        assert len(detail["version_summaries"]) >= 1

    def test_get_template_detail_rejects_other_tenant(self, db):
        from app.models.company import Company
        from app.models.document_template import (
            DocumentTemplate,
            DocumentTemplateVersion,
        )
        from app.services.documents import template_service

        # Create tenant A with its own template
        tenant_a = Company(
            id=str(uuid.uuid4()), name="A", slug="a", is_active=True
        )
        db.add(tenant_a)
        db.flush()
        tpl = DocumentTemplate(
            id=str(uuid.uuid4()),
            company_id=tenant_a.id,
            template_key="tenant.a.secret",
            document_type="x",
            output_format="html",
            is_active=True,
        )
        db.add(tpl)
        db.flush()
        v = DocumentTemplateVersion(
            id=str(uuid.uuid4()),
            template_id=tpl.id,
            version_number=1,
            status="active",
            body_template="secret",
            activated_at=datetime.now(timezone.utc),
        )
        db.add(v)
        db.flush()
        tpl.current_version_id = v.id
        db.flush()

        # Tenant B tries to read it
        tenant_b = Company(
            id=str(uuid.uuid4()), name="B", slug="b", is_active=True
        )
        db.add(tenant_b)
        db.flush()
        detail = template_service.get_template_detail(
            db, tpl.id, current_company_id=tenant_b.id
        )
        assert detail is None


# ---------------------------------------------------------------------------
# Lint rule (smoke test — full logic lives in test_documents_d2_lint.py)
# ---------------------------------------------------------------------------


class TestLintRule:
    def test_weasyprint_import_forbidden_outside_documents(self):
        """Import the lint module and verify it finds the expected
        permanent+transitional allowlist entries (smoke test — the real
        test lives in test_documents_d2_lint.py)."""
        from tests.test_documents_d2_lint import (
            PERMANENT_ALLOWLIST,
            TRANSITIONAL_ALLOWLIST,
        )

        assert (
            "app/services/documents/document_renderer.py"
            in PERMANENT_ALLOWLIST
        )
        # Main diagnostic should be permanently allowlisted
        assert "app/main.py" in PERMANENT_ALLOWLIST
        # Future-migration targets should be transitional
        assert (
            "app/services/pdf_generation_service.py"
            in TRANSITIONAL_ALLOWLIST
        )
