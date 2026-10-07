"""Typed capture, slice 1 — the extractor and the party resolvers.

⚠️ WHOLE TYPED ORDERS THROUGH THE SEAM, BY RULING. Every test here feeds a sequence of
lines the way a director types them and then evaluates through `evaluate_typed`, which
resolves the vault and calls `capture.evaluate`. Asserting on the extractor alone would
be the assembled-pieces failure `test_vault_resolution_wiring.py` was written to close:
the pieces can each be right while the path is broken.

⚠️ THE PHRASINGS ARE JAMES'S, NOT INVENTED. "an oversized", "34 inch Continental",
"tent only", "device and grass", a named Legacy print, years-only dates, a cemetery name
shared by two towns, an equipment-only drop. Two of them currently fail to resolve and
that is asserted as a KNOWN GAP rather than skipped — see
`test_the_phrasings_the_extractor_cannot_place_yet`.

⚠️ NO MODEL IS CALLED. If one ever is, these tests get slow and start costing money,
which is itself the signal.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.services.capture.typed_extraction import EXTRACTOR, evaluate_typed
from app.services.party_resolver import (
    PartyDiscriminator,
    party_counts,
    resolve_cemetery,
    resolve_funeral_home,
)
from app.services.personalization.questions import QUESTION_PERSONALIZATION


def _refuse_a_non_local_database() -> None:
    """⚠️ FILE-SCOPED. One fixture INSERTs a second cemetery; §7 forbids pointing a
    local run at production. Host only — never the credential."""
    from urllib.parse import urlparse

    from app.config import settings

    host = (urlparse(settings.DATABASE_URL).hostname or "").lower()
    assert host in ("localhost", "127.0.0.1", "::1", ""), (
        f"this file writes; refusing to run against host {host!r}"
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


@pytest.fixture(scope="module")
def tenant(db) -> str:
    tid = db.execute(text("SELECT id FROM companies WHERE slug = 'testco'")).scalar()
    assert tid, "testco is not seeded — run scripts/seed_dev.sh"
    return tid


def _type(db, tenant_id: str, lines: list[str]) -> tuple[dict, list, list]:
    """Type a whole order, line by line, carrying the session forward."""
    answers: dict[str, object] = {}
    picks: list = []
    unrecognized: list[str] = []
    for line in lines:
        ex = EXTRACTOR.extract_line(db, tenant_id=tenant_id, line=line, answers=answers)
        answers.update(ex.values)
        picks.extend(ex.picks)
        unrecognized.extend(ex.unrecognized)
    return answers, picks, unrecognized


# ── controls first ──────────────────────────────────────────────────────

def test_the_instruments_see_something(db, tenant):
    """⚠️ EVERY ASSERTION BELOW IS ABOUT A RESOLVER FINDING A ROW. Over empty tables
    they would all report "no match", which is exactly what a correct miss looks
    like."""
    entities, cemeteries = party_counts(db, tenant)
    assert entities > 0, "no company_entities for testco — every party test is void"
    assert cemeteries > 0, "no cemeteries for testco — every cemetery test is void"


def test_nothing_here_calls_a_model(db, tenant, monkeypatch):
    """⚠️ THE RULING, ASSERTED. E1: no model call from the pane. This breaks the
    Intelligence entry point, so if the extractor ever reaches for it the test fails
    loudly rather than quietly costing $0.02 a line."""
    import app.services.intelligence.intelligence_service as isvc

    def _boom(*a, **k):
        raise AssertionError("the deterministic extractor called a model")

    monkeypatch.setattr(isvc, "execute", _boom)
    answers, _, _ = _type(db, tenant, [
        "start an order for Hopkins", "34 inch Continental", "tent only",
    ])
    assert answers["vault"]


# ── James's phrasings ───────────────────────────────────────────────────

def test_a_whole_typed_order_fills_the_capture(db, tenant):
    answers, picks, _ = _type(db, tenant, [
        "start an order for Hopkins",
        "decedent is John Smith",
        "1948 to 2026",
        "34 inch Continental",
        "nameplate only",
        "written out",
        "to Oakwood",
        "service at the church",
        "burial on March 3 2027",
        "service on March 2 2027",
        "service at 10am",
        "section C, lot 14, space 2",
        "tent only",
    ])
    resolution, state = evaluate_typed(db, tenant_id=tenant, answers=answers)

    assert resolution.variant_template_id, "the vault did not resolve"
    assert resolution.candidates[0].sku == "BV-CON34", resolution.candidates[0].sku
    assert answers["funeral_home"] == "Hopkins Funeral Home"
    assert answers["deceased_name"] == "John Smith"
    assert answers["cemetery"] == "Oakwood Cemetery"
    assert answers["cemetery_city"] == "Auburn"
    assert answers[QUESTION_PERSONALIZATION] == "nameplate_only"
    assert answers["cemetery_equipment"] == "Tent Only"
    assert answers["grave_location"] == "Section C, Lot 14, Space 2"
    assert not picks, [p.field_id for p in picks]
    assert QUESTION_PERSONALIZATION in state.answered


@pytest.mark.parametrize("line,field,expected", [
    ("34 inch Continental", "vault", 'Continental 34"'),
    ("tent only", "cemetery_equipment", "Tent Only"),
    ("device and grass", "cemetery_equipment", "Lowering Device & Grass"),
    ("lowering device only", "cemetery_equipment", "Lowering Device Only"),
    ("full setup", "cemetery_equipment", "Full Equipment"),
    ("print is Going Home", "legacy_print_name", "Going Home"),
    ("nameplate and emblem", QUESTION_PERSONALIZATION, "nameplate_and_cover_emblem"),
    ("custom artwork", "legacy_series", "custom"),
    ("years only", "nameplate_date_format", "years"),
    ("graveside", "service_location", "graveside"),
])
def test_each_phrasing_lands_on_its_field(db, tenant, line, field, expected):
    ex = EXTRACTOR.extract_line(db, tenant_id=tenant, line=line, answers={})
    assert ex.values.get(field) == expected, (
        f"{line!r} -> {dict(ex.values)}, picks={[p.field_id for p in ex.picks]}, "
        f"unrecognized={list(ex.unrecognized)}"
    )


def test_a_year_pair_sets_both_dates_and_does_NOT_set_the_format(db, tenant):
    """⚠️ THE FORMAT IS NOT INFERRED FROM THE SHORTHAND. A director typing "1948 to
    2026" has given two dates; whether the nameplate is lettered years-only is a
    separate instruction. Inferring it would read a production decision out of how
    someone typed."""
    ex = EXTRACTOR.extract_line(db, tenant_id=tenant, line="1948 to 2026", answers={})
    assert ex.values["date_of_birth"] == "1948"
    assert ex.values["date_of_death"] == "2026"
    assert "nameplate_date_format" not in ex.values


def test_an_equipment_only_drop_is_complete(db, tenant):
    """⚠️ THE R4 CASE, REACHED BY TYPING. The personalization question must be
    not-applicable on a lowering device, and the order must complete."""
    answers, _, _ = _type(db, tenant, [
        "order for Hopkins",
        "decedent is Mary Jones",
        "Lowering Device",
        "to Oakwood",
        "service at the church",
        "burial on March 3 2027",
        "service on March 2 2027",
        "service at 10am",
        "section A, lot 2",
    ])
    _, state = evaluate_typed(db, tenant_id=tenant, answers=answers)

    assert QUESTION_PERSONALIZATION in state.not_applicable
    assert QUESTION_PERSONALIZATION not in state.missing
    assert state.is_complete, f"missing={state.missing}"


# ── ambiguity asks, never picks ─────────────────────────────────────────

def test_an_ambiguous_vault_phrase_produces_a_pick_not_a_guess(db, tenant):
    ex = EXTRACTOR.extract_line(db, tenant_id=tenant, line="Bronze Triune", answers={})
    assert "vault" not in ex.values, "the extractor picked a vault"
    pick = next(p for p in ex.picks if p.field_id == "vault")
    assert len(pick.options) >= 2
    assert pick.discriminator == "form", pick.discriminator


def test_an_ambiguous_print_name_produces_a_pick(db, tenant):
    ex = EXTRACTOR.extract_line(db, tenant_id=tenant, line="print is Cross", answers={})
    assert "legacy_print_name" not in ex.values
    pick = next(p for p in ex.picks if p.field_id == "legacy_print_name")
    assert len(pick.options) == 3, [o[0] for o in pick.options]
    assert pick.discriminator == "finish"


# ── E3: the two-town cemetery ───────────────────────────────────────────

@pytest.fixture
def db_write():
    """A SEPARATE session for the tests that INSERT.

    ⚠️ ITS OWN SESSION, NOT THE MODULE'S. The first version used the module session and
    its insert hit a unique constraint; the aborted transaction then poisoned the
    session and NINE later tests failed with `PendingRollbackError` for a reason that
    had nothing to do with them. CLAUDE.md records this exact cascade from a 2026-10
    `SELECT DISTINCT` failure. A writing test gets its own connection.
    """
    _refuse_a_non_local_database()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def test_a_CEMETERY_name_cannot_repeat_within_a_tenant_so_that_collision_is_UNREACHABLE(
    db,
):
    """⚠️ E3's PREMISE DOES NOT HOLD FOR CEMETERIES, AND THE SCHEMA IS WHY.

    The ruling asked for "a cemetery name shared by two towns". `cemeteries` carries
    `uq_cemetery_company_name UNIQUE (company_id, name)` — measured from
    `pg_constraint` — so a tenant CANNOT have two cemeteries with the same name. I
    found this by trying to construct the fixture and getting a UniqueViolation.

    The city discriminator still earns its place, for a DIFFERENT and reachable case:
    the director names a town the one matching cemetery is not in, which is a conflict
    rather than a collision (see `test_a_town_no_candidate_is_in_is_a_CONFLICT...`).

    ⚠️ `company_entities` has NO such constraint, so the same-name collision IS
    reachable for funeral homes, and that is where it is tested.
    """
    rows = db.execute(text(
        "SELECT c.conname, pg_get_constraintdef(c.oid) FROM pg_constraint c "
        "JOIN pg_class t ON t.oid = c.conrelid "
        "WHERE t.relname = 'cemeteries' AND c.contype = 'u'"
    )).all()
    defs = {r[0]: r[1] for r in rows}
    assert any("company_id, name" in d for d in defs.values()), defs

    ce = db.execute(text(
        "SELECT count(*) FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid "
        "WHERE t.relname = 'company_entities' AND c.contype = 'u'"
    )).scalar()
    assert ce == 0, (
        "company_entities grew a unique constraint; the funeral-home collision test "
        "below is now unreachable too and this file needs rethinking"
    )


@pytest.fixture
def two_same_named_homes(db_write, tenant):
    """Two funeral homes with the SAME name in different towns, in a savepoint.

    ⚠️ CONSTRUCTED, AND REACHABLE ONLY BECAUSE `company_entities` HAS NO UNIQUE
    CONSTRAINT ON NAME. This is the collision E3 is about, relocated to the table that
    permits it.
    """
    from app.models.company_entity import CompanyEntity

    sp = db_write.begin_nested()
    name = f"Collision Funeral Home {uuid.uuid4().hex[:6]}"
    for city in ("Auburn", "Syracuse"):
        db_write.add(CompanyEntity(
            id=str(uuid.uuid4()), company_id=tenant, name=name, city=city,
        ))
    db_write.flush()
    try:
        yield name
    finally:
        sp.rollback()


def test_a_name_in_two_towns_asks_with_the_town_as_discriminator(
    db_write, tenant, two_same_named_homes
):
    r = resolve_funeral_home(db_write, tenant, two_same_named_homes)

    assert len(r.candidates) == 2, [c.label for c in r.candidates]
    assert r.party_id is None, "the resolver picked one of two towns"
    assert r.discriminators == (PartyDiscriminator.CITY,)
    # ⚠️ THE TOWN MUST BE IN THE LABEL. Two identical labels are not a choice.
    labels = {c.label for c in r.candidates}
    assert len(labels) == 2, labels
    assert any("Auburn" in lab for lab in labels), labels
    assert any("Syracuse" in lab for lab in labels), labels


def test_the_town_narrows_the_collision_to_one(db_write, tenant, two_same_named_homes):
    """⚠️ THE DISCRIMINATING HALF. Without it, a resolver that ALWAYS returned both
    would satisfy the test above."""
    r = resolve_funeral_home(db_write, tenant, two_same_named_homes, city_hint="Syracuse")

    assert r.party_id is not None, [c.label for c in r.candidates]
    assert r.candidates[0].city == "Syracuse"


def test_a_funeral_home_resolves_from_the_opening_line(db, tenant):
    r = resolve_funeral_home(db, tenant, "Hopkins")
    assert r.party_id is not None, [c.label for c in r.candidates]
    assert r.candidates[0].name == "Hopkins Funeral Home"


# ── never dropped ───────────────────────────────────────────────────────

def test_unplaced_text_comes_back_and_is_never_silently_dropped(db, tenant):
    ex = EXTRACTOR.extract_line(
        db, tenant_id=tenant, line="he wants the thing with the swirls", answers={}
    )
    assert ex.understood_nothing
    assert ex.unrecognized, "the line vanished"
    assert any("swirls" in u for u in ex.unrecognized), ex.unrecognized


def test_a_line_that_is_half_understood_reports_the_other_half(db, tenant):
    """⚠️ THE STRUCTURAL GUARANTEE, TESTED AT ITS EDGE. Span consumption means the
    unplaced half survives even when the placed half succeeds — which is the case a
    promise-based implementation gets wrong."""
    ex = EXTRACTOR.extract_line(
        db, tenant_id=tenant, line="tent only and something about swirls", answers={}
    )
    assert ex.values["cemetery_equipment"] == "Tent Only"
    assert any("swirls" in u for u in ex.unrecognized), ex.unrecognized


def test_the_phrasings_the_extractor_cannot_place_yet(db, tenant):
    """⚠️ KNOWN GAPS, ASSERTED RATHER THAN SKIPPED, so closing one is a visible edit.

    "an oversized" is a real thing James says and resolves to nothing: the catalog has
    `Large 34"`, `Large 36"`, `Large 40"` and no variant or alias containing
    "oversized". It is NOT coerced to a guess — it comes back unrecognized, which is
    the ruling.
    """
    ex = EXTRACTOR.extract_line(db, tenant_id=tenant, line="an oversized", answers={})

    assert "vault" not in ex.values, "'an oversized' was coerced to a vault"
    assert not ex.picks
    assert any("oversized" in u for u in ex.unrecognized), ex.unrecognized


def test_a_restatement_is_SURFACED_not_silently_ignored(db, tenant):
    """⚠️ THIS TEST FAILED FOR A BETTER REASON THAN I WROTE IT FOR.

    I wrote it expecting "tent only" after "full setup" to come back as unrecognized
    text. It came back as NOTHING — because leaving the span unclaimed let the VAULT
    resolver have it, and the catalog holds `Cemetery Tent - Single` and `- Double`, so
    a correction to the equipment surfaced as an ambiguous VAULT pick. Silently
    ignoring it was worse than overwriting: it asked a confusing question about a
    different field.

    The re-statement is now claimed and named, so the pane can say what is already
    answered. Changing an answer is a separate interaction and is not in this slice.
    """
    answers, picks, unrec = _type(db, tenant, ["full setup", "tent only"])

    assert answers["cemetery_equipment"] == "Full Equipment"
    assert not [p for p in picks if p.field_id == "vault"], (
        "a correction to the equipment was offered as a vault pick"
    )
    assert any("already" in u for u in unrec), unrec
    assert any("tent" in u.casefold() for u in unrec), unrec


# ── the two seams must not drift ────────────────────────────────────────

def test_evaluate_typed_and_the_call_seam_agree_on_a_shared_case(db, tenant):
    """⚠️ TWO SEAMS, ONE ENGINE. `evaluate_typed` exists because the call path's
    `resolve_and_evaluate` takes extraction-payload key names; both must produce the
    same CaptureState for the same facts, or the pane and the call overlay will
    disagree about the same order."""
    from app.services.call_extraction_service import resolve_and_evaluate

    _, typed = evaluate_typed(
        db, tenant_id=tenant,
        answers={"vault": "Bronze Triune Burial Vault", "deceased_name": "A B"},
    )
    _, called = resolve_and_evaluate(
        db, {"vault_type": "Bronze Triune Burial Vault", "deceased_name": "A B"},
        tenant_id=tenant,
    )

    assert set(typed.answered) == set(called.answered)
    assert set(typed.missing) == set(called.missing)
    assert set(typed.not_applicable) == set(called.not_applicable)
    assert set(typed.indeterminate) == set(called.indeterminate)
