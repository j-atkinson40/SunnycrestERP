"""Calendar Step 4 — 5 action_types canonical commit_handler tests.

Per §3.26.16.17 + §3.26.16.18 + §3.26.16.20:
  - 5 ActionTypeDescriptors registered against central registry
  - State propagation per outcome (accept/reject/counter_propose)
  - En bloc recurring_meeting_proposal acceptance
  - Counter-proposal chaining (original terminal + new action at next idx)
  - action_metadata shape conformance
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

# Ensure Calendar package init runs (registers 5 action_types).
from app.services import calendar as _cal_pkg  # noqa: F401
from app.services.calendar import calendar_action_service
from app.services.calendar.calendar_action_service import (
    ACTION_OUTCOMES_CALENDAR,
    ACTION_TYPES,
    ActionAlreadyCompleted,
    ActionError,
    ActionNotFound,
    CommitResult,
    append_action_to_event,
    build_delivery_date_acceptance_action,
    build_event_reschedule_proposal_action,
    build_joint_event_acceptance_action,
    build_recurring_meeting_proposal_action,
    build_service_date_acceptance_action,
    chain_counter_proposal,
    commit_action,
    compute_reschedule_cascade,
    get_action_at_index,
    get_event_actions,
)
from app.services.platform.action_registry import (
    get_action_type,
    list_action_types_for_primitive,
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
# Registry: 5 action_types canonical
# ─────────────────────────────────────────────────────────────────────


class TestRegistry:
    def test_five_canonical_action_types_registered(self):
        registered = {d.action_type for d in list_action_types_for_primitive("calendar")}
        expected = {
            "service_date_acceptance",
            "delivery_date_acceptance",
            "joint_event_acceptance",
            "recurring_meeting_proposal",
            "event_reschedule_proposal",
        }
        assert expected.issubset(registered)

    def test_action_types_constant_matches_registry(self):
        assert set(ACTION_TYPES) == {
            d.action_type for d in list_action_types_for_primitive("calendar")
        }

    def test_outcomes_canonical(self):
        for action_type in ACTION_TYPES:
            d = get_action_type(action_type)
            assert d.outcomes == ACTION_OUTCOMES_CALENDAR
            assert "counter_propose" in d.requires_completion_note

    def test_action_target_types_per_canon(self):
        # Per §3.26.16.17 verbatim
        targets = {
            d.action_type: d.target_entity_type
            for d in list_action_types_for_primitive("calendar")
        }
        assert targets["service_date_acceptance"] == "fh_case"
        assert targets["delivery_date_acceptance"] == "sales_order"
        assert targets["joint_event_acceptance"] == "cross_tenant_event"
        assert targets["recurring_meeting_proposal"] == "cross_tenant_event"
        assert targets["event_reschedule_proposal"] == "calendar_event"


# ─────────────────────────────────────────────────────────────────────
# Action-shape helpers
# ─────────────────────────────────────────────────────────────────────


class TestActionShapeHelpers:
    def test_build_service_date_acceptance(self):
        action = build_service_date_acceptance_action(
            fh_case_id="case-1",
            proposed_start_at=datetime(2026, 5, 14, 14, tzinfo=timezone.utc),
            proposed_end_at=datetime(2026, 5, 14, 15, 30, tzinfo=timezone.utc),
            proposed_location="Hopkins FH chapel",
            proposing_tenant_name="Sunnycrest Vault",
            deceased_name="Anderson",
        )
        assert action["action_type"] == "service_date_acceptance"
        assert action["action_target_type"] == "fh_case"
        assert action["action_target_id"] == "case-1"
        assert action["action_status"] == "pending"
        meta = action["action_metadata"]
        assert "proposed_start_at" in meta
        assert meta["proposed_location"] == "Hopkins FH chapel"
        assert meta["deceased_name"] == "Anderson"

    def test_build_delivery_date_acceptance(self):
        action = build_delivery_date_acceptance_action(
            sales_order_id="so-1",
            proposed_start_at=datetime(2026, 5, 14, 9, tzinfo=timezone.utc),
            proposed_end_at=datetime(2026, 5, 14, 10, tzinfo=timezone.utc),
            proposed_location=None,
            proposing_tenant_name="Sunnycrest Vault",
            sales_order_number="SO-2026-0445",
        )
        assert action["action_type"] == "delivery_date_acceptance"
        assert action["action_target_type"] == "sales_order"
        assert action["action_metadata"]["sales_order_number"] == "SO-2026-0445"

    def test_build_joint_event_acceptance(self):
        action = build_joint_event_acceptance_action(
            pairing_id="pairing-1",
            proposed_start_at=datetime(2026, 5, 14, 14, tzinfo=timezone.utc),
            proposed_end_at=datetime(2026, 5, 14, 15, tzinfo=timezone.utc),
            proposed_location="Hopkins HQ",
            proposing_tenant_name="Sunnycrest Vault",
            event_subject="Joint quality review",
        )
        assert action["action_type"] == "joint_event_acceptance"
        assert action["action_target_type"] == "cross_tenant_event"
        assert action["action_target_id"] == "pairing-1"

    def test_build_recurring_meeting_proposal(self):
        action = build_recurring_meeting_proposal_action(
            pairing_id="pairing-rec",
            proposed_start_at=datetime(2026, 5, 14, 9, 30, tzinfo=timezone.utc),
            proposed_end_at=datetime(2026, 5, 14, 10, 30, tzinfo=timezone.utc),
            proposed_location="Sunnycrest Vault",
            proposing_tenant_name="Sunnycrest Vault",
            recurrence_rule="RRULE:FREQ=WEEKLY;BYDAY=TU",
            event_subject="Weekly ops sync",
        )
        assert action["action_type"] == "recurring_meeting_proposal"
        assert action["action_metadata"]["recurrence_rule"] == "RRULE:FREQ=WEEKLY;BYDAY=TU"

    def test_build_event_reschedule_proposal(self):
        action = build_event_reschedule_proposal_action(
            event_id="evt-1",
            proposed_start_at=datetime(2026, 5, 14, 14, tzinfo=timezone.utc),
            proposed_end_at=datetime(2026, 5, 14, 15, tzinfo=timezone.utc),
            proposed_location=None,
            proposing_tenant_name="Sunnycrest Vault",
            cascade_impact={"linked_entity_count": 2, "paired_cross_tenant_count": 1},
        )
        assert action["action_type"] == "event_reschedule_proposal"
        assert action["action_metadata"]["cascade_impact"]["linked_entity_count"] == 2


# ─────────────────────────────────────────────────────────────────────
# action_payload accessors
# ─────────────────────────────────────────────────────────────────────


class TestActionPayloadAccessors:
    def test_get_event_actions_empty(self, db_session):
        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        event = make_event(db_session, account)
        assert get_event_actions(event) == []

    def test_append_action_returns_index(self, db_session):
        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        event = make_event(db_session, account)
        a1 = build_service_date_acceptance_action(
            fh_case_id="c1",
            proposed_start_at=datetime(2026, 6, 1, 14, tzinfo=timezone.utc),
            proposed_end_at=datetime(2026, 6, 1, 15, tzinfo=timezone.utc),
            proposed_location="loc",
            proposing_tenant_name="T",
        )
        idx_a = append_action_to_event(event, a1)
        a2 = build_service_date_acceptance_action(
            fh_case_id="c2",
            proposed_start_at=datetime(2026, 6, 2, 14, tzinfo=timezone.utc),
            proposed_end_at=datetime(2026, 6, 2, 15, tzinfo=timezone.utc),
            proposed_location="loc",
            proposing_tenant_name="T",
        )
        idx_b = append_action_to_event(event, a2)
        assert idx_a == 0
        assert idx_b == 1
        assert len(get_event_actions(event)) == 2

    def test_get_action_at_index_out_of_bounds(self, db_session):
        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        event = make_event(db_session, account)
        with pytest.raises(ActionNotFound):
            get_action_at_index(event, 0)


# ─────────────────────────────────────────────────────────────────────
# Service date acceptance commit handler
# ─────────────────────────────────────────────────────────────────────


class TestServiceDateAcceptance:
    def test_accept_flips_event_to_confirmed(self, db_session):
        """Per §3.26.16.18: accept transitions event tentative→confirmed."""
        tenant = make_tenant(db_session, vertical="funeral_home")
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)

        event = make_event(db_session, account, status="tentative")
        action = build_service_date_acceptance_action(
            fh_case_id=str(uuid.uuid4()),
            proposed_start_at=event.start_at,
            proposed_end_at=event.end_at,
            proposed_location="Hopkins chapel",
            proposing_tenant_name="Sunnycrest",
            deceased_name="Anderson",
        )
        idx = append_action_to_event(event, action)

        result = commit_action(
            db_session,
            event=event,
            action_idx=idx,
            outcome="accept",
            actor_user_id=user.id,
            actor_email=user.email,
        )

        assert isinstance(result, CommitResult)
        assert result.updated_action["action_status"] == "accepted"
        # Per §3.26.16.18: accept → event status="confirmed"
        db_session.refresh(event)
        assert event.status == "confirmed"
        # Audit logged the action commit
        from app.models.calendar_primitive import CalendarAuditLog

        audit_rows = (
            db_session.query(CalendarAuditLog)
            .filter(
                CalendarAuditLog.entity_id == event.id,
                CalendarAuditLog.action == "calendar_action_committed",
            )
            .all()
        )
        assert len(audit_rows) == 1
        assert (audit_rows[0].changes or {}).get("outcome") == "accept"
        assert (audit_rows[0].changes or {}).get(
            "action_type"
        ) == "service_date_acceptance"

    def test_accept_propagates_to_fh_case_when_present(self, db_session):
        """Per §3.26.16.18 state propagation: FHCase.service_date set on accept."""
        pytest.importorskip("app.models.fh_case")
        from app.models.fh_case import FHCase

        tenant = make_tenant(db_session, vertical="funeral_home")
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)

        case = FHCase(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            case_number=f"CASE-{uuid.uuid4().hex[:6]}",
            deceased_first_name="Test",
            deceased_last_name="Anderson",
            deceased_date_of_death=datetime(2026, 5, 1, tzinfo=timezone.utc).date(),
        )
        db_session.add(case)
        db_session.flush()

        event = make_event(db_session, account, status="tentative")
        action = build_service_date_acceptance_action(
            fh_case_id=case.id,
            proposed_start_at=event.start_at,
            proposed_end_at=event.end_at,
            proposed_location="Hopkins chapel",
            proposing_tenant_name="Sunnycrest",
            deceased_name="Anderson",
        )
        idx = append_action_to_event(event, action)

        commit_action(
            db_session,
            event=event,
            action_idx=idx,
            outcome="accept",
            actor_user_id=user.id,
            actor_email=user.email,
        )
        db_session.refresh(case)
        assert case.service_date is not None

    def test_reject_does_not_propagate(self, db_session):
        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        event = make_event(db_session, account, status="tentative")
        action = build_service_date_acceptance_action(
            fh_case_id="case-noprop",
            proposed_start_at=event.start_at,
            proposed_end_at=event.end_at,
            proposed_location="loc",
            proposing_tenant_name="T",
        )
        idx = append_action_to_event(event, action)

        result = commit_action(
            db_session,
            event=event,
            action_idx=idx,
            outcome="reject",
            actor_user_id=user.id,
            actor_email=user.email,
        )
        assert result.updated_action["action_status"] == "rejected"
        # Per canon: rejected → event status retained (operator follows up)
        db_session.refresh(event)
        assert event.status == "tentative"

    def test_counter_propose_chains_new_action(self, db_session):
        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        event = make_event(db_session, account, status="tentative")
        action = build_service_date_acceptance_action(
            fh_case_id="case-counter",
            proposed_start_at=event.start_at,
            proposed_end_at=event.end_at,
            proposed_location="orig location",
            proposing_tenant_name="Sunnycrest",
        )
        idx = append_action_to_event(event, action)

        counter_start = datetime(2026, 6, 2, 14, tzinfo=timezone.utc)
        counter_end = datetime(2026, 6, 2, 15, tzinfo=timezone.utc)
        result = commit_action(
            db_session,
            event=event,
            action_idx=idx,
            outcome="counter_propose",
            actor_user_id=user.id,
            actor_email=user.email,
            completion_note="Friday morning works better",
            counter_proposed_start_at=counter_start,
            counter_proposed_end_at=counter_end,
        )
        assert result.updated_action["action_status"] == "counter_proposed"
        # New chained action appended at next idx
        assert result.counter_action_idx == idx + 1
        # Original metadata preserved on chained action
        chained = get_action_at_index(event, result.counter_action_idx)
        assert chained["action_metadata"]["proposed_location"] == "orig location"
        assert chained["action_metadata"]["is_counter_proposal"] is True

    def test_counter_propose_requires_counter_times(self, db_session):
        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        event = make_event(db_session, account)
        action = build_service_date_acceptance_action(
            fh_case_id="c",
            proposed_start_at=event.start_at,
            proposed_end_at=event.end_at,
            proposed_location="l",
            proposing_tenant_name="T",
        )
        idx = append_action_to_event(event, action)

        with pytest.raises(ActionError):
            commit_action(
                db_session,
                event=event,
                action_idx=idx,
                outcome="counter_propose",
                actor_user_id=user.id,
                actor_email=user.email,
                completion_note="counter",
                # Missing counter_proposed_start_at + counter_proposed_end_at
            )

    def test_already_completed_action_rejects_re_commit(self, db_session):
        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        event = make_event(db_session, account)
        action = build_service_date_acceptance_action(
            fh_case_id="c",
            proposed_start_at=event.start_at,
            proposed_end_at=event.end_at,
            proposed_location="l",
            proposing_tenant_name="T",
        )
        idx = append_action_to_event(event, action)

        commit_action(
            db_session,
            event=event,
            action_idx=idx,
            outcome="reject",
            actor_user_id=user.id,
            actor_email=user.email,
        )

        with pytest.raises(ActionAlreadyCompleted):
            commit_action(
                db_session,
                event=event,
                action_idx=idx,
                outcome="accept",
                actor_user_id=user.id,
                actor_email=user.email,
            )


# ─────────────────────────────────────────────────────────────────────
# Delivery date acceptance commit handler
# ─────────────────────────────────────────────────────────────────────


class TestDeliveryDateAcceptance:
    def test_accept_flips_event_to_confirmed(self, db_session):
        """Per §3.26.16.18: accept flips event tentative→confirmed even
        when target SalesOrder isn't present (handler logs + skips
        operational propagation gracefully)."""
        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)

        event = make_event(db_session, account, status="tentative")
        action = build_delivery_date_acceptance_action(
            sales_order_id=str(uuid.uuid4()),  # non-existent SO id
            proposed_start_at=event.start_at,
            proposed_end_at=event.end_at,
            proposed_location=None,
            proposing_tenant_name="Sunnycrest",
        )
        idx = append_action_to_event(event, action)

        result = commit_action(
            db_session,
            event=event,
            action_idx=idx,
            outcome="accept",
            actor_user_id=user.id,
            actor_email=user.email,
        )
        assert result.updated_action["action_status"] == "accepted"
        db_session.refresh(event)
        assert event.status == "confirmed"

    def test_reject_does_not_propagate(self, db_session):
        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        event = make_event(db_session, account, status="tentative")
        action = build_delivery_date_acceptance_action(
            sales_order_id="so-noprop",
            proposed_start_at=event.start_at,
            proposed_end_at=event.end_at,
            proposed_location=None,
            proposing_tenant_name="T",
        )
        idx = append_action_to_event(event, action)
        result = commit_action(
            db_session,
            event=event,
            action_idx=idx,
            outcome="reject",
            actor_user_id=user.id,
            actor_email=user.email,
        )
        assert result.updated_action["action_status"] == "rejected"
        db_session.refresh(event)
        assert event.status == "tentative"


# ─────────────────────────────────────────────────────────────────────
# Joint event acceptance commit handler
# ─────────────────────────────────────────────────────────────────────


class TestJointEventAcceptance:
    def test_accept_finalizes_pairing(self, db_session):
        from app.models.calendar_primitive import CrossTenantEventPairing

        tenant_a = make_tenant(db_session, name_prefix="A")
        tenant_b = make_tenant(db_session, name_prefix="B")
        user = make_user(db_session, tenant_b)
        account = make_account(db_session, tenant_b, user=user)
        event = make_event(
            db_session,
            account,
            status="tentative",
            is_cross_tenant=True,
        )

        # Seed a pending pairing.
        pairing = CrossTenantEventPairing(
            id=str(uuid.uuid4()),
            event_a_id=event.id,
            event_b_id=None,
            tenant_a_id=tenant_a.id,
            tenant_b_id=tenant_b.id,
            paired_at=None,
            revoked_at=None,
        )
        db_session.add(pairing)
        db_session.flush()

        action = build_joint_event_acceptance_action(
            pairing_id=pairing.id,
            proposed_start_at=event.start_at,
            proposed_end_at=event.end_at,
            proposed_location="HQ",
            proposing_tenant_name="A",
        )
        idx = append_action_to_event(event, action)

        result = commit_action(
            db_session,
            event=event,
            action_idx=idx,
            outcome="accept",
            actor_user_id=user.id,
            actor_email=user.email,
        )
        assert result.updated_action["action_status"] == "accepted"
        assert result.target_status == "paired"
        db_session.refresh(pairing)
        assert pairing.paired_at is not None
        assert pairing.revoked_at is None

    def test_reject_revokes_pairing(self, db_session):
        from app.models.calendar_primitive import CrossTenantEventPairing

        tenant_a = make_tenant(db_session, name_prefix="A")
        tenant_b = make_tenant(db_session, name_prefix="B")
        user = make_user(db_session, tenant_b)
        account = make_account(db_session, tenant_b, user=user)
        event = make_event(db_session, account, is_cross_tenant=True)

        pairing = CrossTenantEventPairing(
            id=str(uuid.uuid4()),
            event_a_id=event.id,
            event_b_id=None,
            tenant_a_id=tenant_a.id,
            tenant_b_id=tenant_b.id,
            paired_at=None,
        )
        db_session.add(pairing)
        db_session.flush()

        action = build_joint_event_acceptance_action(
            pairing_id=pairing.id,
            proposed_start_at=event.start_at,
            proposed_end_at=event.end_at,
            proposed_location="HQ",
            proposing_tenant_name="A",
        )
        idx = append_action_to_event(event, action)

        result = commit_action(
            db_session,
            event=event,
            action_idx=idx,
            outcome="reject",
            actor_user_id=user.id,
            actor_email=user.email,
        )
        assert result.target_status == "revoked"
        db_session.refresh(pairing)
        assert pairing.revoked_at is not None


# ─────────────────────────────────────────────────────────────────────
# Recurring meeting proposal commit handler (en bloc per Q4)
# ─────────────────────────────────────────────────────────────────────


class TestRecurringMeetingProposal:
    def test_accept_finalizes_recurring_pairing_en_bloc(self, db_session):
        from app.models.calendar_primitive import CrossTenantEventPairing

        tenant_a = make_tenant(db_session, name_prefix="A")
        tenant_b = make_tenant(db_session, name_prefix="B")
        user = make_user(db_session, tenant_b)
        account = make_account(db_session, tenant_b, user=user)
        event = make_event(
            db_session,
            account,
            status="tentative",
            is_cross_tenant=True,
            recurrence_rule="RRULE:FREQ=WEEKLY;BYDAY=TU",
        )

        pairing = CrossTenantEventPairing(
            id=str(uuid.uuid4()),
            event_a_id=event.id,
            event_b_id=None,
            tenant_a_id=tenant_a.id,
            tenant_b_id=tenant_b.id,
            paired_at=None,
        )
        db_session.add(pairing)
        db_session.flush()

        action = build_recurring_meeting_proposal_action(
            pairing_id=pairing.id,
            proposed_start_at=event.start_at,
            proposed_end_at=event.end_at,
            proposed_location="HQ",
            proposing_tenant_name="A",
            recurrence_rule="RRULE:FREQ=WEEKLY;BYDAY=TU",
        )
        idx = append_action_to_event(event, action)

        # Per Q4: en bloc — single acceptance creates the recurring pairing.
        result = commit_action(
            db_session,
            event=event,
            action_idx=idx,
            outcome="accept",
            actor_user_id=user.id,
            actor_email=user.email,
        )
        assert result.target_status == "paired_recurring"
        db_session.refresh(pairing)
        assert pairing.paired_at is not None


# ─────────────────────────────────────────────────────────────────────
# Event reschedule proposal commit handler
# ─────────────────────────────────────────────────────────────────────


class TestEventRescheduleProposal:
    def test_accept_propagates_event_time(self, db_session):
        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        event = make_event(db_session, account, status="confirmed")

        new_start = datetime(2026, 6, 5, 16, tzinfo=timezone.utc)
        new_end = datetime(2026, 6, 5, 17, tzinfo=timezone.utc)
        action = build_event_reschedule_proposal_action(
            event_id=event.id,
            proposed_start_at=new_start,
            proposed_end_at=new_end,
            proposed_location=None,
            proposing_tenant_name="T",
        )
        idx = append_action_to_event(event, action)

        result = commit_action(
            db_session,
            event=event,
            action_idx=idx,
            outcome="accept",
            actor_user_id=user.id,
            actor_email=user.email,
        )
        assert result.updated_action["action_status"] == "accepted"
        db_session.refresh(event)
        assert event.start_at == new_start
        assert event.end_at == new_end

    def test_target_id_must_match_event(self, db_session):
        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        event = make_event(db_session, account)

        # Build action with mismatched target_id.
        action = build_event_reschedule_proposal_action(
            event_id="different-event-id",
            proposed_start_at=event.start_at,
            proposed_end_at=event.end_at,
            proposed_location=None,
            proposing_tenant_name="T",
        )
        idx = append_action_to_event(event, action)

        with pytest.raises(ActionError):
            commit_action(
                db_session,
                event=event,
                action_idx=idx,
                outcome="accept",
                actor_user_id=user.id,
                actor_email=user.email,
            )

    def test_compute_reschedule_cascade(self, db_session):
        from app.models.calendar_primitive import CalendarEventLinkage

        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        event = make_event(db_session, account)

        # Add 2 linkages
        for _ in range(2):
            db_session.add(
                CalendarEventLinkage(
                    id=str(uuid.uuid4()),
                    event_id=event.id,
                    tenant_id=tenant.id,
                    linked_entity_type="sales_order",
                    linked_entity_id=str(uuid.uuid4()),
                    linkage_source="manual_pre_link",
                )
            )
        db_session.flush()

        cascade = compute_reschedule_cascade(db_session, event)
        assert cascade["linked_entity_count"] == 2
        assert cascade["paired_cross_tenant_count"] == 0


# ─────────────────────────────────────────────────────────────────────
# Counter-proposal chaining helper
# ─────────────────────────────────────────────────────────────────────


class TestCounterProposalChaining:
    def test_chain_appends_at_next_index(self, db_session):
        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        event = make_event(db_session, account)
        original = build_service_date_acceptance_action(
            fh_case_id="c1",
            proposed_start_at=datetime(2026, 6, 1, 14, tzinfo=timezone.utc),
            proposed_end_at=datetime(2026, 6, 1, 15, tzinfo=timezone.utc),
            proposed_location="orig",
            proposing_tenant_name="Sunnycrest",
        )
        append_action_to_event(event, original)
        new_action, idx = chain_counter_proposal(
            event=event,
            original_action=original,
            counter_start_at=datetime(2026, 6, 2, 14, tzinfo=timezone.utc),
            counter_end_at=datetime(2026, 6, 2, 15, tzinfo=timezone.utc),
            counter_note="Tuesday works better",
            proposing_tenant_name="Hopkins",
        )
        assert idx == 1
        assert new_action["action_status"] == "pending"
        assert new_action["action_metadata"]["is_counter_proposal"] is True
        assert new_action["action_metadata"]["proposed_location"] == "orig"
