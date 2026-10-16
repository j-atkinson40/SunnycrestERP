"""Chairs are the one equipment package priced per unit, so the line needs a count.

⚠️ RULED BY JAMES 2026-10-14: "Extra Chairs (Over 8) at $5.00 per chair... Extra
chairs need a quantity: '12 chairs' -> 4 extra; 'extra chairs 4' -> 4. Show the
quantity on the Review line."

FOUR THINGS ARE TESTED HERE, and they fail independently:

  - the two phrasings, with the arithmetic that differs between them. A total has
    `CHAIRS_INCLUDED` subtracted; an "extra" count does not.
  - the quantity reaching the ORDER LINE, which is the only reason the count exists.
    A count captured and displayed but billed at quantity 1 would look entirely
    correct on the pane and under-bill by $15 on a twelve-chair order.
  - the count being VISIBLE, on the equipment row's secondary.
  - zero extra chairs being REPORTED rather than billed as a $0.00 line.

⚠️ THE ARITHMETIC IS THE PART WORTH BREAKING. "extra chairs 4" contains "chairs 4",
so an ordering mistake inside `_chairs` reads the extra count as a total and bills
`4 - 8 -> 0` instead of 4. Both readings produce a plausible number and neither
raises. `test_the_extra_form_is_tried_before_the_total_form` exists for that case.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.services.capture.approval import (
    EQUIPMENT_PRODUCT_NAMES,
    _equipment_quantity,
    assess,
)
from app.services.capture.rows import write_for_a_human
from app.services.capture.schema import EQUIPMENT_PACKAGES
from app.services.capture.typed_extraction import (
    CHAIRS_INCLUDED,
    _chairs,
    evaluate_typed,
    extract_text,
)


def _refuse_a_non_local_database() -> None:
    from urllib.parse import urlparse

    from app.config import settings

    host = (urlparse(settings.DATABASE_URL).hostname or "").lower()
    assert host in ("localhost", "127.0.0.1", "::1", "")


@pytest.fixture(scope="module")
def db():
    _refuse_a_non_local_database()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture(scope="module")
def tenant(db) -> str:
    tid = db.execute(text("SELECT id FROM companies WHERE slug = 'testco'")).scalar()
    assert tid, "testco is not seeded — run scripts/seed_dev.sh"
    return tid


def _vals(db, tenant, body: str) -> dict:
    ex = extract_text(db, tenant_id=tenant, text=f"order for riverside monticello {body}")
    return dict(ex.values)


# ── the two phrasings James named ───────────────────────────────────────

def test_a_TOTAL_subtracts_the_eight_already_included(db, tenant):
    """His first example. "12 chairs" is twelve chairs AT the graveside, eight of
    which are in the package, so four are billable."""
    v = _vals(db, tenant, "12 chairs")
    assert v.get("cemetery_equipment") == "extra_chairs", v
    # 12 - 8 = 4, by hand. CHAIRS_INCLUDED is 8 and is asserted below rather than
    # used here, so this expectation does not move if the constant does.
    assert v.get("extra_chairs_count") == "4", v


def test_an_EXTRA_count_is_taken_as_given(db, tenant):
    """His second example. "extra chairs 4" has already done the subtraction."""
    v = _vals(db, tenant, "extra chairs 4")
    assert v.get("cemetery_equipment") == "extra_chairs", v
    assert v.get("extra_chairs_count") == "4", v


def test_the_constant_is_the_eight_the_price_list_names(db, tenant):
    """⚠️ PINNED SEPARATELY FROM THE ARITHMETIC. The price-list row is "Extra Chairs
    (Over 8)", so eight is the package's own number and not a tunable. If it moves,
    this fails loudly rather than quietly changing every total."""
    assert CHAIRS_INCLUDED == 8


@pytest.mark.parametrize(
    "body,expect",
    [
        ("12 chairs", "4"),
        ("extra chairs 4", "4"),
        ("4 extra chairs", "4"),
        ("chairs over 8: 3", "3"),
        ("20 chairs", "12"),
        ("extra chairs: 2", "2"),
        ("1 extra chair", "1"),
    ],
)
def test_every_phrasing_lands_the_same_way(db, tenant, body, expect):
    v = _vals(db, tenant, body)
    assert v.get("cemetery_equipment") == "extra_chairs", (body, v)
    assert v.get("extra_chairs_count") == expect, (body, v)


def test_the_extra_form_is_tried_before_the_total_form():
    """⚠️ THE ORDERING, ASSERTED DIRECTLY ON `_chairs` RATHER THAN THROUGH A SENTENCE.

    "extra chairs 4" matches the TOTAL pattern too — `chairs?\\s*:?\\s*(\\d+)` sees
    "chairs 4". Tried in the wrong order the extra count becomes a total and bills
    `max(0, 4 - 8) = 0`, so a four-chair order bills nothing and the pane shows a
    conflict about eight included chairs that the director never mentioned.

    Going through `extract_text` would hide which of the two matched; this reads the
    number the function actually returns.
    """
    assert _chairs("extra chairs 4")[0] == 4
    assert _chairs("4 extra chairs")[0] == 4
    # and the total form still does subtract, so the two paths are genuinely distinct
    assert _chairs("12 chairs")[0] == 4
    assert _chairs("4 chairs")[0] == 0


def test_a_grave_LABEL_owns_its_digit_before_chairs_do(db, tenant):
    """⚠️ A DEFECT I INTRODUCED AND THEN MEASURED, PINNED SO IT CANNOT COME BACK.

    Both recognisers want a bare digit. With chairs running first — which is where I
    put them, inside the equipment block — "going to oakwood section 12 chairs" read
    "12 chairs" as a TOTAL and produced `extra_chairs_count='4'` with
    `grave_location=None`. **The section was silently lost**, which is the one outcome
    the span rule exists to prevent.

    ⚠️ THE TIE BREAKS ON WHICH RECOGNISER IS EXPLICIT. "section 12" says in words
    which field the 12 belongs to; "chairs" does not. So the grave location claims
    first, and the leftover "chairs" is reported as unplaced text — visible and
    correctable, rather than a quietly missing grave.

    ⚠️ ASSERTED ON BOTH FIELDS AND ON `unrecognized`, because the symptom appeared on
    the field that was not the subject. A test checking only the chair count would
    have passed while the grave vanished.
    """
    ex = extract_text(
        db,
        tenant_id=tenant,
        text="order for riverside monticello going to oakwood section 12 chairs",
    )
    assert ex.values.get("grave_location") == "Section 12", ex.values
    assert ex.values.get("extra_chairs_count") is None, ex.values
    assert "chairs" in ex.unrecognized, ex.unrecognized


def test_a_grave_location_and_a_chair_count_coexist_when_both_are_explicit(db, tenant):
    """The ordering must not cost the normal case. An "extra chairs N" phrase carries
    its own keyword, so it never competes for a grave label's digit."""
    ex = extract_text(
        db,
        tenant_id=tenant,
        text="order for riverside monticello going to oakwood section 4 lot 12 extra chairs 6",
    )
    assert ex.values.get("grave_location") == "Section 4, Lot 12", ex.values
    assert ex.values.get("extra_chairs_count") == "6", ex.values
    assert ex.unrecognized == (), ex.unrecognized


