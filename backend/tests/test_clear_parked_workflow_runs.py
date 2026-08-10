"""WE-1 A-3 — the disposition table is coherent. Static, no DB.

The script's SQL is simple; what is worth pinning is the DISPOSITION — which
groups clear, which are left, and that each carries its own reason. A uniform
rule would be wrong four different ways at once, and the way that regresses is
someone adding a group without a reason or moving one between lists.
"""
from __future__ import annotations

from datetime import date

from scripts.clear_parked_workflow_runs import _CLEAR, _LEAVE, _SEED_DATE


class TestDispositionTable:
    def test_every_cleared_group_states_why(self):
        """A destructive action without a stated reason is the shape this whole
        arc has been correcting."""
        for name, _extra, why in _CLEAR:
            assert why and len(why) > 20, f"{name} clears without an explanation"

    def test_every_left_group_states_why(self):
        """Exclusions need reasons MORE than inclusions do — an unexplained
        exclusion reads as an oversight and invites someone to 'tidy' it."""
        for name, why in _LEAVE:
            assert why and len(why) > 20, f"{name} is excluded without a reason"

    def test_no_group_is_both_cleared_and_left(self):
        cleared = {n for n, _e, _w in _CLEAR}
        left = {n.split(" (")[0] for n, _w in _LEAVE}
        # Expense Categorization appears in both BY DESIGN — split on the seed
        # date — so the guard is that the split is expressed as a predicate
        # rather than the same unqualified name landing in both lists.
        for name in cleared & left:
            extra = next(e for n, e, _w in _CLEAR if n == name)
            assert extra.strip(), (
                f"{name} is in both lists with no predicate separating them — "
                f"one of the two would silently win"
            )

    def test_the_seed_split_is_dated_not_guessed(self):
        """The DEMO-2 boundary is a specific date, not 'recent'. A relative
        window would move under the script and change what it deletes."""
        assert isinstance(_SEED_DATE, date)
        assert _SEED_DATE == date(2026, 8, 10)

    def test_ar_collections_reason_names_what_survives(self):
        """The safety claim has to be IN the reason, because the reason is what
        gets printed at the point of deletion. 'Cleared 127 AR Collections runs'
        without it reads as discarding collections work."""
        why = next(w for n, _e, w in _CLEAR if n == "AR Collections")
        assert "agent_anomalies" in why or "NOT touched" in why

    def test_first_call_intake_is_left_as_human_work(self):
        """The one group where 'parked' means a person stopped. Two rows, and
        the distinction is what makes the disposition honest rather than
        uniform — so it is pinned rather than left to a comment."""
        why = next(w for n, w in _LEAVE if n.startswith("First Call Intake"))
        assert "person" in why.lower() or "unfinished" in why.lower()
