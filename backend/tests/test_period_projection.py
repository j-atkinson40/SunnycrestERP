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
    covered_ranges,
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

    def test_the_projection_filters_the_same_flag_the_enforcer_does(self):
        """`check_date_in_locked_period` filters `is_active == True`. If the
        projection read released locks too, a re-opened month would still render
        closed while accepting writes."""
        from app.services.accounting.period_projection import active_locks
        from app.services.agents.period_lock import PeriodLockService
        from tests._source import code_only

        projection = code_only(inspect.getsource(active_locks))
        enforcer = code_only(inspect.getsource(PeriodLockService.check_date_in_locked_period))
        assert "is_active" in projection, "the projection does not filter released locks"
        assert "is_active" in enforcer, "the enforcer's filter moved — re-check the pair"

    def test_both_period_surfaces_read_the_one_definition(self):
        """⚠️ THE SURVEY MISS THIS TEST EXISTS FOR. Two period UIs exist —
        `/journal-entries/periods` and `/vault/accounting/periods` — and only the
        first was found on the initial pass, so the better-built one kept
        reporting a close it could not enforce for a further commit.

        A per-route copy of the lock read is how they drift apart again."""
        from app.api.routes import journal_entries, vault_accounting
        from app.services.accounting import period_projection

        for mod in (journal_entries, vault_accounting):
            assert mod._active_locks is period_projection.active_locks, (
                f"{mod.__name__} has its own lock read — the two period "
                f"surfaces can now disagree about which locks count"
            )


class TestTheRangesThatMakeTheThirdStateActionable:
    """"Partially closed" does not predict whether an invoice will post.
    "Closed 1-15 August" does."""

    def test_a_full_month_is_one_range(self):
        assert covered_ranges(
            [lock_span_for_month(8, 2026)], month=8, year=2026
        ) == [(date(2026, 8, 1), date(2026, 8, 31))]

    def test_open_has_no_ranges(self):
        assert covered_ranges([], month=8, year=2026) == []

    def test_a_half_month_reports_the_days_that_are_shut(self):
        assert covered_ranges(
            [(date(2026, 8, 1), date(2026, 8, 15))], month=8, year=2026
        ) == [(date(2026, 8, 1), date(2026, 8, 15))]

    def test_adjacent_locks_merge_into_one_span(self):
        """Two locks touching at the boundary are one closed stretch to a reader.
        Reporting them separately would describe a gap that does not exist."""
        assert covered_ranges(
            [(date(2026, 8, 1), date(2026, 8, 10)), (date(2026, 8, 11), date(2026, 8, 20))],
            month=8, year=2026,
        ) == [(date(2026, 8, 1), date(2026, 8, 20))]

    def test_a_gap_is_preserved_as_two_spans(self):
        assert covered_ranges(
            [(date(2026, 8, 1), date(2026, 8, 10)), (date(2026, 8, 20), date(2026, 8, 31))],
            month=8, year=2026,
        ) == [(date(2026, 8, 1), date(2026, 8, 10)), (date(2026, 8, 20), date(2026, 8, 31))]

    def test_a_lock_overrunning_the_month_is_clipped_to_it(self):
        """A lock running into September is not a fact about August, and showing
        September dates in August's row would misdescribe both."""
        assert covered_ranges(
            [(date(2026, 7, 15), date(2026, 9, 15))], month=8, year=2026
        ) == [(date(2026, 8, 1), date(2026, 8, 31))]

    @pytest.mark.parametrize("spans,month", [
        ([], 8),
        ([lock_span_for_month(8, 2026)], 8),
        ([(date(2026, 8, 5), date(2026, 8, 9))], 8),
        ([(date(2026, 8, 1), date(2026, 8, 3)), (date(2026, 8, 9), date(2026, 8, 31))], 8),
    ])
    def test_ranges_and_status_never_contradict(self, spans, month):
        """The badge and the dates beside it come from two functions. If they
        disagreed, the row would argue with itself."""
        status = project_month(spans, month=month, year=2026)
        ranges = covered_ranges(spans, month=month, year=2026)
        days = sum((e - s).days + 1 for s, e in ranges)
        assert (status == OPEN) == (days == 0)
        assert (status == CLOSED) == (days == 31)
        assert (status == PARTIALLY_CLOSED) == (0 < days < 31)


class TestEveryStateReachesTheOperator:
    """⚠️ THE SILENT FALLBACK. `journal-entries.tsx` looks up its badge as
    `PERIOD_BADGE[p.status] || PERIOD_BADGE.open`. When the backend gained a
    third state the frontend did not know, a partly-LOCKED month rendered as
    fully Open — the most dangerous of the three wrong answers — and both action
    buttons hid, leaving the row inert. No error, no warning.

    This lives backend-side on purpose: a frontend test listing three states
    cannot notice a FOURTH being added here. Only a check that runs where the
    states are defined can.
    """

    #: Files that must name every state the projection can return.
    _SURFACES = [
        "frontend/src/pages/journal-entries.tsx",
        "frontend/src/pages/vault/accounting/AccountingPeriodsTab.tsx",
    ]

    @pytest.mark.parametrize("surface", _SURFACES)
    def test_the_surface_handles_every_state(self, surface):
        import pathlib

        from app.services.accounting.period_projection import PERIOD_STATES

        path = pathlib.Path(__file__).resolve().parents[2] / surface
        assert path.exists(), f"{surface} moved — re-point this guard"
        src = path.read_text()
        missing = [s for s in PERIOD_STATES if s not in src]
        assert not missing, (
            f"{surface} never mentions {missing}. Both period surfaces fall back "
            f"to an 'open' badge on an unknown status, so an unhandled state "
            f"renders a locked month as writable."
        )


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
