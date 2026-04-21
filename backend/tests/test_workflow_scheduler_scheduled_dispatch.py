"""Workflow Arc Phase 8b.5 — scheduler "scheduled" trigger dispatch.

Tests the cron-based dispatch path added to
`workflow_scheduler.check_time_based_workflows`.

Strategy:
  - Unit test the two new helpers (`_intended_scheduled_fire` +
    `_already_fired_scheduled`) directly — fast, isolated.
  - Integration test creates a TENANT-SCOPED workflow
    (`workflow.company_id = <one tenant id>`) so the sweep's
    cross-join only iterates one tenant pair, keeping the test
    fast on a shared dev DB with many accumulated tenants.

Coverage per Phase 8b.5 audit approved tests:
  1. `test_intended_fire_matches_cron_in_window`
  2. `test_intended_fire_returns_none_outside_window`
  3. `test_intended_fire_respects_timezone`
  4. `test_invalid_cron_raises_value_error`
  5. `test_already_fired_scheduled_detects_prior_run`
  6. `test_integration_scheduled_workflow_fires` (tenant-scoped)
  7. `test_integration_idempotency_within_window` (tenant-scoped)
  8. `test_integration_time_of_day_unchanged` (regression)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture(scope="module", autouse=True)
def _cleanup_test_workflows():
    """Drop any lingering `wf_sched_*` / `wf_tod_*` workflows + their
    runs at module teardown. Prevents accumulation across test runs on
    the shared dev DB (which would otherwise slow subsequent sweeps
    and trip the Phase 8a `tier=1 IMPLIES scope=core` invariant if
    fixtures were ever accidentally misconfigured)."""
    yield  # tests run here
    from app.database import SessionLocal
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
            .filter(
                Workflow.id.like("wf_sched_%") | Workflow.id.like("wf_tod_%")
            )
            .all()
        ]
        if not stale_ids:
            return
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
            name=f"SCHED-{suffix}",
            slug=f"sched-{suffix}",
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
    """Tenant-scoped workflow so the sweep's filter at
    `w.company_id and w.company_id != company.id` excludes every
    other tenant in the dev DB — keeps the test fast.

    tier=4 + scope="tenant" matches the Phase 8a convention (Tier 1
    is core; Tier 2/3 is vertical; Tier 4 is tenant). Preserves the
    invariant `tier=1 IMPLIES scope=core` asserted by
    `test_workflow_scope_phase8a.py::TestMigrationBackfill`.
    """
    from app.database import SessionLocal
    from app.models.workflow import Workflow

    db = SessionLocal()
    try:
        wf = Workflow(
            id=f"wf_sched_{uuid.uuid4().hex[:8]}",
            company_id=company_id,
            name=f"SchedTest-{uuid.uuid4().hex[:4]}",
            description="Phase 8b.5 scheduler-dispatch integration test.",
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


def _make_time_of_day_workflow_scoped(*, hhmm: str, company_id: str) -> str:
    from app.database import SessionLocal
    from app.models.workflow import Workflow

    db = SessionLocal()
    try:
        wf = Workflow(
            id=f"wf_tod_{uuid.uuid4().hex[:8]}",
            company_id=company_id,
            name=f"TODTest-{uuid.uuid4().hex[:4]}",
            description="Phase 8b.5 regression — time_of_day unchanged.",
            tier=4,
            vertical=None,
            trigger_type="time_of_day",
            trigger_config={
                "time": hhmm,
                "days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
            },
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


# ── Unit tests for _intended_scheduled_fire ──────────────────────────


class TestIntendedScheduledFire:
    """Unit tests for the cron-window matcher. Fast, no DB."""

    def test_intended_fire_matches_cron_in_window(self):
        from app.services.workflow_scheduler import _intended_scheduled_fire

        tz = ZoneInfo("America/New_York")
        # Cron "0 * * * *" fires at :00 every hour. At UTC 14:05 in NY
        # tz, the most recent fire was 14:00 NY (= UTC 18:00 roughly
        # depending on DST). Use an easier check: cron "0 * * * *"
        # with a tz — we supply now such that a cron fire occurred in
        # the last 15 min.
        # "now" = 2026-04-21 14:05 UTC; in NY that's 10:05 EDT. Cron
        # last fired at 10:00 NY = 14:00 UTC, which is 5 min ago.
        now = datetime(2026, 4, 21, 14, 5, 0, tzinfo=timezone.utc)
        intended = _intended_scheduled_fire("0 * * * *", tz, now)
        assert intended is not None
        # The returned fire time should be 14:00 UTC (10:00 NY).
        assert intended.astimezone(timezone.utc) == datetime(
            2026, 4, 21, 14, 0, 0, tzinfo=timezone.utc
        )

    def test_intended_fire_returns_none_outside_window(self):
        from app.services.workflow_scheduler import _intended_scheduled_fire

        tz = ZoneInfo("America/New_York")
        # "now" = 14:20 UTC; cron fired at 14:00 → 20 min ago → outside 15-min window.
        now = datetime(2026, 4, 21, 14, 20, 0, tzinfo=timezone.utc)
        intended = _intended_scheduled_fire("0 * * * *", tz, now)
        assert intended is None

    def test_intended_fire_respects_timezone(self):
        """Same cron interpreted in two different timezones fires at
        different UTC moments."""
        from app.services.workflow_scheduler import _intended_scheduled_fire

        # Cron "0 9 * * *" = 9am tenant-local daily.
        ny_tz = ZoneInfo("America/New_York")
        la_tz = ZoneInfo("America/Los_Angeles")

        # 2026-04-21 13:05 UTC = 09:05 NY (EDT -04). In window for NY.
        #                      = 06:05 LA (PDT -07). Way outside for LA.
        now_ny = datetime(2026, 4, 21, 13, 5, 0, tzinfo=timezone.utc)
        assert _intended_scheduled_fire("0 9 * * *", ny_tz, now_ny) is not None
        assert _intended_scheduled_fire("0 9 * * *", la_tz, now_ny) is None

        # 2026-04-21 16:05 UTC = 09:05 LA → fires for LA.
        now_la = datetime(2026, 4, 21, 16, 5, 0, tzinfo=timezone.utc)
        assert _intended_scheduled_fire("0 9 * * *", la_tz, now_la) is not None

    def test_invalid_cron_raises_value_error(self):
        from app.services.workflow_scheduler import _intended_scheduled_fire

        tz = ZoneInfo("America/New_York")
        now = datetime(2026, 4, 21, 14, 5, 0, tzinfo=timezone.utc)
        with pytest.raises(ValueError):
            _intended_scheduled_fire("not a cron", tz, now)


# ── Unit tests for _already_fired_scheduled ──────────────────────────


class TestAlreadyFiredScheduled:
    """Idempotency helper — fast, single-tenant writes only."""

    def test_detects_prior_run_with_matching_intended_fire(
        self, db_session
    ):
        """The idempotency check looks at
        `trigger_context.intended_fire` (canonical audit trail) — not
        `started_at` (wall-clock)."""
        from app.models.workflow import WorkflowRun
        from app.services.workflow_scheduler import _already_fired_scheduled

        tenant_id = _make_tenant()
        wf_id = _make_scheduled_workflow_scoped(
            cron="0 * * * *", company_id=tenant_id
        )
        intended_fire = datetime(
            2026, 4, 21, 14, 0, 0, tzinfo=timezone.utc
        )
        # Before any run: idempotency check is False (go ahead and fire).
        assert not _already_fired_scheduled(
            db_session,
            workflow_id=wf_id,
            company_id=tenant_id,
            intended_fire=intended_fire,
        )
        # Insert a run with matching intended_fire in trigger_context.
        db_session.add(
            WorkflowRun(
                id=str(uuid.uuid4()),
                workflow_id=wf_id,
                company_id=tenant_id,
                status="completed",
                trigger_source="schedule",
                started_at=intended_fire + timedelta(minutes=2),
                trigger_context={
                    "fired_at": "test",
                    "intended_fire": intended_fire.isoformat(),
                    "cron": "0 * * * *",
                },
            )
        )
        db_session.commit()
        # Now the check returns True (already fired for this tick).
        assert _already_fired_scheduled(
            db_session,
            workflow_id=wf_id,
            company_id=tenant_id,
            intended_fire=intended_fire,
        )

    def test_run_with_different_intended_fire_does_not_block(
        self, db_session
    ):
        """A WorkflowRun whose trigger_context records a DIFFERENT
        intended_fire (e.g., the previous hour's cron tick) doesn't
        count as a prior fire for the current tick."""
        from app.models.workflow import WorkflowRun
        from app.services.workflow_scheduler import _already_fired_scheduled

        tenant_id = _make_tenant()
        wf_id = _make_scheduled_workflow_scoped(
            cron="0 * * * *", company_id=tenant_id
        )
        intended_fire = datetime(
            2026, 4, 21, 14, 0, 0, tzinfo=timezone.utc
        )
        # A run for the PREVIOUS tick — different intended_fire.
        prev_tick = intended_fire - timedelta(hours=1)
        db_session.add(
            WorkflowRun(
                id=str(uuid.uuid4()),
                workflow_id=wf_id,
                company_id=tenant_id,
                status="completed",
                trigger_source="schedule",
                started_at=intended_fire - timedelta(minutes=5),
                trigger_context={
                    "fired_at": "prev",
                    "intended_fire": prev_tick.isoformat(),
                    "cron": "0 * * * *",
                },
            )
        )
        db_session.commit()
        assert not _already_fired_scheduled(
            db_session,
            workflow_id=wf_id,
            company_id=tenant_id,
            intended_fire=intended_fire,
        )


# ── Integration: full sweep with tenant-scoped workflow ──────────────


class TestSchedulerSweepIntegration:
    """These use `check_time_based_workflows()` but scope the workflow
    to a single tenant (workflow.company_id = tenant_id) so the
    sweep's inner loop excludes every other company in the dev DB.
    """

    def test_scheduled_workflow_fires_and_records_context(
        self, db_session
    ):
        from app.models.workflow import WorkflowRun
        from app.services import workflow_scheduler

        tenant_id = _make_tenant()
        wf_id = _make_scheduled_workflow_scoped(
            cron="0 * * * *", company_id=tenant_id
        )

        # 2026-04-21 14:05 UTC = 10:05 NY (EDT). Cron fires at :00
        # every hour → last fire was 14:00 UTC.
        fake_now = datetime(2026, 4, 21, 14, 5, 0, tzinfo=timezone.utc)
        with patch.object(
            workflow_scheduler, "datetime", new=_FrozenDatetime(fake_now)
        ):
            result = workflow_scheduler.check_time_based_workflows()

        assert result["scheduled_fired"] >= 1, result
        assert _count_scheduled_runs(db_session, wf_id, tenant_id) == 1

        run = (
            db_session.query(WorkflowRun)
            .filter(
                WorkflowRun.workflow_id == wf_id,
                WorkflowRun.company_id == tenant_id,
            )
            .first()
        )
        assert run is not None
        ctx = run.trigger_context or {}
        assert ctx.get("cron") == "0 * * * *"
        assert "intended_fire" in ctx
        assert "fired_at" in ctx

    def test_idempotency_within_window(self, db_session):
        """Second sweep for the same intended_fire does NOT create a
        second run."""
        from app.services import workflow_scheduler

        tenant_id = _make_tenant()
        wf_id = _make_scheduled_workflow_scoped(
            cron="0 * * * *", company_id=tenant_id
        )
        fake_now = datetime(2026, 4, 21, 14, 5, 0, tzinfo=timezone.utc)
        with patch.object(
            workflow_scheduler, "datetime", new=_FrozenDatetime(fake_now)
        ):
            workflow_scheduler.check_time_based_workflows()
            # Second sweep within the same 15-min window (simulating
            # two overlapping APScheduler ticks).
            workflow_scheduler.check_time_based_workflows()
        assert _count_scheduled_runs(db_session, wf_id, tenant_id) == 1

    def test_invalid_cron_skipped_gracefully(self, db_session, caplog):
        """Malformed cron on one workflow doesn't halt the sweep for
        a sibling workflow that has valid cron."""
        import logging

        from app.services import workflow_scheduler

        tenant_id = _make_tenant()
        bad_wf = _make_scheduled_workflow_scoped(
            cron="this is not cron", company_id=tenant_id
        )
        good_wf = _make_scheduled_workflow_scoped(
            cron="0 * * * *", company_id=tenant_id
        )
        fake_now = datetime(2026, 4, 21, 14, 5, 0, tzinfo=timezone.utc)
        with caplog.at_level(logging.WARNING):
            with patch.object(
                workflow_scheduler,
                "datetime",
                new=_FrozenDatetime(fake_now),
            ):
                result = workflow_scheduler.check_time_based_workflows()

        assert result["scheduled_skipped_invalid_cron"] >= 1
        assert _count_scheduled_runs(db_session, bad_wf, tenant_id) == 0
        assert _count_scheduled_runs(db_session, good_wf, tenant_id) == 1
        assert any(
            "Invalid cron expression" in rec.message for rec in caplog.records
        )

    def test_time_of_day_dispatch_unchanged(self, db_session):
        """Regression: existing time_of_day path still fires at its
        configured UTC wall-clock 15-min window."""
        from app.services import workflow_scheduler

        tenant_id = _make_tenant()
        wf_id = _make_time_of_day_workflow_scoped(
            hhmm="14:00", company_id=tenant_id
        )
        fake_now = datetime(2026, 4, 21, 14, 5, 0, tzinfo=timezone.utc)
        with patch.object(
            workflow_scheduler, "datetime", new=_FrozenDatetime(fake_now)
        ):
            result = workflow_scheduler.check_time_based_workflows()

        assert result["time_of_day_fired"] >= 1
        assert _count_scheduled_runs(db_session, wf_id, tenant_id) >= 1


# ── Frozen datetime helper ───────────────────────────────────────────


class _FrozenDatetime:
    """Minimal stand-in for the module-level `datetime` class reference
    in workflow_scheduler. Only `datetime.now(timezone.utc)` is
    frozen; other classmethods pass through to the real class."""

    def __init__(self, fake_now: datetime):
        self._fake_now = fake_now

    def now(self, tz=None):
        if tz is None:
            return self._fake_now.replace(tzinfo=None)
        return self._fake_now.astimezone(tz)

    def __getattr__(self, name):
        import datetime as real_dt

        return getattr(real_dt.datetime, name)
