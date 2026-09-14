"""The wrapper-return population: derived, bounded, and permanently tolerated.

⚠️ THE POPULATION FOR THE REMOVAL IS NOT (c)'s POPULATION, AND CONFLATING THEM
WOULD HAVE CAUSED A LIVE OUTAGE.

`test_job_outcome_ratchet.py` declares 13 targets and its ceiling reached 0 at
(c) 2c. That list was correct for what (c) SET OUT TO DO: it is the set of
targets that SWALLOW, where a total failure was indistinguishable from an empty
day. Every one of them now returns a `JobOutcome`.

Commit 3 is a different question. It makes the wrappers REFUSE anything that is
not a `JobOutcome`, and the population for a refusal is EVERY CALLER OF THE
WRAPPER -- not the subset (c) chose to fix. Measured 2026-09-14 by walking
`scheduler.py`'s AST for `_run_per_tenant` / `_run_global` call sites:

    27 wrapper call sites
    13 returning JobOutcome
    14 NOT  -- twelve imported targets plus two defined in scheduler.py itself

The fourteen were excluded from (c) on a correct criterion: they RAISE on
failure rather than swallowing, so they never had the silent-success defect.
That says nothing about what they RETURN, and the refusal is about what they
return.

Enforcing the refusal would raise TypeError in fourteen scheduled jobs,
nightly, against live tenants -- the exact conversion of a latent defect into a
live outage that CLAUDE.md's sequencing rule exists to prevent.

⚠️ RULED 2026-09-14: THE REFUSAL IS NOT DEFERRED, IT IS ABANDONED, AND THE
TOLERANCE IS DESIGN.

Migrating fourteen jobs that have no defect, to satisfy a refusal whose purpose
was to fix a defect they do not have, is churn with a nightly TypeError as its
failure mode -- and eleven of them are outside item (c) entirely. A NARROWER
refusal is worse than none: a rule with a carve-out has to name what is carved
out, and that name is a declared population, which is the thing that just
failed.

So this file is not a countdown. The ceiling is a STANDING BOUND: it may only
shrink, it is not required to reach 0, and nothing is waiting on it. What it
buys is that the population cannot GROW silently -- every new wrapper call site
either returns a `JobOutcome` or moves a number.

⚠️ THIS RATCHET DERIVES ITS POPULATION RATHER THAN DECLARING IT. The declared
list is what went wrong: `POPULATION` was right about (c) and was then read as
though it described the wrappers' callers. A derived population cannot drift
from the code that way -- adding a wrapper call site with a non-migrated target
moves this count on the next run, with no list for anyone to forget to update.
"""
from __future__ import annotations

import ast
import importlib
import pathlib
import re

import pytest

SCHEDULER = pathlib.Path(__file__).resolve().parents[1] / "app" / "scheduler.py"
WRAPPERS = ("_run_per_tenant", "_run_global")

#: ⚠️ A STANDING BOUND, NOT A COUNTDOWN. May only shrink; is not required to
#: reach 0. Nothing is waiting on this number, and reaching 0 does NOT
#: authorise removing the wrappers' tolerance -- see the ruling above.
REMOVAL_CEILING = 14

#: Independent cross-check: the scheduler-wrapper ratchet measured 27 jobs
#: routing through a wrapper on 2026-09-11 by a completely different method
#: (runtime registration + co_names). Two methods, one number.
EXPECTED_CALL_SITES = 27


def _wrapper_call_sites() -> list[tuple[str, str]]:
    """(job_label, target_expression) for every wrapper call site."""
    tree = ast.parse(SCHEDULER.read_text())
    out = []
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id in WRAPPERS and len(n.args) >= 2):
            label = ast.unparse(n.args[0]).strip("'\"")
            out.append((label, ast.unparse(n.args[1])))
    return out


def _lazy_imports() -> dict[str, str]:
    tree = ast.parse(SCHEDULER.read_text())
    return {
        (a.asname or a.name): n.module
        for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module
        for a in n.names
    }


def _resolve(target_expr: str):
    """Resolve a target expression to a function object, or None if local."""
    name = target_expr
    if name.startswith("lambda"):
        m = re.search(r"(\w+)\(\)", name)
        if not m:
            return None, name
        name = m.group(1)
    mod = _lazy_imports().get(name)
    if mod is None:
        return None, name          # defined in scheduler.py itself
    return getattr(importlib.import_module(mod), name), name


def _returns_outcome(fn) -> bool:
    code = getattr(fn, "__code__", None)
    return bool(code and "JobOutcome" in code.co_names)


