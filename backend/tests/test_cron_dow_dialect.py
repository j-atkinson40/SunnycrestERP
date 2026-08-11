"""The stored cron dialect is STANDARD CRON. Pinned, because APScheduler's is not.

⚠️ THE DEFECT. `CronTrigger.from_crontab` reads day-of-week 0 as MONDAY.
Standard cron — and every author who has typed one of these strings — means
SUNDAY. Verified empirically before the fix: `0..6` fired Monday…Sunday where the
author meant Sunday…Saturday. Every value, off by one.

Live consequence, stated at its true size: ONE workflow. `wf_sys_catalog_fetch`
carries `0 3 * * 1`, is documented "weekly Monday", and fetched on TUESDAYS. The
other two dow-carrying workflows were already `is_active=False` (r166, r167). A
"platform-wide dow bug" and "one catalog fetch runs a day late" are different
urgencies and the second is the true one.

WHY THIS TEST EXISTS RATHER THAN A COMMENT: the fix is one call-site rewrite, and
nothing else in the codebase would notice if it were reverted, refactored away, or
bypassed by a second parse site. The dialect is a contract with whoever writes the
next cron string, and a contract nothing checks is a convention — which is the
failure mode this codebase has been correcting all week.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.services.workflow_scheduler import (
    _intended_scheduled_fire,
    _standard_dow_to_names,
)

_TZ = ZoneInfo("America/New_York")
#: A Tuesday, so "next Monday" is unambiguous and six days out.
_BASE = datetime(2026, 8, 11, 12, 0, tzinfo=_TZ)

_STANDARD = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def _fires_on(cron: str) -> str:
    from apscheduler.triggers.cron import CronTrigger

    trigger = CronTrigger.from_crontab(_standard_dow_to_names(cron), timezone=_TZ)
    return trigger.get_next_fire_time(None, _BASE).strftime("%A")


class TestTheDialectIsStandardCron:
    @pytest.mark.parametrize("dow,expected", list(enumerate(_STANDARD)))
    def test_every_day_of_week_means_what_standard_cron_says(self, dow, expected):
        """THE WHOLE CONTRACT, all seven values. Before the fix every one of
        these was wrong by a day."""
        assert _fires_on(f"0 3 * * {dow}") == expected

    def test_seven_is_sunday_too(self):
        """Standard cron accepts 7 as an alias for Sunday. APScheduler's numeric
        range has no 7, so an untranslated `7` would raise rather than fire."""
        assert _fires_on("0 3 * * 7") == "Sunday"

    def test_the_live_case_fires_on_monday(self):
        """`wf_sys_catalog_fetch` — the one workflow the defect actually reached.
        Named explicitly so a regression is legible as "the catalog fetch moved
        back to Tuesday" rather than an abstract dialect failure."""
        assert _fires_on("0 3 * * 1") == "Monday"


class TestTranslationShapes:
    """Ranges, lists and steps — the forms a future author will reach for."""

    @pytest.mark.parametrize("cron,expected_dow", [
        ("0 3 * * 1-5", "mon-fri"),
        ("0 3 * * 1,3,5", "mon,wed,fri"),
        ("0 3 * * 0,6", "sun,sat"),
        ("0 3 * * 1-5/2", "mon-fri/2"),
    ])
    def test_numerics_are_translated_inside_compound_fields(self, cron, expected_dow):
        assert _standard_dow_to_names(cron).split()[4] == expected_dow

    @pytest.mark.parametrize("cron", [
        "0 3 * * *",          # wildcard
        "*/15 * * * *",       # wildcard, sub-hourly
        "0 3 * * mon",        # already a name
        "0 3 * * mon-fri",    # already names
        "0 6 1 * *",          # day-of-MONTH, dow untouched
    ])
    def test_untouched_forms_pass_through_unchanged(self, cron):
        """Passing a name through the numeric map would corrupt it, and a
        wildcard must never acquire a day."""
        assert _standard_dow_to_names(cron) == cron

    def test_a_malformed_expression_is_left_for_apscheduler_to_reject(self):
        """The translator must not swallow a bad cron — the caller already
        catches `ValueError` from the parser and skips that workflow with a log
        line. Turning it into a silent pass-through here would hide it."""
        assert _standard_dow_to_names("nonsense") == "nonsense"


class TestDayOfMonthIsUnaffected:
    """The claim that made this urgent was that Statement Run's 09-01 tick was
    at risk. It was not — its dow is `*`. Pinned so the false urgency is not
    re-derived."""

    def test_first_of_month_still_computes_correctly(self):
        fire = _intended_scheduled_fire(
            "0 6 1 * *", _TZ, datetime(2026, 9, 1, 6, 5, tzinfo=_TZ)
        )
        assert fire is not None, "the 1st-of-month tick must still be found"
        assert fire.day == 1 and fire.hour == 6

    def test_a_dow_free_cron_is_not_rewritten_at_all(self):
        assert _standard_dow_to_names("0 6 1 * *") == "0 6 1 * *"


class TestNoStoredCronWasPreCompensated:
    """The pre-flight that made the translation safe to land.

    If an author had already worked around the bug — writing `0` to get Monday —
    this fix would shift THEIR cron the wrong way. None had. Kept as a test
    because a pre-compensated expression added later would be silently broken by
    the translation that fixed everything else.
    """

    def test_no_definition_uses_a_dow_that_reads_as_compensation(self):
        from app.data.default_workflows import ALL_DEFAULT_WORKFLOWS

        suspicious = []
        for w in ALL_DEFAULT_WORKFLOWS:
            cron = (w.get("trigger_config") or {}).get("cron")
            if not cron:
                continue
            parts = cron.split()
            if len(parts) >= 5 and parts[4] == "0":
                suspicious.append(w["id"])
        assert not suspicious, (
            f"{suspicious} use dow=0. Under the corrected dialect that means "
            f"SUNDAY. If it was written to mean Monday as a workaround for the "
            f"APScheduler off-by-one, it is now wrong by a day — confirm the "
            f"author's intent before accepting this."
        )
