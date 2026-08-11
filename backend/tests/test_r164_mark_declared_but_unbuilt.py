"""IOD r164 — the two flags are two different claims, and only one stops a cron.

Static, no DB.

The defect this guards is specific and was nearly shipped: `is_coming_soon` is
NOT filtered by the scheduler. Marking a cron-triggered placeholder and stopping
there labels it correctly and leaves it firing — which would have looked like a
fix and produced a daily failed run forever.

    workflow_scheduler.py sweep  → is_active, schedule_retired_at
    workflow_engine.py catalog   → is_active, is_coming_soon

Two queries, two questions. "This was never built" and "do not fire this on a
timer" are different facts, and only Auto-Delivery needs both.
"""
from __future__ import annotations

import importlib.util
import pathlib
import re

import pytest

_MIGRATION = (
    pathlib.Path(__file__).resolve().parents[1]
    / "alembic" / "versions" / "r164_mark_declared_but_unbuilt.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("r164", _MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


r164 = _load()


class TestTheTwoFlagsAreTwoClaims:
    def test_only_the_cron_triggered_one_is_deactivated(self):
        """The seven are event/manual — the scheduler dispatches only
        time_of_day / time_after_event / scheduled, so they never fire and
        deactivating them would hide a declaration we decided to keep visible."""
        assert r164._DEACTIVATE == ["wf_sys_auto_delivery"]

    def test_everything_deactivated_is_also_marked(self):
        """Deactivating without marking says "off" without saying why. The
        marking is the record that it was declared and never built."""
        assert set(r164._DEACTIVATE) <= set(r164._DEACTIVATE + r164._MARK_ONLY)
        src = _MIGRATION.read_text()
        assert "_MARK_ONLY + _DEACTIVATE" in src, (
            "the is_coming_soon update must cover the deactivated set too"
        )

    def test_all_eight_minus_the_deleted_one_are_covered(self):
        """r163 deleted Social Service Certificate; the remaining seven plus
        Auto-Delivery are the eight the IOD derivation found."""
        covered = set(r164._MARK_ONLY) | set(r164._DEACTIVATE)
        assert len(covered) == 8
        assert "wf_sys_ss_certificate" not in covered, (
            "already deleted by r163 — marking a deleted row is a no-op that "
            "reads as coverage"
        )

    def test_the_scheduler_does_not_filter_is_coming_soon(self):
        """DERIVED FROM THE SOURCE. This is the fact the whole migration turns
        on: if the scheduler ever starts filtering `is_coming_soon`, the
        `is_active=False` half becomes redundant — and if someone REMOVES the
        `is_active` filter, marking stops being sufficient and placeholders fire
        again."""
        from app.services import workflow_scheduler

        src = pathlib.Path(workflow_scheduler.__file__).read_text()
        sweep = src.split("def _schedulable_workflows")[1].split("def ")[0] \
            if "_schedulable_workflows" in src else src
        assert "is_active" in sweep, (
            "the scheduler no longer filters is_active — deactivating a "
            "placeholder no longer stops it firing"
        )
        assert "schedule_retired_at" in sweep

    def test_schedule_retired_at_is_not_used_as_an_off_switch(self):
        """It means "a MoC trigger adopted this schedule" (r129 / Transfer T-1).
        Using it to mean "never built" would make Monthly Statement Run —
        genuinely adopted, stamped 2026-07-17 — indistinguishable from a
        placeholder."""
        src = _MIGRATION.read_text()
        setters = re.findall(r"SET\s+schedule_retired_at", src, re.IGNORECASE)
        assert not setters, "schedule_retired_at must not be stamped here"


class TestReversibility:
    def test_downgrade_restores_both_flags(self):
        src = _MIGRATION.read_text()
        down = src.split("def downgrade")[1]
        assert "is_active = true" in down
        assert "is_coming_soon = false" in down

    def test_no_row_is_deleted(self):
        """The whole point of reversing the delete ruling. Auto-Delivery has 8
        runs and `workflow_runs.workflow_id` is ON DELETE NO ACTION, so deleting
        it would have required destroying the history that records the silent
        period plus A-1's first honest failure."""
        src = _MIGRATION.read_text()
        assert "DELETE FROM" not in src.upper()

    @pytest.mark.parametrize("workflow_id", [
        "wf_sys_scribe_processing", "wf_sys_legacy_print_proof",
        "wf_sys_vault_order_fulfillment", "wf_sys_auto_delivery",
    ])
    def test_the_definitions_stay_in_the_seeder(self, workflow_id):
        """Unlike r163, no code edit — these workflows continue to be declared.
        Marking is a state change on an existing declaration, not a removal."""
        from app.data.default_workflows import ALL_DEFAULT_WORKFLOWS

        assert workflow_id in {w["id"] for w in ALL_DEFAULT_WORKFLOWS}
