"""Calendar Step 4 — cross-tenant pairing service tests.

Per §3.26.16.14 + §3.26.16.20:
  - propose_pairing / finalize_pairing / revoke_pairing lifecycle
  - Bilateral state propagation (per-side audit logs)
  - Revocation discipline (either tenant can revoke)
  - Per-tenant participant routing (per §3.26.11.7)
  - Per-tenant copy semantics
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

# Ensure Calendar package init runs.
from app.services import calendar as _cal_pkg  # noqa: F401
from app.models.calendar_primitive import (
    CalendarAuditLog,
    CrossTenantEventPairing,
)
from app.services.calendar import cross_tenant_pairing_service as ctp
from app.services.calendar.cross_tenant_pairing_service import (
    CrossTenantPairingConflict,
    CrossTenantPairingError,
    CrossTenantPairingNotFound,
    CrossTenantPairingPermissionDenied,
)

from tests._calendar_step4_fixtures import (
    db_session,  # noqa: F401
    make_account,
    make_attendee,
    make_event,
    make_tenant,
    make_user,
)


# ─────────────────────────────────────────────────────────────────────
# Lifecycle: propose / finalize / revoke
# ─────────────────────────────────────────────────────────────────────


class TestProposePairing:
    def test_propose_creates_pending_row(self, db_session):
        tenant_a = make_tenant(db_session, name_prefix="A")
        tenant_b = make_tenant(db_session, name_prefix="B")
        user = make_user(db_session, tenant_a)
        account = make_account(db_session, tenant_a, user=user)
        event = make_event(db_session, account, is_cross_tenant=True)

        pairing = ctp.propose_pairing(
            db_session,
            initiating_event=event,
            partner_tenant_id=tenant_b.id,
            actor_user_id=user.id,
        )
        assert pairing.event_a_id == event.id
        assert pairing.event_b_id is None
        assert pairing.tenant_a_id == tenant_a.id
        assert pairing.tenant_b_id == tenant_b.id
        # Pending semantics per Q2.
        assert pairing.paired_at is None
        assert pairing.revoked_at is None

    def test_self_pairing_rejected(self, db_session):
        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        event = make_event(db_session, account, is_cross_tenant=True)
        with pytest.raises(CrossTenantPairingError):
            ctp.propose_pairing(
                db_session,
                initiating_event=event,
                partner_tenant_id=tenant.id,
            )

    def test_non_cross_tenant_event_rejected(self, db_session):
        tenant_a = make_tenant(db_session, name_prefix="A")
        tenant_b = make_tenant(db_session, name_prefix="B")
        user = make_user(db_session, tenant_a)
        account = make_account(db_session, tenant_a, user=user)
        # is_cross_tenant=False
        event = make_event(db_session, account, is_cross_tenant=False)
        with pytest.raises(CrossTenantPairingError):
            ctp.propose_pairing(
                db_session,
                initiating_event=event,
                partner_tenant_id=tenant_b.id,
            )

    def test_duplicate_active_pairing_rejected(self, db_session):
        tenant_a = make_tenant(db_session, name_prefix="A")
        tenant_b = make_tenant(db_session, name_prefix="B")
        user = make_user(db_session, tenant_a)
        account = make_account(db_session, tenant_a, user=user)
        event = make_event(db_session, account, is_cross_tenant=True)
        ctp.propose_pairing(
            db_session,
            initiating_event=event,
            partner_tenant_id=tenant_b.id,
        )
        with pytest.raises(CrossTenantPairingConflict):
            ctp.propose_pairing(
                db_session,
                initiating_event=event,
                partner_tenant_id=tenant_b.id,
            )

    def test_propose_writes_audit_row(self, db_session):
        tenant_a = make_tenant(db_session, name_prefix="A")
        tenant_b = make_tenant(db_session, name_prefix="B")
        user = make_user(db_session, tenant_a)
        account = make_account(db_session, tenant_a, user=user)
        event = make_event(db_session, account, is_cross_tenant=True)
        pairing = ctp.propose_pairing(
            db_session,
            initiating_event=event,
            partner_tenant_id=tenant_b.id,
            actor_user_id=user.id,
        )
        rows = (
            db_session.query(CalendarAuditLog)
            .filter(
                CalendarAuditLog.entity_id == pairing.id,
                CalendarAuditLog.action == "cross_tenant_pairing_proposed",
            )
            .all()
        )
        assert len(rows) == 1


class TestFinalizePairing:
    def test_finalize_stamps_paired_at(self, db_session):
        tenant_a = make_tenant(db_session, name_prefix="A")
        tenant_b = make_tenant(db_session, name_prefix="B")
        user = make_user(db_session, tenant_a)
        account = make_account(db_session, tenant_a, user=user)
        event = make_event(db_session, account, is_cross_tenant=True)
        pairing = ctp.propose_pairing(
            db_session,
            initiating_event=event,
            partner_tenant_id=tenant_b.id,
        )
        ctp.finalize_pairing(db_session, pairing=pairing)
        db_session.refresh(pairing)
        assert pairing.paired_at is not None
        assert ctp.get_pairing_status(pairing) == "paired"

    def test_finalize_backfills_partner_event_id(self, db_session):
        tenant_a = make_tenant(db_session, name_prefix="A")
        tenant_b = make_tenant(db_session, name_prefix="B")
        user_a = make_user(db_session, tenant_a)
        account_a = make_account(db_session, tenant_a, user=user_a)
        event_a = make_event(db_session, account_a, is_cross_tenant=True)

        # Partner-side event row created at accept-time.
        user_b = make_user(db_session, tenant_b)
        account_b = make_account(db_session, tenant_b, user=user_b)
        event_b = make_event(db_session, account_b, is_cross_tenant=True)

        pairing = ctp.propose_pairing(
            db_session,
            initiating_event=event_a,
            partner_tenant_id=tenant_b.id,
        )
        ctp.finalize_pairing(
            db_session, pairing=pairing, partner_event_id=event_b.id
        )
        db_session.refresh(pairing)
        assert pairing.event_b_id == event_b.id

    def test_finalize_idempotent(self, db_session):
        tenant_a = make_tenant(db_session, name_prefix="A")
        tenant_b = make_tenant(db_session, name_prefix="B")
        user = make_user(db_session, tenant_a)
        account = make_account(db_session, tenant_a, user=user)
        event = make_event(db_session, account, is_cross_tenant=True)
        pairing = ctp.propose_pairing(
            db_session,
            initiating_event=event,
            partner_tenant_id=tenant_b.id,
        )
        ctp.finalize_pairing(db_session, pairing=pairing)
        first_paired_at = pairing.paired_at
        # Second call — no-op
        ctp.finalize_pairing(db_session, pairing=pairing)
        assert pairing.paired_at == first_paired_at

    def test_finalize_rejects_revoked_pairing(self, db_session):
        tenant_a = make_tenant(db_session, name_prefix="A")
        tenant_b = make_tenant(db_session, name_prefix="B")
        user = make_user(db_session, tenant_a)
        account = make_account(db_session, tenant_a, user=user)
        event = make_event(db_session, account, is_cross_tenant=True)
        pairing = ctp.propose_pairing(
            db_session,
            initiating_event=event,
            partner_tenant_id=tenant_b.id,
        )
        ctp.revoke_pairing(
            db_session,
            pairing=pairing,
            revoking_tenant_id=tenant_a.id,
        )
        with pytest.raises(CrossTenantPairingError):
            ctp.finalize_pairing(db_session, pairing=pairing)

    def test_finalize_writes_per_side_audit(self, db_session):
        tenant_a = make_tenant(db_session, name_prefix="A")
        tenant_b = make_tenant(db_session, name_prefix="B")
        user = make_user(db_session, tenant_a)
        account = make_account(db_session, tenant_a, user=user)
        event = make_event(db_session, account, is_cross_tenant=True)
        pairing = ctp.propose_pairing(
            db_session,
            initiating_event=event,
            partner_tenant_id=tenant_b.id,
        )
        ctp.finalize_pairing(db_session, pairing=pairing)

        # Per §3.26.11.10 per-side audit logs.
        for tenant_id in (tenant_a.id, tenant_b.id):
            rows = (
                db_session.query(CalendarAuditLog)
                .filter(
                    CalendarAuditLog.entity_id == pairing.id,
                    CalendarAuditLog.action == "cross_tenant_pairing_finalized",
                    CalendarAuditLog.tenant_id == tenant_id,
                )
                .all()
            )
            assert len(rows) == 1


class TestRevokePairing:
    def test_either_tenant_can_revoke(self, db_session):
        tenant_a = make_tenant(db_session, name_prefix="A")
        tenant_b = make_tenant(db_session, name_prefix="B")
        user = make_user(db_session, tenant_a)
        account = make_account(db_session, tenant_a, user=user)
        event = make_event(db_session, account, is_cross_tenant=True)

        # Tenant A revokes
        pairing_1 = ctp.propose_pairing(
            db_session,
            initiating_event=event,
            partner_tenant_id=tenant_b.id,
        )
        ctp.revoke_pairing(
            db_session,
            pairing=pairing_1,
            revoking_tenant_id=tenant_a.id,
        )
        assert pairing_1.revoked_at is not None

        # Tenant B revokes a different pairing (after re-proposal allowed
        # since first was revoked).
        event2 = make_event(db_session, account, is_cross_tenant=True)
        pairing_2 = ctp.propose_pairing(
            db_session,
            initiating_event=event2,
            partner_tenant_id=tenant_b.id,
        )
        ctp.revoke_pairing(
            db_session,
            pairing=pairing_2,
            revoking_tenant_id=tenant_b.id,
        )
        assert pairing_2.revoked_at is not None

    def test_non_participant_tenant_rejected(self, db_session):
        tenant_a = make_tenant(db_session, name_prefix="A")
        tenant_b = make_tenant(db_session, name_prefix="B")
        tenant_c = make_tenant(db_session, name_prefix="C")
        user = make_user(db_session, tenant_a)
        account = make_account(db_session, tenant_a, user=user)
        event = make_event(db_session, account, is_cross_tenant=True)
        pairing = ctp.propose_pairing(
            db_session,
            initiating_event=event,
            partner_tenant_id=tenant_b.id,
        )
        with pytest.raises(CrossTenantPairingPermissionDenied):
            ctp.revoke_pairing(
                db_session,
                pairing=pairing,
                revoking_tenant_id=tenant_c.id,
            )

    def test_double_revoke_rejected(self, db_session):
        tenant_a = make_tenant(db_session, name_prefix="A")
        tenant_b = make_tenant(db_session, name_prefix="B")
        user = make_user(db_session, tenant_a)
        account = make_account(db_session, tenant_a, user=user)
        event = make_event(db_session, account, is_cross_tenant=True)
        pairing = ctp.propose_pairing(
            db_session,
            initiating_event=event,
            partner_tenant_id=tenant_b.id,
        )
        ctp.revoke_pairing(
            db_session,
            pairing=pairing,
            revoking_tenant_id=tenant_a.id,
        )
        with pytest.raises(CrossTenantPairingError):
            ctp.revoke_pairing(
                db_session,
                pairing=pairing,
                revoking_tenant_id=tenant_a.id,
            )


class TestListAndStatus:
    def test_list_pairings_for_tenant_status_filter(self, db_session):
        tenant_a = make_tenant(db_session, name_prefix="A")
        tenant_b = make_tenant(db_session, name_prefix="B")
        user = make_user(db_session, tenant_a)
        account = make_account(db_session, tenant_a, user=user)

        # Pending pairing
        e1 = make_event(db_session, account, is_cross_tenant=True)
        p1 = ctp.propose_pairing(
            db_session,
            initiating_event=e1,
            partner_tenant_id=tenant_b.id,
        )
        # Paired
        e2 = make_event(db_session, account, is_cross_tenant=True)
        p2 = ctp.propose_pairing(
            db_session,
            initiating_event=e2,
            partner_tenant_id=tenant_b.id,
        )
        ctp.finalize_pairing(db_session, pairing=p2)
        # Revoked
        e3 = make_event(db_session, account, is_cross_tenant=True)
        p3 = ctp.propose_pairing(
            db_session,
            initiating_event=e3,
            partner_tenant_id=tenant_b.id,
        )
        ctp.revoke_pairing(
            db_session,
            pairing=p3,
            revoking_tenant_id=tenant_a.id,
        )

        pending = ctp.list_pairings_for_tenant(
            db_session, tenant_id=tenant_a.id, status="pending"
        )
        assert {p.id for p in pending} == {p1.id}
        paired = ctp.list_pairings_for_tenant(
            db_session, tenant_id=tenant_a.id, status="paired"
        )
        assert {p.id for p in paired} == {p2.id}
        revoked = ctp.list_pairings_for_tenant(
            db_session, tenant_id=tenant_a.id, status="revoked"
        )
        assert {p.id for p in revoked} == {p3.id}

    def test_get_pairing_not_found(self, db_session):
        with pytest.raises(CrossTenantPairingNotFound):
            ctp.get_pairing(db_session, pairing_id=str(uuid.uuid4()))


class TestPerTenantParticipantRouting:
    def test_lists_attendees_for_tenant_a_side(self, db_session):
        tenant_a = make_tenant(db_session, name_prefix="A")
        tenant_b = make_tenant(db_session, name_prefix="B")
        user_a = make_user(db_session, tenant_a)
        account_a = make_account(db_session, tenant_a, user=user_a)
        event_a = make_event(db_session, account_a, is_cross_tenant=True)

        att_a1 = make_attendee(
            db_session,
            event_a,
            email_address="a1@a.test",
            is_internal=True,
        )
        att_a2 = make_attendee(
            db_session,
            event_a,
            email_address="a2@a.test",
            is_internal=False,
        )
        pairing = ctp.propose_pairing(
            db_session,
            initiating_event=event_a,
            partner_tenant_id=tenant_b.id,
        )

        attendees = ctp.list_participants_for_tenant_side(
            db_session, pairing=pairing, tenant_id=tenant_a.id
        )
        assert {a.email_address for a in attendees} == {
            "a1@a.test",
            "a2@a.test",
        }

    def test_partner_side_empty_pre_accept(self, db_session):
        # event_b_id is NULL pre-accept; partner-side attendee list empty.
        tenant_a = make_tenant(db_session, name_prefix="A")
        tenant_b = make_tenant(db_session, name_prefix="B")
        user = make_user(db_session, tenant_a)
        account = make_account(db_session, tenant_a, user=user)
        event = make_event(db_session, account, is_cross_tenant=True)
        pairing = ctp.propose_pairing(
            db_session,
            initiating_event=event,
            partner_tenant_id=tenant_b.id,
        )
        partner_attendees = ctp.list_participants_for_tenant_side(
            db_session, pairing=pairing, tenant_id=tenant_b.id
        )
        assert partner_attendees == []

    def test_non_participant_rejected(self, db_session):
        tenant_a = make_tenant(db_session, name_prefix="A")
        tenant_b = make_tenant(db_session, name_prefix="B")
        tenant_c = make_tenant(db_session, name_prefix="C")
        user = make_user(db_session, tenant_a)
        account = make_account(db_session, tenant_a, user=user)
        event = make_event(db_session, account, is_cross_tenant=True)
        pairing = ctp.propose_pairing(
            db_session,
            initiating_event=event,
            partner_tenant_id=tenant_b.id,
        )
        with pytest.raises(CrossTenantPairingError):
            ctp.list_participants_for_tenant_side(
                db_session, pairing=pairing, tenant_id=tenant_c.id
            )
