"""Every captured answer lands in a row, or is shown as a conflict. Nothing vanishes.

⚠️ WALK NOTE, James, production 2026-10-13 13:48: "nameplate only" on a Monticello
disappeared without a trace — no row (correct, the vault offers no personalization)
and not in Not Understood either (not correct). On a real call that is exactly what
a director needs to be told.

⚠️ IT IS NOT THE `UnpermittedAnswer` CASE, WHICH ALREADY WORKED. That one fires when
a vault offers a DIFFERENT set and `capture.evaluate` raises; this one is
availability NOT_OFFERED, where the field is filtered into `not_applicable` and the
answer is simply ignored. Two different silences, and only the louder one had a
handler.

⚠️ THE GENERAL RULE IS THE TEST THAT MATTERS. Rather than one case, the invariant:
for every key the extractor captured, the field is either ANSWERED (so a row shows
it) or named in a CONFLICT. An answer in neither is an answer the office typed and
the pane never mentioned.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.services.capture.typed_extraction import evaluate_typed, extract_text


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


@pytest.fixture(scope="module")
def the_vaults_differ(db, tenant):
    """⚠️ THE CASE NEEDS A VAULT THAT OFFERS NOTHING AND ONE THAT OFFERS SOMETHING.

    Measured 2026-10-13: a Monticello puts `personalization` in `not_applicable`; a
    Continental 34" puts it in `answered`. Without both, a test could not tell "the
    conflict fires" from "the conflict always fires".
    """
    def where(vault_phrase):
        ex = extract_text(
            db, tenant_id=tenant, text=f"order for riverside {vault_phrase} nameplate only"
        )
        _r, st, _c = evaluate_typed(db, tenant_id=tenant, answers=dict(ex.values))
        if "personalization" in st.not_applicable:
            return "not_applicable"
        if "personalization" in st.answered:
            return "answered"
        return "other"

    assert where("monticello burial vault") == "not_applicable", (
        "the Monticello no longer reports personalization as not applicable — "
        "this suite's premise is gone"
    )
    assert where("continental 34") == "answered", (
        "the Continental 34in no longer accepts a nameplate; the positive control "
        "is gone and the conflict tests would pass vacuously"
    )
    return True


def _extract(db, tenant, body):
    ex = extract_text(db, tenant_id=tenant, text=body)
    _r, st, conflicts = evaluate_typed(db, tenant_id=tenant, answers=dict(ex.values))
    return ex, st, conflicts


# ── the case James hit ──────────────────────────────────────────────────────

def test_a_nameplate_on_a_vault_that_offers_none_is_REPORTED(db, tenant, the_vaults_differ):
    _ex, _st, conflicts = _extract(
        db, tenant, "order for riverside monticello burial vault nameplate only"
    )
    personal = [c for c in conflicts if c.field_id == "personalization"]
    assert personal, f"the answer vanished; conflicts={conflicts}"


def test_the_message_names_the_vault_and_what_it_does_not_offer(db, tenant, the_vaults_differ):
    # ⚠️ THE WORDING IS THE DELIVERABLE. "personalization is not applicable" tells a
    # director nothing; the vault's name and the thing they asked for is the sentence
    # James wrote in the dispatch.
    _ex, _st, conflicts = _extract(
        db, tenant, "order for riverside monticello burial vault nameplate only"
    )
    msg = next(c.message for c in conflicts if c.field_id == "personalization")
    assert "Monticello Burial Vault" in msg, msg
    assert "nameplate" in msg.lower(), msg
    assert "offer" in msg.lower(), msg


def test_a_vault_that_DOES_offer_it_raises_no_conflict(db, tenant, the_vaults_differ):
    # ⚠️ THE POSITIVE CONTROL. A build that reported every personalization answer as
    # a conflict would pass both tests above.
    ex, st, conflicts = _extract(
        db, tenant, "order for riverside continental 34 nameplate only"
    )
    assert ex.values.get("personalization") == "nameplate_only", ex.values
    assert "personalization" in st.answered, sorted(st.answered)
    assert not [c for c in conflicts if c.field_id == "personalization"], conflicts


def test_no_personalization_typed_means_no_conflict(db, tenant, the_vaults_differ):
    _ex, _st, conflicts = _extract(
        db, tenant, "order for riverside monticello burial vault"
    )
    assert not conflicts, conflicts


# ── the general rule ────────────────────────────────────────────────────────

SENTENCES = [
    # James's exact walk sentence
    "order for hopkins monticello with full equipment going to St. Mary's "
    "section 4 service Friday 11 am nameplate only last name Keegan",
    # the same with a vault that accepts the nameplate
    "order for hopkins continental 34 going to oakwood nameplate only",
    # personalization on a vault offering nothing, plus more detail
    "order for riverside monticello burial vault nameplate only cross symbol",
    # a plain order with no personalization at all
    "order for riverside monticello burial vault going to oakwood section 4",
    # two personalization answers, one of them unavailable
    "order for riverside monticello burial vault legacy print",
]


@pytest.mark.parametrize("body", SENTENCES)
def test_EVERY_CAPTURED_ANSWER_IS_SHOWN_SOMEWHERE(db, tenant, the_vaults_differ, body):
    """The invariant, as a property over whole sentences.

    ⚠️ A CAPTURED ANSWER IS EITHER ANSWERED OR CONFLICTED, with nothing in between.
    `answered` is what the surface renders into a row; a conflict is what the pane
    shows as a problem. A key in neither set was read off the director's sentence and
    then never mentioned again — which is the defect this file exists for, and it is
    invisible unless you compare the two collections.
    """
    ex, st, conflicts = _extract(db, tenant, body)
    shown = set(st.answered) | {c.field_id for c in conflicts}
    dropped = set(ex.values) - shown
    assert not dropped, (
        f"captured and never shown: {sorted(dropped)} "
        f"(values={sorted(ex.values)}, answered={sorted(st.answered)}, "
        f"conflicts={[c.field_id for c in conflicts]})"
    )


def test_the_invariant_can_FAIL_so_it_is_worth_asserting(db, tenant, the_vaults_differ):
    """⚠️ THE INVARIANT'S OWN POSITIVE CONTROL, because an invariant that cannot fail
    is decoration. This reproduces the pre-fix state by hand — evaluating WITHOUT the
    not-applicable sweep — and shows the comparison catches it."""
    ex = extract_text(
        db, tenant_id=tenant, text="order for riverside monticello burial vault nameplate only"
    )
    _r, st, _c = evaluate_typed(db, tenant_id=tenant, answers=dict(ex.values))
    # with NO conflicts counted, the nameplate is dropped — which is what James saw
    dropped_without_conflicts = set(ex.values) - set(st.answered)
    assert "personalization" in dropped_without_conflicts, dropped_without_conflicts
