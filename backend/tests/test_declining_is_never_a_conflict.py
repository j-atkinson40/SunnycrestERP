""""none" answers the question. It never contradicts the vault.

James's ruling, 2026-10-16: *"'No personalization' / 'none' is always an acceptable
answer, on any vault, and never a conflict. On a vault with no personalization options it
simply answers the question."*

⚠️ WHAT WENT WRONG, AND WHY IT IS A BUG RATHER THAN A DESIGN CHOICE. Two separate places
enforce a vault's personalization availability, and they disagreed about declining:

    missing._reject_unpermitted        a vault with a CONFIGURED permitted set.
                                       Already exempted `ANSWER_NONE`, with the comment
                                       "Declining is permitted wherever the question is
                                       asked at all."

    typed_extraction, the loop over    a vault where the question does not APPLY at all
    `state.not_applicable`             (availability NOT_OFFERED). Raised a conflict for
                                       ANY answer, including "none".

One rule, two paths, and only one of them had it. Measured on production 2026-10-16: the
step-3 verification walk was refused with *"Monticello Burial Vault doesn't offer None. It
offers no personalization."* — the engine arguing with a director who had just agreed
with it.

⚠️ THE FIELD STAYS `not_applicable`, DELIBERATELY. The vault genuinely offers nothing, so
no row should claim a personalization that will not be made and `assess` must build no
line. What changed is only that the decline stops BLOCKING.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.services.capture.typed_extraction import EXTRACTOR, evaluate_typed
from app.services.personalization.questions import ANSWER_NONE

#: The real tenant whose catalogue has a vault with no personalization. Using Sunnycrest's
#: own data rather than a fixture is the point: this bug was invisible to every synthetic
#: tenant because the synthetic vaults all offer something.
TENANT_SLUG = "sunnycrest"
VAULT = "Monticello Burial Vault"


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def tenant(db) -> str:
    t = db.execute(
        sql_text("SELECT id FROM companies WHERE slug = :s"), {"s": TENANT_SLUG}
    ).scalar()
    if not t:
        pytest.skip(f"{TENANT_SLUG} is not seeded on this database")
    return t


def _conflicts_for(db, tenant: str, answers: dict):
    _res, state, conflicts = evaluate_typed(db, tenant_id=tenant, answers=dict(answers))
    return state, conflicts


def test_the_vault_really_does_offer_no_personalization(db, tenant):
    """⚠️ THE PRECONDITION, ASSERTED. Every test below is about a vault that offers
    nothing; if Sunnycrest's catalogue changed so the Monticello offered something, they
    would all pass while testing a case that no longer exists.
    """
    state, _conflicts = _conflicts_for(db, tenant, {"vault": VAULT})
    assert "personalization" in state.not_applicable, (
        f"{VAULT} now offers personalization on this database — these tests no longer "
        "cover the no-options case"
    )


def test_declining_on_a_vault_with_no_options_is_not_a_conflict(db, tenant):
    _state, conflicts = _conflicts_for(
        db, tenant, {"vault": VAULT, "personalization": ANSWER_NONE}
    )
    assert [c.message for c in conflicts] == [], (
        "declining produced a conflict; this is the production refusal"
    )


def test_james_phrase_typed_verbatim_produces_no_conflict(db, tenant):
    """"monticello no personalization" — the words, through the real extractor."""
    ex = EXTRACTOR.extract_line(
        db, tenant_id=tenant,
        line="order for hopkins monticello no personalization", answers={},
    )
    assert ex.values.get("personalization") == ANSWER_NONE, (
        f"the phrase did not extract as a decline: {ex.values}"
    )
    assert list(ex.unrecognized) == [], ex.unrecognized

    _state, conflicts = _conflicts_for(db, tenant, dict(ex.values))
    assert [c.field_id for c in conflicts] == []


def test_choosing_something_the_vault_does_not_offer_IS_still_a_conflict(db, tenant):
    """⚠️ THE POSITIVE CONTROL, AND WITHOUT IT THIS FILE IS SATISFIED BY DELETING THE
    CONFLICT LOOP ENTIRELY. Declining is permitted; ASKING FOR something the vault cannot
    do is still refused, with the vault named.
    """
    _state, conflicts = _conflicts_for(
        db, tenant, {"vault": VAULT, "personalization": "nameplate_only"}
    )
    assert [c.field_id for c in conflicts] == ["personalization"], (
        "a real unavailable choice stopped being reported"
    )
    assert VAULT in conflicts[0].message
    assert "Nameplate Only" in conflicts[0].message


def test_a_complete_order_declining_personalization_is_APPROVABLE(db, tenant):
    """James's test: "monticello no personalization" reaches an approvable Review.

    ⚠️ ASSERTED THROUGH `assess`, which is the function the Approve button is gated on and
    the one `approve()` re-checks inside its own transaction. A test that only counted
    conflicts would not prove the Review is actually approvable.
    """
    from app.services.capture.approval import assess

    answers = {
        "funeral_home": "Hopkins Funeral Home",
        "deceased_name": "declining walker",
        "vault": VAULT,
        "cemetery": "St. Mary's Cemetery",
        "service_date": "2026-10-23",
        "service_time": "10:00",
        "service_location": "graveside",
        "cemetery_equipment": "full_equipment",
        "personalization": ANSWER_NONE,
    }
    state, conflicts = _conflicts_for(db, tenant, answers)
    assert [c.message for c in conflicts] == []

    missing_labels = {
        f.label
        for f in state.resolved_fields
        if f.field_id in state.missing
    }
    assessment = assess(
        db, tenant_id=tenant, answers=answers,
        missing_labels=missing_labels, open_picks=(), conflicts=conflicts,
    )
    assert assessment.ready is True, assessment.blockers
    assert assessment.total > Decimal("0.00")

    # ⚠️ AND NO PERSONALIZATION LINE IS BILLED. The decline must not become a line item
    # just because it stopped blocking.
    descriptions = [l.description for l in assessment.lines]
    assert not any("nameplate" in d.lower() or "legacy" in d.lower() for d in descriptions), (
        f"a personalization line was billed on a declined order: {descriptions}"
    )


def test_the_approve_effect_line_appears_for_a_declined_order(db, tenant):
    """The Review's promise is composed for this order too — it was None before, because
    an unapprovable order gets no promise."""
    from app.services.capture.approval import assess, describe_approve_effect

    answers = {
        "funeral_home": "Hopkins Funeral Home",
        "deceased_name": "declining walker",
        "vault": VAULT,
        "cemetery": "St. Mary's Cemetery",
        "service_date": "2026-10-23",
        "service_time": "10:00",
        "service_location": "graveside",
        "cemetery_equipment": "full_equipment",
        "personalization": ANSWER_NONE,
    }
    state, conflicts = _conflicts_for(db, tenant, answers)
    missing_labels = {
        f.label for f in state.resolved_fields if f.field_id in state.missing
    }
    assessment = assess(
        db, tenant_id=tenant, answers=answers,
        missing_labels=missing_labels, open_picks=(), conflicts=conflicts,
    )
    effect = describe_approve_effect(db, tenant, answers, assessment)
    assert effect is not None, "an approvable order still got no effect line"
    assert effect.startswith("Confirms the order · Delivered Fri Oct 23"), effect


def test_declining_the_EQUIPMENT_question_is_also_not_a_conflict(db, tenant):
    """⚠️ THE RULING IS ABOUT THE VALUE, NOT THE FIELD. "none" is a decline wherever it
    appears, so the exemption is keyed on `ANSWER_NONE` rather than on
    `field_id == "personalization"`. `cemetery_equipment` carries its own `none` option
    and must behave the same way if it ever becomes not-applicable.
    """
    import inspect

    from app.services.capture import typed_extraction

    src = inspect.getsource(typed_extraction.evaluate_typed)
    assert 'if str(answers[field_id]) == ANSWER_NONE:' in src, (
        "the exemption is no longer keyed on the VALUE; a field-specific check would "
        "leave every other decline blocking"
    )
