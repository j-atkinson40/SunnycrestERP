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
    CONTRADICTED,
    DECLINED,
    MISSING,
    NOT_YET_DUE,
    RENDERED,
    UNKNOWN,
    VERDICTS,
    review,
)

from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

TENANT = TESTCO_ID

# ⚠️ THIS FILE ASSUMED A ROW IT NEVER CREATED, AND ONLY A THIRD OF IT NOTICED.
# `TENANT` was a bare literal. On CI's fresh Postgres the three tests below that
# INSERT a nil claim died on completeness_nil_claims_tenant_id_fkey while every
# other test passed — `review()` against a nonexistent tenant returns
# all-`missing` without touching a foreign key. Ninety percent green, resting
# entirely on seed_staging having run.
#
# Teardown is create-scoped by construction (see tests/_tenant.py): purging
# `staging-test-001` outright would delete a developer's real testco.
canonical_tenant = make_canonical_tenant_fixture(
    child_tables=("completeness_nil_claims", "completeness_declinations"),
)


def _decline(
    db,
    key: str,
    on: date,
    *,
    reason: str = "no on-site pours",
    revoked: date | None = None,
    name: str = "R. Okafor",
    role: str = "admin",
):
    """Record a declination as a ROW, the way the surface will.

    ⚠️ THESE TESTS USED TO MONKEYPATCH A CODE DICT, AND THAT BYPASSED THE THING
    MOST LIKELY TO BREAK. `TENANT_DECLINED` was removed in D-1 (`r169`) because a
    dict and a table both answering "is this declined" is two producers of one
    fact — but the test-shape consequence matters on its own: patching the
    in-memory source meant the loader, the column names and the row→dataclass
    mapping were never exercised by anything. A guessed column name is one of
    this codebase's recurring silent failures, and nothing here would have caught
    one.

    Safe on a bare database: `completeness_declinations`' only FKs are
    `companies` (which the shared fixture guarantees) and `users` (nullable, left
    NULL here). No products, no users, nothing seeded.
    """
    import uuid
    from datetime import datetime, timezone

    db.execute(
        text(
            "INSERT INTO completeness_declinations "
            "(id, tenant_id, expectation_key, declined_on, reason, declined_by, "
            " declined_by_name, declined_by_role_slug, revoked_on, revoked_at, "
            " created_at) "
            "VALUES (:i,:t,:k,:d,:reason,NULL,:n,:r,:rev,:rev_at,:c)"
        ),
        {
            "i": str(uuid.uuid4()), "t": TENANT, "k": key, "d": on,
            "reason": reason, "n": name, "r": role, "rev": revoked,
            # `revoked_at` is what the live-episode partial unique index keys on,
            # so it has to move with `revoked_on` or a second episode is refused.
            "rev_at": datetime.now(timezone.utc) if revoked else None,
            "c": datetime.now(timezone.utc),
        },
    )
    db.flush()


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
    def test_a_declined_obligation_still_renders(self, db):
        """⚠️ THE DISTINCTION THAT IS THE DESIGN. Declined and never-declared
        must not look identical; filtering the row out would make them so."""
        _decline(db, "production_log_daily", date(2026, 5, 1))
        rows = review(db, TENANT, "manufacturing", date(2026, 8, 13))
        got = [r for r in rows if r.key == "production_log_daily"]
        assert got, "the declined obligation disappeared — indistinguishable "
        assert all(r.verdict == DECLINED for r in got)
        assert "no on-site pours" in got[0].detail, "the reason was dropped"

    def test_declined_is_not_actionable(self, db):
        _decline(db, "production_log_daily", date(2026, 5, 1), reason="x")
        rows = review(db, TENANT, "manufacturing", date(2026, 8, 13))
        assert DECLINED not in ACTIONABLE
        assert all(r.verdict != MISSING for r in rows if r.key == "production_log_daily")

    def test_declined_survives_the_whole_read_path(self, db):
        """⚠️ THE TEST THAT WAS MISSING, AND ITS ABSENCE SHIPPED THE DEFECT.

        Its siblings above assert on `review()`. `review()` was never the read
        path — the endpoint runs `summarise(collapse(review(...)))`, and
        `summarise` selected on ACTIONABLE, so the declined row was dropped one
        layer below where anything was looking and counted as "1 obligation
        current". Two true facts (the service emits it, the tab styles it grey)
        were read as a third that nobody checked: that it arrives.

        So this asserts against the SHAPE THE ENDPOINT RETURNS, not the service's
        intermediate.
        """
        from app.services.completeness.collapse import collapse, summarise

        _decline(db, "production_log_daily", date(2026, 5, 1))
        shown, closing = summarise(collapse(
            review(db, TENANT, "manufacturing", date(2026, 8, 13))
        ))
        got = [r for r in shown if r.key == "production_log_daily"]
        assert got, (
            "the declined obligation never reached the response — it was "
            "folded into the quiet count, where it reads as up to date"
        )
        assert got[0].verdict == DECLINED
        assert "no on-site pours" in got[0].detail, "the reason was dropped"
        assert not got[0].actionable, "declined is an answer, not a gap"

    def test_the_quiet_count_does_not_absorb_a_declination(self):
        """The closing line says "N obligations current". A declined obligation
        is not current — it is one the tenant has said they do not have. Counting
        it there makes the sentence false, quietly, in the direction of
        reassurance: the reader is told a thing is up to date when what happened
        is that it was struck off.

        Hand-built rather than derived from `review()`, so the number the
        assertion checks is stated here and not computed by the code under test.
        """
        from app.services.completeness.collapse import Run, summarise

        declined = Run("d", "Deliveries", "driver", DECLINED,
                       date(2026, 8, 13), date(2026, 8, 13), 1, "Declined 1 May: no fleet")
        current = Run("b", "Bank feed", "admin", NOT_YET_DUE,
                      date(2026, 8, 13), date(2026, 8, 13), 1, "Due 14 Aug.")
        shown, closing = summarise([declined, current])

        assert declined in shown, "the declination was folded into the quiet count"
        assert closing == "1 obligation current.", (
            f"the quiet count is {closing!r} — with one genuinely-current "
            f"obligation and one declined, only the first is current"
        )


