"""Rulings 1 and 2 of 2026-11-02 — an order can be equipment, and a family ASKS.

James, after the vault slot was closed to non-vaults:

    1. *"EQUIPMENT-ONLY ORDERS ARE REAL. An order is complete with no vault when an
       equipment bundle is set and no vault was mentioned. Vault is required only when
       nothing else makes it a sale: required_when 'no equipment bundle'. Opas still
       asks the vault question first on a new order; a pill 'No vault — equipment only'
       answers it."*
    2. *"'lowering device' alone → Opas asks, two pills: 'Device only' / 'Device &
       grass'. Never map it to either price silently. 'lowering device and grass' /
       'device only' resolve directly as now."*

### Why these two rulings arrived together

⚠️ BOTH ARE CONSEQUENCES OF CLOSING THE VAULT SLOT, AND NEITHER WAS VISIBLE BEFORE IT.
`"Lowering Device"` used to resolve into `vault` — it is `form = 'equipment'`, so that
was the Vault Placer defect again — and the only test of an equipment-only order passed
BECAUSE of it. Once the slot refused equipment, two things were suddenly true at once:
no equipment-only order could complete (ruling 1), and `"lowering device"` reached no
field at all (ruling 2). One fix, two holes it uncovered.

⚠️ AND BOTH REFUSE TO GUESS AT MONEY, WHICH IS THE SHAPE THEY SHARE. Ruling 1 will not
let an order approve with nothing on it; ruling 2 will not pick between two price-list
rows. The vault resolver has worked this way since it was written — an ambiguous phrase
asks — and the one exception to that (2026-10-13, a form-only ambiguity takes the burial
vault) was ruled precisely because the two readings cost the same.
"""

from __future__ import annotations

import os
import uuid
from datetime import date
from decimal import Decimal
from urllib.parse import urlparse

import pytest
from sqlalchemy import text as sql

from app.database import SessionLocal
from app.models.company import Company
from app.models.company_entity import CompanyEntity
from app.models.customer import Customer
from app.models.product import Product
from app.models.role import Role
from app.models.user import User
from app.services.capture import SALES_ORDER, session_service, template_for
from app.services.capture.approval import assess
from app.services.capture.conditions import NoAnswerOrSentinel, Verdict
from app.services.capture.pills import pills_for
from app.services.capture.schema import (
    EQUIPMENT_NONE_ANSWER,
    VAULT_FIELD_ID,
    VAULT_NONE_ANSWER,
    VAULT_NONE_LABEL,
    PLATFORM_DEFAULT_FIELDS,
    resolve_schema,
)
from app.services.capture.typed_extraction import evaluate_typed, extract_text

from tests._cleanup import purge_companies_by_slug

SLUG = "tc-eqonly"


def _local_only() -> None:
    host = (urlparse(os.environ.get("DATABASE_URL", "")).hostname or "").lower()
    assert host in ("localhost", "127.0.0.1", "::1", ""), host


@pytest.fixture()
def world():
    """A tenant that stocks BOTH lowering-device packages, at different prices.

    ⚠️ BOTH, AND AT DIFFERENT PRICES, BECAUSE THAT IS WHY RULING 2 EXISTS. A fixture
    carrying one of them would make `"lowering device"` unambiguous in practice and
    every assertion about asking would pass for the wrong reason.
    """
    _local_only()
    db = SessionLocal()
    purge_companies_by_slug(db, SLUG)
    cid = str(uuid.uuid4())
    db.add(Company(id=cid, name="Equip Only Co", slug=SLUG, vertical="manufacturing"))
    db.flush()
    role = Role(id=str(uuid.uuid4()), company_id=cid, name="Admin", slug="admin")
    db.add(role)
    db.flush()
    uid = str(uuid.uuid4())
    db.add(User(id=uid, company_id=cid, email=f"{SLUG}@example.com", first_name="E",
                last_name="O", hashed_password="x", role_id=role.id))
    db.add_all([
        CompanyEntity(id=str(uuid.uuid4()), company_id=cid,
                      name="Lakeshore Funeral Chapel", city="Auburn", state="NY",
                      is_funeral_home=True),
        Customer(id=str(uuid.uuid4()), company_id=cid, name="Lakeshore Funeral Chapel",
                 account_number="FH-900", customer_type="funeral_home"),
    ])
    for name, sku, price in (
        ("Lowering Device Only", "Q-PKG-LD", Decimal("140.00")),
        ("Lowering Device & Grass", "Q-PKG-LDG", Decimal("185.00")),
        ("Full Equipment", "Q-PKG-FULL", Decimal("300.00")),
    ):
        db.add(Product(id=str(uuid.uuid4()), company_id=cid, name=name, sku=sku,
                       price=price, is_active=True, included_chairs=8))
    db.commit()
    yield db, cid, uid
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


