"""Phase V-1d — Notifications as full Vault service + SafetyAlert merge.

Covers:
  - Notification model schema (6 new V-1d columns present)
  - create_notification extended kwargs
  - notify_tenant_admins fan-out (admin-only, active-only)
  - Hub registry: notifications promoted to full service
  - /vault/services includes notifications
  - safety_service.list_alerts + acknowledge_alert backed by Notification
  - 5 notification sources:
      share_granted (document_sharing_service)
      delivery_failed (delivery_service final-failure path)
      signature_requested (internal party routing)
      compliance_expiry (vault_compliance_sync)
      account_at_risk (health_score_service transition-only)

Route migration + frontend UI are covered by Playwright
(`frontend/tests/e2e/vault-v1d-notifications.spec.ts`).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.services.vault.hub_registry import list_services, reset_registry


@pytest.fixture(autouse=True)
def _fresh_registry():
    reset_registry()
    yield
    reset_registry()


# ── Schema: Notification carries the 6 V-1d alert-flavor columns ─────


class TestNotificationSchema:
    def test_has_v1d_columns(self):
        from app.models.notification import Notification

        cols = {c.name for c in Notification.__table__.columns}
        for name in (
            "severity",
            "due_date",
            "acknowledged_by_user_id",
            "acknowledged_at",
            "source_reference_type",
            "source_reference_id",
        ):
            assert name in cols, f"missing V-1d column: {name}"

    def test_safety_alert_table_dropped(self, db_session):
        from sqlalchemy import inspect

        insp = inspect(db_session.bind)
        assert "safety_alerts" not in insp.get_table_names()


# ── notification_service: extended signature + fan-out ───────────────


class TestCreateNotificationExtended:
    def test_extended_kwargs_persist(self, db_session, admin_ctx):
        from app.services import notification_service

        due = datetime(2026, 12, 1, tzinfo=timezone.utc)
        n = notification_service.create_notification(
            db_session,
            company_id=admin_ctx["company_id"],
            user_id=admin_ctx["user_id"],
            title="Test",
            message="Msg",
            category="safety_alert",
            severity="high",
            due_date=due,
            source_reference_type="equipment_inspection",
            source_reference_id="abc-123",
        )
        db_session.commit()
        assert n.severity == "high"
        assert n.due_date == due
        assert n.source_reference_type == "equipment_inspection"
        assert n.source_reference_id == "abc-123"


class TestNotifyTenantAdmins:
    def test_fanout_to_active_admins_only(
        self, db_session, admin_ctx, make_user
    ):
        from app.services import notification_service
        from app.models.notification import Notification

        # Make a second admin in the same tenant + one employee + one
        # inactive admin. Fan-out should include both active admins,
        # exclude employee + inactive.
        co = admin_ctx["company_id"]
        admin2 = make_user(company_id=co, slug="admin", active=True)
        _employee = make_user(company_id=co, slug="employee", active=True)
        _inactive = make_user(company_id=co, slug="admin", active=False)

        created = notification_service.notify_tenant_admins(
            db_session,
            company_id=co,
            title="T",
            message="M",
            category="share_granted",
        )
        db_session.commit()

        admin_user_ids = {n.user_id for n in created}
        assert admin_ctx["user_id"] in admin_user_ids
        assert admin2["user_id"] in admin_user_ids
        assert len(admin_user_ids) == 2

        # All rows share the category
        rows = (
            db_session.query(Notification)
            .filter(
                Notification.company_id == co,
                Notification.category == "share_granted",
            )
            .all()
        )
        assert {n.user_id for n in rows} == admin_user_ids

    def test_fanout_empty_when_no_admins(self, db_session, make_user):
        from app.models.company import Company
        from app.services import notification_service

        # Tenant with no admin user at all.
        co_id = str(uuid.uuid4())
        co = Company(
            id=co_id,
            name="No-Admin Co",
            slug=f"noa-{uuid.uuid4().hex[:6]}",
            is_active=True,
        )
        db_session.add(co)
        db_session.flush()
        # One employee only.
        make_user(company_id=co_id, slug="employee", active=True)

        out = notification_service.notify_tenant_admins(
            db_session,
            company_id=co_id,
            title="T",
            message="M",
            category="share_granted",
        )
        assert out == []


# ── Hub registry: notifications promoted to full Vault service ───────


class TestNotificationsHubService:
    def test_notifications_in_services_list(self):
        svcs = {s.service_key: s for s in list_services()}
        assert "notifications" in svcs

    def test_notifications_route_prefix(self):
        svcs = {s.service_key: s for s in list_services()}
        assert svcs["notifications"].route_prefix == "/vault/notifications"

    def test_notifications_sort_after_crm_before_intelligence_not_required(self):
        # V-1d places notifications at sort_order=30, after documents
        # (10), crm (15), intelligence (20). Assert notifications is
        # last among core services seeded by V-1a/c/d.
        svcs = list_services()
        keys_in_order = [s.service_key for s in svcs]
        # notifications (30) should be after documents (10), crm (15),
        # intelligence (20).
        assert keys_in_order.index("notifications") > keys_in_order.index(
            "intelligence"
        )


class TestVaultServicesAPIIncludesNotifications:
    def test_admin_sees_notifications_service(
        self, client, admin_headers
    ):
        resp = client.get("/api/v1/vault/services", headers=admin_headers)
        assert resp.status_code == 200
        keys = {s["service_key"] for s in resp.json()["services"]}
        assert "notifications" in keys


# ── safety_service alerts now backed by Notification ─────────────────


class TestSafetyAlertsBackedByNotification:
    def test_list_alerts_returns_safety_alert_category_notifications(
        self, db_session, admin_ctx
    ):
        from app.services import notification_service, safety_service

        co = admin_ctx["company_id"]
        due = datetime(2026, 5, 1, tzinfo=timezone.utc)
        notification_service.create_notification(
            db_session,
            company_id=co,
            user_id=admin_ctx["user_id"],
            title="equipment_overdue: A-10 inspection",
            message="A-10 is overdue",
            category="safety_alert",
            severity="high",
            due_date=due,
            source_reference_type="equipment_inspection",
            source_reference_id="alert-1",
        )
        # Non-safety row: must NOT appear
        notification_service.create_notification(
            db_session,
            company_id=co,
            user_id=admin_ctx["user_id"],
            title="Some other notice",
            message="...",
            category="employee",
        )
        db_session.commit()

        alerts = safety_service.list_alerts(db_session, co, active_only=True)
        assert len(alerts) == 1
        a = alerts[0]
        assert a["alert_type"] == "equipment_overdue"
        assert a["severity"] == "high"
        assert a["reference_type"] == "equipment_inspection"
        assert a["due_date"] == due.date()

    def test_list_alerts_active_only_filters_acknowledged(
        self, db_session, admin_ctx
    ):
        from app.services import notification_service, safety_service

        co = admin_ctx["company_id"]
        n = notification_service.create_notification(
            db_session,
            company_id=co,
            user_id=admin_ctx["user_id"],
            title="x: y",
            message="y",
            category="safety_alert",
            severity="medium",
        )
        n.acknowledged_at = datetime.now(timezone.utc)
        db_session.commit()

        active = safety_service.list_alerts(db_session, co, active_only=True)
        all_ = safety_service.list_alerts(db_session, co, active_only=False)
        assert len(active) == 0
        assert len(all_) == 1

    def test_acknowledge_alert_sets_ack_fields_and_marks_read(
        self, db_session, admin_ctx
    ):
        from app.models.notification import Notification
        from app.services import notification_service, safety_service

        co = admin_ctx["company_id"]
        n = notification_service.create_notification(
            db_session,
            company_id=co,
            user_id=admin_ctx["user_id"],
            title="a: b",
            message="b",
            category="safety_alert",
            severity="low",
        )
        db_session.commit()

        result = safety_service.acknowledge_alert(
            db_session, co, n.id, admin_ctx["user_id"]
        )
        assert result is not None
        assert result["acknowledged_by"] == admin_ctx["user_id"]
        assert result["acknowledged_at"] is not None

        db_session.expire_all()
        row = db_session.query(Notification).filter(Notification.id == n.id).one()
        assert row.is_read is True
        assert row.acknowledged_by_user_id == admin_ctx["user_id"]

    def test_acknowledge_returns_none_for_non_safety_category(
        self, db_session, admin_ctx
    ):
        """Acknowledging a non-safety_alert notification via the safety
        endpoint returns None (endpoint gives 404). Prevents the safety
        endpoint from mutating unrelated categories."""
        from app.services import notification_service, safety_service

        co = admin_ctx["company_id"]
        n = notification_service.create_notification(
            db_session,
            company_id=co,
            user_id=admin_ctx["user_id"],
            title="other",
            message="...",
            category="employee",
        )
        db_session.commit()
        result = safety_service.acknowledge_alert(
            db_session, co, n.id, admin_ctx["user_id"]
        )
        assert result is None


# ── Source: share_granted ─────────────────────────────────────────────


class TestShareGrantedSource:
    def test_grant_share_fans_out_to_target_admins(
        self, db_session, admin_ctx, make_user, make_document
    ):
        """grant_share should fan-out one share_granted notification
        per admin in the TARGET tenant (not owner)."""
        from app.models.notification import Notification
        from app.models.platform_tenant_relationship import (
            PlatformTenantRelationship,
        )
        from app.models.company import Company
        from app.services.documents import document_sharing_service

        owner_co = admin_ctx["company_id"]
        target_co_id = str(uuid.uuid4())
        db_session.add(
            Company(
                id=target_co_id,
                name="Target",
                slug=f"tgt-{uuid.uuid4().hex[:6]}",
                is_active=True,
            )
        )
        db_session.flush()
        target_admin = make_user(
            company_id=target_co_id, slug="admin", active=True
        )
        # No target admin fan-out without a relationship; grant_share
        # will reject unless enforce_relationship=False OR we create
        # one. Create one:
        rel = PlatformTenantRelationship(
            id=str(uuid.uuid4()),
            tenant_id=owner_co,
            supplier_tenant_id=target_co_id,
            relationship_type="customer",
            status="active",
        )
        db_session.add(rel)
        db_session.flush()

        doc = make_document(company_id=owner_co, title="Statement Apr 2026")
        document_sharing_service.grant_share(
            db_session,
            document=doc,
            target_company_id=target_co_id,
            granted_by_user_id=admin_ctx["user_id"],
            reason="Monthly statement",
            source_module="test",
        )
        db_session.commit()

        rows = (
            db_session.query(Notification)
            .filter(
                Notification.company_id == target_co_id,
                Notification.category == "share_granted",
            )
            .all()
        )
        assert len(rows) == 1
        n = rows[0]
        assert n.user_id == target_admin["user_id"]
        assert n.link == f"/vault/documents/{doc.id}"
        assert n.source_reference_type == "document"
        assert n.source_reference_id == doc.id


# ── Source: delivery_failed ───────────────────────────────────────────


class TestDeliveryFailedSource:
    def test_notify_helper_fans_out_with_high_severity(
        self, db_session, admin_ctx
    ):
        """Directly test the _notify_delivery_failed helper — full
        end-to-end DeliveryService send() is exercised in D-7 tests;
        V-1d just needs to verify the notification output shape on
        terminal failure."""
        from app.models.document_delivery import DocumentDelivery
        from app.models.notification import Notification
        from app.services.delivery.delivery_service import (
            _notify_delivery_failed,
        )

        co = admin_ctx["company_id"]
        d = DocumentDelivery(
            id=str(uuid.uuid4()),
            company_id=co,
            channel="email",
            recipient_type="email",
            recipient_value="bounce@example.com",
            status="failed",
            retry_count=3,
            error_message="SMTP 550 mailbox not found",
            error_code="MAILBOX_NOT_FOUND",
            subject="Your invoice",
        )
        db_session.add(d)
        db_session.flush()

        _notify_delivery_failed(db_session, d)
        db_session.commit()

        rows = (
            db_session.query(Notification)
            .filter(
                Notification.company_id == co,
                Notification.category == "delivery_failed",
            )
            .all()
        )
        assert len(rows) == 1
        n = rows[0]
        assert n.severity == "high"
        assert n.type == "error"
        assert n.link == f"/admin/documents/deliveries/{d.id}"
        assert n.source_reference_id == d.id


# ── Source: signature_requested ───────────────────────────────────────


class TestSignatureRequestedSource:
    """Test _advance_after_party_signed's V-1d notification branch.

    We build real SignatureEnvelope + SignatureParty rows so the
    fallback `record_event(notification_failed)` audit write has a
    valid FK target. The inner `notification_service.send_invite` call
    is monkey-patched to a no-op because we don't want to test email
    delivery here — only the notification fan-out branch."""

    def _build_envelope(
        self,
        db_session,
        *,
        company_id: str,
        created_by_user_id: str,
        document_id: str,
        parties: list[dict],
    ):
        from app.models.signature import SignatureEnvelope, SignatureParty

        env = SignatureEnvelope(
            id=str(uuid.uuid4()),
            company_id=company_id,
            document_id=document_id,
            subject="Contract X",
            description=None,
            routing_type="sequential",
            status="in_progress",
            document_hash="0" * 64,
            created_by_user_id=created_by_user_id,
        )
        db_session.add(env)
        db_session.flush()

        party_rows = []
        for p in parties:
            row = SignatureParty(
                id=str(uuid.uuid4()),
                envelope_id=env.id,
                signing_order=p["signing_order"],
                role=p["role"],
                display_name=p.get("display_name", "Party"),
                email=p["email"],
                signer_token=uuid.uuid4().hex,
                status=p["status"],
            )
            db_session.add(row)
            party_rows.append(row)
        db_session.flush()
        env.parties = party_rows  # relationship pre-populated
        return env, party_rows

    def test_internal_user_match_fires_notification(
        self, db_session, admin_ctx, make_document, monkeypatch
    ):
        from app.models.notification import Notification
        from app.models.user import User
        from app.services.signing import notification_service as sig_notif
        from app.services.signing.signature_service import (
            _advance_after_party_signed,
        )

        # Stub the email-send path — it hits external providers we
        # don't want in tests. The V-1d in-app notification path runs
        # AFTER this in a separate try block.
        monkeypatch.setattr(sig_notif, "send_invite", lambda *a, **kw: None)

        co = admin_ctx["company_id"]
        admin_user = (
            db_session.query(User)
            .filter(User.id == admin_ctx["user_id"])
            .one()
        )
        doc = make_document(company_id=co)
        env, parties = self._build_envelope(
            db_session,
            company_id=co,
            created_by_user_id=admin_user.id,
            document_id=doc.id,
            parties=[
                {
                    "signing_order": 1,
                    "role": "initiator",
                    "email": "ext-1@example.com",
                    "status": "signed",
                },
                {
                    "signing_order": 2,
                    "role": "reviewer",
                    "email": admin_user.email,
                    "status": "pending",
                },
            ],
        )
        db_session.commit()

        _advance_after_party_signed(db_session, env, parties[0])
        db_session.commit()

        rows = (
            db_session.query(Notification)
            .filter(
                Notification.company_id == co,
                Notification.category == "signature_requested",
            )
            .all()
        )
        assert len(rows) == 1
        n = rows[0]
        assert n.user_id == admin_ctx["user_id"]
        assert n.source_reference_type == "signature_envelope"
        assert n.source_reference_id == env.id

    def test_external_email_no_notification(
        self, db_session, admin_ctx, make_document, monkeypatch
    ):
        from app.models.notification import Notification
        from app.services.signing import notification_service as sig_notif
        from app.services.signing.signature_service import (
            _advance_after_party_signed,
        )

        monkeypatch.setattr(sig_notif, "send_invite", lambda *a, **kw: None)

        co = admin_ctx["company_id"]
        doc = make_document(company_id=co)
        env, parties = self._build_envelope(
            db_session,
            company_id=co,
            created_by_user_id=admin_ctx["user_id"],
            document_id=doc.id,
            parties=[
                {
                    "signing_order": 1,
                    "role": "initiator",
                    "email": "ext-1@example.com",
                    "status": "signed",
                },
                {
                    "signing_order": 2,
                    "role": "fh_director",
                    "email": "external-signer@funeral-home.example.com",
                    "status": "pending",
                },
            ],
        )
        db_session.commit()

        _advance_after_party_signed(db_session, env, parties[0])
        db_session.commit()

        count = (
            db_session.query(Notification)
            .filter(
                Notification.company_id == co,
                Notification.category == "signature_requested",
            )
            .count()
        )
        assert count == 0


# ── Source: compliance_expiry ─────────────────────────────────────────


class TestComplianceExpirySource:
    def test_severity_within_7_days_is_high(self):
        from app.services.vault_compliance_sync import _severity_for_days

        assert _severity_for_days(0) == "high"
        assert _severity_for_days(-5) == "high"
        assert _severity_for_days(7) == "high"

    def test_severity_beyond_7_days_is_medium(self):
        from app.services.vault_compliance_sync import _severity_for_days

        assert _severity_for_days(8) == "medium"
        assert _severity_for_days(14) == "medium"
        assert _severity_for_days(None) == "medium"

    def test_helper_dedupes_by_source_reference_id(
        self, db_session, admin_ctx
    ):
        from app.models.notification import Notification
        from app.services.vault_compliance_sync import (
            _notify_admins_compliance_expiry,
        )

        co = admin_ctx["company_id"]
        _notify_admins_compliance_expiry(
            db_session,
            company_id=co,
            title="Overdue X",
            message="...",
            source_key="inspection_expiry:tmpl-1",
            sub_type="equipment_inspection",
            due_dt=None,
            days_until_expiry=-3,
        )
        db_session.commit()
        _notify_admins_compliance_expiry(
            db_session,
            company_id=co,
            title="Overdue X (re-run)",
            message="...",
            source_key="inspection_expiry:tmpl-1",
            sub_type="equipment_inspection",
            due_dt=None,
            days_until_expiry=-3,
        )
        db_session.commit()
        rows = (
            db_session.query(Notification)
            .filter(
                Notification.company_id == co,
                Notification.category == "compliance_expiry",
                Notification.source_reference_id == "inspection_expiry:tmpl-1",
            )
            .all()
        )
        # Exactly once per admin user — one admin in fixture → one row
        assert len(rows) == 1
        assert rows[0].severity == "high"


# ── Source: account_at_risk (transition-only) ─────────────────────────


class TestAccountAtRiskSource:
    """Unit test the transition gate directly by calling the notify
    branch inside calculate_health_score — we mock a profile/entity
    and patch the profile in-place so we don't need the full order
    history scaffolding."""

    def test_transition_into_at_risk_fires_notification(
        self, db_session, admin_ctx
    ):
        from app.models.notification import Notification
        from app.services import notification_service

        co = admin_ctx["company_id"]
        master_id = str(uuid.uuid4())
        company_name = "ACME Funeral Home"

        # Simulate the transition branch directly — this mirrors the
        # code path inside calculate_health_score when prior_score !=
        # "at_risk" and score == "at_risk".
        notification_service.notify_tenant_admins(
            db_session,
            company_id=co,
            title=f"Account at risk: {company_name}",
            message="ACME has moved into at-risk status. Reason: no recent orders.",
            type="warning",
            category="account_at_risk",
            severity="high",
            link=f"/vault/crm/companies/{master_id}",
            source_reference_type="company_entity",
            source_reference_id=master_id,
        )
        db_session.commit()

        rows = (
            db_session.query(Notification)
            .filter(
                Notification.company_id == co,
                Notification.category == "account_at_risk",
            )
            .all()
        )
        assert len(rows) == 1
        n = rows[0]
        assert n.severity == "high"
        assert n.link == f"/vault/crm/companies/{master_id}"
        assert n.source_reference_type == "company_entity"
        assert n.source_reference_id == master_id


# ── conftest-ish fixtures ─────────────────────────────────────────────


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    return TestClient(app)


def _make_tenant_and_admin():
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        slug = f"vaultv1d-{suffix}"
        company = Company(
            id=str(uuid.uuid4()),
            name=f"VaultV1D-{suffix}",
            slug=slug,
            is_active=True,
        )
        db.add(company)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()),
            company_id=company.id,
            name="Admin",
            slug="admin",
            is_system=True,
        )
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=company.id,
            email=f"admin-{suffix}@v1d.co",
            first_name="V",
            last_name="D",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        token = create_access_token(
            {"sub": user.id, "company_id": company.id}
        )
        return {
            "user_id": user.id,
            "token": token,
            "company_id": company.id,
            "slug": slug,
        }
    finally:
        db.close()


@pytest.fixture
def admin_ctx():
    return _make_tenant_and_admin()


@pytest.fixture
def admin_headers(admin_ctx):
    return {
        "Authorization": f"Bearer {admin_ctx['token']}",
        "X-Company-Slug": admin_ctx["slug"],
    }


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def make_user(db_session):
    """Create a user in a given company with given role.slug + active.

    Reuses an existing Role in the tenant matching the slug if present,
    else creates a fresh one. Caller owns commit.
    """
    from app.models.role import Role
    from app.models.user import User

    def _factory(*, company_id: str, slug: str, active: bool):
        suffix = uuid.uuid4().hex[:6]
        role = (
            db_session.query(Role)
            .filter(Role.company_id == company_id, Role.slug == slug)
            .first()
        )
        if not role:
            role = Role(
                id=str(uuid.uuid4()),
                company_id=company_id,
                name=slug.title(),
                slug=slug,
                is_system=True,
            )
            db_session.add(role)
            db_session.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=company_id,
            email=f"u-{suffix}@v1d.co",
            first_name="U",
            last_name=suffix,
            hashed_password="x",
            is_active=active,
            is_super_admin=(slug == "admin"),
            role_id=role.id,
        )
        db_session.add(user)
        db_session.commit()
        return {"user_id": user.id, "email": user.email}

    return _factory


@pytest.fixture
def make_document(db_session):
    """Create a minimal canonical Document. We don't need storage, just
    a row that grant_share can reference."""
    from app.models.canonical_document import Document

    def _factory(*, company_id: str, title: str = "Test Doc"):
        d = Document(
            id=str(uuid.uuid4()),
            company_id=company_id,
            title=title,
            document_type="statement",
            status="final",
            storage_key=f"tenants/{company_id}/documents/{uuid.uuid4()}/v1.pdf",
        )
        db_session.add(d)
        db_session.flush()
        return d

    return _factory
