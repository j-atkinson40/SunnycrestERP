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
from sqlalchemy import text

from app.services.completeness.review import (
    ARRIVED,
    REPORTED_NONE,
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


class TestTheNothingHappenedPath:
    """⚠️ WITHOUT THIS, EVERY QUIET DAY READS AS A GAP. Measured on testco: 21
    `missing` rows, of which 6 may be a factory that simply did not pour. The
    carve-out is what makes the report CORRECT, not merely quieter."""

    def _claim(self, db, key, start, end, *, name="J. Atkinson", role="production"):
        from datetime import datetime, timezone
        import uuid
        db.execute(text(
            "INSERT INTO completeness_nil_claims (id, tenant_id, expectation_key, "
            "period_start, period_end, claimed_by, claimed_by_name, "
            "claimed_by_role_slug, claimed_at, note, created_at) VALUES "
            "(:i,:t,:k,:s,:e,NULL,:n,:r,:a,'quiet day',:a)"),
            {"i": str(uuid.uuid4()), "t": TENANT, "k": key, "s": start, "e": end,
             "n": name, "r": role, "a": datetime.now(timezone.utc)})
        db.flush()

    def test_a_claim_turns_missing_into_reported_none(self, db):
        past = date(2026, 8, 8)
        before = [r for r in review(db, TENANT, "manufacturing", date(2026, 8, 13))
                  if r.key == "production_log_daily" and r.period_start == past]
        assert before and before[0].verdict == MISSING, "fixture assumption broke"

        self._claim(db, "production_log_daily", past, past)
        after = [r for r in review(db, TENANT, "manufacturing", date(2026, 8, 13))
                 if r.key == "production_log_daily" and r.period_start == past]
        assert after[0].verdict == REPORTED_NONE

    def test_the_claimant_is_named_on_the_row(self, db):
        """The accountability IS the evidence — a nil claim nobody signed is
        just silence with extra steps."""
        past = date(2026, 8, 8)
        self._claim(db, "production_log_daily", past, past)
        row = next(r for r in review(db, TENANT, "manufacturing", date(2026, 8, 13))
                   if r.key == "production_log_daily" and r.period_start == past)
        assert "J. Atkinson" in row.detail and "production" in row.detail

    def test_reported_none_is_not_arrived(self, db):
        """A month of nil claims must not render as a month of work."""
        past = date(2026, 8, 8)
        self._claim(db, "production_log_daily", past, past)
        row = next(r for r in review(db, TENANT, "manufacturing", date(2026, 8, 13))
                   if r.key == "production_log_daily" and r.period_start == past)
        assert row.verdict != ARRIVED
        assert row.verdict not in ACTIONABLE, "a signed nil claim is not a gap"


class TestEvidenceIsTheDeliverableNotTheMechanism:
    def test_no_expectation_reads_a_run_table(self):
        """⚠️ MAP-5 ASKS IF THE MECHANISM RAN; THIS ASKS IF THE DELIVERABLE
        ARRIVED. A bank sync that ran green and imported nothing satisfies MAP-5
        and must not satisfy this — measured this week as "the error stopped,
        and green does not mean the feed works". Declaring `workflow_runs` as
        evidence would silently make a dry-run preview count as satisfaction."""
        from app.services.completeness.review import _NEVER_EVIDENCE

        for e in ex.PLATFORM + [x for v in ex.VERTICAL.values() for x in v]:
            assert e.evidence.table not in _NEVER_EVIDENCE, (
                f"{e.key} takes its evidence from {e.evidence.table} — a run "
                f"record, which a dry run also writes"
            )


class TestRunCollapse:
    """⚠️ SIX CONSECUTIVE MISSING DAYS IS ONE CONDITION. Rendering it six times
    makes the report describe incidents that do not exist — measured at 21 rows
    where 4 conditions existed. This is not polish; the un-collapsed list is
    wrong about the world."""

    def test_a_run_of_missing_days_becomes_one_row(self, db):
        from app.services.completeness.collapse import collapse
        rows = review(db, TENANT, "manufacturing", date(2026, 8, 13))
        runs = collapse(rows)
        assert len(runs) < len(rows), "nothing collapsed"
        bank = [r for r in runs if r.key == "bank_feed_daily" and r.verdict == MISSING]
        assert len(bank) == 1, f"the bank feed rendered as {len(bank)} conditions"
        assert bank[0].periods > 1
        assert "Nothing since" in bank[0].detail

    def test_collapse_never_merges_different_verdicts(self, db):
        from app.services.completeness.collapse import collapse
        for r in collapse(review(db, TENANT, "manufacturing", date(2026, 8, 13))):
            assert r.verdict in VERDICTS

    def test_the_quiet_are_counted_not_enumerated(self, db):
        """Silence is what a reader fills in with an assumption."""
        from app.services.completeness.collapse import collapse, summarise
        shown, closing = summarise(collapse(review(db, TENANT, "manufacturing",
                                                   date(2026, 8, 13))))
        assert all(r.actionable or r.verdict == REPORTED_NONE for r in shown)
        assert closing, "the quiet obligations vanished instead of being counted"

    def test_reported_none_renders_despite_being_quiet(self, db):
        """⚠️ A MONTH OF NIL CLAIMS IS A FINDING, and it only is one if someone
        can see it. Folding it into the quiet count would hide the single thing
        the carve-out could be abused to do."""
        from app.services.completeness.collapse import Run, summarise
        r = Run("k", "L", "production", REPORTED_NONE, date(2026, 8, 1),
                date(2026, 8, 30), 30, "30 periods reported empty.")
        shown, _ = summarise([r])
        assert r in shown and not r.actionable


class TestOnlyTheRoleThatOwesItMayClaim:
    def test_the_endpoint_checks_the_role(self):
        """The carve-out's whole value is that a named person HOLDING the
        obligation stood behind it. A claim from anyone else is an opinion."""
        import inspect
        from app.api.routes import completeness
        from tests._source import code_only
        src = code_only(inspect.getsource(completeness.file_nil_claim))
        assert "exp.role_slug" in src and "403" in src

    def test_the_prompt_can_be_filtered_to_a_role(self, db):
        """⚠️ PROMPTED, NOT REMEMBERED. A quiet day produces no reason to open
        anything; role-filtering is what lets this power a prompt where the
        person already is, rather than a page they had to choose to visit."""
        rows = review(db, TENANT, "manufacturing", date(2026, 8, 13),
                      role_slug="production")
        assert rows, "role filter returned nothing"
        assert {r.role_slug for r in rows} == {"production"}
