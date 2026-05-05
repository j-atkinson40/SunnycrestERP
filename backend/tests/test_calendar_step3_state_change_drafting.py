"""Calendar Step 3 — state-change drafting canonical 7-mapping tests.

Per §3.26.16.18:
  - Canonical 7 mappings: sales_order / fh_case / quote / work_order /
    equipment / compliance_requirement / disinterment.
  - Auto-confirmation rules: internal-only auto-confirms; cross-tenant
    canonical mappings (fh_case, disinterment) require manual review;
    external attendees disable auto-confirmation.
  - Drafted-not-auto-sent: events default tentative; status flip to
    confirmed only when auto-confirmation rule applies.
  - Audit trail: every drafted event writes a calendar_audit_log row
    with generation_source provenance.
  - Linkage: every drafted event has a CalendarEventLinkage row to the
    operational entity.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.database import SessionLocal
from app.models import Company, Role, User
from app.models.calendar_primitive import (
    CalendarAccount,
    CalendarAuditLog,
    CalendarEvent,
    CalendarEventAttendee,
    CalendarEventLinkage,
)
from app.services.calendar.state_change_drafting import (
    CANONICAL_MAPPINGS,
    DraftEventRequest,
    draft_event_from_state_change,
    get_mapping,
    list_drafted_state_change_events,
    should_auto_confirm,
)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def tenant(db_session):
    import uuid as _uuid

    co = Company(
        id=str(_uuid.uuid4()),
        name=f"SC {_uuid.uuid4().hex[:8]}",
        slug=f"sc{_uuid.uuid4().hex[:8]}",
        vertical="manufacturing",
    )
    db_session.add(co)
    db_session.flush()
    return co


@pytest.fixture
def user(db_session, tenant):
    import uuid as _uuid

    role = Role(
        id=str(_uuid.uuid4()),
        company_id=tenant.id,
        name="Admin",
        slug="admin",
        is_system=True,
    )
    db_session.add(role)
    db_session.flush()
    user = User(
        id=str(_uuid.uuid4()),
        email=f"u-{_uuid.uuid4().hex[:8]}@sc.test",
        hashed_password="x",
        first_name="S",
        last_name="C",
        company_id=tenant.id,
        role_id=role.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def account(db_session, tenant, user):
    import uuid as _uuid

    acc = CalendarAccount(
        id=str(_uuid.uuid4()),
        tenant_id=tenant.id,
        account_type="shared",
        display_name="State Change Test",
        primary_email_address=f"sc-{_uuid.uuid4().hex[:8]}@sc.test",
        provider_type="local",
        outbound_enabled=True,
        created_by_user_id=user.id,
    )
    db_session.add(acc)
    db_session.flush()
    return acc


# ─────────────────────────────────────────────────────────────────────
# Canonical 7-mapping registry
# ─────────────────────────────────────────────────────────────────────


class TestCanonicalMappings:
    def test_all_seven_mappings_present(self):
        expected = {
            "sales_order",
            "fh_case",
            "quote",
            "work_order",
            "equipment",
            "compliance_requirement",
            "disinterment",
        }
        assert set(CANONICAL_MAPPINGS.keys()) == expected

    def test_compliance_requirement_uses_30_day_lead(self):
        m = get_mapping("compliance_requirement")
        assert m is not None
        assert m.days_before_event == 30

    def test_fh_case_is_cross_tenant(self):
        # Per §3.26.16.18 row 2: cross-tenant invitation to manufacturer.
        m = get_mapping("fh_case")
        assert m is not None
        assert m.cross_tenant is True

    def test_disinterment_is_cross_tenant(self):
        # Per §3.26.16.18 row 7: cross-tenant FH+cemetery+driver.
        m = get_mapping("disinterment")
        assert m is not None
        assert m.cross_tenant is True

    def test_sales_order_is_internal_only(self):
        m = get_mapping("sales_order")
        assert m is not None
        assert m.cross_tenant is False
        assert m.days_before_event == 0

    def test_get_mapping_unknown_returns_none(self):
        assert get_mapping("not_a_real_entity") is None


# ─────────────────────────────────────────────────────────────────────
# Auto-confirmation rules
# ─────────────────────────────────────────────────────────────────────


class TestAutoConfirmationRules:
    def test_internal_only_non_cross_tenant_auto_confirms(self):
        m = get_mapping("sales_order")
        assert should_auto_confirm(
            mapping=m,
            has_external_attendees=False,
            has_cross_tenant_attendees=False,
        )

    def test_cross_tenant_canonical_mapping_disables_auto_confirm(self):
        # fh_case is canonically cross-tenant per §3.26.16.18.
        m = get_mapping("fh_case")
        assert (
            should_auto_confirm(
                mapping=m,
                has_external_attendees=False,
                has_cross_tenant_attendees=False,
            )
            is False
        )

    def test_external_attendees_disable_auto_confirm(self):
        m = get_mapping("sales_order")
        assert (
            should_auto_confirm(
                mapping=m,
                has_external_attendees=True,
                has_cross_tenant_attendees=False,
            )
            is False
        )

    def test_cross_tenant_attendees_disable_auto_confirm(self):
        m = get_mapping("sales_order")
        assert (
            should_auto_confirm(
                mapping=m,
                has_external_attendees=False,
                has_cross_tenant_attendees=True,
            )
            is False
        )


# ─────────────────────────────────────────────────────────────────────
# draft_event_from_state_change
# ─────────────────────────────────────────────────────────────────────


class TestDraftEventFromStateChange:
    def test_sales_order_internal_auto_confirms(
        self, db_session, account, user
    ):
        request = DraftEventRequest(
            source_entity_type="sales_order",
            source_entity_id="so-123",
            source_entity_label="Hopkins #SO-2026-0001",
            date_at=datetime(2026, 6, 15, 14, 0, tzinfo=timezone.utc),
            duration_minutes=60,
            attendee_emails=["dispatcher@org.test"],
            tenant_id=account.tenant_id,
            actor_user_id=user.id,
        )
        event = draft_event_from_state_change(
            db_session, request=request, account=account
        )

        assert event.status == "confirmed"
        assert event.generation_source == "state_change"
        assert event.generation_entity_type == "sales_order"
        assert event.generation_entity_id == "so-123"
        assert event.subject == "Delivery: Hopkins #SO-2026-0001"
        assert event.start_at == datetime(2026, 6, 15, 14, 0, tzinfo=timezone.utc)
        assert event.end_at == datetime(2026, 6, 15, 15, 0, tzinfo=timezone.utc)

    def test_fh_case_cross_tenant_drafts_tentative(
        self, db_session, account, user
    ):
        request = DraftEventRequest(
            source_entity_type="fh_case",
            source_entity_id="case-456",
            source_entity_label="Smith family service",
            date_at=datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc),
            duration_minutes=120,
            attendee_emails=["fh@hopkins.test"],
            tenant_id=account.tenant_id,
            actor_user_id=user.id,
        )
        event = draft_event_from_state_change(
            db_session, request=request, account=account
        )

        # Cross-tenant disables auto-confirmation per §3.26.16.18.
        assert event.status == "tentative"
        assert event.is_cross_tenant is True

    def test_compliance_requirement_subtracts_30_days(
        self, db_session, account, user
    ):
        # date_at is the expiry date; event start_at = expiry - 30 days.
        expiry = datetime(2026, 12, 31, 12, 0, tzinfo=timezone.utc)
        request = DraftEventRequest(
            source_entity_type="compliance_requirement",
            source_entity_id="comp-789",
            source_entity_label="OSHA 300 filing",
            date_at=expiry,
            duration_minutes=30,
            attendee_emails=["compliance@org.test"],
            tenant_id=account.tenant_id,
            actor_user_id=user.id,
        )
        event = draft_event_from_state_change(
            db_session, request=request, account=account
        )

        expected_start = expiry - timedelta(days=30)
        assert event.start_at == expected_start
        assert event.status == "confirmed"  # internal-only

    def test_external_attendees_disable_auto_confirm(
        self, db_session, account, user
    ):
        request = DraftEventRequest(
            source_entity_type="sales_order",
            source_entity_id="so-ext-1",
            source_entity_label="Acme",
            date_at=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
            attendee_emails=["dispatcher@org.test"],
            external_attendee_emails=["customer@acme.test"],
            tenant_id=account.tenant_id,
            actor_user_id=user.id,
        )
        event = draft_event_from_state_change(
            db_session, request=request, account=account
        )
        # External attendee disables auto-confirmation.
        assert event.status == "tentative"

    def test_attendees_partitioned_internal_vs_external(
        self, db_session, account, user
    ):
        request = DraftEventRequest(
            source_entity_type="sales_order",
            source_entity_id="so-att-1",
            source_entity_label="Acme",
            date_at=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
            attendee_emails=["a@org.test", "b@org.test"],
            external_attendee_emails=["x@partner.test"],
            tenant_id=account.tenant_id,
            actor_user_id=user.id,
        )
        event = draft_event_from_state_change(
            db_session, request=request, account=account
        )
        attendees = (
            db_session.query(CalendarEventAttendee)
            .filter(CalendarEventAttendee.event_id == event.id)
            .all()
        )
        internal = {a.email_address for a in attendees if a.is_internal}
        external = {a.email_address for a in attendees if not a.is_internal}
        assert internal == {"a@org.test", "b@org.test"}
        assert external == {"x@partner.test"}

    def test_creates_linkage_row(self, db_session, account, user):
        request = DraftEventRequest(
            source_entity_type="quote",
            source_entity_id="quote-555",
            source_entity_label="Quote 555",
            date_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
            tenant_id=account.tenant_id,
            actor_user_id=user.id,
        )
        event = draft_event_from_state_change(
            db_session, request=request, account=account
        )
        linkage = (
            db_session.query(CalendarEventLinkage)
            .filter(CalendarEventLinkage.event_id == event.id)
            .first()
        )
        assert linkage is not None
        assert linkage.linked_entity_type == "quote"
        assert linkage.linked_entity_id == "quote-555"

    def test_writes_audit_row_with_provenance(
        self, db_session, account, user
    ):
        request = DraftEventRequest(
            source_entity_type="sales_order",
            source_entity_id="so-audit-1",
            source_entity_label="Audit test",
            date_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
            tenant_id=account.tenant_id,
            actor_user_id=user.id,
        )
        event = draft_event_from_state_change(
            db_session, request=request, account=account
        )
        rows = (
            db_session.query(CalendarAuditLog)
            .filter(
                CalendarAuditLog.entity_id == event.id,
                CalendarAuditLog.action == "event_drafted_from_state_change",
            )
            .all()
        )
        assert len(rows) == 1
        changes = rows[0].changes or {}
        assert changes.get("generation_source") == "state_change"
        assert changes.get("source_entity_type") == "sales_order"
        assert changes.get("source_entity_id") == "so-audit-1"
        assert "auto_confirmed" in changes

    def test_unknown_source_entity_type_raises(
        self, db_session, account, user
    ):
        request = DraftEventRequest(
            source_entity_type="not_a_real_entity",
            source_entity_id="bogus",
            source_entity_label="Bogus",
            date_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
            tenant_id=account.tenant_id,
            actor_user_id=user.id,
        )
        with pytest.raises(ValueError):
            draft_event_from_state_change(
                db_session, request=request, account=account
            )


# ─────────────────────────────────────────────────────────────────────
# Drafted-event review queue
# ─────────────────────────────────────────────────────────────────────


class TestDraftedEventReviewQueue:
    def test_lists_only_tentative_state_change_events(
        self, db_session, account, user
    ):
        # Tentative + state_change → in queue.
        req_a = DraftEventRequest(
            source_entity_type="fh_case",  # cross-tenant → tentative
            source_entity_id="case-q-1",
            source_entity_label="Family A",
            date_at=datetime(2026, 6, 15, 10, tzinfo=timezone.utc),
            tenant_id=account.tenant_id,
            actor_user_id=user.id,
        )
        ev_a = draft_event_from_state_change(
            db_session, request=req_a, account=account
        )
        # Confirmed → NOT in queue (sales_order auto-confirms).
        req_b = DraftEventRequest(
            source_entity_type="sales_order",
            source_entity_id="so-q-2",
            source_entity_label="Order B",
            date_at=datetime(2026, 6, 16, 10, tzinfo=timezone.utc),
            tenant_id=account.tenant_id,
            actor_user_id=user.id,
        )
        ev_b = draft_event_from_state_change(
            db_session, request=req_b, account=account
        )

        queue = list_drafted_state_change_events(
            db_session, tenant_id=account.tenant_id
        )
        ids = {e.id for e in queue}
        assert ev_a.id in ids
        assert ev_b.id not in ids

    def test_orders_by_start_at_ascending(
        self, db_session, account, user
    ):
        req_later = DraftEventRequest(
            source_entity_type="fh_case",
            source_entity_id="case-late",
            source_entity_label="Later",
            date_at=datetime(2026, 8, 1, 10, tzinfo=timezone.utc),
            tenant_id=account.tenant_id,
            actor_user_id=user.id,
        )
        req_sooner = DraftEventRequest(
            source_entity_type="fh_case",
            source_entity_id="case-soon",
            source_entity_label="Sooner",
            date_at=datetime(2026, 6, 1, 10, tzinfo=timezone.utc),
            tenant_id=account.tenant_id,
            actor_user_id=user.id,
        )
        ev_late = draft_event_from_state_change(
            db_session, request=req_later, account=account
        )
        ev_soon = draft_event_from_state_change(
            db_session, request=req_sooner, account=account
        )

        queue = list_drafted_state_change_events(
            db_session, tenant_id=account.tenant_id
        )
        # Soonest first.
        ordered_ids = [
            e.id for e in queue if e.id in {ev_late.id, ev_soon.id}
        ]
        assert ordered_ids[0] == ev_soon.id
        assert ordered_ids[1] == ev_late.id

    def test_queue_scoped_to_tenant(self, db_session, account, user):
        # Create a separate tenant + drafted tentative event.
        import uuid as _uuid

        co2 = Company(
            id=str(_uuid.uuid4()),
            name=f"Other {_uuid.uuid4().hex[:8]}",
            slug=f"oth{_uuid.uuid4().hex[:8]}",
            vertical="manufacturing",
        )
        db_session.add(co2)
        db_session.flush()
        role2 = Role(
            id=str(_uuid.uuid4()),
            company_id=co2.id,
            name="Admin",
            slug="admin",
            is_system=True,
        )
        db_session.add(role2)
        db_session.flush()
        user2 = User(
            id=str(_uuid.uuid4()),
            email=f"x-{_uuid.uuid4().hex[:8]}@y.test",
            hashed_password="x",
            first_name="O",
            last_name="U",
            company_id=co2.id,
            role_id=role2.id,
            is_active=True,
        )
        db_session.add(user2)
        db_session.flush()
        acc2 = CalendarAccount(
            id=str(_uuid.uuid4()),
            tenant_id=co2.id,
            account_type="shared",
            display_name="Other",
            primary_email_address=f"o-{_uuid.uuid4().hex[:8]}@y.test",
            provider_type="local",
            created_by_user_id=user2.id,
        )
        db_session.add(acc2)
        db_session.flush()

        # Other tenant draft.
        other_req = DraftEventRequest(
            source_entity_type="fh_case",
            source_entity_id="case-other",
            source_entity_label="Other",
            date_at=datetime(2026, 6, 15, 10, tzinfo=timezone.utc),
            tenant_id=co2.id,
            actor_user_id=user2.id,
        )
        ev_other = draft_event_from_state_change(
            db_session, request=other_req, account=acc2
        )

        # Caller tenant draft.
        caller_req = DraftEventRequest(
            source_entity_type="fh_case",
            source_entity_id="case-caller",
            source_entity_label="Caller",
            date_at=datetime(2026, 6, 16, 10, tzinfo=timezone.utc),
            tenant_id=account.tenant_id,
            actor_user_id=user.id,
        )
        ev_caller = draft_event_from_state_change(
            db_session, request=caller_req, account=account
        )

        queue = list_drafted_state_change_events(
            db_session, tenant_id=account.tenant_id
        )
        ids = {e.id for e in queue}
        assert ev_caller.id in ids
        assert ev_other.id not in ids
