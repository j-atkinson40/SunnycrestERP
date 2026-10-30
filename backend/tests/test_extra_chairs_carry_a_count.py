"""Chairs are billed per unit, so the line needs a count — and the count depends on the bundle.

⚠️ REWRITTEN 2026-10-30 FOR RULINGS A/B'/C/D'/E. The file's original subject was one
field, `extra_chairs_count`, holding an already-subtracted extra count, with
`CHAIRS_INCLUDED = 8` doing the subtraction at EXTRACTION time. All three of those are
gone. What survives unchanged is the reason the file exists: a count captured and
displayed but billed wrongly looks entirely correct on the pane and gets the money wrong.

James 2026-10-14 (still in force): *"Extra Chairs (Over 8) at $5.00 per chair… Extra
chairs need a quantity… Show the quantity on the Review line."*
James 2026-10-30 (what changed): *"cemetery_equipment holds the package only… Store the
TOTAL chairs the director said; derive billable extras from it per package."* And:
*"Included chairs: 8 for every package except Device Only, which includes 0."*

WHAT IS TESTED HERE, each failing independently:

  - the two phrasings keep their SENSES rather than being converted into one another.
    `"12 chairs"` is a total; `"extra chairs 4"` is already netted. Neither can be
    turned into the other without a bundle, so neither is.
  - the arithmetic, derived from the BUNDLE's own `included_chairs` and hand-proven
    against literals here rather than computed by the code under test.
  - the quantity reaching the ORDER LINE, which is the only reason a count exists.
  - a zero extra count building NO line — "never a $0 line" (ruling B').
  - the four phrasings of one intent agreeing (ruling C), kept as a test on James's
    instruction even though ruling A fixes it by construction.

⚠️ THE ARITHMETIC IS STILL THE PART WORTH BREAKING, and the trap has moved rather than
gone. "extra chairs 4" contains "chairs 4", so an ordering mistake inside `_chairs`
reads an extra count as a total. Before ruling B' that billed `4 - 8 -> 0`; now it
stores `chairs_total=4`, and on a bundle including 8 that STILL bills 0. Both readings
produce a plausible number and neither raises.
`test_the_extra_form_is_tried_before_the_total_form` exists for that case.

### Why this file seeds its own tenant

⚠️ `products.included_chairs` IS WRITTEN ON PRODUCTION AND NOWHERE ELSE. The five
Sunnycrest rows were a separately-authorised production write (ruling B'); no seed sets
the column. A test leaning on `testco` would therefore read NULL for every bundle,
`billable_extra_chairs` would correctly refuse to derive anything, and every billing
assertion here would pass or fail for a reason that has nothing to do with chairs —
the "a test can pass because data is MISSING" class, in the direction where it fails
loudly rather than quietly. Seeding the bundles here makes the included counts an
explicit premise of each test instead of an inherited accident.
"""

from __future__ import annotations

import os
import uuid
from decimal import Decimal
from urllib.parse import urlparse

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.models.cemetery import Cemetery
from app.models.company import Company
from app.models.company_entity import CompanyEntity
from app.models.customer import Customer
from app.models.product import Product
from app.services.capture.approval import (
    EXTRA_CHAIRS_PRODUCT_NAME,
    _equipment_quantity,
    assess,
    billable_extra_chairs,
    chairs_readings,
)
from app.services.capture.rows import write_for_a_human
from app.services.capture.schema import EQUIPMENT_PACKAGES
from app.services.capture.typed_extraction import _chairs, evaluate_typed, extract_text

from tests._cleanup import purge_companies_by_slug

SLUG = "tc-chairs"

#: The bundles this file bills against, with the included counts ruled on 2026-10-30.
#: ⚠️ THE NUMBERS ARE THE RULING'S, NOT DERIVED FROM ANYTHING HERE. "A bundle includes
#: chairs when a family is coming; no-family bundles include none."
BUNDLES: tuple[tuple[str, str, Decimal, int], ...] = (
    ("Full Equipment", "T-PKG-FULL", Decimal("300.00"), 8),
    ("Lowering Device Only", "T-PKG-LD", Decimal("140.00"), 0),
)
CHAIR_PRICE = Decimal("5.00")


