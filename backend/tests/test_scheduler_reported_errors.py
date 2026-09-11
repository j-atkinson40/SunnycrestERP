"""The wrapper records a run whose target REPORTED an error.

Item 0a of the 2026-09-10 held-work list.

⚠️ THE FIXTURE SHAPE IS MEASURED, NOT INVENTED. `{"error": str(e)}` is what
`run_ar_aging_monitor`, `run_collections_sequence`, `run_ap_upcoming_payments`
and `run_reorder_suggestion_job` actually return from their broad except
handlers — enumerated by AST over every target `scheduler.py` wraps, 2026-09-11.
A fixture derived from reading the WRAPPER would be the same reading twice and
would prove nothing about the shipped path.
"""
from __future__ import annotations

import pytest

from app import scheduler as sch


# ── the pure part ────────────────────────────────────────────────────────


def test_reported_error_reads_the_marker_the_targets_actually_return():
    assert sch._reported_error({"error": "boom"}) == "boom"


def test_a_normal_summary_is_not_an_error():
    # The real success shape, from run_ar_aging_monitor's happy path.
    assert sch._reported_error(
        {"invoices_checked": 3, "alerts_created": 0, "sequences_started": 0}
    ) is None


def test_a_falsy_error_value_is_not_an_error():
    assert sch._reported_error({"error": None}) is None
    assert sch._reported_error({"error": ""}) is None


def test_a_non_dict_return_is_not_an_error():
    for v in (None, 0, "", [], "done", 7):
        assert sch._reported_error(v) is None


def test_NONE_IS_STILL_SUCCESS_and_that_is_the_remaining_gap():
    """⚠️ DELIBERATE, AND ASSERTED SO IT STAYS DELIBERATE.

    Eight targets swallow per-item inside a loop and return nothing. That
    tolerance is correct for one bad row and silent for a broken world — a
    loop in which every item fails still returns normally.

    Closing it needs a structured result that makes silent success
    unexpressible, which is a separate build. Pinned here so that widening
    `_reported_error` to treat `None` as failure is a decision someone makes
    against a red test, rather than a tweak that quietly changes 25 jobs.
    """
    assert sch._reported_error(None) is None


# ── the wrapper ──────────────────────────────────────────────────────────


@pytest.fixture
def recorded(monkeypatch):
    """Capture what the wrapper writes to job_runs, without a database."""
    calls: dict = {}
    monkeypatch.setattr(sch, "_log_job_run", lambda *a, **k: "run-1")
    monkeypatch.setattr(
        sch, "_complete_job_run",
        lambda run_id, status, duration, **kw: calls.update(
            status=status, **kw
        ),
    )
    monkeypatch.setattr(sch, "SessionLocal", lambda: _NullSession())
    return calls


class _NullSession:
    def close(self): pass


def test_per_tenant_records_FAILED_when_the_target_reports(recorded, monkeypatch):
    """⚠️ The case that was green for 264 consecutive production runs."""
    monkeypatch.setattr(sch, "_get_active_tenant_ids", lambda: ["t1", "t2"])
    sch._run_per_tenant("TEST_JOB", lambda db, tid: {"error": "date vs datetime"})
    assert recorded["status"] == "failed"
    assert recorded["error_count"] == 2
    assert recorded["success_count"] == 0
    assert "date vs datetime" in recorded["error_message"]


def test_per_tenant_counts_a_reporting_tenant_apart_from_a_clean_one(
    recorded, monkeypatch
):
    """The production shape exactly: some tenants fail, one has nothing to do."""
    monkeypatch.setattr(sch, "_get_active_tenant_ids", lambda: ["bad", "ok"])

    def target(db, tid):
        return {"error": "boom"} if tid == "bad" else {"invoices_checked": 0}

    sch._run_per_tenant("TEST_JOB", target)
    assert recorded["status"] == "failed"
    assert recorded["success_count"] == 1
    assert recorded["error_count"] == 1


def test_per_tenant_still_records_completed_when_nothing_reports(
    recorded, monkeypatch
):
    monkeypatch.setattr(sch, "_get_active_tenant_ids", lambda: ["t1"])
    sch._run_per_tenant("TEST_JOB", lambda db, tid: {"invoices_checked": 4})
    assert recorded["status"] == "completed"
    assert recorded["error_count"] == 0


def test_per_tenant_RAISING_is_unchanged(recorded, monkeypatch):
    """The 14 targets that propagate must behave exactly as before."""
    monkeypatch.setattr(sch, "_get_active_tenant_ids", lambda: ["t1"])

    def boom(db, tid):
        raise RuntimeError("raised not returned")

    sch._run_per_tenant("TEST_JOB", boom)
    assert recorded["status"] == "failed"
    assert recorded["error_count"] == 1
    assert "raised not returned" in recorded["error_message"]


def test_global_records_FAILED_when_the_target_reports(recorded):
    sch._run_global("TEST_JOB", lambda db: {"error": "sweep failed"})
    assert recorded["status"] == "failed"
    assert recorded["error_message"] == "sweep failed"


def test_global_still_completes_on_a_normal_return(recorded):
    sch._run_global("TEST_JOB", lambda db: {"generated": 3})
    assert recorded["status"] == "completed"
