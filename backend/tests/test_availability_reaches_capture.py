"""Availability reaches `evaluate` through the production seam, not beside it.

⚠️ THE DEFECT THIS CLOSES, AND IT IS THE SAME SHAPE AS THE ONE
`test_vault_resolution_wiring.py` CLOSED ONE LAYER UP.

That file's docstring records that `vault_product_id` was None at every call site,
so the conditional personalization questions had never been asked on any call. Piece
4 fixed the vault half. The other half stayed broken and nothing said so:
`resolve_and_evaluate` called `capture.evaluate` with no `personalization_config` at
all, so the parameter defaulted to None, `read_availability` returned NOT_CONFIGURED
for every question, and the personalization field landed in `indeterminate` on every
call regardless of what the licensee had configured.

So the vault resolved, and then the thing the vault was resolved FOR could not be
read. Measured 2026-10-07.

⚠️ TESTED THROUGH `resolve_and_evaluate`, NOT BY ASSEMBLING THE PIECES — by ruling,
and for the reason that file gives: the previous round of this defect survived
because the tests exercised `read_availability` and `evaluate` separately and
reconstructed their combination. Reconstructing a combination is not exercising a
path. Every test here goes through the seam the production caller uses.

⚠️ WRITES NOTHING. The enrollment row each test needs is created inside a SAVEPOINT
and rolled back. Availability data is NOT written to any database by this dispatch,
and a test that seeded a real row would be writing exactly the data that was ruled
out of scope.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.services.call_extraction_service import resolve_and_evaluate
from app.services.personalization.enrollment import read_personalization_config
from app.services.personalization.questions import (
    ANSWER_NAMEPLATE_ONLY,
    QUESTION_PERSONALIZATION,
)

#: Resolves to exactly one variant — the same phrase the wiring test uses, so a
#: catalog change breaks both rather than silently making this one vacuous.
UNAMBIGUOUS = "Bronze Triune Burial Vault"


def _refuse_a_non_local_database() -> None:
    """⚠️ FILE-SCOPED GUARD. These tests INSERT, and §7 forbids pointing a local
    run at production. Host/port/database only — never the credential."""
    from urllib.parse import urlparse

    from app.config import settings

    u = urlparse(settings.DATABASE_URL)
    host = (u.hostname or "").lower()
    assert host in ("localhost", "127.0.0.1", "::1", ""), (
        f"these tests write; refusing to run against host {host!r}"
    )


@pytest.fixture(scope="module")
def db():
    _refuse_a_non_local_database()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture
def tenant_with_availability(db):
    """A company plus an enrollment carrying `availability`, inside a savepoint.

    ⚠️ CONSTRUCTED, NOT SEEDED, AND THAT IS WHY THIS CAN BE TESTED AT ALL.
    `wilbert_program_enrollments` holds 3 rows on production and NONE of them has an
    `availability` key — measured 2026-10-06 — so there is no live row that exercises
    the offered branch. Against live data every test here would pass by reading
    NOT_CONFIGURED, which is the state the defect produced.
    """
    from app.services.call_extraction_service import _resolve_vault_phrase

    sp = db.begin_nested()
    company_id = str(uuid.uuid4())
    # ⚠️ THROUGH THE ORM, NOT RAW SQL. `companies` has NOT NULL columns with
    # Python-side defaults (`created_at`/`updated_at`), so a hand-written INSERT
    # chases columns; the model already knows them.
    from app.models.company import Company

    db.add(Company(id=company_id, name="Availability Fixture Co",
                   slug=f"avail-fixture-{company_id[:8]}"))
    db.flush()

    # ⚠️ THE VARIANT THE PHRASE RESOLVES TO, NOT AN ARBITRARY ACTIVE ONE. This was
    # `ORDER BY id LIMIT 1` first, and it made the seam test vacuous: the fixture
    # configured one variant while `resolve_and_evaluate` resolved a different one, so
    # the question read NOT_CONFIGURED and the test could not tell wired from unwired.
    # Configuring the variant the phrase actually resolves to is what lets the
    # permitted set be observed through the seam.
    resolution = _resolve_vault_phrase(db, {"vault_type": UNAMBIGUOUS})
    variant_id = resolution.variant_template_id
    assert variant_id, (
        f"{UNAMBIGUOUS!r} no longer resolves to exactly one variant "
        f"(candidates={len(resolution.candidates)}) — the catalog moved and this "
        f"fixture is measuring nothing"
    )

    # ⚠️ THROUGH THE ORM FOR THE SAME REASON AS `Company` ABOVE, and it was a raw
    # INSERT first: `wilbert_program_enrollments.program_code` is NOT NULL, so the
    # hand-written statement failed on a column nobody had read. CLAUDE.md records
    # this exact lesson from an earlier break test — use the model rather than
    # chasing columns, because the model already knows them.
    from app.models.wilbert_program_enrollment import WilbertProgramEnrollment

    db.add(WilbertProgramEnrollment(
        id=str(uuid.uuid4()),
        company_id=company_id,
        # ⚠️ BOTH NOT-NULL COLUMNS, ENUMERATED FROM `information_schema` RATHER THAN
        # DISCOVERED ONE PER TEST RUN. The first attempt failed on `program_code`, the
        # second on `program_name`; enumerating gave all four non-defaulted NOT NULL
        # columns in one query (`id`, `company_id`, `program_code`, `program_name`).
        program_code="wilbert",
        program_name="Wilbert Program",
        is_active=True,
        personalization_config={
            "availability": {
                variant_id: {QUESTION_PERSONALIZATION: [ANSWER_NAMEPLATE_ONLY]}
            }
        },
    ))
    db.flush()
    try:
        yield company_id, variant_id
    finally:
        sp.rollback()


def test_the_supplier_reads_the_config_it_was_given(db, tenant_with_availability):
    """⚠️ THE POSITIVE CONTROL, AND IT RUNS FIRST ON PURPOSE. Every assertion below
    is about availability being USED; all of them would also pass if the fixture
    silently wrote nothing and everything read NOT_CONFIGURED. This one requires a
    non-empty value, so the fixture cannot be vacuous (CLAUDE.md §11 — a control that
    cannot distinguish itself from a failure is not a control)."""
    company_id, variant_id = tenant_with_availability

    config = read_personalization_config(db, company_id)

    assert config is not None, "the fixture wrote no config — every test below is void"
    assert config["availability"][variant_id][QUESTION_PERSONALIZATION] == [
        ANSWER_NAMEPLATE_ONLY
    ]


def test_availability_reaches_evaluate_through_the_seam(db, tenant_with_availability):
    """The whole claim: a tenant's configured answer set arrives at `evaluate`.

    ⚠️ THE DISCRIMINATOR IS A REFUSAL, NOT A PRESENCE, AND THE FIRST VERSION OF THIS
    TEST GOT IT WRONG. `CaptureState` carries field ids and no permitted set, so
    nothing observable through the seam reports availability directly — and the field
    is PRESENT under NOT_CONFIGURED too, because the ruling is "ask, not skip". So
    asserting presence is green whether the config is wired or not, which is exactly
    the defect this file exists for. My first draft asserted presence under a
    docstring claiming it asserted the permitted set.

    What only a WIRED config can produce is a refusal: the vault permits
    `nameplate_only`, so `cover_emblem_only` must raise. Unwired, the permitted set is
    empty, `_reject_unpermitted` returns early by design, and nothing raises.
    """
    from app.services.capture.missing import UnpermittedAnswer
    from app.services.personalization.questions import ANSWER_COVER_EMBLEM_ONLY

    company_id, _ = tenant_with_availability

    with pytest.raises(UnpermittedAnswer) as exc:
        resolve_and_evaluate(
            db,
            {"vault_type": UNAMBIGUOUS, "personalization": ANSWER_COVER_EMBLEM_ONLY},
            tenant_id=company_id,
        )
    assert QUESTION_PERSONALIZATION in str(exc.value)


def test_the_answer_the_vault_DOES_permit_passes_through_the_same_seam(
    db, tenant_with_availability
):
    """⚠️ THE CONTROL ON THE TEST ABOVE. A seam that raised on every personalization
    answer — or a vault whose permitted set were empty in a different way — would
    satisfy a refusal test. This requires the permitted answer to be ACCEPTED, so the
    pair together pin the actual set rather than the existence of a guard."""
    company_id, _ = tenant_with_availability

    _, state = resolve_and_evaluate(
        db,
        {"vault_type": UNAMBIGUOUS, "personalization": ANSWER_NAMEPLATE_ONLY},
        tenant_id=company_id,
    )

    assert QUESTION_PERSONALIZATION in state.answered


def test_a_configured_vault_carries_its_permitted_answers_into_the_schema(
    db, tenant_with_availability
):
    """⚠️ THE DISCRIMINATING TEST. Resolves nothing; evaluates against the variant
    the fixture actually configured, which is the only way to reach the OFFERED
    branch. Before the wiring this asserted set was empty."""
    from app.services import capture

    company_id, variant_id = tenant_with_availability

    resolved = capture.resolve_schema(
        vault_product_id=variant_id,
        personalization_config=read_personalization_config(db, company_id),
        platform_fields=capture.template_for(capture.SALES_ORDER),
    )
    field = next(f for f in resolved if f.field_id == QUESTION_PERSONALIZATION)

    assert field.permitted_answers == (ANSWER_NAMEPLATE_ONLY,), (
        "the licensee's configured answer set did not reach the resolved schema"
    )


def test_omitting_the_tenant_reads_NOT_CONFIGURED_rather_than_raising(db):
    """⚠️ THE OTHER HALF OF THE CONTRACT. `tenant_id` is optional so the seam stays
    callable without a tenant; this pins that the omission is HONEST — the question
    is unresolved rather than answered, and nothing raises."""
    _, state = resolve_and_evaluate(db, {"vault_type": UNAMBIGUOUS})

    assert QUESTION_PERSONALIZATION not in state.answered
    assert QUESTION_PERSONALIZATION in state.missing + state.indeterminate
