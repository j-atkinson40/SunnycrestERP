"""Sampling harness for the BLOCKING latency gates: the endpoint's own time.

⚠️ WHAT THIS EXCLUDES, AND WHY EXCLUDING BEATS TOLERATING
──────────────────────────────────────────────────────────────────────────
A generation-2 collection on this application's heap costs HUNDREDS OF
MILLISECONDS and is not proportional to the garbage being freed — it is
proportional to the permanent heap it must walk. It lands on whichever request
is in flight when the allocation counters happen to cross. That request is not
slow; it was interrupted.

Tolerating it means every budget has to be large enough to absorb that pause,
which makes nearly all of them assert nothing. A p50 of 19ms under a budget of
500ms is a decision in form only. So the gates EXCLUDE the pause and measure
what the endpoint did.

The pause is real and is not being dropped on the floor: it is tracked in
production by `app/services/arc_telemetry._gc_snapshot`, on a surface built for
it, where frequency — the thing that actually matters for a single-process
service — is the question being asked.

⚠️ THE CODE PATH IS UNCHANGED. Nothing is disabled, frozen, or tuned. gc runs
exactly as it does in production, collections happen exactly when they would,
and the endpoint executes the same bytes. The only thing that happens is that
the interpreter says how long it spent collecting, and that interval is
subtracted from the sample it landed in. Rejected alternatives, and why:

  gc.disable() around the sample   The endpoint would run under a runtime
                                   state that never ships, and the allocation
                                   signal would vanish with the pause.
  gc.freeze() at session start     Same objection, and it is the candidate
                                   PRODUCTION fix — a gate that pre-applies it
                                   would report the fix as already landed.
  discard the affected sample      Silently shrinks the denominator, and the
                                   shrinkage is invisible in the number. Kept
                                   as a fallback if subtraction had not held.

⚠️ GEN-0 AND GEN-1 ARE NOT EXCLUDED. They are sub-millisecond, they scale with
what the endpoint itself allocates, and they are part of the cost of running
this code. Only generation 2 — the full walk of a heap the endpoint did not
create — comes out.

⚠️ AND THE ALLOCATION SIGNAL IS KEPT, DELIBERATELY. Excluding the pause must
not also exclude the evidence that an endpoint started allocating heavily —
that is the regression a latency gate exists to catch. Two different facts are
recorded, and the distinction is the point:

    gen-2 pause        THE RUNTIME COLLECTED.  Excluded from the latency.
    gen-0 collections  THIS ENDPOINT MADE THE RUNTIME COLLECT. Asserted.

gen-0 fires every 2,000 net container allocations (`gc.get_threshold()[0]`,
read at run time by `test_gc_latency_harness`), so its count over a sample loop
is a direct, high-count proxy for how much the endpoint allocates — and it is
what drives promotion into the generation whose collection is being excluded.

⚠️ THE GEN-2 COUNT WOULD NOT HAVE DONE THIS JOB, and that was measured rather
than assumed. In-sample gen-2 counts observed across every gate and every run
were 0 or 1; the number is dominated by where the PROCESS is in its allocation
history, not by the endpoint. gen-0 counts over the same runs were identical
across separate processes for almost every gate. One of those can carry a
ceiling and the other cannot.
"""
from __future__ import annotations

import gc
import statistics
import time
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass(frozen=True)
class Sample:
    """One measured call, with the collector's share separated out."""

    raw_ms: float
    gen2_pause_ms: float
    gen2_collections: int

    @property
    def endpoint_ms(self) -> float:
        return self.raw_ms - self.gen2_pause_ms


