"""RULING E — the equipment row says both chair numbers, in one sentence.

James, 2026-10-30: *"`Full equipment · 12 chairs (4 extra)` when extras are non-zero,
`Full equipment · 2 chairs` at or under the included count, and never a bare 0 — and it
shows BOTH numbers whichever sense the director used, so `extra chairs 4` on Full
Equipment still reads `12 chairs (4 extra)`."*

⚠️ THE DEFECT IT CLOSES IS A NUMBER IN THE WRONG SENSE, WHICH IS WORSE THAN A MISSING
ONE. Rulings A/B' split one field into two — `chairs_total` ("12 chairs", what the crew
sets out) and `chairs_extra` ("extra chairs 4", already netted) — and `resolve_surface`
renders the first of the two that holds a value. So an order saying "extra chairs 4" on
Full Equipment displayed **"4 chairs"**: a true number, labelled as if it were the
total, on a row that actually means twelve. Nothing on the pane said which sense it was.

⚠️ AND THE COMPOSITION CANNOT HAPPEN WHERE THE ROW IS BUILT, which is why this is a
serializer test. The derived extra needs the bundle's own `products.included_chairs`
(`r218_included_chairs`), and neither `rows.py` nor `surfaces.py` has a database. The
row carries both senses as its `secondary`; `session_service` turns them into one
sentence, at the same layer and for the same reason the urn-vault row label flips there.

### Why this file seeds its own tenant

Same reason `test_extra_chairs_carry_a_count.py` does, and it is worth repeating because
it is the difference between this file measuring the ruling and measuring nothing:
`products.included_chairs` is written on Sunnycrest's five PRODUCTION rows and nowhere
else — no seed sets it. Against a tenant whose bundles are NULL, `chairs_for_display`
correctly refuses to convert between the senses and EVERY ruled string here would be
replaced by the underived form, with the tests passing or failing for a reason that has
nothing to do with ruling E. The included counts are an explicit premise below.
"""

from __future__ import annotations

import os
import uuid
from decimal import Decimal
from urllib.parse import urlparse

import pytest

from app.database import SessionLocal
from app.models.company import Company
from app.models.company_entity import CompanyEntity
from app.models.customer import Customer
from app.models.product import Product
from app.models.role import Role
from app.models.user import User
from app.services.capture import session_service
from app.services.capture.approval import (
    EXTRA_CHAIRS_PRODUCT_NAME,
    chairs_for_display,
    included_chairs_for,
)

from tests._cleanup import purge_companies_by_slug

SLUG = "tc-rowe"

#: ⚠️ TWO BUNDLES WITH DIFFERENT INCLUDED COUNTS, DELIBERATELY. A single bundle at 8
#: would let a hard-coded 8 pass every assertion here — the exact constant ruling B'
#: deleted, which was wrong for two of the five production bundles.
BUNDLES: tuple[tuple[str, str, Decimal, int], ...] = (
    ("Full Equipment", "E-PKG-FULL", Decimal("300.00"), 8),
    ("Lowering Device Only", "E-PKG-LD", Decimal("140.00"), 0),
)


def _local_only() -> None:
    host = (urlparse(os.environ.get("DATABASE_URL", "")).hostname or "").lower()
    assert host in ("localhost", "127.0.0.1", "::1", ""), host


@pytest.fixture()
def world():
    _local_only()
    db = SessionLocal()
    purge_companies_by_slug(db, SLUG)
    cid = str(uuid.uuid4())
    db.add(Company(id=cid, name="Row E Co", slug=SLUG, vertical="manufacturing"))
    db.flush()
    role = Role(id=str(uuid.uuid4()), company_id=cid, name="Admin", slug="admin")
    db.add(role)
    db.flush()
    uid = str(uuid.uuid4())
    db.add(User(id=uid, company_id=cid, email=f"{SLUG}@example.com", first_name="R",
                last_name="E", hashed_password="x", role_id=role.id))
    db.add_all([
        CompanyEntity(id=str(uuid.uuid4()), company_id=cid,
                      name="Lakeshore Funeral Chapel", city="Auburn", state="NY",
                      is_funeral_home=True),
        Customer(id=str(uuid.uuid4()), company_id=cid, name="Lakeshore Funeral Chapel",
                 account_number="FH-800", customer_type="funeral_home"),
    ])
    for name, sku, price, included in BUNDLES:
        db.add(Product(id=str(uuid.uuid4()), company_id=cid, name=name, sku=sku,
                       price=price, is_active=True, included_chairs=included))
    db.add(Product(id=str(uuid.uuid4()), company_id=cid, name=EXTRA_CHAIRS_PRODUCT_NAME,
                   sku="E-CHAIR-EX", price=Decimal("5.00"), is_active=True))
    db.commit()
    yield db, cid, uid
    db.rollback()
    purge_companies_by_slug(db, SLUG)
    db.commit()
    db.close()


