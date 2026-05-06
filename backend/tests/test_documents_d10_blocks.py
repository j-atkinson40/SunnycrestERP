"""Phase D-10 tests — block-based document template authoring.

Covers:
  - Block CRUD lifecycle (add / update / delete / reorder)
  - Block kind registry validation
  - Conditional wrapper parent/child semantics
  - Recompose hook persists body_template + variable_schema
  - Composer correctness for each of the 6 block kinds
  - Composition produces complete renderable Jinja
  - Document type catalog returns curated types

Follows the SQLite in-memory fixture pattern from test_documents_d3.py.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import JSON, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.database import Base


@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:")

    from app.models.canonical_document import Document, DocumentVersion  # noqa: F401
    from app.models.company import Company  # noqa: F401
    from app.models.document_template import (  # noqa: F401
        DocumentTemplate,
        DocumentTemplateAuditLog,
        DocumentTemplateVersion,
    )
    from app.models.document_template_block import (  # noqa: F401
        DocumentTemplateBlock,
    )
    from app.models.user import User  # noqa: F401

    tables_needed = [
        "companies",
        "users",
        "documents",
        "document_versions",
        "document_templates",
        "document_template_versions",
        "document_template_audit_log",
        "document_template_blocks",
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
def template_version(db):
    """Create a tenant + draft template version to author blocks against."""
    from app.models.company import Company
    from app.models.document_template import (
        DocumentTemplate,
        DocumentTemplateVersion,
    )

    c = Company(
        id=str(uuid.uuid4()), name="Tenant A", slug="tenant-a", is_active=True
    )
    db.add(c)
    db.flush()

    t = DocumentTemplate(
        id=str(uuid.uuid4()),
        company_id=c.id,
        template_key="custom.invoice.draft",
        document_type="invoice",
        output_format="pdf",
        is_active=True,
    )
    db.add(t)
    db.flush()

    v = DocumentTemplateVersion(
        id=str(uuid.uuid4()),
        template_id=t.id,
        version_number=1,
        status="draft",
        body_template="(empty)",
    )
    db.add(v)
    db.flush()
    return v


# ─── Block kind registry ───────────────────────────────────────


class TestBlockRegistry:
    def test_six_canonical_kinds_registered(self):
        from app.services.documents.block_registry import list_block_kinds

        kinds = {k.kind for k in list_block_kinds()}
        assert kinds == {
            "header",
            "body_section",
            "line_items",
            "totals",
            "signature",
            "conditional_wrapper",
        }

    def test_conditional_wrapper_accepts_children(self):
        from app.services.documents.block_registry import get_block_kind

        assert get_block_kind("conditional_wrapper").accepts_children is True
        assert get_block_kind("header").accepts_children is False
        assert get_block_kind("line_items").accepts_children is False

    def test_unknown_kind_raises(self):
        from app.services.documents.block_registry import get_block_kind

        with pytest.raises(KeyError):
            get_block_kind("not-a-kind")


# ─── Block CRUD ─────────────────────────────────────────────────


class TestBlockCrud:
    def test_add_block_appends_at_end(self, db, template_version):
        from app.services.documents.block_service import add_block

        b1 = add_block(
            db,
            version_id=template_version.id,
            block_kind="header",
            config={"title": "Test"},
        )
        b2 = add_block(
            db,
            version_id=template_version.id,
            block_kind="body_section",
            config={"heading": "Section 1"},
        )
        db.flush()
        assert b1.position == 0
        assert b2.position == 1

    def test_add_block_recomposes_body_template(self, db, template_version):
        from app.services.documents.block_service import add_block

        add_block(
            db,
            version_id=template_version.id,
            block_kind="header",
            config={"title": "My Invoice"},
        )
        db.refresh(template_version)
        assert "<header" in template_version.body_template
        assert "My Invoice" in template_version.body_template
        # Recompose also populates variable_schema
        assert template_version.variable_schema is not None
        assert "company_name" in template_version.variable_schema

    def test_unknown_kind_rejected(self, db, template_version):
        from app.services.documents.block_service import (
            BlockServiceError,
            add_block,
        )

        with pytest.raises(BlockServiceError) as exc_info:
            add_block(
                db,
                version_id=template_version.id,
                block_kind="not-a-kind",
            )
        assert exc_info.value.http_status == 400

    def test_update_block_recomposes(self, db, template_version):
        from app.services.documents.block_service import (
            add_block,
            update_block,
        )

        b = add_block(
            db,
            version_id=template_version.id,
            block_kind="header",
            config={"title": "Initial"},
        )
        update_block(db, block_id=b.id, config={"title": "Updated"})
        db.refresh(template_version)
        assert "Updated" in template_version.body_template
        assert "Initial" not in template_version.body_template

    def test_delete_block_recomposes(self, db, template_version):
        from app.services.documents.block_service import (
            add_block,
            delete_block,
        )

        b1 = add_block(
            db,
            version_id=template_version.id,
            block_kind="header",
            config={"title": "Stays"},
        )
        b2 = add_block(
            db,
            version_id=template_version.id,
            block_kind="body_section",
            config={"heading": "Goes"},
        )
        delete_block(db, block_id=b2.id)
        db.refresh(template_version)
        assert "Stays" in template_version.body_template
        assert "Goes" not in template_version.body_template
        # b1 still exists
        from app.models.document_template_block import DocumentTemplateBlock

        remaining = db.query(DocumentTemplateBlock).all()
        assert len(remaining) == 1
        assert remaining[0].id == b1.id

    def test_reorder_blocks_updates_positions(self, db, template_version):
        from app.services.documents.block_service import (
            add_block,
            reorder_blocks,
        )

        b1 = add_block(
            db,
            version_id=template_version.id,
            block_kind="header",
            config={"title": "A"},
        )
        b2 = add_block(
            db,
            version_id=template_version.id,
            block_kind="body_section",
            config={"heading": "B"},
        )
        b3 = add_block(
            db,
            version_id=template_version.id,
            block_kind="totals",
            config={},
        )
        # Reverse order
        reorder_blocks(
            db,
            version_id=template_version.id,
            block_id_order=[b3.id, b2.id, b1.id],
        )
        db.refresh(b1)
        db.refresh(b2)
        db.refresh(b3)
        assert b3.position == 0
        assert b2.position == 1
        assert b1.position == 2

    def test_reorder_rejects_unknown_block_id(self, db, template_version):
        from app.services.documents.block_service import (
            BlockServiceError,
            add_block,
            reorder_blocks,
        )

        b1 = add_block(
            db, version_id=template_version.id, block_kind="header", config={}
        )
        with pytest.raises(BlockServiceError) as exc_info:
            reorder_blocks(
                db,
                version_id=template_version.id,
                block_id_order=[b1.id, "not-a-block-id"],
            )
        assert exc_info.value.http_status == 400


# ─── Conditional wrapper ────────────────────────────────────────


class TestConditionalWrapper:
    def test_wrapper_with_children_compiles_with_if_block(
        self, db, template_version
    ):
        from app.services.documents.block_service import add_block

        wrapper = add_block(
            db,
            version_id=template_version.id,
            block_kind="conditional_wrapper",
            config={"label": "Cremation only"},
            condition="disposition == 'cremation'",
        )
        add_block(
            db,
            version_id=template_version.id,
            block_kind="body_section",
            config={"heading": "Cremation Details", "body": "Some content"},
            parent_block_id=wrapper.id,
        )
        db.refresh(template_version)
        body = template_version.body_template
        assert "{% if disposition == 'cremation' %}" in body
        assert "{% endif %}" in body
        assert "Cremation Details" in body

    def test_wrapper_cascade_deletes_children(self, db, template_version):
        from app.models.document_template_block import DocumentTemplateBlock
        from app.services.documents.block_service import (
            add_block,
            delete_block,
        )

        wrapper = add_block(
            db,
            version_id=template_version.id,
            block_kind="conditional_wrapper",
            config={},
            condition="True",
        )
        child = add_block(
            db,
            version_id=template_version.id,
            block_kind="body_section",
            config={"heading": "Child"},
            parent_block_id=wrapper.id,
        )
        # Delete the wrapper — child cascades.
        delete_block(db, block_id=wrapper.id)
        # Both rows gone.
        assert (
            db.query(DocumentTemplateBlock)
            .filter(DocumentTemplateBlock.id.in_([wrapper.id, child.id]))
            .count()
            == 0
        )

    def test_condition_only_on_wrappers(self, db, template_version):
        from app.services.documents.block_service import (
            BlockServiceError,
            add_block,
        )

        with pytest.raises(BlockServiceError) as exc_info:
            add_block(
                db,
                version_id=template_version.id,
                block_kind="header",
                config={},
                condition="False",  # Not allowed on header
            )
        assert exc_info.value.http_status == 400


# ─── Activated version is immutable ─────────────────────────────


class TestActivatedVersionImmutable:
    def test_cannot_add_block_to_activated_version(self, db, template_version):
        from app.services.documents.block_service import (
            BlockServiceError,
            add_block,
        )

        template_version.status = "active"
        db.flush()
        with pytest.raises(BlockServiceError) as exc_info:
            add_block(
                db,
                version_id=template_version.id,
                block_kind="header",
                config={},
            )
        assert exc_info.value.http_status == 409
