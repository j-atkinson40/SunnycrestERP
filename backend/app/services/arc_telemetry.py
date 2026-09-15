"""Phase 7 — Arc endpoint telemetry.

Minimal in-memory rolling counters for the 5 non-Intelligence arc
endpoints. Intelligence-dominated endpoints (NL extract, briefing
generate) read from `intelligence_executions` directly — that data
is already persisted per-execution and aggregated.

Scope per approved Phase 7 plan:
  - No new table
  - Counters cleared on process restart (documented in UI)
  - Tracked endpoints: see TRACKED_ENDPOINTS. ⚠️ This line said "Five" and
    listed five while the tuple held EIGHT -- saved_view_preview, peek_fetch
    and quote_preview were appended by later phases without the prose being
    updated. Do not restate the count here; the tuple is the enumeration.
  - Per-endpoint rolling 1000-sample latency buffer for p50/p99

⚠️ THE p99 THIS MODULE REPORTS IS NOT A LATENCY ANY REQUEST EXPERIENCED, below
99 samples. `statistics.quantiles(..., n=100)` uses the default "exclusive"
method, which projects past the observed tails: measured, the reported p99
exceeds the largest actual sample by up to 93% at n=2, decaying to 0% at n=99.
The buffer refills from empty on every process restart, so the surface is least
trustworthy right after a deploy -- when an operator is most likely to read it.

p50 from the same call is SOUND at every n (verified against statistics.median
across five distribution shapes; see tests/test_arc_telemetry_percentile.py).

⚠️ RESOLVED 2026-09-14 — THE LABEL CHANGES, THE VALUE IS NEVER RELABELLED.

Below `_P99_MIN_SAMPLES` no p99 is computed at all. `_tail()` returns the
observed MAX together with the string "max", and the surface renders that name.
At or above the threshold it returns a real p99 and says "p99". Same column,
true at both ends, and the transition is visible to the reader rather than
silent.

Rejected: blanking the cell (a blank meaning "not enough data" and a blank
meaning "broken" are indistinguishable, and the column would blank after every
deploy — exactly when someone looks). Rejected: keeping the p99 label and
attaching the sample count (still a number that never happened, weighable only
by a reader who already knows this paragraph exists).

⚠️ AND NEVER clamp an interpolated value to the observed max. That yields a
number always exactly equal to the maximum while still called p99 — the same
lie with a smaller error bar. Guarded by
test_the_reported_p99_is_NEVER_IDENTICALLY_THE_MAXIMUM, which fires only on
rows whose label says "p99".

For long-term observability, post-arc roadmap covers real APM.
"""

from __future__ import annotations

import gc
import statistics
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque


_BUFFER_CAP = 1000


@dataclass
class _EndpointCounter:
    """Rolling latency + error buffer per endpoint."""
    latencies_ms: Deque[float] = field(
        default_factory=lambda: deque(maxlen=_BUFFER_CAP)
    )
    error_count: int = 0
    request_count: int = 0


# Thread-safe: a lock guards the per-endpoint dict + the deques.
_LOCK = threading.Lock()
_COUNTERS: dict[str, _EndpointCounter] = {}

# Process-startup timestamp — shown in the UI so viewers know how
# long the counters have been collecting.
_PROCESS_START_TS: float = time.time()


#: ⚠️ GENERATION-2 GC, MEASURED BECAUSE A 380ms PAUSE WAS FOUND BY ACCIDENT.
#:
#: A triage latency gate was failing on one sample ~20x its median. Measured
#: 2026-09-15: the slow call issued the SAME 86 statements and the SAME 9ms of
#: SQL as every other call — all ~390ms was a generation-2 collection, timed at
#: the source via `gc.callbacks`. Disabling gc removed it entirely.
#:
#: The heap it walks is the APPLICATION's: 2,082,954 tracked objects after
#: `import app.main`, on Python's default thresholds (2000, 10, 10), with no
#: file under app/ touching gc. A forced collection costs 432ms, and an
#: immediately repeated one costs 468ms — the cost is WALKING the permanent
#: heap, not reclaiming garbage.
#:
#: ⚠️ AND THE SERVICE RUNS ONE UVICORN PROCESS WITH NO --workers, so a pause
#: stalls everything in flight rather than one worker's share. That makes the
#: frequency an availability question, not a per-endpoint latency one.
#:
#: What is NOT known is how often production collects. Collections are
#: allocation-driven, not request-driven, so it cannot be inferred from traffic.
#: This records it. It deliberately does NOT fix it: shipping `gc.freeze()`
#: alongside its own measurement would mean the "before" reading never existed.
_GC = {
    "gen2_collections": 0,
    "gen2_pause_ms_total": 0.0,
    "gen2_pause_ms_max": 0.0,
    "_started_at": 0.0,
}

