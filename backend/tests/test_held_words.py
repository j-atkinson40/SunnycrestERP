"""The held-word foundation — slice 2's clauses 2, 4 and 5 share one measurement.

⚠️ EVERY DISPATCH CASE IN THIS FILE WAS RUN AGAINST PRODUCTION BEFORE IT WAS WRITTEN,
and three of them did not behave as the dispatch assumed. Those are recorded here as
tests rather than as prose, because a surprise that is only written down is a surprise
that gets re-discovered.

No database: pure functions over a term list shaped like `vocabulary.Term`.
"""
from __future__ import annotations

import pytest

from app.services.capture.held import (
    MAX_TYPO_DISTANCE,
    MIN_SUGGESTIBLE_LENGTH,
    ORIGIN_EDITED,
    ORIGIN_TYPED,
    HeldWord,
    did_you_mean,
    distance_within,
    still_forming,
    within_two,
)


class T:
    """A stand-in for `vocabulary.Term` — `.text` and `.kind` are all that is read."""

    def __init__(self, text: str, kind: str = "vault") -> None:
        self.text = text
        self.kind = kind


#: ⚠️ THE REAL SHAPE OF SUNNYCREST'S VOCABULARY, measured 2026-10-28: full product
#: names, no bare "Monticello". That absence is the reason `did_you_mean` compares
#: words as well as whole terms, so the fixture has to reproduce it or the tests below
#: would pass against a whole-term implementation that fails on production.
PRODUCTION_SHAPED = [
    T("Monticello Burial Vault", "vault"),
    T("Monticello Urn Vault", "vault"),
    T("Continental Burial Vault", "vault"),
    T('Continental 34"', "vault"),
    T("Hopkins Funeral Home", "funeral_home"),
    T("Riverside Memorial Chapel", "funeral_home"),
    T("St. Mary's Cemetery", "cemetery"),
]


# ── the measurement ────────────────────────────────────────────────────────────────

def test_the_threshold_is_ONE_number_for_both_clauses():
    """⚠️ CLAUSE 2 HOLDS A WORD "within 2 letters of a known term"; CLAUSE 5 SUGGESTS FOR
    A WORD "within 2 letters of exactly one known term". Same measurement, two uses — so
    it must be one constant, or a word could be held as a typo and never suggested."""
    assert MAX_TYPO_DISTANCE == 2
    # the suggestion path and the hold path ask the same function
    assert within_two("montcello", "monticello") is True
    assert distance_within("montcello", "monticello") == 1


@pytest.mark.parametrize("a,b,expected", [
    ("monticello", "monticello", 0),
    ("montcello", "monticello", 1),      # one deletion — the dispatch's case
    ("monticelo", "monticello", 1),      # one deletion elsewhere
    ("monticellos", "monticello", 1),    # one insertion
    ("monticallo", "monticello", 1),     # one substitution
    ("montcallo", "monticello", 2),      # two edits
    ("fleg", "flag", 1),
])
def test_the_distance_is_an_EDIT_distance(a, b, expected):
    """⚠️ EDIT DISTANCE, NOT A SIMILARITY RATIO, AND THE CODEBASE'S FOUR
    `SequenceMatcher(...).ratio()` CALL SITES ARE WHY THIS IS SPELLED OUT. A ratio is
    relative to length, so one threshold means ~1 letter on a short word and ~4 on a long
    one. "within 2 letters" is a count."""
    assert distance_within(a, b) == expected


@pytest.mark.parametrize("a,b", [
    ("hopkins", "riverside"),
    ("montcello", "continental"),
    ("a", "monticello"),            # the length gate
    ("monticello", "mont"),         # and the other way
])
def test_too_far_is_None_rather_than_a_big_number(a, b):
    """⚠️ None RATHER THAN A SENTINEL, so "too far" cannot be compared as a number by
    accident — `distance_within(...) < 3` would be True for a sentinel of -1."""
    assert distance_within(a, b) is None
    assert within_two(a, b) is False


def test_the_bound_is_respected_even_for_long_words():
    """⚠️ THE EARLY EXIT IS ON THE ROW MINIMUM, not the final cell — a word that diverges
    early must be rejected rather than measured to the end."""
    assert distance_within("zzzzzzzzzzzzzzz", "monticellovault") is None


# ── clause 5: did you mean ─────────────────────────────────────────────────────────