def test_chairs_with_no_number_is_a_GAP_not_a_one(db, tenant):
    """⚠️ IT DOES NOT DEFAULT. "extra chairs" with no count is a real thing to type,
    and assuming one chair would put a $5.00 line on the order that nobody chose.
    The count is unanswered and the capture asks for it."""
    v = _vals(db, tenant, "extra chairs")
    assert v.get("cemetery_equipment") == "extra_chairs", v
    assert "extra_chairs_count" not in v, v

    _r, st, _c = evaluate_typed(db, tenant_id=tenant, answers=v)
    assert "extra_chairs_count" in st.missing, sorted(st.missing)


def test_the_count_is_not_asked_when_chairs_were_not_chosen(db, tenant):
    """The other side of the condition. Every other package is a flat charge, so the
    question must not exist — a required field nobody can answer would block every
    full-equipment order forever."""
    v = _vals(db, tenant, "full equipment")
    assert v.get("cemetery_equipment") == "full_equipment", v
    _r, st, _c = evaluate_typed(db, tenant_id=tenant, answers=v)
    assert "extra_chairs_count" not in st.missing, sorted(st.missing)
    assert "extra_chairs_count" in st.not_applicable, sorted(st.not_applicable)


# ── zero is a contradiction, not a quantity ─────────────────────────────

