"""WE-1 r162 — the cleanup and the gate predicate are ONE change, and the absence is deliberate.

Static, no DB.

Two things here are judgement rather than mechanism, and both would read as
mistakes to someone tidying up later:

  1. Month-End Close's gate has NO `park_when` while its three siblings do. That
     gap is correct — the gate approves a period lock, not a review of findings —
     and the workflow will park on EVERY run as a result.
  2. Safety Program's gate is DELETED rather than predicated, because a predicate
     would make a redundant third review surface fire intermittently instead of
     removing it.

An intentional gap needs to say it is intentional, in the place someone looks.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

_MIGRATION = (
    pathlib.Path(__file__).resolve().parents[1]
    / "alembic" / "versions" / "r162_finish_the_migrated_four.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("r162", _MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


r162 = _load()

_DELETED = {(w, k) for w, _o, k, _t, _c, _i, _d in r162._DELETE}
_NEUTRALISED = {(w, k) for w, k, _o, _w2 in r162._NEUTRALISE}


class TestDeleteVersusNeutralise:
    """The split is per STEP, on run-step history — not per workflow."""

    def test_no_step_is_both_deleted_and_neutralised(self):
        assert not (_DELETED & _NEUTRALISED)

    def test_the_two_with_history_are_neutralised_not_deleted(self):
        """`tier_classification` (120 run-steps) and `notify_if_updated` (2).
        Deleting either violates `workflow_run_steps.step_id ON DELETE NO ACTION`
        — the ONE foreign key referencing workflow_steps, derived from
        pg_constraint rather than assumed."""
        assert ("wf_sys_ar_collections", "tier_classification") in _NEUTRALISED
        assert ("wf_sys_catalog_fetch", "notify_if_updated") in _NEUTRALISED
        assert ("wf_sys_ar_collections", "tier_classification") not in _DELETED
        assert ("wf_sys_catalog_fetch", "notify_if_updated") not in _DELETED

    @pytest.mark.parametrize("step_key", ["invoice_coverage", "scrape_osha"])
    def test_r161s_zero_history_rows_are_deleted_not_left_as_residue(self, step_key):
        """r161 neutralised these on an over-general claim ("history rows
        reference these steps") that held for two of its four and not these two.
        Both have zero run-steps, so the clean delete r161 could have done is
        done here."""
        assert step_key in {k for _w, k in _DELETED}

    def test_the_two_that_genuinely_needed_neutralising_are_left_alone(self):
        """`ar_snapshot` (121) and `fetch_catalog` (2) stay inert — the
        correction to r161 applies only to its zero-history members."""
        assert "ar_snapshot" not in {k for _w, k in _DELETED}
        assert "fetch_catalog" not in {k for _w, k in _DELETED}

    def test_downgrade_can_actually_recreate_every_deleted_row(self):
        """A delete whose reverse is a guess is not reversible. Each entry
        carries order, key, type, config, is_core and display_name — everything
        the table needs except the id, which nothing referenced."""
        for w, order, key, step_type, cfg, _core, _dn in r162._DELETE:
            assert w and key and step_type in {"action", "input"}
            assert isinstance(order, int)
            assert isinstance(cfg, dict) and cfg, f"{key} has no config to restore"
            assert "_retired" not in cfg, (
                f"{key}'s restore config is the r161 INERT shape, not the "
                f"original — the reverse would restore something that never existed"
            )


class TestTheOnePredicate:
    def test_ar_collections_park_when_targets_the_field_the_gate_asks_about(self):
        """Derived the way `needs_review > 0` was: the gate says "review drafts",
        the producer returns `drafts_generated`, and A-3 measured it at 0 on all
        127 runs. Field must reference the PRODUCER step, not the orphan."""
        assert r162._AR_PARK_WHEN == {
            "op": ">",
            "field": "{output.run_collections.drafts_generated}",
            "value": 0,
        }

    def test_the_predicate_uses_a_known_operator(self):
        """An unknown operator is `park_condition_unresolvable` — a failure, not
        a default. Cheap to get wrong, loud when wrong, so pinned."""
        from app.services.workflow_engine import _PARK_OPS

        assert r162._AR_PARK_WHEN["op"] in _PARK_OPS

    def test_the_predicate_evaluates_correctly_on_both_sides(self):
        """The whole point: zero drafts must NOT park; some drafts must."""
        from app.services.workflow_engine import _evaluate_park_when

        gate = dict(r162._AR_PARK_WHEN)
        assert _evaluate_park_when({**gate, "field": 0}) == {"park": False}
        assert _evaluate_park_when({**gate, "field": 3}) == {"park": True}


class TestTheDeliberateAbsence:
    """Month-End Close. The gap that will read as an oversight."""

    def test_month_end_close_gets_no_park_when(self):
        """Pinned as an absence, because the failure mode is someone ADDING one
        by analogy with the three siblings that have one.

        Asserted STRUCTURALLY, not by substring. The note deliberately NAMES
        `anomaly_count` in order to explain why it was rejected, so a substring
        check fails on the explanation — which is the note doing its job. What
        must hold is that no predicate is actually applied, and that the one
        predicate this migration does apply is not keyed on that field.
        """
        assert "park_when" not in r162._MEC_NO_PARK_WHEN, (
            "the intentional-absence note must not itself carry a predicate"
        )
        assert set(r162._MEC_NO_PARK_WHEN) == {"by", "decision", "why", "expect"}
        assert "anomaly_count" not in r162._AR_PARK_WHEN["field"], (
            "a park_when keyed on anomaly_count would suppress a decision rather "
            "than an empty prompt — zero anomalies is a clean close that still "
            "wants a human"
        )

    def test_the_absence_says_why_on_the_row_not_only_in_the_docstring(self):
        """A docstring is read by whoever goes looking for it; a field on the row
        is read by whoever finds the row."""
        note = r162._MEC_NO_PARK_WHEN
        assert "period" in note["why"].lower() and "lock" in note["why"].lower()
        assert "decision" in note["why"].lower()

    def test_the_row_warns_that_parking_every_run_is_correct(self):
        """Six months from now this reads as the A-2 pathology returning. The
        row has to say it is not."""
        expect = r162._MEC_NO_PARK_WHEN["expect"]
        assert "EVERY RUN" in expect
        assert "not the A-2" in expect or "correct" in expect.lower()


class TestTheRemovedGate:
    def test_safety_programs_gate_is_deleted_not_predicated(self):
        """Three review surfaces for one artifact; 8d.1 named
        `safety_program_triage` canonical. A predicate would make the redundant
        surface fire intermittently rather than remove it — worse, because it
        stays in the definition and still competes for the same decision."""
        assert ("wf_sys_safety_program_gen", "approval_gate") in _DELETED
        gates = [k for _w, _o, k, t, _c, _i, _d in r162._DELETE if t == "input"]
        assert gates == ["approval_gate"], (
            "exactly one gate is removed; removing another would need its own "
            "argument about which surface is canonical"
        )

    def test_no_other_workflows_gate_is_touched(self):
        """AR Collections and Month-End Close keep theirs — one predicated, one
        deliberately not."""
        for wf in ("wf_sys_ar_collections", "wf_sys_month_end_close"):
            assert (wf, "approval_gate") not in _DELETED
            assert (wf, "approval_gate") not in _NEUTRALISED