def _local_only() -> None:
    host = (urlparse(os.environ.get("DATABASE_URL", "")).hostname or "").lower()
    assert host in ("localhost", "127.0.0.1", "::1", ""), host


@pytest.fixture()
def world():
    """A tenant with two bundles whose included counts are KNOWN, plus a chair product."""
    _local_only()
    db = SessionLocal()
    purge_companies_by_slug(db, SLUG)
    cid = str(uuid.uuid4())
    db.add(Company(id=cid, name="Chairs Co", slug=SLUG, vertical="manufacturing"))
    db.flush()
    db.add_all([
        CompanyEntity(id=str(uuid.uuid4()), company_id=cid, name="Lakeshore Funeral Chapel",
                      city="Auburn", state="NY", is_funeral_home=True),
        # ⚠️ A CUSTOMER AS WELL AS AN ENTITY, AND FIVE TESTS FAILED FOR WANT OF IT.
        # `assess` bills to a CUSTOMER record and blocks with "No customer record for
        # …" when there is none — so every billing assertion here failed on a blocker
        # about the funeral home rather than anything about chairs. The entity is what
        # the EXTRACTOR resolves; the customer is what the ORDER bills. Two records,
        # two jobs, and a fixture needs both to reach a line.
        Customer(id=str(uuid.uuid4()), company_id=cid, name="Lakeshore Funeral Chapel",
                 account_number="FH-700", customer_type="funeral_home"),
        Cemetery(id=str(uuid.uuid4()), company_id=cid, name="Hillcrest Cemetery",
                 city="Auburn", state="NY", is_active=True),
    ])
    for name, sku, price, included in BUNDLES:
        db.add(Product(id=str(uuid.uuid4()), company_id=cid, name=name, sku=sku,
                       price=price, is_active=True, included_chairs=included))
    db.add(Product(id=str(uuid.uuid4()), company_id=cid, name=EXTRA_CHAIRS_PRODUCT_NAME,
                   sku="T-CHAIR-EX", price=CHAIR_PRICE, is_active=True))
    db.commit()
    yield db, cid
    db.rollback()
    purge_companies_by_slug(db, SLUG)
    db.commit()
    db.close()


def _vals(db, cid, body: str) -> dict:
    return dict(extract_text(db, tenant_id=cid, text=f"order for lakeshore {body}").values)


def _assess(db, cid, answers):
    _r, _st, conflicts = evaluate_typed(db, tenant_id=cid, answers=answers)
    return assess(db, tenant_id=cid, answers=answers, missing_labels=(), open_picks=(),
                  conflicts=tuple(c.message for c in conflicts))


# ── the premise, first, because every billing claim below rests on it ────────


def test_the_BUNDLES_carry_the_included_counts_this_file_assumes(world):
    """⚠️ THE POSITIVE CONTROL ON THE FIXTURE. If the seed stopped setting
    `included_chairs`, every derivation below would refuse to compute and the billing
    tests would fail for a reason unrelated to chairs. This says which premise broke."""
    db, cid = world
    got = dict(db.execute(text(
        "SELECT name, included_chairs FROM products WHERE company_id=:t "
        "AND included_chairs IS NOT NULL"), {"t": cid}).all())
    assert got == {"Full Equipment": 8, "Lowering Device Only": 0}, got


def test_chairs_are_NOT_an_equipment_bundle_any_more(world):
    """Ruling A. ⚠️ ASSERTED ON THE VOCABULARY, NOT ON A SENTENCE, because this is the
    thing that made chairs and the bundle compete for one single-valued field."""
    slugs = [slug for slug, _label in EQUIPMENT_PACKAGES]
    assert "extra_chairs" not in slugs, slugs
    # and the product name billing needs did NOT vanish with it
    assert EXTRA_CHAIRS_PRODUCT_NAME == "Extra Chairs (Over 8)"


# ── the two phrasings keep their senses ─────────────────────────────────────


