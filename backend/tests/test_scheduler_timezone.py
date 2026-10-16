"""Every `CronTrigger` in `app/scheduler.py` declares its timezone.

⚠️ WHAT THIS EXISTS TO CATCH IS INVISIBLE IN THE SOURCE. `CronTrigger(hour=18)` reads
as fine. It is not: a trigger OBJECT does not inherit the scheduler's timezone, so until
2026-10-16 every cron job in that file fired on container UTC while its comment claimed
Eastern — the end-of-day invoice batch at 2 PM Eastern, the nightly block at 7 PM.

The mechanism, recorded because the next person to add a job will not guess it:

    BaseScheduler._create_trigger:
        if isinstance(trigger, BaseTrigger): return trigger      <-- returned UNTOUCHED
        ...
        trigger_args.setdefault("timezone", self.timezone)       <-- STRING triggers only

    CronTrigger.__init__:
        self.timezone = get_localzone()                          <-- UTC on the container

So `BackgroundScheduler(timezone=...)` is inert for every trigger in the file, and the
only thing that makes a job fire when its comment says is an explicit `timezone=`.

TWO INDEPENDENT ASSERTIONS, deliberately:

  * `test_every_crontrigger_in_source_declares_a_timezone` reads the SOURCE. It catches
    the form a reviewer scans for, and it fails on a newly-added bare trigger even if
    that job is never registered.
  * `test_every_registered_cron_job_has_a_non_local_timezone` reads the REGISTERED JOBS.
    It is the stronger of the two — it asserts what actually exists at runtime, covers a
    trigger constructed anywhere, and is the one that would have caught the original
    defect.

Neither subsumes the other: the static check misses a trigger built in another module,
and the runtime check misses a trigger that is written but not registered.

⚠️ THIS SUITE DOES NOT ASSERT *WHICH* TIMEZONE. Nine registrations are UTC on purpose —
`dispatch_auto_finalize` is a coverage window whose real gate is in-service and whose
production tenants are all UTC, and eight are minute-only cadences that fire at the same
instants in either zone. Pinning every job to Eastern would be wrong, and pinning the
specific split would make this a copy of `scheduler.py` rather than a check on it. What
is asserted is that the choice was MADE.
"""

from __future__ import annotations

import ast
import pathlib

import pytest
from apscheduler.triggers.cron import CronTrigger

# ⚠️ IMPORTED FROM `tzlocal`, THE SAME PLACE `CronTrigger` GETS IT
# (`apscheduler/triggers/cron/__init__.py:3`), so this test and the code under test
# agree on what "local" means by construction rather than by two lookups agreeing.
from tzlocal import get_localzone

SCHEDULER_PATH = pathlib.Path(__file__).resolve().parents[1] / "app" / "scheduler.py"

#: The names `scheduler.py` is allowed to pass as `timezone=`. A literal string is also
#: accepted — the point is that something was passed, not that it came from a constant.
ALLOWED_TZ_NAMES = {"BUSINESS_TZ", "UTC_TZ"}


def _crontrigger_calls() -> list[ast.Call]:
    tree = ast.parse(SCHEDULER_PATH.read_text())
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "CronTrigger"
    ]


def test_the_source_actually_contains_crontriggers():
    """Positive control for the static check.

    ⚠️ WITHOUT THIS, `test_every_crontrigger_in_source_declares_a_timezone` PASSES
    TRIVIALLY on an empty list — a renamed import, a refactor into a helper, or a typo
    in `node.func.id` all produce "0 bare triggers" and read as green. An absence is
    only evidence when the instrument is shown to be able to see.
    """
    calls = _crontrigger_calls()
    assert len(calls) >= 20, (
        f"found only {len(calls)} CronTrigger calls in {SCHEDULER_PATH.name}; "
        "the scanner is probably not matching (renamed import? wrapped in a helper?) "
        "rather than the file having genuinely shrunk"
    )


def test_every_crontrigger_in_source_declares_a_timezone():
    """Static: no bare `CronTrigger(...)` in `app/scheduler.py`."""
    bare = []
    for call in _crontrigger_calls():
        names = {kw.arg for kw in call.keywords}
        if "timezone" not in names:
            bare.append(call.lineno)

    assert not bare, (
        "CronTrigger built without an explicit timezone at "
        f"{SCHEDULER_PATH.name}:{bare}. A trigger object does NOT inherit the "
        "scheduler's timezone — it falls back to the container's local zone, which is "
        "UTC in production. Pass timezone=BUSINESS_TZ for a business-local time, or "
        "timezone=UTC_TZ if the time is genuinely UTC (and say why at the call site)."
    )


def test_crontrigger_timezones_come_from_the_declared_constants():
    """Static: the timezone is one of the two named constants, not an ad-hoc literal.

    Not about correctness — `timezone="America/New_York"` inline would behave
    identically. It is about the next bulk edit: a constant is greppable and a literal
    is twenty-five independent strings to keep in step.
    """
    offenders = []
    for call in _crontrigger_calls():
        for kw in call.keywords:
            if kw.arg != "timezone":
                continue
            if isinstance(kw.value, ast.Name) and kw.value.id in ALLOWED_TZ_NAMES:
                continue
            offenders.append((call.lineno, ast.dump(kw.value)))

    assert not offenders, (
        f"CronTrigger timezone should be BUSINESS_TZ or UTC_TZ; found {offenders}"
    )


