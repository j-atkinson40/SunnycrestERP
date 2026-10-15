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
