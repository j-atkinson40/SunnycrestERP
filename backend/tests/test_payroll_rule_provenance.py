"""Per-key provenance on the rulebook — Payroll 4 Phase 3.

⚠️ **WHAT THIS BUYS, AND IT IS ONE THING.** Payroll 1 shipped ten constants.
Seven faithfully reproduced the accountant's workbook; three were open
questions with a default chosen so something would run. Nothing in the data
told them apart, so a reader seeing `sick_in_dues_hours = True` could not know
whether it was a decision or a placeholder — and the only record of which was
prose in a spec that the database never consults.

⚠️ **AND THE STATUS THAT MATTERS IS `disputed`.** It says the stored value is
in use because something had to be, not because anyone agreed. One key is
disputed right now: the `vacation_bonus` tiers, where the dispatch's figures
and a year of real registers do not agree.
"""
from __future__ import annotations

import pytest

from app.services.payroll.rules import (
    RULE_FIELDS,
    RULE_STATUSES,
    DEFAULT_RULES,
    rule_provenance,
)


def test_a_status_must_be_one_of_the_four():
    for status in RULE_STATUSES:
        assert rule_provenance(status, "a real source here")["status"] == status
    with pytest.raises(ValueError, match="status must be one of"):
        rule_provenance("probably", "a real source here")


def test_a_status_without_a_source_is_refused():
    """⚠️ The whole point of the column.

    `confirmed` with an empty source is indistinguishable from an assumption
    somebody felt confident about, which is the confusion this exists to
    remove. So the source is required and must be substantive.
    """
    for bad in ("", "   ", "ok", "James"):
        with pytest.raises(ValueError, match="source must say"):
            rule_provenance("confirmed", bad)


def test_the_source_is_stripped_but_kept_verbatim_otherwise():
    assert rule_provenance("confirmed", "  accountant 2026-11-03  ") == {
        "status": "confirmed", "source": "accountant 2026-11-03"}


def test_disputed_is_an_available_status():
    """A rulebook that cannot say "we disagree" forces a false choice.

    Without it, the only ways to record the vacation-bonus disagreement are to
    seed one side's figure as if it were settled, or to leave the key looking
    like every other assumption.
    """
    assert "disputed" in RULE_STATUSES
    assert rule_provenance("disputed", "the dispatch and the registers "
                                       "disagree about the two-week total")["status"] == "disputed"


# ── the seed script's rules, asserted without running it ─────────────────────

def test_the_seed_changes_only_keys_that_are_real_rules():
    """A seed naming a key that is not a rule would do nothing, silently."""
    from scripts.seed_payroll_rule_set_2026_11_09 import CHANGES, DISPUTED

    for key in list(CHANGES) + list(DISPUTED):
        assert key in RULE_FIELDS, f"{key} is not a rule field"


def test_the_seed_sets_sick_in_dues_hours_false_as_confirmed():
    """The accountant's answer of 2026-11-03, and it reverses the shipped default."""
    from scripts.seed_payroll_rule_set_2026_11_09 import CHANGES

    value, provenance = CHANGES["sick_in_dues_hours"]
    assert value is False
    assert provenance["status"] == "confirmed"
    assert "2026-11-03" in provenance["source"]
    # ⚠️ And it really is a reversal, or the seed is a no-op dressed as a change.
    assert DEFAULT_RULES.sick_in_dues_hours is True


def test_the_seed_sets_remittance_grouping_to_check_date():
    from scripts.seed_payroll_rule_set_2026_11_09 import CHANGES

    value, provenance = CHANGES["remittance_group_by"]
    assert value == "check_date"
    assert provenance["status"] == "confirmed"
    assert DEFAULT_RULES.remittance_group_by == "week_end_date", "not a reversal"


def test_the_seed_refuses_to_set_a_disputed_key():
    """⚠️ THE RULING, HELD IN CODE.

    *"If the current set's values disagree with the Phase 3 list, stop and show
    me before seeding."* `vacation_bonus` disagrees, so it must appear in
    DISPUTED and must NOT appear in CHANGES — a key in both would be seeded
    while claiming to be held.
    """
    from scripts.seed_payroll_rule_set_2026_11_09 import CHANGES, DISPUTED

    assert "vacation_bonus" in DISPUTED
    assert "vacation_bonus" not in CHANGES
    assert not (set(CHANGES) & set(DISPUTED)), "a key cannot be both changed and held"


def test_every_disputed_key_explains_the_disagreement():
    """A `disputed` marker with no explanation is just an unexplained value."""
    from scripts.seed_payroll_rule_set_2026_11_09 import DISPUTED

    for key, why in DISPUTED.items():
        assert len(why) > 200, f"{key}: the disagreement needs stating, got {why!r}"
        # Both sides must be present, or a reader cannot settle it.
        assert "dispatch" in why.lower()
        assert "register" in why.lower()


def test_the_disputed_explanation_names_the_figures_it_disagrees_about():
    """⚠️ Prose that does not contain the numbers cannot be checked by anyone."""
    from scripts.seed_payroll_rule_set_2026_11_09 import DISPUTED

    why = DISPUTED["vacation_bonus"]
    for figure in ("75.00", "125.00", "155.00", "85.00", "105.00"):
        assert figure in why, f"the explanation does not mention {figure}"
