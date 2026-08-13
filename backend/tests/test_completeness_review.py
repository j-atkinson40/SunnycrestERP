"""CR-2 A-1 — the verdicts, and the two ways this review can say nothing.

⚠️ BOTH FAILURE MODES ARE REACHABLE AND BOTH WERE HIT DURING THE BUILD.

  1. SILENT-GREEN. The first version evaluated only the CURRENT period. A
     current period's due date is by construction in the future, so every row
     rendered `not_yet_due` forever and `missing` was structurally unreachable —
     a review that can never say anything while looking like it works. Same
     family as `park_when: drafts_generated > 0`, a predicate that could not fire.
  2. WALL-OF-RED. The fix rendered 21 `missing` rows on a normal day, six of
     which were one ongoing condition repeated per day. Expense Categorization's
     gate fired 12,365 times and was never once answered; that is what an
     un-collapsed list becomes.

The tests below pin the first. The second is a GRAIN problem and belongs to A-3.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services.completeness import expectations as ex
from app.services.completeness.review import (
    ACTIONABLE,
    DECLINED,
    MISSING,
    NOT_YET_DUE,
    UNKNOWN,
    VERDICTS,
    review,
)

TENANT = "staging-test-001"


@pytest.fixture
def db():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


class TestMissingIsReachable:
    """⚠️ THE REGRESSION THAT WOULD RESTORE SILENT-GREEN. If someone narrows the
    window back to the current period to quieten the report, every one of these
    fails. That is the point — the quiet version was the broken one."""

    def test_the_window_reaches_past_the_due_date(self):
        window = ex.periods_in_window("daily", date(2026, 8, 13))
        oldest_end = window[0][1]
        exp = ex.VERTICAL["manufacturing"][0]
        assert ex.due_on(exp, oldest_end) < date(2026, 8, 13), (
            "no period in the window is past due — `missing` cannot fire"
        )

    def test_a_normal_day_produces_actionable_rows(self, db):
        rows = review(db, TENANT, "manufacturing", date(2026, 8, 13))
        assert any(r.verdict in ACTIONABLE for r in rows), (
            "every row is quiet — the review cannot report a gap"
        )

    def test_the_current_period_alone_can_never_be_missing(self):
        """Stated as its own test so the reason is legible: this is WHY the
        window exists, not an incidental property of it."""
        today = date(2026, 8, 13)
        exp = ex.VERTICAL["manufacturing"][0]
        _, end = ex.period_for(exp.cadence, today)
        assert today <= ex.due_on(exp, end)


class TestNoGracefulPath:
    def test_every_declared_expectation_appears(self, db):
        rows = review(db, TENANT, "manufacturing", date(2026, 8, 13))
        declared = {e.key for e in ex.for_tenant(TENANT, "manufacturing")}
        assert {r.key for r in rows} == declared, (
            "an expectation produced no row at all — the silent skip this "
            "module exists to refuse"
        )

    def test_a_broken_probe_reads_as_unknown_not_clean(self, db, monkeypatch):
        """⚠️ THE SUBSTITUTION THIS REFUSES. A renamed column must not report a
        clean count of nothing. A broken check and a complete period are
        opposite facts and this is the only place that can tell them apart."""
        broken = ex.Expectation(
            key="broken_probe", label="Broken", role_slug="admin",
            cadence="daily", due_offset_days=1,
            evidence=ex.Evidence("no_such_table", "tenant_id", "nope"),
            matters_because="—",
        )
        monkeypatch.setattr(ex, "PLATFORM", [broken])
        rows = review(db, TENANT, "manufacturing", date(2026, 8, 13))
        got = [r for r in rows if r.key == "broken_probe"]
        assert got, "the broken expectation vanished instead of reporting"
        assert all(r.verdict == UNKNOWN for r in got)
        assert all(r.observed is None for r in got), "a failed probe reported a count"

    def test_every_verdict_is_a_declared_member(self, db):
        rows = review(db, TENANT, "manufacturing", date(2026, 8, 13))
        assert {r.verdict for r in rows} <= set(VERDICTS)

    def test_every_row_carries_a_role(self, db):
        """The obligation is a ROLE'S. A row nobody owes cannot be queried back
        to a person who can answer it, which is A-3's whole exit path."""
        rows = review(db, TENANT, "manufacturing", date(2026, 8, 13))
        assert all(r.role_slug for r in rows)


class TestDecliningIsNotDeletion:
    def test_a_declined_obligation_still_renders(self, db, monkeypatch):
        """⚠️ THE DISTINCTION THAT IS THE DESIGN. Declined and never-declared
        must not look identical; filtering the row out would make them so."""
        monkeypatch.setattr(ex, "TENANT_DECLINED", {
            TENANT: [ex.Declination("production_log_daily", "no on-site pours",
                                    date(2026, 5, 1))]
        })
        rows = review(db, TENANT, "manufacturing", date(2026, 8, 13))
        got = [r for r in rows if r.key == "production_log_daily"]
        assert got, "the declined obligation disappeared — indistinguishable "
        assert all(r.verdict == DECLINED for r in got)
        assert "no on-site pours" in got[0].detail, "the reason was dropped"

    def test_declined_is_not_actionable(self, db, monkeypatch):
        monkeypatch.setattr(ex, "TENANT_DECLINED", {
            TENANT: [ex.Declination("production_log_daily", "x", date(2026, 5, 1))]
        })
        rows = review(db, TENANT, "manufacturing", date(2026, 8, 13))
        assert DECLINED not in ACTIONABLE
        assert all(r.verdict != MISSING for r in rows if r.key == "production_log_daily")


class TestNothingIsOwedBeforeTheTenantExisted:
    def test_the_window_stops_at_the_start_date(self):
        """Back-filling red to the beginning of the calendar is how a report
        teaches its reader to ignore it."""
        as_of = date(2026, 8, 13)
        started = as_of - timedelta(days=2)
        window = ex.periods_in_window("daily", as_of, not_before=started)
        assert all(e >= started for _, e in window), (
            f"window reaches before the tenant existed: {window}"
        )

    def test_no_bound_means_the_full_lookback(self):
        assert len(ex.periods_in_window("daily", date(2026, 8, 13))) == (
            ex.LOOKBACK["daily"] + 1
        )


class TestPeriodArithmetic:
    @pytest.mark.parametrize("cadence,as_of,start,end", [
        ("daily", date(2026, 8, 13), date(2026, 8, 13), date(2026, 8, 13)),
        ("weekly", date(2026, 8, 13), date(2026, 8, 10), date(2026, 8, 16)),
        ("monthly", date(2026, 8, 13), date(2026, 8, 1), date(2026, 8, 31)),
        ("monthly", date(2028, 2, 5), date(2028, 2, 1), date(2028, 2, 29)),  # leap
    ])
    def test_period_bounds(self, cadence, as_of, start, end):
        assert ex.period_for(cadence, as_of) == (start, end)

    def test_windows_do_not_overlap_or_gap(self):
        """A duplicated period double-counts a gap; a skipped one hides it."""
        w = ex.periods_in_window("daily", date(2026, 8, 13))
        for (_, prev_end), (nxt_start, _) in zip(w, w[1:]):
            assert nxt_start == prev_end + timedelta(days=1)
