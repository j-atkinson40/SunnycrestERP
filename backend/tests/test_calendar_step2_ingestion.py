"""Calendar Step 2 — ingestion pipeline tests.

Covers idempotency + cross-tenant detection + linkage auto-resolution.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.database import SessionLocal
from app.models import Company, CompanyEntity, Role, User
from app.models.calendar_primitive import (
    CalendarAccount,
    CalendarEvent,
    CalendarEventAttendee,
)
from app.services.calendar.ingestion import ingest_provider_event
from app.services.calendar.providers.base import (
    ProviderAttendeeRef,
    ProviderFetchedEvent,
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
        name=f"Ingest {_uuid.uuid4().hex[:8]}",
        slug=f"ing{_uuid.uuid4().hex[:8]}",
        vertical="manufacturing",
    )
    db_session.add(co)
    db_session.flush()
    return co


@pytest.fixture
def other_tenant(db_session):
    import uuid as _uuid

    co = Company(
        id=str(_uuid.uuid4()),
        name=f"Other {_uuid.uuid4().hex[:8]}",
        slug=f"oth{_uuid.uuid4().hex[:8]}",
        vertical="manufacturing",
    )
    db_session.add(co)
    db_session.flush()
    return co


@pytest.fixture
def admin_user(db_session, tenant):
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
        email=f"admin-{_uuid.uuid4().hex[:8]}@ing.test",
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


@pytest.fixture
def account(db_session, tenant, admin_user):
    import uuid as _uuid

    acc = CalendarAccount(
        id=str(_uuid.uuid4()),
        tenant_id=tenant.id,
        account_type="shared",
        display_name="Ingest Test",
        primary_email_address=f"ing-{_uuid.uuid4().hex[:8]}@ing.test",
        provider_type="google_calendar",
        created_by_user_id=admin_user.id,
    )
    db_session.add(acc)
    db_session.flush()
    return acc


def _make_provider_event(
    *,
    provider_event_id: str = "evt-1",
    subject: str = "Test event",
    start: datetime | None = None,
    end: datetime | None = None,
    attendees: list[ProviderAttendeeRef] | None = None,
    recurrence_rule: str | None = None,
) -> ProviderFetchedEvent:
    start = start or datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc)
    end = end or datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc)
    return ProviderFetchedEvent(
        provider_event_id=provider_event_id,
        provider_calendar_id="primary",
        subject=subject,
        start_at=start,
        end_at=end,
        is_all_day=False,
        event_timezone="UTC",
        recurrence_rule=recurrence_rule,
        status="confirmed",
        transparency="opaque",
        attendees=attendees or [],
    )


# ─────────────────────────────────────────────────────────────────────
# Idempotency
# ─────────────────────────────────────────────────────────────────────


class TestIdempotency:
    def test_re_ingest_same_provider_id_updates_existing(
        self, db_session, account
    ):
        first = ingest_provider_event(
            db_session,
            account=account,
            provider_event=_make_provider_event(
                provider_event_id="dup-1", subject="Original"
            ),
        )
        assert first.subject == "Original"

        second = ingest_provider_event(
            db_session,
            account=account,
            provider_event=_make_provider_event(
                provider_event_id="dup-1", subject="Updated"
            ),
        )
        # Same row id (UPDATE not INSERT).
        assert second.id == first.id
        db_session.refresh(second)
        assert second.subject == "Updated"

    def test_distinct_provider_ids_create_distinct_rows(
        self, db_session, account
    ):
        e1 = ingest_provider_event(
            db_session,
            account=account,
            provider_event=_make_provider_event(provider_event_id="a"),
        )
        e2 = ingest_provider_event(
            db_session,
            account=account,
            provider_event=_make_provider_event(provider_event_id="b"),
        )
        assert e1.id != e2.id

    def test_recurring_event_recurrence_rule_persisted_verbatim(
        self, db_session, account
    ):
        rrule = "RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR"
        event = ingest_provider_event(
            db_session,
            account=account,
            provider_event=_make_provider_event(
                provider_event_id="rec-1",
                subject="MWF Standup",
                recurrence_rule=rrule,
            ),
        )
        assert event.recurrence_rule == rrule


# ─────────────────────────────────────────────────────────────────────
# Cross-tenant detection
# ─────────────────────────────────────────────────────────────────────


class TestCrossTenantDetection:
    def test_attendee_in_other_tenant_marks_cross_tenant(
        self, db_session, account, other_tenant
    ):
        import uuid as _uuid

        # Seed a User in other_tenant with a known email.
        other_role = Role(
            id=str(_uuid.uuid4()),
            company_id=other_tenant.id,
            name="Admin",
            slug="admin",
            is_system=True,
        )
        db_session.add(other_role)
        db_session.flush()
        other_user = User(
            id=str(_uuid.uuid4()),
            email="partner@other-tenant.test",
            hashed_password="x",
            first_name="P",
            last_name="U",
            company_id=other_tenant.id,
            role_id=other_role.id,
            is_active=True,
        )
        db_session.add(other_user)
        db_session.flush()

        attendees = [
            ProviderAttendeeRef(
                email_address="partner@other-tenant.test",
                role="required_attendee",
                response_status="accepted",
            )
        ]
        event = ingest_provider_event(
            db_session,
            account=account,
            provider_event=_make_provider_event(
                provider_event_id="ct-1", attendees=attendees
            ),
        )
        db_session.refresh(event)
        assert event.is_cross_tenant is True

        # Attendee row carries external_tenant_id.
        att_row = (
            db_session.query(CalendarEventAttendee)
            .filter(
                CalendarEventAttendee.event_id == event.id,
                CalendarEventAttendee.email_address
                == "partner@other-tenant.test",
            )
            .first()
        )
        assert att_row is not None
        assert att_row.external_tenant_id == other_tenant.id

    def test_internal_attendee_does_not_mark_cross_tenant(
        self, db_session, account
    ):
        attendees = [
            ProviderAttendeeRef(
                email_address="external-only@example.com",
                role="required_attendee",
            )
        ]
        event = ingest_provider_event(
            db_session,
            account=account,
            provider_event=_make_provider_event(
                provider_event_id="non-ct-1", attendees=attendees
            ),
        )
        db_session.refresh(event)
        assert event.is_cross_tenant is False


# ─────────────────────────────────────────────────────────────────────
# Linkage auto-resolution to CompanyEntity
# ─────────────────────────────────────────────────────────────────────


class TestCompanyEntityResolution:
    def test_attendee_email_matches_company_entity(
        self, db_session, account, tenant
    ):
        import uuid as _uuid

        entity = CompanyEntity(
            id=str(_uuid.uuid4()),
            company_id=tenant.id,
            name="Hopkins Funeral Home",
            email="contact@hopkins-fh.test",
            is_funeral_home=True,
            customer_type="funeral_home",
        )
        db_session.add(entity)
        db_session.flush()

        attendees = [
            ProviderAttendeeRef(
                email_address="contact@hopkins-fh.test",
                role="required_attendee",
            )
        ]
        event = ingest_provider_event(
            db_session,
            account=account,
            provider_event=_make_provider_event(
                provider_event_id="link-1", attendees=attendees
            ),
        )
        db_session.refresh(event)

        att_row = (
            db_session.query(CalendarEventAttendee)
            .filter(CalendarEventAttendee.event_id == event.id)
            .first()
        )
        assert att_row is not None
        assert att_row.resolved_company_entity_id == entity.id


# ─────────────────────────────────────────────────────────────────────
# Reconcile on update (provider source of truth for membership)
# ─────────────────────────────────────────────────────────────────────


class TestReconcileOnUpdate:
    def test_attendee_removed_on_provider_drop(self, db_session, account):
        # First ingest — 2 attendees.
        attendees_1 = [
            ProviderAttendeeRef(email_address="a@example.com"),
            ProviderAttendeeRef(email_address="b@example.com"),
        ]
        event = ingest_provider_event(
            db_session,
            account=account,
            provider_event=_make_provider_event(
                provider_event_id="reconcile-1", attendees=attendees_1
            ),
        )
        db_session.refresh(event)
        assert len(event.attendees) == 2

        # Re-ingest — 1 attendee (b dropped from provider).
        attendees_2 = [ProviderAttendeeRef(email_address="a@example.com")]
        ingest_provider_event(
            db_session,
            account=account,
            provider_event=_make_provider_event(
                provider_event_id="reconcile-1", attendees=attendees_2
            ),
        )
        db_session.refresh(event)
        emails = {a.email_address for a in event.attendees}
        assert emails == {"a@example.com"}