# ── ruling 1: the requirement, as a condition rather than a literal ─────────

def test_the_vault_declares_the_RULED_CONDITION_and_not_a_hand_rolled_one():
    """⚠️ THE DECLARATION, ASSERTED AS A DECLARATION. Ruling 1 names the condition —
    `required_when "no equipment bundle"` — and this pins that the field says so, with
    the equipment sentinel in it. A test that only exercised behaviour would pass
    against a special case buried in `missing.py`, which is where this rule would be
    invisible to the next reader."""
    vault = next(f for f in PLATFORM_DEFAULT_FIELDS if f.field_id == VAULT_FIELD_ID)
    assert isinstance(vault.required_when, NoAnswerOrSentinel), vault.required_when
    assert vault.required_when.field_id == "cemetery_equipment"
    assert vault.required_when.sentinels == frozenset({EQUIPMENT_NONE_ANSWER})
    # ⚠️ AND IT IS NO LONGER UNCONDITIONALLY REQUIRED, which is the thing every caller
    # reading `definition.required` now gets right and used to get wrong.
    assert vault.required is False


@pytest.mark.parametrize("equipment,vault_required", [
    (None, True),                       # a new order: nothing makes it a sale yet
    (EQUIPMENT_NONE_ANSWER, True),      # "no equipment" is an ANSWER, not a bundle
    ("full_equipment", False),
    ("lowering_device_and_grass", False),
    ("vault_placer", False),
])
def test_the_requirement_follows_the_bundle(equipment, vault_required):
    """⚠️ THE WALK'S OWN VERDICT, over the five states the equipment field can be in.

    ⚠️ AN UNANSWERED BUNDLE READS REQUIRED, NOT INDETERMINATE, AND THAT IS THE ONE
    DELIBERATE INVERSION IN `conditions.py`. Every other node reads an unanswered
    dependency as INDETERMINATE so that a requirement cannot appear mid-flow. Here
    "not yet answered" IS the answer — on a brand-new order nothing is answered and the
    vault must be required then, or Opas opens an order and never asks about the vault
    at all. Measured on the first attempt, which is why the node is documented at
    length.
    """
    resolved = resolve_schema(
        vault_product_id=None, personalization_config=None,
        platform_fields=template_for(SALES_ORDER),
        answers={} if equipment is None else {"cemetery_equipment": equipment},
    )
    vault = next(r for r in resolved if r.definition.field_id == VAULT_FIELD_ID)
    assert (vault.required_verdict is Verdict.TRUE) is vault_required, (
        equipment, vault.required_verdict
    )


def test_an_equipment_only_order_BILLS_AND_APPROVES(world):
    """The money end of ruling 1: a bundle, no vault, a real line, nothing blocking."""
    db, cid, _uid = world
    v = _vals(db, cid, "lowering device and grass")
    assert v.get("vault") is None, v
    ap = _assess(db, cid, v)
    assert [(l.kind, l.description) for l in ap.lines] == [
        ("equipment", "Lowering Device & Grass")
    ], ap.lines
    assert list(ap.blockers) == [], ap.blockers


def test_an_order_with_NEITHER_still_blocks(world):
    """⚠️ THE CONTROL ON RULING 1, AND WITHOUT IT "complete with no vault" WOULD BE A
    LICENCE TO APPROVE NOTHING. Relaxing the requirement must not make an empty order
    approvable — and it does not, because the blocker that catches it is about LINES
    rather than about fields."""
    db, cid, _uid = world
    ap = _assess(db, cid, _vals(db, cid, ""))
    assert [b for b in ap.blockers if "Nothing to bill" in b], ap.blockers


# ── ruling 1: the pill that answers the question ────────────────────────────

