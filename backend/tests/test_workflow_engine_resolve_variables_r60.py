"""Phase R-6.0a — workflow_engine.resolve_variables prefix extension tests.

Covers the four new prefix branches added in R-6.0a + the
``previous_step_key`` threading. The four prefixes:

  * ``incoming_email.<path>``
  * ``incoming_transcription.<path>``
  * ``vault_item.<path>``
  * ``workflow_input.<path>`` (alias resolving against the previous
    step's output_data — passed in via ``previous_step_key``)

These prefixes power R-6.0 trigger-driven workflows + the canonical
chained-step pattern (``invoke_generation_focus`` →
``invoke_review_focus``). resolve_variables stays a pure function;
no DB access; tests live as plain unit tests against the function.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import workflow_engine


def _mk_run(trigger_context: dict | None = None, input_data: dict | None = None):
    """A minimal stand-in for WorkflowRun. resolve_variables only
    reads .trigger_context and .input_data — so a SimpleNamespace
    suffices for unit-level coverage of the resolver itself."""
    return SimpleNamespace(
        trigger_context=trigger_context, input_data=input_data
    )


# ── incoming_email prefix ───────────────────────────────────────────


class TestIncomingEmailPrefix:
    """Phase R-6.0a — `{incoming_email.X}` walks
    `run.trigger_context["incoming_email"]`."""

    def test_subject_field_resolves(self):
        run = _mk_run(
            trigger_context={
                "incoming_email": {
                    "subject": "RE: Decedent info",
                    "body": "John Smith, DOD 2026-04-30",
                }
            }
        )
        out = workflow_engine.resolve_variables("{incoming_email.subject}", run, {})
        assert out == "RE: Decedent info"

    def test_nested_path(self):
        run = _mk_run(
            trigger_context={
                "incoming_email": {
                    "from": {"email": "fh@example.com", "name": "Hopkins FH"}
                }
            }
        )
        out = workflow_engine.resolve_variables(
            "{incoming_email.from.email}", run, {}
        )
        assert out == "fh@example.com"

    def test_missing_returns_none(self):
        run = _mk_run(trigger_context={})
        out = workflow_engine.resolve_variables(
            "{incoming_email.subject}", run, {}
        )
        assert out is None


# ── incoming_transcription prefix ───────────────────────────────────


class TestIncomingTranscriptionPrefix:
    """Phase R-6.0a — `{incoming_transcription.X}` walks
    `run.trigger_context["incoming_transcription"]`."""

    def test_text_resolves(self):
        run = _mk_run(
            trigger_context={
                "incoming_transcription": {
                    "text": "Hi, this is Hopkins FH calling about John Smith.",
                    "call_id": "rc-call-7891",
                }
            }
        )
        out = workflow_engine.resolve_variables(
            "{incoming_transcription.text}", run, {}
        )
        assert out.startswith("Hi, this is Hopkins FH")

    def test_call_id_inline_substitute(self):
        run = _mk_run(
            trigger_context={
                "incoming_transcription": {"call_id": "rc-call-7891"}
            }
        )
        out = workflow_engine.resolve_variables(
            "Call ID: {incoming_transcription.call_id}", run, {}
        )
        assert out == "Call ID: rc-call-7891"


# ── vault_item prefix ───────────────────────────────────────────────


class TestVaultItemPrefix:
    """Phase R-6.0a — `{vault_item.X}` walks
    `run.trigger_context["vault_item"]`."""

    def test_vault_item_id_resolves(self):
        run = _mk_run(
            trigger_context={
                "vault_item": {
                    "id": "vi-abc-123",
                    "item_type": "incoming_email",
                }
            }
        )
        out = workflow_engine.resolve_variables("{vault_item.id}", run, {})
        assert out == "vi-abc-123"

    def test_metadata_json_nested(self):
        run = _mk_run(
            trigger_context={
                "vault_item": {
                    "metadata_json": {"sender": "supplier@vendor.test"}
                }
            }
        )
        out = workflow_engine.resolve_variables(
            "{vault_item.metadata_json.sender}", run, {}
        )
        assert out == "supplier@vendor.test"


# ── workflow_input alias ────────────────────────────────────────────


class TestWorkflowInputAlias:
    """Phase R-6.0a — `{workflow_input.X}` resolves against the
    previous step's output_data (via the new previous_step_key
    keyword arg). Decouples downstream steps from explicit
    upstream step_key references."""

    def test_resolves_against_previous_step_output(self):
        step_outputs = {
            "extract_data": {
                "line_items": [
                    {"field_key": "deceased_name", "value": "John Smith"}
                ]
            }
        }
        out = workflow_engine.resolve_variables(
            "{workflow_input.line_items}",
            run=_mk_run(),
            step_outputs=step_outputs,
            previous_step_key="extract_data",
        )
        assert isinstance(out, list)
        assert out[0]["value"] == "John Smith"

    def test_returns_none_when_previous_step_key_is_none(self):
        out = workflow_engine.resolve_variables(
            "{workflow_input.line_items}",
            run=_mk_run(),
            step_outputs={"extract_data": {"line_items": []}},
            previous_step_key=None,
        )
        assert out is None

    def test_returns_none_when_previous_step_output_missing(self):
        out = workflow_engine.resolve_variables(
            "{workflow_input.foo}",
            run=_mk_run(),
            step_outputs={},
            previous_step_key="extract_data",
        )
        assert out is None

    def test_dict_recursion_threads_previous_step_key(self):
        """The recursive dict path must thread previous_step_key
        through to nested resolve_variables calls."""
        step_outputs = {"prior": {"line_items": [{"x": 1}]}}
        template = {
            "kwargs": {"items": "{workflow_input.line_items}"},
        }
        out = workflow_engine.resolve_variables(
            template,
            run=_mk_run(),
            step_outputs=step_outputs,
            previous_step_key="prior",
        )
        assert out == {"kwargs": {"items": [{"x": 1}]}}
