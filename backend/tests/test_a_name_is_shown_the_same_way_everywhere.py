"""One casing rule, two surfaces. James 2026-10-15: "title-cased wherever displayed".

⚠️ THE DEFECT THIS CLOSES WAS A RULING THAT REACHED ONE SURFACE. On 2026-10-14 a
lowercase name began rendering "Mary Smith" in the capture pane while
`/ar/orders/:id` still read "mary smith" for the same order — both consistent with
"stored as typed, title-cased for display", and the second one was simply never
taught the display half.

⚠️ THE FIX IS AT THE API BOUNDARY RATHER THAN AT EACH RENDER SITE, and that choice is
the reason this file exists. Measured 2026-10-15: 25+ frontend files reference a
deceased name. An enumeration of them would be exhaustive on the day it was written
and silently stop being so — which is the constructed-scope failure CLAUDE.md §11
names. A validator on the RESPONSE schema is correct for a surface nobody has built
yet.
"""

from __future__ import annotations

import pytest

from app.schemas.sales import SalesOrderCreate, SalesOrderResponse
from app.services.capture.rows import write_for_a_human
from app.services.display_name import title_case_for_display

_ORDER = {
    "id": "1", "company_id": "c", "number": "SO-1", "customer_id": "cu",
    "status": "draft", "order_date": "2026-10-15T00:00:00Z",
    "subtotal": "0", "tax_rate": "0", "tax_amount": "0", "total": "0",
    "created_at": "2026-10-15T00:00:00Z",
}


@pytest.mark.parametrize(
    "typed,shown,why",
    [
        ("mary smith", "Mary Smith", "the ruling's own example"),
        ("smith", "Smith", "one word"),
        ("o'brien", "O'Brien", "an apostrophe is a word boundary"),
        ("smith-jones", "Smith-Jones", "so is a hyphen"),
        ("deSoto", "deSoto", "already capitalised — left alone"),
        ("MacLeod", "MacLeod", "already capitalised — left alone"),
        # ⚠️ RULED 2026-10-29, AND BOTH WERE UNRULED UNTIL THEN. The all-lowercase guard
        # introduced on 2026-10-15 meant these two fell straight through untouched —
        # a consequence of the guard rather than a decision about these shapes. James
        # ruled them deliberate: *"only an all-lowercase name is title-cased. Any name
        # containing a capital … displays exactly as entered."*
        #
        # ⚠️ AND THEY ARE THE TWO SHAPES ON WHICH THE DELETED DUPLICATE DISAGREED.
        # `order_list/detail.py::title_case_name` guarded PER WORD, so it rendered
        # "Mcleod" and "Mary Smith" for these. Pinning them here is what stops a future
        # "improvement" quietly reinstating the per-word rule: forcing title case turns
        # McLeod into Mcleod and DeAngelo into Deangelo, which is a wrong name on a
        # document rather than a cosmetic miss.
        #
        # ⚠️ THE ONE ARGUMENT FOR CONVERTING ALL-CAPS — funeral homes typing surnames in
        # caps out of habit — was checked against production rather than weighed:
        # ZERO of the 15 orders carrying a deceased name are all-caps. If that changes,
        # this is the case to revisit and that figure is what to re-measure.
        ("MCLEOD", "MCLEOD", "all caps — a capital means leave it alone"),
        ("mary SMITH", "mary SMITH", "mixed case — displayed exactly as entered"),
        ("", "", "empty passes through"),
    ],
)
def test_the_rule(typed, shown, why):
    assert title_case_for_display(typed) == shown, why


def test_the_capture_pane_and_the_order_api_AGREE(typed="mary smith"):
    """⚠️ THE ASSERTION IS THAT THE TWO SURFACES MATCH, not that each is right on its
    own. Two separately-correct-looking implementations drifting is the failure this
    whole file is about, so the comparison is between them rather than against a
    literal twice."""
    pane = write_for_a_human(typed, "name")
    api = SalesOrderResponse.model_validate({**_ORDER, "deceased_name": typed}).deceased_name
    assert pane == api == "Mary Smith", (pane, api)


def test_what_is_STORED_is_untouched():
    """⚠️ THE OTHER HALF OF THE RULING, AND THE REASON THE VALIDATOR IS ON THE
    RESPONSE ONLY. `SalesOrderCreate` decides what lands in the column; putting the
    casing there would rewrite the director's own capitalisation into the database,
    which "stored as typed" forbids."""
    created = SalesOrderCreate.model_validate(
        {"customer_id": "cu", "order_date": "2026-10-15T00:00:00Z",
         "deceased_name": "mary smith"}
    )
    assert created.deceased_name == "mary smith"


def test_a_null_name_stays_null():
    m = SalesOrderResponse.model_validate({**_ORDER, "deceased_name": None})
    assert m.deceased_name is None
