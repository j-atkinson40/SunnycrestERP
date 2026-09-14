"""Item (c), commit 1 of 3 — the type, the wrapper's reading of it, and a ceiling.

⚠️ THIS IS A CEILING RATCHET: the number of targets NOT yet returning a
`JobOutcome` may only fall. Nothing is migrated in this commit; the ceiling
starts at the full population and each migration lowers it.

WHY A CEILING AND NOT AN ASSERTION OF ZERO. The removal rule: you cannot remove
a method while its callers still use it. A wrapper that refuses the old shapes
before the thirteen are migrated turns a latent ambiguity into a nightly
TypeError against live tenants. So the direction is enforced first, the callers
move second, and the refusal lands last.

THE POPULATION IS 13, ON TWO DIFFERENT GROUNDS. Twelve targets SWALLOW, so "all
items failed" is indistinguishable from "nothing to do" — that is (c)'s defect.
`generate_draft_invoices` joins on different grounds: it is annotated `-> None`,
so all three states are indistinguishable regardless of how its failures travel.
The other fifteen wrapped targets RAISE; the wrapper already records `failed`
for them and migrating them would be churn against no defect.
"""
from __future__ import annotations

import importlib

import pytest

from app import scheduler as sched
from app.services.job_outcome import (
    STATE_ABORTED,
    STATE_COMPLETED_WITH_ERRORS,
    STATE_NO_WORK,
    STATE_OK,
    JobOutcome,
)

#: (module, function) for every target in (c)'s population. Declared rather than
#: discovered, so the list is auditable — and `test_every_declared_target_resolves`
#: is the control that the declaration still matches the code.
POPULATION: list[tuple[str, str]] = [
    ("app.services.agent_service", "run_ar_aging_monitor"),
    ("app.services.agent_service", "run_collections_sequence"),
    ("app.services.agent_service", "run_ap_upcoming_payments"),
    ("app.services.audit_health_tasks", "raise_tasks_for_health_findings"),
    ("app.services.briefings.scheduler_integration", "sweep_briefings_to_generate"),
    ("app.services.draft_invoice_service", "generate_draft_invoices"),
    ("app.services.note.settling_sweep", "sweep_notes_to_settle"),
    ("app.services.price_increase_service", "activate_scheduled_versions"),
    ("app.services.proactive_agents", "run_reorder_suggestion_job"),
    ("app.services.proactive_agents", "run_uncleared_check_monitor"),
    ("app.services.proactive_agents", "enrich_payment_patterns"),
    ("app.services.proactive_agents", "run_discount_expiry_monitor"),
    ("app.services.workflow_scheduler", "check_time_based_workflows"),
]

#: ⚠️ LOWER THIS AS TARGETS MIGRATE. Never raise it. When it reaches 0, the
#: wrapper stops accepting anything else (commit 3) and this ceiling is deleted.
UNMIGRATED_CEILING = 0


def _resolve(mod: str, name: str):
    return getattr(importlib.import_module(mod), name)


def _returns_outcome(fn) -> bool:
    """Does this target reference `JobOutcome`? Read off the code object."""
    code = getattr(fn, "__code__", None)
    return bool(code and "JobOutcome" in code.co_names)


# ── the ceiling ──────────────────────────────────────────────────────────


def test_unmigrated_count_is_at_or_below_the_ceiling():
    """⚠️ THE RATCHET. Direction only — it does not require any migration."""
    unmigrated = sorted(
        name for mod, name in POPULATION if not _returns_outcome(_resolve(mod, name))
    )
    assert len(unmigrated) <= UNMIGRATED_CEILING, (
        f"{len(unmigrated)} targets do not return a JobOutcome, ceiling is "
        f"{UNMIGRATED_CEILING}: {unmigrated}"
    )


def test_the_ceiling_is_TIGHT():
    """⚠️ CONTROL. A ceiling above the real count has stopped ratcheting and
    refuses nothing — it would pass while every target regressed.

    So this asserts the ceiling equals reality, forcing whoever migrates a
    target to lower it in the same commit. Without this the ratchet is an
    inventory rather than a direction.
    """
    unmigrated = [
        name for mod, name in POPULATION if not _returns_outcome(_resolve(mod, name))
    ]
    assert len(unmigrated) == UNMIGRATED_CEILING, (
        f"ceiling is {UNMIGRATED_CEILING} but {len(unmigrated)} are unmigrated. "
        "Lower UNMIGRATED_CEILING in the commit that migrates a target."
    )


def test_every_declared_target_RESOLVES(): 
    """⚠️ CONTROL. A ceiling over a population that does not import is a ceiling
    over nothing — an ImportError here would otherwise surface as a collection
    error somewhere else, and a renamed target would silently leave the set."""
    for mod, name in POPULATION:
        fn = _resolve(mod, name)
        assert callable(fn), f"{mod}.{name} is not callable"
    assert len(POPULATION) == 13


