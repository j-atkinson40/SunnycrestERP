"""WE-1 A-2 — a gate may decline to ask an empty question.

An `input` step parked on EVERY run regardless of whether its upstream produced
anything. Expense Categorization did it 12,367 times at a 15-minute cadence over
three months — the same defect `ae3a2eab` fixed on the agent side, one layer over.

⚠️ THE AGENT-SIDE PREDICATE WOULD NOT HAVE FIXED IT. `_nothing_to_approve()` keys
on `anomaly_count == 0`; the parked runs carry `needs_review: 0` AND
`anomaly_count: 1`. A faithful port would have kept parking all 12,367 — correct
by its own definition and useless. The two subsystems mean different things by
"nothing", which is why the condition is DECLARED at the step rather than
inferred by the engine.
"""
from __future__ import annotations

import pytest

from app.services.workflow_engine import (
    _FAILURE_STATUSES,
    _PARK_OPS,
    _evaluate_condition,
    _evaluate_park_when,
)


class TestParkWhenVerdicts:
    def test_the_production_case_does_not_park(self):
        """needs_review: 0 → skip. The 12,367-run case."""
        assert _evaluate_park_when(
            {"field": 0, "op": ">", "value": 0}
        ) == {"park": False}

    def test_something_to_review_still_parks(self):
        assert _evaluate_park_when(
            {"field": 3, "op": ">", "value": 0}
        ) == {"park": True}

    def test_anomaly_count_would_have_given_the_opposite_answer(self):
        """Pins WHY the field choice matters, not just that it works.

        The same parked run carries needs_review 0 and anomaly_count 1. If the
        gate keyed on anomaly_count it would still park — which is what a
        faithful port of the agent-side fix would have done.
        """
        assert _evaluate_park_when({"field": 0, "op": ">", "value": 0})["park"] is False
        assert _evaluate_park_when({"field": 1, "op": ">", "value": 0})["park"] is True


class TestBrokenGatesFailLoud:
    """NEVER DEFAULT. Parking or skipping on a broken gate is a silent wrong
    answer — the class A-1 closed one function over."""

    @pytest.mark.parametrize("gate,why", [
        ({"field": 1, "op": "~", "value": 0}, "unknown operator"),
        ({"field": "{output.nope.x}", "op": ">", "value": 0}, "unresolved field"),
        ({"field": None, "op": ">", "value": 0}, "not comparable"),
        ("true", "not an object"),
        (["field", ">", 0], "not an object"),
    ])
    def test_unevaluable_gates_report_failure(self, gate, why):
        out = _evaluate_park_when(gate)
        assert out.get("status") == "park_condition_unresolvable", why
        assert out.get("reason"), "a failure must say what was wrong"

    def test_the_failure_status_is_wired_into_the_engine_set(self):
        """Its own status, not `error`, so the cause is legible in output_data
        without reading the expression back — and it must be in the set A-1
        checks or a broken gate is silently a completed step."""
        assert "park_condition_unresolvable" in _FAILURE_STATUSES

    def test_an_unresolved_template_is_not_compared_as_a_string(self):
        """`{output.x.y}` survives resolution as literal text when the step or
        key does not exist. Compared rather than caught, it would be truthy and
        the gate would park forever on a typo."""
        out = _evaluate_park_when(
            {"field": "{output.run_categorization.typo}", "op": ">", "value": 0}
        )
        assert out.get("status") == "park_condition_unresolvable"


class TestAdditiveByConstruction:
    def test_absent_park_when_is_not_this_module_s_business(self):
        """A gate with no `park_when` never reaches the evaluator — the engine
        parks as it always did. That is what makes this additive: no exclusion
        list, and 17 other workflows keep their behaviour untouched.

        Pinned as a property of the OPERATOR SET rather than of the engine call
        path: there is no operator that means "absent", so absence cannot be
        expressed as a verdict and must be handled before the call.
        """
        assert None not in _PARK_OPS
        assert "" not in _PARK_OPS


class TestConditionStepUnknownOperator:
    """The tenth instance, fixed in the same commit because `park_when` creates
    the hazard: `>` is now a thing people reach for, and written on a condition
    step it used to evaluate false and say nothing."""

    def test_unknown_operator_now_reports_failure(self):
        out = _evaluate_condition({"field": 5, "op": ">", "value": 0})
        assert out.get("status") == "error"
        assert "unknown condition operator" in out["error"]
        assert "park_when" in out["error"], (
            "the message should point at where numeric comparison DOES live"
        )

    @pytest.mark.parametrize("op,field,value,expected", [
        ("==", "a", "a", True),
        ("!=", "a", "b", True),
        ("in", "a", ["a", "b"], True),
        ("==", "a", "b", False),
    ])
    def test_the_three_known_operators_are_unchanged(self, op, field, value, expected):
        """The fix must not alter existing condition steps — only the
        previously-silent fall-through."""
        out = _evaluate_condition({"field": field, "op": op, "value": value})
        assert out["condition_result"] is expected
        assert "status" not in out

    def test_default_operator_is_still_equality(self):
        """`op` omitted defaults to `==` — unchanged, and worth pinning because
        the new `else` branch sits right where that default is resolved."""
        out = _evaluate_condition({"field": "x", "value": "x"})
        assert out["condition_result"] is True
