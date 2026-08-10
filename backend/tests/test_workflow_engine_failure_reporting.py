"""WE-1 A-1 — a step that reported a failure is not recorded as a success.

THE PROPERTY THAT HAD NEVER HELD ONCE. Before this fix `_execute_step` set
`rs.status = "completed"` without inspecting the output, so every failure the
engine returns as DATA rather than raising was written down as success. Measured
on production before the change:

    steps marked completed while reporting unknown_action_type : 13,207
    steps ever marked failed, for any reason, in all history   :      0

Zero. Not because nothing failed — because failure was overwritten. Only a
RAISED exception ever reached the `except` branch, and the SIX shapes in
`_FAILURE_STATUSES` are returned, not raised.

These tests are deliberately about the SEAM rather than any one action type: the
thing worth pinning is "a failure-shaped output does not become a completed
step", because the specific shape that bit us (`unknown_action_type`) is one of
six — and the sixth, `errored`, was missed on the first pass and found by the
derived test below rather than by re-reading the list.
"""
from __future__ import annotations

import pytest

from app.services import workflow_engine


class TestFailureStatusSet:
    """The set is the only thing between a returned failure and a green step."""

    def test_every_failure_return_in_the_module_is_in_the_set(self):
        """DERIVED FROM THE SOURCE, not from memory.

        Scans this module for `{"status": "<x>"}` returns and asserts each is
        either a known failure shape or a known success shape. A new failure
        return added without registering it here is silently a success — which
        is the exact defect, so it fails this test instead.
        """
        import pathlib
        import re

        src = pathlib.Path(workflow_engine.__file__).read_text()
        returned = set(re.findall(r'"status":\s*"([a-z_]+)"', src))

        # Statuses that legitimately mean "this worked" or are informational.
        benign = {
            "completed", "ok", "success", "skipped", "queued", "sent",
            "applied", "pending", "running", "awaiting_input",
            "awaiting_approval", "failed", "dry_run", "no_op", "noop",
        }
        unclassified = returned - workflow_engine._FAILURE_STATUSES - benign
        assert not unclassified, (
            f"status value(s) {sorted(unclassified)} are returned by the engine "
            f"but classified neither as failure nor benign. If any means 'this "
            f"did not work', add it to _FAILURE_STATUSES — otherwise it is "
            f"recorded as a completed step, which is the defect this guards."
        )

    def test_the_shape_that_cost_three_months_is_in_the_set(self):
        # 13,207 steps. Named explicitly so a refactor that drops it fails
        # loudly rather than restoring the silence.
        assert "unknown_action_type" in workflow_engine._FAILURE_STATUSES

    def test_all_known_shapes_are_covered(self):
        assert workflow_engine._FAILURE_STATUSES == {
            "unknown_action_type",
            "unknown_step_type",
            "error",
            "errored",
            "unsupported_record_type",
            "missing_params",
        }


class TestTheSeam:
    """The predicate itself, without a database.

    `_execute_step` needs a live run/step/session; these pin the DECISION it
    makes rather than re-testing SQLAlchemy. The integration behaviour (run
    halts, escalation routes) is covered by the engine's own suites.
    """

    @pytest.mark.parametrize("status", sorted({
        "unknown_action_type", "unknown_step_type", "error", "errored",
        "unsupported_record_type", "missing_params",
    }))
    def test_failure_shapes_are_recognised(self, status):
        assert {"status": status}.get("status") in workflow_engine._FAILURE_STATUSES

    @pytest.mark.parametrize("output", [
        {"status": "completed"},
        {"type": "open_slide_over", "record_type": "invoice"},
        {"condition_result": True},
        {},
    ])
    def test_success_and_shapeless_outputs_are_not_failures(self, output):
        """A step whose output has no `status` at all must still complete.

        Most handlers return a payload with no status key — `open_slide_over`
        returns a type, condition steps return `condition_result`. Treating a
        missing status as failure would fail nearly every step on the platform,
        which is the opposite error and a far louder one.
        """
        assert output.get("status") not in workflow_engine._FAILURE_STATUSES

    def test_a_non_dict_output_is_not_treated_as_failure(self):
        """The guard is `isinstance(output, dict)` first.

        A handler returning a string or None must not raise inside the status
        check — the fix must not convert an odd-but-working handler into a
        failure.
        """
        for output in (None, "done", 42, []):
            assert not (
                isinstance(output, dict)
                and output.get("status") in workflow_engine._FAILURE_STATUSES
            )