def _equipment_row(db, cid, uid, body: str):
    """The equipment row as the PANE receives it, through the typed path.

    ⚠️ `set_text`, NOT `add_line`, AND THE DIFFERENCE IS MEASURED RATHER THAN ASSUMED.
    `set_text` re-reads the whole text and is "the source of truth for the typed pane"
    in its own docstring; `add_line` extracts one line at a time. On
    `"full equipment, 12 chairs, 6 extra chairs"` they DISAGREE — `set_text` captures
    both senses and `add_line` captures only `chairs_extra`, because the per-line
    extractor sees one clause and `_chairs` tries the extra patterns first. The
    disagreement case below is only reachable through the surface the pane actually
    uses, so that is the surface this file drives.
    """
    row = session_service.start(db, company_id=cid, user_id=uid)
    session_service.set_text(db, row.id, company_id=cid, user_id=uid,
                             text=f"order for lakeshore {body}")
    state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)
    return next(r for r in state["surface"]["rows"]
                if r["row_id"] == "cemetery_equipment")


# ── the premise, first ──────────────────────────────────────────────────────

def test_the_bundles_included_counts_are_readable_and_DIFFERENT(world):
    """⚠️ THE CONTROL, AND WITHOUT IT EVERY RULED STRING BELOW IS UNFALSIFIABLE. If
    `included_chairs_for` returned None — a NULL column, a renamed product, a SELECT
    that stopped naming the column — `chairs_for_display` would refuse to derive and
    the row would show the director's raw number. Several assertions below would then
    still pass, for a reason that has nothing to do with ruling E."""
    db, cid, _uid = world
    assert included_chairs_for(db, cid, {"cemetery_equipment": "full_equipment"}) == 8
    assert included_chairs_for(db, cid, {"cemetery_equipment": "lowering_device_only"}) == 0
    # and the three ways there is no count to read
    assert included_chairs_for(db, cid, {}) is None
    assert included_chairs_for(db, cid, {"cemetery_equipment": "none"}) is None
    assert included_chairs_for(db, cid, {"cemetery_equipment": "not_a_package"}) is None


# ── the ruled strings, through the typed path ───────────────────────────────

def test_a_TOTAL_over_the_included_count_shows_both_numbers(world):
    """The first ruled form, verbatim: "Full equipment · 12 chairs (4 extra)"."""
    db, cid, uid = world
    row = _equipment_row(db, cid, uid, "full equipment, 12 chairs")
    assert row["value"] == "Full Equipment", row
    assert row["secondary_value"] == "12 chairs (4 extra)", row


def test_an_EXTRA_count_shows_THE_SAME_STRING_as_the_total_that_means_it(world):
    """⚠️ THE SENTENCE THE RULING SPELLS OUT, AND THE DEFECT IT NAMES. *"it shows BOTH
    numbers whichever sense the director used, so `extra chairs 4` on Full Equipment
    still reads `12 chairs (4 extra)`."* Before ruling E this row read "4 chairs" — the
    extras wearing the total's label.

    ⚠️ ASSERTED AS EQUALITY WITH THE TOTAL PHRASING, not as a literal twice. Two
    literals could both be edited to agree on a wrong string; this one cannot be
    satisfied unless the two senses genuinely converge."""
    db, cid, uid = world
    said_as_a_total = _equipment_row(db, cid, uid, "full equipment, 12 chairs")
    said_as_extras = _equipment_row(db, cid, uid, "full equipment, extra chairs 4")
    assert said_as_extras["secondary_value"] == "12 chairs (4 extra)", said_as_extras
    assert said_as_extras["secondary_value"] == said_as_a_total["secondary_value"]


def test_at_or_under_the_included_count_there_is_NO_EXTRA_CLAUSE(world):
    """The second ruled form: "Full equipment · 2 chairs", and never "(0 extra)"."""
    db, cid, uid = world
    under = _equipment_row(db, cid, uid, "full equipment, 2 chairs")
    assert under["secondary_value"] == "2 chairs", under
    exactly = _equipment_row(db, cid, uid, "full equipment, 8 chairs")
    assert exactly["secondary_value"] == "8 chairs", exactly
    assert "extra" not in (under["secondary_value"] + exactly["secondary_value"])


def test_a_bundle_that_includes_NO_chairs_bills_them_all_as_extra(world):
    """⚠️ THE CASE A CONSTANT GOT WRONG ON PRODUCTION. `CHAIRS_INCLUDED = 8` made
    "lowering device only, 10 chairs" read as 2 extras; the bundle includes none, so
    all ten are. The row has to say so for the same reason the line does."""
    db, cid, uid = world
    row = _equipment_row(db, cid, uid, "lowering device only, 10 chairs")
    assert row["value"] == "Lowering Device Only", row
    assert row["secondary_value"] == "10 chairs (10 extra)", row


def test_the_two_senses_DISAGREEING_shows_both_readings_and_picks_neither(world):
    """⚠️ RULING B's DISAGREEMENT, ON THE ROW. "12 chairs, 6 extra chairs" on a bundle
    including 8 is two different orders — 12 chairs or 14 — and `assess` blocks with
    exactly these numbers. A row that displayed one of them would quietly answer the
    question the blocker is asking."""
    db, cid, uid = world
    row = _equipment_row(db, cid, uid, "full equipment, 12 chairs, 6 extra chairs")
    assert row["secondary_value"] == "12 chairs (4 extra) or 14 chairs (6 extra)", row


