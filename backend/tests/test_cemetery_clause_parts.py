"""The cemetery clause, part by part — because one regex failed silently three times.

⚠️ THE THREE FAILURES, EACH A DIFFERENT WAY FOR ONE EXPRESSION TO BREAK:

  1. a greedy `{0,2}` name group ATE ITS OWN DELIMITER — "to St Mary's cemetery in
     Auburn" asked the resolver for "St Mary's cemetery in" and matched nothing.
  2. `{{2,30}}` inside an f-string left the braces LITERAL, so the town group matched
     the text "{2,30}" — i.e. never. The town was never captured at all.
  3. `\\s*(?:cemetery)?` CONSUMED THE SPACE THE TOWN GROUP NEEDED, so with "Cemetery"
     omitted `\\s+in\\s+` could not match and the town was silently lost. That one
     resolved "St Mary's in Auburn" to the Skaneateles record for weeks.

⚠️ EVERY ONE WAS INVISIBLE FOR THE SAME REASON: the clause still matched, still
produced a name, and the part that broke was OPTIONAL — so its absence looked exactly
like the director not having said a town.

⚠️ AND COMPOSING NAMED FRAGMENTS BACK INTO ONE PATTERN WOULD NOT HELP. Failure 3 was
an interaction BETWEEN two adjacent fragments; concatenating named fragments
reproduces it. So the clause is parsed in STEPS, each anchored at an explicit position
and reporting where it ended. This file tests each step alone, then the composition,
then the three failures as named regression cases.
"""
from __future__ import annotations

import pytest

from app.services.capture.typed_extraction import (
    _CEM_MARKER,
    _CEM_NAME,
    _CEM_SUFFIX,
    _CEM_TOWN,
    parse_cemetery_clause,
)


# ── step 1: the marker ──────────────────────────────────────────────────

@pytest.mark.parametrize("line,consumed", [
    ("to St Mary's", "to "),
    ("at Oakwood", "at "),
    ("going to Oakwood", "going to "),
    ("burial at Oakwood", "burial at "),
    ("buried at Oakwood", "buried at "),
])
def test_the_marker_consumes_itself_and_its_trailing_space(line, consumed):
    m = _CEM_MARKER.search(line)
    assert m and m.group(0) == consumed, m


def test_no_marker_means_no_clause():
    assert _CEM_MARKER.search("order for Hopkins") is None


# ── step 2: the name ────────────────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("St Mary's", "St Mary's"),
    ("Oakwood", "Oakwood"),
    ("Lakeview Memorial Gardens", "Lakeview Memorial Gardens"),
])
def test_the_name_takes_up_to_three_words(text, expected):
    m = _CEM_NAME.match(text, 0)
    assert m and m.group(0) == expected, m


@pytest.mark.parametrize("text,expected", [
    # ⚠️ FAILURE 1, AS A UNIT. Without the lookahead the name swallows its own
    # delimiters and the resolver is asked for a phrase no record carries.
    ("St Mary's cemetery in Auburn", "St Mary's"),
    ("Oakwood in Auburn", "Oakwood"),
    ("Oakwood and something", "Oakwood"),
    ("Oakwood at noon", "Oakwood"),
])
def test_the_name_STOPS_at_a_reserved_word(text, expected):
    m = _CEM_NAME.match(text, 0)
    assert m and m.group(0) == expected, m.group(0) if m else None


# ── step 3: the optional "cemetery" ─────────────────────────────────────

def test_the_suffix_owns_its_leading_space():
    """⚠️ FAILURE 3 MADE STRUCTURAL. The space belongs to the suffix, so a step that
    does NOT match consumes NOTHING and the separator the next step needs is still
    there."""
    assert _CEM_SUFFIX.match(" Cemetery", 0).group(0) == " Cemetery"
    assert _CEM_SUFFIX.match(" cemeteries", 0).group(0) == " cemeteries"


def test_the_suffix_matches_nothing_when_absent():
    """And when it is absent it consumes NOTHING — which is the entire fix."""
    assert _CEM_SUFFIX.match(" in Auburn", 0) is None


# ── step 4: the optional town ───────────────────────────────────────────

