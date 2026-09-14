"""`arc_telemetry` tail statistic — the defect, and the repair that replaced it.

⚠️ PRODUCTION, OPERATOR-FACING, AND UNTESTED UNTIL NOW. `_percentile` feeds
`snapshot()`, which `GET /api/platform/admin/arc-telemetry` returns and
`bridgeable-admin/pages/ArcTelemetry.tsx` renders as a "p99" column. Before this
file, nothing tested it: two suites touch `arc_telemetry` incidentally
(test_peek_api, test_saved_view_preview) and neither exercises the percentile.

⚠️ THE DEFECT, PINNED DELIBERATELY. `statistics.quantiles(samples, n=100)` uses
the DEFAULT "exclusive" method, which assumes the sample under-covers the tails
and projects BEYOND them. Below n=99 the 99th cut point lands past the largest
observed value, so **the number labelled p99 is not a latency any request
experienced.**

The buffer is in-memory and capped at 1000, and it REFILLS FROM EMPTY ON EVERY
PROCESS RESTART. So the surface is least trustworthy immediately after a deploy,
which is when an operator is most likely to be looking at it.

⚠️ A FORBIDDEN REPAIR, NAMED SO THE NEXT READER DOES NOT REACH FOR IT.
Clamping the interpolated value to the observed max makes the number look right
and keeps it wrong: it would then be *always exactly the maximum*, labelled p99.
That is the max-check-wearing-a-p99's-name problem moved out of the test gates
and into production. Whatever the repair is, it is not that.

⚠️ REPAIRED 2026-09-14, and this file now pins the repair rather than the defect.
The WRONGNESS tests below are kept in SUPERSEDED form — each states what it used
to assert — because the repair is only reviewable against what it replaced.

THE REPAIR: `_percentile(samples, p)` is GONE. It could be asked for a 99th
percentile it had no data to compute, and was. Two narrower helpers replace it —
`_p50`, which is sound at every n, and `_tail`, which returns the value TOGETHER
WITH THE NAME OF THE STATISTIC IT USED ("p99" or "max"). The label travels with
the value; the value is never relabelled.
"""
from __future__ import annotations

import random
import statistics

import pytest

from app.services import arc_telemetry as at


@pytest.fixture(autouse=True)
def _clean_counters():
    at.reset_for_testing()
    yield
    at.reset_for_testing()


def _uniform(n, seed=20260914):
    r = random.Random(seed)
    return [r.uniform(10.0, 60.0) for _ in range(n)]


# ── the sound half, asserted FIRST as the control ────────────────────────


