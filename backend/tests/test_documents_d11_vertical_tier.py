"""Phase D-11 tests — three-tier scope (platform → vertical → tenant)
for document_templates.

Covers:
  - Platform-only resolution returns the platform_default
  - Vertical-default exists, no tenant override → vertical_default wins
  - Tenant override exists, vertical_default exists → tenant wins
  - Tenant in vertical without vertical_default → falls back to platform
  - Pre-D-11 two-tier behavior preserved when vertical kwarg omitted
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


def _seed_template(
    db,
    *,
    template_key: str,
    company_id: str | None = None,
    vertical: str | None = None,
    body: str = "(empty)",
) -> tuple[str, str]:
    """Create a template + active version. Returns (template_id, version_id)."""
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


# ─── Three-tier resolution ──────────────────────────────────────


class TestThreeTierResolution:
    def test_platform_default_only(self, db, tenant_id):
        """No vertical or tenant rows → platform default wins."""
        from app.services.documents.template_loader import _resolve_version

        _seed_template(
            db,
            template_key="invoice.shared",
            body="PLATFORM",
        )

        pair = _resolve_version(
            db,
            "invoice.shared",
            company_id=tenant_id,
            vertical="manufacturing",
        )
        assert pair is not None
        _, version = pair
        assert version.body_template == "PLATFORM"

    def test_vertical_default_wins_over_platform(self, db, tenant_id):
        """Vertical_default exists for caller's vertical → vertical wins."""
        from app.services.documents.template_loader import _resolve_version

        _seed_template(
            db,
            template_key="invoice.shared",
            body="PLATFORM",
        )
        _seed_template(
            db,
            template_key="invoice.shared",
            vertical="manufacturing",
            body="MANUFACTURING_DEFAULT",
        )

        pair = _resolve_version(
            db,
            "invoice.shared",
            company_id=tenant_id,
            vertical="manufacturing",
        )
        assert pair is not None
        _, version = pair
        assert version.body_template == "MANUFACTURING_DEFAULT"

    def test_tenant_override_wins_over_vertical_default(self, db, tenant_id):
        """Tenant override exists → tenant wins, even if vertical_default present."""
        from app.services.documents.template_loader import _resolve_version

        _seed_template(
            db,
            template_key="invoice.shared",
            body="PLATFORM",
        )
        _seed_template(
            db,
            template_key="invoice.shared",
            vertical="manufacturing",
            body="MANUFACTURING_DEFAULT",
        )
        _seed_template(
            db,
            template_key="invoice.shared",
            company_id=tenant_id,
            body="TENANT_OVERRIDE",
        )

        pair = _resolve_version(
            db,
            "invoice.shared",
            company_id=tenant_id,
            vertical="manufacturing",
        )
        assert pair is not None
        _, version = pair
        assert version.body_template == "TENANT_OVERRIDE"

    def test_tenant_in_vertical_without_vertical_default_falls_to_platform(
        self, db, tenant_id
    ):
        """Tenant exists in vertical X but no vertical_default for X."""
        from app.services.documents.template_loader import _resolve_version

        _seed_template(
            db,
            template_key="invoice.shared",
            body="PLATFORM",
        )
        # Vertical default exists for funeral_home but not manufacturing
        _seed_template(
            db,
            template_key="invoice.shared",
            vertical="funeral_home",
            body="FH_DEFAULT",
        )

        pair = _resolve_version(
            db,
            "invoice.shared",
            company_id=tenant_id,
            vertical="manufacturing",
        )
        assert pair is not None
        _, version = pair
        assert version.body_template == "PLATFORM"


# ─── Two-tier back-compat ────────────────────────────────────────


class TestTwoTierBackCompat:
    def test_omitting_vertical_kwarg_works_as_before(self, db, tenant_id):
        """Pre-D-11 callers don't pass `vertical`. Should still resolve
        platform → tenant correctly."""
        from app.services.documents.template_loader import _resolve_version

        _seed_template(
            db,
            template_key="invoice.shared",
            body="PLATFORM",
        )
        # No vertical row, no tenant row — caller doesn't pass vertical.
        pair = _resolve_version(
            db,
            "invoice.shared",
            company_id=tenant_id,
        )
        assert pair is not None
        _, version = pair
        assert version.body_template == "PLATFORM"

    def test_existing_two_tier_template_unaffected(self, db, tenant_id):
        """The 18 seeded platform templates have vertical=NULL — must
        continue to resolve as platform_default."""
        from app.services.documents.template_loader import _resolve_version

        # Simulate a pre-D-11 platform template (vertical=NULL).
        _seed_template(
            db,
            template_key="invoice.shared",
            body="PRE_D11",
        )

        # Caller now passes vertical (post-D-11 path).
        pair = _resolve_version(
            db,
            "invoice.shared",
            company_id=tenant_id,
            vertical="manufacturing",
        )
        assert pair is not None
        _, version = pair
        # Falls through to platform_default since no vertical row exists.
        assert version.body_template == "PRE_D11"


# ─── load() public API exposes vertical kwarg ────────────────────


class TestLoadApiExposesVertical:
    def test_load_with_vertical_kwarg(self, db, tenant_id):
        from app.services.documents.template_loader import load

        _seed_template(
            db,
            template_key="invoice.api",
            body="PLATFORM",
        )
        _seed_template(
            db,
            template_key="invoice.api",
            vertical="funeral_home",
            body="FH_DEFAULT",
        )

        loaded = load(
            "invoice.api",
            company_id=tenant_id,
            db=db,
            vertical="funeral_home",
        )
        assert loaded.body_template == "FH_DEFAULT"

    def test_load_without_vertical_skips_vertical_tier(
        self, db, tenant_id
    ):
        from app.services.documents.template_loader import load

        _seed_template(
            db,
            template_key="invoice.api2",
            body="PLATFORM",
        )
        _seed_template(
            db,
            template_key="invoice.api2",
            vertical="funeral_home",
            body="FH_DEFAULT",
        )

        # No vertical kwarg — vertical tier is skipped, falls through
        # to platform.
        loaded = load("invoice.api2", company_id=tenant_id, db=db)
        assert loaded.body_template == "PLATFORM"
