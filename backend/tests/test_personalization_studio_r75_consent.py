"""Personalization Studio implementation arc Step 1 Step 0 Migration r75
— canonical 4-state PTR consent column tests (column-per-capability per Q4).

Per Q4 canonical resolution (column-per-capability discipline) +
canonical-substrate-shape distinction from Calendar Step 4.1:

- Canonical column type ``String(32)`` with ``server_default="default"``
- Canonical 4-state machine stored DIRECTLY at column substrate
  (``default`` | ``pending_outbound`` | ``pending_inbound`` | ``active``)
- Canonical CHECK constraint enumerating canonical 4 state values
- Canonical dual-row update pattern at service layer (no resolver):
  request_*: forward ``default → pending_outbound`` + reverse ``default → pending_inbound``
  accept_*: forward ``pending_inbound → active`` + reverse ``pending_outbound → active``
  revoke_*: BOTH rows ``* → default``
- Canonical-substrate-shape distinction from Calendar Step 4.1:
  Calendar stores per-side intent + resolves bilateral 4-state at
  service-layer resolver; Personalization Studio stores 4-state directly
  at column substrate per Q4 canonical direction
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import AuditLog, Company, Notification, Role, User
from app.models.platform_tenant_relationship import PlatformTenantRelationship
from app.services.calendar import ptr_consent_service
from app.services.calendar.ptr_consent_service import (
    CANONICAL_PERSONALIZATION_STUDIO_STATES,
    PERSONALIZATION_STUDIO_CONSENT_COLUMN,
    PtrConsentInvalidTransition,
    PtrConsentNotFound,
    accept_personalization_studio_consent,
    check_personalization_studio_consent,
    list_partner_personalization_studio_consent_states,
    request_personalization_studio_consent,
    revoke_personalization_studio_consent,
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


def _make_tenant(db_session, *, name_prefix="R75"):
    co = Company(
        id=str(uuid.uuid4()),
        name=f"{name_prefix} {uuid.uuid4().hex[:8]}",
        slug=f"r75{uuid.uuid4().hex[:8]}",
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
        email=f"u-{uuid.uuid4().hex[:8]}@r75.test",
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
    relationship_type: str = "personalization_studio_partner",
    forward_state: str = "default",
    reverse_state: str = "default",
    create_reverse: bool = True,
) -> tuple[PlatformTenantRelationship, PlatformTenantRelationship | None]:
    """Create a bidirectional PTR pair with caller-supplied
    personalization_studio canonical 4-state values."""
    forward = PlatformTenantRelationship(
        id=str(uuid.uuid4()),
        tenant_id=tenant_a.id,
        supplier_tenant_id=tenant_b.id,
        relationship_type=relationship_type,
        status="active",
        personalization_studio_cross_tenant_sharing_consent=forward_state,
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
            personalization_studio_cross_tenant_sharing_consent=reverse_state,
        )
        db_session.add(reverse)
        db_session.flush()

    return forward, reverse


# ─────────────────────────────────────────────────────────────────────
# 1. Schema verification — canonical column shape + CHECK constraint
# ─────────────────────────────────────────────────────────────────────


class TestColumnPerCapabilityDiscipline:
    """Q4 canonical: canonical 4-state column-per-capability per PTR row."""

    def test_personalization_studio_consent_column_exists(self, db_session):
        cols = {
            c["name"]
            for c in inspect(db_session.bind).get_columns(
                "platform_tenant_relationships"
            )
        }
        assert "personalization_studio_cross_tenant_sharing_consent" in cols

    def test_personalization_studio_consent_metadata_columns_exist(
        self, db_session
    ):
        """Q3 canonical metadata columns parallel to Calendar Step 4.1."""
        cols = {
            c["name"]
            for c in inspect(db_session.bind).get_columns(
                "platform_tenant_relationships"
            )
        }
        assert (
            "personalization_studio_cross_tenant_sharing_consent_updated_at" in cols
        )
        assert (
            "personalization_studio_cross_tenant_sharing_consent_updated_by" in cols
        )

    def test_calendar_consent_column_unaffected_by_r75(self, db_session):
        """Q4 canonical: r75 does NOT touch ``calendar_freebusy_consent``."""
        cols = {
            c["name"]
            for c in inspect(db_session.bind).get_columns(
                "platform_tenant_relationships"
            )
        }
        assert "calendar_freebusy_consent" in cols
        assert "calendar_freebusy_consent_updated_at" in cols

    def test_canonical_column_constant_canonical(self):
        assert (
            PERSONALIZATION_STUDIO_CONSENT_COLUMN
            == "personalization_studio_cross_tenant_sharing_consent"
        )

    def test_canonical_4_state_constant_canonical(self):
        """Canonical 4-state machine values per Q4 canonical direction."""
        assert CANONICAL_PERSONALIZATION_STUDIO_STATES == (
            "default",
            "pending_outbound",
            "pending_inbound",
            "active",
        )

    def test_default_value_canonical_baseline(self, db_session):
        """Canonical default ``default`` per Q4 canonical direction (NOT
        Calendar-domain ``free_busy_only`` vocabulary)."""
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        # Insert via raw row to verify server_default canonical.
        rel = PlatformTenantRelationship(
            id=str(uuid.uuid4()),
            tenant_id=a.id,
            supplier_tenant_id=b.id,
            relationship_type="some_partner",
            status="active",
            # server_default takes effect — no explicit consent value.
        )
        db_session.add(rel)
        db_session.flush()
        db_session.refresh(rel)
        assert (
            rel.personalization_studio_cross_tenant_sharing_consent
            == "default"
        )

    def test_check_constraint_enumerates_canonical_4_states(self, db_session):
        """Canonical CHECK constraint at substrate boundary per Q4."""
        result = db_session.execute(
            text(
                """
                SELECT pg_get_constraintdef(c.oid) AS def
                FROM pg_constraint c
                WHERE c.conname = 'ck_ptr_personalization_studio_consent'
                AND c.conrelid = 'platform_tenant_relationships'::regclass
                """
            )
        ).first()
        assert result is not None
        check_def = result[0]
        # Canonical 4-state machine values present in CHECK constraint.
        for state in CANONICAL_PERSONALIZATION_STUDIO_STATES:
            assert f"'{state}'" in check_def

    def test_check_constraint_rejects_invalid_state(self, db_session):
        """CHECK constraint blocks non-canonical state values at substrate boundary."""
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        rel = PlatformTenantRelationship(
            id=str(uuid.uuid4()),
            tenant_id=a.id,
            supplier_tenant_id=b.id,
            relationship_type="some_partner",
            status="active",
            personalization_studio_cross_tenant_sharing_consent="bogus_state",
        )
        db_session.add(rel)
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_check_constraint_rejects_calendar_vocabulary(self, db_session):
        """Q4 canonical-substrate-shape distinction: Calendar's ``free_busy_only``
        vocabulary is canonically rejected at personalization_studio
        column substrate."""
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        rel = PlatformTenantRelationship(
            id=str(uuid.uuid4()),
            tenant_id=a.id,
            supplier_tenant_id=b.id,
            relationship_type="some_partner",
            status="active",
            # Calendar-domain vocabulary canonically rejected at
            # personalization_studio column substrate.
            personalization_studio_cross_tenant_sharing_consent="free_busy_only",
        )
        db_session.add(rel)
        with pytest.raises(IntegrityError):
            db_session.flush()


# ─────────────────────────────────────────────────────────────────────
# 2. State machine transitions — dual-row update pattern per Q4
# ─────────────────────────────────────────────────────────────────────


class TestStateMachineDualRowUpdate:
    """Canonical dual-row update pattern per Q4: state transitions update
    BOTH PTR rows synchronously."""

    def test_request_default_to_pending_outbound_dual_row_update(
        self, db_session
    ):
        """request_*: forward ``default → pending_outbound`` +
        reverse ``default → pending_inbound``."""
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_admin(db_session, a)
        forward, reverse = _make_relationship_pair(db_session, a, b)

        result = request_personalization_studio_consent(
            db_session,
            requesting_tenant_id=a.id,
            relationship_id=forward.id,
            requested_by_user_id=user_a.id,
        )

        assert result["prior_state"] == "default"
        assert result["new_state"] == "pending_outbound"

        # Forward row: caller side perspective.
        db_session.refresh(forward)
        assert (
            forward.personalization_studio_cross_tenant_sharing_consent
            == "pending_outbound"
        )

        # Reverse row: partner side perspective — canonical dual-row
        # update sets to ``pending_inbound``.
        db_session.refresh(reverse)
        assert (
            reverse.personalization_studio_cross_tenant_sharing_consent
            == "pending_inbound"
        )

        # Q3 metadata stamped on BOTH rows per dual-row canonical pattern.
        assert (
            forward.personalization_studio_cross_tenant_sharing_consent_updated_at
            is not None
        )
        assert (
            forward.personalization_studio_cross_tenant_sharing_consent_updated_by
            == user_a.id
        )
        assert (
            reverse.personalization_studio_cross_tenant_sharing_consent_updated_at
            is not None
        )
        assert (
            reverse.personalization_studio_cross_tenant_sharing_consent_updated_by
            == user_a.id
        )

    def test_accept_pending_inbound_to_active_dual_row_update(self, db_session):
        """accept_*: forward (acceptor) ``pending_inbound → active`` +
        reverse (requester) ``pending_outbound → active``."""
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_b = _make_admin(db_session, b)
        # Partner (a) requested; b's row is pending_inbound, a's row is pending_outbound.
        forward_b, reverse_a = _make_relationship_pair(
            db_session, b, a,
            forward_state="pending_inbound",
            reverse_state="pending_outbound",
        )

        result = accept_personalization_studio_consent(
            db_session,
            accepting_tenant_id=b.id,
            relationship_id=forward_b.id,
            accepted_by_user_id=user_b.id,
        )

        assert result["prior_state"] == "pending_inbound"
        assert result["new_state"] == "active"

        # Forward row (acceptor): pending_inbound → active.
        db_session.refresh(forward_b)
        assert (
            forward_b.personalization_studio_cross_tenant_sharing_consent
            == "active"
        )

        # Reverse row (requester): pending_outbound → active.
        db_session.refresh(reverse_a)
        assert (
            reverse_a.personalization_studio_cross_tenant_sharing_consent
            == "active"
        )

    def test_revoke_active_to_default_dual_row_update(self, db_session):
        """revoke_*: BOTH rows ``active → default``."""
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_admin(db_session, a)
        forward, reverse = _make_relationship_pair(
            db_session, a, b,
            forward_state="active",
            reverse_state="active",
        )

        result = revoke_personalization_studio_consent(
            db_session,
            revoking_tenant_id=a.id,
            relationship_id=forward.id,
            revoked_by_user_id=user_a.id,
        )

        assert result["prior_state"] == "active"
        assert result["new_state"] == "default"

        # Both rows reset to canonical default per dual-row pattern.
        db_session.refresh(forward)
        db_session.refresh(reverse)
        assert (
            forward.personalization_studio_cross_tenant_sharing_consent
            == "default"
        )
        assert (
            reverse.personalization_studio_cross_tenant_sharing_consent
            == "default"
        )

    def test_revoke_pending_outbound_to_default_dual_row_update(
        self, db_session
    ):
        """Canonical cancellation flow: caller cancels their own pending request."""
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_admin(db_session, a)
        forward, reverse = _make_relationship_pair(
            db_session, a, b,
            forward_state="pending_outbound",
            reverse_state="pending_inbound",
        )

        result = revoke_personalization_studio_consent(
            db_session,
            revoking_tenant_id=a.id,
            relationship_id=forward.id,
            revoked_by_user_id=user_a.id,
        )

        assert result["prior_state"] == "pending_outbound"
        assert result["new_state"] == "default"

        # Both rows reset to default per canonical pattern.
        db_session.refresh(forward)
        db_session.refresh(reverse)
        assert (
            forward.personalization_studio_cross_tenant_sharing_consent
            == "default"
        )
        assert (
            reverse.personalization_studio_cross_tenant_sharing_consent
            == "default"
        )

    def test_request_when_not_default_rejects(self, db_session):
        """Canonical request_* requires ``default`` prior state."""
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_admin(db_session, a)
        forward, _ = _make_relationship_pair(
            db_session, a, b,
            forward_state="pending_outbound",
            reverse_state="pending_inbound",
        )
        with pytest.raises(PtrConsentInvalidTransition):
            request_personalization_studio_consent(
                db_session,
                requesting_tenant_id=a.id,
                relationship_id=forward.id,
                requested_by_user_id=user_a.id,
            )

    def test_accept_when_not_pending_inbound_rejects(self, db_session):
        """Canonical accept_* requires ``pending_inbound`` prior state."""
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_admin(db_session, a)
        forward, _ = _make_relationship_pair(db_session, a, b)
        with pytest.raises(PtrConsentInvalidTransition):
            accept_personalization_studio_consent(
                db_session,
                accepting_tenant_id=a.id,
                relationship_id=forward.id,
                accepted_by_user_id=user_a.id,
            )

    def test_revoke_already_default_rejects(self, db_session):
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_admin(db_session, a)
        forward, _ = _make_relationship_pair(db_session, a, b)
        with pytest.raises(PtrConsentInvalidTransition):
            revoke_personalization_studio_consent(
                db_session,
                revoking_tenant_id=a.id,
                relationship_id=forward.id,
                revoked_by_user_id=user_a.id,
            )

    def test_cross_tenant_relationship_id_returns_404(self, db_session):
        """Existence-hiding: caller can't operate on other tenant's PTR row."""
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        c = _make_tenant(db_session, name_prefix="C")
        user_c = _make_admin(db_session, c)
        forward_a_to_b, _ = _make_relationship_pair(db_session, a, b)
        with pytest.raises(PtrConsentNotFound):
            request_personalization_studio_consent(
                db_session,
                requesting_tenant_id=c.id,
                relationship_id=forward_a_to_b.id,
                requested_by_user_id=user_c.id,
            )

    def test_missing_reverse_row_rejects(self, db_session):
        """Canonical dual-row pattern requires bidirectional PTR pair."""
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_admin(db_session, a)
        forward, _ = _make_relationship_pair(
            db_session, a, b, create_reverse=False
        )
        with pytest.raises(PtrConsentNotFound):
            request_personalization_studio_consent(
                db_session,
                requesting_tenant_id=a.id,
                relationship_id=forward.id,
                requested_by_user_id=user_a.id,
            )


# ─────────────────────────────────────────────────────────────────────
# 3. Audit log discipline — per-side joint event canon
# ─────────────────────────────────────────────────────────────────────


class TestAuditDiscipline:
    """Per Q4 canonical separation: personalization_studio consent transitions
    write to platform-wide ``audit_logs`` (NOT ``calendar_audit_log``)."""

    def test_request_writes_audit_to_caller_side_only(self, db_session):
        """Tenant-side-only event per §3.26.11.10 canonical."""
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_admin(db_session, a)
        forward, _ = _make_relationship_pair(db_session, a, b)

        request_personalization_studio_consent(
            db_session,
            requesting_tenant_id=a.id,
            relationship_id=forward.id,
            requested_by_user_id=user_a.id,
        )

        a_logs = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.company_id == a.id,
                AuditLog.action
                == "personalization_studio_consent_upgrade_requested",
            )
            .all()
        )
        b_logs = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.company_id == b.id,
                AuditLog.action
                == "personalization_studio_consent_upgrade_requested",
            )
            .all()
        )
        assert len(a_logs) == 1
        assert len(b_logs) == 0  # tenant-side-only event

    def test_accept_writes_audit_to_both_sides(self, db_session):
        """Joint event per §3.26.11.10 — bilateral activation writes both sides."""
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_b = _make_admin(db_session, b)
        forward_b, _ = _make_relationship_pair(
            db_session, b, a,
            forward_state="pending_inbound",
            reverse_state="pending_outbound",
        )

        accept_personalization_studio_consent(
            db_session,
            accepting_tenant_id=b.id,
            relationship_id=forward_b.id,
            accepted_by_user_id=user_b.id,
        )

        a_logs = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.company_id == a.id,
                AuditLog.action
                == "personalization_studio_consent_upgrade_accepted",
            )
            .all()
        )
        b_logs = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.company_id == b.id,
                AuditLog.action
                == "personalization_studio_consent_upgrade_accepted",
            )
            .all()
        )
        assert len(a_logs) == 1
        assert len(b_logs) == 1

    def test_audit_changes_canonical_4_state_shape(self, db_session):
        """Audit row carries canonical 4-state state-transition metadata."""
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_admin(db_session, a)
        forward, _ = _make_relationship_pair(db_session, a, b)

        request_personalization_studio_consent(
            db_session,
            requesting_tenant_id=a.id,
            relationship_id=forward.id,
            requested_by_user_id=user_a.id,
        )

        log = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.company_id == a.id,
                AuditLog.action
                == "personalization_studio_consent_upgrade_requested",
            )
            .first()
        )
        assert log is not None
        changes = (
            json.loads(log.changes) if isinstance(log.changes, str) else log.changes
        )
        assert changes["relationship_id"] == forward.id
        assert changes["partner_tenant_id"] == b.id
        assert changes["requesting_tenant_id"] == a.id
        # Canonical 4-state shape in audit changes per Q4.
        assert changes["prior_state"] == "default"
        assert changes["new_state"] == "pending_outbound"
        assert changes["reverse_row_new_state"] == "pending_inbound"

    def test_audit_destination_separation_from_calendar(self, db_session):
        """Q4 canonical-domain-boundary: personalization_studio consent
        audit lives in platform ``audit_logs``, NOT ``calendar_audit_log``."""
        from app.models.calendar_primitive import CalendarAuditLog

        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_admin(db_session, a)
        forward, _ = _make_relationship_pair(db_session, a, b)

        request_personalization_studio_consent(
            db_session,
            requesting_tenant_id=a.id,
            relationship_id=forward.id,
            requested_by_user_id=user_a.id,
        )

        cal_logs = (
            db_session.query(CalendarAuditLog)
            .filter(
                CalendarAuditLog.tenant_id == a.id,
                CalendarAuditLog.action.like(
                    "personalization_studio_consent_%"
                ),
            )
            .all()
        )
        assert len(cal_logs) == 0


# ─────────────────────────────────────────────────────────────────────
# 4. Notifications — V-1d substrate fan-out
# ─────────────────────────────────────────────────────────────────────


class TestNotifications:
    def test_request_notifies_partner_admins(self, db_session):
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_admin(db_session, a)
        admin_b = _make_admin(db_session, b)
        forward, _ = _make_relationship_pair(db_session, a, b)

        request_personalization_studio_consent(
            db_session,
            requesting_tenant_id=a.id,
            relationship_id=forward.id,
            requested_by_user_id=user_a.id,
        )

        notifs = (
            db_session.query(Notification)
            .filter(
                Notification.company_id == b.id,
                Notification.category
                == "personalization_studio_consent_upgrade_request",
            )
            .all()
        )
        assert len(notifs) >= 1
        notif = notifs[0]
        assert (
            notif.link
            == "/settings/personalization-studio/cross-tenant-sharing-consent"
        )

    def test_accept_notifies_requester_admins(self, db_session):
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        admin_a = _make_admin(db_session, a)
        user_b = _make_admin(db_session, b)
        forward_b, _ = _make_relationship_pair(
            db_session, b, a,
            forward_state="pending_inbound",
            reverse_state="pending_outbound",
        )

        accept_personalization_studio_consent(
            db_session,
            accepting_tenant_id=b.id,
            relationship_id=forward_b.id,
            accepted_by_user_id=user_b.id,
        )

        notifs = (
            db_session.query(Notification)
            .filter(
                Notification.company_id == a.id,
                Notification.category
                == "personalization_studio_consent_upgrade_accepted",
            )
            .all()
        )
        assert len(notifs) >= 1

    def test_revoke_notifies_partner_admins(self, db_session):
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_admin(db_session, a)
        admin_b = _make_admin(db_session, b)
        forward, _ = _make_relationship_pair(
            db_session, a, b,
            forward_state="active",
            reverse_state="active",
        )

        revoke_personalization_studio_consent(
            db_session,
            revoking_tenant_id=a.id,
            relationship_id=forward.id,
            revoked_by_user_id=user_a.id,
        )

        notifs = (
            db_session.query(Notification)
            .filter(
                Notification.company_id == b.id,
                Notification.category == "personalization_studio_consent_revoked",
            )
            .all()
        )
        assert len(notifs) >= 1


# ─────────────────────────────────────────────────────────────────────
# 5. check_* + list_partner_* — read directly from caller's row (no resolver)
# ─────────────────────────────────────────────────────────────────────


class TestReadHelpers:
    """Per Q4 canonical: state read DIRECTLY from caller's row (no resolver)."""

    def test_check_consent_returns_active_when_bilateral(self, db_session):
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        _make_relationship_pair(
            db_session, a, b,
            relationship_type="custom_partner",
            forward_state="active",
            reverse_state="active",
        )
        state = check_personalization_studio_consent(
            db_session,
            tenant_id=a.id,
            partner_tenant_id=b.id,
            relationship_type="custom_partner",
        )
        assert state == "active"

    def test_check_consent_returns_default_when_neither_side_active(
        self, db_session
    ):
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        _make_relationship_pair(
            db_session, a, b,
            relationship_type="custom_partner",
        )
        state = check_personalization_studio_consent(
            db_session,
            tenant_id=a.id,
            partner_tenant_id=b.id,
            relationship_type="custom_partner",
        )
        assert state == "default"

    def test_check_consent_returns_pending_outbound_from_caller_perspective(
        self, db_session
    ):
        """Each row stores state from THAT tenant's perspective per Q4."""
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        _make_relationship_pair(
            db_session, a, b,
            relationship_type="custom_partner",
            forward_state="pending_outbound",
            reverse_state="pending_inbound",
        )
        # A queries: A's perspective is pending_outbound.
        a_state = check_personalization_studio_consent(
            db_session,
            tenant_id=a.id,
            partner_tenant_id=b.id,
            relationship_type="custom_partner",
        )
        assert a_state == "pending_outbound"

        # B queries: B's perspective is pending_inbound.
        b_state = check_personalization_studio_consent(
            db_session,
            tenant_id=b.id,
            partner_tenant_id=a.id,
            relationship_type="custom_partner",
        )
        assert b_state == "pending_inbound"

    def test_check_consent_returns_default_when_no_relationship(
        self, db_session
    ):
        """Canonical privacy default when forward row missing."""
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        state = check_personalization_studio_consent(
            db_session,
            tenant_id=a.id,
            partner_tenant_id=b.id,
            relationship_type="never_existed",
        )
        assert state == "default"

    def test_list_partner_consent_states_canonical_shape(self, db_session):
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        forward, _ = _make_relationship_pair(
            db_session, a, b,
            forward_state="pending_outbound",
            reverse_state="pending_inbound",
        )
        results = list_partner_personalization_studio_consent_states(
            db_session, tenant_id=a.id
        )
        assert len(results) == 1
        row = results[0]
        assert row["relationship_id"] == forward.id
        assert row["partner_tenant_id"] == b.id
        assert row["state"] == "pending_outbound"
        assert row["partner_side_state"] == "pending_inbound"

    def test_list_excludes_other_tenants(self, db_session):
        """Canonical multi-tenant isolation."""
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        c = _make_tenant(db_session, name_prefix="C")
        _make_relationship_pair(db_session, a, b)
        _make_relationship_pair(
            db_session, c, b,
            relationship_type="other_partner",
        )
        a_results = list_partner_personalization_studio_consent_states(
            db_session, tenant_id=a.id
        )
        assert len(a_results) == 1
        assert a_results[0]["partner_tenant_id"] == b.id


