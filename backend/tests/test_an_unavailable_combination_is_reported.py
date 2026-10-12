"""Saying a combination the vault does not allow REPORTS it. It used to 500.

⚠️ THIS FILE EXISTS BECAUSE A LIVE HTTP REQUEST ON DEV RETURNED
`Internal Server Error`, AND 477 GREEN TESTS DID NOT. Measured 2026-10-12 against
uvicorn on localhost with the `testco` tenant: typing

    "start an order for Hopkins, Mary Smith, Continental 34, tent only,
     nameplate and vinyl, cross, …"

made the extractor produce `personalization='nameplate_and_lifes_reflections'`
against a vault whose availability permits only `nameplate_only`. `capture.evaluate`
raised `UnpermittedAnswer`, nothing in `app/` caught it, and the pane died
mid-sentence.

⚠️ WHY EVERY TEST MISSED IT — AND THE FIRST ANSWER I GAVE WAS WRONG. This paragraph
read: *"The session tests build a BARE tenant … With no vault resolving, availability
never narrows."* Measured afterwards, on a tenant of one `companies` row: the catalog,
the 56 aliases and the availability config are all PLATFORM-level, `Continental 34`
resolves, availability narrows to `['nameplate_only']`, and THIS CONFLICT ARISES.
A bare tenant would have caught this defect.

What actually hid it is that no session test ever typed a phrase resolving a vault to
ONE variant. The inputs were `tent only`, `nameplate only`, `years only`, `full
setup`, and `Continental` — ambiguous, so a pick rather than a resolution. Every
phrase stopped short of the same layer, and a missing INPUT is not auditable the way
a missing fixture is: it looks like a test suite with a lot of tests in it.

See `docs/investigations/2026-10-12-the-bare-tenant-gap.md`.

⚠️ AND THE RAISE WAS DOCUMENTED AS EXPECTED. `test_vinyl_is_what_the_office_says.py`
carried a comment saying `evaluate_typed` raises `UnpermittedAnswer` on the
Continental 34 — written while measuring, entirely accurate, and read by nobody as
"therefore the live path 500s". A raise whose only reader is a test comment is an
unhandled error on every real path.

⚠️ THIS FILE REQUIRES THE SEEDED `testco` TENANT and says so loudly rather than
skipping, because a skip here would restore exactly the blindness above.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.services.capture.typed_extraction import (
    EXTRACTOR,
    Conflict,
    evaluate_typed,
)

#: ⚠️ THE MEASURED PAIR, NOT AN INVENTED ONE. The Continental 34" permits
#: `nameplate_only` alone; "nameplate and vinyl" resolves to
#: `nameplate_and_lifes_reflections`. Both halves were read off the live tenant.
VAULT = "Continental 34"
UNAVAILABLE = "nameplate and vinyl"


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


def _answers(db, tenant, lines):
    answers: dict = {}
    for line in lines:
        ex = EXTRACTOR.extract_line(db, tenant_id=tenant, line=line, answers=answers)
        answers.update(ex.values)
    return answers


# ── the controls, READ FIRST ────────────────────────────────────────────

def test_the_vault_really_does_resolve_on_this_tenant(db, tenant):
    """⚠️ WITHOUT THIS, EVERY ASSERTION BELOW IS VACUOUS. If "Continental 34" does not
    resolve, no availability narrows, nothing is unpermitted, and a test asserting
    "no conflict" would pass against a tenant with no products at all."""
    answers = _answers(db, tenant, [VAULT])
    assert answers.get("vault"), f"{VAULT!r} captured nothing"
    _, state, _ = evaluate_typed(db, tenant_id=tenant, answers=answers)
    assert "vault" in state.answered, (
        f"{VAULT!r} did not resolve to a single product — the conflict this file "
        f"tests cannot arise, so the file is measuring nothing"
    )


def test_the_combination_really_is_unavailable_on_this_vault(db, tenant):
    """⚠️ THE SECOND HALF OF THE PRECONDITION. If this vault ever starts permitting
    `nameplate_and_lifes_reflections`, the conflict test below would pass for the
    wrong reason — no conflict, rather than a conflict handled."""
    answers = _answers(db, tenant, [VAULT, UNAVAILABLE])
    assert answers["personalization"] == "nameplate_and_lifes_reflections"
    _, state, conflicts = evaluate_typed(db, tenant_id=tenant, answers=answers)
    assert conflicts, (
        "the vault now permits this combination; this file's premise has expired"
    )


# ── the claim ───────────────────────────────────────────────────────────

def test_it_DOES_NOT_RAISE(db, tenant):
    """The whole defect, in one line."""
    answers = _answers(db, tenant, [VAULT, UNAVAILABLE])
    evaluate_typed(db, tenant_id=tenant, answers=answers)  # must not raise


def test_the_conflict_names_the_field_the_value_and_what_IS_available(db, tenant):
    """⚠️ ALL THREE, BECAUSE A DIRECTOR CANNOT ACT ON FEWER. "That is not available"
    without the alternatives is a dead end; the permitted set is what turns the
    message into a next step."""
    answers = _answers(db, tenant, [VAULT, UNAVAILABLE])
    _, _, conflicts = evaluate_typed(db, tenant_id=tenant, answers=answers)

    assert len(conflicts) == 1, conflicts
    c = conflicts[0]
    assert isinstance(c, Conflict)
    assert c.field_id == "personalization"
    assert c.value == "nameplate_and_lifes_reflections"
    assert "nameplate_only" in c.permitted, c.permitted
    assert c.message


def test_THE_REST_OF_THE_ORDER_SURVIVES(db, tenant):
    """⚠️ THE POINT OF REPORTING RATHER THAN RAISING. Before this, one impossible
    combination threw away every other field the director had said — the equipment,
    the name, the cemetery, all of it, because the exception came from the one call
    that produces the whole state."""
    answers = _answers(
        db, tenant, [VAULT, UNAVAILABLE, "tent only", "years only"]
    )
    _, state, conflicts = evaluate_typed(db, tenant_id=tenant, answers=answers)

    assert conflicts
    assert "vault" in state.answered
    assert "cemetery_equipment" in state.answered
    # ⚠️ AND THE SURFACE RENDERS, which is what the pane actually needs. A state that
    # evaluated but could not be rendered would still be a blank pane.
    assert state.resolved_fields


def test_the_conflicting_field_is_NOT_reported_as_answered(db, tenant):
    """⚠️ IT WAS WITHHELD FROM `evaluate`, so it must not appear as settled. A row
    reading "Nameplate and Life's Reflections" over a conflict message would be the
    response contradicting itself — the defect class that produced
    `not_configured`-vs-`answered` earlier in this arc."""
    answers = _answers(db, tenant, [VAULT, UNAVAILABLE])
    _, state, _ = evaluate_typed(db, tenant_id=tenant, answers=answers)
    assert "personalization" not in state.answered


def test_a_PERMITTED_combination_reports_NO_conflict(db, tenant):
    """⚠️ THE POSITIVE CONTROL ON THE CONFLICT LIST ITSELF. Without it, a function that
    returned a conflict for everything would satisfy every test above."""
    answers = _answers(db, tenant, [VAULT, "nameplate only"])
    _, state, conflicts = evaluate_typed(db, tenant_id=tenant, answers=answers)
    assert conflicts == (), conflicts
    assert "personalization" in state.answered
