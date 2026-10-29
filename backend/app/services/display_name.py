"""One rule for how a person's name is shown, used by every surface that shows one.

⚠️ RULED BY JAMES 2026-10-14 AND WIDENED 2026-10-15. The first ruling was "a
lowercase name is title-cased for display, stored as typed", and it reached the
capture pane only — so the pane read "Mary Smith" and `/ar/orders/:id` read
"mary smith" for the same order. The second ruling closes that: "Deceased name
title-cased wherever displayed (order page too)."

⚠️ IT LIVES HERE RATHER THAN IN `rows.py` BECAUSE IT NOW HAS TWO CALLERS. The capture
pane renders through `rows.write_for_a_human`; the API renders through the response
schemas. Two copies of a casing rule is one copy too many — they would look right in
isolation and drift on the first edit, which is exactly the shape CLAUDE.md §11 names
when it says a rule with two homes has no home.

⚠️ THE STORED VALUE IS NEVER TOUCHED. This is a rendering. `extract_text` records the
director's own capitalisation and `sales_orders.deceased_name` keeps it; only what is
handed to a screen changes.
"""

from __future__ import annotations


def title_case_for_display(value: str | None) -> str | None:
    """"mary smith" -> "Mary Smith". Anything already capitalised is left alone.

    ⚠️ IT ONLY ACTS ON AN ALL-LOWERCASE VALUE, AND THAT IS THE WHOLE CARE IN IT.
    `.title()` applied unconditionally turns "deSoto" into "Desoto", "MacLeod" into
    "Macleod" and "O'Brien" into "O'brien". A name the director already capitalised
    carries information, and the office's own capitalisation is the better guess
    about a family than any rule this function could hold.

    ⚠️ `.title()` IS SAFE **INSIDE** THAT GUARD, AND ONLY INSIDE IT. The capture pane
    used a per-word first-character raise, which is correct for "mary smith" and
    wrong for every name carrying an internal boundary: measured 2026-10-15, it gave
    "O'brien" and "Smith-jones". `str.title()` capitalises after each non-letter and
    gets both right — and the reason it is normally dangerous (it would flatten
    "deSoto" to "Desoto") cannot bite here, because a value that is not already
    all-lowercase never reaches this line.

    ⚠️ IT IS STILL NOT PERFECT AND IS NOT TRYING TO BE. "mcleod" renders "Mcleod",
    not "McLeod"; nothing in an all-lowercase string says where the capital belongs.
    A director who types the capitals keeps them, which is the escape hatch.
    """
    if not value:
        return value
    if value != value.lower():
        return value
    return value.title()


#: What a pane shows where no deceased name is recorded. One spelling, because four
#: panes each spelled it themselves and a fifth would have spelled it a fifth way.
UNNAMED = "Unnamed"


def deceased_for_display(value: str | None) -> str:
    """The deceased as a PANE shows it: title-cased, or `UNNAMED` when absent.

    ⚠️ ADDED 2026-10-29 AFTER THE RULING REACHED ITS THIRD SURFACE AND MISSED IT.
    James's walk screenshot showed "smith" and "smith it" rendering lowercase in the
    Order List pane and the Cemetery pane's "Coming up here". The 2026-10-15 ruling —
    "title-cased wherever displayed" — had been applied at the API RESPONSE BOUNDARY,
    deliberately, because enumerating render sites is a scope that stops being
    exhaustive the day it is written. The Opas panes do not render through those
    schemas: they build their own dicts, so the boundary never covered them.

    ⚠️ AND THE PANES HAD A SECOND IMPLEMENTATION OF THE CASING RULE, which is why one
    pane was right and the rest were not. `order_list/detail.py::title_case_name`
    title-cased PER WORD on `islower() or isupper()`; this module guards on the WHOLE
    string. Measured, they disagree on exactly two shapes: an all-caps "MCLEOD"
    (-> "MCLEOD" here, "Mcleod" there) and a mixed "mary SMITH" (-> unchanged here,
    "Mary Smith" there). They also disagreed on None (None vs ""). Neither divergent
    shape is ruled; this module's guard is the one the ruling's own test file pins, so
    it is the one kept and `title_case_name` is deleted.

    ⚠️ MEASURED ON PRODUCTION BEFORE COLLAPSING THEM: all 15 orders carrying a deceased
    name render identically under both, so there is no visible change to any existing
    row — the fix is to the panes that were not calling either one.

    ⚠️ IT RETURNS A NON-EMPTY STRING ALWAYS, so it must NOT be used where an absent name
    has to stay falsy. The Cemetery pane's "Coming up here" line joins its parts with
    `p for p in (...) if p`; passing "Unnamed" through there would put the word into a
    label that is supposed to omit it. That site calls `title_case_for_display`.
    """
    return title_case_for_display(value) or UNNAMED