def test_a_TOTAL_is_stored_AS_SAID_and_not_subtracted(world):
    """⚠️ THE OPPOSITE OF WHAT THIS FILE USED TO ASSERT, BY RULING B'. It read
    `test_a_TOTAL_subtracts_the_eight_already_included` and expected `"12 chairs"` to
    store 4. The subtraction moved to billing, and the reason is not only that the 8 was
    wrong for two bundles: subtracting here DESTROYED the number the director said, so
    `"6 chairs"` stored 0 and the pane could never show "6 chairs" again."""
    db, cid = world
    v = _vals(db, cid, "12 chairs")
    assert v.get("chairs_total") == "12", v
    assert v.get("chairs_extra") is None, v


def test_an_EXTRA_count_is_stored_as_an_extra(world):
    """His second phrasing. It is already netted of whatever the bundle includes, so it
    is stored in the field that means that and never converted to a total."""
    db, cid = world
    v = _vals(db, cid, "extra chairs 4")
    assert v.get("chairs_extra") == "4", v
    assert v.get("chairs_total") is None, v


def test_the_extra_form_is_tried_before_the_total_form():
    """⚠️ THE ORDERING TRAP, WHICH MOVED RATHER THAN WENT AWAY. "extra chairs 4"
    contains "chairs 4". Tried the other way round the extra count is read as a TOTAL —
    which before ruling B' billed `4 - 8 -> 0`, and now stores `chairs_total=4` which on
    a bundle including 8 still bills 0. The money is wrong by the same $20 either way,
    and nothing raises.

    ⚠️ IT GOES THROUGH `_chairs` DIRECTLY, not `extract_text`, because the whole point is
    which of the two pattern groups matched — a sentence-level test cannot see that and
    would pass on either."""
    assert _chairs("extra chairs 4") == ("extra", 4, (0, 14))
    assert _chairs("4 extra chairs")[0] == "extra"
    assert _chairs("12 chairs")[0] == "total"
    assert _chairs("chairs over 8: 3")[0] == "extra"


def test_the_over_8_phrasing_still_matches(world):
    """⚠️ IT WAS BUILT FROM `CHAIRS_INCLUDED` BY STRING INTERPOLATION — `r"chairs?\\s+over
    \\s+%d" % CHAIRS_INCLUDED` — so deleting that constant would have silently stopped
    this phrasing matching. The 8 here is a PHRASE the price list uses in its own row
    name, not the arithmetic constant, and the two are now independent."""
    db, cid = world
    v = _vals(db, cid, "chairs over 8: 3")
    assert v.get("chairs_extra") == "3", v


# ── ruling C: four phrasings, one answer ────────────────────────────────────


@pytest.mark.parametrize("body", [
    "full equipment 12 chairs",
    "full equipment, 12 chairs",
    "12 chairs full equipment",
    "12 chairs, full equipment",
])
def test_the_FOUR_PHRASINGS_agree(world, body):
    """Ruling C. ⚠️ KEPT ON JAMES'S INSTRUCTION EVEN THOUGH RULING A FIXES IT BY
    CONSTRUCTION: *"verifying it's fixed by construction is right; keep the
    four-phrasings test regardless so it stays fixed."*

    Measured on 2026-10-30 before the change, these four gave FOUR different answers
    decided by a comma — two losing the chair count to the `once()` gate, one losing the
    bundle to the overwrite, one correct. They could not all be right while chairs and
    the bundle shared a single-valued field.
    """
    db, cid = world
    v = _vals(db, cid, body)
    assert v.get("cemetery_equipment") == "full_equipment", (body, v)
    assert v.get("chairs_total") == "12", (body, v)
    assert v.get("chairs_extra") is None, (body, v)


# ── the arithmetic, hand-proven ─────────────────────────────────────────────


