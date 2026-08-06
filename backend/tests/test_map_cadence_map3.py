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


def _cadence(db) -> dict[str, str]:
    script = build_area_ponder_script(db, vertical="manufacturing", area="Accounting")
    return {
        b["key"]: b["text"]
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

    def test_overnight_is_where_the_accounting_day_is(self, db):
        """Five of the seven scheduled jobs run between 10:30 PM and 3:00 AM.
        If that stops being true the beat should change, and this should fail
        rather than quietly teach the old shape."""
        c = _cadence(db)
        assert "cadence:nightly" in c
        assert "Bank reconciliation" in c["cadence:nightly"]

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

    def test_an_authored_CADENCE_caption_is_surfaced_with_its_derived_text(self):
        """Surfaced FOR REVIEW, not auto-detected. Knowing a caption is stale
        needs the derived text as of authoring, and captions store only text —
        so the check reports the pair a human needs to compare. Claiming
        automatic detection would be the same over-claim the beat avoids."""
        beats = [{
            "key": "cadence:nightly", "authored": True,
            "derived_text": "Overnight — A and B.",
        }]

        out = check_area_drift(beats, {"cadence:nightly": "our words"})

        assert len(out) == 1
        assert "schedule-coupled" in out[0]
        assert "Overnight — A and B." in out[0]

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
