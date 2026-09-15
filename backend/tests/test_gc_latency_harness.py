"""Controls for the gate sampling harness in tests/_gc_latency.py.

⚠️ THE HARNESS IS THE THING THAT DECIDES WHAT EVERY LATENCY GATE MEASURES, so
it gets the scrutiny a gate gets. These are controls, not coverage: each one
names a way the harness could be silently wrong and forces it to speak.

The four that matter, and what each would let through if it were absent:

  SEES        A sampler that never attributes anything reports every endpoint
              as clean. A zero from a dead instrument and a zero from a quiet
              process are the same zero.
  SUBTRACTS   Attribution without subtraction is a diagnostic, not an
              exclusion, and the budgets would still be asserted against a
              number containing the pause.
  SCOPES      A collection between samples must not be charged to a sample.
              Charging it would understate an endpoint by the one number the
              gate is most sensitive to.
  CHANGES     NOTHING. gc must still be enabled, on the same thresholds, with
              nothing frozen, and the hook must be gone afterwards. The moment
              the harness alters the runtime, the gate measures a process that
              does not ship.
"""
from __future__ import annotations

import ast
import gc
import pathlib
import time

from tests._gc_latency import Gen2Excluded


def _burn(ms: float) -> None:
    """Spin for approximately `ms`, so a sample has a floor above zero."""
    end = time.perf_counter() + ms / 1000.0
    while time.perf_counter() < end:
        pass


class _Cyclic:
    """Refcounting cannot free a pair of these; only the collector can."""
    def __init__(self):
        self.peer = None


def _make_cyclic_garbage(n: int) -> None:
    for _ in range(n):
        a, b = _Cyclic(), _Cyclic()
        a.peer, b.peer = b, a


# ── SEES ────────────────────────────────────────────────────────────────

def test_a_REAL_collection_inside_a_sample_IS_ATTRIBUTED_to_it():
    """The instrument's positive control. Everything else reads absences."""
    with Gen2Excluded() as s:
        with s.sample():
            _burn(2.0)
            gc.collect(2)          # a real full collection, not a simulation
        with s.sample():
            _burn(2.0)

    assert s.samples[0].gen2_collections == 1, (
        "the harness did not see a gen-2 collection that definitely happened — "
        "every zero it has ever reported is worthless until this passes"
    )
    assert s.samples[0].gen2_pause_ms > 0.0
    assert s.samples[1].gen2_collections == 0, (
        "a collection in sample 0 was charged to sample 1 as well"
    )


# ── SUBTRACTS ───────────────────────────────────────────────────────────

def test_the_pause_is_SUBTRACTED_not_merely_counted():
    """⚠️ THE BREAK TEST FOR THE WHOLE ITEM.

    Delete the subtraction in `Sample.endpoint_ms` (return raw_ms) and this
    goes red on its own — not merely something, this. A harness that counts
    the pause and still asserts against wall time has changed nothing.
    """
    with Gen2Excluded() as s:
        with s.sample():
            _burn(1.0)
            gc.collect(2)

    sample = s.samples[0]
    assert sample.gen2_pause_ms > 0.0, "no pause to subtract — test is vacuous"
    assert sample.endpoint_ms < sample.raw_ms, (
        "endpoint_ms == raw_ms with a pause recorded: the harness is reporting "
        "the exclusion without applying it"
    )
    assert abs(sample.endpoint_ms - (sample.raw_ms - sample.gen2_pause_ms)) < 1e-9


def test_the_corrected_sample_LANDS_IN_THE_DISTRIBUTION_of_the_clean_ones():
    """The claim subtraction makes, tested as a prediction rather than asserted.

    If a gen-2 pause is genuinely additive — the endpoint's own work plus an
    interruption — then removing it must put the interrupted sample back among
    the samples that were not interrupted. If the corrected value were still an
    outlier, the pause would not be the whole story and subtraction would be
    the wrong correction.
    """
    with Gen2Excluded() as s:
        for i in range(9):
            with s.sample():
                _burn(3.0)
                if i == 4:
                    gc.collect(2)

    hit = s.samples[4]
    assert hit.gen2_collections >= 1, "the collection did not land where placed"
    clean = [x.endpoint_ms for i, x in enumerate(s.samples) if i != 4]
    # Generous band: this asserts the correction WORKS, not that the machine is
    # quiet. Uncorrected, the spike is many times the band on this heap.
    assert hit.endpoint_ms <= max(clean) * 3, (
        f"corrected sample {hit.endpoint_ms:.1f}ms is still an outlier against "
        f"clean max {max(clean):.1f}ms — the pause is not the whole difference"
    )


