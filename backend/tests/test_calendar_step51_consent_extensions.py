"""Phase W-4b Layer 1 Calendar Step 5.1 — PTR consent extension tests.

Coverage matrix per Q8 confirmed pre-build (~15 backend tests
consolidated into a single file with 5 test classes for fixture
DRY-ness — same discipline as Calendar Step 5):

  Section 1 — managed email template seed (3 tests):
    - fresh seed creates template + v1 active
    - re-run is noop_matched (idempotent)
    - variable_schema declares canonical Jinja vars

  Section 2 — ptr_consent_service email integration (5 tests):
    - send_email defaults to False (in-app notify only, no email)
    - send_email=True + admins resolved → DocumentDelivery rows created
      (one per admin per Q2)
    - email send failure does NOT block consent state mutation OR
      in-app notify (best-effort discipline preserved)
    - DocumentDelivery.metadata_json carries relationship_id +
      caller_module per Q7 audit linkage discipline
    - send_email=True with no admins → no rows; consent + in-app
      notify continue normally

  Section 3 — calendar_consent_pending widget data (4 tests):
    - empty payload when no PTR relationships exist
    - empty payload when PTRs exist but none in pending_inbound
    - populated payload with pending_inbound row → count + top_requester
    - tenant isolation: cross-tenant PTRs do NOT surface

  Section 4 — widget endpoint + registry (2 tests):
    - widget definition seeded with canonical shape
    - GET /widget-data/calendar-consent-pending returns canonical shape

  Section 5 — end-to-end integration (1 test):
    - request_upgrade(send_email=True) full flow: state mutation
      + audit log + in-app notify + email DocumentDelivery rows
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _make_tenant(db_session, *, name_prefix="S51"):
    from app.models import Company

    co = Company(
        id=str(uuid.uuid4()),
        name=f"{name_prefix} {uuid.uuid4().hex[:8]}",
        slug=f"s51{uuid.uuid4().hex[:8]}",
        vertical="manufacturing",
        is_active=True,
    )
    db_session.add(co)
    db_session.flush()
    return co


def _make_admin(db_session, tenant, *, email_suffix=None, is_super_admin=False):
    """Make an admin user. Reuses existing admin role for the tenant if
    one exists — UNIQUE on (slug, company_id) prevents double-create."""
    from app.models import Role, User

    role = (
        db_session.query(Role)
        .filter(Role.company_id == tenant.id, Role.slug == "admin")
        .first()
    )
    if role is None:
        role = Role(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            name="Admin",
            slug="admin",
            is_system=True,
        )
        db_session.add(role)
        db_session.flush()
    user = User(
        id=str(uuid.uuid4()),
        email=email_suffix
        or f"a-{uuid.uuid4().hex[:8]}@s51.test",
        hashed_password="x",
        first_name="Admin",
        last_name="User",
        company_id=tenant.id,
        role_id=role.id,
        is_active=True,
        is_super_admin=is_super_admin,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _make_ptr_pair(
    db_session,
    tenant_a,
    tenant_b,
    *,
    relationship_type="calendar_partner",
    forward_consent="free_busy_only",
    reverse_consent="free_busy_only",
):
    from app.models.platform_tenant_relationship import PlatformTenantRelationship

    forward = PlatformTenantRelationship(
        id=str(uuid.uuid4()),
        tenant_id=tenant_a.id,
        supplier_tenant_id=tenant_b.id,
        relationship_type=relationship_type,
        status="active",
        calendar_freebusy_consent=forward_consent,
    )
    db_session.add(forward)
    db_session.flush()
    reverse = PlatformTenantRelationship(
        id=str(uuid.uuid4()),
        tenant_id=tenant_b.id,
        supplier_tenant_id=tenant_a.id,
        relationship_type=relationship_type,
        status="active",
        calendar_freebusy_consent=reverse_consent,
    )
    db_session.add(reverse)
    db_session.flush()
    return forward, reverse


def _auth_headers(user, tenant):
    from app.core.security import create_access_token

    token = create_access_token({"sub": user.id, "company_id": tenant.id})
    return {
        "Authorization": f"Bearer {token}",
        "X-Company-Slug": tenant.slug,
    }


# ─────────────────────────────────────────────────────────────────────
# Section 1 — Managed email template seed
# ─────────────────────────────────────────────────────────────────────


class TestEmailTemplateSeed:
    def test_fresh_seed_creates_template_and_v1_active(self, db_session):
        """First run on a clean platform creates the template + v1 active.

        Pre-condition for this test: clear any pre-existing seeded row
        (the seed script runs idempotently in dev DB; we want to
        observe the fresh-install branch in isolation).
        """
        from app.models.document_template import (
            DocumentTemplate,
            DocumentTemplateVersion,
        )
        from scripts.seed_calendar_step51_email_template import _seed_template

        # Defensive cleanup — soft-delete any existing platform row so
        # the test exercises the fresh-install branch.
        existing = (
            db_session.query(DocumentTemplate)
            .filter(
                DocumentTemplate.company_id.is_(None),
                DocumentTemplate.template_key
                == "email.calendar_consent_upgrade_request",
                DocumentTemplate.deleted_at.is_(None),
            )
            .first()
        )
        if existing is not None:
            db_session.query(DocumentTemplateVersion).filter(
                DocumentTemplateVersion.template_id == existing.id
            ).delete()
            db_session.delete(existing)
            db_session.commit()

        counters = _seed_template(db_session)

        assert counters["created"] == 1
        assert counters["noop_matched"] == 0
        assert counters["platform_update"] == 0
        assert counters["skipped_customized"] == 0

        template = (
            db_session.query(DocumentTemplate)
            .filter(
                DocumentTemplate.company_id.is_(None),
                DocumentTemplate.template_key
                == "email.calendar_consent_upgrade_request",
                DocumentTemplate.deleted_at.is_(None),
            )
            .first()
        )
        assert template is not None
        assert template.document_type == "email"
        assert template.output_format == "html"
        versions = (
            db_session.query(DocumentTemplateVersion)
            .filter(DocumentTemplateVersion.template_id == template.id)
            .all()
        )
        assert len(versions) == 1
        assert versions[0].status == "active"
        assert versions[0].version_number == 1
        assert template.current_version_id == versions[0].id

    def test_rerun_is_noop_matched(self, db_session):
        """Second run after fresh seed produces noop_matched=1."""
        from scripts.seed_calendar_step51_email_template import _seed_template

        # Ensure first run completes
        _seed_template(db_session)
        # Second run — content matches → noop
        counters = _seed_template(db_session)
        assert counters["created"] == 0
        assert counters["noop_matched"] == 1
        assert counters["platform_update"] == 0
        assert counters["skipped_customized"] == 0

    def test_variable_schema_declares_canonical_jinja_vars(self, db_session):
        """Every required Jinja var per build prompt is declared in
        variable_schema. Required: requesting_tenant_name +
        partner_tenant_name + recipient_first_name + consent_upgrade_url +
        relationship_type. Optional: expires_in_copy.
        """
        from app.models.document_template import (
            DocumentTemplate,
            DocumentTemplateVersion,
        )
        from scripts.seed_calendar_step51_email_template import _seed_template

        _seed_template(db_session)
        template = (
            db_session.query(DocumentTemplate)
            .filter(
                DocumentTemplate.company_id.is_(None),
                DocumentTemplate.template_key
                == "email.calendar_consent_upgrade_request",
                DocumentTemplate.deleted_at.is_(None),
            )
            .first()
        )
        version = (
            db_session.query(DocumentTemplateVersion)
            .filter(
                DocumentTemplateVersion.template_id == template.id,
                DocumentTemplateVersion.status == "active",
            )
            .first()
        )
        schema = version.variable_schema
        assert schema["requesting_tenant_name"]["required"] is True
        assert schema["partner_tenant_name"]["required"] is True
        assert schema["recipient_first_name"]["required"] is True
        assert schema["consent_upgrade_url"]["required"] is True
        assert schema["relationship_type"]["required"] is True
        assert schema["expires_in_copy"]["required"] is False
        # Subject ≤120 chars per email canon
        assert len(version.subject_template) <= 120


# ─────────────────────────────────────────────────────────────────────
# Section 2 — ptr_consent_service email integration
# ─────────────────────────────────────────────────────────────────────


class TestPtrConsentEmailIntegration:
    def _ensure_template_seeded(self, db_session):
        from scripts.seed_calendar_step51_email_template import _seed_template

        _seed_template(db_session)

    def test_send_email_default_off_no_delivery_rows(self, db_session):
        """When send_email is omitted, no DocumentDelivery rows are
        created. In-app notify still fires (Step 4.1 contract)."""
        from app.models.document_delivery import DocumentDelivery
        from app.services.calendar.ptr_consent_service import request_upgrade

        self._ensure_template_seeded(db_session)
        a = _make_tenant(db_session)
        b = _make_tenant(db_session)
        admin_a = _make_admin(db_session, a)
        _make_admin(db_session, b)  # partner admin
        forward, _ = _make_ptr_pair(db_session, a, b)
        db_session.commit()

        before = (
            db_session.query(DocumentDelivery)
            .filter(
                DocumentDelivery.template_key
                == "email.calendar_consent_upgrade_request"
            )
            .count()
        )
        # Default send_email=False
        request_upgrade(
            db_session,
            requesting_tenant_id=a.id,
            relationship_id=forward.id,
            requested_by_user_id=admin_a.id,
        )
        db_session.commit()
        after = (
            db_session.query(DocumentDelivery)
            .filter(
                DocumentDelivery.template_key
                == "email.calendar_consent_upgrade_request"
            )
            .count()
        )
        assert before == after, (
            "send_email default-off must NOT create any DocumentDelivery rows"
        )

    def test_send_email_true_creates_per_admin_delivery_rows(
        self, db_session
    ):
        """One DocumentDelivery row per partner admin per Q2."""
        from app.models.document_delivery import DocumentDelivery
        from app.services.calendar.ptr_consent_service import request_upgrade

        self._ensure_template_seeded(db_session)
        a = _make_tenant(db_session)
        b = _make_tenant(db_session)
        admin_a = _make_admin(db_session, a)
        # 2 admins on partner side → 2 DocumentDelivery rows
        _make_admin(db_session, b, email_suffix="b1@s51.test")
        _make_admin(db_session, b, email_suffix="b2@s51.test")
        forward, _ = _make_ptr_pair(db_session, a, b)
        db_session.commit()

        request_upgrade(
            db_session,
            requesting_tenant_id=a.id,
            relationship_id=forward.id,
            requested_by_user_id=admin_a.id,
            send_email=True,
        )
        db_session.commit()

        rows = (
            db_session.query(DocumentDelivery)
            .filter(
                DocumentDelivery.template_key
                == "email.calendar_consent_upgrade_request",
                DocumentDelivery.company_id == b.id,
            )
            .all()
        )
        # Per Q2: per-recipient DocumentDelivery (NOT BCC blast)
        assert len(rows) == 2
        recipients = sorted([r.recipient_value for r in rows])
        assert recipients == ["b1@s51.test", "b2@s51.test"]
        # Phase D-9 mandatory threading: company_id=partner tenant
        assert all(r.company_id == b.id for r in rows)

    def test_email_failure_does_not_block_consent_or_notify(
        self, db_session, monkeypatch
    ):
        """Best-effort discipline: simulate delivery_service failure;
        consent state still flips + in-app notify still fires."""
        from app.models import Notification
        from app.models.platform_tenant_relationship import (
            PlatformTenantRelationship,
        )
        from app.services.calendar import ptr_consent_service
        from app.services.calendar.ptr_consent_service import request_upgrade
        from app.services.delivery import delivery_service

        self._ensure_template_seeded(db_session)
        a = _make_tenant(db_session)
        b = _make_tenant(db_session)
        admin_a = _make_admin(db_session, a)
        _make_admin(db_session, b)
        forward, _ = _make_ptr_pair(db_session, a, b)
        db_session.commit()

        # Simulate delivery_service.send_email_with_template raising —
        # best-effort discipline must isolate this failure.
        def _boom(*args, **kwargs):
            raise RuntimeError("simulated SMTP outage")

        monkeypatch.setattr(
            delivery_service, "send_email_with_template", _boom
        )

        # Should NOT raise even though email layer is broken
        request_upgrade(
            db_session,
            requesting_tenant_id=a.id,
            relationship_id=forward.id,
            requested_by_user_id=admin_a.id,
            send_email=True,
        )
        db_session.commit()

        # Consent state: flipped to full_details
        forward_row = (
            db_session.query(PlatformTenantRelationship)
            .filter(PlatformTenantRelationship.id == forward.id)
            .first()
        )
        assert forward_row.calendar_freebusy_consent == "full_details"

        # In-app notify: at least one Notification row for partner admin
        partner_notifs = (
            db_session.query(Notification)
            .filter(
                Notification.company_id == b.id,
                Notification.category == "calendar_consent_upgrade_request",
            )
            .all()
        )
        assert len(partner_notifs) >= 1

    def test_metadata_carries_relationship_id_and_caller_module(
        self, db_session
    ):
        """Per Q7: DocumentDelivery.metadata_json JSONB carries
        relationship_id + caller_module for audit linkage."""
        from app.models.document_delivery import DocumentDelivery
        from app.services.calendar.ptr_consent_service import request_upgrade

        self._ensure_template_seeded(db_session)
        a = _make_tenant(db_session)
        b = _make_tenant(db_session)
        admin_a = _make_admin(db_session, a)
        _make_admin(db_session, b)
        forward, _ = _make_ptr_pair(db_session, a, b)
        db_session.commit()

        request_upgrade(
            db_session,
            requesting_tenant_id=a.id,
            relationship_id=forward.id,
            requested_by_user_id=admin_a.id,
            send_email=True,
        )
        db_session.commit()

        row = (
            db_session.query(DocumentDelivery)
            .filter(
                DocumentDelivery.template_key
                == "email.calendar_consent_upgrade_request",
                DocumentDelivery.company_id == b.id,
            )
            .first()
        )
        assert row is not None
        assert (
            row.caller_module == "ptr_consent_service.request_upgrade_email"
        )
        assert row.metadata_json is not None
        assert row.metadata_json.get("relationship_id") == forward.id
        assert row.metadata_json.get("requesting_tenant_id") == a.id
        assert row.metadata_json.get("partner_tenant_id") == b.id
        assert (
            row.metadata_json.get("step_5_1_category")
            == "calendar_consent_upgrade_request"
        )

    def test_no_admins_no_rows_consent_still_succeeds(self, db_session):
        """Partner with no active admins: no DocumentDelivery rows
        created; consent state still flips."""
        from app.models.document_delivery import DocumentDelivery
        from app.models.platform_tenant_relationship import (
            PlatformTenantRelationship,
        )
        from app.services.calendar.ptr_consent_service import request_upgrade

        self._ensure_template_seeded(db_session)
        a = _make_tenant(db_session)
        b = _make_tenant(db_session)
        admin_a = _make_admin(db_session, a)
        # Intentionally NOT creating an admin on tenant b
        forward, _ = _make_ptr_pair(db_session, a, b)
        db_session.commit()

        request_upgrade(
            db_session,
            requesting_tenant_id=a.id,
            relationship_id=forward.id,
            requested_by_user_id=admin_a.id,
            send_email=True,
        )
        db_session.commit()

        rows = (
            db_session.query(DocumentDelivery)
            .filter(
                DocumentDelivery.template_key
                == "email.calendar_consent_upgrade_request",
                DocumentDelivery.company_id == b.id,
            )
            .all()
        )
        assert rows == []
        # Consent still flipped despite no admin recipients
        forward_row = (
            db_session.query(PlatformTenantRelationship)
            .filter(PlatformTenantRelationship.id == forward.id)
            .first()
        )
        assert forward_row.calendar_freebusy_consent == "full_details"


# ─────────────────────────────────────────────────────────────────────
# Section 3 — calendar_consent_pending widget data
# ─────────────────────────────────────────────────────────────────────


class TestConsentPendingWidget:
    def test_empty_payload_no_relationships(self, db_session):
        from app.services.widgets.calendar_consent_pending_service import (
            get_calendar_consent_pending,
        )

        a = _make_tenant(db_session)
        user_a = _make_admin(db_session, a)
        db_session.commit()

        payload = get_calendar_consent_pending(db_session, user=user_a)
        assert payload["has_pending"] is False
        assert payload["pending_consent_count"] == 0
        assert payload["target_relationship_id"] is None

    def test_empty_payload_no_pending_inbound(self, db_session):
        """PTR exists but state is 'default' (both free_busy_only)."""
        from app.services.widgets.calendar_consent_pending_service import (
            get_calendar_consent_pending,
        )

        a = _make_tenant(db_session)
        b = _make_tenant(db_session)
        user_a = _make_admin(db_session, a)
        # Default state pair: both 'free_busy_only' → state='default'
        _make_ptr_pair(db_session, a, b)
        db_session.commit()

        payload = get_calendar_consent_pending(db_session, user=user_a)
        assert payload["has_pending"] is False
        assert payload["pending_consent_count"] == 0

    def test_populated_with_pending_inbound(self, db_session):
        """When state == 'pending_inbound', widget surfaces count + top
        requester. Partner has consented to full_details; this side
        hasn't yet."""
        from app.services.widgets.calendar_consent_pending_service import (
            get_calendar_consent_pending,
        )

        a = _make_tenant(db_session, name_prefix="MyCo")
        b = _make_tenant(db_session, name_prefix="HopkinsFH")
        user_a = _make_admin(db_session, a)
        # forward (a→b) is free_busy_only; reverse (b→a) is full_details
        # → for caller a: this_side=free_busy_only, partner_side=full_details
        # → state='pending_inbound'
        _make_ptr_pair(
            db_session,
            a,
            b,
            forward_consent="free_busy_only",
            reverse_consent="full_details",
        )
        db_session.commit()

        payload = get_calendar_consent_pending(db_session, user=user_a)
        assert payload["has_pending"] is True
        assert payload["pending_consent_count"] == 1
        # Single pending → target_relationship_id set for direct-link
        assert payload["target_relationship_id"] is not None
        # top_requester_name is the partner tenant's name (resolved via
        # list_partner_consent_states from the partner Company row)
        assert payload["top_requester_name"] is not None
        assert "HopkinsFH" in payload["top_requester_name"]

    def test_tenant_isolation_cross_tenant_ptr_does_not_surface(
        self, db_session
    ):
        """A pending_inbound PTR for tenant b does NOT surface on
        tenant a's widget — list_partner_consent_states tenant-scopes."""
        from app.services.widgets.calendar_consent_pending_service import (
            get_calendar_consent_pending,
        )

        a = _make_tenant(db_session)
        b = _make_tenant(db_session)
        c = _make_tenant(db_session)
        user_a = _make_admin(db_session, a)
        # b ↔ c PTR with pending_inbound on b's side — must NOT surface
        # on tenant a's widget.
        _make_ptr_pair(
            db_session,
            b,
            c,
            forward_consent="free_busy_only",
            reverse_consent="full_details",
        )
        db_session.commit()

        payload = get_calendar_consent_pending(db_session, user=user_a)
        assert payload["has_pending"] is False
        assert payload["pending_consent_count"] == 0