@pytest.mark.parametrize("n", [2, 3, 5, 10, 20, 30, 50, 99, 100, 250, 1000])
def test_p50_IS_SOUND_at_every_sample_count(n):
    """⚠️ THE CONTROL FOR EVERYTHING BELOW.

    p50 came from the same `quantiles` call as the old p99. If it were also
    wrong this would be a far larger item, so it is re-derived rather than
    assumed: it must equal `statistics.median` exactly and lie inside the data.
    It was verified sound BEFORE the repair and is re-verified after.
    """
    for data in (
        [20.0] * (n - 1) + [450.0],
        [20.0] * n,
        _uniform(n),
        [12.0] * (n // 2) + [180.0] * (n - n // 2),
    ):
        got = at._p50(data)
        assert got == pytest.approx(statistics.median(data), abs=1e-9)
        assert min(data) - 1e-9 <= got <= max(data) + 1e-9


# ── the defect ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("n", [2, 3, 5, 10, 20, 30, 50, 75, 98])
def test_below_the_threshold_the_tail_is_the_MAX_and_SAYS_SO(n):
    """SUPERSEDED the old `test_WRONGNESS_p99_exceeds_the_largest_sample_below_n99`,
    which asserted `p99 > max(data)` — a number no request experienced.

    Now: no p99 is computed at all below the threshold. The observed maximum is
    reported, and `tail_stat` says "max" so the reader is not told it is a p99.
    """
    for data in ([20.0] * (n - 1) + [450.0], _uniform(n), _uniform(n, seed=99)):
        value, stat = at._tail(data)
        assert stat == "max"
        assert value == max(data)
        assert value in data, "the reported number must be one that occurred"


@pytest.mark.parametrize("n", [99, 100, 150, 400, 1000])
def test_at_or_above_the_threshold_it_is_a_REAL_p99(n):
    """And "real" means NEAREST-RANK — an actual sample, not an interpolation
    between two of them.

    ⚠️ This is the codebase's own pattern, not a new invention:
    `intelligence.py` computes p95 as `rows[int(0.95 * (len - 1))]` over an
    ORDER BY. `quantiles()` would interpolate — on 119 samples at 20ms and one
    at 450ms it returns 359.7ms, inside the data range and measured by nothing.
    Within-range is not the same as true.
    """
    for data in ([20.0] * (n - 1) + [450.0], _uniform(n)):
        value, stat = at._tail(data)
        assert stat == "p99"
        assert value in data, "a p99 must be a latency some request recorded"
        assert min(data) <= value <= max(data)


def test_the_threshold_is_EXACTLY_99_samples():
    """Measured, not chosen. 99 is the smallest n at which the 99th cut point of
    `quantiles(n=100)` falls inside the sample — so it is the smallest n at
    which asking for a p99 is a question the data can answer."""
    assert at._P99_MIN_SAMPLES == 99
    assert at._tail(_uniform(98))[1] == "max"
    assert at._tail(_uniform(99))[1] == "p99"


def test_the_TRANSITION_is_visible_and_not_a_cliff_for_the_real_shape():
    """⚠️ THE PROPERTY THE RULING TURNED ON. A ~390ms spike every 30 requests is
    3.3% of traffic, so it sits above the 99th percentile and a correct p99
    reports it. The number does not collapse when the buffer crosses 99 — it
    reads 390 as a max below the threshold and 390 as a p99 above it.

    An instrument that makes a real recurring event visible is working.
    """
    def shape(n):
        return [390.0 if i % 30 == 18 else 19.0 for i in range(n)]

    for n in (30, 60, 98, 99, 150, 1000):
        value, stat = at._tail(shape(n))
        assert value == 390.0, f"n={n}: spike vanished, got {value}"
        assert stat == ("p99" if n >= 99 else "max")


def test_a_FLAT_TOP_reports_its_single_value():
    value, stat = at._tail([20.0] * 30)
    assert (value, stat) == (20.0, "max")


def test_the_general_percentile_helper_is_GONE_not_guarded():
    """⚠️ REMOVAL OVER VALIDATION. `_percentile(samples, p)` accepted any p and
    would answer 99 from 5 samples. It is deleted rather than guarded, so the
    wrong question is unaskable instead of merely refused."""
    assert not hasattr(at, "_percentile")


# ── the surface ──────────────────────────────────────────────────────────


def test_snapshot_ALREADY_CARRIES_the_sample_count():
    """⚠️ LOAD-BEARING FOR THE PENDING DECISION. Whatever the surface does about
    a p99 it cannot compute, the sample count is ALREADY in the payload and
    ALREADY rendered (ArcTelemetry.tsx, 'Samples' column). Nothing needs adding
    to the wire format to attach n to the number."""
    at.record("command_bar_query", 20.0)
    at.record("command_bar_query", 30.0)
    row = next(
        e for e in at.snapshot()["endpoints"] if e["endpoint"] == "command_bar_query"
    )
    assert row["samples"] == 2
    assert row["p50_ms"] is not None
    assert row["tail_ms"] is not None
    assert row["tail_stat"] == "max"   # 2 samples cannot support a p99


def test_the_operator_visible_case_after_a_deploy():
    """⚠️ WRONGNESS, as a person actually meets it. Five requests into a fresh
    process, slowest 450ms, and the dashboard says the p99 is ~853ms."""
    for v in (18.0, 19.0, 21.0, 20.0, 450.0):
        at.record("triage_next_item", v)
    row = next(
        e for e in at.snapshot()["endpoints"] if e["endpoint"] == "triage_next_item"
    )
    # SUPERSEDED. Was: `p99_ms > 800.0` and `> 450.0 * 1.85` -- i.e. the
    # dashboard reporting ~853ms when the slowest request took 450ms.
    assert row["samples"] == 5
    assert row["p50_ms"] == pytest.approx(20.0)
    assert row["tail_ms"] == 450.0, "the slowest request, exactly"
    assert row["tail_stat"] == "max", "and not called a p99"


def test_a_fresh_process_reports_None_not_zero():
    """The empty case is already honest — None, which the UI renders as a dash.
    The dishonest range is 2 <= n < 99, not n == 0."""
    for row in at.snapshot()["endpoints"]:
        assert row["samples"] == 0
        assert row["p50_ms"] is None
        assert row["tail_ms"] is None and row["tail_stat"] is None


def test_the_buffer_caps_at_1000_and_request_count_does_not():
    for i in range(1500):
        at.record("peek_fetch", 20.0)
    row = next(e for e in at.snapshot()["endpoints"] if e["endpoint"] == "peek_fetch")
    assert row["samples"] == 1000
    assert row["request_count"] == 1500


def test_TRACKED_ENDPOINTS_is_eight_not_five():
    """The module docstring said 'Five tracked endpoints' while the tuple held
    eight — three were appended by later phases (saved_view_preview, peek_fetch,
    quote_preview) without the prose being updated. Pinned so the next addition
    updates both."""
    assert len(at.TRACKED_ENDPOINTS) == 8


# ── a FORWARD guard, not a characterization ──────────────────────────────


def test_the_reported_p99_is_NEVER_IDENTICALLY_THE_MAXIMUM():
    """⚠️ THIS ONE GUARDS THE FUTURE, NOT THE PRESENT.

    Every other test in this file pins what the code does today. This one
    rejects a specific wrong repair: clamping the interpolated value to the
    observed max. That makes the number stop being an over-estimate and start
    being *always exactly the largest sample*, still labelled p99 — the
    max-check-wearing-a-p99's-name problem relocated from the test gates into
    production.

    It passes today (the value is strictly ABOVE the max) and it would pass
    under an honest repair such as nearest-rank (strictly BELOW, except on a
    flat top). It fails only under the clamp.

    The two break tests recorded in this commit both produced 12 failed / 16
    passed — the characterization alone could not tell an honest repair from
    the forbidden one. This is what tells them apart.

    ⚠️ RESCOPED BY THE REPAIR. It used to run at any n. Below the threshold the
    surface now reports the max ON PURPOSE and says so, so the guard would fire
    on correct behaviour. It therefore applies only to rows whose label claims
    "p99" — which is exactly where the lie would live.
    """
    r = random.Random(4242)
    equal_to_max = checked = 0
    for _ in range(40):
        n = r.randint(99, 400)
        data = [r.uniform(5.0, 500.0) for _ in range(n)]
        value, stat = at._tail(data)
        if stat != "p99" or len(set(data)) == 1:
            continue
        checked += 1
        if value == max(data):
            equal_to_max += 1
    assert checked >= 30, f"guard exercised only {checked} times -- it is not looking"
    assert equal_to_max == 0, (
        f"{equal_to_max}/{checked} rows labelled p99 reported a value identically "
        "equal to the maximum. That is the clamp -- a max-check wearing a p99's name."
    )
