"""MAP-5 — a card shows EVERY schedule a task runs on, not the first one.

⚠️ THE DEFECT. `resolve_task` took `next((t for t in active_triggers if t.kind ==
"schedule"), None)` and humanized that one, silently dropping every schedule
after it. MEASURED [PLATFORM-WIDE]: `Pull Bank Transactions` carries TWO active
schedule triggers — `30 22 * * *` and `30 6 * * *` — and rendered as
"Daily · 10:30 PM" alone, while its runs land at 06:31 daily. A twice-daily job
shown as once-daily.

⚠️ WHY IT SHIPS WITH LIVENESS RATHER THAN AFTER IT. A liveness line reading "last
ran 6 hours ago" beside a clock time 14 hours old looks like the NEW feature is
broken, while being exactly correct. Shipping liveness onto a frequency that drops
half a schedule would make the new thing look like the defect.

⚠️ AND THE NAIVE FIX READS AS A BUG. `humanize_schedule` returns "<cadence> ·
<time>", so joining two with the same separator gives
"Daily · 10:30 PM · Daily · 6:30 AM" — the cadence repeats and the join collides
with the separator already inside each phrase. A correct fix that looks wrong is
its own defect on a teaching surface.
"""
from __future__ import annotations

import pytest

from app.services.maps_of_content.task_catalog import _join_frequencies


class TestSharedCadenceIsStatedOnce:
    def test_the_production_case(self):
        """`Pull Bank Transactions`, the job that exposed this."""
        assert _join_frequencies(["Daily · 10:30 PM", "Daily · 6:30 AM"]) == (
            "Daily · 10:30 PM and 6:30 AM"
        )

    def test_three_times_use_a_serial_list(self):
        assert _join_frequencies(
            ["Daily · 10:30 PM", "Daily · 6:30 AM", "Daily · 2:00 PM"]
        ) == "Daily · 10:30 PM, 6:30 AM and 2:00 PM"

    def test_the_cadence_is_not_repeated(self):
        """The specific ugliness the helper exists to avoid."""
        out = _join_frequencies(["Daily · 10:30 PM", "Daily · 6:30 AM"])
        assert out.count("Daily") == 1


class TestMixedAndDegenerateShapes:
    def test_mixed_cadences_fall_back_to_semicolons(self):
        """Unambiguous beats pretty. "Daily · 6:00 AM and Mon, 7:00 AM" would
        read as one cadence with two times, which is false."""
        assert _join_frequencies(
            ["Daily · 6:00 AM", "Weekly · Mon, 7:00 AM"]
        ) == "Daily · 6:00 AM; Weekly · Mon, 7:00 AM"

    @pytest.mark.parametrize("phrases,expected", [
        ([], None),
        (["Daily · 10:30 PM"], "Daily · 10:30 PM"),
        (["Monthly"], "Monthly"),
    ])
    def test_zero_and_one(self, phrases, expected):
        assert _join_frequencies(list(phrases)) == expected

    def test_a_phrase_without_the_separator_does_not_crash(self):
        """Not every humanization carries " · " — a bare "Monthly" has no time
        part, and mixing one with a timed phrase must not raise."""
        assert _join_frequencies(["Monthly", "Daily · 6:00 AM"]) == (
            "Monthly; Daily · 6:00 AM"
        )


class TestTheCallSiteTakesAllOfThem:
    def test_resolve_task_no_longer_takes_only_the_first(self):
        """Guards the actual defect rather than only the helper. `next(...)`
        returning the first match is the silent-lookup family: it lands on the
        wrong thing rather than on nothing."""
        import inspect

        from tests._source import code_only

        from app.services.maps_of_content import task_catalog

        src = code_only(inspect.getsource(task_catalog.resolve_task))
        assert 'next((t for t in active_triggers if t.kind == "schedule")' not in src
        assert "schedule_triggers = [" in src