#: ⚠️ TWO CONDITIONS, AND THE SECOND ONE I GOT WRONG FIRST.
#:
#: A rate needs an INTERVAL, and one event gives no interval — it gives an upper
#: bound on frequency and nothing else. Hence the minimum count.
#:
#: But a count alone is not enough: the first implementation gated on count only
#: and reported **4,888,149 collections per hour** from two collections in a
#: zero-second window. The DENOMINATOR has to support the rate too.
#:
#: ⚠️ SO THE RULE IS THE ONE THIS MODULE WAS JUST REPAIRED FOR: DO NOT
#: EXTRAPOLATE PAST THE OBSERVATION WINDOW. A per-hour rate from four minutes of
#: uptime is the same defect as a p99 from thirty samples — a real statistic
#: computed over a span that cannot carry it, labelled as though it could.
#: `gen2_per_hour` therefore stays None until the process has been up an hour,
#: and below that the surface reports the count and the window instead.
_GC_MIN_COLLECTIONS_FOR_RATE = 2
_GC_MIN_UPTIME_S_FOR_RATE = 3600.0


def _gc_callback(phase: str, info: dict) -> None:
    """⚠️ THIS RUNS ON EVERY COLLECTION, INCLUDING GEN-0, WHICH IS CONSTANT.

    The generation check is therefore the first statement and the common path is
    one dict lookup and one comparison. Nothing is allocated here, and no lock is
    taken: a lock acquired inside a collection would add contention to the pause
    it is trying to measure, and the cost of a torn counter is a wrong statistic,
    not wrong behaviour.
    """
    if info.get("generation") != 2:
        return
    if phase == "start":
        _GC["_started_at"] = time.perf_counter()
        return
    started = _GC["_started_at"]
    if not started:
        return
    _GC["_started_at"] = 0.0
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    _GC["gen2_collections"] += 1
    _GC["gen2_pause_ms_total"] += elapsed_ms
    if elapsed_ms > _GC["gen2_pause_ms_max"]:
        _GC["gen2_pause_ms_max"] = elapsed_ms


gc.callbacks.append(_gc_callback)


def _gc_snapshot(uptime_seconds: float) -> dict:
    """Gen-2 collection stats, with the rate qualified by what supports it."""
    n = _GC["gen2_collections"]
    per_hour = None
    if (n >= _GC_MIN_COLLECTIONS_FOR_RATE
            and uptime_seconds >= _GC_MIN_UPTIME_S_FOR_RATE):
        per_hour = n / (uptime_seconds / 3600.0)

    mins = uptime_seconds / 60.0
    if n == 0:
        basis = f"none observed in {mins:.0f} min of uptime"
    elif n < _GC_MIN_COLLECTIONS_FOR_RATE:
        basis = f"{n} in {mins:.0f} min — one event gives no interval"
    elif uptime_seconds < _GC_MIN_UPTIME_S_FOR_RATE:
        basis = (f"{n} in {mins:.0f} min — too short to state an hourly rate "
                 "without extrapolating past the window")
    else:
        basis = f"{n} over {uptime_seconds / 3600.0:.1f} h of uptime"
    return {
        "gen2_collections": n,
        "gen2_pause_ms_max": _GC["gen2_pause_ms_max"] or None,
        "gen2_pause_ms_total": _GC["gen2_pause_ms_total"],
        "gen2_per_hour": per_hour,
        "gen2_rate_basis": basis,
        # ⚠️ HEAP SIZE IS DELIBERATELY ABSENT. It is what determines the pause
        # cost, so it is the obvious thing to report — but `len(gc.get_objects())`
        # materialises a list of every tracked object, two million of them here,
        # and would itself cause the kind of pause this is measuring. An
        # instrument that perturbs what it observes is worse than a missing field.
    }


TRACKED_ENDPOINTS = (
    "command_bar_query",
    "saved_view_execute",
    # Follow-up 3 — live preview in the saved view builder. Separate
    # from execute because the hot-path characteristics differ: preview
    # caps rows at 100 server-side and fires on every 300ms-debounced
    # config change.
    "saved_view_preview",
    "nl_extract",
    "triage_next_item",
    "triage_apply_action",
    # Follow-up 4 (arc finale) — peek endpoint backs hover + click
    # peeks across 4 surfaces (command bar, briefing pending decisions,
    # saved view rows, triage related entities). Own key because
    # per-request characteristics differ from the five: smaller
    # payloads, higher call frequency per user (hover spam), and a
    # session cache shield on the client side.
    "peek_fetch",
    # S-2 (§4.3) — quote-preview contextual surface. Fired on the
    # extraction-settle trigger while composing a quote; assembles the
    # order-resolver pricing + renders the real quote document to HTML.
    # Own key (own BLOCKING gate) because it does money-math + a Jinja
    # render per fire, unlike the lighter peek/query hot paths.
    "quote_preview",
)


def record(endpoint: str, latency_ms: float, errored: bool = False) -> None:
    """Append a single sample. Unknown endpoints are tracked too (so
    ad-hoc additions don't need registration), but only
    `TRACKED_ENDPOINTS` surface in the admin UI by default."""
    if endpoint == "":
        return
    with _LOCK:
        counter = _COUNTERS.get(endpoint)
        if counter is None:
            counter = _EndpointCounter()
            _COUNTERS[endpoint] = counter
        counter.latencies_ms.append(float(latency_ms))
        counter.request_count += 1
        if errored:
            counter.error_count += 1


