"""Calendar Step 4.1 — PTR consent state machine tests.

Per §3.26.16.6 + §3.26.16.14 + §3.26.11.10 + Q1-Q6 confirmed pre-build:

  - State machine × 6 (Q6 coverage strategy): default → pending_outbound,
    pending_inbound → active, active → revoked from each side, pending_outbound
    → revoked (cancellation), resolve_consent_state edge cases
  - Notifications × 3: request triggers partner-admin notify; accept triggers
    requester-admin notify; revoke triggers partner-admin notify
  - Audit × 2: per-side audit log discipline (request writes single side;
    accept/revoke writes both sides per §3.26.11.10 joint event canonical)
  - API × 4: list / request / accept / revoke endpoints
  - Latent-bug regression × 1: single-row consent_levels does NOT upgrade to
    bilateral full_details in freebusy_service (Q2 latent privacy bug fix)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.database import SessionLocal
from app.models import Company, Notification, Role, User
from app.models.calendar_primitive import (
    CalendarAccount,
    CalendarAuditLog,
)
from app.models.platform_tenant_relationship import PlatformTenantRelationship
from app.services.calendar import ptr_consent_service
from app.services.calendar.ptr_consent_service import (
    PtrConsentInvalidTransition,
    PtrConsentNotFound,
    resolve_consent_state,
)
from app.services.calendar.freebusy_service import (
    CrossTenantConsentDenied,
    query_cross_tenant_freebusy,
)


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def _make_tenant(db_session, *, name_prefix="S41"):
    co = Company(
        id=str(uuid.uuid4()),
        name=f"{name_prefix} {uuid.uuid4().hex[:8]}",
        slug=f"s41{uuid.uuid4().hex[:8]}",
        vertical="manufacturing",
    )
    db_session.add(co)
    db_session.flush()
    return co


def _make_admin(db_session, tenant, *, slug="admin"):
    role = Role(
        id=str(uuid.uuid4()),
        company_id=tenant.id,
        name="Admin" if slug == "admin" else slug,
        slug=slug,
        is_system=True,
    )
    db_session.add(role)
    db_session.flush()
    user = User(
        id=str(uuid.uuid4()),
        email=f"u-{uuid.uuid4().hex[:8]}@s41.test",
        hashed_password="x",
        first_name="A",
        last_name="U",
        company_id=tenant.id,
        role_id=role.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _make_relationship_pair(
    db_session,
    tenant_a: Company,
    tenant_b: Company,
    *,
    relationship_type: str = "calendar_partner",
    forward_consent: str = "free_busy_only",
    reverse_consent: str = "free_busy_only",
    create_reverse: bool = True,
) -> tuple[PlatformTenantRelationship, PlatformTenantRelationship | None]:
    """Create a bidirectional PTR pair with caller-supplied consent values."""
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

    reverse = None
    if create_reverse:
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


# ─────────────────────────────────────────────────────────────────────
# 1. State resolver — edge cases
# ─────────────────────────────────────────────────────────────────────


class TestResolveConsentState:
    def test_both_default_resolves_default(self, db_session):
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        forward, reverse = _make_relationship_pair(db_session, a, b)
        assert resolve_consent_state(forward, reverse) == "default"

    def test_this_full_partner_default_pending_outbound(self, db_session):
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        forward, reverse = _make_relationship_pair(
            db_session, a, b,
            forward_consent="full_details",
            reverse_consent="free_busy_only",
        )
        assert resolve_consent_state(forward, reverse) == "pending_outbound"

    def test_this_default_partner_full_pending_inbound(self, db_session):
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        forward, reverse = _make_relationship_pair(
            db_session, a, b,
            forward_consent="free_busy_only",
            reverse_consent="full_details",
        )
        assert resolve_consent_state(forward, reverse) == "pending_inbound"

    def test_both_full_resolves_active(self, db_session):
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        forward, reverse = _make_relationship_pair(
            db_session, a, b,
            forward_consent="full_details",
            reverse_consent="full_details",
        )
        assert resolve_consent_state(forward, reverse) == "active"

    def test_missing_reverse_treats_as_default(self, db_session):
        # Per Q2 privacy-default discipline: missing reverse = treat as
        # free_busy_only.
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        forward, _ = _make_relationship_pair(
            db_session, a, b,
            forward_consent="full_details",
            create_reverse=False,
        )
        # Forward=full, reverse=missing → pending_outbound
        # (caller has stated consent; partner is implicitly free_busy_only)
        assert resolve_consent_state(forward, None) == "pending_outbound"


# ─────────────────────────────────────────────────────────────────────
# 2. State machine transitions
# ─────────────────────────────────────────────────────────────────────


class TestStateMachine:
    def test_request_default_to_pending_outbound(self, db_session):
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_admin(db_session, a)
        forward, reverse = _make_relationship_pair(db_session, a, b)

        result = ptr_consent_service.request_upgrade(
            db_session,
            requesting_tenant_id=a.id,
            relationship_id=forward.id,
            requested_by_user_id=user_a.id,
        )
        assert result["prior_state"] == "default"
        assert result["new_state"] == "pending_outbound"
        db_session.refresh(forward)
        assert forward.calendar_freebusy_consent == "full_details"
        assert forward.calendar_freebusy_consent_updated_by == user_a.id
        assert forward.calendar_freebusy_consent_updated_at is not None

    def test_accept_pending_inbound_to_active(self, db_session):
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_admin(db_session, a)
        # Partner (b) has already requested upgrade → reverse=full_details.
        forward, reverse = _make_relationship_pair(
            db_session, a, b,
            forward_consent="free_busy_only",
            reverse_consent="full_details",
        )

        result = ptr_consent_service.accept_upgrade(
            db_session,
            accepting_tenant_id=a.id,
            relationship_id=forward.id,
            accepted_by_user_id=user_a.id,
        )
        assert result["prior_state"] == "pending_inbound"
        assert result["new_state"] == "active"
        db_session.refresh(forward)
        assert forward.calendar_freebusy_consent == "full_details"

    def test_revoke_active_back_to_pending_inbound(self, db_session):
        # When this side revokes from active, partner remains at full_details
        # → state becomes pending_inbound from this side's perspective.
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_admin(db_session, a)
        forward, reverse = _make_relationship_pair(
            db_session, a, b,
            forward_consent="full_details",
            reverse_consent="full_details",
        )

        result = ptr_consent_service.revoke_upgrade(
            db_session,
            revoking_tenant_id=a.id,
            relationship_id=forward.id,
            revoked_by_user_id=user_a.id,
        )
        assert result["prior_state"] == "active"
        assert result["new_state"] == "pending_inbound"
        db_session.refresh(forward)
        assert forward.calendar_freebusy_consent == "free_busy_only"

    def test_revoke_pending_outbound_to_default(self, db_session):
        # Cancel a pending request before partner accepts.
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_admin(db_session, a)
        forward, reverse = _make_relationship_pair(
            db_session, a, b,
            forward_consent="full_details",
            reverse_consent="free_busy_only",
        )

        result = ptr_consent_service.revoke_upgrade(
            db_session,
            revoking_tenant_id=a.id,
            relationship_id=forward.id,
            revoked_by_user_id=user_a.id,
        )
        assert result["prior_state"] == "pending_outbound"
        assert result["new_state"] == "default"

    def test_request_when_already_full_details_rejects(self, db_session):
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_admin(db_session, a)
        forward, reverse = _make_relationship_pair(
            db_session, a, b,
            forward_consent="full_details",
            reverse_consent="free_busy_only",
        )
        with pytest.raises(PtrConsentInvalidTransition):
            ptr_consent_service.request_upgrade(
                db_session,
                requesting_tenant_id=a.id,
                relationship_id=forward.id,
                requested_by_user_id=user_a.id,
            )

    def test_accept_without_partner_request_rejects(self, db_session):
        # Partner hasn't requested upgrade — accept_upgrade should
        # reject and direct caller to request_upgrade.
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_admin(db_session, a)
        forward, reverse = _make_relationship_pair(db_session, a, b)
        with pytest.raises(PtrConsentInvalidTransition):
            ptr_consent_service.accept_upgrade(
                db_session,
                accepting_tenant_id=a.id,
                relationship_id=forward.id,
                accepted_by_user_id=user_a.id,
            )

    def test_revoke_already_default_rejects(self, db_session):
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_admin(db_session, a)
        forward, reverse = _make_relationship_pair(db_session, a, b)
        with pytest.raises(PtrConsentInvalidTransition):
            ptr_consent_service.revoke_upgrade(
                db_session,
                revoking_tenant_id=a.id,
                relationship_id=forward.id,
                revoked_by_user_id=user_a.id,
            )

    def test_relationship_not_owned_by_caller_returns_404(self, db_session):
        # Existence-hiding 404 when caller's tenant isn't the row's
        # tenant_id.
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        c = _make_tenant(db_session, name_prefix="C")
        user_c = _make_admin(db_session, c)
        forward, _ = _make_relationship_pair(db_session, a, b)
        # User from tenant C tries to act on A's relationship.
        with pytest.raises(PtrConsentNotFound):
            ptr_consent_service.request_upgrade(
                db_session,
                requesting_tenant_id=c.id,
                relationship_id=forward.id,
                requested_by_user_id=user_c.id,
            )


# ─────────────────────────────────────────────────────────────────────
# 3. Per-side audit log discipline
# ─────────────────────────────────────────────────────────────────────


class TestAuditDiscipline:
    def test_request_writes_single_side_audit(self, db_session):
        # Per §3.26.11.10: tenant-side-only events appear only in the
        # originating side's log.
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_admin(db_session, a)
        forward, reverse = _make_relationship_pair(db_session, a, b)

        ptr_consent_service.request_upgrade(
            db_session,
            requesting_tenant_id=a.id,
            relationship_id=forward.id,
            requested_by_user_id=user_a.id,
        )
        db_session.flush()

        a_rows = (
            db_session.query(CalendarAuditLog)
            .filter(
                CalendarAuditLog.tenant_id == a.id,
                CalendarAuditLog.entity_id == forward.id,
                CalendarAuditLog.action == "consent_upgrade_requested",
            )
            .all()
        )
        b_rows = (
            db_session.query(CalendarAuditLog)
            .filter(
                CalendarAuditLog.tenant_id == b.id,
                CalendarAuditLog.action == "consent_upgrade_requested",
            )
            .all()
        )
        assert len(a_rows) == 1
        assert len(b_rows) == 0  # request is single-side per canon

    def test_accept_writes_both_sides_audit(self, db_session):
        # Per §3.26.11.10: joint events appear in both tenant scopes.
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_admin(db_session, a)
        forward, reverse = _make_relationship_pair(
            db_session, a, b,
            forward_consent="free_busy_only",
            reverse_consent="full_details",  # partner already requested
        )

        ptr_consent_service.accept_upgrade(
            db_session,
            accepting_tenant_id=a.id,
            relationship_id=forward.id,
            accepted_by_user_id=user_a.id,
        )
        db_session.flush()

        for tenant_id in (a.id, b.id):
            rows = (
                db_session.query(CalendarAuditLog)
                .filter(
                    CalendarAuditLog.tenant_id == tenant_id,
                    CalendarAuditLog.action == "consent_upgrade_accepted",
                )
                .all()
            )
            assert len(rows) == 1, (
                f"Expected per-side audit row for tenant {tenant_id}; "
                "joint event canonical per §3.26.11.10"
            )


# ─────────────────────────────────────────────────────────────────────
# 4. Notifications via V-1d notify_tenant_admins
# ─────────────────────────────────────────────────────────────────────


class TestNotifications:
    def test_request_notifies_partner_admins(self, db_session):
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_admin(db_session, a)
        admin_b = _make_admin(db_session, b)  # partner admin
        forward, reverse = _make_relationship_pair(db_session, a, b)

        ptr_consent_service.request_upgrade(
            db_session,
            requesting_tenant_id=a.id,
            relationship_id=forward.id,
            requested_by_user_id=user_a.id,
        )
        db_session.flush()

        # Partner admin B should have received an in-app notification.
        notifications = (
            db_session.query(Notification)
            .filter(
                Notification.company_id == b.id,
                Notification.user_id == admin_b.id,
                Notification.category == "calendar_consent_upgrade_request",
            )
            .all()
        )
        assert len(notifications) == 1
        assert (
            notifications[0].source_reference_id == forward.id
        )

    def test_accept_notifies_requesting_admins(self, db_session):
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        admin_a = _make_admin(db_session, a)
        user_b = _make_admin(db_session, b)
        # B requested upgrade (b's row = full_details); now A accepts.
        # A's perspective: forward = a→b; partner-side row (b→a) = full_details.
        forward_a, reverse_a_b = _make_relationship_pair(
            db_session, a, b,
            forward_consent="free_busy_only",
            reverse_consent="full_details",
        )

        ptr_consent_service.accept_upgrade(
            db_session,
            accepting_tenant_id=a.id,
            relationship_id=forward_a.id,
            accepted_by_user_id=admin_a.id,
        )
        db_session.flush()

        # The requesting tenant (B) should be notified that A accepted.
        notifications = (
            db_session.query(Notification)
            .filter(
                Notification.company_id == b.id,
                Notification.user_id == user_b.id,
                Notification.category == "calendar_consent_upgrade_accepted",
            )
            .all()
        )
        assert len(notifications) == 1

    def test_revoke_notifies_partner_admins(self, db_session):
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_admin(db_session, a)
        admin_b = _make_admin(db_session, b)
        forward, reverse = _make_relationship_pair(
            db_session, a, b,
            forward_consent="full_details",
            reverse_consent="full_details",
        )

        ptr_consent_service.revoke_upgrade(
            db_session,
            revoking_tenant_id=a.id,
            relationship_id=forward.id,
            revoked_by_user_id=user_a.id,
        )
        db_session.flush()

        notifications = (
            db_session.query(Notification)
            .filter(
                Notification.company_id == b.id,
                Notification.user_id == admin_b.id,
                Notification.category == "calendar_consent_upgrade_revoked",
            )
            .all()
        )
        assert len(notifications) == 1


# ─────────────────────────────────────────────────────────────────────
# 5. Latent privacy bug fix regression (Q2)
# ─────────────────────────────────────────────────────────────────────


class TestLatentPrivacyBugFix:
    def test_single_row_full_details_does_not_upgrade_to_bilateral(
        self, db_session
    ):
        # Pre-Step-4.1: forward_row=full_details + reverse_row=None →
        # all([full_details]) returned True → response upgraded to
        # full_details EVEN THOUGH partner never consented.
        # Post-Step-4.1: explicit `forward AND reverse AND both==full_details`
        # → response stays at free_busy_only. Privacy-default discipline.
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        admin_a = _make_admin(db_session, a)

        # CalendarAccount required for partner-tenant freebusy aggregation.
        partner_acc = CalendarAccount(
            id=str(uuid.uuid4()),
            tenant_id=b.id,
            account_type="shared",
            display_name="Partner",
            primary_email_address=f"p-{uuid.uuid4().hex[:8]}@b.test",
            provider_type="local",
            outbound_enabled=True,
            created_by_user_id=None,
        )
        db_session.add(partner_acc)
        db_session.flush()

        # Forward only — caller a→b at full_details; NO reverse row.
        # Pre-fix: leaks partner data; post-fix: privacy-default holds.
        forward, _ = _make_relationship_pair(
            db_session, a, b,
            forward_consent="full_details",
            create_reverse=False,
        )

        result = query_cross_tenant_freebusy(
            db_session,
            requesting_tenant_id=a.id,
            partner_tenant_id=b.id,
            range_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            range_end=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        # Latent-bug-fix invariant: missing reverse row → consent stays
        # privacy-preserving regardless of forward row's value.
        assert result.consent_level == "free_busy_only"


# ─────────────────────────────────────────────────────────────────────
# 6. API endpoints (TestClient)
# ─────────────────────────────────────────────────────────────────────


class TestApi:
    def _auth_headers_for(
        self, db_session, user: User
    ) -> dict[str, str]:
        from app.core.security import create_access_token

        # Resolve tenant slug for X-Company-Slug header (company_resolver
        # reads this; TestClient defaults to host=testserver which has
        # no subdomain).
        company = (
            db_session.query(Company)
            .filter(Company.id == user.company_id)
            .first()
        )
        token = create_access_token(
            data={"sub": user.id, "company_id": user.company_id}
        )
        return {
            "Authorization": f"Bearer {token}",
            "X-Company-Slug": company.slug,
        }

    def test_list_returns_partner_rows(self, db_session):
        from fastapi.testclient import TestClient
        from app.main import app

        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_admin(db_session, a)
        forward, reverse = _make_relationship_pair(db_session, a, b)
        db_session.commit()

        with TestClient(app) as client:
            r = client.get(
                "/api/v1/calendar/consent",
                headers=self._auth_headers_for(db_session, user_a),
            )
        assert r.status_code == 200
        body = r.json()
        partners = body["partners"]
        assert len(partners) == 1
        assert partners[0]["partner_tenant_id"] == b.id
        assert partners[0]["state"] == "default"

    def test_request_endpoint_flips_state(self, db_session):
        from fastapi.testclient import TestClient
        from app.main import app

        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_admin(db_session, a)
        _make_admin(db_session, b)  # partner admin so notification fires
        forward, reverse = _make_relationship_pair(db_session, a, b)
        db_session.commit()

        with TestClient(app) as client:
            r = client.post(
                f"/api/v1/calendar/consent/{forward.id}/request",
                headers=self._auth_headers_for(db_session, user_a),
            )
        assert r.status_code == 200
        body = r.json()
        assert body["prior_state"] == "default"
        assert body["new_state"] == "pending_outbound"

    def test_accept_endpoint_activates_bilateral(self, db_session):
        from fastapi.testclient import TestClient
        from app.main import app

        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_admin(db_session, a)
        _make_admin(db_session, b)
        forward, reverse = _make_relationship_pair(
            db_session, a, b,
            forward_consent="free_busy_only",
            reverse_consent="full_details",
        )
        db_session.commit()

        with TestClient(app) as client:
            r = client.post(
                f"/api/v1/calendar/consent/{forward.id}/accept",
                headers=self._auth_headers_for(db_session, user_a),
            )
        assert r.status_code == 200
        body = r.json()
        assert body["new_state"] == "active"

    def test_revoke_endpoint(self, db_session):
        from fastapi.testclient import TestClient
        from app.main import app

        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_admin(db_session, a)
        _make_admin(db_session, b)
        forward, reverse = _make_relationship_pair(
            db_session, a, b,
            forward_consent="full_details",
            reverse_consent="full_details",
        )
        db_session.commit()

        with TestClient(app) as client:
            r = client.post(
                f"/api/v1/calendar/consent/{forward.id}/revoke",
                headers=self._auth_headers_for(db_session, user_a),
            )
        assert r.status_code == 200
        body = r.json()
        assert body["prior_state"] == "active"
        assert body["new_state"] == "pending_inbound"

    def test_cross_tenant_existence_hiding_404(self, db_session):
        from fastapi.testclient import TestClient
        from app.main import app

        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        c = _make_tenant(db_session, name_prefix="C")
        user_c = _make_admin(db_session, c)
        forward, _ = _make_relationship_pair(db_session, a, b)
        db_session.commit()

        with TestClient(app) as client:
            r = client.post(
                f"/api/v1/calendar/consent/{forward.id}/request",
                headers=self._auth_headers_for(db_session, user_c),
            )
        # Caller is from tenant C; relationship is owned by A. 404 hides
        # cross-tenant existence.
        assert r.status_code == 404
