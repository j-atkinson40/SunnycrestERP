"""MAP-3 — the area story carries the area's rhythm, derived.

CADENCE WAS ALREADY DERIVED AND THE JOB BRANCH DROPPED IT. `task_catalog.py`
resolves an automation's schedule through a three-tier chain — the mirrored
runtime Workflow's trigger when `schedule_authority == "runtime_scheduler"`,
else the first active MoCTaskTrigger, else the manual `frequency` string — and
the automation beat renders it. When Reframe R-2 made JOBS the map's face, the
job branch was written without it, so an area whose jobs lead taught WHAT runs
and never WHEN.

⚠️ THE SENTENCE THIS DELIBERATELY DOES NOT SAY. "The month closes on a clean
queue" is aspiration, not description: month-end close gates on the PeriodLock
and the statement-run conflict check, NOT on queue state. A teaching surface
asserting an unenforced constraint is the failure this arc has been eliminating,
and it is the easiest one to commit because the arc makes it feel true.
`test_it_does_not_assert_the_clean_queue_constraint` pins the absence.

Grouping by grain is also THE CAP FIX rather than a side benefit:
`_TASK_BEAT_CAP = 10` against Accounting's ELEVEN jobs means the area story
already truncated one into "…and N more".

Cleans up its own `map3-` tenants (COMPANY-LITTER ratchet).
"""
from __future__ import annotations

import pytest

from app.database import SessionLocal
from app.services.maps_of_content.area_ponder import (
    _GRAIN_LABEL, _grain_of, _join_names, build_area_ponder_script,
    check_area_drift,
)
from tests._cleanup import purge_new_companies  # noqa: F401


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def area(db):
    """An area built in-test. See `tests/_synthetic_area` for why the seeded
    Accounting area is the wrong substrate for a DERIVATION test."""
    from tests._synthetic_area import SyntheticArea

    a = SyntheticArea(db)
    yield a
    a.teardown()


def _derived(db, area_name: str) -> dict[str, str]:
    script = build_area_ponder_script(db, vertical="manufacturing", area=area_name)
    return {
        b["key"]: b["derived_text"]
        for b in script["beats"] if b["key"].startswith("cadence")
    }


def _cadence(db) -> dict[str, str]:
    """The DERIVED sentence per cadence beat.

    ⚠️ READS `derived_text`, NOT `text`, AND THAT IS A DELIBERATE CHANGE. These
    tests originally read `text` — correct when nothing was authored, wrong the
    moment r158 (MAP-4) seeded a caption per grain, because `text` is then the
    OPERATOR'S prose and the derivation moves to `derived_text`.

    What these tests are about is the DERIVATION — that the rhythm is read from
    trigger schedules rather than written down. Following the authored text
    would have quietly turned them into assertions about r158's copy.
    """
    script = build_area_ponder_script(db, vertical="manufacturing", area="Accounting")
    return {
        b["key"]: b["derived_text"]
        for b in script["beats"] if b["key"].startswith("cadence")
    }


class TestGrainBucketing:
    """DELIBERATELY COARSE. Clock times matter for one automation; the GRAIN is
    what a person plans around — "I work the queues in the morning" is a fact
    about overnight, not about 11:30 PM."""

    @pytest.mark.parametrize("when,grain", [
        ("Every 15 minutes", "continuous"),
        ("Daily · 10:30 PM", "nightly"),
        ("Daily · 3:00 AM", "nightly"),
        ("Weekly · Mon, 8:00 AM", "weekly"),
        ("Monthly · 1st, 6:00 AM", "monthly"),
        ("When a case is opened", "other"),
    ])
    def test_it_buckets_to_the_rhythm_an_operator_thinks_in(self, when, grain):
        assert _grain_of(when) == grain

    def test_nine_accounting_clock_times_collapse_to_four_grains(self, db):
        """The whole argument for grouping: the accounting jobs occupy NINE
        distinct clock times and FOUR rhythms. Eleven cards taught eleven
        things; four grains teach a shape."""
        keys = {k for k in _cadence(db) if k != "cadence:none"}
        assert len(keys) <= 4, f"expected ≤4 grains, got {sorted(keys)}"


class TestTheRhythmIsDerived:
    def test_the_area_story_now_carries_WHEN(self, db):
        """The job branch rendered no cadence at all before this."""
        assert _cadence(db), "the area story carries no rhythm"

    def test_overnight_gathers_the_jobs_whose_automations_run_at_night(
        self, db, area
    ):
        """⚠️ RESHAPED. This asserted "Bank reconciliation is in overnight" on
        the SEEDED area — which passes where someone once adopted a schedule and
        fails everywhere else, and could not tell a broken derivation from an
        empty one. Both render as no cards.

        What MAP-3 built is the chain from a schedule string to a grain. So the
        schedules are given here, and the claim is about what the chain does
        with them: two night jobs land together under one grain, and the beat
        names them."""
        area.job("Matcher", schedules=["Every day at 11:30 PM"])
        area.job("Sweeper", schedules=["Every day at 3:00 AM"])
        area.job("Filing", schedules=["Monthly on the 1st at 6:00 AM"])
        db.commit()

        c = _derived(db, area.name)
        assert "cadence:nightly" in c
        assert "Matcher" in c["cadence:nightly"]
        assert "Sweeper" in c["cadence:nightly"]
        # The discrimination the old shape could not make: the monthly job is
        # NOT swept into overnight just because it also has a clock time.
        assert "Filing" not in c["cadence:nightly"]
        assert "Filing" in c["cadence:monthly"]

    def test_it_reads_the_SAME_precedence_the_automation_beat_reads(self, db):
        """One expression, two consumers — a job's rhythm and its automation's
        rhythm cannot disagree, because `_job_cadences` reads the identical
        `runtime_schedule_summary` / `derived_frequency` / `frequency` chain."""
        import inspect

        from app.services.maps_of_content import area_ponder as ap

        src = inspect.getsource(ap._job_cadences)
        for field in ("runtime_schedule_summary", "schedule_authority",
                      "derived_frequency", "frequency"):
            assert field in src


