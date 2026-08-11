"""IOD r165 — MSR is wired AND deliberately partial. Both halves are pinned.

Static, no DB.

Two judgements here would each read as a mistake to someone tidying up:

  1. `send_statements` is LEFT BROKEN. A cleanup pass holding a list of broken
     steps would clear it — and the workflow would then complete green having
     sent nothing, which is the silent-success class A-1 was built to end.
  2. The gate gets NO `park_when`, while siblings in the same arc have one.

And one structural choice that would be easy to "simplify" wrongly: the producer
REPLACES a step instead of being inserted, because inserting at an occupied
`step_order` would recreate the pathology r161 and r162 removed.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

_MIGRATION = (
    pathlib.Path(__file__).resolve().parents[1]
    / "alembic" / "versions" / "r165_wire_monthly_statement_run.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("r165", _MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


r165 = _load()


class TestTheProducerIsWiredToSomethingReal:
    def test_the_method_is_actually_registered(self):
        """DERIVED FROM THE ENGINE, not asserted. A config pointing at an
        unregistered method fails at run time with `unknown method`, which after
        A-1 halts the run — the wiring would be worse than the no-op it replaced."""
        from app.services.workflow_engine import _SERVICE_METHOD_REGISTRY

        assert r165._PRODUCER_CONFIG["method_name"] in _SERVICE_METHOD_REGISTRY

    def test_the_kwargs_are_within_the_registry_safelist(self):
        """The registry declares an allowed-kwargs tuple per entry; anything
        outside it is rejected at dispatch."""
        from app.services.workflow_engine import _SERVICE_METHOD_REGISTRY

        entry = _SERVICE_METHOD_REGISTRY[r165._PRODUCER_CONFIG["method_name"]]
        allowed = set(entry[1])
        assert set(r165._PRODUCER_CONFIG.get("kwargs", {})) <= allowed

    def test_the_action_type_is_one_the_engine_knows(self):
        import re

        from app.services import workflow_engine

        src = pathlib.Path(workflow_engine.__file__).read_text()
        known = set(re.findall(r'action_type == "([a-z_]+)"', src))
        assert r165._PRODUCER_CONFIG["action_type"] in known

    def test_the_producer_replaces_rather_than_inserts(self):
        """No INSERT of a step. Adding one at an occupied step_order would
        manufacture the duplicate-order race r161/r162 just removed — in the same
        arc that removed it."""
        src = _MIGRATION.read_text()
        assert "INSERT INTO workflow_steps" not in src.upper()
        assert r165._PRODUCER_STEP == "generate_statements"


class TestTheDeliberatelyPartialState:
    def test_send_statements_is_not_repaired_or_cleared(self):
        """THE LOAD-BEARING OMISSION. Bulk dispatch does not exist;
        generate_statement_run generates only. Clearing this step makes the run
        complete green having sent nothing."""
        src = _MIGRATION.read_text()
        assert "DELETE FROM" not in src.upper(), "no step is deleted here"
        note = r165._DELIBERATELY_BROKEN
        assert "LEFT BROKEN" in note["decision"]
        # ⚠️ ASSERTION CORRECTED 2026-08-11 (BSS-1). This previously required the
        # reason to say "generates only … nothing bulk-sends", which was FALSE:
        # `statement_service.send_all_digital` IS a bulk fan-out. The durable
        # property is that the note names the ACTUAL gap — a sender filtered to
        # zero rows by a column mismatch — rather than a non-existent capability.
        why = note["why"].lower()
        assert "send_all_digital" in why or "exists" in why, (
            "the reason must acknowledge that bulk dispatch EXISTS — claiming "
            "otherwise is what stops the next reader finding it"
        )
        assert "filtered" in why or "zero rows" in why, (
            "the reason must name the real gap: the sender is filtered to zero "
            "rows for this producer's output"
        )

    def test_the_broken_step_carries_its_reason_on_the_row(self):
        """An unexplained broken step reads as an oversight and the next pass
        closes it. The explanation has to live where the row is queried."""
        note = r165._DELIBERATELY_BROKEN
        assert "silent" in note["why"].lower()
        assert note["upgrade_path"]
        assert note["params_are_the_spec"] == [
            "from_name", "reply_to", "include_zero_balance",
        ]

    def test_the_upgrade_path_does_not_cite_the_unproven_recipe(self):
        """⚠️ THIS TEST WAS INVERTED 2026-08-11 (BSS-1), AND ITS OLD NAME WAS THE
        FALSEHOOD: `test_the_upgrade_path_names_the_proven_recipe`.

        It asserted that the note cites `wf_mfg_send_statement` as a proven
        recipe. Measured: that workflow's `generate_document` step omits
        `template_key` + `title` so the handler raises, its `send_email` step is
        a two-line stub that calls nothing, and it has ZERO runs platform-wide.
        It proves nothing.

        "Fully built" was asserted from step NAMES and recognised action types
        without reading the configs — the same error STATE records that morning
        as `notify_admins` / "one rename from working", repeated four hours later.

        A test that pins a false claim is worse than no test: it enforces the
        falsehood against anyone who corrects it. So the assertion is now the
        reverse — the note must NOT hold that workflow up as a model.
        """
        note = r165._DELIBERATELY_BROKEN
        assert "wf_mfg_send_statement" not in note["upgrade_path"], (
            "the upgrade path cites wf_mfg_send_statement as a recipe; it is "
            "broken and has never run"
        )
        assert "was_recorded_as" in " ".join(note), (
            "the corrected note must preserve what it previously claimed, so "
            "the correction is legible rather than silent"
        )

    def test_the_docstring_leads_with_the_red_run_being_intended(self):
        """Someone triaging a failed run six weeks from now should find this
        before filing a regression."""
        doc = r165.__doc__ or ""
        head = doc[:400]
        assert "INTENDED" in head or "intended" in head
        assert "regression" in head


class TestTheDeliberateAbsence:
    def test_no_park_when_is_applied(self):
        assert "park_when" not in r165._NO_PARK_WHEN
        assert set(r165._NO_PARK_WHEN) == {
            "by", "decision", "why", "expect", "upgrade_path",
        }

    def test_the_rejected_predicate_is_named_with_its_failure_mode(self):
        """total_customers > 0 is the plausible wrong answer — the one someone
        reaches for by analogy. The note says why it is wrong, not just that it
        was not chosen."""
        why = r165._NO_PARK_WHEN["why"]
        assert "total_customers" in why
        assert "flagged" in why.lower()

    def test_the_upgrade_path_is_recorded_so_it_is_not_re_derived(self):
        up = r165._NO_PARK_WHEN["upgrade_path"]
        assert "flagged_count" in up
        assert "StatementRunItem" in up

    def test_both_intended_outcomes_are_stated_together(self):
        """It parks AND then fails. Either one alone looks like a bug."""
        expect = r165._NO_PARK_WHEN["expect"]
        assert "PARKS" in expect and "FAILS" in expect


class TestReversibility:
    @pytest.mark.parametrize("original,key", [
        ({"description": "Generate statement PDFs"}, "_PRODUCER_WAS"),
        ({"description": "Find charge-account customers with activity"}, "_INERT_WAS"),
    ])
    def test_downgrade_restores_the_real_originals(self, original, key):
        """Read off production, not reconstructed — both are prose-only configs
        with no action_type, and inventing one would not be a reverse."""
        assert getattr(r165, key) == original
        assert "action_type" not in getattr(r165, key)

    def test_downgrade_removes_both_annotations(self):
        down = _MIGRATION.read_text().split("def downgrade")[1]
        assert "_deliberately_broken" in down
        assert "_no_park_when" in down

    def test_the_producer_config_is_json_serialisable(self):
        """It is written through json.dumps into a jsonb column; a non-encodable
        value fails at apply time on production rather than here."""
        json.dumps(r165._PRODUCER_CONFIG)
        json.dumps(r165._NO_PARK_WHEN)
        json.dumps(r165._DELIBERATELY_BROKEN)
