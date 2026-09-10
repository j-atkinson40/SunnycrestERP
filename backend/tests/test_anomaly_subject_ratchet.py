"""Anomaly-subject arc, phase 1 — the ratchet, and item 5's contract fix.

⚠️ WHY THIS IS A RATCHET AND NOT A REQUIRED PARAMETER, YET.

The arc's ruling is shape 2: make `entity_type`/`entity_id` required on the
anomaly write path, so a subjectless anomaly becomes unexpressible rather than
discouraged. That is still the destination. It cannot be the first step.

Measured: a required parameter fails at CALL time with `TypeError`, not at
import and not at parse. 34 of 64 call sites currently pass neither argument.
Making them required today would leave twelve scheduled production agents —
including `month_end_close`, `ar_collections`, `cash_receipts` and
`expense_categorization` — raising `TypeError` at their next run, against a live
tenant's books.

So the removal happens LAST, after phases 2 and 3 fill the subjects in. This
ratchet holds the direction in the meantime: **the non-compliant count may only
shrink.** It is a mechanically enforced guard rather than a convention someone
must remember, which is the most the criterion permits while callers still exist.

⚠️ THE COUNT BELOW IS A CEILING THAT MOVES ONE WAY. Lower it as sites are fixed.
Raising it is the failure this file exists to prevent, and the assertion says so.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

_AGENTS = Path(__file__).resolve().parents[1] / "app" / "services" / "agents"

#: Measured 2026-09-04 at phase 1: **64 call sites, 30 pass a subject, 34 do not.**
#: This is the number phases 2 and 3 drive to zero.
#:
#: ⚠️ CORRECTING 75/30/45, WHICH WAS WRONG AND WHICH I PROPAGATED. The audit that
#: produced those figures counted with `grep '_make_anomaly(\|add_anomaly('`,
#: which matched the ELEVEN `def _make_anomaly(` lines as though they were call
#: sites. 75 = 64 calls + 11 definitions; 45 = 34 + the same 11. The error
#: travelled from the audit into the arc scope and into the operator's ruling.
#: `test_call_sites_are_actually_found` caught it — a positive control written
#: against the wrong number found the number wrong.
#:
#: LOWERED 34 -> 2 at phases 2-3 (2026-09-04). The 32 filled sites each answered
#: the rule from DECISIONS 2026-09-04: the subject is what the END TRANSITION
#: acts on. The 2 that remain are the sites where NOTHING THE OPERATOR CAN DO
#: makes the condition go away, so there is no transition and therefore no
#: subject — see the Type B batch in
#: `docs/investigations/2026-09-04-anomaly-subject-phase23.md`.
#:
#: ⚠️ DO NOT DRIVE THIS TO ZERO BY INVENTING SUBJECTS FOR THE LAST TWO. They are
#: held open deliberately. The arc's own STOP line says inventing a subject is
#: worse than stopping, and a fabricated subject here would key two permanent
#: notices as if they were resolvable decisions.
MAX_SITES_WITHOUT_SUBJECT = 2

#: Proximity window for the subject check. Stated rather than hidden: a call
#: passing `entity_id` on the ninth line reads as non-compliant here. That makes
#: the count a conservative over-estimate of the defect, which is the right
#: direction for a ratchet — it can only accuse, never excuse.
_WINDOW = 8


def _call_sites() -> list[tuple[str, int, bool]]:
    """Every anomaly write site. Returns (file, line, passes_subject)."""
    out: list[tuple[str, int, bool]] = []
    for f in sorted(_AGENTS.glob("*.py")):
        lines = f.read_text().split("\n")
        for i, line in enumerate(lines):
            if re.search(r"(self\._make_anomaly\(|self\.add_anomaly\()", line):
                window = "\n".join(lines[i : i + _WINDOW])
                out.append((f.name, i + 1, "entity_id=" in window))
    return out


def test_the_ratchet_may_only_shrink():
    """⚠️ THE RATCHET. Lower MAX_SITES_WITHOUT_SUBJECT as phases 2-3 land."""
    sites = _call_sites()
    without = [s for s in sites if not s[2]]
    assert len(without) <= MAX_SITES_WITHOUT_SUBJECT, (
        f"{len(without)} anomaly write sites pass no subject, above the ceiling "
        f"of {MAX_SITES_WITHOUT_SUBJECT}. A new subjectless write site was added. "
        "The arc's destination is that this is impossible; until the parameter "
        "can be made required, this ceiling is what holds the direction."
    )


def test_the_ceiling_is_not_stale():
    """POSITIVE CONTROL FOR THE RATCHET ITSELF.

    A ceiling far above the real count never rejects anything and is
    indistinguishable from an unwired check. This asserts the ceiling is still
    tight — if phases 2-3 fixed sites without lowering it, this fails and says so.
    """
    without = [s for s in _call_sites() if not s[2]]
    assert len(without) == MAX_SITES_WITHOUT_SUBJECT, (
        f"{len(without)} sites lack a subject but the ceiling is "
        f"{MAX_SITES_WITHOUT_SUBJECT}. If sites were fixed, lower the ceiling — "
        "a ceiling above the real count is a ratchet that has stopped ratcheting."
    )


def test_call_sites_are_actually_found():
    """POSITIVE CONTROL FOR THE SCANNER. A scanner that finds nothing satisfies
    the ratchet trivially — 0 <= 45. This is the absent-signal check: prove the
    instrument can see before trusting what it reports."""
    sites = _call_sites()
    assert len(sites) >= 60, (
        f"the scanner found only {len(sites)} call sites; it found 64 at phase 1. "
        "A scanner that stops matching makes the ratchet pass by seeing nothing."
    )
    assert any(s[2] for s in sites), "no compliant site found — scanner is broken"
    assert any(not s[2] for s in sites), "no non-compliant site found — scanner is broken"


# ── The consolidation, pinned ────────────────────────────────────────


def test_make_anomaly_is_defined_exactly_once():
    """Eleven byte-identical copies were consolidated onto BaseAgent in phase 1.
    Eleven copies are eleven places a future author can diverge, and eleven
    places the arc's eventual signature change would have to land identically."""
    defs = [
        (f.name, i + 1)
        for f in sorted(_AGENTS.glob("*.py"))
        for i, line in enumerate(f.read_text().split("\n"))
        if re.match(r"\s*def _make_anomaly\(", line)
    ]
    assert len(defs) == 1, f"_make_anomaly is defined {len(defs)} times: {defs}"
    assert defs[0][0] == "base_agent.py", f"it should live on BaseAgent, found in {defs[0][0]}"


