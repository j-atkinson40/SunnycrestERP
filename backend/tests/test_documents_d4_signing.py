"""Phase D-4 tests — native signing infrastructure.

Covers envelope lifecycle, signer flow, field handling, token security,
lifecycle transitions, tamper detection, audit integrity, and permission
gates.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
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
    from app.models.fh_case import FHCase  # noqa: F401
    from app.models.invoice import Invoice  # noqa: F401
    from app.models.price_list_version import PriceListVersion  # noqa: F401
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
        "signature_envelopes",
        "signature_parties",
        "signature_fields",
        "signature_events",
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

    # Seed signing-related platform templates so rendering succeeds
    _seed_signing_templates(session)
    yield session
    session.close()
    trans.rollback()
    conn.close()


def _seed_signing_templates(session: Session) -> None:
    from app.models.document_template import (
        DocumentTemplate,
        DocumentTemplateVersion,
    )
    from app.services.documents._template_seeds import _signing_seeds

    for seed in _signing_seeds():
        tpl = DocumentTemplate(
            id=str(uuid.uuid4()),
            company_id=None,
            template_key=seed["template_key"],
            document_type=seed["document_type"],
            output_format=seed["output_format"],
            description=seed.get("description"),
            supports_variants=False,
            is_active=True,
        )
        session.add(tpl)
        session.flush()
        v = DocumentTemplateVersion(
            id=str(uuid.uuid4()),
            template_id=tpl.id,
            version_number=1,
            status="active",
            body_template=seed["body_template"],
            subject_template=seed.get("subject_template"),
            activated_at=datetime.now(timezone.utc),
        )
        session.add(v)
        session.flush()
        tpl.current_version_id = v.id
    session.flush()


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
def admin_user(db, tenant):
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
        email="admin@tenant.a",
        first_name="Ada",
        last_name="Admin",
        hashed_password="x",
        is_active=True,
        is_super_admin=False,
        role_id=role.id,
    )
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def document(db, tenant):
    from app.models.canonical_document import Document

    d = Document(
        id=str(uuid.uuid4()),
        company_id=tenant.id,
        document_type="disinterment_release",
        title="Test Release Form",
        storage_key=f"tenants/{tenant.id}/documents/test-doc/v1.pdf",
        mime_type="application/pdf",
        file_size_bytes=100,
        status="rendered",
    )
    db.add(d)
    db.flush()
    return d


def _make_party_input(order: int, role: str = "signer"):
    from app.services.signing.signature_service import PartyInput

    return PartyInput(
        signing_order=order,
        role=role,
        display_name=f"Signer {order}",
        email=f"signer{order}@example.com",
    )


def _create_envelope(
    db, *, tenant, admin_user, document, parties=None, fields=None,
    routing_type="sequential",
):
    from app.services.signing import signature_service

    parties = parties or [
        _make_party_input(1, "funeral_home_director"),
        _make_party_input(2, "next_of_kin"),
    ]
    fields = fields or []
    # Patch R2 to avoid needing actual uploads
    with patch(
        "app.services.signing.signature_service.legacy_r2_client"
    ) as mock_r2:
        mock_r2.download_bytes.return_value = b"%PDF fake content"
        env = signature_service.create_envelope(
            db,
            document_id=document.id,
            company_id=tenant.id,
            created_by_user_id=admin_user.id,
            subject="Test envelope",
            description="Test description",
            parties=parties,
            fields=fields,
            routing_type=routing_type,
        )
    db.flush()
    return env


# ---------------------------------------------------------------------------
# Token service
# ---------------------------------------------------------------------------


class TestTokenService:
    def test_token_is_urlsafe_and_long(self):
        from app.services.signing.token_service import generate_signer_token

        tok = generate_signer_token()
        assert isinstance(tok, str)
        assert len(tok) >= 40  # 32 bytes base64-urlsafe ~= 43 chars
        # No padding
        assert "=" not in tok

    def test_tokens_are_unique(self):
        from app.services.signing.token_service import generate_signer_token

        tokens = {generate_signer_token() for _ in range(200)}
        assert len(tokens) == 200


# ---------------------------------------------------------------------------
# Envelope creation
# ---------------------------------------------------------------------------


class TestEnvelopeCreation:
    def test_create_envelope_draft_status(self, db, tenant, admin_user, document):
        env = _create_envelope(db, tenant=tenant, admin_user=admin_user, document=document)
        assert env.status == "draft"

    def test_create_envelope_generates_document_hash(self, db, tenant, admin_user, document):
        env = _create_envelope(db, tenant=tenant, admin_user=admin_user, document=document)
        assert env.document_hash
        assert len(env.document_hash) == 64  # SHA-256 hex

    def test_create_envelope_generates_unique_party_tokens(
        self, db, tenant, admin_user, document
    ):
        env = _create_envelope(db, tenant=tenant, admin_user=admin_user, document=document)
        tokens = {p.signer_token for p in env.parties}
        assert len(tokens) == len(env.parties)
        for t in tokens:
            assert len(t) >= 40

    def test_create_envelope_requires_parties(self, db, tenant, admin_user, document):
        from app.services.signing import signature_service
        from app.services.signing.signature_service import SignatureServiceError

        with patch("app.services.signing.signature_service.legacy_r2_client") as mock_r2:
            mock_r2.download_bytes.return_value = b"%PDF"
            with pytest.raises(SignatureServiceError):
                signature_service.create_envelope(
                    db,
                    document_id=document.id,
                    company_id=tenant.id,
                    created_by_user_id=admin_user.id,
                    subject="X",
                    description=None,
                    parties=[],
                    fields=[],
                )

    def test_create_envelope_rejects_cross_tenant_document(
        self, db, tenant, admin_user
    ):
        from app.models.canonical_document import Document
        from app.models.company import Company
        from app.services.signing import signature_service
        from app.services.signing.signature_service import SignatureServiceError

        other = Company(
            id=str(uuid.uuid4()), name="Other", slug="other", is_active=True
        )
        db.add(other)
        db.flush()
        other_doc = Document(
            id=str(uuid.uuid4()),
            company_id=other.id,
            document_type="x",
            title="Other",
            storage_key="x",
            mime_type="application/pdf",
            status="rendered",
        )
        db.add(other_doc)
        db.flush()

        with patch("app.services.signing.signature_service.legacy_r2_client") as mock_r2:
            mock_r2.download_bytes.return_value = b"%PDF"
            with pytest.raises(SignatureServiceError) as exc:
                signature_service.create_envelope(
                    db,
                    document_id=other_doc.id,
                    company_id=tenant.id,
                    created_by_user_id=admin_user.id,
                    subject="X",
                    description=None,
                    parties=[_make_party_input(1)],
                    fields=[],
                )
            assert exc.value.http_status == 404

    def test_create_envelope_creates_event(self, db, tenant, admin_user, document):
        from app.models.signature import SignatureEvent

        env = _create_envelope(db, tenant=tenant, admin_user=admin_user, document=document)
        events = (
            db.query(SignatureEvent)
            .filter_by(envelope_id=env.id)
            .all()
        )
        assert any(e.event_type == "envelope_created" for e in events)


# ---------------------------------------------------------------------------
# Envelope lifecycle — send
# ---------------------------------------------------------------------------


class TestEnvelopeSend:
    def test_send_envelope_sequential_notifies_first_only(
        self, db, tenant, admin_user, document
    ):
        from app.services.signing import signature_service

        env = _create_envelope(
            db, tenant=tenant, admin_user=admin_user, document=document,
            routing_type="sequential",
        )
        with patch(
            "app.services.signing.notification_service.send_invite"
        ) as mock_invite:
            signature_service.send_envelope(db, env.id)
        db.flush()
        assert mock_invite.call_count == 1
        # Only first party transitioned to sent
        parties = sorted(env.parties, key=lambda p: p.signing_order)
        assert parties[0].status == "sent"
        assert parties[1].status == "pending"

    def test_send_envelope_parallel_notifies_all(
        self, db, tenant, admin_user, document
    ):
        from app.services.signing import signature_service

        env = _create_envelope(
            db, tenant=tenant, admin_user=admin_user, document=document,
            routing_type="parallel",
        )
        with patch(
            "app.services.signing.notification_service.send_invite"
        ) as mock_invite:
            signature_service.send_envelope(db, env.id)
        db.flush()
        assert mock_invite.call_count == len(env.parties)
        for p in env.parties:
            assert p.status == "sent"

    def test_send_envelope_rejects_non_draft(
        self, db, tenant, admin_user, document
    ):
        from app.services.signing import signature_service
        from app.services.signing.signature_service import SignatureServiceError

        env = _create_envelope(db, tenant=tenant, admin_user=admin_user, document=document)
        with patch("app.services.signing.notification_service.send_invite"):
            signature_service.send_envelope(db, env.id)
        db.flush()
        with pytest.raises(SignatureServiceError) as exc:
            signature_service.send_envelope(db, env.id)
        assert exc.value.http_status == 409


# ---------------------------------------------------------------------------
# Signer flow — view, consent, sign, decline
# ---------------------------------------------------------------------------


class TestSignerFlow:
    def _send_envelope(self, db, env):
        from app.services.signing import signature_service

        with patch("app.services.signing.notification_service.send_invite"):
            signature_service.send_envelope(db, env.id)
        db.flush()

    def test_view_link_records_viewed_status(
        self, db, tenant, admin_user, document
    ):
        from app.services.signing import signature_service

        env = _create_envelope(db, tenant=tenant, admin_user=admin_user, document=document)
        self._send_envelope(db, env)
        p1 = sorted(env.parties, key=lambda p: p.signing_order)[0]
        signature_service.record_party_view(
            db, p1, ip_address="1.2.3.4", user_agent="Mozilla/5.0"
        )
        db.flush()
        assert p1.status == "viewed"
        assert p1.viewed_at is not None
        # Envelope transitioned to in_progress
        assert env.status == "in_progress"

    def test_consent_transitions_party_status(
        self, db, tenant, admin_user, document
    ):
        from app.services.signing import signature_service

        env = _create_envelope(db, tenant=tenant, admin_user=admin_user, document=document)
        self._send_envelope(db, env)
        p1 = sorted(env.parties, key=lambda p: p.signing_order)[0]
        signature_service.record_party_view(
            db, p1, ip_address="1.2.3.4", user_agent="ua"
        )
        signature_service.record_party_consent(
            db, p1, consent_text="I agree",
            ip_address="1.2.3.4", user_agent="ua",
        )
        db.flush()
        assert p1.status == "consented"
        assert p1.consented_at is not None

    def test_sign_records_all_data(
        self, db, tenant, admin_user, document
    ):
        from app.services.signing import signature_service

        env = _create_envelope(db, tenant=tenant, admin_user=admin_user, document=document)
        self._send_envelope(db, env)
        p1 = sorted(env.parties, key=lambda p: p.signing_order)[0]
        signature_service.record_party_view(
            db, p1, ip_address="1.2.3.4", user_agent="ua"
        )
        signature_service.record_party_consent(
            db, p1, consent_text="I agree",
            ip_address="1.2.3.4", user_agent="ua",
        )
        # Mock completion path — avoid actual PDF generation
        with patch(
            "app.services.signing.signature_service.complete_envelope"
        ):
            signature_service.record_party_signature(
                db, p1,
                signature_type="typed",
                signature_data="John Smith",
                typed_signature_name="John Smith",
                field_values={},
                ip_address="9.9.9.9",
                user_agent="SignerBrowser",
            )
        db.flush()
        assert p1.status == "signed"
        assert p1.signed_at is not None
        assert p1.signature_type == "typed"
        assert p1.signature_data == "John Smith"
        assert p1.typed_signature_name == "John Smith"
        assert p1.signing_ip_address == "9.9.9.9"
        assert p1.signing_user_agent == "SignerBrowser"

    def test_sign_triggers_next_party_sequential(
        self, db, tenant, admin_user, document
    ):
        from app.services.signing import signature_service

        env = _create_envelope(
            db, tenant=tenant, admin_user=admin_user, document=document,
            routing_type="sequential",
        )
        self._send_envelope(db, env)
        parties = sorted(env.parties, key=lambda p: p.signing_order)
        p1, p2 = parties[0], parties[1]
        signature_service.record_party_view(db, p1)
        signature_service.record_party_consent(
            db, p1, consent_text="I agree", ip_address=None, user_agent=None
        )
        with patch(
            "app.services.signing.notification_service.send_invite"
        ) as mock_invite, patch(
            "app.services.signing.signature_service.complete_envelope"
        ):
            signature_service.record_party_signature(
                db, p1,
                signature_type="typed",
                signature_data="Signed",
                typed_signature_name="Signed",
                field_values={},
                ip_address=None, user_agent=None,
            )
        db.flush()
        assert p1.status == "signed"
        assert p2.status == "sent"
        # Next party notified
        assert mock_invite.called

    def test_sign_completes_envelope_when_last_party(
        self, db, tenant, admin_user, document
    ):
        from app.services.signing import signature_service

        env = _create_envelope(
            db, tenant=tenant, admin_user=admin_user, document=document,
            parties=[_make_party_input(1)],
        )
        self._send_envelope(db, env)
        p1 = env.parties[0]
        signature_service.record_party_view(db, p1)
        signature_service.record_party_consent(
            db, p1, consent_text="I agree", ip_address=None, user_agent=None
        )
        # Mock heavy completion paths
        with patch(
            "app.services.signing.signature_renderer.apply_signatures_as_new_version"
        ), patch(
            "app.services.signing.certificate_service.generate_certificate"
        ) as mock_cert, patch(
            "app.services.signing.notification_service.send_completed"
        ):
            cert_doc = type(
                "DocStub", (), {"id": "cert-id"}
            )()
            mock_cert.return_value = cert_doc
            signature_service.record_party_signature(
                db, p1,
                signature_type="typed",
                signature_data="Last",
                typed_signature_name="Last",
                field_values={},
                ip_address=None, user_agent=None,
            )
        db.flush()
        assert env.status == "completed"
        assert env.completed_at is not None

    def test_decline_cancels_envelope(
        self, db, tenant, admin_user, document
    ):
        from app.services.signing import signature_service

        env = _create_envelope(db, tenant=tenant, admin_user=admin_user, document=document)
        self._send_envelope(db, env)
        p1 = sorted(env.parties, key=lambda p: p.signing_order)[0]
        signature_service.record_party_view(db, p1)
        with patch(
            "app.services.signing.notification_service.send_declined"
        ):
            signature_service.record_party_decline(
                db, p1,
                reason="Signer changed their mind",
                ip_address="2.2.2.2", user_agent="ua",
            )
        db.flush()
        assert env.status == "declined"
        # Other parties transitioned to expired
        other = sorted(env.parties, key=lambda p: p.signing_order)[1]
        assert other.status == "expired"


# ---------------------------------------------------------------------------
# Field handling
# ---------------------------------------------------------------------------


class TestFieldHandling:
    def test_field_values_persist(
        self, db, tenant, admin_user, document
    ):
        from app.services.signing import signature_service
        from app.services.signing.signature_service import FieldInput

        fields = [
            FieldInput(signing_order=1, field_type="signature", anchor_string="/sig/"),
            FieldInput(
                signing_order=1, field_type="text",
                anchor_string="/name/", label="Full name",
            ),
        ]
        env = _create_envelope(
            db, tenant=tenant, admin_user=admin_user, document=document,
            parties=[_make_party_input(1)],
            fields=fields,
        )
        with patch("app.services.signing.notification_service.send_invite"):
            signature_service.send_envelope(db, env.id)
        p1 = env.parties[0]
        signature_service.record_party_view(db, p1)
        signature_service.record_party_consent(
            db, p1, consent_text="I agree", ip_address=None, user_agent=None,
        )
        text_field = next(f for f in p1.fields if f.field_type == "text")
        with patch(
            "app.services.signing.signature_renderer.apply_signatures_as_new_version"
        ), patch(
            "app.services.signing.certificate_service.generate_certificate"
        ) as mock_cert, patch(
            "app.services.signing.notification_service.send_completed"
        ):
            mock_cert.return_value = type(
                "DocStub", (), {"id": "cert-doc-id"}
            )()
            signature_service.record_party_signature(
                db, p1,
                signature_type="typed",
                signature_data="x",
                typed_signature_name="x",
                field_values={text_field.id: "John Q. Public"},
                ip_address=None, user_agent=None,
            )
        db.flush()
        db.refresh(text_field)
        assert text_field.value == "John Q. Public"

    def test_required_fields_must_be_filled(
        self, db, tenant, admin_user, document
    ):
        from app.services.signing import signature_service
        from app.services.signing.signature_service import (
            FieldInput,
            SignatureServiceError,
        )

        fields = [
            FieldInput(
                signing_order=1, field_type="text",
                anchor_string="/name/", label="Full name", required=True,
            ),
        ]
        env = _create_envelope(
            db, tenant=tenant, admin_user=admin_user, document=document,
            parties=[_make_party_input(1)],
            fields=fields,
        )
        with patch("app.services.signing.notification_service.send_invite"):
            signature_service.send_envelope(db, env.id)
        p1 = env.parties[0]
        signature_service.record_party_view(db, p1)
        signature_service.record_party_consent(
            db, p1, consent_text="I agree", ip_address=None, user_agent=None,
        )
        with pytest.raises(SignatureServiceError):
            signature_service.record_party_signature(
                db, p1,
                signature_type="typed",
                signature_data="x",
                typed_signature_name="x",
                field_values={},  # missing required text field
                ip_address=None, user_agent=None,
            )


# ---------------------------------------------------------------------------
# Void + resend
# ---------------------------------------------------------------------------


class TestVoidAndResend:
    def test_void_envelope_cancels_pending_parties(
        self, db, tenant, admin_user, document
    ):
        from app.services.signing import signature_service

        env = _create_envelope(db, tenant=tenant, admin_user=admin_user, document=document)
        with patch("app.services.signing.notification_service.send_invite"):
            signature_service.send_envelope(db, env.id)
        with patch(
            "app.services.signing.notification_service.send_voided"
        ):
            signature_service.void_envelope(
                db, env.id, reason="No longer needed",
                voided_by_user_id=admin_user.id,
            )
        db.flush()
        assert env.status == "voided"
        assert env.voided_at is not None
        for p in env.parties:
            assert p.status == "expired"

    def test_resend_notification_increments_count(
        self, db, tenant, admin_user, document
    ):
        from app.services.signing import signature_service

        env = _create_envelope(db, tenant=tenant, admin_user=admin_user, document=document)
        with patch("app.services.signing.notification_service.send_invite"):
            signature_service.send_envelope(db, env.id)
        p1 = sorted(env.parties, key=lambda p: p.signing_order)[0]
        prior = p1.notification_sent_count
        with patch("app.services.signing.notification_service.send_invite"):
            signature_service.resend_notification(db, p1.id)
        db.flush()
        assert p1.notification_sent_count == prior + 1

    def test_check_expiration_transitions_expired(
        self, db, tenant, admin_user, document
    ):
        from app.models.signature import SignatureEnvelope
        from app.services.signing import signature_service

        env = _create_envelope(db, tenant=tenant, admin_user=admin_user, document=document)
        with patch("app.services.signing.notification_service.send_invite"):
            signature_service.send_envelope(db, env.id)
        # Force expires_at into the past
        env.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.flush()

        count = signature_service.check_expiration(db)
        assert count == 1
        db.refresh(env)
        assert env.status == "expired"


# ---------------------------------------------------------------------------
# Tamper detection
# ---------------------------------------------------------------------------


class TestTamperDetection:
    def test_document_hash_recorded_at_creation(
        self, db, tenant, admin_user, document
    ):
        env = _create_envelope(db, tenant=tenant, admin_user=admin_user, document=document)
        assert len(env.document_hash) == 64

    def test_hash_function_is_deterministic(self):
        from app.services.signing.signature_service import compute_document_hash

        a = compute_document_hash(b"hello world")
        b = compute_document_hash(b"hello world")
        c = compute_document_hash(b"hello worldx")
        assert a == b
        assert a != c


# ---------------------------------------------------------------------------
# Audit integrity
# ---------------------------------------------------------------------------


class TestAuditIntegrity:
    def test_signature_events_sequence_monotonic(
        self, db, tenant, admin_user, document
    ):
        from app.models.signature import SignatureEvent
        from app.services.signing import signature_service

        env = _create_envelope(db, tenant=tenant, admin_user=admin_user, document=document)
        with patch("app.services.signing.notification_service.send_invite"):
            signature_service.send_envelope(db, env.id)
        p1 = sorted(env.parties, key=lambda p: p.signing_order)[0]
        signature_service.record_party_view(db, p1)
        signature_service.record_party_consent(
            db, p1, consent_text="I agree", ip_address=None, user_agent=None,
        )
        db.flush()
        events = (
            db.query(SignatureEvent)
            .filter_by(envelope_id=env.id)
            .order_by(SignatureEvent.sequence_number)
            .all()
        )
        seqs = [e.sequence_number for e in events]
        # Monotonically increasing starting at 1
        assert seqs == list(range(1, len(seqs) + 1))

    def test_signature_events_service_has_no_update_or_delete(self):
        """The audit log is append-only by convention; the service module
        exposes only record_event, no update/delete helpers."""
        from app.services.signing import signature_service

        public = [
            name
            for name in dir(signature_service)
            if not name.startswith("_")
        ]
        # Deny-list: no verb like update/delete on events should exist
        denied = [
            n
            for n in public
            if "event" in n.lower()
            and (
                "update" in n.lower()
                or "delete" in n.lower()
                or "modify" in n.lower()
            )
        ]
        assert denied == []

    def test_event_meta_json_stores_kwargs(
        self, db, tenant, admin_user, document
    ):
        from app.models.signature import SignatureEvent

        env = _create_envelope(db, tenant=tenant, admin_user=admin_user, document=document)
        created = (
            db.query(SignatureEvent)
            .filter_by(envelope_id=env.id, event_type="envelope_created")
            .first()
        )
        assert created is not None
        assert "party_count" in created.meta_json
        assert created.meta_json["party_count"] == 2


# ---------------------------------------------------------------------------
# Public route — token validation + rate limit
# ---------------------------------------------------------------------------


class TestPublicRoutes:
    def test_invalid_token_returns_404(self):
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            r = client.get(
                "/api/v1/sign/not-a-real-token/status"
            )
            assert r.status_code == 404

    def test_token_rate_limit_enforced(self):
        from fastapi.testclient import TestClient
        from app.main import app
        from app.api.routes import signing_public

        # Clear any prior state
        signing_public._REQUEST_LOG.clear()
        with TestClient(app) as client:
            for _ in range(signing_public._RATE_MAX_REQUESTS):
                r = client.get("/api/v1/sign/rate-test/status")
                # 404 because token doesn't exist — but rate limit check runs first
                assert r.status_code in (404, 429)
            r = client.get("/api/v1/sign/rate-test/status")
            assert r.status_code == 429


# ---------------------------------------------------------------------------
# Permission gates
# ---------------------------------------------------------------------------


class TestPermissionGates:
    def test_admin_cannot_access_cross_tenant_envelope(
        self, db, tenant, admin_user, document
    ):
        from app.models.company import Company
        from app.models.role import Role
        from app.models.user import User
        from app.services.signing import signature_service

        env = _create_envelope(db, tenant=tenant, admin_user=admin_user, document=document)
        # Create different tenant + admin
        other = Company(
            id=str(uuid.uuid4()), name="Other", slug="other", is_active=True,
        )
        db.add(other)
        db.flush()
        other_role = Role(
            id=str(uuid.uuid4()), company_id=other.id, name="Admin",
            slug="admin", is_system=True,
        )
        db.add(other_role)
        db.flush()
        other_admin = User(
            id=str(uuid.uuid4()), company_id=other.id,
            email="other@other.co",
            first_name="O", last_name="O",
            hashed_password="x", is_active=True, role_id=other_role.id,
        )
        db.add(other_admin)
        db.flush()

        # tenant-scoped lookup returns None for cross-tenant caller
        found = signature_service.get_envelope_for_tenant(
            db, env.id, other_admin.company_id
        )
        assert found is None

    def test_public_signing_routes_no_auth_required(self):
        """The /sign/* routes are intentionally unauthenticated —
        signer_token is the sole auth. Verify the path is registered
        OUTSIDE any auth dependency."""
        from app.main import app

        sign_routes = [
            r for r in app.routes
            if getattr(r, "path", "").startswith("/api/v1/sign/{token}")
        ]
        assert len(sign_routes) >= 4
        # None of these endpoints use auth dependencies at route level;
        # verified structurally by looking at the dependency injection
        # signatures (no require_admin / get_current_user).
        for r in sign_routes:
            if hasattr(r, "dependant"):
                dep_names = [
                    d.call.__name__ if hasattr(d, "call") else str(d)
                    for d in getattr(r.dependant, "dependencies", [])
                ]
                assert "require_admin" not in dep_names
                assert "get_current_user" not in dep_names