@pytest.mark.parametrize("included,total,extra,want,why", [
    (8, "12", None, Decimal("4"), "12 set out, 8 in the bundle -> 12-8 = 4"),
    (8, "2", None, Decimal("0"), "2 is fewer than the 8 included -> clamp to 0"),
    (8, "8", None, Decimal("0"), "exactly the included count -> 0"),
    (8, None, "4", Decimal("4"), "already netted -> 4"),
    (0, "10", None, Decimal("10"), "device only includes 0 -> all 10 are extras"),
    (0, None, "4", Decimal("4"), "netted against a 0-chair bundle -> 4"),
    (8, "12", "4", Decimal("4"), "both said and they AGREE (12-8 == 4)"),
    (8, "12", "6", None, "both said and they DISAGREE -> a question, not a number"),
    (None, "12", None, None, "not a bundle: a TOTAL cannot be converted"),
    (None, None, "4", Decimal("4"), "not a bundle: an EXTRA is already netted"),
    (8, None, None, None, "chairs mentioned, no number -> open"),
    (8, "", None, None, "empty is unsaid, not zero"),
    (8, "abc", None, None, "unreadable is unsaid, not one"),
])
def test_the_billable_count(included, total, extra, want, why):
    """⚠️ EVERY EXPECTED VALUE IS A LITERAL COMPUTED BY HAND, never by calling the
    function under test — CLAUDE.md's money rule. `why` is the arithmetic shown.

    ⚠️ AND `None` IS NEVER ZERO HERE. Zero means "no chairs to bill, bill no line";
    None means "I cannot say yet" — no bundle, no number, or two readings conflicting. A
    caller treating them alike bills a $0 line or drops a real one."""
    assert billable_extra_chairs(included, total, extra) == want, why


def test_the_disagreement_offers_BOTH_readings_spelled_out():
    """Ruling: *"Opas asks '12 chairs (4 extra) or 14 chairs (6 extra)?' with two
    pills."* ⚠️ A PICK OFFERING "4 or 6" WOULD ASK THE DIRECTOR TO DO THE ARITHMETIC
    THAT CONFUSED THE ENGINE."""
    assert chairs_readings(8, "12", "6") == ((12, 4), (14, 6))
    # and there is nothing to offer unless both were said against a known bundle
    assert chairs_readings(8, "12", None) == ()
    assert chairs_readings(None, "12", "6") == ()


def test_a_BUNDLE_always_bills_one(world):
    """⚠️ THIS FUNCTION USED TO BRANCH ON CHAIRS AND CANNOT NOW. Every value
    `cemetery_equipment` can hold is a bundle, and every bundle is a flat setup charge.
    `Vault Placer` at $0.00 still bills a REAL line — its PRICE is zero and its QUANTITY
    is one, and that distinction is the whole of the old zero-quantity rule."""
    assert _equipment_quantity("full_equipment", {}) == Decimal("1")
    assert _equipment_quantity("lowering_device_only", {"chairs_total": "99"}) == Decimal("1")


# ── the quantity reaches the order line ─────────────────────────────────────


def test_the_extras_are_a_SECOND_line_beside_the_bundle(world):
    """⚠️ TWO LINES, NOT ONE, AND THAT IS RULING A's BILLING CONSEQUENCE. They are two
    rows on the price list — a flat setup charge and a per-unit overage — and billing
    them as alternatives is why "full equipment, 12 chairs" used to produce an order
    with the chairs and no package.

    ⚠️ THE MONEY IS HAND-COMPUTED: 300.00 for the bundle, and 4 chairs at 5.00 = 20.00.
    """
    db, cid = world
    v = _vals(db, cid, "full equipment, 12 chairs")
    ap = _assess(db, cid, v)
    eq = [l for l in ap.lines if l.kind == "equipment"]
    assert len(eq) == 2, [(l.description, l.quantity, l.unit_price) for l in eq]
    by_name = {l.description: l for l in eq}
    assert by_name["Full Equipment"].quantity == Decimal("1")
    assert by_name["Full Equipment"].unit_price == Decimal("300.00")
    assert by_name[EXTRA_CHAIRS_PRODUCT_NAME].quantity == Decimal("4")
    assert by_name[EXTRA_CHAIRS_PRODUCT_NAME].unit_price == Decimal("5.00")
    assert by_name[EXTRA_CHAIRS_PRODUCT_NAME].line_total == Decimal("20.00")
    assert not [b for b in ap.blockers if "chair" in b.lower()], ap.blockers