def test_the_dispatch_s_OWN_CASE_works_and_it_needs_WORD_level_comparison():
    """⚠️ THE FINDING THAT CHANGED THE IMPLEMENTATION. The dispatch's headline case is
    "montcello" -> "Did you mean Monticello?" — and measured against Sunnycrest's real
    vocabulary **there is no term "Monticello"**. The terms are `Monticello Burial Vault`
    and `Monticello Urn Vault`, and "montcello" is distance 11 from either as a whole
    string. A whole-term implementation returns None and the dispatch's own example
    fails.
    """
    got = did_you_mean("montcello", PRODUCTION_SHAPED)
    assert got is not None, "the dispatch's headline case produced no suggestion"
    assert got.term == "Monticello", got
    assert got.distance == 1
    # ⚠️ AND IT IS ONE SUGGESTION, NOT TWO, even though "Monticello" is a word of two
    # different terms. Counting candidates rather than distinct spellings would make
    # this ambiguous and the question would never be asked.
    assert got.kind == "vault"


def test_an_ABBREVIATION_is_not_a_typo():
    """⚠️ "monti" GETS NO SUGGESTION, AND THAT IS CORRECT RATHER THAN A GAP. It is five
    letters from "monticello", and it is what the office actually types — the ghost and
    `prefix_resolve` already complete it. Suggesting a correction for a working
    abbreviation would interrupt the common case."""
    assert did_you_mean("monti", PRODUCTION_SHAPED) is None


def test_an_EXACT_term_ABORTS_the_scan_rather_than_merely_skipping_itself():
    """⚠️ A WORD THAT IS A KNOWN TERM WAS NEVER HELD. "Did you mean Monticello?" about the
    word "Monticello" is the pane asking a question it has already answered.

    ⚠️ AND THE FIXTURE DISTINGUISHES TWO GUARDS THAT LOOK INTERCHANGEABLE, which a break
    test is how I learned. There are two: an early `return None` on an exact match, and a
    `continue` that skips a zero-distance candidate. Removing the first leaves the second,
    so my first version stayed green — but they are NOT the same. The early return abandons
    the whole scan; the `continue` keeps looking, and would then suggest a DIFFERENT term
    that happens to be within two.

    `cars` is exactly a term AND one letter from `card`. Only the early return gives None.
    """
    assert did_you_mean("cars", [T("cars"), T("card")]) is None
    # and the plain cases
    assert did_you_mean("Monticello", PRODUCTION_SHAPED) is None
    assert did_you_mean("monticello", PRODUCTION_SHAPED) is None
    assert did_you_mean("Hopkins Funeral Home", PRODUCTION_SHAPED) is None


def test_a_word_within_two_of_SEVERAL_terms_gets_no_suggestion():
    """"Exactly one" is the dispatch's word and it is the whole guard.

    ⚠️ CONSTRUCTED SO BOTH ARE REACHABLE, which is the only arrangement that tests the
    guard: "bay" is one letter from both "Bar" and "Ray", so neither is the answer."""
    terms = [T("Bar"), T("Ray")]
    assert did_you_mean("bay", terms) is None


def test_a_TIE_is_refused_rather_than_broken_by_distance():
    """⚠️ TWO TERMS AT DIFFERENT DISTANCES LOOK LIKE A CLEAR WINNER AND ARE NOT. Closer
    by SPELLING says nothing about which the director meant, and Yes on the pill PLACES
    the answer — so a wrong suggestion writes a wrong value.

    ⚠️ THE GUARD THIS WATCHES IS THE EARLY `if len(found) > 1: return None`, NOT the final
    return — recorded because a break test aimed at the final return left this green and
    read as a blind test. Both spellings here are distance 1 from "cart", so the second
    distinct candidate trips the early exit before any final-return arithmetic happens.
    """
    terms = [T("cars"), T("chart")]
    assert distance_within("cart", "cars") == 1
    assert distance_within("cart", "chart") == 1
    assert did_you_mean("cart", terms) is None


@pytest.mark.parametrize("short", ["ab", "abc", "flg"])
def test_a_SHORT_word_is_never_suggested_about(short):
    """⚠️ A FLOOR THE DISPATCH DOES NOT STATE, reported rather than assumed. At distance
    2 every three-letter word reaches a crowd — "flg" reaches flag, fly, fog, leg — so
    below this length the measurement stops discriminating. A short word is HELD without
    a suggestion rather than suggested wrongly.

    ⚠️ EXACTLY ONE TERM IN THE FIXTURE, AND A BREAK TEST IS WHY. My first version offered
    three (`flag`, `Fly`, `Fog`) — all within 2 of "flg" — so the TIE guard returned None
    and removing the floor entirely left the test green. It was asserting the right thing
    for the wrong reason: §11 shape 6. With one term, the floor is the only thing
    standing between "flg" and a suggestion.
    """
    assert len(short) < MIN_SUGGESTIBLE_LENGTH
    assert did_you_mean(short, [T("flag")]) is None
    # ⚠️ THE CONTROL: at or above the floor, that same single term IS suggested — so the
    # assertion above is about the LENGTH and not about the fixture being unreachable.
    assert did_you_mean("flagg", [T("flag")]) is not None


