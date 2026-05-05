"""Calendar Step 2 — recurrence_engine canonical RFC 5545 patterns.

The architectural keystone of Step 2. Tests cover the canonical patterns
required by §3.26.16.4 RRULE-as-source-of-truth:

  - Non-recurring events (single materialized instance when overlapping range)
  - WEEKLY recurrence
  - MONTHLY BYMONTHDAY
  - MONTHLY BYDAY (e.g. 2nd Tuesday)
  - YEARLY
  - EXDATE handling (canonical RFC 5545 + dateutil multi-line block)
  - COUNT termination
  - UNTIL termination
  - Modified-instance shadowing via calendar_event_instance_overrides
  - Cancelled-instance hiding (is_cancelled=True override)
  - max_count cap (defensive against FREQ=SECONDLY)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.database import SessionLocal
from app.models import Company, Role, User
from app.models.calendar_primitive import (
    CalendarAccount,
    CalendarEvent,
    CalendarEventInstanceOverride,
)
from app.services.calendar.recurrence_engine import (
    DEFAULT_MAX_INSTANCES,
    MaterializedInstance,
    materialize_instances,
    materialize_instances_for_events,
)


# ─────────────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────────────


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

    company = Company(
        id=str(_uuid.uuid4()),
        name=f"RR Test Tenant {_uuid.uuid4().hex[:8]}",
        slug=f"rrtest{_uuid.uuid4().hex[:8]}",
        vertical="manufacturing",
    )
    db_session.add(company)
    db_session.flush()
    return company


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
        email=f"rr-{_uuid.uuid4().hex[:8]}@rrtest.test",
        hashed_password="x",
        first_name="RR",
        last_name="User",
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
        display_name="RR Test Account",
        primary_email_address=f"rr-{_uuid.uuid4().hex[:8]}@rrtest.test",
        provider_type="local",
        created_by_user_id=admin_user.id,
    )
    db_session.add(acc)
    db_session.flush()
    return acc


def _make_event(
    db_session,
    account,
    *,
    subject: str,
    start_at: datetime,
    end_at: datetime,
    recurrence_rule: str | None = None,
    status: str = "confirmed",
    transparency: str = "opaque",
) -> CalendarEvent:
    import uuid as _uuid

    event = CalendarEvent(
        id=str(_uuid.uuid4()),
        tenant_id=account.tenant_id,
        account_id=account.id,
        subject=subject,
        start_at=start_at,
        end_at=end_at,
        event_timezone="UTC",
        recurrence_rule=recurrence_rule,
        status=status,
        transparency=transparency,
    )
    db_session.add(event)
    db_session.flush()
    return event


# ─────────────────────────────────────────────────────────────────────
# Non-recurring events
# ─────────────────────────────────────────────────────────────────────


class TestNonRecurringExpansion:
    def test_single_event_overlapping_range_returns_one_instance(
        self, db_session, account
    ):
        event = _make_event(
            db_session,
            account,
            subject="One-off",
            start_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
        )
        result = materialize_instances(
            db_session,
            event=event,
            range_start=datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc),
            range_end=datetime(2026, 6, 2, 0, 0, tzinfo=timezone.utc),
        )
        assert len(result) == 1
        assert result[0].event_id == event.id
        assert result[0].is_modified is False
        assert result[0].start_at == event.start_at
        assert result[0].end_at == event.end_at

    def test_event_outside_range_returns_empty(self, db_session, account):
        event = _make_event(
            db_session,
            account,
            subject="Outside",
            start_at=datetime(2026, 7, 1, 14, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 7, 1, 15, 0, tzinfo=timezone.utc),
        )
        result = materialize_instances(
            db_session,
            event=event,
            range_start=datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc),
            range_end=datetime(2026, 6, 2, 0, 0, tzinfo=timezone.utc),
        )
        assert result == []


# ─────────────────────────────────────────────────────────────────────
# Recurring patterns
# ─────────────────────────────────────────────────────────────────────


class TestRecurringExpansion:
    def test_weekly_recurrence(self, db_session, account):
        # Tuesday 2026-06-02 at 14:00 UTC, weekly.
        event = _make_event(
            db_session,
            account,
            subject="Weekly",
            start_at=datetime(2026, 6, 2, 14, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 6, 2, 15, 0, tzinfo=timezone.utc),
            recurrence_rule="RRULE:FREQ=WEEKLY",
        )
        result = materialize_instances(
            db_session,
            event=event,
            range_start=datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc),
            range_end=datetime(2026, 6, 30, 0, 0, tzinfo=timezone.utc),
        )
        # June 2 + 9 + 16 + 23 = 4 instances within the range.
        assert len(result) == 4
        assert all(r.event_id == event.id for r in result)
        # Verify ordering.
        starts = [r.start_at for r in result]
        assert starts == sorted(starts)
        # Verify weekly cadence (each instance 7 days after prior).
        for prev, curr in zip(starts, starts[1:]):
            assert (curr - prev) == timedelta(days=7)

    def test_monthly_bymonthday(self, db_session, account):
        # 15th of each month at 10:00 UTC.
        event = _make_event(
            db_session,
            account,
            subject="Monthly 15th",
            start_at=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 1, 15, 11, 0, tzinfo=timezone.utc),
            recurrence_rule="RRULE:FREQ=MONTHLY;BYMONTHDAY=15",
        )
        result = materialize_instances(
            db_session,
            event=event,
            range_start=datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc),
            range_end=datetime(2026, 8, 31, 23, 59, tzinfo=timezone.utc),
        )
        # June 15, July 15, August 15 = 3 instances.
        assert len(result) == 3
        for r in result:
            assert r.start_at.day == 15

    def test_monthly_byday_2tu(self, db_session, account):
        # 2nd Tuesday of each month at 10:00 UTC.
        # 2026-06-09 is the 2nd Tuesday of June 2026.
        event = _make_event(
            db_session,
            account,
            subject="2nd Tuesday",
            start_at=datetime(2026, 6, 9, 10, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 6, 9, 11, 0, tzinfo=timezone.utc),
            recurrence_rule="RRULE:FREQ=MONTHLY;BYDAY=2TU",
        )
        result = materialize_instances(
            db_session,
            event=event,
            range_start=datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc),
            range_end=datetime(2026, 9, 30, 0, 0, tzinfo=timezone.utc),
        )
        # June 9, July 14, August 11, September 8 = 4 instances.
        assert len(result) == 4
        # Each instance is a Tuesday.
        for r in result:
            assert r.start_at.weekday() == 1  # Tuesday = 1

    def test_yearly_recurrence(self, db_session, account):
        event = _make_event(
            db_session,
            account,
            subject="Annual",
            start_at=datetime(2024, 6, 1, 14, 0, tzinfo=timezone.utc),
            end_at=datetime(2024, 6, 1, 15, 0, tzinfo=timezone.utc),
            recurrence_rule="RRULE:FREQ=YEARLY",
        )
        result = materialize_instances(
            db_session,
            event=event,
            range_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            range_end=datetime(2027, 1, 1, tzinfo=timezone.utc),
        )
        # 2024, 2025, 2026 = 3 instances.
        assert len(result) == 3


# ─────────────────────────────────────────────────────────────────────
# COUNT / UNTIL termination
# ─────────────────────────────────────────────────────────────────────


class TestRecurrenceTermination:
    def test_count_termination(self, db_session, account):
        # 5 weekly occurrences then stop.
        event = _make_event(
            db_session,
            account,
            subject="5 weekly",
            start_at=datetime(2026, 6, 2, 14, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 6, 2, 15, 0, tzinfo=timezone.utc),
            recurrence_rule="RRULE:FREQ=WEEKLY;COUNT=5",
        )
        result = materialize_instances(
            db_session,
            event=event,
            range_start=datetime(2026, 6, 1, tzinfo=timezone.utc),
            range_end=datetime(2026, 12, 31, tzinfo=timezone.utc),
        )
        assert len(result) == 5

    def test_until_termination(self, db_session, account):
        # Weekly until 2026-06-30 23:59:59 UTC — June 2, 9, 16, 23, 30 = 5.
        event = _make_event(
            db_session,
            account,
            subject="Until",
            start_at=datetime(2026, 6, 2, 14, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 6, 2, 15, 0, tzinfo=timezone.utc),
            recurrence_rule="RRULE:FREQ=WEEKLY;UNTIL=20260630T235959Z",
        )
        result = materialize_instances(
            db_session,
            event=event,
            range_start=datetime(2026, 6, 1, tzinfo=timezone.utc),
            range_end=datetime(2026, 12, 31, tzinfo=timezone.utc),
        )
        assert len(result) == 5


# ─────────────────────────────────────────────────────────────────────
# EXDATE handling
# ─────────────────────────────────────────────────────────────────────


class TestExdateHandling:
    def test_exdate_excludes_instances(self, db_session, account):
        # Weekly with one EXDATE excluding the 2nd occurrence (June 9).
        rrule_block = (
            "DTSTART:20260602T140000Z\n"
            "RRULE:FREQ=WEEKLY;COUNT=4\n"
            "EXDATE:20260609T140000Z"
        )
        event = _make_event(
            db_session,
            account,
            subject="Weekly w/ EXDATE",
            start_at=datetime(2026, 6, 2, 14, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 6, 2, 15, 0, tzinfo=timezone.utc),
            recurrence_rule=rrule_block,
        )
        result = materialize_instances(
            db_session,
            event=event,
            range_start=datetime(2026, 6, 1, tzinfo=timezone.utc),
            range_end=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        # COUNT=4 minus EXDATE=1 = 3 instances (June 2, 16, 23).
        assert len(result) == 3
        starts = [r.start_at for r in result]
        # The June 9 instance must be excluded.
        june_9 = datetime(2026, 6, 9, 14, 0, tzinfo=timezone.utc)
        assert june_9 not in starts


# ─────────────────────────────────────────────────────────────────────
# Modified-instance + cancelled-instance shadowing
# ─────────────────────────────────────────────────────────────────────


class TestInstanceOverrides:
    def test_cancelled_instance_excluded(self, db_session, account):
        import uuid as _uuid

        # Weekly recurrence, 4 occurrences. Cancel the 2nd (June 9).
        event = _make_event(
            db_session,
            account,
            subject="Cancelled instance",
            start_at=datetime(2026, 6, 2, 14, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 6, 2, 15, 0, tzinfo=timezone.utc),
            recurrence_rule="RRULE:FREQ=WEEKLY;COUNT=4",
        )

        cancel_override = CalendarEventInstanceOverride(
            id=str(_uuid.uuid4()),
            master_event_id=event.id,
            recurrence_instance_start_at=datetime(
                2026, 6, 9, 14, 0, tzinfo=timezone.utc
            ),
            is_cancelled=True,
        )
        db_session.add(cancel_override)
        db_session.flush()

        result = materialize_instances(
            db_session,
            event=event,
            range_start=datetime(2026, 6, 1, tzinfo=timezone.utc),
            range_end=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        # 4 RRULE instances minus 1 cancelled = 3.
        assert len(result) == 3
        starts = [r.start_at for r in result]
        june_9 = datetime(2026, 6, 9, 14, 0, tzinfo=timezone.utc)
        assert june_9 not in starts

    def test_modified_instance_uses_override_event_content(
        self, db_session, account
    ):
        import uuid as _uuid

        # Weekly recurrence, 3 occurrences. Move the 2nd occurrence
        # (originally June 9 at 14:00) to June 10 at 16:00 with a
        # different subject.
        event = _make_event(
            db_session,
            account,
            subject="Original subject",
            start_at=datetime(2026, 6, 2, 14, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 6, 2, 15, 0, tzinfo=timezone.utc),
            recurrence_rule="RRULE:FREQ=WEEKLY;COUNT=3",
        )

        override_event = CalendarEvent(
            id=str(_uuid.uuid4()),
            tenant_id=account.tenant_id,
            account_id=account.id,
            subject="Modified subject",
            start_at=datetime(2026, 6, 10, 16, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 6, 10, 17, 0, tzinfo=timezone.utc),
            recurrence_master_event_id=event.id,
            recurrence_instance_start_at=datetime(
                2026, 6, 9, 14, 0, tzinfo=timezone.utc
            ),
        )
        db_session.add(override_event)
        db_session.flush()

        override_row = CalendarEventInstanceOverride(
            id=str(_uuid.uuid4()),
            master_event_id=event.id,
            recurrence_instance_start_at=datetime(
                2026, 6, 9, 14, 0, tzinfo=timezone.utc
            ),
            is_cancelled=False,
            override_event_id=override_event.id,
        )
        db_session.add(override_row)
        db_session.flush()

        result = materialize_instances(
            db_session,
            event=event,
            range_start=datetime(2026, 6, 1, tzinfo=timezone.utc),
            range_end=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        # 3 instances total.
        assert len(result) == 3
        # Find the modified instance (originally June 9).
        modified = [r for r in result if r.is_modified]
        assert len(modified) == 1
        assert modified[0].subject == "Modified subject"
        assert modified[0].start_at == datetime(
            2026, 6, 10, 16, 0, tzinfo=timezone.utc
        )
        assert modified[0].override_event_id == override_event.id
        # Original recurrence_instance_start_at preserved for RFC 5545
        # RECURRENCE-ID semantics.
        assert modified[0].instance_start_at == datetime(
            2026, 6, 9, 14, 0, tzinfo=timezone.utc
        )


# ─────────────────────────────────────────────────────────────────────
# Defensive max_count cap
# ─────────────────────────────────────────────────────────────────────


class TestMaxCountCap:
    def test_max_count_caps_pathological_rrule(self, db_session, account):
        # FREQ=DAILY for many years inside a 30-day window — naturally
        # bounded by range, but if we ran it for a year it would still
        # exceed max_count. Use a tighter cap to force the truncation.
        event = _make_event(
            db_session,
            account,
            subject="Daily",
            start_at=datetime(2026, 1, 1, 14, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 1, 1, 15, 0, tzinfo=timezone.utc),
            recurrence_rule="RRULE:FREQ=DAILY",
        )
        result = materialize_instances(
            db_session,
            event=event,
            range_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            range_end=datetime(2026, 12, 31, tzinfo=timezone.utc),
            max_count=10,  # force truncation at 10
        )
        assert len(result) == 10

    def test_default_max_count_is_500(self):
        assert DEFAULT_MAX_INSTANCES == 500


# ─────────────────────────────────────────────────────────────────────
# Defensive: malformed RRULE doesn't crash, returns empty
# ─────────────────────────────────────────────────────────────────────


class TestMalformedRrule:
    def test_invalid_rrule_returns_empty(self, db_session, account):
        event = _make_event(
            db_session,
            account,
            subject="Bad",
            start_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
            recurrence_rule="RRULE:GIBBERISH=YES",
        )
        # Should not raise; returns empty per stale-but-correct discipline.
        result = materialize_instances(
            db_session,
            event=event,
            range_start=datetime(2026, 6, 1, tzinfo=timezone.utc),
            range_end=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        assert result == []


# ─────────────────────────────────────────────────────────────────────
# Bulk expansion across multiple events
# ─────────────────────────────────────────────────────────────────────


class TestBulkExpansion:
    def test_expansion_across_multiple_events_sorted_by_start(
        self, db_session, account
    ):
        e1 = _make_event(
            db_session,
            account,
            subject="A",
            start_at=datetime(2026, 6, 5, 10, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 6, 5, 11, 0, tzinfo=timezone.utc),
        )
        e2 = _make_event(
            db_session,
            account,
            subject="B",
            start_at=datetime(2026, 6, 2, 14, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 6, 2, 15, 0, tzinfo=timezone.utc),
            recurrence_rule="RRULE:FREQ=WEEKLY;COUNT=3",
        )
        result = materialize_instances_for_events(
            db_session,
            events=[e1, e2],
            range_start=datetime(2026, 6, 1, tzinfo=timezone.utc),
            range_end=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        # 1 from e1 + 3 from e2 = 4 total.
        assert len(result) == 4
        # Sorted by start_at ascending.
        starts = [r.start_at for r in result]
        assert starts == sorted(starts)