class TestADeclinationGovernsOnlyThePeriodsItCovers:
    """⚠️ DECLINING USED TO ERASE HISTORY, AND THAT MADE THE AFFORDANCE A BUTTON
    FOR CLEARING RED ROWS. Measured on testco at as_of=2026-08-13 before this
    landed: `production_log_daily` rendered `missing 6–11 Aug (6 periods)`, and
    declining it rendered `declined 13 Aug (1 period)` — six days gone, because
    the resolver emitted one current-period row and skipped the window.

    An answer given today must not rewrite last week. These pin that, because the
    D-2 authoring surface is only safe to build on top of it.
    """

    KEY = "production_log_daily"
    AS_OF = date(2026, 8, 13)

    def _decline(self, db, on, revoked=None):
        _decline(db, self.KEY, on, revoked=revoked)

    def _rows(self, db):
        return [r for r in review(db, TENANT, "manufacturing", self.AS_OF)
                if r.key == self.KEY]

    def test_periods_before_the_declination_keep_their_verdict(self, db):
        before = {r.period_start: r.verdict for r in self._rows(db)}
        assert MISSING in before.values(), "fixture assumption broke"

        self._decline(db, date(2026, 8, 11))
        after = {r.period_start: r.verdict for r in self._rows(db)}

        assert set(before) == set(after), (
            "declining changed WHICH periods are evaluated — the window is not "
            "the declination's to decide"
        )
        earlier = [p for p in after if p < date(2026, 8, 11)]
        assert earlier, "no period precedes the declination; test proves nothing"
        assert all(after[p] == before[p] for p in earlier), (
            f"declining rewrote earlier periods: "
            f"{ {p: (before[p], after[p]) for p in earlier if before[p] != after[p]} }"
        )
        assert all(after[p] == DECLINED for p in after if p >= date(2026, 8, 11))

    def test_a_revocation_resumes_the_obligation(self, db):
        """`[declined_on, revoked_on)` — the period a tenant resumes in is OWED,
        not forgiven. An inclusive end would leave that period ambiguous between
        the two episodes that touch it."""
        self._decline(db, date(2026, 8, 8), revoked=date(2026, 8, 11))
        got = {r.period_start: r.verdict for r in self._rows(db)}

        assert got[date(2026, 8, 8)] == DECLINED
        assert got[date(2026, 8, 10)] == DECLINED, "revocation started a day early"
        assert got[date(2026, 8, 11)] != DECLINED, (
            "the obligation was still declined on the day it was resumed"
        )

    @pytest.mark.parametrize("period_start,expected", [
        (date(2026, 8, 7), False),   # before it
        (date(2026, 8, 8), True),    # the day it begins — inclusive
        (date(2026, 8, 10), True),   # inside
        (date(2026, 8, 11), False),  # the day it is revoked — EXCLUSIVE
        (date(2026, 8, 12), False),  # after
    ])
    def test_the_range_is_half_open(self, period_start, expected):
        d = ex.Declination("k", "r", date(2026, 8, 8), "R. Okafor", "admin",
                           revoked_on=date(2026, 8, 11))
        assert (ex.declination_covering([d], period_start) is not None) is expected

    def test_an_unrevoked_declination_has_no_end(self):
        d = ex.Declination("k", "r", date(2026, 8, 8), "R. Okafor", "admin")
        assert ex.declination_covering([d], date(2099, 1, 1)) is not None

    def test_overlapping_episodes_resolve_by_a_stated_rule(self):
        """Sane data has none — D-1's partial unique index allows one live
        episode. If they ever exist the answer must be a RULE (most recent
        statement wins), not whichever the list happened to hold first, which is
        the ordering-decides-the-outcome defect this repo has shipped twice."""
        old = ex.Declination("k", "old", date(2026, 1, 1), "R. Okafor", "admin")
        new = ex.Declination("k", "new", date(2026, 8, 1), "R. Okafor", "admin")
        assert ex.declination_covering([old, new], date(2026, 8, 5)).reason == "new"
        assert ex.declination_covering([new, old], date(2026, 8, 5)).reason == "new"