def test_a_LABEL_word_inside_a_term_is_never_the_suggestion():
    """⚠️ "Vault", "Burial" AND "Cemetery" APPEAR IN DOZENS OF TERMS. Suggesting them
    would make every near-miss ambiguous and the question would never be asked — so the
    interior-word candidates skip `_NOISE_WORDS`, the same list clause 2 skips."""
    # "vaalt" is one letter from "vault", which is a word of four fixture terms
    assert did_you_mean("vaalt", PRODUCTION_SHAPED) is None
    # ⚠️ THE CONTROL: a non-label interior word IS suggestible, or the test above would
    # pass against an implementation that never looks inside a term at all.
    assert did_you_mean("montcello", PRODUCTION_SHAPED) is not None


# ── clause 1: the waiting rule ─────────────────────────────────────────────────────

def test_a_term_that_PREFIXES_a_longer_one_is_still_forming():
    assert still_forming("hopkins", PRODUCTION_SHAPED) is True
    assert still_forming("monticello", PRODUCTION_SHAPED) is True


def test_the_waiting_rule_is_PUNCTUATION_INSENSITIVE_and_production_is_why():
    """⚠️ THE OFFICE TYPES `st marys`; THE TERM IS `St. Mary's Cemetery`. Under plain
    lower-casing, `"st. mary's cemetery".startswith("st marys")` is **False** — the
    period and the apostrophe are both in the way — so the lookahead would never fire on
    the very term the dispatch's example names. Measured against production before this
    was written."""
    assert still_forming("st marys", PRODUCTION_SHAPED) is True
    assert still_forming("st mary's", PRODUCTION_SHAPED) is True
    assert still_forming("St. Marys", PRODUCTION_SHAPED) is True


def test_a_COMPLETE_term_with_nothing_longer_is_not_still_forming():
    """⚠️ THE CONTROL, and without it a function returning True always would pass every
    test above."""
    assert still_forming("riverside memorial chapel", PRODUCTION_SHAPED) is False
    assert still_forming("continental 34", PRODUCTION_SHAPED) is False
    assert still_forming("", PRODUCTION_SHAPED) is False


def test_an_ABBREVIATION_does_not_WAIT_which_is_the_gate_this_is_not():
    """⚠️ `GATING_TAIL_OPEN` LOOKS LIKE THIS RULE AND IS NOT IT. That gate is about an
    INCOMPLETE word — it exists so "Hopk" does not resolve mid-word. This is about a
    COMPLETE term that prefixes a longer one. "monti" is not a term at all, so it must
    not wait; the ghost already handles it."""
    assert still_forming("monti", PRODUCTION_SHAPED) is False
    assert still_forming("hopk", PRODUCTION_SHAPED) is False


def test_a_term_that_CONTAINS_the_phrase_mid_way_is_not_a_continuation():
    """⚠️ "STARTS WITH", NOT "CONTAINS". A term containing the phrase somewhere in the
    middle is a different term, not a continuation of this one — holding an answer on
    that basis would make a word wait for something the director is demonstrably not
    typing."""
    assert still_forming("mary", [T("St. Mary's Cemetery", "cemetery")]) is False
    assert still_forming("memorial", PRODUCTION_SHAPED) is False


# ── the held word's own record ─────────────────────────────────────────────────────

def test_a_held_word_round_trips_through_its_dict():
    h = HeldWord(word="fleg")
    assert HeldWord.from_dict(h.as_dict()) == h
    edited = HeldWord(word="flag", origin=ORIGIN_EDITED, declined=["Flag"])
    assert HeldWord.from_dict(edited.as_dict()) == edited


def test_a_BARE_STRING_is_tolerated_because_the_column_is_JSON():
    """⚠️ AN OLDER ROW OR A HAND-EDIT CAN HOLD ONE, and the strip is an aid — a malformed
    entry must not take the pane down."""
    assert HeldWord.from_dict("fleg") == HeldWord(word="fleg", origin=ORIGIN_TYPED)
    assert HeldWord.from_dict("   ") is None
    assert HeldWord.from_dict(None) is None
    assert HeldWord.from_dict(7) is None
    assert HeldWord.from_dict({"origin": "typed"}) is None  # no word


def test_an_unknown_ORIGIN_falls_back_rather_than_raising():
    assert HeldWord.from_dict({"word": "x", "origin": "teleported"}).origin == ORIGIN_TYPED


def test_DECLINED_terms_are_remembered_on_the_word():
    """Clause 5: "No keeps it held and never asks about that word again."

    ⚠️ STORED AS THE TERMS DECLINED RATHER THAN A BARE FLAG, so editing the word to
    something else can still be suggested about — a flag would silence the question for a
    word the director has since changed."""
    h = HeldWord(word="montcello", declined=["Monticello"])
    assert "Monticello" in HeldWord.from_dict(h.as_dict()).declined
    # a bare flag could not express this
    assert HeldWord(word="montcello").declined == []
