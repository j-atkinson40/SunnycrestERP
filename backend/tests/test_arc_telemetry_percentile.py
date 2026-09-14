"""`arc_telemetry._percentile` — characterization, INCLUDING THE DEFECT.

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

These tests are GREEN against unmodified code. They go red when the surface is
repaired, which is the point — the repair becomes a visible diff against a
measured starting state rather than against nobody's idea of what this did.
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

    p50 comes from the same `quantiles` call as p99. If it were also wrong this
    would be a far larger item, so it is re-derived here rather than assumed:
    it must equal `statistics.median` exactly, and must lie inside the data.
    """
    for data in (
        [20.0] * (n - 1) + [450.0],
        [20.0] * n,
        _uniform(n),
        [12.0] * (n // 2) + [180.0] * (n - n // 2),
    ):
        got = at._percentile(data, 50)
        assert got == pytest.approx(statistics.median(data), abs=1e-9)
        assert min(data) - 1e-9 <= got <= max(data) + 1e-9


# ── the defect ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("n", [2, 3, 5, 10, 20, 30, 50, 75, 98])
def test_WRONGNESS_p99_exceeds_the_largest_sample_below_n99(n):
    """⚠️ WRONGNESS. The reported p99 is larger than anything that happened.

    Asserted across three distribution shapes so this is a property of the
    METHOD, not of one contrived input. (A flat top — every sample identical —
    is the one shape where the extrapolation coincides with the max; it is
    excluded here and covered by its own test below.)
    """
    for data in ([20.0] * (n - 1) + [450.0], _uniform(n), _uniform(n, seed=99)):
        p99 = at._percentile(data, 99)
        assert p99 > max(data), (
            f"n={n}: expected the extrapolation to exceed max({max(data):.1f}); "
            f"got {p99:.1f}"
        )


def test_WRONGNESS_the_inflation_is_worst_when_the_buffer_is_emptiest():
    """⚠️ WRONGNESS, and the operationally important half.

    The buffer refills from empty on every deploy, so low n is not an edge case
    — it is the state right after every release.
    """
    inflation = {}
    for n in (2, 10, 30, 50, 75):
        data = [20.0] * (n - 1) + [450.0]
        inflation[n] = at._percentile(data, 99) / max(data)

    # Monotonically less wrong as the buffer fills.
    assert inflation[2] > inflation[10] > inflation[30] > inflation[50] > inflation[75]
    # And the worst case is nearly double the true worst request.
    assert inflation[2] > 1.90


def test_the_threshold_is_EXACTLY_99_samples():
    """Measured, not chosen. The exclusive method needs n >= 99 for the 99th
    cut point to fall inside the data."""
    first_ok = next(
        n for n in range(2, 200) if at._percentile(_uniform(n), 99) <= max(_uniform(n))
    )
    assert first_ok == 99


def test_a_FLAT_TOP_is_the_one_shape_that_coincides():
    """Not a counter-example to the defect — a degenerate case. When every
    sample is identical there is nothing to extrapolate past."""
    data = [20.0] * 30
    assert at._percentile(data, 99) == 20.0


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
    assert row["p99_ms"] is not None


def test_the_operator_visible_case_after_a_deploy():
    """⚠️ WRONGNESS, as a person actually meets it. Five requests into a fresh
    process, slowest 450ms, and the dashboard says the p99 is ~853ms."""
    for v in (18.0, 19.0, 21.0, 20.0, 450.0):
        at.record("triage_next_item", v)
    row = next(
        e for e in at.snapshot()["endpoints"] if e["endpoint"] == "triage_next_item"
    )
    assert row["samples"] == 5
    assert row["p50_ms"] == pytest.approx(20.0)
    assert row["p99_ms"] > 800.0
    assert row["p99_ms"] > 450.0 * 1.85


def test_a_fresh_process_reports_None_not_zero():
    """The empty case is already honest — None, which the UI renders as a dash.
    The dishonest range is 2 <= n < 99, not n == 0."""
    for row in at.snapshot()["endpoints"]:
        assert row["samples"] == 0
        assert row["p50_ms"] is None and row["p99_ms"] is None


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
    """
    r = random.Random(4242)
    equal_to_max = 0
    trials = 40
    for _ in range(trials):
        n = r.randint(5, 60)
        data = [r.uniform(5.0, 500.0) for _ in range(n)]
        if len(set(data)) == 1:          # flat top: excluded, nothing to separate
            continue
        if at._percentile(data, 99) == max(data):
            equal_to_max += 1
    assert equal_to_max == 0, (
        f"{equal_to_max}/{trials} samples reported a p99 identically equal to the "
        "maximum. That is the clamp — a max-check wearing a p99's name."
    )
