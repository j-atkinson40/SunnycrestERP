"""The switch suites put the switch back — proven by RUNNING one, twice.

⚠️ **THE DEFECT THIS PINS BLANKED A LIVE SCREEN, AND NO TEST COULD SEE IT.**
Every test in `test_payroll_data_switch.py` passed, before and after. What was
wrong was what the suite left behind: its teardown REMOVED the switch key
whichever way it found it, so a tenant whose switch had been deliberately
turned on had it silently turned off by an unrelated test run. The payroll note
then rendered empty, and the 2026-11-17 walk-through photographed it that way.

⚠️ **SO THIS TEST ASSERTS ON STATE AFTER A REAL RUN, NOT ON THE FIXTURE'S
CODE.** A test that called the fixture's helpers directly would check that the
helpers work, which they did — the leak was in a teardown that was reasoned
about and wrong, and in four sibling suites that had copied it. The suite is
invoked as a subprocess so the assertion is about the same thing the walk-through
suffered: what the database holds once pytest has exited.

⚠️ **TWICE, NOT ONCE.** A run that restores by accident — by writing the value
its own setup happened to want — looks identical to one that restores by
capture, for exactly one run. The second run starts from the state the first
left, which is the condition a `before`/`after` delta cannot distinguish (see
CLAUDE.md §11, "a gate that mutates shared state is not repeatable"). The switch
is asserted after each.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

import pytest

from tests._payroll_switch import ABSENT, read_switch, write_switch
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

_canonical_tenant = make_canonical_tenant_fixture()

#: The suite under observation. ⚠️ Named explicitly rather than discovered:
#: this test is about THIS file's teardown, and a glob would quietly start
#: measuring something else the day another switch suite is added.
SUBJECT = "tests/test_payroll_data_switch.py"


def _run_subject() -> tuple[int, str]:
    """Run the subject suite in a child process. Returns (code, output).

    ⚠️ **NOT PIPED.** `subprocess.run` hands back the child's own exit status;
    reading `$?` through a pipe would report the pipe's last command, which
    succeeds at displaying a crash (CLAUDE.md §11).
    """
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", SUBJECT, "-q", "--no-header", "-p",
         "no:cacheprovider"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        capture_output=True,
        text=True,
        timeout=600,
        env={**os.environ},
    )
    return proc.returncode, proc.stdout + proc.stderr


def _tests_actually_ran(output: str) -> int:
    """How many tests the child reported passing.

    ⚠️ **THE POSITIVE CONTROL, AND IT IS THE LOAD-BEARING HALF OF THIS FILE.**
    "The switch is unchanged after running the suite" is satisfied perfectly by
    a suite that never ran — a bad path, an import error, a collection failure
    all leave the switch exactly as it was. That reading is indistinguishable
    from the fix working. So the count is required to be NON-ZERO and is read
    before the state assertion it vouches for.
    """
    m = re.search(r"(\d+) passed", output)
    return int(m.group(1)) if m else 0


@pytest.mark.parametrize(
    "prior",
    [
        pytest.param(True, id="on-the-state-that-broke-the-walk"),
        pytest.param(False, id="off-but-present"),
        pytest.param(ABSENT, id="absent"),
    ],
)
def test_the_switch_suite_leaves_the_switch_as_it_found_it(prior, _canonical_tenant):
    """⚠️ **ALL THREE PRIOR STATES, BECAUSE TWO OF THEM ARE FALSEY.** `absent`,
    `False` and `True` are three distinct things the tenant can hold. The old
    teardown mapped all three to one, and `on` is the one that cost a
    walk-through — but a restore that collapsed `absent` into `False` would be
    a different world that behaves the same until something reads the key to
    decide whether the tenant has ever been configured.
    """
    original = read_switch(TESTCO_ID)
    try:
        write_switch(TESTCO_ID, prior)
        assert _same(read_switch(TESTCO_ID), prior), "the test could not set up"

        for run in (1, 2):
            code, output = _run_subject()
            ran = _tests_actually_ran(output)
            # The control first, then the thing it vouches for.
            assert ran > 0, (
                f"run {run} reported no passing tests, so 'the switch is "
                f"unchanged' would be true of a suite that never executed:\n"
                f"{output[-3000:]}"
            )
            assert code == 0, f"run {run} failed:\n{output[-3000:]}"

            after = read_switch(TESTCO_ID)
            assert _same(after, prior), (
                f"run {run} of {SUBJECT} left the switch as {after!r}, "
                f"not {prior!r} as it found it. This is the defect that blanked "
                f"the payroll note mid-walk-through on 2026-11-17."
            )
    finally:
        write_switch(TESTCO_ID, original)


def _same(a, b) -> bool:
    """Equality that keeps `ABSENT` distinct from every falsey value.

    ⚠️ `ABSENT == False` would be False by object identity anyway, but `a == b`
    on the sentinel invites someone to "simplify" this to `not a and not b`
    later — which is the collapse the whole file exists to prevent. The
    sentinel's `__bool__` raises for the same reason.
    """
    if a is ABSENT or b is ABSENT:
        return a is ABSENT and b is ABSENT
    return a is b if isinstance(a, bool) or isinstance(b, bool) else a == b
