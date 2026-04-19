"""Phase D-1 tests — canonical Document backbone.

Covers:
  - DocumentRenderer.render creates Document + DocumentVersion rows
  - storage_key follows the tenant-scoped path convention
  - All linkage columns (polymorphic + specialty) populate correctly
  - rendering_context_hash is computed for every render
  - rerender creates a new version, flips is_current, updates Document.storage_key
  - Template-missing errors surface as DocumentRenderError
  - WeasyPrint-missing errors surface as DocumentRenderError
  - Workflow engine generate_document action creates a Document
  - Workflow output is structured for downstream step reference
  - API: list/detail/download/regenerate work as expected
  - API: all endpoints admin-gated (source-level lint)

Tests mock WeasyPrint and R2 to avoid system dependencies — the
DocumentRenderer.render path is exercised end-to-end with the real
SQLAlchemy layer + a stubbed upload_bytes + a stubbed HTML-to-PDF.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

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

    # Import every model class that the canonical Document references via FK
    # so Base.metadata has their tables registered before we subset.
    from app.models.agent import AgentJob  # noqa: F401
    from app.models.canonical_document import Document, DocumentVersion  # noqa: F401
    from app.models.company import Company  # noqa: F401
    from app.models.customer import Customer  # noqa: F401
    from app.models.disinterment_case import DisintermentCase  # noqa: F401
    from app.models.fh_case import FHCase  # noqa: F401
    from app.models.invoice import Invoice  # noqa: F401
    from app.models.price_list_version import PriceListVersion  # noqa: F401
    from app.models.role import Role  # noqa: F401
    from app.models.safety_program_generation import SafetyProgramGeneration  # noqa: F401
    from app.models.sales_order import SalesOrder  # noqa: F401
    from app.models.statement import CustomerStatement  # noqa: F401
    from app.models.user import User  # noqa: F401
    from app.models.workflow import WorkflowRun, WorkflowRunStep  # noqa: F401

    # Import CompanyEntity so DisintermentCase's joined-load on cemetery/fh
    # resolves (both point at company_entities via the master_company pattern).
    from app.models.company_entity import CompanyEntity  # noqa: F401

    # D-2: template registry tables
    from app.models.document_template import (  # noqa: F401
        DocumentTemplate,
        DocumentTemplateVersion,
    )
    # D-6: cross-tenant sharing tables
    from app.models.document_share import (  # noqa: F401
        DocumentShare,
        DocumentShareEvent,
    )

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
        "document_shares",
        "document_share_events",
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

    # D-2: seed platform templates so template_loader.load() resolves
    # keys like "disinterment.release_form", "invoice.professional", etc.
    # We seed directly into this transaction so each test gets a clean copy.
    _seed_platform_templates(session)

    yield session
    session.close()
    trans.rollback()
    conn.close()


def _seed_platform_templates(session: Session) -> None:
    """Insert the 18 platform template seeds so tests can load() them.
    Keeps the test DB schema matching production's post-r21 state."""
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


@pytest.fixture
def admin_role(db, company):
    from app.models.role import Role

    r = Role(
        id=str(uuid.uuid4()),
        company_id=company.id,
        name="Admin",
        slug="admin",
        is_system=True,
    )
    db.add(r)
    db.flush()
    return r


@pytest.fixture
def admin_user(db, company, admin_role):
    from app.models.user import User

    u = User(
        id=str(uuid.uuid4()),
        company_id=company.id,
        email="admin@test.co",
        first_name="Ada",
        last_name="Admin",
        hashed_password="x",
        is_active=True,
        is_super_admin=False,
        role_id=admin_role.id,
    )
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def mock_renderer_deps():
    """Replace WeasyPrint + R2 with predictable stubs. The DocumentRenderer
    still executes the full Jinja render + DB write path — only the
    expensive external calls are stubbed."""
    uploads: list[tuple[bytes, str]] = []

    def fake_upload(data: bytes, r2_key: str, content_type: str = "application/pdf"):
        uploads.append((data, r2_key))
        return f"https://r2.test/{r2_key}"

    def fake_html_to_pdf(html: str, base_url: str | None = None) -> bytes:
        return f"%PDF-TEST:{len(html)}".encode("utf-8")

    with (
        patch(
            "app.services.documents.document_renderer.legacy_r2_client.upload_bytes",
            side_effect=fake_upload,
        ),
        patch(
            "app.services.documents.document_renderer._html_to_pdf",
            side_effect=fake_html_to_pdf,
        ),
    ):
        yield uploads