def test_DEVICE_ONLY_bills_every_chair_as_an_extra(world):
    """⚠️ THE CASE THE GLOBAL CONSTANT GOT WRONG, measured on production 2026-10-30:
    `"device only, 10 chairs"` billed 2 extras, subtracting eight chairs from a bundle
    that includes none. Per-bundle data gets it right. 10 at 5.00 = 50.00, by hand."""
    db, cid = world
    v = _vals(db, cid, "lowering device only, 10 chairs")
    assert v.get("cemetery_equipment") == "lowering_device_only", v
    ap = _assess(db, cid, v)
    chairs = [l for l in ap.lines if l.description == EXTRA_CHAIRS_PRODUCT_NAME]
    assert len(chairs) == 1, [(l.description, l.quantity) for l in ap.lines]
    assert chairs[0].quantity == Decimal("10"), chairs[0]
    assert chairs[0].line_total == Decimal("50.00"), chairs[0]


# ── zero bills nothing, and says so ─────────────────────────────────────────


@pytest.mark.parametrize("body", ["full equipment, 8 chairs", "full equipment, 6 chairs"])
def test_at_or_under_the_included_count_BUILDS_NO_LINE(world, body):
    """Ruling B': *"no Extra Chairs line when extras = 0 — never a $0 line."* James
    2026-10-15 is also still in force: *"8 or fewer chairs: no extra-chairs line, no
    conflict."* A director saying "8 chairs" is describing the standard setup.

    ⚠️ THE BUNDLE LINE IS STILL THERE. Only the chairs line is absent — the earlier
    version of this test asserted NO equipment line at all, which was right when chairs
    WERE the equipment and would now hide a missing package."""
    db, cid = world
    v = _vals(db, cid, body)
    ap = _assess(db, cid, v)
    assert [l.description for l in ap.lines if l.kind == "equipment"] == ["Full Equipment"], ap.lines
    assert not [b for b in ap.blockers if "chair" in b.lower()], ap.blockers


def test_a_zero_count_reads_as_words_on_the_row(world):
    """⚠️ "0 chairs" READS LIKE A DEFECT on a row. Unchanged by these rulings; kept
    because ruling E forbids a bare 0 and this is the rendering that already did."""
    assert write_for_a_human("0", "count") == "none extra"
    assert write_for_a_human("4", "count") == "4 chairs"
    assert write_for_a_human("1", "count") == "1 chair"


# ── the open cases block rather than billing nothing ────────────────────────


def test_chairs_with_NO_NUMBER_is_a_GAP_not_a_one(world):
    """⚠️ IT DOES NOT DEFAULT. "extra chairs" with no count is a real thing to type, and
    assuming one would put a $5.00 line on the order nobody chose.

    ⚠️ THE MARKER IS WHY THE QUESTION STILL GETS ASKED. Before ruling A the mention was
    carried by `cemetery_equipment = extra_chairs` — the conflation being removed — so
    without `chairs_count_pending` this sentence would have stopped asking anything."""
    db, cid = world
    v = _vals(db, cid, "extra chairs")
    assert v.get("chairs_total") is None, v
    assert v.get("chairs_extra") is None, v
    assert not [l for l in _assess(db, cid, v).lines
                if l.description == EXTRA_CHAIRS_PRODUCT_NAME], v


