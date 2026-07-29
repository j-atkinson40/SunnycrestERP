"""S-1c — the time-based sweep's PER-PAIR isolation guarantee.

`check_time_based_workflows` cross-joins every active time-based workflow
against every active company. Pre-S-1c a single (workflow, tenant) pair
that raised while firing (a bad `start_run`, a transient DB error, a
config bug) aborted the ENTIRE sweep — every remaining tenant silently
went un-fired for that tick. This is the scheduler-side twin of the S-1b
Plaid-sweep hardening, with the same expected-vs-unexpected discipline:

  - EXPECTED non-fires (vertical mismatch, tier-3 not enrolled, no cron,
    out-of-window, already-fired, malformed cron) stay `continue`s — they
    are "not applicable", not failures, and never count as errors.
  - An UNEXPECTED raise while firing one pair is caught at the per-pair
    boundary: the session is rolled back, the failure is logged LOUDLY
    (ERROR + trace + the pair identity), counted, and the sweep CONTINUES
    for the remaining pairs.
  - The run then RAISES at the end iff any pair failed — a partial sweep
    is never reported as a clean run.

The tenant-scoped-workflow trick (workflow.company_id = one tenant id)
keeps the sweep's inner loop to a single tenant pair per workflow, fast
on a shared dev DB with many accumulated tenants — same approach as
test_workflow_scheduler_scheduled_dispatch.py.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import pytest


# ── Fixtures / helpers (mirror the 8b.5 dispatch test) ───────────────


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture(scope="module", autouse=True)
def _cleanup_test_workflows():
    """Drop this module's `wf_sched_*` workflows + their runs AND the
    `pairiso-*` tenants at teardown. Cleaning up our own companies keeps
    this new file off the COMPANY-LITTER tripwire's ledger — the general
    suite-rot trajectory is tracked in STATE, but a fresh file shouldn't
    add to it. (The pre-existing 8b.5 dispatch file's un-cleaned tenants
    are out of scope for S-1c.)"""
    yield
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.workflow import (
        Workflow,
        WorkflowRun,
        WorkflowRunStep,
        WorkflowStep,
    )

    db = SessionLocal()
    try:
        stale_ids = [
            w.id
            for w in db.query(Workflow)
            .filter(Workflow.id.like("wf_sched_%"))
            .all()
        ]
        if stale_ids:
            run_ids = [
                r.id
                for r in db.query(WorkflowRun)
                .filter(WorkflowRun.workflow_id.in_(stale_ids))
                .all()
            ]
            if run_ids:
                db.query(WorkflowRunStep).filter(
                    WorkflowRunStep.run_id.in_(run_ids)
                ).delete(synchronize_session=False)
                db.query(WorkflowRun).filter(
                    WorkflowRun.id.in_(run_ids)
                ).delete(synchronize_session=False)
            db.query(WorkflowStep).filter(
                WorkflowStep.workflow_id.in_(stale_ids)
            ).delete(synchronize_session=False)
            db.query(Workflow).filter(Workflow.id.in_(stale_ids)).delete(
                synchronize_session=False
            )
        # Workflows/runs gone → the pairiso tenants have no dangling FK.
        db.query(Company).filter(Company.slug.like("pairiso-%")).delete(
            synchronize_session=False
        )
        db.commit()
    finally:
        db.close()


def _make_tenant(tz_name: str = "America/New_York") -> str:
    from app.database import SessionLocal
    from app.models.company import Company

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"PAIRISO-{suffix}",
            slug=f"pairiso-{suffix}",
            is_active=True,
            vertical="manufacturing",
            timezone=tz_name,
        )
        db.add(co)
        db.commit()
        return co.id
    finally:
        db.close()


def _make_scheduled_workflow_scoped(*, cron: str, company_id: str) -> str:
    """Tenant-scoped so the sweep only iterates this one tenant pair."""
    from app.database import SessionLocal
    from app.models.workflow import Workflow

    db = SessionLocal()
    try:
        wf = Workflow(
            id=f"wf_sched_{uuid.uuid4().hex[:8]}",
            company_id=company_id,
            name=f"PairIso-{uuid.uuid4().hex[:4]}",
            description="S-1c per-pair isolation test.",
            tier=4,
            vertical=None,
            trigger_type="scheduled",
            trigger_config={"cron": cron},
            scope="tenant",
            is_active=True,
            is_system=False,
        )
        db.add(wf)
        db.commit()
        return wf.id
    finally:
        db.close()


def _count_scheduled_runs(db, workflow_id: str, company_id: str) -> int:
    from app.models.workflow import WorkflowRun

    return (
        db.query(WorkflowRun)
        .filter(
            WorkflowRun.workflow_id == workflow_id,
            WorkflowRun.company_id == company_id,
            WorkflowRun.trigger_source == "schedule",
        )
        .count()
    )


class _FrozenDatetime:
    """Freeze only `datetime.now(...)`; delegate everything else."""

    def __init__(self, fake_now: datetime):
        self._fake_now = fake_now

    def now(self, tz=None):
        if tz is None:
            return self._fake_now.replace(tzinfo=None)
        return self._fake_now.astimezone(tz)

    def __getattr__(self, name):
        import datetime as real_dt

        return getattr(real_dt.datetime, name)


# In-window "now" for cron "0 * * * *" (last fired 14:00 UTC, 5 min ago).
_IN_WINDOW = datetime(2026, 4, 21, 14, 5, 0, tzinfo=timezone.utc)


# ── Tests ────────────────────────────────────────────────────────────


class TestPairIsolation:
    def test_one_pair_failure_isolated_sweep_completes_then_raises(
        self, db_session, caplog
    ):
        """The load-bearing case: two tenant-scoped workflows both due to
        fire this tick; `start_run` raises for ONE. The sibling STILL
        fires (isolation), the failure is recorded loudly + counted, and
        the run raises at the end (a partial sweep is never clean)."""
        from app.services import workflow_engine, workflow_scheduler

        tenant_id = _make_tenant()
        bad_wf = _make_scheduled_workflow_scoped(
            cron="0 * * * *", company_id=tenant_id
        )
        good_wf = _make_scheduled_workflow_scoped(
            cron="0 * * * *", company_id=tenant_id
        )

        real_start_run = workflow_engine.start_run

        def flaky_start_run(*, workflow_id, **kwargs):
            if workflow_id == bad_wf:
                raise RuntimeError("boom firing this pair")
            return real_start_run(workflow_id=workflow_id, **kwargs)

        with caplog.at_level(logging.ERROR):
            with pytest.MonkeyPatch.context() as mp:
                mp.setattr(workflow_engine, "start_run", flaky_start_run)
                mp.setattr(
                    workflow_scheduler,
                    "datetime",
                    _FrozenDatetime(_IN_WINDOW),
                )
                with pytest.raises(RuntimeError, match="failed to fire"):
                    workflow_scheduler.check_time_based_workflows()

        # Isolation: the good pair fired despite the bad pair raising.
        assert _count_scheduled_runs(db_session, good_wf, tenant_id) == 1
        assert _count_scheduled_runs(db_session, bad_wf, tenant_id) == 0
        # Recorded loudly, with the failing pair's identity.
        assert any(
            rec.levelno == logging.ERROR
            and bad_wf in rec.getMessage()
            and tenant_id in rec.getMessage()
            for rec in caplog.records
        ), [r.getMessage() for r in caplog.records]

    def test_clean_sweep_reports_zero_start_errors_and_does_not_raise(
        self, db_session
    ):
        """A sweep where every due pair fires cleanly returns a summary
        carrying the new `start_errors` key == 0 and never raises."""
        from app.services import workflow_scheduler

        tenant_id = _make_tenant()
        wf_id = _make_scheduled_workflow_scoped(
            cron="0 * * * *", company_id=tenant_id
        )
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                workflow_scheduler, "datetime", _FrozenDatetime(_IN_WINDOW)
            )
            summary = workflow_scheduler.check_time_based_workflows()

        assert summary["start_errors"] == 0
        assert summary["scheduled_fired"] >= 1
        assert _count_scheduled_runs(db_session, wf_id, tenant_id) == 1

    def test_expected_non_fire_is_not_a_start_error(self, db_session):
        """An out-of-window scheduled workflow is an EXPECTED non-fire —
        it must NOT count as a start_error nor raise (the distinction the
        discipline turns on: not-applicable ≠ failed)."""
        from app.services import workflow_scheduler

        tenant_id = _make_tenant()
        wf_id = _make_scheduled_workflow_scoped(
            cron="0 * * * *", company_id=tenant_id
        )
        # 14:20 UTC — cron fired 14:00, 20 min ago → outside the 15-min
        # window. The pair is visited but legitimately does not fire.
        out_of_window = datetime(2026, 4, 21, 14, 20, 0, tzinfo=timezone.utc)
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                workflow_scheduler,
                "datetime",
                _FrozenDatetime(out_of_window),
            )
            summary = workflow_scheduler.check_time_based_workflows()

        assert summary["start_errors"] == 0
        assert _count_scheduled_runs(db_session, wf_id, tenant_id) == 0
