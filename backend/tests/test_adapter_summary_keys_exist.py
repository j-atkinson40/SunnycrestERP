"""An adapter must not read a summary key the agent never writes. CR-1.

⚠️ THE WORST FORM OF THE WRONG-NAME FAMILY. This week produced twelve wrong-name
lookups. Eleven returned nothing — an empty result, a False, a crash. THIS ONE
RETURNED A PLAUSIBLE NUMBER:

    exec_summary.get("drafts_generated", 0)

`drafts_generated` appears in 0 of 40 real `ar_collections` report payloads;
`drafts_ready` appears in 40 of 40, non-zero on 3. The agent writes
`drafts_generated` into a STEP's data dict, never into `report_payload`. So the
`.get()` returned its default forever, and the default was a valid-looking zero.

⚠️ AND IT SURVIVED BEING MEASURED. r162 added `park_when: drafts_generated > 0`
to stop this gate parking on nothing 127 times, citing "A-3 measured
drafts_generated: 0 on every run across three months" as evidence. That zero
meant ABSENT and was read as meaning NONE — the exact distinction the arc exists
to draw. Against an always-zero key the gate could never park AT ALL, including
the three runs that genuinely had drafts. A noisy false positive became a silent
false negative.

A crash is a gift. A default is a disguise.
"""
from __future__ import annotations

import inspect
import re

import pytest

from tests._source import code_only

#: (adapter module, agent module) pairs whose summary keys must agree.
_PAIRS = [
    (
        "app.services.workflows.ar_collections_adapter",
        "app.services.agents.ar_collections_agent",
    ),
    (
        "app.services.workflows.expense_categorization_adapter",
        "app.services.agents.expense_categorization_agent",
    ),
]

#: Keys sourced from the AgentJob row rather than the payload — not summary reads.
_NOT_FROM_SUMMARY = {"anomaly_count", "status", "dry_run"}


def _summary_reads(module_name: str) -> set[str]:
    """Keys the adapter pulls out of a report payload.

    Comments stripped first: the fix's own explanation quotes the broken key, and
    matching raw source finds it — which is the comment-matching family that hit
    five times this week, including in the verification of this very fix.
    """
    mod = __import__(module_name, fromlist=["_"])
    src = code_only(inspect.getsource(mod))
    return {
        m.group(1)
        for m in re.finditer(r'(?:exec_summary|summary|payload)\.get\(\s*"([a-z_]+)"', src)
    } - _NOT_FROM_SUMMARY


def _agent_writes(module_name: str) -> set[str]:
    """Every string key the agent puts in a dict literal.

    DELIBERATELY OVER-BROAD. It collects keys from step dicts as well as the
    report payload, so it cannot prove a key reaches `report_payload` — only that
    the agent knows the NAME at all. A narrower check would need to trace which
    dict becomes the payload, which is exactly the reasoning that got this wrong
    the first time. Over-broad here means the test still catches a name the agent
    never uses, and never fires falsely on one it does.
    """
    mod = __import__(module_name, fromlist=["_"])
    src = code_only(inspect.getsource(mod))
    return {m.group(1) for m in re.finditer(r'"([a-z_]+)"\s*:', src)}


class TestAdaptersOnlyReadKeysTheAgentKnows:
    @pytest.mark.parametrize("adapter,agent", _PAIRS)
    def test_every_read_key_exists_in_the_agent(self, adapter, agent):
        reads = _summary_reads(adapter)
        assert reads, f"no summary reads found in {adapter} — the regex missed"
        unknown = sorted(reads - _agent_writes(agent))
        assert not unknown, (
            f"{adapter} reads {unknown} from the agent's summary, and "
            f"{agent} never writes that name. A .get() with a default returns a "
            f"plausible number for a key that does not exist — it will not "
            f"crash, and it will survive being measured."
        )

    def test_the_ar_gate_reads_the_key_the_adapter_emits(self):
        """The two halves of the contract live in different files and nothing
        else checks they agree — which is how the gate ended up pointed at a key
        that is always zero."""
        from app.data.default_workflows import ALL_DEFAULT_WORKFLOWS

        wf = next(w for w in ALL_DEFAULT_WORKFLOWS if w["id"] == "wf_sys_ar_collections")
        gate = next(s for s in wf["steps"] if s["step_key"] == "approval_gate")
        field = gate["config"]["park_when"]["field"]
        key = field.rstrip("}").rsplit(".", 1)[-1]
        assert key in _summary_reads(
            "app.services.workflows.ar_collections_adapter"
        ), f"the gate parks on {key!r}, which the adapter does not emit"

    def test_the_broken_key_is_gone(self):
        """Named explicitly so a revert is legible rather than looking like a
        refactor."""
        assert "drafts_generated" not in _summary_reads(
            "app.services.workflows.ar_collections_adapter"
        )