class Gen2Excluded:
    """Measures each call and attributes any gen-2 pause inside it.

    Usage::

        with Gen2Excluded() as s:
            for _ in range(N):
                with s.sample():
                    r = client.post(...)
                assert r.status_code == 200

    The `gc.callbacks` hook is registered only for the life of the context and
    removed on exit, so nothing is left behind for the rest of the session.
    """

    def __init__(self) -> None:
        self.samples: list[Sample] = []
        #: gen-0 collections over the WHOLE loop, not per sample — the
        #: allocation signal. Set on exit from gc.get_stats() deltas.
        self.gen0_collections: int = 0
        self.gen1_collections: int = 0
        #: gen-2 collections over the whole loop, including any that landed
        #: BETWEEN samples. Always >= the in-sample sum.
        self.gen2_collections_total: int = 0
        self._in_sample = False
        self._pause_ms = 0.0
        self._count = 0
        self._started_at = 0.0
        self._stats_before: tuple[int, ...] = ()

    # ── the hook ────────────────────────────────────────────────────────
    def _callback(self, phase: str, info: dict) -> None:
        # Generation check first: this runs on every gen-0 collection too,
        # which is constant. Nothing is allocated on the common path.
        if info.get("generation") != 2:
            return
        if phase == "start":
            self._started_at = time.perf_counter()
            return
        if not self._started_at:
            return
        elapsed_ms = (time.perf_counter() - self._started_at) * 1000.0
        self._started_at = 0.0
        if self._in_sample:
            self._pause_ms += elapsed_ms
            self._count += 1

    # ── lifecycle ───────────────────────────────────────────────────────
    def __enter__(self) -> "Gen2Excluded":
        self._stats_before = _generation_collections()
        gc.callbacks.append(self._callback)
        return self

    def __exit__(self, *exc) -> bool:
        gc.callbacks.remove(self._callback)
        after = _generation_collections()
        d = tuple(a - b for a, b in zip(after, self._stats_before))
        self.gen0_collections, self.gen1_collections = d[0], d[1]
        self.gen2_collections_total = d[2]
        return False

    @contextmanager
    def sample(self):
        self._in_sample = True
        self._pause_ms = 0.0
        self._count = 0
        t0 = time.perf_counter()
        try:
            yield
        finally:
            t1 = time.perf_counter()
            self._in_sample = False
            self.samples.append(
                Sample((t1 - t0) * 1000.0, self._pause_ms, self._count)
            )

    # ── readouts ────────────────────────────────────────────────────────
    @property
    def durations_ms(self) -> list[float]:
        """The endpoint's own time — what the budgets are asserted against."""
        return [s.endpoint_ms for s in self.samples]

    @property
    def raw_ms(self) -> list[float]:
        """Wall time including any collector pause. Reported, never asserted."""
        return [s.raw_ms for s in self.samples]

    @property
    def gen2_in_sample(self) -> int:
        return sum(s.gen2_collections for s in self.samples)

    @property
    def gen2_pause_ms(self) -> float:
        return sum(s.gen2_pause_ms for s in self.samples)

    def exclusion_note(self) -> str:
        """⚠️ ALWAYS SAYS WHAT WAS EXCLUDED, INCLUDING WHEN IT WAS NOTHING.

        A note that appears only when a collection happened would make the
        common case read as an ordinary unqualified measurement, which is the
        thing this whole harness is trying not to be.
        """
        if self.gen2_in_sample == 0:
            return (
                f"gc: 0 gen-2 collections in-sample "
                f"({self.gen0_collections} gen-0), nothing excluded"
            )
        return (
            f"gc: EXCLUDED {self.gen2_pause_ms:.1f}ms across "
            f"{self.gen2_in_sample} gen-2 collection(s) in-sample "
            f"(raw max {max(self.raw_ms):.1f}ms → "
            f"{max(self.durations_ms):.1f}ms; {self.gen0_collections} gen-0)"
        )


def _generation_collections() -> tuple[int, ...]:
    return tuple(g["collections"] for g in gc.get_stats())


def assert_allocation_ceiling(
    sampler: "Gen2Excluded", ceiling: int, label: str
) -> None:
    """⚠️ THE HALF OF THE GATE THAT EXCLUDING THE PAUSE COULD OTHERWISE DELETE.

    The latency assertion now measures the endpoint's own time, which is the
    point — but it means an endpoint that starts allocating hard enough to make
    the runtime collect would show a pause that the gate then removes. This
    keeps the cause in view even though the symptom is excluded.

    `ceiling` is measured-times-headroom, in the same manner as the latency
    budgets, and it is stated per gate rather than shared because allocation
    per request differs by two orders of magnitude across these endpoints.
    """
    observed = sampler.gen0_collections
    assert observed <= ceiling, (
        f"{label}: {observed} gen-0 collections over {len(sampler.samples)} "
        f"samples, ceiling {ceiling}. THIS GATE EXCLUDES GEN-2 PAUSES, so an "
        f"endpoint that started allocating heavily would NOT show up as "
        f"latency here — this is the signal that would otherwise be lost. "
        f"Either the endpoint's allocation volume changed and that is the "
        f"finding, or the ceiling needs re-deriving against a measurement."
    )
