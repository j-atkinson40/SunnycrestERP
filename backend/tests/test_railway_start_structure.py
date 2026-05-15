"""Sub-arc D-1 — structural assertions on backend/railway-start.sh.

Pure-text inspection (no subprocess, no DB). Verifies the deploy script
preserves D-1's invariants:

1. `alembic upgrade head` precedes seed execution.
2. The canonical-seeds runner is invoked AFTER the existing fail-loud
   seed invocations and BEFORE `exec uvicorn`.
3. The canonical-seeds runner invocation is NOT gated by `set -e`
   (failures must be non-fatal — locked decision 2).
4. The existing fail-loud seed invocations (R-1.6.3) survive D-1
   unchanged.
"""

from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RAILWAY_START = REPO_ROOT / "backend" / "railway-start.sh"
SEED_RUNNER = REPO_ROOT / "backend" / "scripts" / "run_canonical_seeds.sh"


@pytest.fixture(scope="module")
def railway_start_text() -> str:
    assert RAILWAY_START.exists(), f"missing {RAILWAY_START}"
    return RAILWAY_START.read_text()


@pytest.fixture(scope="module")
def seed_runner_text() -> str:
    assert SEED_RUNNER.exists(), f"missing {SEED_RUNNER}"
    return SEED_RUNNER.read_text()


def _line_of(text: str, needle: str) -> int:
    for i, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return i
    raise AssertionError(f"needle not found in railway-start.sh: {needle!r}")


def test_alembic_upgrade_precedes_canonical_seeds(railway_start_text: str) -> None:
    """alembic upgrade head must run before the D-1 canonical runner."""
    alembic_line = _line_of(railway_start_text, "alembic upgrade head")
    runner_line = _line_of(railway_start_text, "run_canonical_seeds.sh")
    assert alembic_line < runner_line, (
        f"alembic upgrade head (line {alembic_line}) must precede "
        f"run_canonical_seeds.sh (line {runner_line})"
    )


def test_canonical_seeds_precedes_uvicorn(railway_start_text: str) -> None:
    """Canonical seeds must complete before the application starts."""
    runner_line = _line_of(railway_start_text, "run_canonical_seeds.sh")
    uvicorn_line = _line_of(railway_start_text, "exec uvicorn")
    assert runner_line < uvicorn_line, (
        f"run_canonical_seeds.sh (line {runner_line}) must precede "
        f"exec uvicorn (line {uvicorn_line})"
    )


def test_fail_loud_seeds_precede_canonical_runner(railway_start_text: str) -> None:
    """R-1.6.3 fail-loud seeds run before the non-fatal canonical runner.

    The canonical runner skips these via SKIP_SEEDS to avoid double-run;
    keeping them upstream preserves their fail-the-deploy contract.
    """
    seed_staging_line = _line_of(railway_start_text, "python -m scripts.seed_staging")
    runner_line = _line_of(railway_start_text, "run_canonical_seeds.sh")
    assert seed_staging_line < runner_line


def test_runner_invocation_not_set_e_gated(railway_start_text: str) -> None:
    """The runner is invoked via bare `bash ...` — exit code is ignored.

    The runner itself exits 0 always (locked decision 2). railway-start.sh
    must NOT wrap the invocation in `if ! bash ...; then exit 1; fi` —
    that would re-introduce a fail-fast path for seed failures.
    """
    text = railway_start_text
    # Find the line invoking the runner
    runner_lines = [
        line for line in text.splitlines()
        if "run_canonical_seeds.sh" in line and not line.lstrip().startswith("#")
    ]
    assert runner_lines, "no executable invocation of run_canonical_seeds.sh"
    for line in runner_lines:
        # Should NOT be inside an `if !` guard
        assert "if !" not in line, (
            f"canonical runner invocation must not be fail-fast-gated: {line!r}"
        )


def test_seed_runner_exits_zero_always(seed_runner_text: str) -> None:
    """The runner ends with `exit 0` (non-fatal contract — decision 2)."""
    # Strip comments + blank lines, find the final non-comment statement.
    statements = [
        line.strip()
        for line in seed_runner_text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert statements, "runner is empty"
    assert statements[-1] == "exit 0", (
        f"runner must end with `exit 0`; got {statements[-1]!r}"
    )


def test_seed_runner_does_not_set_minus_e(seed_runner_text: str) -> None:
    """`set -e` would abort the loop on first seed failure — forbidden."""
    for line in seed_runner_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert stripped != "set -e", "runner must NOT `set -e` (locked decision 2)"


def test_skip_seeds_list_present(seed_runner_text: str) -> None:
    """SKIP_SEEDS must include the four upstream fail-loud seeds.

    If any entry is removed from SKIP_SEEDS without also removing the
    fail-loud invocation in railway-start.sh, that seed runs twice on
    every deploy. The list and the upstream invocations must stay in
    lockstep.
    """
    required = [
        "seed_staging",
        "seed_fh_demo",
        "seed_dispatch_demo",
        "seed_edge_panel_inheritance",
    ]
    for name in required:
        assert f'"{name}"' in seed_runner_text, (
            f"SKIP_SEEDS missing {name!r}"
        )
