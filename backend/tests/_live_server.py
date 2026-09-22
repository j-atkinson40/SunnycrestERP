"""Refuse to run HTTP integration suites blind.

⚠️ WHY THIS EXISTS. On 2026-09-22 nothing was listening on `localhost:8000` and
the two HTTP integration suites produced **117 errors**, one per test, every one
an `httpcore.ConnectError` raised during setup. An erroring test asserts
nothing, so 117 tests covering the API — including every test of the
personalization availability surface — were UNCHECKED while the suite reported
a number that looked like a result.

⚠️ AND THE IN-SESSION DIFF CALLED IT CLEAN. Baseline and final both had the same
117 errors, so "zero new, zero gone" was true and proved nothing about the code
those tests cover. The defect was only caught by comparing against a figure from
a week earlier. Nothing in the run said "these did not run".

So the guard is not a convenience. A suite that cannot reach its server must say
so ONCE, loudly, naming the URL — not 117 times in a form that survives a diff.

⚠️ DELIBERATELY NOT `pytest.skip`. A skip is quiet, and quiet is the whole
defect. This raises, so the module reports a collection error with an
actionable message and the rest of the tree still runs.
"""
from __future__ import annotations

import os

import httpx

#: Where the HTTP suites look. One definition, so the guard and the suites
#: cannot disagree about what was probed.
BASE_URL: str = os.environ.get("STAGING_URL", "http://localhost:8000")

#: Probe result, cached per process: the check is a network round trip and both
#: suites import this.
_reachable: bool | None = None


class LiveServerUnavailable(RuntimeError):
    """Raised at import time when the suite's server is not answering."""


def _probe(base_url: str, timeout: float = 3.0) -> bool:
    """Is ANYTHING answering HTTP there?

    ⚠️ Any status counts, including 404. The question is whether a server is
    listening, not whether one route exists — a guard that demanded 200 from a
    particular path would start failing for a second reason and the message
    would stop being true.
    """
    try:
        with httpx.Client(timeout=timeout) as c:
            c.get(f"{base_url}/api/health")
        return True
    except httpx.HTTPError:
        return False


def unreachable_message(base_url: str | None = None) -> str:
    url = base_url or BASE_URL
    return (
        f"\n"
        f"╭─ HTTP INTEGRATION SUITES CANNOT REACH THEIR SERVER ──────────╮\n"
        f"│ {url}\n"
        f"│\n"
        f"│ Those suites call the API over the wire. Without a server\n"
        f"│ they assert NOTHING — and because they fail during setup, an\n"
        f"│ in-session diff sees the same errors on both sides and reports\n"
        f"│ the run as unchanged. On 2026-09-22 that hid 117 tests,\n"
        f"│ including every test of the personalization availability\n"
        f"│ surface.\n"
        f"│\n"
        f"│ They are SKIPPED, not run. This one test fails so the run\n"
        f"│ cannot be read as clean.\n"
        f"│\n"
        f"│ Start a server:\n"
        f"│   cd backend && .venv/bin/uvicorn app.main:app --port 8000\n"
        f"│\n"
        f"│ Or point the suites elsewhere:\n"
        f"│   STAGING_URL=https://… python -m pytest …\n"
        f"╰──────────────────────────────────────────────────────────────╯"
    )


def is_reachable(base_url: str | None = None) -> bool:
    global _reachable
    if _reachable is None:
        _reachable = _probe(base_url or BASE_URL)
    return _reachable


def require_live_server(base_url: str | None = None) -> None:
    """Call at MODULE level in any suite that talks to the API over the wire.

    ⚠️ SKIPS, AND THE LOUDNESS LIVES ELSEWHERE — deliberately, and the first
    version of this got it wrong. Raising at module level produces a COLLECTION
    ERROR, and pytest treats collection errors as fatal: measured, a single
    guarded module aborted a run that also contained 21 unrelated tests, none of
    which executed. That turns "117 tests were unchecked" into "nothing ran",
    which is worse than the defect.

    So the module is skipped WITH A REASON, and
    `test_live_server_precondition.py` holds one test that FAILS. The run
    therefore carries a failure nobody can read as clean, every other suite
    still runs, and a skip is visibly not a pass.
    """
    import pytest

    if is_reachable(base_url):
        return
    pytest.skip(
        f"live server unreachable at {base_url or BASE_URL} — see the failure "
        f"in tests/test_live_server_precondition.py",
        allow_module_level=True,
    )