def snapshot() -> dict:
    """Return a point-in-time view of all tracked endpoints.

    Shape:
      {
        "process_uptime_seconds": float,
        "gc": {                        # generation-2 collections in THIS process
          "gen2_collections": int,
          "gen2_pause_ms_max": float | None,
          "gen2_pause_ms_total": float,
          "gen2_per_hour": float | None,   # None until a rate is supportable
          "gen2_rate_basis": str,          # what the number above rests on
        },
        "endpoints": [
          {
            "endpoint": str,
            "request_count": int,
            "error_count": int,
            "error_rate": float,
            "samples": int,  # size of rolling buffer
            "p50_ms": float | None,       # sound at every n
            "tail_ms": float | None,      # the slow-end value
            "tail_stat": str | None,      # "p99" | "max" -- WHICH statistic
                                          # tail_ms actually is. Below
                                          # _P99_MIN_SAMPLES a p99 cannot be
                                          # computed, so the max is reported
                                          # and says so.
          },
          ...
        ]
      }
    """
    with _LOCK:
        # Copy the buffers + counts so we release the lock quickly.
        snapshot_data: list[dict] = []
        for endpoint in TRACKED_ENDPOINTS:
            counter = _COUNTERS.get(endpoint)
            if counter is None:
                snapshot_data.append({
                    "endpoint": endpoint,
                    "request_count": 0,
                    "error_count": 0,
                    "error_rate": 0.0,
                    "samples": 0,
                    "p50_ms": None,
                    "tail_ms": None,
                    "tail_stat": None,
                })
                continue
            latencies = list(counter.latencies_ms)
            tail_ms, tail_stat = _tail(latencies)
            snapshot_data.append({
                "endpoint": endpoint,
                "request_count": counter.request_count,
                "error_count": counter.error_count,
                "error_rate": (
                    counter.error_count / counter.request_count
                    if counter.request_count
                    else 0.0
                ),
                "samples": len(latencies),
                "p50_ms": _p50(latencies),
                "tail_ms": tail_ms,
                "tail_stat": tail_stat,
            })

    uptime = time.time() - _PROCESS_START_TS
    return {
        "process_uptime_seconds": uptime,
        "endpoints": snapshot_data,
        "gc": _gc_snapshot(uptime),
    }


#: ⚠️ MEASURED, NOT CHOSEN. `statistics.quantiles(xs, n=100)` uses the default
#: "exclusive" method, which assumes the sample under-covers the tails and
#: projects past them. 99 is the smallest n at which the 99th cut point falls
#: INSIDE the data; below it the result is an extrapolation and exceeds the
#: largest sample by up to 93%. Pinned by
#: tests/test_arc_telemetry_percentile.py::test_the_threshold_is_EXACTLY_99_samples.
_P99_MIN_SAMPLES = 99


def _p50(samples: list[float]) -> float | None:
    """The median. Sound at every sample count.

    ⚠️ THIS REPLACED A GENERAL `_percentile(samples, p)`. The general form could
    be asked for a 99th percentile it had no data to compute, and was — that is
    the defect this module carried. Narrowing the helper to the one statistic it
    can always answer makes the wrong question UNASKABLE rather than guarded.
    The slow end goes through `_tail`, which reports which statistic it used.
    """
    if not samples:
        return None
    return float(statistics.median(samples))


def _tail(samples: list[float]) -> tuple[float | None, str | None]:
    """The slow-end statistic AND THE NAME OF THE STATISTIC ACTUALLY USED.

    Returns `(value, "p99")` when there are enough samples for a p99 to mean
    something, `(value, "max")` when there are not, `(None, None)` when there is
    nothing at all.

    ⚠️ THE LABEL TRAVELS WITH THE VALUE, DELIBERATELY. The alternative — keep
    calling it p99 and quietly substitute the max below the threshold — is the
    defect in a different costume: a number that is always exactly the maximum,
    labelled as something else. Callers render whichever name comes back.
    """
    if not samples:
        return None, None
    if len(samples) >= _P99_MIN_SAMPLES:
        # ⚠️ NEAREST-RANK, NOT INTERPOLATION, AND IT IS THE CODEBASE'S OWN
        # PATTERN. `intelligence.py` computes its p95 as
        # `rows[int(0.95 * (len(rows) - 1))]` over an ORDER BY -- always a value
        # some request actually recorded. `quantiles()` interpolates BETWEEN
        # order statistics: on 119 samples at 20ms and one at 450ms it returns
        # 359.7ms, which is inside the data range and which nothing measured.
        # Within-range is not the same as true.
        #
        # This module diverged from a working pattern rather than lacking one.
        ordered = sorted(samples)
        return float(ordered[int(0.99 * (len(ordered) - 1))]), "p99"
    return float(max(samples)), "max"


def reset_for_testing() -> None:
    """Test hook only. Do not call in production."""
    with _LOCK:
        _COUNTERS.clear()