# ---------------------------------------------------------------------------
# DocumentRenderer.render
# ---------------------------------------------------------------------------


class TestRender:
    def test_creates_document_and_version(
        self, db, company, admin_user, mock_renderer_deps
    ):
        from app.models.canonical_document import Document, DocumentVersion
        from app.services.documents import document_renderer

        doc = document_renderer.render(
            db,
            template_key="invoice.professional",
            context={"invoice_number": "INV-1", "total": "100"},
            document_type="invoice",
            title="Invoice INV-1",
            company_id=company.id,
            entity_type="invoice",
            entity_id="inv-1",
            rendered_by_user_id=admin_user.id,
        )

        # Document row persisted
        fetched = db.query(Document).filter(Document.id == doc.id).first()
        assert fetched is not None
        assert fetched.document_type == "invoice"
        assert fetched.title == "Invoice INV-1"
        assert fetched.template_key == "invoice.professional"
        assert fetched.status == "rendered"
        assert fetched.rendered_by_user_id == admin_user.id
        assert fetched.file_size_bytes is not None and fetched.file_size_bytes > 0
        assert fetched.rendering_context_hash is not None
        # DocumentVersion row persisted
        versions = (
            db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == doc.id)
            .all()
        )
        assert len(versions) == 1
        assert versions[0].version_number == 1
        assert versions[0].is_current is True
        assert versions[0].render_reason == "initial"
        assert versions[0].storage_key == fetched.storage_key

    def test_storage_key_follows_tenant_scoped_convention(
        self, db, company, mock_renderer_deps
    ):
        from app.services.documents import document_renderer

        doc = document_renderer.render(
            db,
            template_key="invoice.professional",
            context={"invoice_number": "INV-2"},
            document_type="invoice",
            title="Invoice INV-2",
            company_id=company.id,
        )
        assert doc.storage_key.startswith(f"tenants/{company.id}/documents/")
        assert doc.storage_key.endswith("/v1.pdf")
        assert doc.id in doc.storage_key

    def test_populates_all_linkage_columns(
        self, db, company, admin_user, mock_renderer_deps
    ):
        from app.services.documents import document_renderer

        doc = document_renderer.render(
            db,
            template_key="disinterment.release_form",
            context={
                "company_name": "X",
                "case_number": "CASE-1",
                "generated_date": "Jan 1, 2026",
                "decedent_name": "J Doe",
                "date_of_death": None,
                "date_of_burial": None,
                "vault_description": "Triune",
                "cemetery_name": "Rosedale",
                "cemetery_lot_section": "A",
                "cemetery_lot_space": "12",
                "reason": "relocation",
                "destination": "Oakwood",
                "next_of_kin": [],
                "accepted_quote_amount": None,
            },
            document_type="disinterment_release_form",
            title="Release CASE-1",
            company_id=company.id,
            entity_type="disinterment_case",
            entity_id="case-1",
            disinterment_case_id="case-1",
            caller_module="test.disinterment",
            caller_workflow_run_id="run-1",
            caller_workflow_step_id="step-1",
            rendered_by_user_id=admin_user.id,
        )
        assert doc.entity_type == "disinterment_case"
        assert doc.entity_id == "case-1"
        assert doc.disinterment_case_id == "case-1"
        assert doc.caller_module == "test.disinterment"
        assert doc.caller_workflow_run_id == "run-1"
        assert doc.caller_workflow_step_id == "step-1"
        assert doc.rendered_by_user_id == admin_user.id

    def test_computes_context_hash(self, db, company, mock_renderer_deps):
        from app.services.documents import document_renderer

        ctx_a = {"name": "Alice"}
        ctx_b = {"name": "Bob"}
        doc_a = document_renderer.render(
            db,
            template_key="invoice.professional",
            context=ctx_a,
            document_type="invoice",
            title="A",
            company_id=company.id,
        )
        doc_b = document_renderer.render(
            db,
            template_key="invoice.professional",
            context=ctx_b,
            document_type="invoice",
            title="B",
            company_id=company.id,
        )
        assert doc_a.rendering_context_hash != doc_b.rendering_context_hash
        assert len(doc_a.rendering_context_hash) == 64  # SHA-256 hex
        # Hash is deterministic — same context → same hash
        doc_c = document_renderer.render(
            db,
            template_key="invoice.professional",
            context=ctx_a,
            document_type="invoice",
            title="A again",
            company_id=company.id,
        )
        assert doc_c.rendering_context_hash == doc_a.rendering_context_hash

    def test_fails_gracefully_when_template_missing(self, db, company):
        from app.services.documents import document_renderer, template_loader

        with pytest.raises(template_loader.TemplateNotFoundError):
            document_renderer.render(
                db,
                template_key="nonexistent.template",
                context={},
                document_type="invoice",
                title="broken",
                company_id=company.id,
            )

    def test_fails_gracefully_when_weasyprint_fails(
        self, db, company, mock_renderer_deps
    ):
        from app.services.documents import document_renderer

        with patch(
            "app.services.documents.document_renderer._html_to_pdf",
            side_effect=document_renderer.DocumentRenderError("weasy broken"),
        ):
            with pytest.raises(document_renderer.DocumentRenderError):
                document_renderer.render(
                    db,
                    template_key="invoice.professional",
                    context={"invoice_number": "X"},
                    document_type="invoice",
                    title="X",
                    company_id=company.id,
                )


