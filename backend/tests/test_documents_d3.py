"""Phase D-3 tests — template editing, versioning, fork, test render,
audit log, variable schema validation, permission gates.

Follows the SQLite in-memory fixture pattern from test_documents_d1.py
and test_documents_d2.py.
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

    from app.models.agent import AgentJob  # noqa: F401
    from app.models.canonical_document import Document, DocumentVersion  # noqa: F401
    from app.models.company import Company  # noqa: F401
    from app.models.company_entity import CompanyEntity  # noqa: F401
    from app.models.customer import Customer  # noqa: F401
    from app.models.disinterment_case import DisintermentCase  # noqa: F401
    from app.models.document_template import (  # noqa: F401
        DocumentTemplate,
        DocumentTemplateAuditLog,
        DocumentTemplateVersion,
    )
    from app.models.document_share import (  # noqa: F401
        DocumentShare,
        DocumentShareEvent,
    )
    from app.models.fh_case import FHCase  # noqa: F401
    from app.models.invoice import Invoice  # noqa: F401
    from app.models.price_list_version import PriceListVersion  # noqa: F401
    from app.models.role import Role  # noqa: F401
    from app.models.safety_program_generation import SafetyProgramGeneration  # noqa: F401
    from app.models.sales_order import SalesOrder  # noqa: F401
    from app.models.statement import CustomerStatement  # noqa: F401
    from app.models.user import User  # noqa: F401
    from app.models.workflow import WorkflowRun, WorkflowRunStep  # noqa: F401

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
def tenant(db):
    from app.models.company import Company

    c = Company(
        id=str(uuid.uuid4()), name="Tenant A", slug="tenant-a", is_active=True
    )
    db.add(c)
    db.flush()
    return c


@pytest.fixture
def other_tenant(db):
    from app.models.company import Company

    c = Company(
        id=str(uuid.uuid4()), name="Tenant B", slug="tenant-b", is_active=True
    )
    db.add(c)
    db.flush()
    return c


def _seed_platform_template(
    db, template_key="invoice.professional", output_format="pdf"
):
    from app.models.document_template import (
        DocumentTemplate,
        DocumentTemplateVersion,
    )

    tpl = DocumentTemplate(
        id=str(uuid.uuid4()),
        company_id=None,
        template_key=template_key,
        document_type="invoice",
        output_format=output_format,
        description="Platform seed",
        is_active=True,
    )
    db.add(tpl)
    db.flush()
    v = DocumentTemplateVersion(
        id=str(uuid.uuid4()),
        template_id=tpl.id,
        version_number=1,
        status="active",
        body_template="<html>{{ invoice_number }} for {{ customer_name }}</html>",
        subject_template=None,
        variable_schema={"invoice_number": {}, "customer_name": {}},
        changelog="Initial seed",
        activated_at=datetime.now(timezone.utc),
    )
    db.add(v)
    db.flush()
    tpl.current_version_id = v.id
    db.flush()
    return tpl, v


def _seed_tenant_template(db, tenant_id: str, template_key="invoice.custom"):
    from app.models.document_template import (
        DocumentTemplate,
        DocumentTemplateVersion,
    )

    tpl = DocumentTemplate(
        id=str(uuid.uuid4()),
        company_id=tenant_id,
        template_key=template_key,
        document_type="invoice",
        output_format="pdf",
        is_active=True,
    )
    db.add(tpl)
    db.flush()
    v = DocumentTemplateVersion(
        id=str(uuid.uuid4()),
        template_id=tpl.id,
        version_number=1,
        status="active",
        body_template="<html>TENANT {{ var }}</html>",
        variable_schema={"var": {}},
        changelog="tenant seed",
        activated_at=datetime.now(timezone.utc),
    )
    db.add(v)
    db.flush()
    tpl.current_version_id = v.id
    db.flush()
    return tpl, v


# ---------------------------------------------------------------------------
# Draft lifecycle
# ---------------------------------------------------------------------------


class TestDraftLifecycle:
    def test_create_draft_from_active(self, db, tenant):
        from app.services.documents import template_service

        tpl, v = _seed_tenant_template(db, tenant.id)
        draft = template_service.create_draft(
            db,
            template=tpl,
            base_version_id=None,
            changelog="Trying new wording",
            actor_user_id="user-1",
            actor_email="a@b.co",
        )
        db.flush()
        assert draft.status == "draft"
        assert draft.version_number == 2
        assert draft.body_template == v.body_template
        assert draft.changelog == "Trying new wording"

    def test_only_one_draft_per_template(self, db, tenant):
        from app.services.documents import template_service
        from app.services.documents.template_service import TemplateEditError

        tpl, _ = _seed_tenant_template(db, tenant.id)
        template_service.create_draft(
            db,
            template=tpl,
            base_version_id=None,
            changelog="first",
            actor_user_id=None,
            actor_email=None,
        )
        db.flush()
        with pytest.raises(TemplateEditError) as exc:
            template_service.create_draft(
                db,
                template=tpl,
                base_version_id=None,
                changelog="second",
                actor_user_id=None,
                actor_email=None,
            )
        assert exc.value.http_status == 409

    def test_update_draft_only_works_on_drafts(self, db, tenant):
        from app.services.documents import template_service
        from app.services.documents.template_service import TemplateEditError

        tpl, active = _seed_tenant_template(db, tenant.id)
        # Active version cannot be updated
        with pytest.raises(TemplateEditError) as exc:
            template_service.update_draft(
                db,
                template=tpl,
                version=active,
                fields={"body_template": "new"},
                actor_user_id=None,
                actor_email=None,
            )
        assert exc.value.http_status == 409

    def test_delete_draft_rejects_active(self, db, tenant):
        from app.services.documents import template_service
        from app.services.documents.template_service import TemplateEditError

        tpl, active = _seed_tenant_template(db, tenant.id)
        with pytest.raises(TemplateEditError) as exc:
            template_service.delete_draft(
                db,
                template=tpl,
                version=active,
                actor_user_id=None,
                actor_email=None,
            )
        assert exc.value.http_status == 409

    def test_delete_draft_removes_row(self, db, tenant):
        from app.models.document_template import DocumentTemplateVersion
        from app.services.documents import template_service

        tpl, _ = _seed_tenant_template(db, tenant.id)
        draft = template_service.create_draft(
            db, template=tpl, base_version_id=None,
            changelog=None, actor_user_id=None, actor_email=None,
        )
        draft_id = draft.id
        db.flush()
        template_service.delete_draft(
            db,
            template=tpl,
            version=draft,
            actor_user_id=None,
            actor_email=None,
        )
        db.flush()
        assert (
            db.query(DocumentTemplateVersion)
            .filter_by(id=draft_id)
            .count()
            == 0
        )


# ---------------------------------------------------------------------------
# Activation
# ---------------------------------------------------------------------------


class TestActivation:
    def test_activate_retires_previous_active(self, db, tenant):
        from app.services.documents import template_service

        tpl, active = _seed_tenant_template(db, tenant.id)
        draft = template_service.create_draft(
            db,
            template=tpl,
            base_version_id=None,
            changelog=None,
            actor_user_id=None,
            actor_email=None,
        )
        db.flush()
        activated = template_service.activate_version(
            db,
            template=tpl,
            version=draft,
            changelog="Publish v2",
            actor_user_id="u1",
            actor_email="u1@x.co",
        )
        db.flush()
        db.refresh(active)
        assert active.status == "retired"
        assert activated.status == "active"
        assert activated.activated_at is not None
        assert tpl.current_version_id == activated.id

    def test_activate_requires_changelog(self, db, tenant):
        from app.services.documents import template_service
        from app.services.documents.template_service import TemplateEditError

        tpl, _ = _seed_tenant_template(db, tenant.id)
        draft = template_service.create_draft(
            db, template=tpl, base_version_id=None,
            changelog=None, actor_user_id=None, actor_email=None,
        )
        db.flush()
        with pytest.raises(TemplateEditError) as exc:
            template_service.activate_version(
                db,
                template=tpl,
                version=draft,
                changelog="",
                actor_user_id=None,
                actor_email=None,
            )
        assert exc.value.http_status == 400

    def test_activate_rejects_non_draft(self, db, tenant):
        from app.services.documents import template_service
        from app.services.documents.template_service import TemplateEditError

        tpl, active = _seed_tenant_template(db, tenant.id)
        with pytest.raises(TemplateEditError) as exc:
            template_service.activate_version(
                db,
                template=tpl,
                version=active,
                changelog="x",
                actor_user_id=None,
                actor_email=None,
            )
        assert exc.value.http_status == 409

    def test_template_current_version_id_updates_on_activation(self, db, tenant):
        from app.services.documents import template_service

        tpl, active = _seed_tenant_template(db, tenant.id)
        original_current = tpl.current_version_id
        draft = template_service.create_draft(
            db, template=tpl, base_version_id=None,
            changelog=None, actor_user_id=None, actor_email=None,
        )
        db.flush()
        template_service.activate_version(
            db, template=tpl, version=draft, changelog="cl",
            actor_user_id=None, actor_email=None,
        )
        db.flush()
        assert tpl.current_version_id == draft.id
        assert tpl.current_version_id != original_current


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------


class TestRollback:
    def _make_history(self, db, tenant):
        """Build: v1 retired, v2 retired, v3 active. Return (template, v1)."""
        from app.services.documents import template_service

        tpl, v1 = _seed_tenant_template(db, tenant.id)
        # Activate v2
        d2 = template_service.create_draft(
            db, template=tpl, base_version_id=None, changelog=None,
            actor_user_id=None, actor_email=None,
        )
        db.flush()
        template_service.activate_version(
            db, template=tpl, version=d2, changelog="cl2",
            actor_user_id=None, actor_email=None,
        )
        db.flush()
        # Activate v3
        d3 = template_service.create_draft(
            db, template=tpl, base_version_id=None, changelog=None,
            actor_user_id=None, actor_email=None,
        )
        db.flush()
        template_service.activate_version(
            db, template=tpl, version=d3, changelog="cl3",
            actor_user_id=None, actor_email=None,
        )
        db.flush()
        db.refresh(v1)
        return tpl, v1, d3

    def test_rollback_creates_new_version_not_reactivation(
        self, db, tenant
    ):
        from app.services.documents import template_service

        tpl, v1, v3 = self._make_history(db, tenant)
        original_v1_id = v1.id
        new_version = template_service.rollback_to_version(
            db,
            template=tpl,
            target=v1,
            changelog="Rolled back",
            actor_user_id=None,
            actor_email=None,
        )
        db.flush()
        # New version created with new ID
        assert new_version.id != original_v1_id
        # Version number is monotonic (v4)
        assert new_version.version_number == 4
        # Content was copied from v1
        assert new_version.body_template == v1.body_template
        assert new_version.status == "active"
        # v1 itself still retired (not re-activated)
        db.refresh(v1)
        assert v1.status == "retired"

    def test_rollback_retires_current_active(self, db, tenant):
        from app.services.documents import template_service

        tpl, v1, v3 = self._make_history(db, tenant)
        template_service.rollback_to_version(
            db, template=tpl, target=v1, changelog="rb",
            actor_user_id=None, actor_email=None,
        )
        db.flush()
        db.refresh(v3)
        assert v3.status == "retired"

    def test_rollback_only_allows_retired_target(self, db, tenant):
        from app.services.documents import template_service
        from app.services.documents.template_service import TemplateEditError

        tpl, v1, v3 = self._make_history(db, tenant)
        # v3 is active — cannot roll back to it
        with pytest.raises(TemplateEditError) as exc:
            template_service.rollback_to_version(
                db, template=tpl, target=v3, changelog="x",
                actor_user_id=None, actor_email=None,
            )
        assert exc.value.http_status == 409


# ---------------------------------------------------------------------------
# Fork
# ---------------------------------------------------------------------------


class TestFork:
    def test_fork_platform_to_tenant(self, db, tenant):
        from app.services.documents import template_service

        source, active = _seed_platform_template(db)
        forked = template_service.fork_platform_to_tenant(
            db,
            source_template=source,
            target_company_id=tenant.id,
            actor_user_id="u1",
            actor_email="u1@x.co",
        )
        db.flush()
        assert forked.company_id == tenant.id
        assert forked.template_key == source.template_key
        # Tenant copy starts at v1 (independent history)
        assert forked.current_version_id is not None

    def test_fork_rejects_non_platform_source(self, db, tenant):
        from app.services.documents import template_service
        from app.services.documents.template_service import TemplateEditError

        tenant_tpl, _ = _seed_tenant_template(db, tenant.id)
        with pytest.raises(TemplateEditError) as exc:
            template_service.fork_platform_to_tenant(
                db,
                source_template=tenant_tpl,
                target_company_id=tenant.id,
                actor_user_id=None,
                actor_email=None,
            )
        assert exc.value.http_status == 400

    def test_fork_rejects_duplicate_tenant_key(self, db, tenant):
        from app.services.documents import template_service
        from app.services.documents.template_service import TemplateEditError

        source, _ = _seed_platform_template(db)
        template_service.fork_platform_to_tenant(
            db,
            source_template=source,
            target_company_id=tenant.id,
            actor_user_id=None,
            actor_email=None,
        )
        db.flush()
        # Second fork for same (tenant, template_key) → 409
        with pytest.raises(TemplateEditError) as exc:
            template_service.fork_platform_to_tenant(
                db,
                source_template=source,
                target_company_id=tenant.id,
                actor_user_id=None,
                actor_email=None,
            )
        assert exc.value.http_status == 409

    def test_fork_preserves_body_and_schema(self, db, tenant):
        from app.models.document_template import DocumentTemplateVersion
        from app.services.documents import template_service

        source, active = _seed_platform_template(db)
        forked = template_service.fork_platform_to_tenant(
            db,
            source_template=source,
            target_company_id=tenant.id,
            actor_user_id=None,
            actor_email=None,
        )
        db.flush()
        tenant_version = (
            db.query(DocumentTemplateVersion)
            .filter_by(id=forked.current_version_id)
            .first()
        )
        assert tenant_version is not None
        assert tenant_version.body_template == active.body_template
        assert tenant_version.variable_schema == active.variable_schema
        # Tenant version history starts fresh at v1
        assert tenant_version.version_number == 1


# ---------------------------------------------------------------------------
# Variable schema validation
# ---------------------------------------------------------------------------


class TestVariableSchemaValidation:
    def test_extract_variables_from_jinja_template(self):
        from app.services.documents.template_validator import (
            extract_template_variables,
        )

        refs = extract_template_variables(
            "Hello {{ customer_name }}, your order {{ order_number }} is ready."
        )
        assert refs == {"customer_name", "order_number"}

    def test_extract_excludes_loop_locals(self):
        from app.services.documents.template_validator import (
            extract_template_variables,
        )

        refs = extract_template_variables(
            "{% for item in items %}{{ item.name }}{% endfor %}"
        )
        # `item` is a loop local — shouldn't be in the undeclared set
        assert "items" in refs
        assert "item" not in refs

    def test_validate_catches_undeclared(self):
        from app.services.documents.template_validator import (
            validate_template_content,
        )

        result = validate_template_content(
            body_template="Hello {{ name }} on {{ date }}",
            subject_template=None,
            variable_schema={"name": {}},
        )
        assert result.has_errors
        errors = [i for i in result.issues if i.severity == "error"]
        assert any(i.variable_name == "date" for i in errors)

    def test_validate_catches_unused_non_optional(self):
        from app.services.documents.template_validator import (
            validate_template_content,
        )

        result = validate_template_content(
            body_template="Hello {{ name }}",
            variable_schema={"name": {}, "unused_var": {}},
        )
        assert not result.has_errors
        assert result.has_warnings
        warnings = [i for i in result.issues if i.severity == "warning"]
        assert any(i.variable_name == "unused_var" for i in warnings)

    def test_validate_excuses_optional_variables(self):
        from app.services.documents.template_validator import (
            validate_template_content,
        )

        result = validate_template_content(
            body_template="Hello {{ name }}",
            variable_schema={
                "name": {},
                "signature": {"optional": True},
            },
        )
        assert not result.has_errors
        assert not result.has_warnings

    def test_validate_catches_invalid_jinja_syntax(self):
        from app.services.documents.template_validator import (
            validate_template_content,
        )

        result = validate_template_content(
            body_template="{{ unclosed",
            variable_schema={},
        )
        assert result.has_errors
        assert any(
            i.issue_type == "invalid_jinja_syntax" for i in result.issues
        )

    def test_validate_subject_and_body_both_checked(self):
        from app.services.documents.template_validator import (
            validate_template_content,
        )

        result = validate_template_content(
            body_template="Body {{ b }}",
            subject_template="Subject {{ s }}",
            variable_schema={"b": {}},
        )
        errors = [i for i in result.issues if i.severity == "error"]
        assert any(i.variable_name == "s" for i in errors)


# ---------------------------------------------------------------------------
# Test render
# ---------------------------------------------------------------------------


class TestRenderFlag:
    def test_test_render_sets_flag_on_document(self, db, tenant):
        from app.models.canonical_document import Document
        from app.services.documents import document_renderer

        _, v = _seed_tenant_template(db, tenant.id)
        with patch(
            "app.services.documents.document_renderer._html_to_pdf"
        ) as mock_pdf, patch(
            "app.services.documents.document_renderer.legacy_r2_client"
        ) as mock_r2:
            mock_pdf.return_value = b"%PDF fake"
            mock_r2.upload_bytes = lambda *a, **kw: None

            doc = document_renderer.render(
                db,
                template_key="invoice.custom",
                context={"var": "x"},
                document_type="invoice",
                title="Test",
                company_id=tenant.id,
                is_test_render=True,
            )
        assert isinstance(doc, Document)
        assert doc.is_test_render is True

    def test_production_render_flag_defaults_false(self, db, tenant):
        from app.models.canonical_document import Document
        from app.services.documents import document_renderer

        _seed_tenant_template(db, tenant.id)
        with patch(
            "app.services.documents.document_renderer._html_to_pdf"
        ) as mock_pdf, patch(
            "app.services.documents.document_renderer.legacy_r2_client"
        ) as mock_r2:
            mock_pdf.return_value = b"%PDF fake"
            mock_r2.upload_bytes = lambda *a, **kw: None

            doc = document_renderer.render(
                db,
                template_key="invoice.custom",
                context={"var": "x"},
                document_type="invoice",
                title="Prod",
                company_id=tenant.id,
            )
        assert isinstance(doc, Document)
        assert doc.is_test_render is False


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


class TestAuditLog:
    def test_audit_row_written_on_create_draft(self, db, tenant):
        from app.models.document_template import DocumentTemplateAuditLog
        from app.services.documents import template_service

        tpl, _ = _seed_tenant_template(db, tenant.id)
        before = (
            db.query(DocumentTemplateAuditLog)
            .filter_by(template_id=tpl.id)
            .count()
        )
        template_service.create_draft(
            db, template=tpl, base_version_id=None,
            changelog="cl", actor_user_id="u", actor_email="u@x.co",
        )
        db.flush()
        after = (
            db.query(DocumentTemplateAuditLog)
            .filter_by(template_id=tpl.id)
            .count()
        )
        assert after == before + 1
        row = (
            db.query(DocumentTemplateAuditLog)
            .filter_by(template_id=tpl.id)
            .order_by(DocumentTemplateAuditLog.created_at.desc())
            .first()
        )
        assert row.action == "create_draft"
        assert row.actor_email == "u@x.co"

    def test_audit_row_written_on_activate(self, db, tenant):
        from app.models.document_template import DocumentTemplateAuditLog
        from app.services.documents import template_service

        tpl, _ = _seed_tenant_template(db, tenant.id)
        draft = template_service.create_draft(
            db, template=tpl, base_version_id=None,
            changelog=None, actor_user_id=None, actor_email=None,
        )
        db.flush()
        template_service.activate_version(
            db, template=tpl, version=draft, changelog="cl-activate",
            actor_user_id="u", actor_email="u@x.co",
        )
        db.flush()
        row = (
            db.query(DocumentTemplateAuditLog)
            .filter_by(template_id=tpl.id, action="activate")
            .order_by(DocumentTemplateAuditLog.created_at.desc())
            .first()
        )
        assert row is not None
        assert row.changelog_summary == "cl-activate"

    def test_audit_row_written_on_rollback(self, db, tenant):
        from app.models.document_template import DocumentTemplateAuditLog
        from app.services.documents import template_service

        # Setup: v1 retired, v2 active
        tpl, v1 = _seed_tenant_template(db, tenant.id)
        draft = template_service.create_draft(
            db, template=tpl, base_version_id=None,
            changelog=None, actor_user_id=None, actor_email=None,
        )
        db.flush()
        template_service.activate_version(
            db, template=tpl, version=draft, changelog="cl",
            actor_user_id=None, actor_email=None,
        )
        db.flush()
        db.refresh(v1)

        template_service.rollback_to_version(
            db, template=tpl, target=v1, changelog="rollback",
            actor_user_id="u", actor_email="u@x.co",
        )
        db.flush()
        row = (
            db.query(DocumentTemplateAuditLog)
            .filter_by(template_id=tpl.id, action="rollback")
            .first()
        )
        assert row is not None
        assert row.meta_json.get("rolled_back_to_version_number") == 1

    def test_audit_row_written_on_fork(self, db, tenant):
        from app.models.document_template import DocumentTemplateAuditLog
        from app.services.documents import template_service

        source, _ = _seed_platform_template(db)
        template_service.fork_platform_to_tenant(
            db, source_template=source, target_company_id=tenant.id,
            actor_user_id="u", actor_email="u@x.co",
        )
        db.flush()
        source_rows = (
            db.query(DocumentTemplateAuditLog)
            .filter_by(template_id=source.id, action="fork_to_tenant")
            .all()
        )
        assert len(source_rows) == 1
        assert source_rows[0].meta_json.get("target_company_id") == tenant.id

    def test_audit_log_chronological(self, db, tenant):
        from app.services.documents import template_service

        tpl, _ = _seed_tenant_template(db, tenant.id)
        draft = template_service.create_draft(
            db, template=tpl, base_version_id=None,
            changelog=None, actor_user_id=None, actor_email=None,
        )
        db.flush()
        template_service.update_draft(
            db, template=tpl, version=draft,
            fields={"body_template": "new body"},
            actor_user_id=None, actor_email=None,
        )
        db.flush()
        template_service.activate_version(
            db, template=tpl, version=draft, changelog="cl",
            actor_user_id=None, actor_email=None,
        )
        db.flush()

        entries = template_service.list_audit(db, tpl.id, limit=10)
        # Newest first
        assert len(entries) >= 3
        actions = [e.action for e in entries]
        assert actions[0] == "activate"
        # update_draft and create_draft both present
        assert "update_draft" in actions
        assert "create_draft" in actions


# ---------------------------------------------------------------------------
# Document Log behavior with is_test_render
# ---------------------------------------------------------------------------


class TestDocumentLogTestRenderExclusion:
    def _seed_docs(self, db, tenant):
        from app.models.canonical_document import Document

        prod = Document(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            document_type="invoice",
            title="Production",
            storage_key=f"tenants/{tenant.id}/documents/prod/v1.pdf",
            mime_type="application/pdf",
            file_size_bytes=10,
            status="rendered",
            is_test_render=False,
        )
        test = Document(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            document_type="invoice",
            title="Test",
            storage_key=f"tenants/{tenant.id}/documents/test/v1.pdf",
            mime_type="application/pdf",
            file_size_bytes=10,
            status="rendered",
            is_test_render=True,
        )
        db.add_all([prod, test])
        db.flush()

    def test_log_excludes_test_renders_by_default(self, db, tenant):
        from app.api.routes.documents_v2 import list_document_log
        from app.models.user import User

        self._seed_docs(db, tenant)
        from app.models.role import Role

        role = Role(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            name="Admin",
            slug="admin",
            is_system=True,
        )
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            email=f"admin-{uuid.uuid4().hex[:6]}@x",
            first_name="A",
            last_name="A",
            hashed_password="x",
            is_active=True,
            is_super_admin=False,
            role_id=role.id,
        )
        db.add(user)
        db.flush()

        rows = list_document_log(
            document_type=None, template_key=None, status_filter=None,
            entity_type=None, intelligence_generated=None,
            include_test_renders=False,
            date_from=None, date_to=None, limit=100, offset=0,
            current_user=user, db=db,
        )
        titles = [r.title for r in rows]
        assert "Production" in titles
        assert "Test" not in titles

    def test_log_includes_test_renders_when_toggled(self, db, tenant):
        from app.api.routes.documents_v2 import list_document_log
        from app.models.user import User

        self._seed_docs(db, tenant)
        from app.models.role import Role

        role = Role(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            name="Admin",
            slug="admin",
            is_system=True,
        )
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            email=f"admin-{uuid.uuid4().hex[:6]}@x",
            first_name="A",
            last_name="A",
            hashed_password="x",
            is_active=True,
            is_super_admin=False,
            role_id=role.id,
        )
        db.add(user)
        db.flush()

        rows = list_document_log(
            document_type=None, template_key=None, status_filter=None,
            entity_type=None, intelligence_generated=None,
            include_test_renders=True,
            date_from=None, date_to=None, limit=100, offset=0,
            current_user=user, db=db,
        )
        titles = [r.title for r in rows]
        assert "Production" in titles
        assert "Test" in titles


# ---------------------------------------------------------------------------
# Permission gates
# ---------------------------------------------------------------------------


class TestPermissionGates:
    def _user(self, db, tenant, *, super_admin=False):
        from app.models.role import Role
        from app.models.user import User

        role = Role(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            name="Admin",
            slug="admin",
            is_system=True,
        )
        db.add(role)
        db.flush()
        u = User(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            email=f"u-{uuid.uuid4().hex[:6]}@x.co",
            first_name="U",
            last_name="U",
            hashed_password="x",
            is_active=True,
            is_super_admin=super_admin,
            role_id=role.id,
        )
        db.add(u)
        db.flush()
        return u

    def test_platform_template_edit_blocked_for_admin(self, db, tenant):
        from app.api.routes.documents_v2 import _validate_edit_permission

        source, _ = _seed_platform_template(db)
        admin = self._user(db, tenant, super_admin=False)
        perm = _validate_edit_permission(admin, source)
        assert perm.can_edit is False
        assert perm.requires_super_admin is True
        assert perm.can_fork is True

    def test_platform_template_edit_allowed_for_super_admin(self, db, tenant):
        from app.api.routes.documents_v2 import _validate_edit_permission

        source, _ = _seed_platform_template(db)
        su = self._user(db, tenant, super_admin=True)
        perm = _validate_edit_permission(su, source)
        assert perm.can_edit is True
        assert perm.requires_confirmation_text is True

    def test_tenant_template_edit_allowed_for_tenant_admin(self, db, tenant):
        from app.api.routes.documents_v2 import _validate_edit_permission

        tpl, _ = _seed_tenant_template(db, tenant.id)
        admin = self._user(db, tenant, super_admin=False)
        perm = _validate_edit_permission(admin, tpl)
        assert perm.can_edit is True
        assert perm.requires_super_admin is False
        assert perm.requires_confirmation_text is False

    def test_cross_tenant_template_blocked(self, db, tenant, other_tenant):
        from app.api.routes.documents_v2 import _get_visible_template_or_404
        from fastapi import HTTPException

        other_tpl, _ = _seed_tenant_template(db, other_tenant.id)
        admin = self._user(db, tenant, super_admin=False)
        with pytest.raises(HTTPException) as exc:
            _get_visible_template_or_404(db, other_tpl.id, admin.company_id)
        assert exc.value.status_code == 404
