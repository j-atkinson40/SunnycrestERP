"""BSS-2 D-4 — send_statements dispatches, and the column pair is reconciled.

Static, no DB.

⚠️ WHAT THIS CLOSES. `send_statements` carried `_deliberately_broken` since r165
on a claim that was FALSE: bulk dispatch existed as
`statement_service.send_all_digital` with three live callers. It was unreachable
from a workflow, and filtered to zero rows by a column mismatch between two
statement subsystems sharing one table.

    D-1  reconciled the vocabulary   (established: digital / ready)
    D-2  wired the zero-caller renderer so the email carries a statement
    D-3  made the ledger survive a failure
    D-4  pointed the step at the dispatch

⚠️ THE COHORT AXIS DELIBERATELY GOES THE OTHER WAY. Everything else adopts the
established side; the cohort keeps the newcomer's `receives_monthly_statement`,
because that is the only one of the four columns anyone curated — 11 True / 11
False against a `false` default, versus `receives_statements` at all-default
True. Switching would silently double the cohort from 11 to 22.
"""
from __future__ import annotations

import inspect

import pytest

from app.data.default_workflows import ALL_DEFAULT_WORKFLOWS
from app.services.workflow_engine import _SERVICE_METHOD_REGISTRY


def _send_step() -> dict:
    wf = next(w for w in ALL_DEFAULT_WORKFLOWS if w["id"] == "wf_sys_statement_run")
    return next(s for s in wf["steps"] if s["step_key"] == "send_statements")


class TestTheStepDispatches:
    def test_it_is_no_longer_broken(self):
        cfg = _send_step()["config"]
        assert cfg.get("action_type") == "call_service_method"
        assert "_deliberately_broken" not in cfg

    def test_the_method_is_registered(self):
        assert _send_step()["config"]["method_name"] in _SERVICE_METHOD_REGISTRY

    def test_the_kwargs_are_within_the_registry_safelist(self):
        cfg = _send_step()["config"]
        allowed = set(_SERVICE_METHOD_REGISTRY[cfg["method_name"]][1])
        assert set(cfg.get("kwargs", {})) <= allowed

    def test_the_run_id_binds_to_the_producers_output(self):
        """THE CONTRACT BETWEEN THE TWO STEPS. If the producer's output key is
        renamed, this template resolves to literal text and the adapter raises —
        loudly, by design, rather than dispatching nothing."""
        kwargs = _send_step()["config"]["kwargs"]
        assert kwargs["statement_run_id"] == (
            "{output.generate_statements.statement_run_id}"
        )

    def test_the_producer_actually_emits_that_key(self):
        """Derived from the producer rather than assumed — the two halves of the
        contract are in different files and nothing else checks they agree."""
        from app.services.workflows import invoice_statement_adapter

        src = inspect.getsource(invoice_statement_adapter.run_statement_run)
        assert '"statement_run_id"' in src

    def test_a_missing_run_id_raises_rather_than_dispatching_nothing(self):
        """A misbound template is a configuration error, not an empty run. It
        must not look like a successful dispatch of zero statements."""
        from app.services.workflows.invoice_statement_adapter import (
            run_statement_dispatch,
        )

        with pytest.raises(ValueError, match="statement_run_id"):
            run_statement_dispatch(None, company_id="c", statement_run_id=None)


class TestTheColumnReconciliation:
    def test_the_producer_writes_the_established_vocabulary(self):
        """`send_all_digital` selects delivery_method == "digital" AND status ==
        "ready". The producer wrote "email"/"pending" — either predicate alone
        matched zero rows, so nothing it generated was ever sendable."""
        from app.services import statement_generation_service

        src = inspect.getsource(statement_generation_service)
        assert 'delivery_method=customer.statement_delivery_method or "digital"' in src
        assert 'status="ready"' in src

    def test_the_old_vocabulary_is_gone(self):
        """⚠️ COMMENTS STRIPPED BEFORE MATCHING. The replacement comment QUOTES
        the old vocabulary in order to explain why it was replaced, so matching
        raw source finds it and reports a fix that landed as a fix that
        didn't. Fourth occurrence of that in one session — see `tests/_source`."""
        from app.services import statement_generation_service

        from tests._source import code_only

        src = code_only(inspect.getsource(statement_generation_service))
        assert 'preferred_delivery_method or "email"' not in src
        assert 'status="pending"' not in src

    def test_the_cohort_selector_is_unchanged(self):
        """⚠️ THE AXIS THAT GOES THE OTHER WAY. Switching this to the
        established side would silently double the cohort from 11 to 22 —
        invisible until a customer receives a statement they should never have
        been sent.

        Comments stripped: the docstring explaining this decision names
        `receives_statements` as the column NOT chosen."""
        from app.services import statement_generation_service

        from tests._source import code_only

        src = code_only(
            inspect.getsource(statement_generation_service.get_eligible_customers)
        )
        assert "receives_monthly_statement" in src
        assert "receives_statements" not in src.replace(
            "receives_monthly_statement", ""
        ), "the cohort switched to the uncurated column"


class TestThePreservedRetraction:
    def test_the_false_claims_travel_with_their_resolution(self):
        note = _send_step()["config"]["_was_recorded_as"]
        assert "FALSE" in note["r165_claimed"]
        assert "FALSE" in note["r165_also_claimed"]
        assert "resolved_by" in note

    def test_the_params_status_is_honest(self):
        """⚠️ NONE of the three declared params is honoured, and one cannot be.
        `include_zero_balance` filters at GENERATION, so a param on the SEND
        step cannot include what generation already excluded. Recorded rather
        than quietly left looking supported."""
        status = _send_step()["config"]["_params_status"]
        assert status["honoured"] == []
        assert set(status["supported_but_unwired"]) == {"from_name", "reply_to"}
        assert status["on_the_wrong_step"] == ["include_zero_balance"]


class TestTheRatchetProtectsThisChange:
    def test_doing_d4_as_a_migration_would_be_caught(self):
        """The durable version lives in `default_workflows.py`; a migration would
        be reverted by the seeder within a deploy, as r165 was. Verified rather
        than assumed — the ratchet was built this morning and its detector
        needed correcting once already."""
        from tests.test_workflow_definition_ownership_ratchet import (
            _WRITES_STEP_CONFIG,
            _normalise,
        )

        attempt = (
            '"""Wire send_statements."""\n'
            "def upgrade():\n"
            "    conn.execute(sa.text(\n"
            '        "UPDATE workflow_steps "\n'
            '        "SET config = CAST(:c AS jsonb) "\n'
            '        "WHERE step_key = :k"\n'
            "    ))\n"
        )
        assert _WRITES_STEP_CONFIG.search(_normalise(attempt)), (
            "the ratchet would not catch D-4 written as a migration"
        )