def test_a_NUMBERLESS_MENTION_IS_LOST_ENTIRELY_which_is_NOT_what_was_ruled(world):
    """⚠️ OWED TO JAMES, AND PINNED HERE BECAUSE IT IS A SILENT LOSS. This test asserts
    behaviour that is WRONG. It exists so the wrongness is measured, named and
    unmissable rather than discovered on an invoice.

    ⚠️ WHAT WAS RULED (2026-10-30): *"accept the approval-time block for a numberless
    'extra chairs'. Capture-time ask comes back via proper condition combinators."*
    The trade James accepted was LATER AND LOUDER — no capture-time question, but
    `assess` refusing to approve an order whose chairs have no count.

    ⚠️ WHAT IS ACTUALLY IMPLEMENTED IS NEITHER. MEASURED, not inferred:

        'extra chairs'                   values={funeral_home}
                                         blockers=['Nothing to bill …']   ← not chairs
        'full equipment, extra chairs'   values={funeral_home, cemetery_equipment}
                                         lines=[('equipment', 'Full Equipment')]
                                         blockers=[]                      ← APPROVES

    The second line is the defect in one row: a director names a bundle AND extra
    chairs, the order approves with no blocker at all, and the invoice carries the
    bundle and no chairs. The chairs are gone and nothing said so.

    ⚠️ THE CAUSE IS ONE GATE, AND IT CANNOT BE FIXED BY PHRASING THE SENTENCE BETTER.
    `approval.assess` reaches its chairs branch only under
    `if chairs_total is not None or chairs_extra is not None`. A numberless mention
    writes NEITHER field — by design, since "extra chairs" names no number — so the
    branch is unreachable and `"Chairs were named but the count is still needed."` is
    DEAD CODE on this path. It fires only for a malformed count (e.g. `chairs_total`
    holding something `_as_int` refuses), never for the case it was written for.

    ⚠️ AND IT IS A REGRESSION PAST WHAT WAS ACCEPTED, which is the part that needs a
    ruling. Before ruling A this sentence set `cemetery_equipment = extra_chairs`,
    which made `extra_chairs_count` REQUIRED, so capture ASKED. The slice was meant to
    move that question later; it removed it instead. "Later and louder" was accepted —
    "gone and silent" was not.

    ⚠️ THE HANDOFF SAID THE OPPOSITE, AND THE CLAIM IS RECORDED SO IT IS NOT RE-DERIVED:
    *"The fix is to the TEST: give the sentence a vault or a bundle so it reaches the
    chairs path. The code is correct."* Giving it a bundle was tried first and is the
    measurement above — the blocker still does not fire, because the gate is on the
    FIELDS, not on whether lines exist.

    ⚠️ WHY NOTHING IS BOLTED ON HERE. Recording the mention needs somewhere to put it,
    and all three candidates are James's call, not an executor's:
      1. a sentinel value in `chairs_total` (e.g. `""` meaning "named, count unknown")
         — two fields still, but a field whose stored value is not a value;
      2. the `conflicts` channel into `assess`, which today means "an answer the
         availability config forbids" and would be widened to mean "incomplete";
      3. stop claiming the span, so "extra chairs" renders as UNPLACED text and the
         director sees at capture that it was not understood — no new field, no new
         channel, and it does not give the approval-time block that was ruled.
    James, 2026-10-30: *"nothing gets bolted on now."*
    """
    db, cid = world
    v = _vals(db, cid, "full equipment, extra chairs")
    assert v.get("chairs_total") is None, v
    assert v.get("chairs_extra") is None, v

    ap = _assess(db, cid, v)
    # the bundle bills, which is correct
    assert [l.description for l in ap.lines if l.kind == "equipment"] == [
        "Full Equipment"
    ], ap.lines
    # ⚠️ AND NOTHING AT ALL IS SAID ABOUT THE CHAIRS. The day this assertion starts
    # failing is the day the gap closes — change it then, do not relax it now.
    assert not [b for b in ap.blockers if "chair" in b.lower()], (
        "the chairs gap has closed — update this test by ruling rather than "
        "deleting it: " + repr(list(ap.blockers))
    )
    assert not [l for l in ap.lines if l.description == EXTRA_CHAIRS_PRODUCT_NAME], ap.lines


