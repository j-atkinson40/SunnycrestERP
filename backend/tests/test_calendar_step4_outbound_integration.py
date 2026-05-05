"""Calendar Step 4 — outbound iTIP REQUEST integration tests.

Per Q5 confirmed pre-build: outbound_service.send_event embeds magic-
link tokens for non-Bridgeable attendees automatically (default-on
with embed_magic_links=False opt-out).

Coverage:
  - Non-Bridgeable attendee detection (CalendarEventAttendee.is_internal=False)
  - Token issuance + URL composition for external attendees
  - Internal attendees do NOT receive magic-links
  - embed_magic_links=False suppresses issuance
  - Empty attendee list is no-op
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

# Ensure Calendar package init runs.
from app.services import calendar as _cal_pkg  # noqa: F401
from app.models.calendar_primitive import CalendarAccountAccess
from app.services.calendar import calendar_action_service, outbound_service
from app.services.calendar.calendar_action_service import (
    append_action_to_event,
    build_service_date_acceptance_action,
)

from tests._calendar_step4_fixtures import (
    db_session,  # noqa: F401
    make_account,
    make_attendee,
    make_event,
    make_tenant,
    make_user,
)


def _grant_admin(db_session, account, user):
    grant = CalendarAccountAccess(
        id=str(uuid.uuid4()),
        account_id=account.id,
        user_id=user.id,
        tenant_id=account.tenant_id,
        access_level="admin",
    )
    db_session.add(grant)
    db_session.flush()


# ─────────────────────────────────────────────────────────────────────
# Magic-link issuance for external attendees
# ─────────────────────────────────────────────────────────────────────


class TestMagicLinkEmbedding:
    def test_external_attendee_receives_magic_link(self, db_session):
        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        _grant_admin(db_session, account, user)

        event = make_event(db_session, account, status="tentative")
        # External attendee (is_internal=False)
        external = make_attendee(
            db_session,
            event,
            email_address="fh@hopkins.test",
            is_internal=False,
        )
        # Append a pending action so magic-link has a target.
        action = build_service_date_acceptance_action(
            fh_case_id=str(uuid.uuid4()),
            proposed_start_at=event.start_at,
            proposed_end_at=event.end_at,
            proposed_location="Hopkins chapel",
            proposing_tenant_name="Sunnycrest",
        )
        append_action_to_event(event, action)
        db_session.flush()

        result = outbound_service.send_event(
            db_session,
            event=event,
            sender=user,
        )
        magic_links = result["magic_links"]
        assert len(magic_links) == 1
        assert magic_links[0]["recipient_email"] == "fh@hopkins.test"
        assert magic_links[0]["action_type"] == "service_date_acceptance"
        assert "/calendar/actions/" in magic_links[0]["url"]

    def test_internal_attendee_does_not_receive_magic_link(self, db_session):
        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        _grant_admin(db_session, account, user)

        event = make_event(db_session, account, status="tentative")
        make_attendee(
            db_session,
            event,
            email_address="internal@sunnycrest.test",
            is_internal=True,
        )
        action = build_service_date_acceptance_action(
            fh_case_id=str(uuid.uuid4()),
            proposed_start_at=event.start_at,
            proposed_end_at=event.end_at,
            proposed_location="loc",
            proposing_tenant_name="Sunnycrest",
        )
        append_action_to_event(event, action)
        db_session.flush()

        result = outbound_service.send_event(
            db_session,
            event=event,
            sender=user,
        )
        # Internal attendees skipped per §3.26.11.9 (have full Bridgeable access).
        assert result["magic_links"] == []

    def test_mixed_attendees_only_external_get_links(self, db_session):
        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        _grant_admin(db_session, account, user)

        event = make_event(db_session, account, status="tentative")
        make_attendee(
            db_session,
            event,
            email_address="internal@sunnycrest.test",
            is_internal=True,
        )
        make_attendee(
            db_session,
            event,
            email_address="ext1@partner.test",
            is_internal=False,
        )
        make_attendee(
            db_session,
            event,
            email_address="ext2@partner.test",
            is_internal=False,
        )
        action = build_service_date_acceptance_action(
            fh_case_id=str(uuid.uuid4()),
            proposed_start_at=event.start_at,
            proposed_end_at=event.end_at,
            proposed_location="loc",
            proposing_tenant_name="Sunnycrest",
        )
        append_action_to_event(event, action)
        db_session.flush()

        result = outbound_service.send_event(
            db_session,
            event=event,
            sender=user,
        )
        emails = {m["recipient_email"] for m in result["magic_links"]}
        assert emails == {"ext1@partner.test", "ext2@partner.test"}

    def test_embed_magic_links_false_suppresses(self, db_session):
        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        _grant_admin(db_session, account, user)

        event = make_event(db_session, account, status="tentative")
        make_attendee(
            db_session,
            event,
            email_address="ext@partner.test",
            is_internal=False,
        )
        action = build_service_date_acceptance_action(
            fh_case_id=str(uuid.uuid4()),
            proposed_start_at=event.start_at,
            proposed_end_at=event.end_at,
            proposed_location="loc",
            proposing_tenant_name="Sunnycrest",
        )
        append_action_to_event(event, action)
        db_session.flush()

        result = outbound_service.send_event(
            db_session,
            event=event,
            sender=user,
            embed_magic_links=False,  # opt-out
        )
        assert result["magic_links"] == []

    def test_no_pending_action_no_links_issued(self, db_session):
        # Event with no actions in payload — no magic-links to embed.
        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        _grant_admin(db_session, account, user)

        event = make_event(db_session, account, status="tentative")
        make_attendee(
            db_session,
            event,
            email_address="ext@partner.test",
            is_internal=False,
        )
        # No append_action_to_event — action_payload is empty.
        result = outbound_service.send_event(
            db_session,
            event=event,
            sender=user,
        )
        assert result["magic_links"] == []

    def test_magic_link_action_type_override(self, db_session):
        # Caller supplies magic_link_action_type when no actions in
        # payload yet (e.g. counter-proposal chaining bridge).
        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        _grant_admin(db_session, account, user)

        event = make_event(db_session, account, status="tentative")
        make_attendee(
            db_session,
            event,
            email_address="ext@partner.test",
            is_internal=False,
        )
        result = outbound_service.send_event(
            db_session,
            event=event,
            sender=user,
            magic_link_action_type="joint_event_acceptance",
        )
        assert len(result["magic_links"]) == 1
        assert (
            result["magic_links"][0]["action_type"]
            == "joint_event_acceptance"
        )

    def test_invalid_magic_link_action_type_skipped(self, db_session):
        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        _grant_admin(db_session, account, user)

        event = make_event(db_session, account, status="tentative")
        make_attendee(
            db_session,
            event,
            email_address="ext@partner.test",
            is_internal=False,
        )
        # Caller-supplied invalid action_type — handler logs + skips.
        result = outbound_service.send_event(
            db_session,
            event=event,
            sender=user,
            magic_link_action_type="not_a_real_calendar_action",
        )
        assert result["magic_links"] == []

    def test_audit_log_records_magic_links_count(self, db_session):
        from app.models.calendar_primitive import CalendarAuditLog

        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        _grant_admin(db_session, account, user)

        event = make_event(db_session, account, status="tentative")
        make_attendee(
            db_session,
            event,
            email_address="ext@partner.test",
            is_internal=False,
        )
        action = build_service_date_acceptance_action(
            fh_case_id="c",
            proposed_start_at=event.start_at,
            proposed_end_at=event.end_at,
            proposed_location="loc",
            proposing_tenant_name="T",
        )
        append_action_to_event(event, action)
        db_session.flush()

        outbound_service.send_event(db_session, event=event, sender=user)

        sent_audit = (
            db_session.query(CalendarAuditLog)
            .filter(
                CalendarAuditLog.entity_id == event.id,
                CalendarAuditLog.action == "event_sent",
            )
            .first()
        )
        assert sent_audit is not None
        assert (sent_audit.changes or {}).get("magic_links_issued") == 1
