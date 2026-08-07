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
from tests._synthetic_area import representative


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def area(db):
    """An area built in-test. The seeded Accounting area is the wrong substrate
    for a DERIVATION test — see `tests/_synthetic_area`."""
    from tests._synthetic_area import SyntheticArea

    a = SyntheticArea(db)
    yield a
    a.teardown()


def _cards(db, area="Accounting") -> dict[str, dict]:
    script = build_area_ponder_script(db, vertical="manufacturing", area=area)
    return {
        b["key"]: b for b in script["beats"] if b.get("cadence")
    }


class TestTheBeatsCarryTheirParts:
    """A card needs the pieces separately; the story needs them as a sentence.
    One derivation renders both."""

    def test_every_cadence_beat_carries_structure(self, db, area):
        for key, beat in _cards(db, representative(area, db)).items():
            c = beat["cadence"]
            assert c["grain"], f"{key} has no grain"
            assert c["label"], f"{key} has no label"
            assert isinstance(c["jobs"], list) and c["jobs"], f"{key} has no jobs"

    def test_the_sentence_still_renders_for_the_story(self, db, area):
        """MAP-3's altitude is KEPT. The story is not replaced by the cards —
        an operator who wants the whole rhythm still gets it in one narrative."""
        for beat in _cards(db, representative(area, db)).values():
            assert beat["text"], "a beat lost its sentence"

    def test_jobs_carry_IDS_so_a_chip_can_link(self, db, area):
        """The chip is the way INTO the task card. A name alone would render a
        card that names its members and cannot reach them — the affordance gap
        this session hit three times."""
        for beat in _cards(db, representative(area, db)).values():
            for job in beat["cadence"]["jobs"]:
                assert job.get("id"), f"{job.get('name')} has no id to link to"


class TestTheTimesAreSurfaced:
    def test_overnight_carries_its_ACTUAL_times(self, db, area):
        """"Overnight" loses that it is 10:30 PM to 3:00 AM. Someone deciding
        when to sit down with the queue needs the number, not the adjective —
        the story keeps the adjective, the card shows both.

        ⚠️ RESHAPED off the seeded area: the times are given here, so the claim
        is that the card SURFACES them rather than that this database happens to
        have a 10:30 PM schedule adopted."""
        area.job("Early", schedules=["Every day at 10:30 PM"])
        area.job("Late", schedules=["Every day at 3:00 AM"])
        db.commit()

        whens = _cards(db, area.name)["cadence:nightly"]["cadence"]["whens"]
        assert len(whens) == 2, "both clock times survive the grain collapse"
        assert any("10:30 PM" in w for w in whens)
        assert any("3:00 AM" in w for w in whens)

    def test_one_grain_does_not_lose_a_second_job_on_the_same_time(
        self, db, area
    ):
        """The bucket de-dupes WHENS but must not de-dupe JOBS — two jobs on the
        identical schedule are two chips under one clock."""
        area.job("First", schedules=["Every day at 11:00 PM"])
        area.job("Second", schedules=["Every day at 11:00 PM"])
        db.commit()

        c = _cards(db, area.name)["cadence:nightly"]["cadence"]
        assert c["whens"] == ["Every day at 11:00 PM"]
        assert {j["name"] for j in c["jobs"]} == {"First", "Second"}

    def test_the_no_schedule_group_carries_NO_times(self, db, area):
        """Nothing runs them, so there is nothing to show — and an empty list
        renders no clock rather than a misleading one."""
        assert _cards(db, representative(area, db))["cadence:none"]["cadence"]["whens"] == []


class TestTheNoScheduleGroup:
    def test_it_is_named_for_what_the_work_IS(self, db, area):
        """"On your schedule", not "No schedule". A category defined by absence
        still describes real work, and it is the group an operator actually asks
        about: what do I do that isn't automatic.

        ⚠️ RESHAPED. The old version asserted `len(jobs) == 4` — a COUNT of what
        the seeded area happened to hold, which says nothing about the grouping
        and breaks whenever content changes. What matters is that a job with no
        automation lands here and one with an automation does not."""
        area.job("By hand")
        area.job("Also by hand")
        area.job("Automated", schedules=["Every day at 9:00 PM"])
        db.commit()

        c = _cards(db, area.name)["cadence:none"]["cadence"]
        assert c["label"] == "On your schedule"
        assert {j["name"] for j in c["jobs"]} == {"By hand", "Also by hand"}
        assert c["whens"] == [], "nothing runs them, so there is no clock"


