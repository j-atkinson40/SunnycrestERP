"""Generation-2 GC instrumentation in `arc_telemetry`.

⚠️ WHY THIS IS MEASURED AND NOT FIXED. A triage latency gate was failing on one
sample ~20x its median. The slow call issued the same 86 statements and the same
9ms of SQL as every other call — the ~390ms was a gen-2 collection, timed at the
source. Disabling gc removed it entirely.

The heap it walks is the APPLICATION's (2,082,954 tracked objects after
`import app.main`), on Python's default thresholds, with nothing under app/
touching gc, in a single uvicorn process with no `--workers`. So a pause stalls
everything in flight, not one worker's share.

What nobody has is how often PRODUCTION collects — collections are
allocation-driven, not request-driven, so it cannot be inferred from traffic.
This records it. `gc.freeze()` is deliberately NOT shipped here: a fix landed
alongside its own measurement leaves no "before" reading to evaluate it against.
"""
from __future__ import annotations

import gc
import time

import pytest

from app.services import arc_telemetry as at


@pytest.fixture(autouse=True)
def _restore():
    saved = dict(at._GC)
    started = at._PROCESS_START_TS
    yield
    at._GC.update(saved)
    at._PROCESS_START_TS = started


# ── controls ─────────────────────────────────────────────────────────────


def test_the_callback_IS_REGISTERED_not_merely_defined():
    """⚠️ CONTROL, AND THE ONE THAT MATTERS MOST.

    Every other test here calls `_gc_callback` or reads `_GC` directly. All of
    them would pass against a module that defines the hook and never installs
    it — which is a perfectly plausible refactor, and would silently produce a
    surface reporting zero collections forever.
    """
    assert at._gc_callback in gc.callbacks


def test_a_REAL_collection_moves_the_counter_end_to_end():
    """⚠️ CONTROL. Not a synthetic call to the hook — an actual gen-2
    collection, so the wiring between Python's collector and this module is
    exercised rather than assumed."""
    before = at._GC["gen2_collections"]
    gc.collect(2)
    assert at._GC["gen2_collections"] == before + 1
    assert at._GC["gen2_pause_ms_max"] > 0


# ── the generation filter ────────────────────────────────────────────────


def test_gen0_and_gen1_are_IGNORED():
    """The hook fires on every collection. Only generation 2 may register —
    gen-0 runs constantly and would swamp both the counter and the cost."""
    before = dict(at._GC)
    for generation in (0, 1):
        at._gc_callback("start", {"generation": generation})
        at._gc_callback("stop", {"generation": generation})
    assert at._GC["gen2_collections"] == before["gen2_collections"]
    assert at._GC["gen2_pause_ms_total"] == before["gen2_pause_ms_total"]


def test_a_stop_without_a_start_is_ignored():
    """Defensive: `gc.callbacks` can be installed mid-collection, so a 'stop'
    may arrive with no matching 'start'. It must not record a pause measured
    from a zero timestamp."""
    at._GC["_started_at"] = 0.0
    before = at._GC["gen2_collections"]
    at._gc_callback("stop", {"generation": 2})
    assert at._GC["gen2_collections"] == before


# ── ⚠️ the rate, which is where this module's own defect was ─────────────


def _set(collections: int, uptime_s: float) -> dict:
    at._GC["gen2_collections"] = collections
    at._GC["gen2_pause_ms_max"] = 380.0 if collections else 0.0
    at._PROCESS_START_TS = time.time() - uptime_s
    return at.snapshot()["gc"]


def test_no_collections_reports_the_WINDOW_not_a_zero_rate():
    g = _set(0, 7200)
    assert g["gen2_per_hour"] is None
    assert "none observed" in g["gen2_rate_basis"]
    assert "120 min" in g["gen2_rate_basis"]


def test_ONE_collection_is_not_a_rate():
    """One event gives an upper bound on frequency, not an interval."""
    g = _set(1, 7200)
    assert g["gen2_per_hour"] is None
    assert "no interval" in g["gen2_rate_basis"]


def test_a_SHORT_WINDOW_is_not_a_rate_either():
    """⚠️ THE DEFECT THIS MODULE SHIPPED IN ITS FIRST DRAFT.

    Gating on the collection count alone, two collections in a zero-second
    window reported **4,888,149 collections per hour**. The denominator has to
    support the rate too — which is the same rule the p99 repair in this file
    established: do not extrapolate past the observation window.
    """
    g = _set(2, 240)  # two collections, four minutes of uptime
    assert g["gen2_per_hour"] is None
    assert "extrapolating past the window" in g["gen2_rate_basis"]


def test_a_rate_IS_reported_once_both_conditions_hold():
    g = _set(4, 7200)  # 4 collections over 2 hours
    assert g["gen2_per_hour"] == pytest.approx(2.0)
    assert "over 2.0 h" in g["gen2_rate_basis"]


def test_the_uptime_threshold_is_an_hour_and_the_count_is_two():
    """Pinned so that loosening either is a visible decision rather than a
    tweak. Both exist because a number was reported that its sample could not
    carry."""
    assert at._GC_MIN_COLLECTIONS_FOR_RATE == 2
    assert at._GC_MIN_UPTIME_S_FOR_RATE == 3600.0


# ── the surface ──────────────────────────────────────────────────────────


def test_the_snapshot_carries_gc_and_uptime_together():
    """The rate's denominator must travel with it. Uptime was already in this
    payload — the same field the 'Samples' column now uses to qualify the
    slow-end value."""
    snap = at.snapshot()
    assert "gc" in snap and "process_uptime_seconds" in snap
    assert set(snap["gc"]) == {
        "gen2_collections", "gen2_pause_ms_max", "gen2_pause_ms_total",
        "gen2_per_hour", "gen2_rate_basis",
    }


def test_heap_size_is_NOT_reported():
    """⚠️ DELIBERATE ABSENCE. Heap size determines the pause cost, so it is the
    obvious field to add — but `len(gc.get_objects())` materialises a list of
    every tracked object, two million here, and would itself cause the kind of
    pause being measured. An instrument that perturbs what it observes is worse
    than a missing field."""
    assert "tracked_objects" not in at.snapshot()["gc"]

    # ⚠️ AST, NOT A STRING SEARCH — AND THAT IS THE SECOND TIME TODAY.
    # The first version asserted "get_objects" was absent from the source and
    # failed on the COMMENT explaining why it is absent. A control that searches
    # source for a literal will find that literal in its own justification; the
    # FK guard hit the identical shape this morning searching for "app.models".
    # Asking the syntax tree for a CALL cannot be fooled by prose.
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(at._gc_snapshot))
    calls = {
        ast.unparse(n.func)
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
    }
    assert not any("get_objects" in c for c in calls), calls
