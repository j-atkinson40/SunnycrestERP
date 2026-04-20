"""Phase D-6 tests — cross-tenant document sharing fabric.

Covers:
  - DocumentShare lifecycle (grant, revoke, re-grant)
  - PlatformTenantRelationship enforcement on grant
  - Document.visible_to() visibility filter
  - Audit events append-only
  - Migrated generators (statement, delivery, legacy vault print)
    create shares automatically
  - API permission gates
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
# Engine + fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:")

    # Import every model that's referenced in this test's subset
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
    from app.models.platform_tenant_relationship import (  # noqa: F401
        PlatformTenantRelationship,
    )
    from app.models.price_list_version import PriceListVersion  # noqa: F401
    from app.models.received_statement import ReceivedStatement  # noqa: F401
    from app.models.role import Role  # noqa: F401
    from app.models.safety_program_generation import SafetyProgramGeneration  # noqa: F401
    from app.models.sales_order import SalesOrder  # noqa: F401
    from app.models.signature import (  # noqa: F401
        SignatureEnvelope,
        SignatureEvent,
        SignatureField,
        SignatureParty,
    )
    from app.models.document_delivery import DocumentDelivery  # noqa: F401
    from app.models.notification import Notification  # noqa: F401
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
        "received_statements",
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
        "signature_envelopes",
        "signature_parties",
        "signature_fields",
        "signature_events",
        "document_shares",
        "document_share_events",
        "document_share_reads",
        "platform_tenant_relationships",
        "document_deliveries",
        # V-1d: share_granted notifications fan-out to target-tenant
        # admins; grant_share swallows errors but SQLAlchemy's session
        # gets poisoned if the INSERT fails, so the table must exist.
        "notifications",
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
def tenant_a(db):
    from app.models.company import Company

    c = Company(id=str(uuid.uuid4()), name="Manufacturer A", slug="mfg-a", is_active=True)
    db.add(c)
    db.flush()
    return c


@pytest.fixture
def tenant_b(db):
    from app.models.company import Company

    c = Company(id=str(uuid.uuid4()), name="Funeral Home B", slug="fh-b", is_active=True)
    db.add(c)
    db.flush()
    return c


@pytest.fixture
def tenant_c(db):
    from app.models.company import Company

    c = Company(id=str(uuid.uuid4()), name="Unrelated C", slug="mfg-c", is_active=True)
    db.add(c)
    db.flush()
    return c


@pytest.fixture
def admin_a(db, tenant_a):
    from app.models.role import Role
    from app.models.user import User

    role = Role(
        id=str(uuid.uuid4()), company_id=tenant_a.id,
        name="Admin", slug="admin", is_system=True,
    )
    db.add(role)
    db.flush()
    u = User(
        id=str(uuid.uuid4()), company_id=tenant_a.id,
        email="admin@mfg-a.co", first_name="A", last_name="A",
        hashed_password="x", is_active=True, role_id=role.id,
    )
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def relationship_ab(db, tenant_a, tenant_b):
    from app.models.platform_tenant_relationship import PlatformTenantRelationship

    r = PlatformTenantRelationship(
        id=str(uuid.uuid4()),
        tenant_id=tenant_b.id,  # customer
        supplier_tenant_id=tenant_a.id,  # supplier / manufacturer
        relationship_type="billing",
        status="active",
    )
    db.add(r)
    db.flush()
    return r


@pytest.fixture
def document_a(db, tenant_a):
    """Document owned by tenant A."""
    from app.models.canonical_document import Document

    d = Document(
        id=str(uuid.uuid4()),
        company_id=tenant_a.id,
        document_type="statement",
        title="Statement April 2026",
        storage_key=f"tenants/{tenant_a.id}/documents/stmt/v1.pdf",
        mime_type="application/pdf",
        file_size_bytes=100,
        status="rendered",
    )
    db.add(d)
    db.flush()
    return d


# ---------------------------------------------------------------------------
# Sharing service — grant
# ---------------------------------------------------------------------------


class TestGrantShare:
    def test_grant_creates_share_with_active_relationship(
        self, db, tenant_a, tenant_b, admin_a, document_a, relationship_ab
    ):
        from app.services.documents import document_sharing_service

        share = document_sharing_service.grant_share(
            db,
            document=document_a,
            target_company_id=tenant_b.id,
            granted_by_user_id=admin_a.id,
            reason="Monthly statement",
        )
        db.flush()
        assert share.owner_company_id == tenant_a.id
        assert share.target_company_id == tenant_b.id
        assert share.permission == "read"
        assert share.revoked_at is None

    def test_grant_rejects_without_relationship(
        self, db, tenant_a, tenant_c, admin_a, document_a
    ):
        from app.services.documents import document_sharing_service
        from app.services.documents.document_sharing_service import SharingError

        with pytest.raises(SharingError) as exc:
            document_sharing_service.grant_share(
                db,
                document=document_a,
                target_company_id=tenant_c.id,
                granted_by_user_id=admin_a.id,
                reason="Unauthorized",
            )
        assert exc.value.http_status == 403

    def test_grant_rejects_self_target(
        self, db, tenant_a, admin_a, document_a
    ):
        from app.services.documents import document_sharing_service
        from app.services.documents.document_sharing_service import SharingError

        with pytest.raises(SharingError) as exc:
            document_sharing_service.grant_share(
                db,
                document=document_a,
                target_company_id=tenant_a.id,
                granted_by_user_id=admin_a.id,
            )
        assert exc.value.http_status == 400

    def test_grant_rejects_duplicate_active(
        self, db, tenant_a, tenant_b, admin_a, document_a, relationship_ab
    ):
        from app.services.documents import document_sharing_service
        from app.services.documents.document_sharing_service import SharingError

        document_sharing_service.grant_share(
            db, document=document_a,
            target_company_id=tenant_b.id,
            granted_by_user_id=admin_a.id,
        )
        db.flush()
        with pytest.raises(SharingError) as exc:
            document_sharing_service.grant_share(
                db, document=document_a,
                target_company_id=tenant_b.id,
                granted_by_user_id=admin_a.id,
            )
        assert exc.value.http_status == 409

    def test_grant_writes_event(
        self, db, tenant_a, tenant_b, admin_a, document_a, relationship_ab
    ):
        from app.models.document_share import DocumentShareEvent
        from app.services.documents import document_sharing_service

        share = document_sharing_service.grant_share(
            db, document=document_a,
            target_company_id=tenant_b.id,
            granted_by_user_id=admin_a.id,
        )
        db.flush()
        events = (
            db.query(DocumentShareEvent)
            .filter_by(share_id=share.id)
            .all()
        )
        assert len(events) == 1
        assert events[0].event_type == "granted"

    def test_has_active_relationship_checks_both_directions(
        self, db, tenant_a, tenant_b, relationship_ab
    ):
        from app.services.documents import document_sharing_service

        # Relationship is B→A (tenant=B, supplier=A)
        assert document_sharing_service.has_active_relationship(
            db, tenant_a.id, tenant_b.id
        )
        assert document_sharing_service.has_active_relationship(
            db, tenant_b.id, tenant_a.id
        )

    def test_ensure_share_is_idempotent(
        self, db, tenant_a, tenant_b, admin_a, document_a, relationship_ab
    ):
        from app.services.documents import document_sharing_service

        share1 = document_sharing_service.ensure_share(
            db, document=document_a,
            target_company_id=tenant_b.id,
            reason="Statement",
            source_module="test",
        )
        db.flush()
        share2 = document_sharing_service.ensure_share(
            db, document=document_a,
            target_company_id=tenant_b.id,
            reason="Statement",
            source_module="test",
        )
        db.flush()
        assert share1.id == share2.id

    def test_ensure_share_bypasses_relationship_by_default(
        self, db, tenant_a, tenant_c, admin_a, document_a
    ):
        """Auto-created shares from generator paths skip relationship
        check — the share itself IS the relationship evidence."""
        from app.services.documents import document_sharing_service

        share = document_sharing_service.ensure_share(
            db,
            document=document_a,
            target_company_id=tenant_c.id,
            reason="delivery",
            source_module="delivery_service",
        )
        db.flush()
        assert share.owner_company_id == tenant_a.id


# ---------------------------------------------------------------------------
# Sharing service — revoke + re-grant
# ---------------------------------------------------------------------------


class TestRevokeShare:
    def test_revoke_sets_revoked_at(
        self, db, tenant_a, tenant_b, admin_a, document_a, relationship_ab
    ):
        from app.services.documents import document_sharing_service

        share = document_sharing_service.grant_share(
            db, document=document_a,
            target_company_id=tenant_b.id,
            granted_by_user_id=admin_a.id,
        )
        db.flush()
        document_sharing_service.revoke_share(
            db, share=share, revoked_by_user_id=admin_a.id,
            revoke_reason="No longer needed",
        )
        db.flush()
        assert share.revoked_at is not None
        assert share.revoked_by_user_id == admin_a.id
        assert share.revoke_reason == "No longer needed"

    def test_revoke_twice_is_409(
        self, db, tenant_a, tenant_b, admin_a, document_a, relationship_ab
    ):
        from app.services.documents import document_sharing_service
        from app.services.documents.document_sharing_service import SharingError

        share = document_sharing_service.grant_share(
            db, document=document_a,
            target_company_id=tenant_b.id,
            granted_by_user_id=admin_a.id,
        )
        db.flush()
        document_sharing_service.revoke_share(
            db, share=share, revoked_by_user_id=admin_a.id,
        )
        db.flush()
        with pytest.raises(SharingError) as exc:
            document_sharing_service.revoke_share(
                db, share=share, revoked_by_user_id=admin_a.id,
            )
        assert exc.value.http_status == 409

    def test_regrant_after_revoke_creates_new_row(
        self, db, tenant_a, tenant_b, admin_a, document_a, relationship_ab
    ):
        from app.services.documents import document_sharing_service

        share1 = document_sharing_service.grant_share(
            db, document=document_a,
            target_company_id=tenant_b.id,
            granted_by_user_id=admin_a.id,
        )
        db.flush()
        document_sharing_service.revoke_share(
            db, share=share1, revoked_by_user_id=admin_a.id,
        )
        db.flush()
        share2 = document_sharing_service.grant_share(
            db, document=document_a,
            target_company_id=tenant_b.id,
            granted_by_user_id=admin_a.id,
        )
        db.flush()
        assert share2.id != share1.id
        assert share2.revoked_at is None
        # Original still retained
        assert share1.revoked_at is not None

    def test_revoke_writes_event(
        self, db, tenant_a, tenant_b, admin_a, document_a, relationship_ab
    ):
        from app.models.document_share import DocumentShareEvent
        from app.services.documents import document_sharing_service

        share = document_sharing_service.grant_share(
            db, document=document_a,
            target_company_id=tenant_b.id,
            granted_by_user_id=admin_a.id,
        )
        db.flush()
        document_sharing_service.revoke_share(
            db, share=share, revoked_by_user_id=admin_a.id,
            revoke_reason="x",
        )
        db.flush()
        events = (
            db.query(DocumentShareEvent)
            .filter_by(share_id=share.id)
            .order_by(DocumentShareEvent.created_at)
            .all()
        )
        types = [e.event_type for e in events]
        assert types == ["granted", "revoked"]


# ---------------------------------------------------------------------------
# Document.visible_to()
# ---------------------------------------------------------------------------


class TestVisibleTo:
    def test_owner_sees_own_document(self, db, tenant_a, document_a):
        from app.models.canonical_document import Document

        rows = (
            db.query(Document)
            .filter(Document.visible_to(tenant_a.id))
            .all()
        )
        assert document_a.id in [r.id for r in rows]

    def test_non_owner_without_share_does_not_see(
        self, db, tenant_a, tenant_b, document_a
    ):
        from app.models.canonical_document import Document

        rows = (
            db.query(Document)
            .filter(Document.visible_to(tenant_b.id))
            .all()
        )
        assert document_a.id not in [r.id for r in rows]

    def test_share_target_sees_shared_document(
        self, db, tenant_a, tenant_b, admin_a, document_a, relationship_ab
    ):
        from app.models.canonical_document import Document
        from app.services.documents import document_sharing_service

        document_sharing_service.grant_share(
            db, document=document_a,
            target_company_id=tenant_b.id,
            granted_by_user_id=admin_a.id,
        )
        db.flush()
        rows = (
            db.query(Document)
            .filter(Document.visible_to(tenant_b.id))
            .all()
        )
        assert document_a.id in [r.id for r in rows]

    def test_revoked_share_hides_document(
        self, db, tenant_a, tenant_b, admin_a, document_a, relationship_ab
    ):
        from app.models.canonical_document import Document
        from app.services.documents import document_sharing_service

        share = document_sharing_service.grant_share(
            db, document=document_a,
            target_company_id=tenant_b.id,
            granted_by_user_id=admin_a.id,
        )
        db.flush()
        # Pre-revoke: visible
        rows_before = (
            db.query(Document).filter(Document.visible_to(tenant_b.id)).all()
        )
        assert document_a.id in [r.id for r in rows_before]
        # Revoke
        document_sharing_service.revoke_share(
            db, share=share, revoked_by_user_id=admin_a.id,
        )
        db.flush()
        # Post-revoke: hidden
        rows_after = (
            db.query(Document).filter(Document.visible_to(tenant_b.id)).all()
        )
        assert document_a.id not in [r.id for r in rows_after]

    def test_is_visible_to_instance_method(
        self, db, tenant_a, tenant_b, admin_a, document_a, relationship_ab
    ):
        from app.services.documents import document_sharing_service

        # Owner always sees
        assert document_a.is_visible_to(tenant_a.id, db=db) is True
        # Non-owner without share
        assert document_a.is_visible_to(tenant_b.id, db=db) is False
        # After grant
        document_sharing_service.grant_share(
            db, document=document_a,
            target_company_id=tenant_b.id,
            granted_by_user_id=admin_a.id,
        )
        db.flush()
        assert document_a.is_visible_to(tenant_b.id, db=db) is True


# ---------------------------------------------------------------------------
# Listing: outgoing + incoming
# ---------------------------------------------------------------------------


class TestListing:
    def test_list_outgoing(
        self, db, tenant_a, tenant_b, admin_a, document_a, relationship_ab
    ):
        from app.services.documents import document_sharing_service

        document_sharing_service.grant_share(
            db, document=document_a,
            target_company_id=tenant_b.id,
            granted_by_user_id=admin_a.id,
        )
        db.flush()
        out = document_sharing_service.list_outgoing_shares(
            db, owner_company_id=tenant_a.id,
        )
        assert len(out) == 1
        assert out[0].target_company_id == tenant_b.id

    def test_list_incoming(
        self, db, tenant_a, tenant_b, admin_a, document_a, relationship_ab
    ):
        from app.services.documents import document_sharing_service

        document_sharing_service.grant_share(
            db, document=document_a,
            target_company_id=tenant_b.id,
            granted_by_user_id=admin_a.id,
            reason="Statement",
        )
        db.flush()
        inbox = document_sharing_service.list_incoming_shares(
            db, target_company_id=tenant_b.id,
        )
        assert len(inbox) == 1
        assert inbox[0].owner_company_id == tenant_a.id
        assert inbox[0].reason == "Statement"

    def test_list_excludes_revoked_by_default(
        self, db, tenant_a, tenant_b, admin_a, document_a, relationship_ab
    ):
        from app.services.documents import document_sharing_service

        share = document_sharing_service.grant_share(
            db, document=document_a,
            target_company_id=tenant_b.id,
            granted_by_user_id=admin_a.id,
        )
        db.flush()
        document_sharing_service.revoke_share(
            db, share=share, revoked_by_user_id=admin_a.id,
        )
        db.flush()
        active = document_sharing_service.list_incoming_shares(
            db, target_company_id=tenant_b.id,
        )
        assert active == []
        with_revoked = document_sharing_service.list_incoming_shares(
            db, target_company_id=tenant_b.id, include_revoked=True,
        )
        assert len(with_revoked) == 1


# ---------------------------------------------------------------------------
# Audit events — append-only
# ---------------------------------------------------------------------------


class TestAuditAppendOnly:
    def test_service_has_no_update_or_delete_on_events(self):
        """Contract: no method in the sharing service updates or deletes
        a share event row."""
        from app.services.documents import document_sharing_service

        names = [
            n
            for n in dir(document_sharing_service)
            if not n.startswith("_")
        ]
        forbidden = [
            n for n in names
            if "event" in n.lower()
            and ("update" in n.lower() or "delete" in n.lower())
        ]
        assert forbidden == []

    def test_record_access_does_not_mutate_share(
        self, db, tenant_a, tenant_b, admin_a, document_a, relationship_ab
    ):
        from app.models.document_share import DocumentShareEvent
        from app.services.documents import document_sharing_service

        share = document_sharing_service.grant_share(
            db, document=document_a,
            target_company_id=tenant_b.id,
            granted_by_user_id=admin_a.id,
        )
        db.flush()
        granted_at_before = share.granted_at
        revoked_at_before = share.revoked_at
        document_sharing_service.record_access(
            db, share=share, actor_user_id=None,
            actor_company_id=tenant_b.id,
        )
        db.flush()
        assert share.granted_at == granted_at_before
        assert share.revoked_at == revoked_at_before
        events = (
            db.query(DocumentShareEvent)
            .filter_by(share_id=share.id, event_type="accessed")
            .count()
        )
        assert events == 1


# ---------------------------------------------------------------------------
# Migrated generators
# ---------------------------------------------------------------------------


class TestGeneratorMigrations:
    def test_cross_tenant_statement_creates_share(
        self, db, tenant_a, tenant_b, admin_a
    ):
        """`cross_tenant_statement_service.deliver_statement_cross_tenant`
        creates a DocumentShare alongside the ReceivedStatement."""
        from app.models.canonical_document import Document
        from app.models.customer import Customer
        from app.models.document_share import DocumentShare
        from app.models.platform_tenant_relationship import (
            PlatformTenantRelationship,
        )
        from app.models.statement import CustomerStatement

        # Create a billing-enabled relationship at insert time — SQLite's
        # server_default handling makes in-place bool updates flaky.
        rel = PlatformTenantRelationship(
            id=str(uuid.uuid4()),
            tenant_id=tenant_b.id,
            supplier_tenant_id=tenant_a.id,
            relationship_type="billing",
            status="active",
            billing_enabled=True,
        )
        db.add(rel)
        db.flush()

        # Seed a customer + statement run + statement + canonical Document
        from app.models.statement import StatementRun

        cust = Customer(
            id=str(uuid.uuid4()),
            company_id=tenant_a.id,
            name="FH-B Customer",
        )
        db.add(cust)
        db.flush()
        run = StatementRun(
            id=str(uuid.uuid4()),
            tenant_id=tenant_a.id,
            statement_period_year=2026,
            statement_period_month=4,
            status="pending",
        )
        db.add(run)
        db.flush()
        stmt = CustomerStatement(
            id=str(uuid.uuid4()),
            tenant_id=tenant_a.id,
            run_id=run.id,
            customer_id=cust.id,
            statement_period_year=2026,
            statement_period_month=4,
            previous_balance=0, new_charges=100, payments_received=0,
            balance_due=100, invoice_count=1,
            delivery_method="platform",
            status="pending",
        )
        db.add(stmt)
        db.flush()
        doc = Document(
            id=str(uuid.uuid4()),
            company_id=tenant_a.id,
            document_type="statement",
            title="April 2026 Statement",
            storage_key=f"tenants/{tenant_a.id}/documents/stmt/v1.pdf",
            mime_type="application/pdf",
            status="rendered",
            customer_statement_id=stmt.id,
        )
        db.add(doc)
        db.flush()

        from app.services import cross_tenant_statement_service

        # The service calls db.commit() internally; swap for flush() so
        # the surrounding test rollback still works.
        original_commit = db.commit
        db.commit = db.flush  # type: ignore[assignment]
        try:
            ok = cross_tenant_statement_service.deliver_statement_cross_tenant(
                db, customer_statement_id=stmt.id, tenant_id=tenant_a.id,
            )
        finally:
            db.commit = original_commit  # type: ignore[assignment]
        assert ok, f"deliver returned False; stmt.send_error={stmt.send_error!r}"
        db.refresh(doc)
        share = (
            db.query(DocumentShare)
            .filter(
                DocumentShare.document_id == doc.id,
                DocumentShare.target_company_id == tenant_b.id,
            )
            .first()
        )
        assert share is not None
        assert share.source_module == "cross_tenant_statement_service"

    def test_legacy_vault_print_share_helper(
        self, db, tenant_a, tenant_b, document_a, relationship_ab
    ):
        """Direct test of `_share_legacy_print_with_manufacturer`."""
        from app.models.document_share import DocumentShare
        from app.services.fh.legacy_vault_print_service import (
            _share_legacy_print_with_manufacturer,
        )

        _share_legacy_print_with_manufacturer(
            db,
            document_id=document_a.id,
            manufacturer_company_id=tenant_b.id,
            case_number="CASE-1",
        )
        db.flush()
        share = (
            db.query(DocumentShare)
            .filter(
                DocumentShare.document_id == document_a.id,
                DocumentShare.target_company_id == tenant_b.id,
            )
            .first()
        )
        assert share is not None
        assert share.source_module == "legacy_vault_print_service"
        assert "CASE-1" in (share.reason or "")

    def test_legacy_vault_print_share_noop_if_same_tenant(
        self, db, tenant_a, document_a
    ):
        from app.models.document_share import DocumentShare
        from app.services.fh.legacy_vault_print_service import (
            _share_legacy_print_with_manufacturer,
        )

        _share_legacy_print_with_manufacturer(
            db,
            document_id=document_a.id,
            manufacturer_company_id=tenant_a.id,  # same as owner
            case_number="CASE-2",
        )
        db.flush()
        shares = (
            db.query(DocumentShare)
            .filter_by(document_id=document_a.id)
            .all()
        )
        assert shares == []


# ---------------------------------------------------------------------------
# API permission gates
# ---------------------------------------------------------------------------


class TestAPIPermissions:
    def test_cannot_grant_on_non_owned_document(
        self, db, tenant_a, tenant_b, document_a, relationship_ab
    ):
        """Calling `_get_owned_document_or_404` with a non-owner tenant
        returns 404."""
        from fastapi import HTTPException
        from app.api.routes.documents_v2 import _get_owned_document_or_404

        with pytest.raises(HTTPException) as exc:
            _get_owned_document_or_404(db, document_a.id, tenant_b.id)
        assert exc.value.status_code == 404

    def test_owner_can_fetch_owned_document(
        self, db, tenant_a, document_a
    ):
        from app.api.routes.documents_v2 import _get_owned_document_or_404

        doc = _get_owned_document_or_404(db, document_a.id, tenant_a.id)
        assert doc.id == document_a.id

    def test_get_visible_document_resolves_shared(
        self, db, tenant_a, tenant_b, admin_a, document_a, relationship_ab
    ):
        """Once shared, `_get_visible_document` resolves for the target
        tenant (D-6 upgrade from D-1's owner-only check)."""
        from app.api.routes.documents_v2 import _get_visible_document
        from app.services.documents import document_sharing_service

        # Before share: 404 for target
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            _get_visible_document(db, document_a.id, tenant_b.id)

        document_sharing_service.grant_share(
            db, document=document_a,
            target_company_id=tenant_b.id,
            granted_by_user_id=admin_a.id,
        )
        db.flush()
        # After share: resolves
        doc = _get_visible_document(db, document_a.id, tenant_b.id)
        assert doc.id == document_a.id


# ---------------------------------------------------------------------------
# caller_document_share_id on IntelligenceExecution
# ---------------------------------------------------------------------------


class TestIntelligenceLinkage:
    def test_intelligence_execution_has_caller_document_share_id(self):
        """Column was added in the r25 migration — symmetric linkage
        pattern with caller_document_id."""
        from app.models.intelligence import IntelligenceExecution

        assert hasattr(IntelligenceExecution, "caller_document_share_id")


# ---------------------------------------------------------------------------
# Phase D-8 — per-user inbox read tracking
# ---------------------------------------------------------------------------


class TestInboxReadTracking:
    def test_mark_share_read_is_idempotent(
        self, db, tenant_a, tenant_b, admin_a, document_a, relationship_ab
    ):
        """Marking a share read twice returns the same row; first
        read_at wins."""
        from app.services.documents import document_sharing_service

        share = document_sharing_service.grant_share(
            db,
            document=document_a,
            target_company_id=tenant_b.id,
            granted_by_user_id=admin_a.id,
        )
        db.flush()
        first = document_sharing_service.mark_share_read(
            db, share_id=share.id, user_id=admin_a.id
        )
        second = document_sharing_service.mark_share_read(
            db, share_id=share.id, user_id=admin_a.id
        )
        assert first.share_id == second.share_id
        assert first.user_id == second.user_id
        assert first.read_at == second.read_at  # first-read wins

    def test_read_state_is_per_user(
        self, db, tenant_a, tenant_b, admin_a, document_a, relationship_ab
    ):
        """Two users on the same tenant have independent read state."""
        import uuid as _uuid

        from app.models.role import Role
        from app.models.user import User
        from app.services.documents import document_sharing_service

        role = Role(
            id=str(_uuid.uuid4()),
            company_id=tenant_b.id,
            name="Admin",
            slug="admin",
            is_system=True,
        )
        db.add(role)
        db.flush()
        u1 = User(
            id=str(_uuid.uuid4()),
            company_id=tenant_b.id,
            email="u1@b.co",
            first_name="U1",
            last_name="B",
            hashed_password="x",
            is_active=True,
            role_id=role.id,
        )
        u2 = User(
            id=str(_uuid.uuid4()),
            company_id=tenant_b.id,
            email="u2@b.co",
            first_name="U2",
            last_name="B",
            hashed_password="x",
            is_active=True,
            role_id=role.id,
        )
        db.add_all([u1, u2])
        db.flush()

        share = document_sharing_service.grant_share(
            db,
            document=document_a,
            target_company_id=tenant_b.id,
            granted_by_user_id=admin_a.id,
        )
        db.flush()
        document_sharing_service.mark_share_read(
            db, share_id=share.id, user_id=u1.id
        )
        # u1 has read; u2 has not.
        u1_reads = document_sharing_service.get_read_share_ids(
            db, user_id=u1.id, share_ids=[share.id]
        )
        u2_reads = document_sharing_service.get_read_share_ids(
            db, user_id=u2.id, share_ids=[share.id]
        )
        assert share.id in u1_reads
        assert share.id not in u2_reads

    def test_mark_all_incoming_read_skips_already_read(
        self, db, tenant_a, tenant_b, admin_a, document_a, relationship_ab
    ):
        """`mark_all_incoming_read` returns count of NEW inserts."""
        from app.models.canonical_document import Document
        from app.services.documents import document_sharing_service

        # Second document + share so there are 2 active incoming.
        doc_b = Document(
            id=str(uuid.uuid4()),
            company_id=tenant_a.id,
            document_type="statement",
            title="Statement Two",
            storage_key=f"tenants/{tenant_a.id}/documents/stmt2/v1.pdf",
            mime_type="application/pdf",
            file_size_bytes=100,
            status="rendered",
        )
        db.add(doc_b)
        db.flush()
        s1 = document_sharing_service.grant_share(
            db,
            document=document_a,
            target_company_id=tenant_b.id,
            granted_by_user_id=admin_a.id,
        )
        document_sharing_service.grant_share(
            db,
            document=doc_b,
            target_company_id=tenant_b.id,
            granted_by_user_id=admin_a.id,
        )
        db.flush()

        # Pre-read one.
        document_sharing_service.mark_share_read(
            db, share_id=s1.id, user_id=admin_a.id
        )
        # Bulk: should insert just one (the other).
        count = document_sharing_service.mark_all_incoming_read(
            db, target_company_id=tenant_b.id, user_id=admin_a.id
        )
        assert count == 1
        # Second call: nothing new.
        count2 = document_sharing_service.mark_all_incoming_read(
            db, target_company_id=tenant_b.id, user_id=admin_a.id
        )
        assert count2 == 0

    def test_mark_all_incoming_read_ignores_revoked(
        self, db, tenant_a, tenant_b, admin_a, document_a, relationship_ab
    ):
        """Revoked shares don't count against the unread total."""
        from app.services.documents import document_sharing_service

        share = document_sharing_service.grant_share(
            db,
            document=document_a,
            target_company_id=tenant_b.id,
            granted_by_user_id=admin_a.id,
        )
        db.flush()
        document_sharing_service.revoke_share(
            db, share=share, revoked_by_user_id=admin_a.id
        )
        db.flush()
        count = document_sharing_service.mark_all_incoming_read(
            db, target_company_id=tenant_b.id, user_id=admin_a.id
        )
        assert count == 0