@pytest.mark.parametrize("body", ["8 chairs", "6 chairs"])
def test_no_extra_chairs_RAISES_NOTHING(db, tenant, body):
    """⚠️ REWRITTEN 2026-10-15. James: "8 or fewer chairs: no extra-chairs line, no
    conflict." This test asserted the opposite for one day.

    It read: "8 chairs" names the eight the package includes, the extra count is
    zero, and a $0.00 line is one nobody asked for — so it was raised as a conflict
    that blocked Approve. **That reasoning was mine**; his original dispatch gave two
    phrasings and neither reaches zero. He has ruled the other way: a director saying
    "8 chairs" is describing the standard setup, not making a mistake to resolve.

    ⚠️ THE ANSWER IS STILL CAPTURED, which is what separates this from a silent drop.
    The count is still 0 and the equipment is still `extra_chairs`, so the pane shows
    it understood; what changed is that nothing blocks and nothing bills.
    """
    v = _vals(db, tenant, body)
    assert v.get("cemetery_equipment") == "extra_chairs", (body, v)
    assert v.get("extra_chairs_count") == "0", (body, v)

    _r, _st, conflicts = evaluate_typed(db, tenant_id=tenant, answers=v)
    assert [c.field_id for c in conflicts] == [], [c.message for c in conflicts]


def test_zero_chairs_BUILDS_NO_LINE_and_does_not_block(db, tenant):
    """The other half of the ruling, asserted through `assess` rather than trusting
    that the conflict's removal was the whole of it.

    ⚠️ A ZERO QUANTITY AND A ZERO PRICE ARE DIFFERENT THINGS, and this is the test
    that keeps them apart. Chairs at quantity 0 build NO line; `Vault Placer` at
    $0.00 builds a REAL line (`test_vault_placer_bills_a_ZERO_line_rather_than_blocking`
    in test_approve_confirms_the_order.py). Collapsing the two would either bill a
    $0.00 chair line or drop the placer from the order it was used on.
    """
    v = _vals(db, tenant, "8 chairs")
    _r, _st, conflicts = evaluate_typed(db, tenant_id=tenant, answers=v)
    ap = assess(
        db,
        tenant_id=tenant,
        answers=v,
        missing_labels=(),
        open_picks=(),
        conflicts=tuple(c.message for c in conflicts),
    )
    assert [l for l in ap.lines if l.kind == "equipment"] == [], ap.lines
    assert not any("chair" in b.lower() for b in ap.blockers), ap.blockers


def test_a_zero_count_reads_as_words_on_the_row(db, tenant):
    """⚠️ "Extra Chairs (Over 8) · 0 chairs" READS LIKE A DEFECT. Since a zero count
    is now a legitimate captured answer it is rendered "none extra", which is the
    sentence the director said rather than the number the engine computed.

    ⚠️ THE WORDING IS MINE. James ruled on the line and the conflict and said nothing
    about the row; flagged to him.
    """
    assert write_for_a_human("0", "count") == "none extra"
    # and the non-zero renderings are unchanged
    assert write_for_a_human("4", "count") == "4 chairs"
    assert write_for_a_human("1", "count") == "1 chair"


# ── the quantity reaches the order line ─────────────────────────────────

def test_the_quantity_is_the_count_not_one(db, tenant):
    """⚠️ THE ONLY REASON THE COUNT EXISTS. Captured, displayed, and then billed at
    quantity 1 would look entirely right on the pane and under-bill a twelve-chair
    order by $15."""
    assert _equipment_quantity("extra_chairs", {"extra_chairs_count": "4"}) == Decimal(
        "4"
    )


def test_every_other_package_bills_one(db, tenant):
    """Each is a flat charge for the setup, so its line total is its price."""
    for slug, _label in EQUIPMENT_PACKAGES:
        if slug in ("extra_chairs", "none"):
            continue
        assert _equipment_quantity(slug, {}) == Decimal("1"), slug


def test_a_missing_count_falls_back_to_one_and_cannot_be_reached_by_approve(db, tenant):
    """⚠️ THE FALLBACK IS DELIBERATE AND UNREACHABLE ON THE APPROVE PATH, which is
    worth asserting in one place so a reader does not have to take the docstring's
    word for it. `extra_chairs_count` is required whenever chairs are chosen, so a
    missing count is already a blocker and no line is built. The fallback serves the
    mid-typing summary, where 0 would render $0.00 and read like a priced answer."""
    assert _equipment_quantity("extra_chairs", {}) == Decimal("1")
    assert _equipment_quantity("extra_chairs", {"extra_chairs_count": "oops"}) == (
        Decimal("1")
    )

    v = _vals(db, tenant, "extra chairs")
    _r, st, _c = evaluate_typed(db, tenant_id=tenant, answers=v)
    assert "extra_chairs_count" in st.missing


# ── it is visible ───────────────────────────────────────────────────────