# ─────────────────────────────────────────────────────────────────────
# Section 4 — Widget endpoint + registry
# ─────────────────────────────────────────────────────────────────────


class TestWidgetEndpointAndRegistry:
    def test_widget_definition_seeded_with_canonical_shape(self, db_session):
        from app.models.widget_definition import WidgetDefinition
        from app.services.widgets.widget_registry import (
            seed_widget_definitions,
        )

        seed_widget_definitions(db_session)
        db_session.commit()

        wd = (
            db_session.query(WidgetDefinition)
            .filter(
                WidgetDefinition.widget_id == "calendar_consent_pending"
            )
            .first()
        )
        assert wd is not None
        assert wd.icon == "UserCheck"
        # Cross-vertical default-ship per Q4
        assert "pulse_grid" in (wd.supported_surfaces or [])
        assert "spaces_pin" in (wd.supported_surfaces or [])
        assert "dashboard_grid" in (wd.supported_surfaces or [])

    def test_endpoint_returns_canonical_shape(self, db_session, client):
        a = _make_tenant(db_session)
        user_a = _make_admin(db_session, a, is_super_admin=True)
        db_session.commit()

        r = client.get(
            "/api/v1/widget-data/calendar-consent-pending",
            headers=_auth_headers(user_a, a),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # Canonical shape per get_calendar_consent_pending
        assert "has_pending" in body
        assert "pending_consent_count" in body
        assert "top_requester_name" in body
        assert "top_requester_tenant_label" in body
        assert "target_relationship_id" in body
        # No PTR seeded → empty payload
        assert body["has_pending"] is False
        assert body["pending_consent_count"] == 0


# ─────────────────────────────────────────────────────────────────────
# Section 5 — End-to-end integration
# ─────────────────────────────────────────────────────────────────────


class TestEndToEndIntegration:
    def test_request_upgrade_with_send_email_full_flow(self, db_session):
        """End-to-end: request_upgrade(send_email=True) flips state +
        writes audit log + creates in-app notify + creates per-admin
        DocumentDelivery rows."""
        from app.models import Notification
        from app.models.calendar_primitive import CalendarAuditLog
        from app.models.document_delivery import DocumentDelivery
        from app.models.platform_tenant_relationship import (
            PlatformTenantRelationship,
        )
        from app.services.calendar.ptr_consent_service import request_upgrade
        from scripts.seed_calendar_step51_email_template import _seed_template

        _seed_template(db_session)
        a = _make_tenant(db_session, name_prefix="Sunny")
        b = _make_tenant(db_session, name_prefix="Hopkins")
        admin_a = _make_admin(db_session, a)
        _make_admin(db_session, b, email_suffix="b1@s51.test")
        _make_admin(db_session, b, email_suffix="b2@s51.test")
        forward, _ = _make_ptr_pair(db_session, a, b)
        db_session.commit()

        result = request_upgrade(
            db_session,
            requesting_tenant_id=a.id,
            relationship_id=forward.id,
            requested_by_user_id=admin_a.id,
            send_email=True,
        )
        db_session.commit()

        # Result shape
        assert result["relationship_id"] == forward.id
        assert result["partner_tenant_id"] == b.id
        assert result["new_state"] == "pending_outbound"

        # 1. State mutation
        forward_row = (
            db_session.query(PlatformTenantRelationship)
            .filter(PlatformTenantRelationship.id == forward.id)
            .first()
        )
        assert forward_row.calendar_freebusy_consent == "full_details"
        assert forward_row.calendar_freebusy_consent_updated_by == admin_a.id

        # 2. Audit log: caller-side row written
        audit = (
            db_session.query(CalendarAuditLog)
            .filter(
                CalendarAuditLog.tenant_id == a.id,
                CalendarAuditLog.action == "consent_upgrade_requested",
                CalendarAuditLog.entity_id == forward.id,
            )
            .first()
        )
        assert audit is not None

        # 3. In-app notify: 2 partner-admin Notification rows
        partner_notifs = (
            db_session.query(Notification)
            .filter(
                Notification.company_id == b.id,
                Notification.category == "calendar_consent_upgrade_request",
            )
            .all()
        )
        assert len(partner_notifs) == 2

        # 4. Email DocumentDelivery: 2 per-admin rows with metadata
        deliveries = (
            db_session.query(DocumentDelivery)
            .filter(
                DocumentDelivery.template_key
                == "email.calendar_consent_upgrade_request",
                DocumentDelivery.company_id == b.id,
            )
            .all()
        )
        assert len(deliveries) == 2
        for d in deliveries:
            assert d.metadata_json is not None
            assert d.metadata_json["relationship_id"] == forward.id
            assert (
                d.caller_module
                == "ptr_consent_service.request_upgrade_email"
            )
