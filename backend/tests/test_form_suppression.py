"""The personalization question applies only to vault forms — R4, 2026-10-07.

⚠️ THE BUG THIS CLOSES WAS FOUND BY THE AVAILABILITY DRY RUN, NOT BY A TEST. Writing
availability to dev and then evaluating a few vaults showed urn `P300` and infant
`LC-19` both reporting the vault personalization question as `missing`. An order for
a lowering device could never be completed, and no test disagreed — because every
capture test used a burial vault.

⚠️ AVAILABILITY COULD NOT HAVE FIXED IT, which is why the fix is a new fact rather
than more data. NOT_CONFIGURED correctly means "ask" — a licensee who has said
nothing has said nothing — and nobody had configured an urn. The engine was right
about availability and wrong about the product: an urn has no carapace, and no
licensee configuration can change that. The FORM is what makes the question
meaningless, and it was not in the context at all.

⚠️ TESTED THROUGH `resolve_and_evaluate`, BY RULING. Every case here goes through the
production seam against the real catalog, so the form reaches the engine the way it
does on a call rather than being handed in by the test.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.services.call_extraction_service import resolve_and_evaluate
from app.services.personalization.questions import (
    PERSONALIZABLE_FORMS,
    QUESTION_PERSONALIZATION,
)


@pytest.fixture(scope="module")
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def _phrase_for(db, sku: str) -> str:
    """The display name of a SKU, used as the spoken phrase.

    ⚠️ READ FROM THE CATALOG, NOT TYPED. A hardcoded phrase that stopped resolving
    would make these tests pass vacuously — an unresolved phrase yields
    `vault_form=None`, which is INDETERMINATE, which is "not missing", which is what
    most of these tests assert.
    """
    name = db.execute(text(
        "SELECT display_name FROM product_variant_templates WHERE sku = :s"
    ), {"s": sku}).scalar()
    assert name, f"{sku} is not in the catalog — this test is measuring nothing"
    return name


def _where(state) -> str:
    q = QUESTION_PERSONALIZATION
    if q in state.answered:
        return "answered"
    if q in state.missing:
        return "missing"
    if q in state.unanswered_optional:
        return "unanswered_optional"
    if q in state.not_applicable:
        return "not_applicable"
    if q in state.indeterminate:
        return "indeterminate"
    return "NO SET"


def test_the_permitted_forms_are_the_two_vault_forms():
    """⚠️ PINS THE RULING ITSELF, so widening it is a visible edit rather than a
    behaviour change someone notices later."""
    assert PERSONALIZABLE_FORMS == frozenset({"burial_vault", "urn_vault"})


@pytest.mark.parametrize("sku,form", [
    ("BV-WBR", "burial_vault"),
    ("UV-BTRI", "urn_vault"),
])
def test_a_vault_form_IS_asked_the_question(db, sku, form):
    """⚠️ THE POSITIVE CONTROL, AND IT RUNS BEFORE THE SUPPRESSION CASES. Every test
    below asserts the question is NOT asked; all of them would pass if the form gate
    suppressed it everywhere. These two require it to still fire on a real vault."""
    _, state = resolve_and_evaluate(db, {"vault_type": _phrase_for(db, sku)})

    assert _where(state) != "not_applicable", (
        f"{sku} is a {form} and the question was suppressed — the gate is too wide"
    )


# ⚠️ ONE UNAMBIGUOUS SKU PER SUPPRESSED FORM, CHOSEN BY MEASUREMENT. My first pass
# used `P300` and `GL-STD`; both have display names the resolver cannot resolve
# ("Cream & Gold" is shared with P310, "Graveliner" matches five variants), so they
# landed in `indeterminate` and the test failed for a reason unrelated to the form
# gate. Enumerating the catalog gave a resolvable phrase for every form.
@pytest.mark.parametrize("sku,form", [
    ("P363", "urn"),            # 'Victorian'
    ("CE-LD", "equipment"),     # 'Lowering Device'
    ("CE-CH", "equipment"),     # 'Graveside Chairs'
    ("GL-34", "grave_liner"),   # 'Graveliner 34"'
    ("LC-19", "infant"),        # 'Loved & Cherished 19"'
])
def test_a_non_vault_form_is_NOT_asked_and_is_never_missing(db, sku, form):
    """One case per suppressed form, by ruling.

    ⚠️ `never missing` IS THE LOAD-BEARING HALF. `not_applicable` and `missing` are
    both "the question has no answer", and only the second blocks completion. Before
    R4 every one of these was `missing`.
    """
    _, state = resolve_and_evaluate(db, {"vault_type": _phrase_for(db, sku)})

    assert QUESTION_PERSONALIZATION not in state.missing, (
        f"{sku} ({form}) reports the vault personalization question as MISSING, so an "
        f"order for it can never be completed"
    )
    assert _where(state) == "not_applicable", f"{sku} landed in {_where(state)!r}"


def test_an_equipment_only_order_is_completable(db):
    """⚠️ THE WHOLE POINT, STATED AS THE OUTCOME RATHER THAN AS A SET MEMBERSHIP.

    A director orders a lowering device and nothing else. Every required field is
    answered. The order must be completable — and before R4 it could not be, because
    a question about a vault carapace was reported as a gap on an order with no vault.
    """
    answers = {
        "vault_type": _phrase_for(db, "CE-LD"),
        "funeral_home_name": "Hopkins Funeral Home",
        "deceased_name": "John Michael Smith",
        "cemetery_name": "St Mary's",
        "cemetery_city": "Auburn",
        "burial_date": "2026-10-09",
        "service_date": "2026-10-08",
        "service_time": "14:00",
        "service_location": "church",
        "grave_location": "Section C, Lot 14",
    }

    _, state = resolve_and_evaluate(db, answers)

    assert QUESTION_PERSONALIZATION not in state.missing
    assert state.is_complete, f"equipment-only order is incomplete: missing={state.missing}"


def test_an_UNRESOLVED_phrase_is_indeterminate_not_suppressed(db):
    """⚠️ THE DISCRIMINATING CASE, AND IT IS THE ONE A SIMPLER FIX WOULD HAVE BROKEN.

    Reading an unknown form as "not a vault form" would mark the question
    not-applicable on every order before a vault is named — and `not_applicable` is a
    claim that we ESTABLISHED it does not apply. An unresolved or ambiguous phrase
    must stay INDETERMINATE: we do not know yet.
    """
    _, state = resolve_and_evaluate(db, {"vault_type": "something nobody sells"})

    assert _where(state) == "indeterminate", (
        f"an unresolved vault phrase produced {_where(state)!r}; unknown is not "
        f"the same as not-applicable"
    )


@pytest.mark.parametrize("phrase,why", [
    ("Cream & Gold", "shared by P300 and P310 — two urns"),
    ("Graveliner", "matches GL-34/38/SS/STD and UV-GL — SPANS grave_liner and urn_vault"),
])
def test_an_ambiguous_phrase_stays_indeterminate_even_across_forms(db, phrase, why):
    """⚠️ THESE TWO WERE MY FAILED FIXTURES AND THEY EARNED THEIR OWN TEST.

    `Graveliner` is the case the None-on-ambiguous rule exists for: its candidate set
    spans `grave_liner` AND `urn_vault`, so a form taken from `candidates[0]` would be
    whichever the sort happened to put first — suppressing the question on an urn
    vault or asking it on a grave liner, depending on nothing.
    """
    _, state = resolve_and_evaluate(db, {"vault_type": phrase})

    assert _where(state) == "indeterminate", f"{phrase!r} ({why}) -> {_where(state)!r}"


def test_an_AMBIGUOUS_phrase_is_also_indeterminate(db):
    """"Bronze Triune" matches BV-BTRI and UV-BTRI — one burial, one urn.

    ⚠️ BOTH ARE PERMITTED FORMS, SO THIS WOULD PASS EITHER WAY IF THE FORM WERE TAKEN
    FROM `candidates[0]`. It is here for the case it guards rather than the case it
    exercises: an ambiguous set CAN span a permitted and a suppressed form, and
    `_resolved_form` returns None whenever the resolver refused to pick, so no form is
    ever read from a product the resolver would not commit to.
    """
    _, state = resolve_and_evaluate(db, {"vault_type": "Bronze Triune"})

    assert _where(state) == "indeterminate"
