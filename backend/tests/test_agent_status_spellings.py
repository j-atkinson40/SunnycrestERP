"""`agent_jobs.status` holds two spellings of one terminal state, both live.

⚠️ THE SEVERITY I FIRST REPORTED FOR THIS WAS WRONG, and the correction is the
point of this file. I claimed `tax_package_agent` could emit a false
`tax_package_missing_*` — reporting a filing obligation as not done — because it
filters `status == "complete"` and would miss the `completed` rows. Measured
against production 2026-09-08, that is false twice over:

  1. The job types tax_package looks for (`year_end_close`, `1099_prep`,
     `month_end_close`, `estimated_tax_prep`) have ZERO rows in EITHER spelling.
  2. Its query also bounds on `period_start`/`period_end`, and all 840
     `completed` rows have a NULL period, which fails both bounds regardless of
     spelling. Reproducing its exact predicate returns 0 `completed` rows.

The real exposure is one unscoped query in the Pulse activity feed, and it is
informational rather than a filing risk.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.schemas.agent import COMPLETE_STATUSES, AgentJobStatus

_APP = Path(__file__).resolve().parents[1] / "app"


def test_the_canonical_spelling_is_in_the_vocabulary():
    assert AgentJobStatus.COMPLETE.value == "complete"
    assert "complete" in COMPLETE_STATUSES and "completed" in COMPLETE_STATUSES


def test_no_unscoped_single_spelling_filter_exists_anywhere():
    """⚠️ REWRITTEN 2026-09-10 WHEN THE SITE IT GUARDED WAS DELETED.

    This read ONE file by path — `services/pulse/activity_layer_service.py` —
    and asserted the fix was present in it. That file was "the one genuinely
    exposed site": an activity feed not scoped by job_type, where a
    single-spelling filter silently dropped every legacy-agent completion
    (9 in 24h, 63 over 7 days, measured 2026-09-08).

    Pulse was retired 2026-09-10 and the activity layer went with it, so the
    test could not pass — it was reading a file that no longer exists.

    ⚠️ THE GUARD IS NOT DELETED, BECAUSE THE BUG CLASS IS NOT. What was
    site-specific about it was an accident of where the defect happened to be
    found. Asserting the fix is present in one named file is a check that dies
    with the file and says nothing about anywhere else — a constructed scope,
    the same shape as a constructed name. This version ENUMERATES instead, so
    it protects every file including ones not yet written.

    Verified at rewrite time: `COMPLETE_STATUSES` now has exactly one reference
    in `app/` — its own definition in `schemas/agent.py`. The exposure went
    with Pulse; the vocabulary is currently unconsumed, and the next unscoped
    completion filter anyone writes should reach for it.
    """
    offenders = []
    for f in sorted(_APP.rglob("*.py")):
        src = f.read_text()
        if '"complete", "approved", "rejected", "failed"' in src:
            offenders.append(str(f.relative_to(_APP)))
    assert offenders == [], (
        "single-spelling completion filter is back in: "
        f"{offenders}. Use COMPLETE_STATUSES from app.schemas.agent — the "
        "legacy agents write 'completed' and an unscoped filter drops them "
        "with nothing about the result looking wrong."
    )


def test_scoped_queries_are_left_alone_deliberately():
    """POSITIVE CONTROL FOR THE SCOPE OF THIS FIX, and the reason it is small.

    Most `status == "complete"` filters in this codebase are CORRECT: they are
    scoped to a job_type that only ever writes the canonical spelling. Rewriting
    them all would be churn justified by a severity that measurement did not
    support. This asserts such sites still exist, so a later reader does not
    'finish the job' by sweeping them."""
    scoped = []
    for f in sorted(_APP.rglob("*.py")):
        lines = f.read_text().split("\n")
        for i, line in enumerate(lines):
            if 'AgentJob.status == "complete"' not in line:
                continue
            window = "\n".join(lines[max(0, i - 8): i + 1])
            if "AgentJob.job_type ==" in window:
                scoped.append(f"{f.relative_to(_APP)}:{i+1}")
    assert scoped, (
        "no job_type-scoped 'complete' filters found — either they were all "
        "swept (churn this fix deliberately avoided) or the scanner is broken"
    )


def test_no_unscoped_single_spelling_filter_remains():
    """⚠️ THE GUARD. An `AgentJob.status` filter that names one spelling and is
    NOT scoped by job_type is the defect class. This finds a new one.

    `tax_package_agent` is excluded by name: its query is unscoped by job_type
    but bounds on period_start/period_end, and every `completed` row has a NULL
    period, so it cannot match one. That exemption is measured, not assumed —
    see this module's docstring.
    """
    offenders = []
    for f in sorted(_APP.rglob("*.py")):
        if f.name == "tax_package_agent.py":
            continue
        lines = f.read_text().split("\n")
        for i, line in enumerate(lines):
            if not re.search(r'AgentJob\.status\s*==\s*"complete"', line):
                continue
            window = "\n".join(lines[max(0, i - 8): i + 1])
            if "AgentJob.job_type ==" not in window:
                offenders.append(f"{f.relative_to(_APP)}:{i+1}: {line.strip()}")
    assert not offenders, (
        "unscoped single-spelling completion filters:\n  " + "\n  ".join(offenders)
        + "\nUse schemas.agent.COMPLETE_STATUSES, or scope the query by job_type."
    )


def test_the_scanner_sees_the_tree():
    """POSITIVE CONTROL. The two scanners above assert absences; a scanner that
    reads nothing satisfies both."""
    hits = sum(
        1 for f in _APP.rglob("*.py")
        for line in f.read_text().split("\n")
        if "AgentJob.status" in line
    )
    assert hits >= 10, f"scanner found only {hits} AgentJob.status references"