def test_a_bare_crontrigger_still_inherits_the_local_zone():
    """⚠️ THE PREMISE OF THIS WHOLE FILE, PINNED — not a test of our code.

    Everything here rests on one APScheduler behaviour: a `CronTrigger` built without
    `timezone=` takes the MACHINE's zone, not the scheduler's. If a future version of
    the library starts threading the scheduler's timezone into pre-constructed
    triggers, the defect becomes unreachable and the guards above become ceremony —
    and this test is the thing that says so, by failing.

    Measured here rather than asserted from the docs: construct a bare trigger, read
    its zone, compare against `tzlocal`.
    """
    bare = CronTrigger(hour=18, minute=0)
    assert str(bare.timezone) == str(get_localzone()), (
        "a bare CronTrigger no longer picks up the machine's local zone "
        f"(got {bare.timezone!r}, local is {get_localzone()!r}). If APScheduler now "
        "inherits the scheduler's timezone, re-read this file's premise before "
        "trusting its other assertions."
    )


def test_every_registered_cron_job_declares_one_of_the_two_timezones():
    """Runtime: register the real jobs and inspect the triggers that exist.

    ⚠️ THE FIRST VERSION OF THIS TEST ASSERTED "not the machine's local zone" AND WAS
    BLIND IN BOTH DIRECTIONS. On a UTC machine a correctly-declared `UTC_TZ` trigger is
    the same value as an inherited one; on an Eastern machine a correctly-declared
    `BUSINESS_TZ` trigger is. It was written with a skip for the UTC case, then failed
    on the author's own Eastern laptop against 25 correctly-fixed jobs — which is the
    shape CLAUDE.md §11 names: a control that cannot distinguish itself from a failure
    is not a control.

    ⚠️ AND THE PROPERTY I WANTED IS NOT OBSERVABLE. A constructed `CronTrigger` keeps no
    record of whether its zone was passed or inherited; `.timezone` is just a zone. No
    runtime assertion can recover the provenance. The static check above is the only
    thing that sees the call site, which is why it is the primary guard and this is the
    secondary one.

    What this CAN assert, machine-independently: every registered cron job's zone is
    one of the two we chose. That catches a job pointed at some third zone, and it
    catches an inherited zone on any machine that is neither Eastern nor UTC (CI, most
    containers). On an Eastern or UTC machine it degrades to a weaker form of the
    static check — stated rather than skipped, because the assertion is still true and
    still worth making.
    """
    from app import scheduler as sched

    sched.register_all_jobs()
    jobs = sched.scheduler.get_jobs()
    assert jobs, "register_all_jobs() registered nothing"

    cron_jobs = [j for j in jobs if isinstance(j.trigger, CronTrigger)]
    assert len(cron_jobs) >= 30, (
        f"only {len(cron_jobs)} cron jobs registered; expected the full set — the "
        "scanner is probably wrong rather than the scheduler"
    )

    declared = {sched.BUSINESS_TZ, sched.UTC_TZ}
    offenders = [
        (j.id, str(j.trigger.timezone))
        for j in cron_jobs
        if str(j.trigger.timezone) not in declared
    ]
    assert not offenders, (
        f"registered cron jobs whose timezone is neither {sched.BUSINESS_TZ} nor "
        f"{sched.UTC_TZ}: {offenders}. On a machine that is neither of those, this is "
        "what an inherited (unpassed) timezone looks like."
    )

    local_key = str(get_localzone())
    if local_key in declared:
        # Not a skip: the assertions above ran and passed. This records that on THIS
        # machine they could not have caught an inherited zone, so the static check is
        # carrying the weight.
        print(
            f"\n  note: local zone is {local_key}, which is one of the declared two — "
            "an inherited zone would have been indistinguishable here. The static "
            "check is the discriminating one on this machine."
        )


def test_the_batch_and_the_nightly_block_are_business_local():
    """The two that step 1 of James's dispatch is actually about.

    Narrow on purpose — this names the jobs whose wrong firing time was the finding,
    rather than re-stating the whole Eastern/UTC split. `draft_invoice_service` marks
    orders delivered and drafts invoices; firing that four hours early put it at 2 PM
    Eastern, before an afternoon service.
    """
    from app import scheduler as sched

    sched.register_all_jobs()
    by_id = {j.id: j for j in sched.scheduler.get_jobs()}

    must_be_eastern = ["draft_invoice_generator", "ar_aging_monitor", "collections_sequence"]
    for job_id in must_be_eastern:
        assert job_id in by_id, f"{job_id} is not registered"
        tz = str(by_id[job_id].trigger.timezone)
        assert tz == sched.BUSINESS_TZ, f"{job_id} fires in {tz}, expected {sched.BUSINESS_TZ}"


def test_dispatch_auto_finalize_stays_utc():
    """⚠️ THE ONE HOUR-BEARING JOB THAT MUST NOT BE EASTERN.

    Its `hour="13-23"` is a coverage range, not a business time: it only has to open
    early enough to catch the earliest tenant's 13:00 local, and the real gate is
    `AUTO_FINALIZE_HOUR` inside `auto_finalize_pending_schedules`. Measured 2026-10-16,
    all four production tenants carry `companies.timezone = 'UTC'` and reach 13:00 local
    at 13:00 UTC. An Eastern window opens at 17:00 UTC and finalizes every one of them
    four hours late.

    This test exists because the obvious tidy-up — "make the whole file Eastern" — is
    a regression here, and nothing else in the suite would object.
    """
    from app import scheduler as sched

    sched.register_all_jobs()
    by_id = {j.id: j for j in sched.scheduler.get_jobs()}
    assert "dispatch_auto_finalize" in by_id
    tz = str(by_id["dispatch_auto_finalize"].trigger.timezone)
    assert tz == sched.UTC_TZ, (
        f"dispatch_auto_finalize fires in {tz}; it must stay UTC — see the comment at "
        "its registration and the docstring of auto_finalize_pending_schedules"
    )