def test_the_vault_pills_OFFER_the_decline(world):
    """*"a pill 'No vault — equipment only' answers it."* Offered on every tenant,
    whatever the order history holds."""
    db, cid, _uid = world
    resolved = resolve_schema(
        vault_product_id=None, personalization_config=None,
        platform_fields=template_for(SALES_ORDER), answers={},
    )
    ps = pills_for(db, tenant_id=cid, field_id=VAULT_FIELD_ID, values={},
                   resolved_fields=resolved, today=date(2026, 11, 2))
    assert [p for p in ps if p.value == VAULT_NONE_ANSWER], [p.value for p in ps]
    assert [p.label for p in ps if p.value == VAULT_NONE_ANSWER] == [VAULT_NONE_LABEL]
    # ⚠️ LAST, BY DESIGN. The habit-ranked vaults are what the office picks nine times
    # in ten; a decline at the head of the list makes the common case travel furthest.
    assert ps[-1].value == VAULT_NONE_ANSWER, [p.value for p in ps]


def test_the_decline_ANSWERS_the_question_and_bills_nothing(world):
    """⚠️ IT HAS TO BE AN ANSWER RATHER THAN A BLANK, AND THAT IS WHY A RESERVED VALUE
    EXISTS. `vault` leaves `missing` either when a bundle is named or when the field is
    ANSWERED — and a director clicking this has named no bundle yet, so without a value
    to write the pill could only be a no-op."""
    db, cid, uid = world
    sp = db.begin_nested()
    try:
        row = session_service.start(db, company_id=cid, user_id=uid)
        session_service.set_text(db, row.id, company_id=cid, user_id=uid,
                                 text="order for lakeshore")
        before = session_service.read_state(db, row.id, company_id=cid, user_id=uid)
        assert "vault" in before["missing"], before["missing"]

        session_service.answer(db, row.id, company_id=cid, user_id=uid,
                               field_id="vault", value=VAULT_NONE_ANSWER)
        after = session_service.read_state(db, row.id, company_id=cid, user_id=uid)
        assert "vault" not in after["missing"], after["missing"]

        # ⚠️ AND THE ROW READS THE LABEL, NOT THE SENTINEL. `label_for` gained a
        # `reserved` lookup for exactly this: `vault` declares no options, so it
        # returned early and the row rendered "none" — the same defect as the Service
        # row reading `funeral_home` on James's 2026-10-12 walk.
        vault_row = next(r for r in after["surface"]["rows"] if r["row_id"] == "vault")
        assert vault_row["value"] == VAULT_NONE_LABEL, vault_row
        assert vault_row["state"] == "done", vault_row
    finally:
        sp.rollback()


def test_the_decline_BUILDS_NO_LINE_and_names_no_product(world):
    """⚠️ WITHOUT THIS THE SENTINEL WOULD REACH THE PRODUCT LOOKUP and block with
    *"none has no product on this tenant"* — a sentence about a product the director
    never named, on an order where they had just said there is no vault."""
    db, cid, _uid = world
    answers = {"funeral_home": "Lakeshore Funeral Chapel",
               "vault": VAULT_NONE_ANSWER,
               "cemetery_equipment": "full_equipment"}
    ap = _assess(db, cid, answers)
    assert [l.kind for l in ap.lines] == ["equipment"], ap.lines
    assert not [b for b in ap.blockers if "none" in b.lower()], ap.blockers


def test_the_decline_IS_THE_ONLY_NON_PRODUCT_THE_VAULT_ACCEPTS(world):
    """⚠️ THE EXEMPTION, BOUNDED. `admits_name` lets exactly one string through that is
    not a vault-form product; every other non-vault is still refused, which is the
    acceptance rule from ruling A unchanged."""
    db, cid, _uid = world
    from app.services.capture.vault_form import FormResolver, admits_name

    forms = FormResolver(db, cid)
    assert admits_name(forms, VAULT_NONE_ANSWER)
    for not_a_vault in ("Graveside Chairs", "Lowering Device", "Full Equipment",
                        "Vault Placer", "Extra Chairs (Over 8)", "Arlington"):
        assert not admits_name(forms, not_a_vault), not_a_vault


# ── ruling 2: a family ASKS, it never picks a price ─────────────────────────