def test_every_agent_can_still_reach_the_helper():
    """Consolidation is only safe if every agent inherits it. Asserted rather
    than assumed — the eleven copies were deleted on the strength of this."""
    from app.services.agents.agent_runner import AgentRunner

    AgentRunner._ensure_registry()
    assert AgentRunner.AGENT_REGISTRY, "registry did not seed"
    for job_type, cls in AgentRunner.AGENT_REGISTRY.items():
        assert hasattr(cls, "_make_anomaly"), f"{cls.__name__} lost _make_anomaly"
        assert hasattr(cls, "add_anomaly"), f"{cls.__name__} lost add_anomaly"


# ── Item 5 — broken is distinguishable from quiet ────────────────────


def test_a_fragment_whose_instances_all_reject_logs_an_error(caplog):
    """⚠️ ITEM 5. A fragment yielding nothing is having a quiet day. A fragment
    yielding instances that ALL fail validation is broken. Both produce an empty
    note, and before this fix both produced the same log."""
    import logging

    from app.services.fragments import (
        Audience,
        FragmentDeclaration,
        FragmentInstance,
        FragmentPayload,
        register_fragment,
        reset_registry,
    )
    from app.services.fragments.emission import emit_for_user

    reset_registry()
    try:
        register_fragment(
            FragmentDeclaration(
                fragment_id="all_reject",
                label="All reject",
                kind="non_prompt",
                audience=Audience.any_authenticated(),
                # Every instance carries an empty subject -> all rejected.
                condition=lambda db, *, user: [
                    FragmentInstance(
                        subject_id="",
                        payload=FragmentPayload(title="T", synthesized_text="x"),
                        predicate={"a": 1},
                        condition_inputs={},
                    )
                ],
                target_surface="peek",
                target_key="t",
                subject_kind="invoice",
            )
        )
        with caplog.at_level(logging.ERROR):
            out = emit_for_user(None, user=None, fragment_ids=["all_reject"])
        assert out == []
        assert any(
            "ALL were rejected" in r.message or "ALL were rejected" in r.getMessage()
            for r in caplog.records
        ), "a fragment that emitted nothing but produced instances must log ERROR"
    finally:
        reset_registry()


def test_a_genuinely_quiet_fragment_logs_no_error(caplog):
    """POSITIVE CONTROL FOR ITEM 5, and the half that makes it meaningful.

    If a quiet fragment also logged ERROR, the log would be noise and the
    distinction would be lost again — the same failure in a new place. A quiet
    day must stay quiet.
    """
    import logging

    from app.services.fragments import (
        Audience,
        FragmentDeclaration,
        register_fragment,
        reset_registry,
    )
    from app.services.fragments.emission import emit_for_user

    reset_registry()
    try:
        register_fragment(
            FragmentDeclaration(
                fragment_id="quiet",
                label="Quiet",
                kind="non_prompt",
                audience=Audience.any_authenticated(),
                condition=lambda db, *, user: [],  # legitimately false
                target_surface="peek",
                target_key="t",
                subject_kind="invoice",
            )
        )
        with caplog.at_level(logging.ERROR):
            out = emit_for_user(None, user=None, fragment_ids=["quiet"])
        assert out == []
        assert not [r for r in caplog.records if r.levelno >= logging.ERROR], (
            "a quiet day must not log an error, or the distinction is noise again"
        )
    finally:
        reset_registry()


# ── The period-subject helper, and the null period that nearly shipped a raise ──


