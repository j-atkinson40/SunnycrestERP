"""MAP-5 — the six... seven states, and the two orderings that carry the design.

Pure classifier tests. The query is one `DISTINCT ON` and is exercised against
production during the build; what needs pinning here is the CLASSIFICATION, since
the whole feature is the distinction between "ran" and "did something".

⚠️ THE STATE THE DESIGN IS TESTED ON IS `runs_dry`. The question it has to pass:
*would this copy have stopped the "green" report?* On 2026-08-12 two Plaid runs
recorded `completed` with `ingested=42`, and were read as a working feed. They
were dry runs; `bank_transactions` had not gained a row since 08-10. The copy
must make "ran" and "wrote nothing" separable at a glance, or it reproduces the
mistake it exists to prevent — a mistake made from BETTER data than a card shows.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.maps_of_content import liveness as L

_NOW = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)
_SIX_HOURS_AGO = _NOW - timedelta(hours=6)


def _classify(**kw):
    base = dict(
        workflow_known=True, has_tenant_ledger=True,
        last_status="completed", last_run_at=_SIX_HOURS_AGO,
        now=_NOW, fires_live=True,
    )
    base.update(kw)
    return L.classify(**base)


class TestRunsDryIsTheDesignsTest:
    def test_a_completed_dry_run_is_not_ran_and_closed(self):
        """⚠️ ORDER IS LOAD-BEARING. The dry check OUTRANKS run status, because
        a dry run that recorded `completed` is still a preview. Ranking status
        first renders "Ran 6 hours ago" over a run that changed nothing."""
        r = _classify(fires_live=False, last_status="completed")
        assert r.state == L.RUNS_DRY

    def test_the_copy_denies_the_write_in_the_same_line_as_the_run(self):
        """The specific failure it must prevent: reading `completed` plus a
        nonzero ingested count as a working feed."""
        label = _classify(fires_live=False).label.lower()
        assert "preview" in label
        assert "nothing was saved" in label

    def test_the_copy_avoids_admin_vocabulary(self):
        """"Writes nothing until promoted" was rejected — accurate, but
        `promoted` names a control a tenant operator cannot see. Correct and
        unhelpful is still a copy failure."""
        assert "promot" not in _classify(fires_live=False).label.lower()


class TestTheBrokenReferenceCannotReadAsNeverRun:
    """⚠️ THE SEVENTH STATE, ADDED BECAUSE THE BUILD PRODUCED THE BUG.

    Verifying this module I passed a guessed workflow id that does not exist.
    The query returned no row and the classifier said "Scheduled, but hasn't run
    yet" about a job that runs twice daily — a missing lookup producing a
    CONFIDENT FALSE CLAIM. That is silence-versus-zero inside the feature built
    to fix silence-versus-zero.
    """

    def test_an_unknown_workflow_is_not_never_run(self):
        r = _classify(workflow_known=False, last_run_at=None, last_status=None)
        assert r.state == L.UNKNOWN_JOB
        assert r.state != L.NEVER_RUN

    def test_it_outranks_every_other_state(self):
        """A dangling member must not be described by ANY fact about rhythm —
        including `runs_dry` or `not_reportable`, which would both read as
        statements about a job that exists."""
        for kw in (
            dict(fires_live=False),
            dict(has_tenant_ledger=False),
            dict(last_status="failed"),
            dict(last_run_at=None, last_status=None),
        ):
            assert _classify(workflow_known=False, **kw).state == L.UNKNOWN_JOB

    def test_the_copy_admits_the_gap_rather_than_asserting(self):
        assert "can't find" in _classify(workflow_known=False).label.lower()


class TestTheCopyDisciplines:
    def test_never_run_is_present_tense_not_an_accusation(self):
        """"Has never run" reads as a fault on a job nobody triggered.
        "Hasn't run yet" is the same information without the blame — the
        deliberately-unmapped discipline."""
        label = _classify(last_run_at=None, last_status=None).label
        assert "hasn't run yet" in label.lower()
        assert "never" not in label.lower()

    def test_not_reportable_states_its_boundary(self):
        """Ten members with liveness and two blank reads as a broken feature;
        naming the boundary makes it a scope limit."""
        label = _classify(has_tenant_ledger=False).label.lower()
        assert "ledger" in label and "can't say" in label

    def test_a_failure_says_didnt_finish_not_failed(self):
        """A run halted on an unimplemented step is not the accountant's fault
        and often not theirs to act on. An alarming word on a surface that
        renders daily teaches people to ignore it."""
        label = _classify(last_status="failed").label.lower()
        assert "didn't finish" in label
        assert "fail" not in label

    def test_a_parked_run_says_who_it_is_waiting_on(self):
        assert "waiting on you" in _classify(last_status="awaiting_input").label.lower()

    def test_a_clean_run_says_only_when(self):
        """The state that should read exactly as the card does today — no extra
        clause, because nothing needs explaining."""
        assert _classify().label == "Ran 6 hours ago"


class TestRecencyIsCoarse:
    @pytest.mark.parametrize("delta,expected", [
        (timedelta(minutes=2), "just now"),
        (timedelta(minutes=30), "30 minutes ago"),
        (timedelta(hours=1), "an hour ago"),
        (timedelta(hours=9), "9 hours ago"),
        (timedelta(days=1), "yesterday"),
        (timedelta(days=5), "5 days ago"),
        (timedelta(days=90), "over a month ago"),
    ])
    def test_phrasing(self, delta, expected):
        """Coarse on purpose: minute-precision invites reading a teaching
        surface as a monitor, and a card that looks like a monitor gets trusted
        like one."""
        assert _classify(last_run_at=_NOW - delta).label.endswith(expected)


class TestEveryStateIsDeclared:
    def test_the_constant_matches_what_classify_can_return(self):
        """A state returned but not declared cannot be styled, filtered, or
        drift-checked — it would render as an unrecognised string."""
        produced = {
            _classify(workflow_known=False).state,
            _classify(has_tenant_ledger=False).state,
            _classify(last_run_at=None, last_status=None).state,
            _classify(fires_live=False).state,
            _classify(last_status="awaiting_input").state,
            _classify(last_status="failed").state,
            _classify().state,
        }
        assert produced == set(L.LIVENESS_STATES)
