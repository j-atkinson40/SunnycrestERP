"""Phase 7 — Arc endpoint telemetry.

Minimal in-memory rolling counters for the 5 non-Intelligence arc
endpoints. Intelligence-dominated endpoints (NL extract, briefing
generate) read from `intelligence_executions` directly — that data
is already persisted per-execution and aggregated.

Scope per approved Phase 7 plan:
  - No new table
  - Counters cleared on process restart (documented in UI)
  - Five tracked endpoints: command_bar_query, saved_view_execute,
    nl_extract, triage_next_item, triage_apply_action
  - Per-endpoint rolling 1000-sample latency buffer for p50/p99

For long-term observability, post-arc roadmap covers real APM.
"""

from __future__ import annotations

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
        "endpoints": [
          {
            "endpoint": str,
            "request_count": int,
            "error_count": int,
            "error_rate": float,
            "samples": int,  # size of rolling buffer
            "p50_ms": float | None,
            "p99_ms": float | None,
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
                    "p99_ms": None,
                })
                continue
            latencies = list(counter.latencies_ms)
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
                "p50_ms": _percentile(latencies, 50),
                "p99_ms": _percentile(latencies, 99),
            })

    return {
        "process_uptime_seconds": time.time() - _PROCESS_START_TS,
        "endpoints": snapshot_data,
    }


def _percentile(samples: list[float], p: int) -> float | None:
    if not samples:
        return None
    if len(samples) == 1:
        return float(samples[0])
    try:
        # statistics.quantiles with n=100 gives us percentile boundaries.
        q = statistics.quantiles(samples, n=100)
        idx = max(0, min(len(q) - 1, p - 1))
        return float(q[idx])
    except statistics.StatisticsError:
        return float(statistics.median(samples))


def reset_for_testing() -> None:
    """Test hook only. Do not call in production."""
    with _LOCK:
        _COUNTERS.clear()