class _PeriodSubjectStub:
    """Exercises the real BaseAgent methods without a DB. The helpers read only
    `self.job` and `self.tenant_id`, so binding them onto a stub tests the
    shipped code rather than a copy of it."""

    from app.services.agents.base_agent import BaseAgent as _B

    _period_subject_id = _B._period_subject_id
    _period_subject_kind = _B._period_subject_kind

    def __init__(self, period_start, period_end):
        self.tenant_id = "tenant-abc"
        self.job = SimpleNamespace(
            id="job-1", job_type="month_end_close",
            period_start=period_start, period_end=period_end,
        )


def test_a_period_scoped_subject_uses_the_period():
    s = _PeriodSubjectStub(date(2026, 8, 1), date(2026, 8, 31))
    assert s._period_subject_kind() == "accounting_period"
    assert s._period_subject_id() == "2026-08-01:2026-08-31"


def test_a_job_with_no_period_does_not_raise():
    """⚠️ REGRESSION. The first version of `_period_subject_id` RAISED on a null
    period, reasoning that AgentRunner requires both dates so it could only fire
    on a job from another path. That was true, and the other path is the common
    one: measured against production 2026-09-04, the only month_end_close job
    that has ever run there carries a null period, 1 of 172 cash_receipts jobs
    does, and four job types are 100% null. The raise would have aborted the
    step at its next run — removal before the callers comply, inside the fix for
    exactly that mistake."""
    s = _PeriodSubjectStub(None, None)
    assert s._period_subject_kind() == "tenant_books"
    assert s._period_subject_id() == "tenant-abc"

    half = _PeriodSubjectStub(date(2026, 8, 1), None)
    assert half._period_subject_kind() == "tenant_books"
    assert half._period_subject_id() == "tenant-abc"


def test_the_unbounded_fallback_is_not_run_scoped():
    """POSITIVE CONTROL, and the half that makes the fallback worth having.

    A fallback that varied per run would satisfy the no-raise test above while
    reintroducing the defect the whole arc exists to remove — a fresh subject
    every run, so nothing ever supersedes. Two distinct jobs must agree."""
    a = _PeriodSubjectStub(None, None)
    b = _PeriodSubjectStub(None, None)
    b.job.id = "job-2"
    assert a._period_subject_id() == b._period_subject_id()
    assert "job-1" not in a._period_subject_id()


def test_kind_and_id_cannot_disagree():
    """They are two calls, so they could drift. Both read the same two fields;
    this pins that an `accounting_period` kind never carries a tenant id."""
    for ps, pe in ((date(2026, 1, 1), date(2026, 3, 31)), (None, None), (None, date(2026, 3, 31))):
        s = _PeriodSubjectStub(ps, pe)
        if s._period_subject_kind() == "accounting_period":
            assert ":" in s._period_subject_id() and s._period_subject_id() != s.tenant_id
        else:
            assert s._period_subject_id() == s.tenant_id


#: The two anomaly types held without subjects, BY NAME. Neither has an operator
#: act, so neither has an end transition, so neither has a subject.
#:
#: ⚠️ Operator ruling 2026-09-04: `agent_anomalies` is the wrong container for
#: both — an anomaly is a finding about the tenant's DATA, and these are about
#: Bridgeable's roadmap and a method's precision. The ruling was explicitly NOT
#: to build a container for two rows. A THIRD INSTANCE DECIDES THE SHAPE.
SUBJECTLESS_BY_RULING = {
    "tax_estimate_rough",           # clears when the quarter fills up
    "w9_tracking_not_implemented",  # clears when Bridgeable ships the feature
}


def test_the_subjectless_sites_are_the_two_that_were_ruled_on():
    """⚠️ THIS IS THE 'THEY CANNOT GROW' GUARD, and it is why the count ratchet
    is not enough on its own.

    `MAX_SITES_WITHOUT_SUBJECT` counts. It would stay satisfied if one held site
    were fixed and a different subjectless site added — same total, different
    population, and the swap invisible. Pinning the NAMES means a third
    subjectless anomaly cannot arrive quietly: it has to edit this set, which is
    the conversation the ruling asked a third instance to trigger.

    Two rows is a note in a comment. Two thousand is `expense_no_gl_mapping`
    again, which is the whole reason this arc exists.
    """
    found = set()
    for f in sorted(_AGENTS.glob("*.py")):
        lines = f.read_text().split("\n")
        for i, line in enumerate(lines):
            if not re.search(r"(self\._make_anomaly\(|self\.add_anomaly\()", line):
                continue
            window = "\n".join(lines[i : i + _WINDOW])
            if "entity_id=" in window:
                continue
            m = re.search(r'anomaly_type=f?"([a-z0-9_{}]+)"', window)
            assert m, f"{f.name}:{i+1} has no subject AND no readable type"
            found.add(m.group(1))

    assert found == SUBJECTLESS_BY_RULING, (
        f"the set of subjectless anomaly types is {sorted(found)}, but the ruling "
        f"covers {sorted(SUBJECTLESS_BY_RULING)}. A new subjectless type is a "
        "decision, not an oversight — either give it a subject, or bring the "
        "third instance to the container question the ruling deferred."
    )
