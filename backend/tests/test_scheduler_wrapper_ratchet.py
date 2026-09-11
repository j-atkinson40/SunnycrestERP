"""Every scheduled job routes through a wrapper, or is on the list.

⚠️ THIS IS A RATCHET. It does not fix the twelve jobs that bypass the wrappers
today; it stops a thirteenth being added without anyone deciding to. A new
scheduled job either uses `_run_per_tenant` / `_run_global`, or somebody adds a
line to `BYPASSES_WRAPPER` below and says which kind of debt it is.

WHY IT MATTERS. The wrappers are what write `job_runs`. A job that bypasses them
either logs by hand (3 today) or leaves no record at all (9 today) — and "no
record" is worse than a wrong record, because the question "did this run last
night?" then has no answer from any durable store. Measured 2026-09-11:
`job_runs` holds 62,788 completed rows and is a log of SOME scheduled jobs, with
nothing inside the table declaring which.

⚠️ ENUMERATION IS AT RUNTIME, AND THAT IS THE WHOLE DESIGN.
`register_all_jobs()` registers ten of its jobs in a LOOP over a `nightly_jobs`
table. A static count of `add_job` CALL SITES therefore reports 28 where the real
population is 37 — a guard keyed on call sites would inherit exactly the blind
spot that produced the wrong count in the first place, and would be blind to it
permanently. Ask the scheduler what it holds.

⚠️ CLASSIFICATION READS THE REGISTERED CALLABLE, NOT THE SOURCE FILE. A job's
routing is decided by `fn.__code__.co_names` — the names that callable actually
references. Parsing `scheduler.py` cannot see the five jobs defined in
`services/calendar/sweeps.py` and `services/email/sweeps.py`. Both methods were
run 2026-09-11 and agreed on all 37; the code-object one is kept because it needs
no assumption about where a job is written.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from app import scheduler as sched

#: The two wrappers that write `job_runs` and interpret a reported error.
WRAPPERS = {"_run_per_tenant", "_run_global"}

#: ⚠️ THIS LIST IS DEBT, NOT DESIGN. Every entry is a scheduled job whose runs
#: are invisible or hand-logged. Adding a line here is a decision that a new job
#: should be invisible too — which is almost never what anyone wants.
#:
#: Categories, measured 2026-09-11:
#:   hand-rolled  — calls `_log_job_run` / `_complete_job_run` itself. Writes a
#:                  `job_runs` row, but nothing reads a returned error, so the
#:                  0a fix (292d8662) does not reach it.
#:   no-job_runs  — writes no `job_runs` row at all. "Did it run?" is
#:                  unanswerable from any durable store.
BYPASSES_WRAPPER: dict[str, str] = {
    # hand-rolled (3)
    "dispatch_auto_finalize": "hand-rolled — and the highest-volume job on production",
    "platform_health_recalculate": "hand-rolled",
    "platform_incident_dispatcher": "hand-rolled",
    # no job_runs row at all, defined in scheduler.py (4)
    "moc_event_matcher": "no-job_runs",
    "moc_schedule_sweep": "no-job_runs",
    "onboarding_pattern": "no-job_runs",
    "workflow_time_based_check": "no-job_runs",
    # no job_runs row at all, defined in services/*/sweeps.py (5)
    "calendar_subscription_renewal_sweep": "no-job_runs (external)",
    "calendar_token_refresh_sweep": "no-job_runs (external)",
    "email_imap_polling_sweep": "no-job_runs (external)",
    "email_subscription_renewal_sweep": "no-job_runs (external)",
    "email_token_refresh_sweep": "no-job_runs (external)",
}


@pytest.fixture
def registered():
    """Register every job, enumerate, and leave the scheduler as we found it.

    ⚠️ `remove_all_jobs()` RUNS IN SETUP AS WELL AS TEARDOWN, AND TEARDOWN-ONLY
    IS NOT SUFFICIENT. `register_all_jobs()` is NOT idempotent: called twice it
    yields 74 jobs rather than 37. Every `add_job` passes
    `replace_existing=True`, but an unstarted scheduler holds jobs in
    `_pending_jobs` while `replace_existing` consults the JOBSTORE — so there is
    nothing to replace against and the additions simply accumulate.

    If another test registered first and did not clean up, a teardown-only
    bracket would leave this test counting 74 and reading it as a population
    change. The doubling looks like a real number, which is what makes it
    dangerous.

    ⚠️ `sched.scheduler` is a MODULE-LEVEL SINGLETON. Five test files import
    `app.scheduler` — test_scheduler_reported_errors, test_audit_health_tasks_hc1,
    test_note_settling_sweep, test_responders, test_zip_alarm. None of them reads
    `get_jobs()`, so the exposure is low; the bracket is what keeps it low.
    """
    sched.scheduler.remove_all_jobs()
    sched.register_all_jobs()
    yield sched.scheduler.get_jobs()
    sched.scheduler.remove_all_jobs()


def _routes_through_wrapper(fn) -> bool:
    code = getattr(fn, "__code__", None)
    return bool(code and (WRAPPERS & set(code.co_names)))


# ── the ratchet ──────────────────────────────────────────────────────────


def test_every_scheduled_job_routes_through_a_wrapper_or_is_declared(registered):
    """⚠️ THE RATCHET. A new bypassing job fails here until someone lists it."""
    undeclared = sorted(
        j.id for j in registered
        if not _routes_through_wrapper(j.func) and j.id not in BYPASSES_WRAPPER
    )
    assert undeclared == [], (
        f"scheduled job(s) bypass _run_per_tenant/_run_global and are not "
        f"declared: {undeclared}. Route them through a wrapper, or add them to "
        f"BYPASSES_WRAPPER with the category — and note that adding a line means "
        f"accepting that the job's runs are hand-logged or invisible."
    )


# ── positive controls ────────────────────────────────────────────────────


def test_the_enumeration_is_NOT_EMPTY_and_sees_the_loop(registered):
    """⚠️ CONTROL 1. The ratchet asserts an ABSENCE, and an absence over an
    empty set passes trivially.

    The specific way it could be empty-but-plausible: `register_all_jobs()`
    silently registering nothing. The specific way it could be non-empty but
    WRONG: missing the ten jobs registered in the `nightly_jobs` loop, which is
    what a static call-site count does.

    So this asserts both a floor AND that a loop-registered job is present.
    """
    assert len(registered) >= 30, (
        f"enumeration returned {len(registered)} jobs — the ratchet above would "
        "pass over a near-empty set and mean nothing"
    )
    ids = {j.id for j in registered}
    assert "ar_aging_monitor" in ids, (
        "ar_aging_monitor is registered in the nightly_jobs LOOP; its absence "
        "means the enumeration is reading call sites, not registrations"
    )


def test_the_wrapper_detector_DISCRIMINATES(registered):
    """⚠️ CONTROL 2a. A detector that matched everything would also make the
    ratchet pass trivially. Assert it says yes to some and no to others."""
    routed = [j for j in registered if _routes_through_wrapper(j.func)]
    bypass = [j for j in registered if not _routes_through_wrapper(j.func)]
    assert routed and bypass, (
        f"detector did not discriminate: routed={len(routed)} bypass={len(bypass)}"
    )


def test_ADDING_a_bypassing_job_is_NAMED_by_the_ratchet(registered):
    """⚠️ CONTROL 2b — the break, with its own confirmation that it applied.

    Red is not enough. A test can go red because the fixture broke. So this
    asserts the job count actually rose, THEN that the ratchet names the new id
    specifically — not merely that something failed.
    """
    before = len(sched.scheduler.get_jobs())

    def _bypassing_job():  # references neither wrapper
        return None

    sched.scheduler.add_job(
        _bypassing_job, "interval", days=1, id="ratchet_probe_job",
    )
    after = sched.scheduler.get_jobs()
    assert len(after) == before + 1, (
        f"MARKER DID NOT APPLY: {before} -> {len(after)}. The break test proves "
        "nothing if the addition did not take."
    )

    undeclared = sorted(
        j.id for j in after
        if not _routes_through_wrapper(j.func) and j.id not in BYPASSES_WRAPPER
    )
    assert undeclared == ["ratchet_probe_job"], (
        f"ratchet did not name the added job; it reported {undeclared}"
    )
    sched.scheduler.remove_job("ratchet_probe_job")


# ── the list itself ──────────────────────────────────────────────────────


def test_no_STALE_entries_in_the_exception_list(registered):
    """⚠️ A stale exception is worse than a missing one.

    If a listed job is removed or renamed and its line stays, the list
    overstates the debt — and a NEW job later registered under that id would be
    pre-approved by a line nobody wrote for it.
    """
    ids = {j.id for j in registered}
    stale = sorted(set(BYPASSES_WRAPPER) - ids)
    assert stale == [], (
        f"BYPASSES_WRAPPER names job(s) that are no longer registered: {stale}. "
        "Remove the line — the debt was paid or the job was renamed."
    )


def test_register_all_jobs_needs_no_database_and_does_not_start():
    """The two properties the fixture relies on, asserted rather than assumed."""
    src = pathlib.Path(sched.__file__).with_suffix(".py").read_text()
    fn = next(
        n for n in ast.walk(ast.parse(src))
        if isinstance(n, ast.FunctionDef) and n.name == "register_all_jobs"
    )
    db_calls = {
        nm for x in ast.walk(fn) if isinstance(x, ast.Call)
        for nm in [getattr(x.func, "id", None) or getattr(x.func, "attr", None)]
        if nm in {"SessionLocal", "query", "commit", "execute", "connect"}
    }
    assert db_calls == set(), f"register_all_jobs touches the DB: {db_calls}"
    assert sched.scheduler.running is False