class TestAbsenceIsNamed:
    def test_jobs_with_no_schedule_are_NAMED_not_omitted(self, db):
        """Four of eleven have no automations at all. They are things an
        operator does rather than things the platform runs — a fact about the
        area worth teaching, not a gap to paper over. Omitting them would
        silently drop a third of Accounting from its own story."""
        c = _cadence(db)
        assert "cadence:none" in c
        assert "no schedule" in c["cadence:none"]
        assert "work you pick up" in c["cadence:none"]


class TestTheClaimItDoesNotMake:
    def test_it_does_not_assert_the_clean_queue_constraint(self, db):
        """⚠️ THE POINT. "The month closes on a clean queue" is FALSE as a
        description — nothing enforces it. Month-end close's preconditions are
        the PeriodLock and the statement-run conflict check.

        If that constraint is ever built, this test fails and someone reads the
        docstring before deciding whether the Map may now say it."""
        text = " ".join(_cadence(db).values()).lower()
        for claim in ("clean queue", "closes on a clean", "must be empty",
                      "before the month closes"):
            assert claim not in text

    def test_it_says_WHEN_and_not_what_the_operator_does(self, db):
        """The derived half is derived; consequence is authored over it or
        derived as a live count, never asserted."""
        text = " ".join(
            v for k, v in _cadence(db).items() if k != "cadence:none"
        ).lower()
        for overreach in ("you should", "make sure", "be sure to", "always "):
            assert overreach not in text


class TestTheDriftCheck:
    """`check_mirror_drift` guards the per-automation builder and nothing else.
    Cadence is the most schedule-coupled claim the Map can make, so authored
    prose over derived times is exactly that failure shape — on the generator
    that had no guard."""

    def test_an_orphaned_caption_is_reported(self):
        out = check_area_drift([{"key": "a", "authored": False}], {"gone": "x"})
        assert any("orphaned" in d and "gone" in d for d in out)

    def test_authored_prose_ALONE_is_no_longer_drift(self):
        """DELIBERATE PIN FLIP (MAP-4). This asserted, verbatim:

            beats = [{"key": "cadence:nightly", "authored": True,
                      "derived_text": "Overnight — A and B."}]
            out = check_area_drift(beats, {"cadence:nightly": "our words"})
            assert len(out) == 1
            assert "schedule-coupled" in out[0]

        THE PREMISE WAS WRONG, NOT THE INTENT. MAP-3 flagged any authored
        cadence caption on the assumption they were rare; MAP-4 seeded five, so
        every render emitted five warnings — a check crying wolf on the expected
        state, which trains people to stop reading the log.

        The hazard was always narrower: prose that RESTATES something derived.
        Durable prose is now permitted; see the two tests below for what still
        fires."""
        beats = [{
            "key": "cadence:nightly", "authored": True,
            "text": "Morning is for the queues.",
            "derived_text": "Overnight — A and B.",
            "cadence": {"whens": ["Daily · 11:30 PM"], "jobs": [{"name": "A"}]},
        }]

        assert check_area_drift(beats, {"cadence:nightly": "our words"}) == []

    def test_a_caption_RESTATING_derived_content_still_fires(self):
        """What the check now catches — the actual failure mode."""
        beats = [{
            "key": "cadence:nightly", "authored": True,
            "text": "A drafts at 11:30 PM.",
            "derived_text": "Overnight — A.",
            "cadence": {"whens": ["Daily · 11:30 PM"], "jobs": [{"name": "A"}]},
        }]

        out = check_area_drift(beats, {"cadence:nightly": "x"})

        assert len(out) == 1 and "restates derived content" in out[0]

    def test_an_UNauthored_cadence_beat_is_not_drift(self):
        """Derived-only content cannot be stale — it is re-read every render."""
        beats = [{"key": "cadence:nightly", "authored": False,
                  "derived_text": "x"}]
        assert check_area_drift(beats, {}) == []

    def test_drift_rides_the_payload_and_never_raises(self, db):
        """WARN, NEVER FAIL — `check_mirror_drift`'s contract. A ponder that
        refused to render would replace a possibly-stale story with no story."""
        script = build_area_ponder_script(db, vertical="manufacturing",
                                          area="Accounting")
        assert "drift" in script
        assert isinstance(script["drift"], list)


class TestTheJoiner:
    @pytest.mark.parametrize("names,expected", [
        (["A"], "A"),
        (["A", "B"], "A and B"),
        (["A", "B", "C"], "A, B, and C"),
    ])
    def test_it_reads_as_a_sentence_at_any_count(self, names, expected):
        assert _join_names(names) == expected

    def test_every_grain_has_a_label(self):
        from app.services.maps_of_content.area_ponder import _GRAIN_ORDER

        for grain in _GRAIN_ORDER:
            assert _GRAIN_LABEL.get(grain), f"{grain} renders without a label"