# ---------------------------------------------------------------------------
# DocumentRenderer.rerender
# ---------------------------------------------------------------------------


class TestRerender:
    def test_creates_new_version_and_flips_is_current(
        self, db, company, mock_renderer_deps
    ):
        from app.models.canonical_document import DocumentVersion
        from app.services.documents import document_renderer

        doc = document_renderer.render(
            db,
            template_key="invoice.professional",
            context={"invoice_number": "INV-R1"},
            document_type="invoice",
            title="Invoice INV-R1",
            company_id=company.id,
        )
        original_storage_key = doc.storage_key

        doc2 = document_renderer.rerender(
            db,
            document_id=doc.id,
            context={"invoice_number": "INV-R1", "total": "updated"},
            render_reason="data_updated",
        )
        # Same document row
        assert doc2.id == doc.id
        # Document.storage_key updated to the new version's key
        assert doc2.storage_key != original_storage_key
        assert doc2.storage_key.endswith("/v2.pdf")

        # Version rows: v1 is_current=False, v2 is_current=True
        versions = (
            db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == doc.id)
            .order_by(DocumentVersion.version_number)
            .all()
        )
        assert len(versions) == 2
        assert versions[0].version_number == 1
        assert versions[0].is_current is False
        assert versions[1].version_number == 2
        assert versions[1].is_current is True
        assert versions[1].render_reason == "data_updated"

    def test_missing_document_raises(self, db, mock_renderer_deps):
        from app.services.documents import document_renderer

        with pytest.raises(ValueError):
            document_renderer.rerender(
                db,
                document_id="nonexistent",
                context={},
            )


# ---------------------------------------------------------------------------
# Migrated generators
# ---------------------------------------------------------------------------


class TestDisintermentGenerator:
    def test_produces_document_via_renderer(
        self, db, company, mock_renderer_deps
    ):
        """Full end-to-end: disinterment_pdf_service.generate_release_form_document
        routes through DocumentRenderer and creates a persisted Document."""
        from app.models.cemetery import Cemetery
        from app.models.disinterment_case import DisintermentCase
        from app.services.disinterment_pdf_service import (
            generate_release_form_document,
        )

        cemetery = Cemetery(
            id=str(uuid.uuid4()),
            company_id=company.id,
            name="Rosedale",
        )
        db.add(cemetery)
        db.flush()

        case = DisintermentCase(
            id=str(uuid.uuid4()),
            company_id=company.id,
            case_number="DIS-2026-001",
            decedent_name="Jane Doe",
            cemetery_id=cemetery.id,
            reason="relocation",
            destination="Oakwood Cemetery",
            status="intake",
            # Explicit defaults for every JSONB column — DisintermentCase
            # uses Postgres literal `server_default="'[]'"` for these
            # which SQLite stores verbatim, then can't JSON-decode.
            next_of_kin=[],
            assigned_crew=[],
        )
        db.add(case)
        db.flush()

        doc = generate_release_form_document(db, case.id, company.id)
        assert doc.document_type == "disinterment_release_form"
        assert doc.disinterment_case_id == case.id
        assert doc.entity_type == "disinterment_case"
        assert doc.entity_id == case.id
        assert doc.caller_module == (
            "disinterment_pdf_service.generate_release_form_document"
        )
        assert doc.template_key == "disinterment.release_form"


# ---------------------------------------------------------------------------
# Workflow engine generate_document action
# ---------------------------------------------------------------------------


