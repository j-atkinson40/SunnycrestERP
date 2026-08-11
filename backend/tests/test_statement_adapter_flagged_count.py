"""BSS-1 — the statement producer surfaces `flagged_count`, so a gate can ask about it.

Static, no DB. The adapter is a thin wrapper; testing its behaviour would test
`statement_generation_service`. What is worth pinning is the CONTRACT between the
producer's output and the gate's question.

⚠️ THE GAP THIS CLOSES. `wf_sys_statement_run`'s approval gate asks "Review
flagged statements". The producer returned `statement_run_id`, `total_customers`,
`period_start`, `period_end` — **no flagged count**. So a `park_when` on that gate
had only the wrong number to gate on: `total_customers > 0` parks on a clean run
of forty unflagged statements, which is a worse answer than no predicate at all.
r165 therefore shipped the gate with a recorded `_no_park_when` and named this as
the upgrade path.

Nothing is computed here. `statement_generation_service` already counts flagged
statements and already uses the count to set `run.status` — the value existed and
simply was not surfaced across the adapter boundary.

⚠️ THIS DOES NOT ADD THE PREDICATE. Whether the gate should fire only on
exceptions is a separate ruling: the standing decision is that dispatching
statements to every charge-account customer is consequential and monthly, so a
human confirming it is not an empty question. This only makes the option
available and honest.
"""
from __future__ import annotations

import inspect

from app.services.workflows import invoice_statement_adapter


class TestTheProducerSurfacesWhatTheGateAsksAbout:
    def test_flagged_count_is_in_the_return(self):
        """Asserted against the SOURCE rather than by calling it, because calling
        it would require a seeded StatementRun and would be testing the
        generation service, not this contract."""
        src = inspect.getsource(invoice_statement_adapter.run_statement_run)
        assert '"flagged_count": run.flagged_count' in src, (
            "the gate asks about flagged statements; without this the only "
            "number available to a park_when is total_customers, which is the "
            "wrong question"
        )

    def test_the_underlying_field_actually_exists(self):
        """The value is read off the model, so a rename there would silently
        break the contract this test exists to hold."""
        from app.models.statement import StatementRun

        assert hasattr(StatementRun, "flagged_count")
        assert hasattr(StatementRun, "status")

    def test_the_service_still_populates_it(self):
        """DERIVED FROM THE SERVICE SOURCE. If generation stops setting
        `flagged_count`, the adapter would faithfully surface a value that is
        always zero — and a gate keyed on it would silently never park, which is
        the silent-wrong-answer class this arc has spent itself removing."""
        import pathlib

        from app.services import statement_generation_service

        src = pathlib.Path(statement_generation_service.__file__).read_text()
        assert "run.flagged_count = flagged_count" in src, (
            "the generation service no longer sets run.flagged_count — anything "
            "gating on it now reads a constant"
        )

    def test_the_existing_keys_are_not_disturbed(self):
        """`statement_run_id` and `total_customers` are the pre-existing
        contract; a downstream step or a later `park_when` may reference either,
        and this change is additive by intent."""
        src = inspect.getsource(invoice_statement_adapter.run_statement_run)
        for key in ('"statement_run_id"', '"total_customers"',
                    '"period_start"', '"period_end"'):
            assert key in src, f"{key} was dropped from the producer's output"


class TestTheGateRulingIsUnchanged:
    """Pinned because the obvious next move is to add the predicate, and that is
    a decision rather than a consequence."""

    def test_no_park_when_was_added_to_the_statement_gate(self):
        from app.data.default_workflows import ALL_DEFAULT_WORKFLOWS

        wf = next(w for w in ALL_DEFAULT_WORKFLOWS if w["id"] == "wf_sys_statement_run")
        gate = next(s for s in wf["steps"] if s["step_key"] == "approval_gate")
        assert "park_when" not in gate["config"], (
            "a park_when appeared on the statement gate. Surfacing flagged_count "
            "makes that option AVAILABLE, not decided — the standing ruling is "
            "that dispatching statements to every charge-account customer is "
            "consequential and monthly, so the gate asks a real question even on "
            "a clean run. Reversing that is a ruling, not a follow-through."
        )