class TestEvidenceAgainstADeclinationIsAFinding:
    """⚠️ A DECLINED OBLIGATION THAT RECEIVES EVIDENCE IS A FINDING. A tenant
    declared they do not do deliveries and a delivery row appeared — either the
    declination is wrong or something unexpected happened, and both want
    reporting. The old resolver could not see it: it skipped the probe on the
    declined branch, so the one thing worth catching was the one thing not
    looked for."""

    KEY = "production_log_daily"
    AS_OF = date(2026, 8, 13)

    def _decline(self, db):
        _decline(db, self.KEY, date(2026, 5, 1))

    def test_the_probe_runs_on_a_declined_period(self, db):
        """The capability claim, asserted directly. `observed` is the probe's
        result, so `None` on every declined row is what "we never looked" looks
        like — which is exactly what shipped."""
        self._decline(db)
        rows = [r for r in review(db, TENANT, "manufacturing", self.AS_OF)
                if r.key == self.KEY]
        assert rows and all(r.verdict == DECLINED for r in rows)
        assert all(r.observed is not None for r in rows), (
            "the probe did not run on a declined period, so a contradiction "
            "could never be detected"
        )

    def test_evidence_in_a_declined_period_is_contradicted(self, db, monkeypatch):
        """⚠️ `_probe` IS PATCHED RATHER THAN EVIDENCE INSERTED, DELIBERATELY.
        `production_log_entries` has NOT NULL FKs to `products` and `users`, and
        the shared tenant fixture creates neither — inserting real rows would
        pass on a seeded developer machine and fail on CI's bare Postgres, which
        is the precise defect `tests/_tenant.py` exists to stop. Patching the
        probe exercises the real `review()` path and depends on no seeded state.
        """
        from app.services.completeness import review as rv

        self._decline(db)
        monkeypatch.setattr(rv, "_probe", lambda *a, **k: 3)
        rows = [r for r in review(db, TENANT, "manufacturing", self.AS_OF)
                if r.key == self.KEY]

        assert rows and all(r.verdict == CONTRADICTED for r in rows)
        assert all(r.observed == 3 for r in rows)
        assert "no on-site pours" in rows[0].detail, "the declination was dropped"
        assert "3 arrived" in rows[0].detail, "the evidence was dropped"

    def test_contradicted_is_actionable_and_rendered(self):
        assert CONTRADICTED in ACTIONABLE
        assert CONTRADICTED in RENDERED
        assert CONTRADICTED in VERDICTS

    def test_a_collapsed_contradiction_does_not_invert_itself(self, db, monkeypatch):
        """⚠️ `contradicted` IS ACTIONABLE, AND THE ACTIONABLE RUN DETAIL SAYS
        "Nothing since 6 Aug" — the exact opposite of what a contradiction means.
        A row whose detail contradicts its own verdict is worse than one that did
        not collapse, because it still looks right."""
        from app.services.completeness import review as rv
        from app.services.completeness.collapse import collapse

        self._decline(db)
        monkeypatch.setattr(rv, "_probe", lambda *a, **k: 3)
        runs = [r for r in collapse(review(db, TENANT, "manufacturing", self.AS_OF))
                if r.key == self.KEY]

        assert len(runs) == 1 and runs[0].periods > 1, "nothing collapsed"
        assert "Nothing since" not in runs[0].detail, (
            f"the run detail inverts its own verdict: {runs[0].detail!r}"
        )
        assert "evidence arrived anyway" in runs[0].detail

    def test_a_broken_probe_stays_declined_but_says_so(self, db, monkeypatch):
        """⚠️ THE ONE JUDGEMENT CALL IN D-3, PINNED SO IT CANNOT DRIFT QUIET.
        Everywhere else `None` becomes `unknown`, because there the probe IS the
        verdict. Here it is not — a declination is a recorded statement and a
        database error cannot un-record it, so reporting `unknown` would have the
        review claim not to know something it does know. But the contradiction
        check silently degrading is the graceful path this module refuses, so the
        failure is SAID on the row."""
        from app.services.completeness import review as rv

        self._decline(db)
        monkeypatch.setattr(rv, "_probe", lambda *a, **k: None)
        rows = [r for r in review(db, TENANT, "manufacturing", self.AS_OF)
                if r.key == self.KEY]

        assert rows and all(r.verdict == DECLINED for r in rows), (
            "a broken probe changed the verdict of a recorded declination"
        )
        assert all("could not check" in r.detail for r in rows), (
            "the contradiction check failed silently — the row reads as a "
            "declination that was verified"
        )