class TestTheAuthoredProse:
    def test_every_grain_ships_with_a_sentence(self):
        """r158 seeds them. A card rendering rhythms with empty prose is worse
        than one that arrives with a sentence — the derived fallback would only
        repeat the job list the card already shows as chips.

        ⚠️ RESHAPED to read the MIGRATION'S CONSTANTS rather than a database.
        The old version asked "does the seeded area render authored prose",
        which is true only where r158 ran AND the area has beats — two
        preconditions for a claim about coverage. The claim is that every grain
        the generator can emit has a caption, and that is checkable from the
        two constants alone."""
        import importlib.util
        from pathlib import Path

        from app.services.maps_of_content.area_ponder import _GRAIN_ORDER

        p = (Path(__file__).resolve().parents[1] / "alembic" / "versions"
             / "r158_accounting_cadence_captions.py")
        spec = importlib.util.spec_from_file_location("r158_under_test", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # ⚠️ `other` IS A KNOWN GAP, FOUND BY THIS RESHAPE AND PINNED RATHER
        # THAN NARROWED AWAY. `_grain_of` returns "other" for any schedule
        # string outside its vocabulary, `_GRAIN_ORDER` includes it, and
        # `_GRAIN_LABEL` gives it a name — so the generator CAN emit a
        # `cadence:other` card, and r158 ships no caption for it. That card
        # renders label + chips + times with derived-only prose. Not fixable
        # here: r158 has already applied, so the caption needs r159 or the
        # seed-side equivalent. The old test could not have found this — it
        # asked whether the SEEDED area rendered authored prose, and the seeded
        # area has no schedule string weird enough to reach "other".
        KNOWN_UNCAPTIONED = {"other"}

        for grain in list(_GRAIN_ORDER) + ["none"]:
            if grain in KNOWN_UNCAPTIONED:
                assert f"cadence:{grain}" not in mod._CAPTIONS, (
                    f"{grain!r} gained a caption — delete it from "
                    f"KNOWN_UNCAPTIONED so this test guards it properly."
                )
                continue
            assert f"cadence:{grain}" in mod._CAPTIONS, (
                f"the generator can emit grain {grain!r} and r158 ships no "
                f"caption for it — that card renders the derived fallback, "
                f"which only repeats its own chips."
            )

    def test_the_monthly_caption_does_not_teach_the_lock(self):
        """⚠️ AN EARLIER DRAFT ENDED "…the close locks the period when you
        approve it." True, and the closest the Map has come to the clean-queue
        claim: a mechanism sentence beside a queue list invites the reader to
        infer an ordering NOTHING ENFORCES. The lock is the close's own business
        and is taught on that task's card.

        Same reasoning kept live counts off these cards — proximity does
        argumentative work that prose would be held accountable for.

        ⚠️ THIS ONE IS A CONTENT TEST AND STAYS ONE — the only survivor of the
        classification. Every other test in this file asks whether the code
        DERIVES correctly and would still be meaningful if the shipped text
        changed, so those moved to a synthetic area. This one asks whether the
        SHIPPED SENTENCE says a specific thing, and changing r158's text SHOULD
        break it. That is the whole job.

        What it stops doing is reading the text back out of a database — the
        caption is the migration's constant, and going through a render only
        added two preconditions (r158 applied, the area has beats) to a claim
        about prose."""
        import importlib.util
        from pathlib import Path

        p = (Path(__file__).resolve().parents[1] / "alembic" / "versions"
             / "r158_accounting_cadence_captions.py")
        spec = importlib.util.spec_from_file_location("r158_monthly", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        text = mod._CAPTIONS["cadence:monthly"].lower()
        for claim in ("locks the period", "clean queue", "before you close",
                      "clear these first"):
            assert claim not in text


class TestTheDriftCheckWasRePointed:
    def test_the_SHIPPED_captions_produce_no_drift(self):
        """THE REGRESSION MAP-4 CAUSED AND FIXED. The first version flagged any
        authored cadence caption; seeding five made every render emit five
        warnings. A check that fires on the expected state is one nobody reads.

        ⚠️ RESHAPED to run the check DIRECTLY over r158's captions and beats
        carrying the parts a caption could echo. The old version asserted
        `script["drift"] == []` on the seeded area — which passes trivially
        when the area has no cadence beats at all, i.e. it was GREEN ON A
        DATABASE WHERE THE THING IT GUARDS COULD NOT HAPPEN."""
        import importlib.util
        from pathlib import Path

        from app.services.maps_of_content.area_ponder import check_area_drift

        p = (Path(__file__).resolve().parents[1] / "alembic" / "versions"
             / "r158_accounting_cadence_captions.py")
        spec = importlib.util.spec_from_file_location("r158_drift", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        beats = [
            {
                "key": key, "authored": True, "text": text,
                # The parts a caption COULD restate — a clock time and a job
                # name. Present so the check has something to catch; the point
                # is that the shipped prose does not name them.
                "cadence": {
                    "whens": ["Daily · 11:30 PM", "Monthly · 1st, 6:00 AM"],
                    "jobs": [{"id": "x", "name": "Bank reconciliation"}],
                },
            }
            for key, text in mod._CAPTIONS.items()
        ]
        assert check_area_drift(beats, {}) == []

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