def _unmigrated() -> list[str]:
    """Wrapper targets that do NOT return a JobOutcome."""
    out = []
    for label, expr in _wrapper_call_sites():
        fn, name = _resolve(expr)
        if fn is None:
            # scheduler-local target -- read it off scheduler.py's own AST
            tree = ast.parse(SCHEDULER.read_text())
            local = next((x for x in ast.walk(tree)
                          if isinstance(x, ast.FunctionDef) and x.name == name), None)
            ok = local is not None and "JobOutcome" in ast.dump(local)
        else:
            ok = _returns_outcome(fn)
        if not ok:
            out.append(f"{label}:{name}")
    return sorted(out)


# ── the ratchet ──────────────────────────────────────────────────────────


def test_unmigrated_wrapper_targets_at_or_below_the_ceiling():
    un = _unmigrated()
    assert len(un) <= REMOVAL_CEILING, (
        f"{len(un)} wrapper targets do not return a JobOutcome, ceiling is "
        f"{REMOVAL_CEILING}: {un}"
    )


def test_the_ceiling_is_TIGHT():
    """⚠️ CONTROL. A ceiling above the real count has stopped ratcheting and
    would pass while every target regressed. This is the control that caught
    break A in (c) commit 1, where the ratchet's own assertion passed."""
    un = _unmigrated()
    assert len(un) == REMOVAL_CEILING, (
        f"ceiling is {REMOVAL_CEILING} but {len(un)} are unmigrated. Lower "
        f"REMOVAL_CEILING in the commit that migrates one: {un}"
    )


def test_the_enumeration_is_NOT_EMPTY_and_matches_an_INDEPENDENT_COUNT():
    """⚠️ CONTROL. A ceiling ratchet passes trivially if it counts nothing.

    The cross-check is the point: `test_scheduler_wrapper_ratchet` arrived at 27
    from RUNTIME registration plus `co_names`; this file arrives at 27 from
    scheduler.py's AST. Two methods that fail differently agreeing on one
    number is evidence; either alone is a measurement.
    """
    sites = _wrapper_call_sites()
    assert sites, "the enumeration found NO wrapper call sites -- it is broken"
    assert len(sites) == EXPECTED_CALL_SITES, (
        f"wrapper call sites moved: {len(sites)} vs {EXPECTED_CALL_SITES}. "
        "If a wrapper call site was added or removed, update "
        "EXPECTED_CALL_SITES here AND check test_scheduler_wrapper_ratchet."
    )


def test_the_detector_DISCRIMINATES(monkeypatch):
    """⚠️ CONTROL. Un-migrate a migrated target; the detector must name it."""
    from app.services import agent_service

    baseline = _unmigrated()
    assert "AR_AGING_MONITOR:run_ar_aging_monitor" not in baseline

    def _old_shape(*a, **k):
        return {"error": "boom"}

    monkeypatch.setattr(agent_service, "run_ar_aging_monitor", _old_shape)
    after = _unmigrated()
    assert "AR_AGING_MONITOR:run_ar_aging_monitor" in after
    assert len(after) == len(baseline) + 1


def test_the_two_POPULATIONS_are_different_and_that_is_the_finding():
    """⚠️ THE ENTRY POINT FOR ANYONE WHO READS `UNMIGRATED_CEILING == 0` AND
    CONCLUDES THE WRAPPERS CAN NOW REFUSE NON-JobOutcome RETURNS.

    (c)'s population is targets that SWALLOW. This file's population is targets
    the WRAPPER CALLS. The first is a strict subset of the second, and the
    removal answers to the second.
    """
    from tests.test_job_outcome_ratchet import POPULATION, UNMIGRATED_CEILING

    assert UNMIGRATED_CEILING == 0, "(c)'s own population should be fully migrated"

    # ⚠️ RESOLVE THROUGH THE LAMBDA. A first draft of this test compared
    # POPULATION's NAMES against the call sites' EXPRESSIONS and reported that
    # `check_time_based_workflows` was not wrapper-called. It is -- via
    # `lambda _db: check_time_based_workflows()` -- so the expression is a
    # lambda and the name never matched. A false absence from comparing two
    # different kinds of string, inside the file whose subject is a population
    # that was counted wrong.
    wrapper_names = {_resolve(expr)[1] for _, expr in _wrapper_call_sites()}
    swallowers = {name for _, name in POPULATION}

    missing = swallowers - wrapper_names
    assert missing == set(), (
        f"(c) targets not reachable from any wrapper call site: {missing}"
    )
    # Strict superset: every swallower is wrapper-called, and the wrapper calls
    # fourteen more besides. THAT is why UNMIGRATED_CEILING == 0 does not mean
    # the removal is safe.
    assert len(wrapper_names) > len(swallowers), (
        f"{len(wrapper_names)} wrapper targets vs {len(swallowers)} swallowers"
    )
    # ⚠️ NOT asserted as > 0. This file outlives the gap: if every wrapper
    # target ever returns a JobOutcome the tolerance STILL stays, because
    # removing it buys nothing and costs fourteen callers. The ratchet keeps
    # holding the population line for whatever is added next.