# ── SCOPES ──────────────────────────────────────────────────────────────

def test_a_collection_BETWEEN_samples_is_counted_but_NOT_SUBTRACTED():
    with Gen2Excluded() as s:
        with s.sample():
            _burn(1.0)
        gc.collect(2)                      # between samples — nobody's cost
        with s.sample():
            _burn(1.0)

    assert s.gen2_in_sample == 0, "a between-samples collection was charged to a sample"
    assert s.gen2_collections_total >= 1, (
        "a collection that happened inside the sampler's lifetime went "
        "unrecorded — the loop-level count is not watching"
    )


# ── CHANGES NOTHING ─────────────────────────────────────────────────────

def test_the_runtime_is_UNCHANGED_during_and_after_sampling():
    thresholds_before = gc.get_threshold()
    enabled_before = gc.isenabled()
    frozen_before = gc.get_freeze_count()

    with Gen2Excluded() as s:
        with s.sample():
            _burn(0.5)
        assert gc.isenabled() is enabled_before, (
            "gc was disabled during sampling — the gate would measure a runtime "
            "that never ships"
        )
        assert gc.get_threshold() == thresholds_before
        assert gc.get_freeze_count() == frozen_before, (
            "something was frozen: that is the candidate PRODUCTION fix, and a "
            "gate applying it would report the fix as already landed"
        )

    assert gc.get_threshold() == thresholds_before
    assert gc.isenabled() is enabled_before
    assert gc.get_freeze_count() == frozen_before


def test_the_hook_is_REMOVED_on_exit():
    before = len(gc.callbacks)
    with Gen2Excluded() as s:
        assert len(gc.callbacks) == before + 1, "the hook was never registered"
        with s.sample():
            _burn(0.2)
    assert len(gc.callbacks) == before, (
        "the hook outlived its context — every later test in the session would "
        "be feeding a sampler nobody reads"
    )


# ── the allocation signal, which must NOT be excluded ───────────────────

def test_gen0_collections_RESPOND_TO_ALLOCATION():
    """The regression signal's own positive control.

    gen-2 pause is excluded. gen-0 count is what remains to say "this endpoint
    started allocating heavily". A counter that does not move with allocation
    cannot carry that job.
    """
    with Gen2Excluded() as quiet:
        for _ in range(5):
            with quiet.sample():
                _burn(0.2)

    with Gen2Excluded() as busy:
        for _ in range(5):
            with busy.sample():
                _make_cyclic_garbage(20_000)

    assert busy.gen0_collections > quiet.gen0_collections * 3 + 5, (
        f"allocating hard moved gen-0 collections only "
        f"{quiet.gen0_collections} → {busy.gen0_collections}: this counter "
        f"cannot detect an allocation regression"
    )


def test_the_gen0_threshold_the_docstring_QUOTES_is_the_one_in_force():
    """_gc_latency's docstring justifies the allocation ceiling by naming
    2,000 as the gen-0 threshold. A number quoted in prose is a claim; this
    reads it from the interpreter so the claim cannot rot silently."""
    assert gc.get_threshold()[0] == 2000, (
        f"gen-0 threshold is {gc.get_threshold()[0]}, not the 2,000 the "
        f"harness docstring reasons from — the ceilings were derived against "
        f"a different interpreter setting"
    )


def test_NOTHING_UNDER_APP_TOUCHES_THE_COLLECTOR_except_the_observer():
    """⚠️ THE EXCLUSION'S LOAD-BEARING PRECONDITION.

    Subtracting gen-2 pauses is only honest while no application code CAUSES a
    collection. If an endpoint called `gc.collect()` itself, that cost would be
    the endpoint's own and the gates would be quietly deleting it.

    Enumerated from the AST, not from a grep for a literal — a source search for
    "gc.collect" finds this docstring. `arc_telemetry` is allowed exactly one
    call: `gc.callbacks.append`, which observes and does not collect.
    """
    app = pathlib.Path(__file__).resolve().parent.parent / "app"
    mutating = {"collect", "disable", "enable", "freeze", "unfreeze",
                "set_threshold", "set_debug"}
    offenders = []
    for path in app.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if not isinstance(fn, ast.Attribute):
                continue
            if isinstance(fn.value, ast.Name) and fn.value.id == "gc":
                if fn.attr in mutating:
                    offenders.append(f"{path.relative_to(app.parent)}:{node.lineno} "
                                     f"gc.{fn.attr}()")
    assert offenders == [], (
        "application code drives the collector, so a gen-2 pause is no longer "
        "purely an interruption and the gates must stop excluding it: "
        + "; ".join(offenders)
    )
