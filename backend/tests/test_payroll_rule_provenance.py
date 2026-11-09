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


def test_no_key_is_both_changed_and_held():
    """⚠️ THE RULING, HELD IN CODE.

    *"If the current set's values disagree with the Phase 3 list, stop and show
    me before seeding."* A key in both CHANGES and DISPUTED would be seeded
    while claiming to be held, which is the one outcome the mechanism exists to
    prevent. This holds whether or not anything is currently disputed.
    """
    from scripts.seed_payroll_rule_set_2026_11_09 import CHANGES, DISPUTED

    assert not (set(CHANGES) & set(DISPUTED)), "a key cannot be both changed and held"


def test_the_vacation_bonus_dispute_was_settled_in_the_registers_favour():
    """James, 2026-11-09: *"the register is right and the dispatch's goldens
    were wrong. Same tiers, different basis."*

    The key that WAS held is now seeded, with `from_registers` rather than
    `confirmed` — the register's behaviour adopted as the rule, with the union
    contract still to be read.
    """
    from scripts.seed_payroll_rule_set_2026_11_09 import CHANGES, DISPUTED

    assert "vacation_bonus" not in DISPUTED
    assert "vacation_bonus_day_tiers" in CHANGES
    value, provenance = CHANGES["vacation_bonus_day_tiers"]
    assert provenance["status"] == "from_registers"
    assert "contract to confirm" in provenance["source"]
    # The tiers themselves, as the ruling states them.
    assert value == [{"through_day": 5, "per_day": "15.00"},
                     {"through_day": 10, "per_day": "10.00"},
                     {"through_day": 15, "per_day": "6.00"}]


def test_the_dispute_mechanism_survives_having_nothing_to_hold():
    """⚠️ Deleting it with the dispute would be the mistake.

    `DISPUTED` is empty now. If the mechanism had gone with the key, the next
    disagreement would have nowhere to go and would get resolved by whoever was
    seeding at the time. So the seed must still import, still check, and still
    exit non-zero when something IS held.
    """
    import scripts.seed_payroll_rule_set_2026_11_09 as seed

    assert isinstance(seed.DISPUTED, dict)
    assert seed.DISPUTED == {}, "update this test when something is disputed again"
    # The machinery that acts on it is still present and still reachable.
    source = io_read = __import__("inspect").getsource(seed.main)
    assert "if DISPUTED:" in source
    assert "return 2" in source, "a disputed key must still make the run non-clean"


def test_every_disputed_key_explains_the_disagreement():
    """A `disputed` marker with no explanation is just an unexplained value."""
    from scripts.seed_payroll_rule_set_2026_11_09 import DISPUTED

    for key, why in DISPUTED.items():
        assert len(why) > 200, f"{key}: the disagreement needs stating, got {why!r}"
        # Both sides must be present, or a reader cannot settle it.
        assert "dispatch" in why.lower()
        assert "register" in why.lower()


def test_from_registers_is_its_own_status_between_confirmed_and_assumed():
    """⚠️ The vacation bonus needed a status that did not exist.

    It is in force (so not `measured`, which is only an observation) and the
    authoritative document has not been read (so not `confirmed`). Collapsing
    it into either would lose the one thing a reader needs to know: that the
    contract is still outstanding.
    """
    assert "from_registers" in RULE_STATUSES
    assert rule_provenance("from_registers",
                           "registers Nov 2026; contract to confirm") == {
        "status": "from_registers",
        "source": "registers Nov 2026; contract to confirm",
    }