def test_the_count_renders_with_its_unit(db, tenant):
    """⚠️ "4" ALONE ON AN EQUIPMENT ROW READS AS FOUR PACKAGES. James asked for the
    quantity on the Review line, and a quantity needs its noun."""
    assert write_for_a_human("4", "count") == "4 chairs"
    assert write_for_a_human("1", "count") == "1 chair"
    # ⚠️ ANYTHING NON-NUMERIC PASSES THROUGH, the same contract every other display
    # kind in `rows.py` has: a visible oddity beats taking the pane down over a row.
    assert write_for_a_human("", "count") == ""
    assert write_for_a_human("lots", "count") == "lots"


def test_both_surfaces_show_the_count(db, tenant):
    """⚠️ CAPTURE AND SUMMARY BOTH, because the field would otherwise be captured and
    invisible on one of them — which is the defect the 2026-10-12 ruling
    ("captured values must be visible") was raised for."""
    from app.services.capture.rows import FieldSource
    from app.services.capture.surfaces import (
        CAPTURE_SALES_ORDER,
        SUMMARY_SALES_ORDER,
    )

    for surface, which in ((CAPTURE_SALES_ORDER, "capture"), (SUMMARY_SALES_ORDER, "summary")):
        row = next(r for r in surface.rows if r.id == "cemetery_equipment")
        ids = {
            s.field_id
            for s in (row.secondary or ())
            if isinstance(s, FieldSource)
        }
        assert "extra_chairs_count" in ids, (which, row.secondary)


# ── the product name the migration must create ──────────────────────────

def test_the_package_label_and_the_product_name_are_ONE_STRING(db, tenant):
    """⚠️ THE JOIN IS THE NAME, AND NOTHING ELSE. `approval.assess` matches a captured
    package against `products.name`; `r212` creates "Extra Chairs (Over 8)" and the
    schema label is the same string. They are the same string on purpose — a product
    named "Extra chairs" or "Extra Chairs (over 8)" would match today only because
    the comparison lowercases both sides, and tightening that comparison later would
    break billing with nothing pointing at the cause.
    """
    assert EQUIPMENT_PRODUCT_NAMES["extra_chairs"] == "Extra Chairs (Over 8)"
    assert EQUIPMENT_PRODUCT_NAMES["vault_placer"] == "Vault Placer"


def test_the_whole_order_bills_the_chairs(db, tenant):
    """End to end, against products this test creates itself.

    ⚠️ IT ENSURES ITS OWN WORLD, AND CI TAUGHT ME THAT THREE TIMES IN THIS ARC. A
    fixture that assumed the tenant already carried priced products failed on a
    fresh CI database for reasons unrelated to chairs. Rows are created, committed so
    the extractor's own sessions can see them, and deleted afterwards.
    """
    made: list[str] = []

    def product(name: str, price: Decimal) -> None:
        pid = str(uuid.uuid4())
        db.execute(
            text(
                "INSERT INTO products (id, company_id, name, sku, price, is_active) "
                "VALUES (:i, :t, :n, :k, :p, true)"
            ),
            {"i": pid, "t": tenant, "n": name, "k": f"CHAIRTEST-{pid[:8]}", "p": price},
        )
        made.append(pid)

    customer_id = str(uuid.uuid4())
    try:
        product("Monticello Burial Vault", Decimal("1405.00"))
        product("Extra Chairs (Over 8)", Decimal("5.00"))
        db.execute(
            text(
                "INSERT INTO customers (id, company_id, name, account_number, is_active) "
                "VALUES (:i, :t, 'Riverside Funeral Home', :a, true)"
            ),
            {"i": customer_id, "t": tenant, "a": f"CT-{customer_id[:8]}"},
        )
        db.commit()

        answers = {
            "funeral_home": "Riverside Funeral Home",
            "vault": "Monticello Burial Vault",
            "cemetery_equipment": "extra_chairs",
            "extra_chairs_count": "4",
        }
        ap = assess(
            db,
            tenant_id=tenant,
            answers=answers,
            missing_labels=(),
            open_picks=(),
        )
        chairs = next(l for l in ap.lines if l.kind == "equipment")
        assert chairs.quantity == Decimal("4"), ap.lines
        assert chairs.unit_price == Decimal("5.00"), ap.lines
        # 4 x $5.00 = $20.00, by hand
        assert chairs.line_total == Decimal("20.00"), chairs.line_total
        # $1,405.00 + $20.00 = $1,425.00, by hand
        assert ap.total == Decimal("1425.00"), (ap.total, ap.lines)
    finally:
        db.rollback()
        if made:
            db.execute(
                text("DELETE FROM products WHERE id = ANY(:i)"), {"i": made}
            )
        db.execute(text("DELETE FROM customers WHERE id = :i"), {"i": customer_id})
        db.commit()
