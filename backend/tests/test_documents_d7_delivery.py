"""Phase D-7 tests — delivery abstraction.

Covers channel protocol + implementations, DeliveryService orchestration,
retry logic, workflow integration, migrated callers, and the admin API.
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
# Engine + fixtures
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
    from app.models.document_delivery import DocumentDelivery  # noqa: F401
    from app.models.document_share import (  # noqa: F401
        DocumentShare,
        DocumentShareEvent,
    )
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
    from app.models.role import Role  # noqa: F401
    from app.models.safety_program_generation import SafetyProgramGeneration  # noqa: F401
    from app.models.sales_order import SalesOrder  # noqa: F401
    from app.models.signature import (  # noqa: F401
        SignatureEnvelope,
        SignatureEvent,
        SignatureField,
        SignatureParty,
    )
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
        "document_shares",
        "document_share_events",
        "platform_tenant_relationships",
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
    # Seed the email templates once (signing tests need them)
    _seed_templates(session)
    yield session
    session.close()
    trans.rollback()
    conn.close()


def _seed_templates(session: Session) -> None:
    """Seed platform templates needed by D-7 flows."""
    from app.models.document_template import (
        DocumentTemplate,
        DocumentTemplateVersion,
    )
    from app.services.documents._template_seeds import (
        list_platform_template_seeds,
    )

    for seed in list_platform_template_seeds():
        if seed["output_format"] != "html":
            continue  # only emails for this fixture
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
        id=str(uuid.uuid4()), name="Mfg A", slug="mfg-a", is_active=True,
    )
    db.add(c)
    db.flush()
    return c


@pytest.fixture
def admin(db, tenant):
    from app.models.role import Role
    from app.models.user import User

    r = Role(id=str(uuid.uuid4()), company_id=tenant.id, name="Admin",
             slug="admin", is_system=True)
    db.add(r)
    db.flush()
    u = User(
        id=str(uuid.uuid4()), company_id=tenant.id,
        email="admin@a.co", first_name="A", last_name="A",
        hashed_password="x", is_active=True, role_id=r.id,
    )
    db.add(u)
    db.flush()
    return u


# ---------------------------------------------------------------------------
# Channel protocol + registry
# ---------------------------------------------------------------------------


class TestChannelRegistry:
    def test_get_channel_email_returns_email_channel(self):
        from app.services.delivery import EmailChannel, get_channel

        assert isinstance(get_channel("email"), EmailChannel)

    def test_get_channel_sms_returns_sms_channel(self):
        from app.services.delivery import SMSChannel, get_channel

        assert isinstance(get_channel("sms"), SMSChannel)

    def test_unknown_channel_raises(self):
        from app.services.delivery import UnknownChannelError, get_channel

        with pytest.raises(UnknownChannelError):
            get_channel("carrier_pigeon")

    def test_email_channel_supports_attachments_and_html(self):
        from app.services.delivery import EmailChannel

        c = EmailChannel()
        assert c.supports_attachments()
        assert c.supports_html_body()
        assert c.channel_type == "email"
        assert c.provider == "resend"

    def test_sms_channel_does_not_support_attachments_or_html(self):
        from app.services.delivery import SMSChannel

        c = SMSChannel()
        assert not c.supports_attachments()
        assert not c.supports_html_body()
        assert c.channel_type == "sms"

    def test_register_channel_replaces_implementation(self):
        """Future native email plugs in via register_channel."""
        from app.services.delivery import (
            EmailChannel,
            get_channel,
            register_channel,
        )

        original = get_channel("email")

        class FakeNative:
            channel_type = "email"
            provider = "native_fake"

            def send(self, request):
                from app.services.delivery import ChannelSendResult
                return ChannelSendResult(success=True, provider=self.provider)

            def supports_attachments(self):
                return True

            def supports_html_body(self):
                return True

        register_channel("email", FakeNative())
        try:
            assert get_channel("email").provider == "native_fake"
        finally:
            register_channel("email", original)


class TestSMSStub:
    def test_sms_send_returns_not_implemented(self):
        from app.services.delivery import (
            ChannelSendRequest,
            Recipient,
            SMSChannel,
        )

        r = ChannelSendRequest(
            recipient=Recipient(type="phone_number", value="+15551234567"),
            subject=None,
            body="Test body",
        )
        result = SMSChannel().send(r)
        assert not result.success
        assert result.error_code == "NOT_IMPLEMENTED"
        assert result.retryable is False
        assert result.provider == "stub_sms"


# ---------------------------------------------------------------------------
# DeliveryService orchestration
# ---------------------------------------------------------------------------


class TestDeliveryServiceCore:
    def _send_params(self, tenant):
        from app.services.delivery import delivery_service

        return delivery_service.SendParams(
            company_id=tenant.id,
            channel="email",
            recipient=delivery_service.RecipientInput(
                type="email_address", value="to@example.com", name="Test Recipient"
            ),
            subject="Hello",
            body="<p>Hi</p>",
            body_html="<p>Hi</p>",
            caller_module="test",
        )

    def test_send_creates_delivery_row(self, db, tenant, admin):
        from app.services.delivery import delivery_service

        params = self._send_params(tenant)
        with patch(
            "app.services.delivery.channels.email_channel.EmailChannel.send"
        ) as mock_send:
            from app.services.delivery.channels.base import ChannelSendResult

            mock_send.return_value = ChannelSendResult(
                success=True,
                provider="resend",
                provider_message_id="msg_abc",
                provider_response={"id": "msg_abc"},
            )
            delivery = delivery_service.send(db, params)
        db.flush()
        assert delivery.id
        assert delivery.company_id == tenant.id
        assert delivery.channel == "email"
        assert delivery.recipient_value == "to@example.com"
        assert delivery.status == "sent"
        assert delivery.provider_message_id == "msg_abc"

    def test_send_with_body_uses_content_directly(self, db, tenant):
        from app.services.delivery import delivery_service

        with patch(
            "app.services.delivery.channels.email_channel.EmailChannel.send"
        ) as mock_send:
            from app.services.delivery.channels.base import ChannelSendResult

            mock_send.return_value = ChannelSendResult(
                success=True, provider="resend", provider_message_id="x"
            )
            delivery = delivery_service.send(db, self._send_params(tenant))
        db.flush()
        # body_preview is the first 500 chars of the body we passed
        assert delivery.body_preview.startswith("<p>Hi</p>")

    def test_send_with_template_renders_content(self, db, tenant):
        from app.services.delivery import delivery_service
        from app.services.delivery.channels.base import ChannelSendResult

        params = delivery_service.SendParams(
            company_id=tenant.id,
            channel="email",
            recipient=delivery_service.RecipientInput(
                type="email_address", value="target@ex.co",
            ),
            template_key="email.statement",
            template_context={
                "customer_name": "Joe",
                "tenant_name": "Wilbert",
                "statement_month": "April 2026",
            },
        )
        captured = {}
        with patch(
            "app.services.delivery.channels.email_channel.EmailChannel.send"
        ) as mock_send:
            def fake_send(req):
                captured["request"] = req
                return ChannelSendResult(
                    success=True, provider="resend",
                    provider_message_id="msg",
                )
            mock_send.side_effect = fake_send
            delivery = delivery_service.send(db, params)
        db.flush()
        # Subject rendered from the template's subject_template
        assert "April 2026" in (delivery.subject or "")
        # Body contains the recipient's name because the template
        # substituted {{ customer_name }}
        assert "Joe" in captured["request"].body_html

    def test_send_handles_failure_and_records_it(self, db, tenant):
        from app.services.delivery import delivery_service
        from app.services.delivery.channels.base import ChannelSendResult

        with patch(
            "app.services.delivery.channels.email_channel.EmailChannel.send"
        ) as mock_send:
            mock_send.return_value = ChannelSendResult(
                success=False, provider="resend",
                error_message="Invalid recipient",
                error_code="ValidationError",
                retryable=False,
            )
            delivery = delivery_service.send(db, self._send_params(tenant))
        db.flush()
        assert delivery.status == "failed"
        assert delivery.error_message == "Invalid recipient"
        assert delivery.failed_at is not None

    def test_sms_returns_rejected_status(self, db, tenant):
        from app.services.delivery import delivery_service

        params = delivery_service.SendParams(
            company_id=tenant.id,
            channel="sms",
            recipient=delivery_service.RecipientInput(
                type="phone_number", value="+15551234567",
            ),
            body="Your appointment is confirmed",
        )
        delivery = delivery_service.send(db, params)
        db.flush()
        assert delivery.status == "rejected"
        assert delivery.error_code == "NOT_IMPLEMENTED"

    def test_send_populates_signature_envelope_linkage(self, db, tenant):
        """Linkage column is populated when caller passes the envelope id."""
        from app.services.delivery import delivery_service
        from app.services.delivery.channels.base import ChannelSendResult

        with patch(
            "app.services.delivery.channels.email_channel.EmailChannel.send"
        ) as mock_send:
            mock_send.return_value = ChannelSendResult(
                success=True, provider="resend", provider_message_id="m",
            )
            delivery = delivery_service.send(
                db,
                delivery_service.SendParams(
                    company_id=tenant.id,
                    channel="email",
                    recipient=delivery_service.RecipientInput(
                        type="email_address", value="to@x",
                    ),
                    body="x",
                    caller_signature_envelope_id="env-123",
                ),
            )
        db.flush()
        assert delivery.caller_signature_envelope_id == "env-123"

    def test_send_requires_template_or_body(self, db, tenant):
        from app.services.delivery import delivery_service

        with pytest.raises(delivery_service.DeliveryError):
            delivery_service.send(
                db,
                delivery_service.SendParams(
                    company_id=tenant.id,
                    channel="email",
                    recipient=delivery_service.RecipientInput(
                        type="email_address", value="to@x",
                    ),
                ),
            )

    def test_send_unknown_channel_raises_delivery_error(self, db, tenant):
        from app.services.delivery import delivery_service

        with pytest.raises(delivery_service.DeliveryError) as exc:
            delivery_service.send(
                db,
                delivery_service.SendParams(
                    company_id=tenant.id,
                    channel="carrier_pigeon",
                    recipient=delivery_service.RecipientInput(
                        type="email_address", value="to@x",
                    ),
                    body="x",
                ),
            )
        assert "Unknown delivery channel" in str(exc.value)


class TestDeliveryServiceRetry:
    def test_retryable_error_increments_count_and_eventually_fails(
        self, db, tenant
    ):
        """Retries happen inline; after max_retries the status=failed."""
        from app.services.delivery import delivery_service
        from app.services.delivery.channels.base import ChannelSendResult

        with patch(
            "app.services.delivery.channels.email_channel.EmailChannel.send"
        ) as mock_send:
            mock_send.return_value = ChannelSendResult(
                success=False, provider="resend",
                error_message="timeout",
                error_code="TimeoutError",
                retryable=True,
            )
            delivery = delivery_service.send(
                db,
                delivery_service.SendParams(
                    company_id=tenant.id,
                    channel="email",
                    recipient=delivery_service.RecipientInput(
                        type="email_address", value="to@x",
                    ),
                    body="x",
                    max_retries=2,
                ),
            )
        db.flush()
        assert delivery.status == "failed"
        # 1 initial + 2 retries = 3 attempts
        assert mock_send.call_count == 3

    def test_non_retryable_error_fails_immediately(self, db, tenant):
        from app.services.delivery import delivery_service
        from app.services.delivery.channels.base import ChannelSendResult

        with patch(
            "app.services.delivery.channels.email_channel.EmailChannel.send"
        ) as mock_send:
            mock_send.return_value = ChannelSendResult(
                success=False, provider="resend",
                error_message="invalid address",
                error_code="BadAddress",
                retryable=False,
            )
            delivery = delivery_service.send(
                db,
                delivery_service.SendParams(
                    company_id=tenant.id,
                    channel="email",
                    recipient=delivery_service.RecipientInput(
                        type="email_address", value="to@x",
                    ),
                    body="x",
                    max_retries=5,
                ),
            )
        db.flush()
        assert delivery.status == "failed"
        # Only one attempt
        assert mock_send.call_count == 1

    def test_retry_then_success(self, db, tenant):
        from app.services.delivery import delivery_service
        from app.services.delivery.channels.base import ChannelSendResult

        attempts = []

        def flaky(req):
            attempts.append(1)
            if len(attempts) < 2:
                return ChannelSendResult(
                    success=False, provider="resend",
                    error_message="timeout",
                    retryable=True,
                )
            return ChannelSendResult(
                success=True, provider="resend",
                provider_message_id="eventually_ok",
            )

        with patch(
            "app.services.delivery.channels.email_channel.EmailChannel.send",
            side_effect=flaky,
        ):
            delivery = delivery_service.send(
                db,
                delivery_service.SendParams(
                    company_id=tenant.id,
                    channel="email",
                    recipient=delivery_service.RecipientInput(
                        type="email_address", value="to@x",
                    ),
                    body="x",
                    max_retries=3,
                ),
            )
        db.flush()
        assert delivery.status == "sent"
        assert delivery.provider_message_id == "eventually_ok"


# ---------------------------------------------------------------------------
# Workflow engine send_document step
# ---------------------------------------------------------------------------


class TestSendDocumentStep:
    def test_execute_send_document_creates_delivery(self, db, tenant):
        """The workflow engine's _execute_send_document calls
        DeliveryService and returns the structured output."""
        from app.services.delivery.channels.base import ChannelSendResult
        from app.services.workflow_engine import _execute_send_document

        # Minimal run stub
        run = MagicMock()
        run.id = "run-abc"
        run.company_id = tenant.id
        run.workflow_id = "wf-1"
        run.trigger_context = {}

        config = {
            "channel": "email",
            "recipient": {
                "type": "email_address",
                "value": "target@example.co",
                "name": "Target",
            },
            "body": "<p>Hello from workflow</p>",
            "subject": "Workflow says hi",
        }

        with patch(
            "app.services.delivery.channels.email_channel.EmailChannel.send"
        ) as mock_send:
            mock_send.return_value = ChannelSendResult(
                success=True, provider="resend",
                provider_message_id="wf-msg-1",
            )
            output = _execute_send_document(db, config, run, "step-1")

        assert output["status"] == "sent"
        assert output["provider_message_id"] == "wf-msg-1"
        assert output["channel"] == "email"
        assert output["recipient"] == "target@example.co"
        assert output["delivery_id"]  # UUID populated

    def test_execute_send_document_populates_workflow_linkage(self, db, tenant):
        from app.models.document_delivery import DocumentDelivery
        from app.services.delivery.channels.base import ChannelSendResult
        from app.services.workflow_engine import _execute_send_document

        run = MagicMock()
        run.id = "run-def"
        run.company_id = tenant.id
        run.workflow_id = "wf-2"
        run.trigger_context = {}

        with patch(
            "app.services.delivery.channels.email_channel.EmailChannel.send"
        ) as mock_send:
            mock_send.return_value = ChannelSendResult(
                success=True, provider="resend", provider_message_id="x",
            )
            output = _execute_send_document(
                db,
                {
                    "channel": "email",
                    "recipient": {"type": "email_address", "value": "a@b.co"},
                    "body": "x",
                },
                run,
                "step-xyz",
            )
        db.flush()
        delivery = (
            db.query(DocumentDelivery)
            .filter_by(id=output["delivery_id"])
            .first()
        )
        assert delivery.caller_workflow_run_id == "run-def"
        assert delivery.caller_workflow_step_id == "step-xyz"
        assert "workflow_engine" in (delivery.caller_module or "")

    def test_execute_send_document_rejects_missing_channel(self, db, tenant):
        from app.services.workflow_engine import _execute_send_document

        run = MagicMock()
        run.id = "r"
        run.company_id = tenant.id
        run.workflow_id = "w"
        run.trigger_context = {}
        with pytest.raises(ValueError) as exc:
            _execute_send_document(
                db,
                {"recipient": {"type": "email_address", "value": "x@y"},
                 "body": "x"},
                run, "s",
            )
        assert "channel" in str(exc.value).lower()

    def test_execute_send_document_rejects_missing_recipient(self, db, tenant):
        from app.services.workflow_engine import _execute_send_document

        run = MagicMock()
        run.id = "r"
        run.company_id = tenant.id
        run.workflow_id = "w"
        run.trigger_context = {}
        with pytest.raises(ValueError):
            _execute_send_document(
                db,
                {"channel": "email", "body": "x"},
                run, "s",
            )


# ---------------------------------------------------------------------------
# Migrated callers
# ---------------------------------------------------------------------------


class TestMigratedEmailCallers:
    def test_send_statement_email_creates_delivery(self, db, tenant):
        from app.models.document_delivery import DocumentDelivery
        from app.services.delivery.channels.base import ChannelSendResult
        from app.services.email_service import email_service

        with patch(
            "app.services.delivery.channels.email_channel.EmailChannel.send"
        ) as mock_send:
            mock_send.return_value = ChannelSendResult(
                success=True, provider="resend", provider_message_id="m",
            )
            result = email_service.send_statement_email(
                customer_email="fh@example.co",
                customer_name="FH Ops",
                tenant_name="Wilbert",
                statement_month="April 2026",
                company_id=tenant.id,
                db=db,
            )
        db.flush()
        assert result["success"]
        # A delivery row was written
        row = (
            db.query(DocumentDelivery)
            .filter_by(recipient_value="fh@example.co")
            .first()
        )
        assert row is not None
        assert row.template_key == "email.statement"
        assert row.caller_module == "email_service.send_statement_email"

    def test_send_collections_email_creates_delivery(self, db, tenant):
        from app.models.document_delivery import DocumentDelivery
        from app.services.delivery.channels.base import ChannelSendResult
        from app.services.email_service import email_service

        with patch(
            "app.services.delivery.channels.email_channel.EmailChannel.send"
        ) as mock_send:
            mock_send.return_value = ChannelSendResult(
                success=True, provider="resend", provider_message_id="m",
            )
            email_service.send_collections_email(
                customer_email="owe@ex.co",
                customer_name="Owed Customer",
                subject="Balance due",
                body="Please remit.",
                tenant_name="Wilbert",
                reply_to_email="ar@wilbert.co",
                company_id=tenant.id,
                db=db,
            )
        db.flush()
        row = (
            db.query(DocumentDelivery)
            .filter_by(recipient_value="owe@ex.co")
            .first()
        )
        assert row is not None
        assert row.template_key == "email.collections"

    def test_send_user_invitation_creates_delivery(self, db, tenant):
        from app.models.document_delivery import DocumentDelivery
        from app.services.delivery.channels.base import ChannelSendResult
        from app.services.email_service import email_service

        with patch(
            "app.services.delivery.channels.email_channel.EmailChannel.send"
        ) as mock_send:
            mock_send.return_value = ChannelSendResult(
                success=True, provider="resend", provider_message_id="m",
            )
            email_service.send_user_invitation(
                email="new@user.co",
                name="New User",
                tenant_name="Wilbert",
                invite_url="https://example.com/invite/xyz",
                company_id=tenant.id,
                db=db,
            )
        db.flush()
        row = (
            db.query(DocumentDelivery)
            .filter_by(recipient_value="new@user.co")
            .first()
        )
        assert row is not None
        assert row.template_key == "email.invitation"

    def test_send_agent_alert_digest_creates_delivery(self, db, tenant):
        from app.models.document_delivery import DocumentDelivery
        from app.services.delivery.channels.base import ChannelSendResult
        from app.services.email_service import email_service

        with patch(
            "app.services.delivery.channels.email_channel.EmailChannel.send"
        ) as mock_send:
            mock_send.return_value = ChannelSendResult(
                success=True, provider="resend", provider_message_id="m",
            )
            email_service.send_agent_alert_digest(
                email="alerts@ex.co",
                tenant_name="Wilbert",
                alerts=[{"title": "T", "summary": "S"}],
                company_id=tenant.id,
                db=db,
            )
        db.flush()
        row = (
            db.query(DocumentDelivery)
            .filter_by(recipient_value="alerts@ex.co")
            .first()
        )
        assert row is not None
        assert row.template_key == "email.alert_digest"

    def test_agent_alert_digest_empty_skipped(self, db, tenant):
        """Empty alerts list short-circuits — no delivery row."""
        from app.models.document_delivery import DocumentDelivery
        from app.services.email_service import email_service

        email_service.send_agent_alert_digest(
            email="alerts@ex.co",
            tenant_name="Wilbert",
            alerts=[],
            company_id=tenant.id,
            db=db,
        )
        db.flush()
        count = db.query(DocumentDelivery).count()
        assert count == 0


class TestSigningNotificationMigration:
    def test_signing_invite_goes_through_delivery_service(self, db, tenant, admin):
        """Signing send_invite routes through DeliveryService with the
        signature envelope linkage column populated."""
        from app.models.document_delivery import DocumentDelivery
        from app.services.delivery.channels.base import ChannelSendResult

        # Build a minimal envelope + party without going through the
        # full service stack
        from app.models.canonical_document import Document
        from app.models.signature import (
            SignatureEnvelope,
            SignatureParty,
        )

        doc = Document(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            document_type="disinterment_release",
            title="Release",
            storage_key=f"tenants/{tenant.id}/documents/rel/v1.pdf",
            mime_type="application/pdf",
            status="rendered",
        )
        db.add(doc)
        db.flush()
        env = SignatureEnvelope(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            document_id=doc.id,
            subject="Sign this",
            description=None,
            routing_type="sequential",
            status="sent",
            document_hash="abc" * 21 + "a",
            created_by_user_id=admin.id,
        )
        db.add(env)
        db.flush()
        party = SignatureParty(
            id=str(uuid.uuid4()),
            envelope_id=env.id,
            signing_order=1,
            role="funeral_home_director",
            display_name="Jane FH",
            email="jane@fh.co",
            signer_token="tok-" + uuid.uuid4().hex,
            status="sent",
        )
        db.add(party)
        db.flush()

        from app.services.signing import notification_service

        with patch(
            "app.services.delivery.channels.email_channel.EmailChannel.send"
        ) as mock_send:
            mock_send.return_value = ChannelSendResult(
                success=True, provider="resend",
                provider_message_id="sig-msg-1",
            )
            notification_service.send_invite(db, env, party)
        db.flush()

        row = (
            db.query(DocumentDelivery)
            .filter_by(recipient_value="jane@fh.co")
            .first()
        )
        assert row is not None
        assert row.caller_signature_envelope_id == env.id
        assert row.template_key == "email.signing_invite"


# ---------------------------------------------------------------------------
# Admin API endpoints
# ---------------------------------------------------------------------------


class TestAdminAPI:
    def test_list_deliveries_tenant_scoped(self, db, tenant, admin):
        from app.api.routes.documents_v2 import list_deliveries
        from app.models.document_delivery import DocumentDelivery

        d = DocumentDelivery(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            channel="email",
            recipient_type="email_address",
            recipient_value="x@y.co",
            status="sent",
            sent_at=datetime.now(timezone.utc),
        )
        db.add(d)
        db.flush()
        rows = list_deliveries(
            channel=None, status_filter=None,
            date_from=None, date_to=None,
            document_id=None, template_key=None,
            recipient_search=None, limit=100, offset=0,
            current_user=admin, db=db,
        )
        assert any(r.id == d.id for r in rows)

    def test_get_delivery_detail(self, db, tenant, admin):
        from app.api.routes.documents_v2 import get_delivery_detail
        from app.models.document_delivery import DocumentDelivery

        d = DocumentDelivery(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            channel="email",
            recipient_type="email_address",
            recipient_value="x@y.co",
            status="sent",
        )
        db.add(d)
        db.flush()
        got = get_delivery_detail(
            delivery_id=d.id, current_user=admin, db=db,
        )
        assert got.id == d.id

    def test_get_delivery_detail_cross_tenant_404(self, db, tenant, admin):
        from fastapi import HTTPException
        from app.api.routes.documents_v2 import get_delivery_detail
        from app.models.company import Company
        from app.models.document_delivery import DocumentDelivery

        other = Company(
            id=str(uuid.uuid4()), name="Other", slug="other", is_active=True,
        )
        db.add(other)
        db.flush()
        d = DocumentDelivery(
            id=str(uuid.uuid4()),
            company_id=other.id,
            channel="email",
            recipient_type="email_address",
            recipient_value="x@y.co",
            status="sent",
        )
        db.add(d)
        db.flush()
        with pytest.raises(HTTPException) as exc:
            get_delivery_detail(
                delivery_id=d.id, current_user=admin, db=db,
            )
        assert exc.value.status_code == 404