@pytest.mark.parametrize("text,town", [
    (" in Auburn", "Auburn"),
    (" in Skaneateles", "Skaneateles"),
    (" in New Hartford", "New Hartford"),
    # ⚠️ A TOWN WITH A PERIOD, AND THIS ROW FOUND A FOURTH GAP IN THE SAME CLAUSE.
    # The original charset allowed apostrophes and hyphens but NOT periods, so
    # "St. Albans" and "Mt. Vernon" were unreadable while the clause still matched
    # and still produced a name — the same invisible shape as the other three.
    (" in St. Albans", "St. Albans"),
    (" in Mt. Vernon", "Mt. Vernon"),
])
def test_the_town_is_read_after_in(text, town):
    # ⚠️ ASSERTED EXACTLY. My first version of this line was
    # `m.group(1).strip() == town.replace(".", "") or ... == town`, which accepts
    # EITHER form and would have passed whether the period survived or not — a
    # condition that cannot distinguish the thing it is testing.
    m = _CEM_TOWN.match(text, 0)
    assert m is not None, f"{text!r} matched nothing"
    assert m.group(1).strip() == town, m.group(1)


def test_the_town_quantifier_is_a_real_quantifier():
    """⚠️ FAILURE 2, AS A UNIT. Written as `{{2,30}}` inside an f-string the braces
    stayed literal and this pattern matched only the TEXT "{2,30}". A one-letter town
    must be rejected and a normal one accepted — which is only true if the quantifier
    is quantifying."""
    assert _CEM_TOWN.match(" in A", 0) is None, "a 1-char town matched"
    assert _CEM_TOWN.match(" in Rome", 0) is not None
    assert _CEM_TOWN.match(" in {2,30}", 0) is None, (
        "the literal text '{2,30}' matched — the braces are not quantifying"
    )


# ── the composition ─────────────────────────────────────────────────────

@pytest.mark.parametrize("line,name,town", [
    ("to St Mary's in Auburn", "St Mary's", "Auburn"),
    ("to St Mary's Cemetery in Auburn", "St Mary's", "Auburn"),
    ("to St Mary's Cemetery", "St Mary's", None),
    ("to St Mary's", "St Mary's", None),
    ("at Oakwood Cemetery in Auburn", "Oakwood", "Auburn"),
    ("buried at Lakeview Memorial Gardens", "Lakeview Memorial Gardens", None),
    ("going to Oakwood in Syracuse", "Oakwood", "Syracuse"),
])
def test_the_clause_parses_every_combination_of_the_optional_parts(line, name, town):
    """⚠️ ALL FOUR COMBINATIONS OF THE TWO OPTIONAL PARTS. Failure 3 lived in exactly
    one of them — suffix absent, town present — which is why a table of phrasings
    somebody happened to try did not contain it."""
    c = parse_cemetery_clause(line)
    assert c is not None, line
    assert c.name == name, c
    assert c.town == town, c


def test_the_clause_covers_the_whole_phrase_it_read():
    """⚠️ THE SPAN IS PART OF THE ANSWER. A clause that parses the town but claims a
    span ending before it leaves "Auburn" as unplaced text — which is how failure 3
    presented, and a name/town assertion alone would not have caught it."""
    line = "to St Mary's in Auburn"
    c = parse_cemetery_clause(line)
    assert (c.start, c.end) == (0, len(line)), (c.start, c.end)
    assert line[c.start:c.end] == line


def test_each_part_reports_its_own_span():
    line = "at Oakwood Cemetery in Auburn"
    c = parse_cemetery_clause(line)
    assert line[c.name_span[0]:c.name_span[1]] == "Oakwood"
    assert line[c.suffix_span[0]:c.suffix_span[1]] == " Cemetery"
    assert line[c.town_span[0]:c.town_span[1]] == "Auburn"


def test_a_line_with_no_marker_yields_no_clause():
    assert parse_cemetery_clause("order for Hopkins") is None
    assert parse_cemetery_clause("") is None


def test_a_marker_with_no_name_yields_no_clause():
    """"at 10am" has a marker and no name — the step parser must refuse rather than
    hand back an empty name for the resolver to puzzle over."""
    assert parse_cemetery_clause("at 10am") is None