class TestWorkflowGenerateDocument:
    def test_action_creates_document(self, db, company, mock_renderer_deps):
        from app.models.canonical_document import Document
        from app.models.workflow import Workflow, WorkflowRun
        from app.services.workflow_engine import _handle_generate_document

        wf = Workflow(
            id=str(uuid.uuid4()),
            company_id=company.id,
            name="Test WF",
            trigger_type="manual",
            trigger_config={},
        )
        db.add(wf)
        db.flush()
        run = WorkflowRun(
            id=str(uuid.uuid4()),
            workflow_id=wf.id,
            company_id=company.id,
            trigger_source="manual",
            trigger_context={},
            status="running",
        )
        db.add(run)
        db.flush()

        # Patch presigned_url so we don't hit real R2
        with patch(
            "app.services.workflow_engine.document_renderer.presigned_url"
            if False
            else "app.services.documents.document_renderer.presigned_url",
            return_value="https://r2.test/signed",
        ):
            output = _handle_generate_document(
                db,
                {
                    "action_type": "generate_document",
                    "template_key": "invoice.professional",
                    "document_type": "invoice",
                    "title": "Invoice from workflow",
                    "context": {"invoice_number": "WF-1"},
                },
                run,
            )

        assert output["type"] == "document_generated"
        assert "document_id" in output
        assert "pdf_url" in output
        assert output["version_number"] == 1
        assert output["document_type"] == "invoice"

        # Verify the Document exists + has workflow linkage
        doc = (
            db.query(Document)
            .filter(Document.id == output["document_id"])
            .first()
        )
        assert doc is not None
        assert doc.caller_workflow_run_id == run.id
        assert doc.caller_module == f"workflow_engine.{wf.id}"

    def test_action_populates_entity_linkage_from_trigger_context(
        self, db, company, mock_renderer_deps
    ):
        from app.models.canonical_document import Document
        from app.models.workflow import Workflow, WorkflowRun
        from app.services.workflow_engine import _handle_generate_document

        wf = Workflow(
            id=str(uuid.uuid4()),
            company_id=company.id,
            name="WF Disinterment",
            trigger_type="manual",
        )
        db.add(wf)
        db.flush()
        case_id = str(uuid.uuid4())
        run = WorkflowRun(
            id=str(uuid.uuid4()),
            workflow_id=wf.id,
            company_id=company.id,
            trigger_source="event",
            trigger_context={
                "entity_type": "disinterment_case",
                "entity_id": case_id,
            },
            status="running",
        )
        db.add(run)
        db.flush()

        with patch(
            "app.services.documents.document_renderer.presigned_url",
            return_value="https://r2.test/signed",
        ):
            output = _handle_generate_document(
                db,
                {
                    "template_key": "disinterment.release_form",
                    "document_type": "disinterment_release_form",
                    "title": "Release",
                    "context": {
                        "company_name": company.name,
                        "case_number": "CASE-99",
                        "generated_date": "Jan 1, 2026",
                        "decedent_name": "J",
                        "date_of_death": None,
                        "date_of_burial": None,
                        "vault_description": None,
                        "cemetery_name": None,
                        "cemetery_lot_section": None,
                        "cemetery_lot_space": None,
                        "reason": None,
                        "destination": None,
                        "next_of_kin": [],
                        "accepted_quote_amount": None,
                    },
                },
                run,
            )

        doc = (
            db.query(Document)
            .filter(Document.id == output["document_id"])
            .first()
        )
        # Entity linkage — both generic (entity_type/entity_id) and specialty
        # (disinterment_case_id) populate from the trigger context
        assert doc.entity_type == "disinterment_case"
        assert doc.entity_id == case_id
        assert doc.disinterment_case_id == case_id

    def test_action_rejects_missing_template_key(self, db, company):
        from app.models.workflow import Workflow, WorkflowRun
        from app.services.workflow_engine import _handle_generate_document

        wf = Workflow(
            id=str(uuid.uuid4()),
            company_id=company.id,
            name="WF",
            trigger_type="manual",
        )
        db.add(wf)
        db.flush()
        run = WorkflowRun(
            id=str(uuid.uuid4()),
            workflow_id=wf.id,
            company_id=company.id,
            trigger_source="manual",
            trigger_context={},
            status="running",
        )
        db.add(run)
        db.flush()

        with pytest.raises(ValueError):
            _handle_generate_document(
                db,
                {"document_type": "invoice", "title": "Bad"},
                run,
            )


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