def test_a_MIGRATED_target_is_named_not_merely_counted(monkeypatch):
    """⚠️ CONTROL. A regression must name the target, not produce a bare count.

    Simulates one target migrating, then confirms the detector sees it — so a
    green ratchet is evidence the detector discriminates rather than evidence it
    matches nothing.
    """
    # ⚠️ INVERTED AT (c) 2c, BECAUSE THE POPULATION RAN OUT.
    #
    # It first patched a hardcoded POPULATION[0] and silently stopped proving
    # anything the moment that element migrated. 2a repointed it at the first
    # CURRENTLY-unmigrated target -- correct then, and dead now that the
    # ceiling is 0 and there is nothing left to patch.
    #
    # The control's job never changed: prove the detector DISCRIMINATES rather
    # than matching everything. With every target migrated, the discriminating
    # move is the inverse -- un-migrate one and confirm the detector notices.
    # This version cannot rot the same way: it has no expiry, because it
    # manufactures its own subject instead of borrowing one from the population.
    mod, name = POPULATION[0]
    module = importlib.import_module(mod)

    def _unmigrated(*a, **k):
        return {"suggestions": 0}

    baseline = [n for m, n in POPULATION if not _returns_outcome(_resolve(m, n))]
    assert baseline == [], f"ceiling is 0 but these are unmigrated: {baseline}"

    monkeypatch.setattr(module, name, _unmigrated)
    assert _returns_outcome(_resolve(mod, name)) is False
    still = [n for m, n in POPULATION if not _returns_outcome(_resolve(m, n))]
    assert still == [name], f"the detector named {still}, expected exactly [{name}]"


# ── the type ─────────────────────────────────────────────────────────────


def test_the_state_is_DERIVED_so_ok_with_failures_is_unwritable():
    """⚠️ THE POINT OF THE TYPE. There is no state field to set."""
    assert JobOutcome.worked(succeeded=3).state == STATE_OK
    assert JobOutcome.worked(succeeded=0, failed=900).state == STATE_COMPLETED_WITH_ERRORS
    assert JobOutcome.worked(succeeded=5, failed=1).state == STATE_COMPLETED_WITH_ERRORS
    assert not hasattr(JobOutcome(), "state_setter")
    assert "state" not in {f for f in JobOutcome.__dataclass_fields__}


def test_nothing_to_do_is_distinct_from_everything_failed():
    """(c) in one assertion: these were both `None` before."""
    assert JobOutcome.nothing_to_do().state == STATE_NO_WORK
    assert JobOutcome.worked(succeeded=0, failed=7).state == STATE_COMPLETED_WITH_ERRORS


def test_aborted_CARRIES_COUNTS():
    """⚠️ A FINDING, NOT A DEFAULT (2026-09-14).

    The three whole-body swallowers hold live progress counters where they
    catch, and all reach `create_alert`, which COMMITS per alert. Work done
    before an abort is durable, so an implicit zero would understate committed
    rows.
    """
    o = JobOutcome.aborted("date vs datetime", succeeded=4, failed=1)
    assert o.state == STATE_ABORTED
    assert (o.succeeded, o.failed) == (4, 1)
    assert JobOutcome.aborted("x").succeeded == 0


def test_detail_survives_and_the_wrapper_never_needs_it():
    o = JobOutcome.worked(succeeded=2, invoices_checked=12, alerts_created=2)
    assert o.detail == {"invoices_checked": 12, "alerts_created": 2}


def test_the_constructors_refuse_nonsense():
    with pytest.raises(ValueError):
        JobOutcome.worked(succeeded=-1)
    with pytest.raises(ValueError):
        JobOutcome.aborted("")


# ── the wrapper's reading ────────────────────────────────────────────────


@pytest.fixture
def recorded(monkeypatch):
    calls: dict = {}
    monkeypatch.setattr(sched, "_log_job_run", lambda *a, **k: "run-1")
    monkeypatch.setattr(
        sched, "_complete_job_run",
        lambda run_id, status, duration, **kw: calls.update(status=status, **kw),
    )
    monkeypatch.setattr(sched, "SessionLocal", lambda: _Null())
    return calls


class _Null:
    def close(self): pass


def test_per_tenant_records_completed_with_errors(recorded, monkeypatch):
    monkeypatch.setattr(sched, "_get_active_tenant_ids", lambda: ["t1"])
    sched._run_per_tenant("T", lambda db, tid: JobOutcome.worked(succeeded=1, failed=2))
    assert recorded["status"] == STATE_COMPLETED_WITH_ERRORS
    # ⚠️ error_count still counts TENANTS. The tenant completed; its items did
    # not. Folding item failures in would give the column two meanings.
    assert recorded["error_count"] == 0
    assert recorded["success_count"] == 1


def test_per_tenant_no_work_is_a_clean_completion(recorded, monkeypatch):
    monkeypatch.setattr(sched, "_get_active_tenant_ids", lambda: ["t1"])
    sched._run_per_tenant("T", lambda db, tid: JobOutcome.nothing_to_do())
    assert recorded["status"] == "completed"


def test_per_tenant_aborted_is_a_failed_run(recorded, monkeypatch):
    monkeypatch.setattr(sched, "_get_active_tenant_ids", lambda: ["t1"])
    sched._run_per_tenant("T", lambda db, tid: JobOutcome.aborted("boom", succeeded=4))
    assert recorded["status"] == "failed"
    assert "boom" in recorded["error_message"]


def test_global_records_completed_with_errors_and_counts(recorded):
    sched._run_global("T", lambda db: JobOutcome.worked(succeeded=8, failed=3))
    assert recorded["status"] == STATE_COMPLETED_WITH_ERRORS
    assert (recorded["success_count"], recorded["error_count"]) == (8, 3)


def test_global_still_accepts_the_OLD_shapes(recorded):
    """Commit 1 accepts both. Refusing the old shape is commit 3."""
    sched._run_global("T", lambda db: {"generated": 3})
    assert recorded["status"] == "completed"
