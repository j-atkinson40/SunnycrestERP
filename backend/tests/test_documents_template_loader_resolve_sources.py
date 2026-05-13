"""Arc 4d — Documents resolver scope-cascade tests.

Verifies the new `resolve_with_sources` function returns the full
resolution chain (winning entry FIRST + up-the-chain entries) so the
inspector tab's SourceBadge + ScopeDiffPopover can render hover-reveal
scope diff.

Documents Class C → Class B transition: per-instance source metadata
now exposed alongside the winning template, parallel to themes /
component_configurations / workflow_templates / focus_compositions.

Covers:
  - Platform-only: 1-entry sources list, source="platform_default"
  - Vertical overrides platform: 2-entry sources, source="vertical_default",
    winning entry FIRST
  - Tenant overrides vertical+platform: 3-entry sources, source=
    "tenant_override", full chain in resolver order
  - Tenant without vertical_default falls back to platform: 2-entry sources
    skipping vertical
  - Returns None when no tier has an active version
  - Winning entry is sources[0] (idx=0)
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

    from app.models.canonical_document import (  # noqa: F401
        Document,
        DocumentVersion,
    )
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


def _seed_template(
    db,
    *,
    template_key: str,
    company_id: str | None = None,
    vertical: str | None = None,
    body: str = "(empty)",
) -> tuple[str, str]:
    from app.models.document_template import (
        DocumentTemplate,
        DocumentTemplateVersion,
    )

    t = DocumentTemplate(
        id=str(uuid.uuid4()),
        company_id=company_id,
        vertical=vertical,
        template_key=template_key,
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
        status="active",
        body_template=body,
    )
    db.add(v)
    db.flush()
    t.current_version_id = v.id
    db.flush()
    return t.id, v.id


@pytest.fixture
def tenant_id(db):
    from app.models.company import Company

    c = Company(
        id=str(uuid.uuid4()),
        name="Tenant",
        slug="tenant-x",
        is_active=True,
    )
    db.add(c)
    db.flush()
    return c.id


# ─── resolve_with_sources contract ──────────────────────────────


class TestResolveWithSources:
    def test_platform_only_single_entry_chain(self, db, tenant_id):
        """No vertical or tenant rows → sources has 1 entry,
        source='platform_default'."""
        from app.services.documents.template_loader import resolve_with_sources

        _seed_template(db, template_key="invoice.x", body="PLATFORM")

        result = resolve_with_sources(
            db,
            "invoice.x",
            company_id=tenant_id,
            vertical="manufacturing",
        )
        assert result is not None
        assert result.source == "platform_default"
        assert len(result.sources) == 1
        assert result.sources[0].scope == "platform_default"
        assert result.version.body_template == "PLATFORM"
        # Winning entry is sources[0]
        assert result.sources[0].version_id == result.version.id

    def test_vertical_overrides_platform_two_entry_chain(self, db, tenant_id):
        """Vertical exists → source='vertical_default', sources has 2 entries
        with vertical winning."""
        from app.services.documents.template_loader import resolve_with_sources

        _seed_template(db, template_key="invoice.x", body="PLATFORM")
        _seed_template(
            db,
            template_key="invoice.x",
            vertical="manufacturing",
            body="MFG",
        )

        result = resolve_with_sources(
            db,
            "invoice.x",
            company_id=tenant_id,
            vertical="manufacturing",
        )
        assert result is not None
        assert result.source == "vertical_default"
        assert result.version.body_template == "MFG"
        assert len(result.sources) == 2
        # Winning entry FIRST
        assert result.sources[0].scope == "vertical_default"
        assert result.sources[1].scope == "platform_default"
        # Winning entry has vertical populated
        assert result.sources[0].vertical == "manufacturing"

    def test_tenant_overrides_vertical_three_entry_chain(self, db, tenant_id):
        """Full chain: tenant > vertical > platform, all three populated."""
        from app.services.documents.template_loader import resolve_with_sources

        _seed_template(db, template_key="invoice.x", body="PLATFORM")
        _seed_template(
            db,
            template_key="invoice.x",
            vertical="manufacturing",
            body="MFG",
        )
        _seed_template(
            db,
            template_key="invoice.x",
            company_id=tenant_id,
            body="TENANT",
        )

        result = resolve_with_sources(
            db,
            "invoice.x",
            company_id=tenant_id,
            vertical="manufacturing",
        )
        assert result is not None
        assert result.source == "tenant_override"
        assert result.version.body_template == "TENANT"
        assert len(result.sources) == 3
        # Resolver order preserved: tenant > vertical > platform
        assert [e.scope for e in result.sources] == [
            "tenant_override",
            "vertical_default",
            "platform_default",
        ]
        # Tenant entry has company_id populated
        assert result.sources[0].company_id == tenant_id
        assert result.sources[0].vertical is None

    def test_tenant_no_vertical_default_falls_through(self, db, tenant_id):
        """Caller has tenant override + platform, no vertical → sources is
        2 entries (tenant + platform), skipping vertical."""
        from app.services.documents.template_loader import resolve_with_sources

        _seed_template(db, template_key="invoice.x", body="PLATFORM")
        _seed_template(
            db,
            template_key="invoice.x",
            company_id=tenant_id,
            body="TENANT",
        )

        result = resolve_with_sources(
            db,
            "invoice.x",
            company_id=tenant_id,
            vertical="manufacturing",
        )
        assert result is not None
        assert result.source == "tenant_override"
        assert len(result.sources) == 2
        assert [e.scope for e in result.sources] == [
            "tenant_override",
            "platform_default",
        ]

    def test_no_template_anywhere_returns_none(self, db, tenant_id):
        """No matching templates at any tier → returns None (same contract
        as _resolve_version)."""
        from app.services.documents.template_loader import resolve_with_sources

        result = resolve_with_sources(
            db,
            "invoice.never-seeded",
            company_id=tenant_id,
            vertical="manufacturing",
        )
        assert result is None

    def test_winning_entry_is_always_sources_first(self, db, tenant_id):
        """Invariant: result.source matches result.sources[0].scope, and
        result.version.id matches result.sources[0].version_id, regardless
        of which tier wins."""
        from app.services.documents.template_loader import resolve_with_sources

        _seed_template(db, template_key="invoice.x", body="PLATFORM")
        _seed_template(
            db,
            template_key="invoice.x",
            vertical="funeral_home",
            body="FH",
        )

        result = resolve_with_sources(
            db,
            "invoice.x",
            company_id=tenant_id,
            vertical="funeral_home",
        )
        assert result is not None
        assert result.source == result.sources[0].scope
        assert result.version.id == result.sources[0].version_id
        assert result.version.body_template == "FH"