class TestDocumentAPI:
    def _seed_doc(self, db, company):
        from app.models.canonical_document import Document, DocumentVersion
        from datetime import datetime, timezone

        doc = Document(
            id=str(uuid.uuid4()),
            company_id=company.id,
            document_type="invoice",
            title="Test invoice",
            storage_key=f"tenants/{company.id}/documents/x/v1.pdf",
            status="rendered",
            template_key="invoice.professional",
            file_size_bytes=4096,
            rendered_at=datetime.now(timezone.utc),
        )
        db.add(doc)
        db.flush()
        v = DocumentVersion(
            id=str(uuid.uuid4()),
            document_id=doc.id,
            version_number=1,
            storage_key=doc.storage_key,
            mime_type="application/pdf",
            file_size_bytes=4096,
            rendered_at=datetime.now(timezone.utc),
            is_current=True,
        )
        db.add(v)
        db.flush()
        return doc

    def test_list_returns_tenant_scoped(self, db, admin_user, company):
        from app.api.routes.documents_v2 import list_documents

        self._seed_doc(db, company)
        rows = list_documents(
            document_type=None,
            entity_type=None,
            entity_id=None,
            status_filter=None,
            date_from=None,
            date_to=None,
            template_key=None,
            intelligence_generated=None,
            limit=100,
            offset=0,
            current_user=admin_user,
            db=db,
        )
        assert len(rows) == 1

    def test_list_filter_by_document_type(self, db, admin_user, company):
        from app.api.routes.documents_v2 import list_documents

        self._seed_doc(db, company)
        rows = list_documents(
            document_type="statement",
            entity_type=None,
            entity_id=None,
            status_filter=None,
            date_from=None,
            date_to=None,
            template_key=None,
            intelligence_generated=None,
            limit=100,
            offset=0,
            current_user=admin_user,
            db=db,
        )
        # Seeded doc is an invoice — statement filter returns nothing
        assert len(rows) == 0

    def test_get_detail_returns_versions(self, db, admin_user, company):
        from app.api.routes.documents_v2 import get_document_detail

        doc = self._seed_doc(db, company)
        resp = get_document_detail(
            document_id=doc.id,
            current_user=admin_user, db=db,
        )
        assert resp.id == doc.id
        assert len(resp.versions) == 1
        assert resp.versions[0].version_number == 1
        assert resp.versions[0].is_current is True

    def test_get_detail_404_on_other_tenant(
        self, db, admin_user, company
    ):
        from fastapi import HTTPException
        from app.api.routes.documents_v2 import get_document_detail
        from app.models.company import Company

        # Seed a doc in a different tenant
        other = Company(id=str(uuid.uuid4()), name="Other", slug="other", is_active=True)
        db.add(other)
        db.flush()
        other_doc = self._seed_doc(db, other)

        with pytest.raises(HTTPException) as exc:
            get_document_detail(
                document_id=other_doc.id,
                current_user=admin_user, db=db,
            )
        assert exc.value.status_code == 404

    def test_soft_deleted_hidden_from_list(self, db, admin_user, company):
        from datetime import datetime, timezone
        from app.api.routes.documents_v2 import list_documents

        doc = self._seed_doc(db, company)
        doc.deleted_at = datetime.now(timezone.utc)
        db.flush()

        rows = list_documents(
            document_type=None, entity_type=None, entity_id=None,
            status_filter=None, date_from=None, date_to=None,
            template_key=None, intelligence_generated=None,
            limit=100, offset=0,
            current_user=admin_user, db=db,
        )
        assert len(rows) == 0

    def test_endpoints_declare_require_admin(self):
        """Source-level lint — every endpoint must use require_admin."""
        from pathlib import Path

        source = (
            Path(__file__).resolve().parent.parent
            / "app" / "api" / "routes" / "documents_v2.py"
        ).read_text(encoding="utf-8")

        # Every route function in this file must have
        # `current_user: User = Depends(require_admin)` on its signature.
        for name in (
            "list_documents",
            "get_document_detail",
            "download_document",
            "download_version",
            "regenerate_document",
        ):
            # Check that the function exists AND that require_admin shows
            # up between its def line and the next def (naive but good
            # enough for a lint check).
            start = source.find(f"def {name}(")
            assert start != -1, f"Missing endpoint {name}"
            next_def = source.find("\ndef ", start + 1)
            block = source[start : next_def if next_def != -1 else len(source)]
            assert "Depends(require_admin)" in block, (
                f"Endpoint {name} does not require admin"
            )