def test_a_count_with_NO_BUNDLE_is_not_converted_into_a_sense_nobody_said(world):
    """Ruling D' leaves the bundle open when only a count was given. Without the
    included count neither sense can be expressed as the other, so the row says what
    the director said — and says which sense it is."""
    db, cid, uid = world
    total = _equipment_row(db, cid, uid, "12 chairs")
    assert total["value"] is None, total
    assert total["secondary_value"] == "12 chairs", total
    extras = _equipment_row(db, cid, uid, "extra chairs 4")
    assert extras["value"] is None, extras
    assert extras["secondary_value"] == "4 extra chairs", extras


def test_a_bundle_with_no_chairs_mentioned_has_NO_secondary(world):
    """⚠️ THE CONTROL ON THE WHOLE COMPOSITION. If `chairs_for_display` invented a
    string from no input — "0 chairs", "none extra" — every full-equipment order in the
    product would grow a chair line nobody typed."""
    db, cid, uid = world
    row = _equipment_row(db, cid, uid, "full equipment")
    assert row["value"] == "Full Equipment", row
    assert row["secondary_value"] is None, row


# ── never a bare number, and never a bare 0 ─────────────────────────────────

def test_NO_RULED_STRING_IS_EVER_A_BARE_NUMBER(world):
    """⚠️ THE PROHIBITION, ASSERTED OVER EVERY REACHABLE FORM RATHER THAN PER CASE.
    "never a bare 0" is one instance of the older rule the `display="count"` kind
    exists for: a number alone on an equipment row invites "four what — four
    packages?"."""
    db, cid, uid = world
    for body in ("full equipment, 12 chairs", "full equipment, 2 chairs",
                 "full equipment, extra chairs 4", "lowering device only, 10 chairs",
                 "full equipment, 12 chairs, 6 extra chairs", "12 chairs",
                 "extra chairs 4"):
        shown = _equipment_row(db, cid, uid, body)["secondary_value"]
        assert shown is not None, body
        assert not shown.strip().isdigit(), (body, shown)
        assert "chair" in shown, (body, shown)


def test_zero_is_WORDS_and_the_zero_extra_clause_is_never_written():
    """⚠️ DELEGATED, NOT RE-DECIDED. `write_for_a_human(..., "count")` has rendered "0"
    as "none extra" since James's 2026-10-15 ruling; routing through it is what keeps
    one answer to "how is zero written". A second body here would be free to drift."""
    assert chairs_for_display(8, "0", None) == "none extra"
    assert chairs_for_display(None, None, "0") == "none extra"
    assert "(0 extra)" not in (chairs_for_display(8, "8", None) or "")
    assert "(0 extra)" not in (chairs_for_display(8, "2", None) or "")


def test_singular_at_one_on_both_sides_of_the_sentence():
    """"1 chairs" is the kind of detail that makes a screen look machine-written."""
    assert chairs_for_display(8, "1", None) == "1 chair"
    assert chairs_for_display(8, None, "1") == "9 chairs (1 extra)"
    assert chairs_for_display(None, None, "1") == "1 extra chair"


def test_nothing_said_renders_nothing():
    assert chairs_for_display(8, None, None) is None
    assert chairs_for_display(None, None, None) is None


def test_an_UNREADABLE_count_is_not_a_count():
    """⚠️ SAME CONTRACT AS `_as_int` EVERYWHERE ELSE: "unreadable" and "unsaid" collapse
    to the same answer, because a half-typed "1" must not become a chair."""
    assert chairs_for_display(8, "", None) is None
    assert chairs_for_display(8, "lots", None) is None


# ── the arithmetic, hand-proven against literals ────────────────────────────

def test_the_derivation_is_hand_proven_and_not_recomputed_by_the_code_under_test():
    """⚠️ LITERALS ON BOTH SIDES. A table built by calling `billable_extra_chairs`
    would agree with any subtraction the code happened to be doing, including a wrong
    one. Each row below was worked out by hand from the ruling."""
    assert chairs_for_display(8, "12", None) == "12 chairs (4 extra)"
    assert chairs_for_display(8, "9", None) == "9 chairs (1 extra)"
    assert chairs_for_display(8, "8", None) == "8 chairs"
    assert chairs_for_display(8, "6", None) == "6 chairs"
    assert chairs_for_display(8, None, "4") == "12 chairs (4 extra)"
    assert chairs_for_display(8, "12", "4") == "12 chairs (4 extra)"
    assert chairs_for_display(0, "10", None) == "10 chairs (10 extra)"
    assert chairs_for_display(0, None, "10") == "10 chairs (10 extra)"
    assert chairs_for_display(None, "12", None) == "12 chairs"
    assert chairs_for_display(None, None, "4") == "4 extra chairs"
    assert chairs_for_display(8, "12", "6") == "12 chairs (4 extra) or 14 chairs (6 extra)"