class TestTheDeclinationTable:
    """CR-3 D-1 — `completeness_declinations` (`r169`).

    A declination is a tenant OBSERVATION, not a platform declaration: authored
    by an operator, dated, attributable, and reversible without a release. It
    used to live in `expectations.TENANT_DECLINED`, a code dict nothing could
    write to — which is what a placeholder for a table looks like, and which made
    the capability unreachable in exactly the way this arc exists to close.
    """

    KEY = "production_log_daily"

    def test_the_loader_reads_what_the_writer_wrote(self, db):
        """Column names, row→dataclass mapping, and the key. Everything the
        monkeypatched dict used to skip."""
        from app.services.completeness.declinations import load_for_tenant

        _decline(db, self.KEY, date(2026, 5, 1), reason="no on-site pours",
                 name="R. Okafor", role="admin")
        got = load_for_tenant(db, TENANT)

        assert self.KEY in got, f"nothing loaded for {self.KEY}: {list(got)}"
        (d,) = got[self.KEY]
        assert d.expectation_key == self.KEY
        assert d.declined_on == date(2026, 5, 1)
        assert d.reason == "no on-site pours"
        assert d.declined_by_name == "R. Okafor"
        assert d.declined_by_role_slug == "admin"
        assert d.revoked_on is None

    def test_revoked_episodes_are_loaded_too(self, db):
        """⚠️ FILTERING TO THE LIVE ONES WOULD REWRITE HISTORY IN THE OTHER
        DIRECTION. A period inside a PAST declination would render `missing` —
        the tenant told to file production logs for the months they had already
        told us they were not producing. The loader brings every episode; the
        range check decides which governs which period."""
        from app.services.completeness.declinations import load_for_tenant

        _decline(db, self.KEY, date(2026, 3, 1), revoked=date(2026, 6, 1))
        got = load_for_tenant(db, TENANT)
        assert got.get(self.KEY), "a revoked episode was dropped by the loader"
        assert got[self.KEY][0].revoked_on == date(2026, 6, 1)

    def test_episodes_accumulate_rather_than_replace(self, db):
        """Declined, resumed, declined again is THREE rows on one obligation —
        the history a delete would have erased and the reason revocation is
        in-row rather than a second kind of record."""
        from app.services.completeness.declinations import load_for_tenant

        _decline(db, self.KEY, date(2026, 1, 1), revoked=date(2026, 3, 1))
        _decline(db, self.KEY, date(2026, 5, 1), revoked=date(2026, 7, 1))
        _decline(db, self.KEY, date(2026, 8, 1))
        assert len(load_for_tenant(db, TENANT)[self.KEY]) == 3

    def test_at_most_one_LIVE_episode_is_enforced_by_the_index(self, db):
        """⚠️ THE PREDICATE `revoked_at IS NULL` IS ONLY AN ANSWER IF THE INDEX
        MAKES IT ONE. Without the partial unique, two live episodes could exist
        and "is this declined now" would be a query returning two rows — which is
        the latest-wins-over-unordered-rows shape that in-row revocation was
        chosen to avoid.
        """
        from sqlalchemy.exc import IntegrityError

        _decline(db, self.KEY, date(2026, 5, 1))
        with pytest.raises(IntegrityError):
            _decline(db, self.KEY, date(2026, 6, 1))
        db.rollback()

    def test_a_revoked_episode_does_not_block_a_new_one(self, db):
        """The other half of the same index, and the half a plain unique would
        have broken: a tenant who resumes must be able to decline again."""
        _decline(db, self.KEY, date(2026, 1, 1), revoked=date(2026, 3, 1))
        _decline(db, self.KEY, date(2026, 5, 1))  # must not raise

    @pytest.mark.parametrize("revoked_on,revoked_at_set", [
        (date(2026, 6, 1), False),   # effective date, never recorded
        (None, True),                # recorded, no effective date
    ])
    def test_the_two_revocation_columns_cannot_disagree(
        self, db, revoked_on, revoked_at_set
    ):
        """⚠️ THEY COULD, AND IT WAS MEASURED BEFORE THE CHECK EXISTED.

        `revoked_on` is the effective date; `revoked_at` is when the revocation
        was recorded. Legitimately different VALUES — revoke today, effective the
        1st — so they are not collapsed into one column. But their NULL-ness is
        one fact, and with only one of them set the system held two answers:
        `declination_covering` stopped at `revoked_on` and treated the episode as
        over, while `revoked_at IS NULL` — the partial unique index and the whole
        "is this declined now" predicate — still counted it live.

        Two derivations of one fact, in the table whose own design notes argue
        against them. Caught before r169 shipped; the constraint is why it cannot
        come back as a writer that forgets one column.
        """
        import uuid
        from datetime import datetime, timezone
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            db.execute(
                text(
                    "INSERT INTO completeness_declinations "
                    "(id, tenant_id, expectation_key, declined_on, reason, "
                    " declined_by_name, declined_by_role_slug, revoked_on, "
                    " revoked_at, created_at) "
                    "VALUES (:i,:t,:k,:d,'r','N','admin',:ron,:rat,:c)"
                ),
                {
                    "i": str(uuid.uuid4()), "t": TENANT, "k": self.KEY,
                    "d": date(2026, 1, 1), "ron": revoked_on,
                    "rat": datetime.now(timezone.utc) if revoked_at_set else None,
                    "c": datetime.now(timezone.utc),
                },
            )
            db.flush()
        db.rollback()

    def test_a_coherent_revocation_is_accepted(self, db):
        """The control. A constraint that refused everything would satisfy the
        test above and break the feature."""
        _decline(db, self.KEY, date(2026, 1, 1), revoked=date(2026, 6, 1))

    def test_declinations_do_not_leak_across_tenants(self, db):
        from app.services.completeness.declinations import load_for_tenant

        _decline(db, self.KEY, date(2026, 5, 1))
        assert load_for_tenant(db, "some-other-tenant") == {}

    def test_the_author_is_named_on_the_rendered_row(self, db):
        """⚠️ ATTRIBUTION AT THE POINT OF USE. A declination silences an
        obligation until someone revokes it; the cheapest thing that stops it
        being used to clear a report is that the row says who answered. Stored
        and never read would be the shape this arc keeps finding."""
        _decline(db, self.KEY, date(2026, 5, 1), name="R. Okafor", role="admin")
        rows = [r for r in review(db, TENANT, "manufacturing", date(2026, 8, 13))
                if r.key == self.KEY]
        assert rows
        assert "R. Okafor" in rows[0].detail, (
            f"the author is stored and not rendered: {rows[0].detail!r}"
        )
        assert "admin" in rows[0].detail, "the role held at write time is dropped"

    def test_the_code_dict_is_gone(self):
        """⚠️ TWO PRODUCERS OF ONE FACT IS THE DEFECT THIS ARC KEEPS UNWINDING.
        A dict and a table both answering "is this declined" would drift, and the
        dict is the one nobody can write to — so a tenant's answer and a
        developer's would disagree with no way to tell which was meant."""
        # ⚠️ THE CONTROL COMES FIRST. `hasattr` on a wrong module reference
        # returns False too, so a negative assertion alone passes vacuously —
        # the same silent-lookup family as `inspect.getsource` on a guessed name
        # returning "" and every assertion against it succeeding. Proving a
        # sibling attribute IS there is what makes the absence mean something.
        assert hasattr(ex, "TENANT_EXTRA"), (
            "the expectations module did not load as expected; the assertion "
            "below would pass for the wrong reason"
        )
        assert not hasattr(ex, "TENANT_DECLINED"), (
            "the code dict is back beside the table"
        )


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
        # Against RENDERED, not a restatement of the selection predicate — an
        # assertion that re-derives the implementation passes whatever the
        # implementation does, which is how `declined` went missing.
        assert all(r.verdict in RENDERED for r in shown)
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
