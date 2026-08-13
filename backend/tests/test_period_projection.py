"""The month view derives from the lock, and agrees with the enforcer. CR-1.

⚠️ WHAT THIS PROTECTS. `accounting_periods.status` and `period_locks` both
modelled period closure. The tab wrote the first; every AR write path honoured
the second; only the journal-entry post read both. So Close stopped journal
entries and left invoices, payments and statements posting — a control that
reported success and half-worked, which is harder to notice than one that fails.

The projection makes the lock the single source. These tests pin the two claims
that make that safe: the three states are distinguishable, and a month the tab
calls `closed` is one the enforcer refuses every day of.
"""
from __future__ import annotations

import inspect
from datetime import date

import pytest

from app.services.accounting.period_projection import (
    CLOSED,
    OPEN,
    PARTIALLY_CLOSED,
    lock_span_for_month,
    month_bounds,
    project_month,
)


class TestTheThreeStates:
    def test_no_locks_is_open(self):
        assert project_month([], month=8, year=2026) == OPEN

    def test_a_lock_over_the_whole_month_is_closed(self):
        assert project_month([lock_span_for_month(8, 2026)], month=8, year=2026) == CLOSED

    def test_half_a_month_is_neither(self):
        """⚠️ THE RULING. A lock over 1–15 August makes "August is closed" false —
        but "August is open" is equally false, because writes to the first half
        will be refused. Both binary answers mislead someone about what happens
        when they post."""
        half = [(date(2026, 8, 1), date(2026, 8, 15))]
        got = project_month(half, month=8, year=2026)
        assert got == PARTIALLY_CLOSED
        assert got not in (CLOSED, OPEN), "collapsed into a neighbouring state"

    def test_one_uncovered_day_is_not_closed(self):
        """The off-by-one that would make a partial month read as fully closed —
        and tell an operator the month is safe when one day still accepts money."""
        assert project_month(
            [(date(2026, 8, 1), date(2026, 8, 30))], month=8, year=2026
        ) == PARTIALLY_CLOSED

    def test_a_lock_entirely_outside_the_month_does_not_touch_it(self):
        assert project_month(
            [lock_span_for_month(7, 2026)], month=8, year=2026
        ) == OPEN


class TestTheUnionNotThePieces:
    def test_two_partial_locks_covering_between_them_is_closed(self):
        """Locks arrive from different writers — the tab and month-end close —
        so coverage is the union, not any single span."""
        assert project_month(
            [(date(2026, 8, 1), date(2026, 8, 15)), (date(2026, 8, 16), date(2026, 8, 31))],
            month=8, year=2026,
        ) == CLOSED

    def test_order_and_overlap_do_not_matter(self):
        assert project_month(
            [(date(2026, 8, 10), date(2026, 9, 5)), (date(2026, 7, 20), date(2026, 8, 20))],
            month=8, year=2026,
        ) == CLOSED

    def test_a_gap_between_two_locks_is_partial(self):
        assert project_month(
            [(date(2026, 8, 1), date(2026, 8, 10)), (date(2026, 8, 12), date(2026, 8, 31))],
            month=8, year=2026,
        ) == PARTIALLY_CLOSED


class TestMonthArithmetic:
    @pytest.mark.parametrize("month,year,last", [
        (2, 2026, 28), (2, 2028, 29),   # leap
        (4, 2026, 30), (12, 2026, 31),
    ])
    def test_month_bounds_are_inclusive_and_leap_aware(self, month, year, last):
        first, end = month_bounds(month, year)
        assert (first.day, end.day) == (1, last)

    @pytest.mark.parametrize("month,year", [(2, 2028), (2, 2026), (12, 2026)])
    def test_close_then_read_round_trips(self, month, year):
        """What Close writes, the tab reads back as closed — including February,
        where a hand-rolled last-day would leave the 29th unlocked."""
        assert project_month(
            [lock_span_for_month(month, year)], month=month, year=year
        ) == CLOSED


class TestTheProjectionAgreesWithTheEnforcer:
    """⚠️ THE PROPERTY THAT MAKES ONE SOURCE SAFE. The tab describes; the write
    paths refuse. If they disagreed, the tab would be a second source again —
    exactly the defect being closed."""

    def test_closed_means_every_day_is_covered(self):
        """`check_date_in_locked_period` asks, per date, whether some active lock
        spans it. `closed` must mean it answers yes for all 31."""
        spans = [lock_span_for_month(8, 2026)]
        assert project_month(spans, month=8, year=2026) == CLOSED
        for d in range(1, 32):
            day = date(2026, 8, d)
            assert any(s <= day <= e for s, e in spans), f"{day} not covered"

    def test_open_means_no_day_is_covered(self):
        spans = [lock_span_for_month(7, 2026)]
        assert project_month(spans, month=8, year=2026) == OPEN
        for d in range(1, 32):
            day = date(2026, 8, d)
            assert not any(s <= day <= e for s, e in spans), f"{day} unexpectedly covered"

    def test_the_route_filters_the_same_flag_the_enforcer_does(self):
        """`check_date_in_locked_period` filters `is_active == True`. If the
        projection read released locks too, a re-opened month would still render
        closed while accepting writes."""
        from app.api.routes import journal_entries
        from app.services.agents.period_lock import PeriodLockService
        from tests._source import code_only

        projection = code_only(inspect.getsource(journal_entries._active_locks))
        enforcer = code_only(inspect.getsource(PeriodLockService.check_date_in_locked_period))
        assert "is_active" in projection, "the projection does not filter released locks"
        assert "is_active" in enforcer, "the enforcer's filter moved — re-check the pair"


class TestTheCloseButtonWritesALock:
    def test_close_writes_period_locks_not_a_status(self):
        """⚠️ THE REGRESSION THAT WOULD BE INVISIBLE. Setting
        `AccountingPeriod.status` still makes the JE post refuse, so a revert
        would look like it worked while every AR path kept writing."""
        from app.api.routes.journal_entries import close_period
        from tests._source import code_only

        src = code_only(inspect.getsource(close_period))
        assert "PeriodLock(" in src, "close no longer writes a lock"
        assert "status" not in src.replace('"status"', ""), (
            "close is setting a status again — the half-working control is back"
        )

    def test_open_releases_overlapping_locks_not_only_exact_ones(self):
        """A lock written by month-end close may not match this tab's span. An
        `open` matching only its own spans would report success and leave the
        month locked."""
        from app.api.routes.journal_entries import open_period
        from tests._source import code_only

        src = code_only(inspect.getsource(open_period))
        assert "is_active = False" in src
        assert "period_start <= end" in src and "period_end >= start" in src, (
            "open matches exactly rather than by overlap"
        )
