"""WE-1 A-1 follow-up — r161's target set is the derived one, and its EXCLUSIONS hold.

Static, no DB. The SQL is four UPDATEs and not worth pinning; what is worth
pinning is the SCOPE, because the scope is the whole judgement.

r160 fixed one instance of a pathology nobody had established was a class. The
derivation found four. It also found seven MORE workflows with a broken step
ahead of a working one where the same treatment would be WRONG — the surviving
step there is a gate or a notification, never a producer, so neutralising would
trade a loud failure for a silent empty park and undo WE-1 A-2.

That exclusion is a judgement call living in a docstring. A later reader with a
list of "broken steps still unfixed" would reasonably close the gap. These tests
make closing it fail loudly instead.
"""
from __future__ import annotations

import importlib.util
import pathlib
import re

import pytest

_MIGRATION = (
    pathlib.Path(__file__).resolve().parents[1]
    / "alembic" / "versions" / "r161_neutralise_orphan_producer_twins.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("r161", _MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


r161 = _load()


class TestTheTargetSet:
    def test_exactly_the_four_derived_twins(self):
        """Exact equality on purpose — an addition should be a deliberate act.

        The set was DERIVED (engine source parsed for recognised action types,
        every step row classified). Two were found by hand; two were not. A
        fifth arriving without re-running that derivation is the thing to catch.
        """
        assert {(w, k) for w, k, _o, _t, _y in r161._TARGETS} == {
            ("wf_sys_ar_collections", "ar_snapshot"),
            ("wf_sys_month_end_close", "invoice_coverage"),
            ("wf_sys_safety_program_gen", "scrape_osha"),
            ("wf_sys_catalog_fetch", "fetch_catalog"),
        }

    def test_every_target_names_the_producer_it_unblocks(self):
        """The justification IS the working twin. Without one named, this
        migration is just disabling a step — which is the excluded case."""
        for _w, key, _o, twin, why in r161._TARGETS:
            assert twin, f"{key} neutralised without naming what it unblocks"
            assert why and len(why) > 30, f"{key} carries no reason"

    def test_latent_and_regressed_are_both_present_and_labelled(self):
        """Two failed post-deploy; two have never run. Including the latent ones
        is the point — a workflow that has not fired since the deploy carries
        the identical break, and waiting for it to bite is not a strategy."""
        reasons = " ".join(y for *_x, y in r161._TARGETS)
        assert reasons.count("LATENT") == 2
        assert reasons.count("ACTIVELY REGRESSED") == 2


class TestTheExclusionsHold:
    """The ruling. Each of these would look like an obvious gap to a later pass."""

    @pytest.mark.parametrize("step_key,survivor,why_not", [
        ("transcribe", "confidence_review", "INPUT step — would park on nothing"),
        ("extract_fields", "confidence_review", "INPUT step — would park on nothing"),
        ("generate_proof", "await_approval", "INPUT step — would park on nothing"),
        ("identify_customers", "approval_gate", "INPUT step — would park on nothing"),
        ("generate_statements", "approval_gate", "INPUT step — would park on nothing"),
        ("scan_documents", "notify_admin", "notification with no producer behind it"),
        ("check_preneed", "notify_if_found", "the survivor CONSUMES its output"),
    ])
    def test_broken_before_a_gate_or_notification_is_not_neutralised(
        self, step_key, survivor, why_not
    ):
        """Neutralising these undoes A-2 rather than completing A-1.

        A-2 exists to stop gates asking about nothing; A-3 cleared 610 runs of
        exactly that. Making the producer inert so the gate can run recreates
        the condition both were written to remove.
        """
        assert step_key not in {k for _w, k, _o, _t, _y in r161._TARGETS}, (
            f"{step_key} was neutralised, but what survives behind it is "
            f"{survivor} — {why_not}"
        )

    @pytest.mark.parametrize("step_key", ["tier_classification", "payment_reconciliation"])
    def test_order_2_twins_are_not_neutralised(self, step_key):
        """The same argument one level down.

        These share step_order 2 with an `approval_gate`. Neutralising them lets
        the gate run, and a gate whose producer is inert parks on nothing.
        """
        assert step_key not in {k for _w, k, _o, _t, _y in r161._TARGETS}


class TestTheNeutralisedShape:
    def test_show_confirmation_is_recognised_by_the_engine(self):
        """Derived from the engine source, not asserted from memory.

        If the handler were ever removed, these four steps would go from inert
        to `unknown_action_type` — silently restoring the exact break this
        migration exists to remove.
        """
        from app.services import workflow_engine

        src = pathlib.Path(workflow_engine.__file__).read_text()
        assert "show_confirmation" in set(
            re.findall(r'action_type == "([a-z_]+)"', src)
        )

    def test_the_inert_handler_returns_no_status(self):
        """Load-bearing: A-1 fails a step whose output carries a failure status.
        `show_confirmation` returns `{"type": "confirmation", ...}` with no
        `status` key, so the step completes and the run PROCEEDS to the producer.
        A handler that grew a status field would re-break all four."""
        from app.services import workflow_engine

        src = pathlib.Path(workflow_engine.__file__).read_text()
        handler = src.split('if action_type == "show_confirmation":')[1].split("\n")[1]
        assert '"status"' not in handler, (
            "show_confirmation now returns a status — verify it is not a failure "
            "shape, or these four steps halt their runs again"
        )

    def test_downgrade_restores_the_real_original_not_a_guess(self):
        """Each original config was read off production rather than reconstructed.

        Three carry only a prose `description` and no action_type at all — a step
        that named its intent and never did anything. A downgrade that invented
        `{"action_type": "system_job"}` for those would not be a reverse.
        """
        originals = {k: o for _w, k, o, _t, _y in r161._TARGETS}
        assert originals["ar_snapshot"] == {"description": "Snapshot overdue AR"}
        assert originals["fetch_catalog"] == {
            "job": "wilbert_catalog_fetch", "action_type": "system_job",
        }
        for key, original in originals.items():
            assert original.get("action_type") != "show_confirmation", (
                f"{key}'s 'original' is the neutralised shape — downgrade would "
                f"be a no-op and the reverse would silently not reverse"
            )

    def test_the_unfixed_limitation_travels_with_the_data(self):
        """The duplicate `step_order` is NOT fixed. That caveat lives in the
        `_retired` note rather than only in a docstring, because the note is what
        a later reader finds when they query the row."""
        note = r161._retired_note("x", {"description": "d"}, "twin", "why")
        assert "not_fixed" in note
        assert "step_order" in note["not_fixed"]
