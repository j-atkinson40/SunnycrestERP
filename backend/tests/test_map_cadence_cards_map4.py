"""MAP-4 — cadence as CARDS, and the drift check re-pointed at the real hazard.

MAP-3 derived the grains and put them in the area STORY: four sentences inside
one narrative behind a button. Correct content at the wrong altitude — an
operator who wanted month-end had to read the whole rhythm to find it.

The beats now carry their PARTS (grain, times, member jobs) alongside the
sentence, so a card and a sentence are two renderings of ONE derivation. If a
schedule moves, both move together; there is no second source of truth.

⚠️ THE DRIFT CHECK'S PREMISE CHANGED AND THE CHECK CHANGED WITH IT. MAP-3's
version flagged any authored caption on a cadence beat, on the assumption they
were rare. MAP-4 ships five seeded ones — so every render produced five
warnings, a check crying wolf on the expected state, which trains people to stop
reading the log. The real hazard is narrower: prose that RESTATES something
derived. "Morning is for the queues" cannot go stale; "the matcher runs at
11:30 PM" goes stale the moment someone re-crons it.

Cleans up nothing — pure read + pure function tests.
"""
from __future__ import annotations

import pytest

from app.database import SessionLocal
from app.services.maps_of_content.area_ponder import (
    build_area_ponder_script, check_area_drift,
)
from tests._cleanup import purge_new_companies  # noqa: F401


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


def _cards(db, area="Accounting") -> dict[str, dict]:
    script = build_area_ponder_script(db, vertical="manufacturing", area=area)
    return {
        b["key"]: b for b in script["beats"] if b.get("cadence")
    }


class TestTheBeatsCarryTheirParts:
    """A card needs the pieces separately; the story needs them as a sentence.
    One derivation renders both."""

    def test_every_cadence_beat_carries_structure(self, db):
        for key, beat in _cards(db).items():
            c = beat["cadence"]
            assert c["grain"], f"{key} has no grain"
            assert c["label"], f"{key} has no label"
            assert isinstance(c["jobs"], list) and c["jobs"], f"{key} has no jobs"

    def test_the_sentence_still_renders_for_the_story(self, db):
        """MAP-3's altitude is KEPT. The story is not replaced by the cards —
        an operator who wants the whole rhythm still gets it in one narrative."""
        for beat in _cards(db).values():
            assert beat["text"], "a beat lost its sentence"

    def test_jobs_carry_IDS_so_a_chip_can_link(self, db):
        """The chip is the way INTO the task card. A name alone would render a
        card that names its members and cannot reach them — the affordance gap
        this session hit three times."""
        for beat in _cards(db).values():
            for job in beat["cadence"]["jobs"]:
                assert job.get("id"), f"{job.get('name')} has no id to link to"


class TestTheTimesAreSurfaced:
    def test_overnight_carries_its_ACTUAL_times(self, db):
        """"Overnight" loses that it is 10:30 PM to 3:00 AM. Someone deciding
        when to sit down with the queue needs the number, not the adjective —
        the story keeps the adjective, the card shows both."""
        whens = _cards(db)["cadence:nightly"]["cadence"]["whens"]
        assert len(whens) >= 2
        assert any("10:30 PM" in w for w in whens)

    def test_the_no_schedule_group_carries_NO_times(self, db):
        """Nothing runs them, so there is nothing to show — and an empty list
        renders no clock rather than a misleading one."""
        assert _cards(db)["cadence:none"]["cadence"]["whens"] == []


class TestTheNoScheduleGroup:
    def test_it_is_named_for_what_the_work_IS(self, db):
        """"On your schedule", not "No schedule". A category defined by absence
        still describes real work, and four of eleven is far too many to drop.
        It is also the group an operator actually asks about: what do I do that
        isn't automatic."""
        c = _cards(db)["cadence:none"]["cadence"]
        assert c["label"] == "On your schedule"
        assert len(c["jobs"]) == 4


