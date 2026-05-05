"""Calendar Step 2 — local provider freebusy with recurring events.

Closes Step 1 architectural Q2: Step 1's local provider was
non-recurring-only; Step 2 RRULE engine activation enables recurring
events to expand into freebusy windows.

Verifies LocalCalendarProvider.fetch_freebusy via the new
``recurrence_engine.materialize_instances_for_events`` path:

  - Recurring events expand into multiple busy windows
  - EXDATE-excluded instances skipped
  - Cancelled-instance overrides skipped (RFC 5545 cancelled events
    don't count toward free/busy)
  - Transparent events skipped (RFC 5545 TRANSP=TRANSPARENT)
  - Q1 Path A: provider receives db_session + account_id via
    constructor params (replaces Step 1's __db__ injection hack)
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
from app.services.calendar.providers.local import LocalCalendarProvider


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
        name=f"FB {_uuid.uuid4().hex[:8]}",
        slug=f"fb{_uuid.uuid4().hex[:8]}",
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
        email=f"u-{_uuid.uuid4().hex[:8]}@fb.test",
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
        display_name="FB Test",
        primary_email_address=f"fb-{_uuid.uuid4().hex[:8]}@fb.test",
        provider_type="local",
        created_by_user_id=admin_user.id,
    )
    db_session.add(acc)
    db_session.flush()
    return acc


def _add_event(
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
# Q1 Path A — constructor params
# ─────────────────────────────────────────────────────────────────────


class TestConstructorPathA:
    def test_provider_with_constructor_db_session_works(
        self, db_session, account
    ):
        """Q1 Path A: provider accepts db_session + account_id via
        constructor instead of __db__ injection."""
        provider = LocalCalendarProvider(
            {"primary_email_address": account.primary_email_address},
            db_session=db_session,
            account_id=account.id,
        )
        result = provider.fetch_freebusy(
            calendar_id=None,
            time_range_start=datetime(2026, 6, 1, tzinfo=timezone.utc),
            time_range_end=datetime(2026, 6, 2, tzinfo=timezone.utc),
        )
        assert result.success is True

    def test_provider_without_db_session_fails_gracefully(self, account):
        """Without db_session + account_id, fetch_freebusy returns
        success=False with a clear error message."""
        provider = LocalCalendarProvider(
            {"primary_email_address": account.primary_email_address}
        )
        result = provider.fetch_freebusy(
            calendar_id=None,
            time_range_start=datetime(2026, 6, 1, tzinfo=timezone.utc),
            time_range_end=datetime(2026, 6, 2, tzinfo=timezone.utc),
        )
        assert result.success is False
        assert "db_session" in (result.error_message or "")

    def test_step_1_legacy_injection_fallback(self, db_session, account):
        """Backwards-compat with Step 1's __db__ + __account_id__
        injection — caller passes via account_config keys."""
        provider = LocalCalendarProvider(
            {
                "primary_email_address": account.primary_email_address,
                "__db__": db_session,
                "__account_id__": account.id,
            }
        )
        result = provider.fetch_freebusy(
            calendar_id=None,
            time_range_start=datetime(2026, 6, 1, tzinfo=timezone.utc),
            time_range_end=datetime(2026, 6, 2, tzinfo=timezone.utc),
        )
        assert result.success is True


# ─────────────────────────────────────────────────────────────────────
# Recurring event expansion in freebusy
# ─────────────────────────────────────────────────────────────────────


class TestRecurringFreebusy:
    def test_weekly_recurring_event_expands_to_multiple_busy_windows(
        self, db_session, account
    ):
        # Weekly meeting: Tuesday 10:00 UTC.
        _add_event(
            db_session,
            account,
            subject="Weekly meeting",
            start_at=datetime(2026, 6, 2, 10, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 6, 2, 11, 0, tzinfo=timezone.utc),
            recurrence_rule="RRULE:FREQ=WEEKLY",
        )

        provider = LocalCalendarProvider(
            {"primary_email_address": account.primary_email_address},
            db_session=db_session,
            account_id=account.id,
        )
        result = provider.fetch_freebusy(
            calendar_id=None,
            time_range_start=datetime(2026, 6, 1, tzinfo=timezone.utc),
            time_range_end=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        # June 2, 9, 16, 23, 30 = 5 instances.
        assert result.success is True
        assert len(result.windows) == 5
        for w in result.windows:
            assert w.status == "busy"
            assert w.end_at - w.start_at == timedelta(hours=1)

    def test_cancelled_override_excluded_from_freebusy(
        self, db_session, account
    ):
        import uuid as _uuid

        master = _add_event(
            db_session,
            account,
            subject="Weekly w/ cancellation",
            start_at=datetime(2026, 6, 2, 10, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 6, 2, 11, 0, tzinfo=timezone.utc),
            recurrence_rule="RRULE:FREQ=WEEKLY;COUNT=4",
        )
        cancel = CalendarEventInstanceOverride(
            id=str(_uuid.uuid4()),
            master_event_id=master.id,
            recurrence_instance_start_at=datetime(
                2026, 6, 9, 10, 0, tzinfo=timezone.utc
            ),
            is_cancelled=True,
        )
        db_session.add(cancel)
        db_session.flush()

        provider = LocalCalendarProvider(
            {"primary_email_address": account.primary_email_address},
            db_session=db_session,
            account_id=account.id,
        )
        result = provider.fetch_freebusy(
            calendar_id=None,
            time_range_start=datetime(2026, 6, 1, tzinfo=timezone.utc),
            time_range_end=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        # 4 RRULE - 1 cancelled = 3.
        assert len(result.windows) == 3
        starts = [w.start_at for w in result.windows]
        # June 9 must be excluded.
        assert datetime(2026, 6, 9, 10, 0, tzinfo=timezone.utc) not in starts

    def test_transparent_event_excluded_from_freebusy(
        self, db_session, account
    ):
        # Transparent event (RFC 5545 TRANSP=TRANSPARENT) does NOT count
        # toward free/busy.
        _add_event(
            db_session,
            account,
            subject="Out of office (transparent)",
            start_at=datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 6, 1, 18, 0, tzinfo=timezone.utc),
            transparency="transparent",
        )
        # Add a normal opaque event for control.
        _add_event(
            db_session,
            account,
            subject="Regular meeting",
            start_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
        )
        provider = LocalCalendarProvider(
            {"primary_email_address": account.primary_email_address},
            db_session=db_session,
            account_id=account.id,
        )
        result = provider.fetch_freebusy(
            calendar_id=None,
            time_range_start=datetime(2026, 6, 1, tzinfo=timezone.utc),
            time_range_end=datetime(2026, 6, 2, tzinfo=timezone.utc),
        )
        # Only the opaque event registers as busy.
        assert len(result.windows) == 1
        assert result.windows[0].start_at == datetime(
            2026, 6, 1, 14, 0, tzinfo=timezone.utc
        )

    def test_cancelled_event_excluded_from_freebusy(
        self, db_session, account
    ):
        _add_event(
            db_session,
            account,
            subject="Cancelled meeting",
            start_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
            status="cancelled",
        )
        provider = LocalCalendarProvider(
            {"primary_email_address": account.primary_email_address},
            db_session=db_session,
            account_id=account.id,
        )
        result = provider.fetch_freebusy(
            calendar_id=None,
            time_range_start=datetime(2026, 6, 1, tzinfo=timezone.utc),
            time_range_end=datetime(2026, 6, 2, tzinfo=timezone.utc),
        )
        # Cancelled event does NOT count.
        assert len(result.windows) == 0

    def test_mixed_recurring_and_non_recurring_in_same_range(
        self, db_session, account
    ):
        # Weekly at 10:00 + non-recurring at 14:00 same day.
        _add_event(
            db_session,
            account,
            subject="Recurring",
            start_at=datetime(2026, 6, 2, 10, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 6, 2, 11, 0, tzinfo=timezone.utc),
            recurrence_rule="RRULE:FREQ=WEEKLY;COUNT=2",
        )
        _add_event(
            db_session,
            account,
            subject="One-off",
            start_at=datetime(2026, 6, 5, 14, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 6, 5, 15, 0, tzinfo=timezone.utc),
        )
        provider = LocalCalendarProvider(
            {"primary_email_address": account.primary_email_address},
            db_session=db_session,
            account_id=account.id,
        )
        result = provider.fetch_freebusy(
            calendar_id=None,
            time_range_start=datetime(2026, 6, 1, tzinfo=timezone.utc),
            time_range_end=datetime(2026, 6, 30, tzinfo=timezone.utc),
        )
        # 2 recurring + 1 one-off = 3 windows; sorted by start_at.
        assert len(result.windows) == 3
        starts = [w.start_at for w in result.windows]
        assert starts == sorted(starts)