def test_the_count_is_still_needed_BLOCKER_is_unreachable_from_a_numberless_mention(world):
    """⚠️ THE CAUSE, PINNED SEPARATELY FROM THE SYMPTOM, so a reader does not have to
    take the paragraph above on trust. `assess` gates its whole chairs branch on one
    of the two count fields being present; a numberless mention supplies neither.

    ⚠️ THE POSITIVE CONTROL IS THE SECOND HALF AND IT IS WHAT MAKES THIS EVIDENCE. If
    the blocker string had simply been deleted, the first assertion would pass for the
    wrong reason. The second shows the message IS reachable — with a count field
    present whose value `_as_int` refuses — so what the first measures is the GATE,
    not the absence of the sentence.
    """
    db, cid = world
    v = _vals(db, cid, "full equipment, extra chairs")
    assert not [b for b in _assess(db, cid, v).blockers
                if "count is still needed" in b], v

    forced = dict(v)
    forced["chairs_total"] = ""
    assert [b for b in _assess(db, cid, forced).blockers
            if "count is still needed" in b], forced


def test_the_count_is_not_asked_when_chairs_were_never_mentioned(world):
    """The other side. A required field nobody can answer would block every
    full-equipment order forever."""
    db, cid = world
    v = _vals(db, cid, "full equipment")
    assert v.get("chairs_total") is None, v
    _r, st, _c = evaluate_typed(db, tenant_id=cid, answers=v)
    assert "chairs_total" not in st.missing, sorted(st.missing)
    # and nothing about chairs blocks an order that never mentioned them
    ap = _assess(db, cid, v)
    assert not [b for b in ap.blockers if "chair" in b.lower()], ap.blockers


def test_chairs_with_NO_BUNDLE_block_rather_than_billing_zero(world):
    """Ruling D' leaves the bundle open when only a count was given — and billing cannot
    proceed, because the extras depend on what the bundle includes.

    ⚠️ IT BLOCKS, IT DOES NOT BILL NOTHING. An order that silently billed $0 for chairs
    the director asked for is the failure the unsaid/zero distinction exists to prevent."""
    db, cid = world
    v = _vals(db, cid, "12 chairs")
    assert v.get("chairs_total") == "12", v
    assert v.get("cemetery_equipment") is None, v
    ap = _assess(db, cid, v)
    assert not [l for l in ap.lines if l.description == EXTRA_CHAIRS_PRODUCT_NAME], ap.lines
    assert [b for b in ap.blockers if "bundle" in b.lower()], ap.blockers


def test_two_readings_that_DISAGREE_block_with_both_spelled_out(world):
    """Ruling: *"Both said and they disagree → don't pick."* ⚠️ THE BLOCKER CARRIES BOTH
    NUMBERS, so the director answers at a glance instead of reconstructing the
    arithmetic."""
    db, cid = world
    v = dict(_vals(db, cid, "full equipment, 12 chairs"))
    v["chairs_extra"] = "6"          # as if the director had said both
    ap = _assess(db, cid, v)
    msg = " ".join(ap.blockers)
    assert "12 chairs (4 extra)" in msg, ap.blockers
    assert "14 chairs (6 extra)" in msg, ap.blockers
    assert not [l for l in ap.lines if l.description == EXTRA_CHAIRS_PRODUCT_NAME], ap.lines


# ── the grave-label tie, unchanged by these rulings ─────────────────────────


def test_a_grave_LABEL_owns_its_digit_before_chairs_do(world):
    """⚠️ MEASURED 2026-10-14 AND STILL THE RULE. "going to hillcrest section 12 chairs"
    read "12 chairs" as a count and produced `grave_location=None` — the section was
    silently lost. "section 12" says in WORDS which field the 12 belongs to; "chairs"
    does not."""
    db, cid = world
    v = _vals(db, cid, "hillcrest section 12 chairs")
    assert v.get("grave_location") == "Section 12", v
    assert v.get("chairs_total") is None, v


def test_a_grave_location_and_a_chair_count_coexist_when_both_are_explicit(world):
    """Both can be had; the tie only bites when one digit could serve either."""
    db, cid = world
    v = _vals(db, cid, "hillcrest section 12, full equipment, 20 chairs")
    assert v.get("grave_location") == "Section 12", v
    assert v.get("chairs_total") == "20", v
