"""HC-1 A-3 — health findings reach a human as tasks.

The producer was never the problem. `run_health_check` computed correct findings
and nothing called it: two on-demand API routes, no scheduler, no briefing, no
widget. Production carried 15 stale draft journal entries for twenty days behind
a working "Review Drafts" action nobody was told about.

Cleans up its own `hct-` tenants (COMPANY-LITTER ratchet).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from app.database import SessionLocal
from app.models.company import Company
from app.models.journal_entry import JournalEntry
from app.models.task_details import TaskDetails
from app.models.vault_item import VaultItem
from app.services import audit_health_tasks as aht
from tests._cleanup import purge_companies_by_slug

_SLUG = "hct-"


@pytest.fixture(autouse=True)
def _purge():
    yield
    s = SessionLocal()
    try:
        purge_companies_by_slug(s, f"{_SLUG}%")
    finally:
        s.close()


@pytest.fixture
def env():
    s = SessionLocal()
    co = Company(id=str(uuid.uuid4()), name="HCT", slug=f"{_SLUG}{uuid.uuid4().hex[:8]}",
                 is_active=True, vertical="manufacturing")
    s.add(co); s.commit()
    yield {"s": s, "co": co.id}
    s.rollback(); s.close()


def _stale_draft(s, co, *, days_old=20):
    """A draft journal entry old enough to trip `stale_drafts` (>7 days)."""
    e = JournalEntry(
        id=str(uuid.uuid4()), tenant_id=co, entry_number=f"HCT-{uuid.uuid4().hex[:6]}",
        entry_type="manual", status="draft", entry_date=date.today(),
        period_month=date.today().month, period_year=date.today().year,
        description="hct probe",
        created_at=datetime.now(timezone.utc) - timedelta(days=days_old),
    )
    s.add(e); s.commit()
    return e


def _tasks(s, co) -> list[TaskDetails]:
    return (
        s.query(TaskDetails)
        .join(VaultItem, VaultItem.id == TaskDetails.vault_item_id)
        .filter(VaultItem.company_id == co,
                TaskDetails.provenance_kind == aht.PROVENANCE_KIND)
        .all()
    )


class TestAFindingBecomesATask:

    def test_a_stale_draft_raises_a_task_that_actually_exists(self, env):
        """Renders, not compiles: the row is read back from the database."""
        _stale_draft(env["s"], env["co"])
        out = aht.raise_tasks_for_health_findings(env["s"], env["co"])
        assert "stale_drafts" in out["created"]

        rows = _tasks(env["s"], env["co"])
        codes = {r.provenance_ref_id.split("@", 1)[0] for r in rows}
        assert "stale_drafts" in codes

    def test_the_task_carries_the_action_the_operator_needs(self, env):
        _stale_draft(env["s"], env["co"])
        aht.raise_tasks_for_health_findings(env["s"], env["co"])
        row = next(r for r in _tasks(env["s"], env["co"])
                   if r.provenance_ref_id.startswith("stale_drafts@"))
        item = env["s"].get(VaultItem, row.vault_item_id)
        assert "draft" in (item.title or "").lower()
        assert row.current_state not in aht._terminal_states()

    def test_green_findings_never_become_tasks(self, env):
        """A tenant with nothing wrong is all green. Raising a task that says
        nothing is wrong is noise with a lifecycle attached."""
        out = aht.raise_tasks_for_health_findings(env["s"], env["co"])
        assert out["created"] == []
        assert _tasks(env["s"], env["co"]) == []


class TestSuppressionAndRecurrence:
    """The load-bearing pair. The obvious implementation gets the second wrong."""

    def test_a_second_run_does_not_duplicate(self, env):
        _stale_draft(env["s"], env["co"])
        first = aht.raise_tasks_for_health_findings(env["s"], env["co"])
        second = aht.raise_tasks_for_health_findings(env["s"], env["co"])
        assert "stale_drafts" in first["created"]
        assert "stale_drafts" in second["suppressed"]
        assert "stale_drafts" not in second["created"]
        assert len([r for r in _tasks(env["s"], env["co"])
                    if r.provenance_ref_id.startswith("stale_drafts@")]) == 1

    def test_a_RESOLVED_task_does_not_suppress_a_recurrence(self, env):
        """⚠️ THE ONE THE OBVIOUS IMPLEMENTATION GETS WRONG.

        `create_task_with_provenance` is idempotent on its composite key and the
        index behind it is `WHERE provenance_ref_id IS NOT NULL` — NOT filtered
        by state. Keying on the bare finding code would mean a resolved task
        blocks the condition ever being raised again: fixed once, silent
        forever. That is the fail-open shape this arc exists to close.
        """
        _stale_draft(env["s"], env["co"])
        aht.raise_tasks_for_health_findings(env["s"], env["co"])

        row = next(r for r in _tasks(env["s"], env["co"])
                   if r.provenance_ref_id.startswith("stale_drafts@"))
        row.current_state = "done"
        env["s"].commit()

        again = aht.raise_tasks_for_health_findings(env["s"], env["co"])
        assert "stale_drafts" in again["created"], (
            "the condition recurred and nothing was raised — a resolved task "
            "must not silence the next occurrence"
        )
        assert len([r for r in _tasks(env["s"], env["co"])
                    if r.provenance_ref_id.startswith("stale_drafts@")]) == 2

    @pytest.mark.parametrize("terminal", ["done", "cancelled"])
    def test_every_terminal_state_releases_the_suppression(self, env, terminal):
        _stale_draft(env["s"], env["co"])
        aht.raise_tasks_for_health_findings(env["s"], env["co"])
        row = next(r for r in _tasks(env["s"], env["co"])
                   if r.provenance_ref_id.startswith("stale_drafts@"))
        row.current_state = terminal
        env["s"].commit()
        assert "stale_drafts" in aht.raise_tasks_for_health_findings(env["s"], env["co"])["created"]

    def test_the_terminal_set_is_derived_not_restated(self):
        """A second hand-written list of terminal states would stop suppressing
        silently if a new one were added to the transition table."""
        from app.services.tasks.lifecycle import ACTION_TRANSITIONS, REMINDER_TRANSITIONS
        expected = {s for s, nxt in {**ACTION_TRANSITIONS, **REMINDER_TRANSITIONS}.items() if not nxt}
        assert aht._terminal_states() == expected


class TestItSurvivesTheScheduler:
    """`_run_per_tenant` calls `func(db, tid)` then `db.close()` with NO commit.
    A bridge that left the commit to it would create correct tasks and discard
    every one of them."""

    def test_tasks_persist_after_a_close_without_commit(self, env):
        _stale_draft(env["s"], env["co"])
        co = env["co"]
        db = SessionLocal()
        try:
            aht.raise_tasks_for_health_findings(db, co)
        finally:
            db.close()          # exactly what the scheduler does

        fresh = SessionLocal()
        try:
            rows = _tasks(fresh, co)
            assert rows, "the tasks did not survive the session closing"
        finally:
            fresh.close()


class TestItRunsTheCheckRatherThanReadingAStoredRow:

    def test_a_stale_stored_row_is_not_the_source(self, env):
        """`GET /reports/audit-health` returns the latest STORED AuditHealthCheck
        and only computes when none exists — so it can serve a months-old result.
        Raising a task from that would be the stale-status defect in a new
        place."""
        from app.models.report import AuditHealthCheck

        env["s"].add(AuditHealthCheck(
            tenant_id=env["co"], check_date=date.today() - timedelta(days=90),
            overall_score="red", green_count=0, amber_count=0, red_count=1,
            findings=[{"severity": "red", "category": "ghost", "code": "ghost_finding",
                       "message": "a finding from ninety days ago"}],
        ))
        env["s"].commit()

        out = aht.raise_tasks_for_health_findings(env["s"], env["co"])
        assert "ghost_finding" not in out["created"]
        assert out["check_date"] == str(date.today())


class TestReachability:
    """Five instances in this lineage of built-and-unreachable, one a mount that
    was an import and nothing else."""

    def test_it_is_in_JOB_REGISTRY(self):
        from app.scheduler import JOB_REGISTRY
        assert "audit_health_tasks" in JOB_REGISTRY
        assert callable(JOB_REGISTRY["audit_health_tasks"])

    def test_it_is_actually_SCHEDULED_not_merely_registered(self):
        """JOB_REGISTRY makes it manually triggerable. Being in the registry and
        never scheduled is precisely the built-and-unreachable shape."""
        import inspect

        from app import scheduler
        src = inspect.getsource(scheduler)
        assert 'id="audit_health_tasks"' in src
        assert "job_audit_health_tasks," in src

    def test_the_job_calls_the_bridge(self):
        import inspect

        from app.scheduler import job_audit_health_tasks
        src = inspect.getsource(job_audit_health_tasks)
        assert "raise_tasks_for_health_findings" in src
        assert "_run_per_tenant" in src


class TestOneFailureDoesNotCostTheOthers:

    def test_a_failing_creation_is_reported_not_swallowed(self, env, monkeypatch):
        _stale_draft(env["s"], env["co"])

        def boom(*a, **k):
            raise RuntimeError("task substrate unavailable")

        monkeypatch.setattr("app.services.tasks.service.create_task_with_provenance", boom)
        out = aht.raise_tasks_for_health_findings(env["s"], env["co"])
        assert out["failed"], "a failure must be reported, never returned as a clean run"
        assert out["created"] == []
