"""The ordinal-weekday rider (Tenant Ponder-Editor P1, commit set 1).

spec_kind="ordinal_weekday" — "the first Monday of every month at 4:00 PM".
Standard cron can't express it (dom/dow OR-semantics); the sweep's matcher is
custom Python, so it lands as a first-class spec evaluated TENANT-LOCAL with
the sweep's inherited window + idempotency semantics:

  * due when tenant-local now ∈ [target, target+15min) on the matching
    ordinal weekday; the intended fire is the target clock time — the
    idempotency key, so a due trigger fires ONCE across the N ticks in its
    window;
  * outside the window → skipped (the T-2.1a catch-up rule — no backlog storm);
  * validation is LOUD (TriggerValidationError on bad ordinal/weekday/time);
  * the prose grammar renders it as the WHEN beat's own sentence (the
    readback the editor mirrors live).

Calendar facts used (August 2026): Aug 1 is a Saturday → first Monday is
Aug 3, second is Aug 10, last is Aug 31. First Tuesday is Aug 4.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.services.maps_of_content.ponder import schedule_trigger_to_prose
from app.services.maps_of_content.schedule_sweep import (
    _due_intended_fire,
    _ordinal_weekday_intended,
)
from app.services.maps_of_content.triggers import (
    TriggerValidationError,
    humanize_schedule,
    validate_trigger,
)

NY = ZoneInfo("America/New_York")


def _local(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=NY)


FIRST_MONDAY_4PM = {"spec_kind": "ordinal_weekday", "ordinal": 1,
                    "weekday": "mon", "time": "16:00"}


class TestMatcher:
    def test_fires_on_first_monday_in_window(self):
        got = _ordinal_weekday_intended(FIRST_MONDAY_4PM, _local(2026, 8, 3, 16, 2))
        assert got == _local(2026, 8, 3, 16, 0)

    def test_window_edges(self):
        # 15:59 — before the window
        assert _ordinal_weekday_intended(FIRST_MONDAY_4PM, _local(2026, 8, 3, 15, 59)) is None
        # 16:14 — last in-window tick, SAME intended fire (the idempotency key)
        assert _ordinal_weekday_intended(
            FIRST_MONDAY_4PM, _local(2026, 8, 3, 16, 14)
        ) == _local(2026, 8, 3, 16, 0)
        # 16:15 — past the window: skipped, never fired late (catch-up rule)
        assert _ordinal_weekday_intended(FIRST_MONDAY_4PM, _local(2026, 8, 3, 16, 15)) is None

    def test_skips_second_monday(self):
        assert _ordinal_weekday_intended(FIRST_MONDAY_4PM, _local(2026, 8, 10, 16, 2)) is None

    def test_skips_first_tuesday(self):
        assert _ordinal_weekday_intended(FIRST_MONDAY_4PM, _local(2026, 8, 4, 16, 2)) is None

    def test_last_weekday_of_month(self):
        cfg = {"spec_kind": "ordinal_weekday", "ordinal": "last",
               "weekday": "mon", "time": "09:00"}
        # Aug 31 2026 IS the last Monday
        assert _ordinal_weekday_intended(cfg, _local(2026, 8, 31, 9, 5)) == \
            _local(2026, 8, 31, 9, 0)
        # Aug 24 is a Monday but NOT the last one
        assert _ordinal_weekday_intended(cfg, _local(2026, 8, 24, 9, 5)) is None

    def test_fourth_vs_fifth_occurrence(self):
        cfg = {"spec_kind": "ordinal_weekday", "ordinal": 4,
               "weekday": "mon", "time": "09:00"}
        # Aug 24 2026 is the fourth Monday
        assert _ordinal_weekday_intended(cfg, _local(2026, 8, 24, 9, 0)) is not None
        # Aug 31 is the fifth — ordinal 4 must not fire there
        assert _ordinal_weekday_intended(cfg, _local(2026, 8, 31, 9, 0)) is None

    def test_invalid_time_skips_with_none(self):
        cfg = {"spec_kind": "ordinal_weekday", "ordinal": 1,
               "weekday": "mon", "time": "nonsense"}
        assert _ordinal_weekday_intended(cfg, _local(2026, 8, 3, 16, 2)) is None

    def test_due_intended_fire_is_tenant_local(self):
        """The sweep hands a UTC now; the match is evaluated in the TENANT's
        timezone. 20:02 UTC on Aug 3 = 16:02 in New York → due; 16:02 UTC
        (= 12:02 NY) → not due."""
        class _Trig:
            id = "t-ordinal-test"
            config = FIRST_MONDAY_4PM
        class _Co:
            timezone = "America/New_York"
        due = _due_intended_fire(_Trig(), _Co(), datetime(2026, 8, 3, 20, 2, tzinfo=timezone.utc))
        assert due is not None and due.hour == 16 and due.tzinfo is not None
        assert _due_intended_fire(_Trig(), _Co(), datetime(2026, 8, 3, 16, 2, tzinfo=timezone.utc)) is None


class TestValidation:
    def test_accepts_first_monday(self, db_or_none=None):
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            validate_trigger(db, kind="schedule", config=FIRST_MONDAY_4PM, vertical=None)
            validate_trigger(db, kind="schedule", config={
                "spec_kind": "ordinal_weekday", "ordinal": "last",
                "weekday": "fri", "time": "09:30",
            }, vertical=None)
        finally:
            db.close()

    @pytest.mark.parametrize("bad", [
        {"spec_kind": "ordinal_weekday", "ordinal": 5, "weekday": "mon", "time": "16:00"},
        {"spec_kind": "ordinal_weekday", "ordinal": "first", "weekday": "mon", "time": "16:00"},
        {"spec_kind": "ordinal_weekday", "ordinal": 1, "weekday": "monday", "time": "16:00"},
        {"spec_kind": "ordinal_weekday", "ordinal": 1, "weekday": "mon", "time": "25:00"},
        {"spec_kind": "ordinal_weekday", "ordinal": 1, "weekday": "mon"},
    ])
    def test_rejects_bad_shapes_loudly(self, bad):
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            with pytest.raises(TriggerValidationError):
                validate_trigger(db, kind="schedule", config=bad, vertical=None)
        finally:
            db.close()


class TestProse:
    def test_the_dispatch_sentence(self):
        assert schedule_trigger_to_prose(FIRST_MONDAY_4PM) == \
            "The first Monday of every month at 4:00 PM"

    def test_last_friday(self):
        assert schedule_trigger_to_prose({
            "spec_kind": "ordinal_weekday", "ordinal": "last",
            "weekday": "fri", "time": "09:30",
        }) == "The last Friday of every month at 9:30 AM"

    def test_time_of_day_prose(self):
        assert schedule_trigger_to_prose({
            "spec_kind": "time_of_day", "time": "18:00", "days": ["mon", "wed"],
        }) == "At 6:00 PM on Mon, Wed"
        assert schedule_trigger_to_prose({
            "spec_kind": "time_of_day", "time": "23:30", "days": [],
        }) == "Every night at 11:30 PM"

    def test_cron_prose_delegates(self):
        assert "6:00 AM" in schedule_trigger_to_prose(
            {"spec_kind": "cron", "cron": "0 6 1 * *"}
        )

    def test_humanize_chip(self):
        assert humanize_schedule(FIRST_MONDAY_4PM) == "Monthly · 1st Mon, 4:00 PM"
        assert humanize_schedule({
            "spec_kind": "ordinal_weekday", "ordinal": "last",
            "weekday": "fri", "time": "09:30",
        }) == "Monthly · Last Fri, 9:30 AM"