class TestTheAuthoredProse:
    def test_every_grain_ships_with_a_sentence(self, db):
        """r158 seeds them. A card rendering four rhythms with empty prose is
        worse than one that arrives with a sentence — the derived fallback would
        only repeat the job list the card already shows as chips."""
        for key, beat in _cards(db).items():
            assert beat["authored"], f"{key} has no authored prose"

    def test_the_monthly_caption_does_not_teach_the_lock(self, db):
        """⚠️ AN EARLIER DRAFT ENDED "…the close locks the period when you
        approve it." True, and the closest the Map has come to the clean-queue
        claim: a mechanism sentence beside a queue list invites the reader to
        infer an ordering NOTHING ENFORCES. The lock is the close's own business
        and is taught on that task's card.

        Same reasoning kept live counts off these cards — proximity does
        argumentative work that prose would be held accountable for."""
        text = _cards(db)["cadence:monthly"]["text"].lower()
        for claim in ("locks the period", "clean queue", "before you close",
                      "clear these first"):
            assert claim not in text


class TestTheDriftCheckWasRePointed:
    def test_the_SHIPPED_captions_produce_no_drift(self, db):
        """THE REGRESSION MAP-4 CAUSED AND FIXED. The first version flagged any
        authored cadence caption; seeding five made every render emit five
        warnings. A check that fires on the expected state is one nobody
        reads."""
        script = build_area_ponder_script(db, vertical="manufacturing",
                                          area="Accounting")
        assert script["drift"] == []

    def test_a_caption_that_restates_a_TIME_is_flagged(self):
        beats = [{
            "key": "cadence:monthly", "authored": True,
            "text": "Everything stages on the 1st and waits.",
            "cadence": {"whens": ["Monthly · 1st, 6:00 AM"], "jobs": []},
        }]

        out = check_area_drift(beats, {"cadence:monthly": "x"})

        assert len(out) == 1 and "restates derived content" in out[0]
        assert "1st" in out[0]

    def test_a_caption_that_restates_a_JOB_NAME_is_flagged(self):
        """Membership moves too — a job gaining or losing an automation changes
        which grain it sits in, and prose naming members goes stale silently."""
        beats = [{
            "key": "cadence:nightly", "authored": True,
            "text": "Collections drafts overnight.",
            "cadence": {"whens": [], "jobs": [{"name": "Collections"}]},
        }]

        out = check_area_drift(beats, {"cadence:nightly": "x"})

        assert len(out) == 1 and "Collections" in out[0]

    def test_durable_prose_is_NOT_flagged(self):
        """"Morning is for the queues" says what the operator DOES and cannot go
        stale. That is the shape the check is trying to permit."""
        beats = [{
            "key": "cadence:nightly", "authored": True,
            "text": "Morning is for the queues.",
            "cadence": {"whens": ["Daily · 11:30 PM"],
                        "jobs": [{"name": "Collections"}]},
        }]

        assert check_area_drift(beats, {"cadence:nightly": "x"}) == []

    def test_orphaned_captions_are_still_reported(self):
        """The other half of the check, unchanged."""
        out = check_area_drift([{"key": "a"}], {"gone": "x"})
        assert any("orphaned" in d for d in out)


class TestEmptyAreasRenderNothing:
    def test_cadence_beats_only_exist_on_the_JOB_branch(self):
        """The structural property, not a data-shaped count.

        My first version asserted "some area produces no cadence" and failed:
        this database has exactly two areas in `moc_job` and BOTH have
        scheduled work, so the assertion was about the fixture rather than the
        code. That is the count-taken-for-a-shape error, committed in a test.

        The real guarantee is structural — the cadence block sits inside
        `if area_jobs:`, so an area whose vocabulary type has automations but no
        JOBS emits no cadence beats at all, and the section renders nothing. A
        source read proves it for every area, present and future; a row count
        proves it for today's fixture.
        """
        import inspect

        from app.services.maps_of_content import area_ponder as ap

        src = inspect.getsource(ap.build_area_ponder_script)
        job_branch = src.index("if area_jobs:")
        cadence_block = src.index('f"cadence:{grain}"')
        else_branch = src.index("# ONE SHORT DERIVED BEAT PER AUTOMATION")

        assert job_branch < cadence_block < else_branch, (
            "the cadence block escaped the job branch — an automation-only area "
            "would now render a Rhythm section"
        )

    def test_the_frontend_section_is_conditional_on_the_beats(self):
        """The other half lives in `CadenceSection`, which returns null on an
        empty list rather than an empty heading. Asserted here as the contract
        the backend relies on: emitting nothing IS the empty state."""
        from pathlib import Path

        src = Path(
            "../frontend/src/components/moc-map/CadenceSection.tsx"
        ).read_text()
        assert "if (cards.length === 0) return null" in src