def test_a_bare_lowering_device_ASKS_WITH_BOTH_PILLS(world):
    """*"'lowering device' alone → Opas asks, two pills: 'Device only' / 'Device &
    grass'. Never map it to either price silently."*

    ⚠️ THE LABELS ARE JAMES'S OWN AND ARE SHORTER THAN THE PACKAGE NAMES. "Lowering
    Device Only" and "Lowering Device & Grass" side by side differ in their last word
    and read as one thing written twice; "Device only" and "Device & grass" read as two
    answers to one question.
    """
    db, cid, _uid = world
    ex = extract_text(db, tenant_id=cid, text="order for lakeshore lowering device")
    assert ex.values.get("cemetery_equipment") is None, dict(ex.values)
    picks = [p for p in ex.picks if p.field_id == "cemetery_equipment"]
    assert len(picks) == 1, [(p.field_id, p.options) for p in ex.picks]
    assert picks[0].options == (
        ("lowering_device_only", "Device only"),
        ("lowering_device_and_grass", "Device & grass"),
    ), picks[0].options
    assert picks[0].discriminator == "package"
    # ⚠️ AND THE WORDS ARE CLAIMED, NOT HELD. A question about a phrase Opas is
    # simultaneously reporting it could not understand is two messages about one word.
    assert list(ex.unrecognized) == [], ex.unrecognized


@pytest.mark.parametrize("typed,expected", [
    ("device only", "lowering_device_only"),
    ("lowering device only", "lowering_device_only"),
    ("just the device", "lowering_device_only"),
    ("lowering device and grass", "lowering_device_and_grass"),
    ("lowering device & grass", "lowering_device_and_grass"),
    ("grass and lowering device", "lowering_device_and_grass"),
])
def test_the_UNAMBIGUOUS_phrasings_still_resolve_directly(world, typed, expected):
    """*"'lowering device and grass' / 'device only' resolve directly as now."* The
    family table runs only on what `_EQUIPMENT` declined, so these never reach it."""
    db, cid, _uid = world
    v = _vals(db, cid, typed)
    assert v.get("cemetery_equipment") == expected, v


def test_choosing_a_pill_SETTLES_the_package_and_bills_it(world):
    """End to end: the question, the choice, the line. ⚠️ THE PRICE IS ASSERTED, because
    the whole reason this asks is that the two packages cost different amounts — a test
    that stopped at the slug would not notice the two being swapped."""
    db, cid, uid = world
    sp = db.begin_nested()
    try:
        row = session_service.start(db, company_id=cid, user_id=uid)
        session_service.set_text(db, row.id, company_id=cid, user_id=uid,
                                 text="order for lakeshore lowering device")
        state = session_service.read_state(db, row.id, company_id=cid, user_id=uid)
        assert [p["field_id"] for p in state["pending_picks"]] == ["cemetery_equipment"]

        session_service.choose(db, row.id, company_id=cid, user_id=uid,
                               field_id="cemetery_equipment", index=1)
        after = session_service.read_state(db, row.id, company_id=cid, user_id=uid)
        assert after["values"].get("cemetery_equipment") == "lowering_device_only"
        assert after["pending_picks"] == [], after["pending_picks"]

        ap = _assess(db, cid, dict(after["values"]))
        billed = [(l.description, str(l.unit_price)) for l in ap.lines]
        assert billed == [("Lowering Device Only", "140.00")], billed
    finally:
        sp.rollback()


def test_the_OTHER_pill_bills_the_OTHER_price(world):
    """⚠️ THE DISCRIMINATING HALF. The test above would pass against a pick whose two
    options both pointed at the cheaper package; this is what makes the pair evidence
    that the choice carries."""
    db, cid, uid = world
    sp = db.begin_nested()
    try:
        row = session_service.start(db, company_id=cid, user_id=uid)
        session_service.set_text(db, row.id, company_id=cid, user_id=uid,
                                 text="order for lakeshore lowering device")
        session_service.choose(db, row.id, company_id=cid, user_id=uid,
                               field_id="cemetery_equipment", index=2)
        after = session_service.read_state(db, row.id, company_id=cid, user_id=uid)
        ap = _assess(db, cid, dict(after["values"]))
        billed = [(l.description, str(l.unit_price)) for l in ap.lines]
        assert billed == [("Lowering Device & Grass", "185.00")], billed
    finally:
        sp.rollback()


def test_the_two_packages_REALLY_DO_COST_DIFFERENT_AMOUNTS(world):
    """⚠️ THE PREMISE OF RULING 2, ASSERTED. *"Never map it to either price silently"*
    is a rule about money; if the two packages cost the same, asking would be
    ceremony and the 2026-10-13 form-default ruling would apply instead — that
    exception exists precisely because the two vault readings cost the same."""
    db, cid, _uid = world
    prices = dict(db.execute(sql(
        "SELECT name, price FROM products WHERE company_id = :t AND name LIKE 'Lowering%'"
    ), {"t": cid}).all())
    assert len(prices) == 2, prices
    assert len(set(prices.values())) == 2, prices
