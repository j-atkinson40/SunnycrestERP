"""IOD r166 — Compliance Sync wired to a live service; Training Expiry retired as COVERED, not unbuilt.

The adapter is thin enough that testing it would test `vault_compliance_sync`.
What is worth pinning is the wiring contract and the two distinctions that would
otherwise look like arbitrary choices:

  1. Training Expiry is `is_active=False` and NOT `is_coming_soon`. Those flags
     mean different things — "already covered daily" versus "declared, never
     built" — and a later reader acting on the wrong one gets a wrong answer from
     a true value.
  2. Training Expiry is retired rather than wired. Wiring it would produce green
     runs that did nothing, because `_notify_admins_compliance_expiry` de-dupes
     and Compliance Sync already ran that morning. That is the pathology this arc
     removed, recreated by the arc.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

_MIGRATION = (
    pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions"
    / "r166_wire_compliance_sync_retire_training_expiry.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("r166", _MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


r166 = _load()


class TestTheWiringIsReal:
    def test_the_method_is_registered(self):
        from app.services.workflow_engine import _SERVICE_METHOD_REGISTRY

        assert r166._PRODUCER_CONFIG["method_name"] in _SERVICE_METHOD_REGISTRY

    def test_the_registry_points_at_an_importable_callable(self):
        """A registry entry naming a module:function that does not resolve fails
        at dispatch, which after A-1 halts the run. Resolved here instead."""
        from app.services.workflow_engine import _SERVICE_METHOD_REGISTRY

        target = _SERVICE_METHOD_REGISTRY[r166._PRODUCER_CONFIG["method_name"]][0]
        module_path, _, func_name = target.partition(":")
        module = __import__(module_path, fromlist=[func_name])
        assert callable(getattr(module, func_name))

    def test_the_adapter_absorbs_the_injected_kwarg(self):
        """THE REASON AN ADAPTER EXISTS AT ALL. The registry auto-injects
        triggered_by_user_id; `sync_compliance_expiries(db, company_id)` has no
        such parameter, so direct registration would TypeError at dispatch."""
        import inspect

        from app.services.workflows.compliance_sync_adapter import run_compliance_sync

        sig = inspect.signature(run_compliance_sync)
        assert "triggered_by_user_id" in sig.parameters
        assert any(
            p.kind is inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        ), "needs **_ignored to tolerate future injected kwargs"

    def test_the_underlying_service_still_exists_and_is_callable(self):
        """The wiring's whole premise is that this capability is already built.
        If it moves or is renamed, the workflow silently points at nothing."""
        from app.services.vault_compliance_sync import sync_compliance_expiries

        assert callable(sync_compliance_expiries)

    def test_kwargs_are_within_the_declared_safelist(self):
        from app.services.workflow_engine import _SERVICE_METHOD_REGISTRY

        allowed = set(
            _SERVICE_METHOD_REGISTRY[r166._PRODUCER_CONFIG["method_name"]][1]
        )
        assert set(r166._PRODUCER_CONFIG.get("kwargs", {})) <= allowed

    def test_the_producer_replaces_rather_than_inserts(self):
        """r165's reasoning, unchanged: a step added at an occupied step_order
        recreates the duplicate-order race r161/r162 removed."""
        assert "INSERT INTO workflow_steps" not in _MIGRATION.read_text().upper()
        assert r166._PRODUCER_STEP == "scan_inspections"

    def test_all_four_declared_steps_are_accounted_for(self):
        """One call covers four declared steps; the other three go inert. A step
        left neither wired nor inert would fail the run after the producer
        succeeded."""
        handled = {r166._PRODUCER_STEP} | {k for k, _o, _w in r166._INERT}
        assert handled == {
            "scan_inspections", "scan_training", "scan_regulatory", "upsert_vault_items",
        }


class TestTrainingExpiryIsRetiredNotMarked:
    def test_is_coming_soon_is_not_set(self):
        """THE DISTINCTION. is_coming_soon means "declared, never built" (r164).
        This capability IS built and IS running daily — it is covered, not
        missing. Overloading the flag is how a later investigation gets a wrong
        answer from a true value."""
        src = _MIGRATION.read_text()
        import re

        assert not re.search(r"SET[^;]*is_coming_soon\s*=", src, re.IGNORECASE), (
            "Training Expiry must not be marked is_coming_soon — it is covered, "
            "not unbuilt"
        )

    def test_it_is_deactivated(self):
        assert "is_active = false" in _MIGRATION.read_text()

    def test_the_reason_is_recorded_in_the_human_readable_field(self):
        """No field gets a second job — the description is what the builder
        already renders, so the explanation goes where a person will see it."""
        desc = r166._TRAINING_NEW_DESC
        assert "RETIRED" in desc
        assert "Compliance Sync" in desc
        assert "de-duped" in desc or "de-dupe" in desc.lower()
        assert "Not 'unbuilt'" in desc or "covered" in desc

    def test_the_original_description_is_preserved_for_the_reverse(self):
        assert r166._TRAINING_WAS_DESC in r166._TRAINING_NEW_DESC
        down = _MIGRATION.read_text().split("def downgrade")[1]
        assert "is_active = true" in down

    def test_the_redundancy_argument_is_written_down(self):
        """"Retired" without "superseded by X" reads as abandonment, and the
        next pass either resurrects it or deletes the wrong one."""
        doc = r166.__doc__ or ""
        assert "REDUNDANT" in doc
        assert "de-dupes" in doc or "de-dupe" in doc
        assert "subset" in doc.lower()


class TestTheFalsifiedClaimIsRecorded:
    def test_the_one_rename_claim_and_its_failure_mode_are_in_the_docstring(self):
        """It was asserted from the step's NAME and falsified by its CONFIG.
        Recorded so the next reader does not re-derive the same wrong fix."""
        doc = r166.__doc__ or ""
        assert "one rename" in doc.lower()
        assert "NAME" in doc and "CONFIG" in doc
        assert "Green and useless" in doc or "green and useless" in doc.lower()


class TestNothingIsDeleted:
    def test_every_touched_step_carries_history_so_none_is_deletable(self):
        """134 / 133 / 133 / 133 and 20 / 19 run-steps. Per step, measured — the
        r162 lesson. Nothing here qualifies for a clean delete."""
        assert "DELETE FROM" not in _MIGRATION.read_text().upper()

    @pytest.mark.parametrize("step_key", [
        "scan_training", "scan_regulatory", "upsert_vault_items",
    ])
    def test_inert_steps_keep_their_original_config_for_the_reverse(self, step_key):
        original = {k: o for k, o, _w in r166._INERT}[step_key]
        assert isinstance(original, dict) and "description" in original
        assert "action_type" not in original, (
            "restoring an invented action_type would not be a reverse"
        )