# ─────────────────────────────────────────────────────────────────────
# 6. Calendar consent independence — Q4 column-per-capability isolation
# ─────────────────────────────────────────────────────────────────────


class TestCalendarConsentIndependence:
    """Q4 canonical: each capability's consent is canonically independent.
    Flipping personalization_studio consent does NOT flip calendar consent
    on the same PTR row, and vice versa."""

    def test_personalization_request_does_not_flip_calendar_consent(
        self, db_session
    ):
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_admin(db_session, a)
        forward, _ = _make_relationship_pair(db_session, a, b)
        # Sanity: Calendar baseline + Personalization baseline.
        assert forward.calendar_freebusy_consent == "free_busy_only"
        assert (
            forward.personalization_studio_cross_tenant_sharing_consent
            == "default"
        )

        request_personalization_studio_consent(
            db_session,
            requesting_tenant_id=a.id,
            relationship_id=forward.id,
            requested_by_user_id=user_a.id,
        )
        db_session.refresh(forward)

        # Personalization Studio flipped to canonical pending_outbound.
        assert (
            forward.personalization_studio_cross_tenant_sharing_consent
            == "pending_outbound"
        )
        # Calendar consent canonically untouched.
        assert forward.calendar_freebusy_consent == "free_busy_only"

    def test_calendar_request_does_not_flip_personalization_consent(
        self, db_session
    ):
        a = _make_tenant(db_session, name_prefix="A")
        b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_admin(db_session, a)
        forward, _ = _make_relationship_pair(db_session, a, b)
        assert (
            forward.personalization_studio_cross_tenant_sharing_consent
            == "default"
        )

        ptr_consent_service.request_upgrade(
            db_session,
            requesting_tenant_id=a.id,
            relationship_id=forward.id,
            requested_by_user_id=user_a.id,
        )
        db_session.refresh(forward)

        assert forward.calendar_freebusy_consent == "full_details"
        # Personalization Studio canonically unaffected.
        assert (
            forward.personalization_studio_cross_tenant_sharing_consent
            == "default"
        )
