"""One question at a time, in call order. James 2026-10-15.

⚠️ THE DEFECT IS A TONE, NOT A BUG, which is why this file pins wording as well as
order. His walk verdict: "it works, but typing into a blank bar with no guidance
feels strange." The bar read "Still need: service date, cemetery, equipment" — three
gaps at once, which is a report. One question is a conversation.

⚠️ THE ORDER IS A THIRD ORDERING AND LIVES IN THE SCHEMA, not in the frontend. It is
neither `PLATFORM_DEFAULT_FIELDS` order nor either surface's row order; a phone call
starts with who is calling. Hand-written in the bar, it would drift from the set the
pane colours from and the two would disagree about what is outstanding.
"""

from __future__ import annotations

import pytest

from app.services.capture.schema import (
    CALL_ORDER,
    CALL_QUESTIONS,
    PLATFORM_DEFAULT_FIELDS,
    READY_TO_REVIEW,
    next_question,
)

TEMPLATE = {f.field_id for f in PLATFORM_DEFAULT_FIELDS}


def test_the_template_is_not_empty():
    """⚠️ THE CONTROL. Over an empty template every assertion below is vacuous."""
    assert len(TEMPLATE) >= 20, len(TEMPLATE)


def test_nothing_missing_reads_READY():
    assert next_question(set()) == READY_TO_REVIEW
    assert next_question(None) == READY_TO_REVIEW
    # ⚠️ REWORDED 2026-10-27, AND BOTH WORDINGS ARE HIS. It was "Ready. Press Enter to
    # review." — the line beside a Complete order BUTTON. The fixes remove the button:
    # "When everything needed is answered, Opas says 'That's everything.' with a Review
    # pill (⌥1) and Enter". With the pill carrying "Enter", a sentence that also says
    # it says it twice.
    assert READY_TO_REVIEW == "That\u2019s everything."
    # ⚠️ AND THE INSTRUCTION MOVED TO THE HINT rather than disappearing — the
    # prototype's own split.
    from app.services.capture.schema import READY_HINT

    assert READY_HINT == "Press Enter to review, or click any line to change it."


@pytest.mark.parametrize(
    "missing,expect",
    [
        ({"funeral_home", "vault", "service_date"}, "Which funeral home?"),
        ({"vault", "service_date"}, "Which vault?"),
        ({"service_date", "cemetery"}, "What day is the service?"),
        ({"cemetery"}, "Which cemetery?"),
        ({"service_location"}, "Where's the service?"),
        # ⚠️ REWORDED BY RULING, 2026-10-27: James gave this sentence verbatim in the
        # guided-capture dispatch — 'question "What is the name of the deceased?"' —
        # superseding "Who is the decedent?", which was this module's own shaping. The
        # old wording is kept in this comment because the test is the only record that
        # it changed, and a reader comparing the dispatch to the code should be able to
        # see that the change was ordered rather than drifted.
        ({"deceased_name", "cemetery"}, "What is the name of the deceased?"),
    ],
)
def test_it_asks_the_FIRST_thing_in_call_order(missing, expect):
    """⚠️ THE SET IS UNORDERED AND THE ANSWER IS NOT. Passing a `set` is deliberate:
    `state.missing` is one, so a rule that accidentally depended on iteration order
    would pass here and be non-deterministic in production."""
    assert next_question(missing) == expect


def test_the_four_James_wrote_are_VERBATIM():
    """⚠️ QUOTED FROM THE DISPATCH. He gave four phrasings in his own words; the rest
    follow their shape. If someone rewords these, it should be a decision."""
    assert CALL_QUESTIONS["funeral_home"] == "Which funeral home?"
    assert CALL_QUESTIONS["vault"] == "Which vault?"
    assert CALL_QUESTIONS["service_location"] == "Where's the service?"
    assert CALL_QUESTIONS["service_date"] == "What day is the service?"


def test_every_field_in_CALL_ORDER_is_a_real_template_field():
    """⚠️ A RATCHET ON THE LIST ITSELF. A typo'd field id would sit in the order
    forever, never matching anything, and the bar would silently skip to the next —
    a question that is never asked and never reported missing."""
    strays = [f for f in CALL_ORDER if f not in TEMPLATE]
    assert strays == [], strays


def test_every_field_in_CALL_ORDER_has_a_question():
    missing = [f for f in CALL_ORDER if f not in CALL_QUESTIONS]
    assert missing == [], missing


def test_a_field_NOT_in_call_order_is_still_asked():
    """⚠️ THE LIST IS A PRIORITY, NOT A FILTER, and this is the difference that
    matters. A field added to the template and forgotten here must still reach the
    director — asked last and asked plainly — rather than becoming invisible. A
    whitelist would have made "forgotten" mean "never mentioned again"."""
    asked = next_question({"a_field_nobody_prioritised"})
    assert asked, "a field outside CALL_ORDER produced no question at all"
    assert asked != READY_TO_REVIEW


def test_it_never_asks_an_OPTIONAL_field(db_missing=None):
    """⚠️ ASSERTED THROUGH THE SET RATHER THAN THROUGH A RULE HERE. "Optional fields
    are never asked" is true because `next_question` reads `state.missing`, and
    `CaptureState` already partitions `unanswered_optional` away from it. There is no
    second rule to keep in step — so what this pins is that the function takes the
    MISSING set and nothing wider.

    ⚠️ `cemetery_equipment` IS THE LIVE EXAMPLE. It is `required_when=Never()`, so it
    never enters `missing` and is therefore never asked — even though it appears in
    CALL_ORDER and in James's verify walk. Flagged to him: his walk lists equipment,
    his rule excludes it, and the rule is what shipped.
    """
    from app.services.capture.schema import PLATFORM_DEFAULT_FIELDS as F
    from app.services.capture.conditions import Never

    equip = next(f for f in F if f.field_id == "cemetery_equipment")
    assert isinstance(equip.required_when, Never), type(equip.required_when)
    # with only an optional field outstanding there is nothing to ask
    assert next_question(set()) == READY_TO_REVIEW
