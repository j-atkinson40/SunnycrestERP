"""No non-vault product can land in `vault`, by any phrasing, through any door.

James, 2026-11-02, after typing `" chairs"` on production and watching the VAULT row
fill with **"Graveside Chairs"**: *"The vault slot must accept only vault-form
products, on every path (typed, prefix, fuzzy, pills, model door). Find every candidate
source for vault and filter by form; same fix shape as the Vault Placer bug. Test: no
non-vault product can ever land in vault, by any phrasing."* And: *"A rule about what a
field accepts has to live in one place that every path goes through."*

### Why this file is a DOOR ENUMERATION and not a list of phrasings

⚠️ BECAUSE THE RULE WAS ALREADY RIGHT AND ALREADY RULED, AND IT REACHED ONE DOOR OUT OF
SIX. `vault_form.VAULT_FORMS` was added in October after a production probe offered
"Vault Placer" as a vault. That fix went into `pills.py` and nowhere else — measured
2026-11-02, `grep -rn VAULT_FORMS app/` returned the definition and a single call site.
The typed n-gram door, the typed prefix door, the ghost vocabulary and the answer-write
path all had no form filter at all. A test that enumerated PHRASINGS would have passed
the day the pills were fixed; what was needed was a test that notices a DOOR.

⚠️ SO TWO OF THE TESTS BELOW ARE STRUCTURAL AND THE REST ARE BEHAVIOURAL, and the
structural pair is the ratchet. `VAULT_FORMS` may be READ in exactly one module —
anywhere else, the question goes through `is_vault_form` and its three helpers — and no
module in the capture package may build a second form set out of literals. Either shape
fails here by name. That is the thing that was missing in October.

⚠️ AND A STRUCTURAL SCAN IS A CONSTRUCTED-NAME INSTRUMENT, DECLARED AS ONE. It reads
source text, so a door that reached the catalogue through a name this scan does not know
would be invisible to it. The behavioural tests are the other half: they drive each door
with real phrases and real data, so a door that bypasses the predicate fails even if the
scan cannot see it. Neither half is sufficient; both are cheap.
"""

from __future__ import annotations

import ast
import os
import pathlib
import uuid
from urllib.parse import urlparse

import pytest

from app.database import SessionLocal
from app.services.capture import session_service
from app.services.capture.vault_form import (
    FORM_EQUIPMENT,
    FORM_URN,
    VAULT_FORMS,
    FormResolver,
    admits_name,
    is_vault_form,
    vault_resolution,
)
from app.services.capture.typed_extraction import extract_text
from app.services.product_name_resolver import build_index

APP = pathlib.Path(__file__).resolve().parent.parent / "app"


def _local_only() -> None:
    host = (urlparse(os.environ.get("DATABASE_URL", "")).hostname or "").lower()
    assert host in ("localhost", "127.0.0.1", "::1", ""), host


@pytest.fixture(scope="module")
def db():
    _local_only()
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture(scope="module")
def tenant(db):
    from sqlalchemy import text

    tid = db.execute(
        text("SELECT id FROM companies WHERE slug = 'testco'")
    ).scalar()
    if not tid:
        pytest.skip("no testco tenant")
    return tid


# ── the premise: the catalogue really does hold non-vaults ───────────────────

def test_the_catalogue_CONTAINS_non_vault_products(db):
    """⚠️ THE CONTROL, AND EVERY REFUSAL BELOW IS VACUOUS WITHOUT IT. If the platform
    catalogue held only vaults, "no non-vault can land in vault" would be true of a
    world with no non-vaults in it — which is exactly how an empty-table test passes
    while the defect is live."""
    from sqlalchemy import text

    forms = {
        r[0]
        for r in db.execute(
            text(
                "SELECT DISTINCT t.form FROM product_variant_templates v "
                "JOIN product_templates t ON t.id = v.product_template_id"
            )
        )
    }
    assert FORM_EQUIPMENT in forms, sorted(forms)
    assert FORM_URN in forms, sorted(forms)
    assert not is_vault_form(FORM_EQUIPMENT)
    assert not is_vault_form(FORM_URN)


def test_grave_liners_and_infant_vaults_STAY_IN(db):
    """⚠️ THE OVER-CORRECTION THIS GUARDS AGAINST, AND IT NEARLY HAPPENED. A first
    measurement of the blast radius tested `form in ("burial_vault", "urn_vault")` and
    reported 22 bad names where the answer is 15 — because it counted the four
    Graveliners and three infant vaults as defects. `VAULT_FORMS` includes both by
    ruling: *"a Graveliner is the answer to 'which vault' even though it is not called
    one, which is exactly why this is a form set rather than a name test."* Had the fix
    been written from that number, seven real products would have become untypeable."""
    assert is_vault_form("grave_liner")
    assert is_vault_form("infant")
    idx = build_index(db)
    assert vault_resolution(idx, 'graveliner 34"').candidates, "a grave liner was refused"
    assert vault_resolution(idx, 'loved & cherished 19"').candidates, "an infant vault was refused"


# ── the structural ratchet: ONE expression of the rule ──────────────────────

def test_VAULT_FORMS_IS_READ_IN_EXACTLY_ONE_PLACE(db):
    """⚠️ THE RATCHET, AND IT IS THE TEST OCTOBER DID NOT HAVE. `VAULT_FORMS` may be
    read only by `is_vault_form`; every door goes through that predicate or through one
    of the three helpers beside it. A door that reaches for the set itself — the shape
    `pills.py` had, and the shape that left five doors unprotected — fails here.

    ⚠️ IT SCANS FOR THE NAME, so it cannot see a door that re-derives the form set from
    the database or spells the forms as literals. That is what
    `test_every_door_refuses_a_non_vault` is for.
    """
    readers: list[str] = []
    for path in APP.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "VAULT_FORMS":
                readers.append(str(path.relative_to(APP)))
                break
            if isinstance(node, ast.Attribute) and node.attr == "VAULT_FORMS":
                readers.append(str(path.relative_to(APP)))
                break
    assert sorted(set(readers)) == ["services/capture/vault_form.py"], (
        "VAULT_FORMS is read outside the module that owns the rule — put the question "
        "through `is_vault_form`/`admits_name`/`admits_term` instead: "
        + repr(sorted(set(readers)))
    )


def test_NO_SECOND_FORM_SET_EXISTS_IN_THE_CAPTURE_PACKAGE(db):
    """⚠️ THE OTHER HALF OF THE RATCHET: a door could filter correctly with its own
    hand-written tuple and this suite would be green while the rule had two bodies —
    which is how `CHAIRS_INCLUDED` came to disagree with the product rows, and how two
    `title_case_name`s came to disagree on "MCLEOD". A capture module that names three
    or more of the vault forms as literals is building a second form set.

    ⚠️ SCOPED TO `services/capture`, AND THE FIRST VERSION WAS SCOPED TO ALL OF `app`
    AND REPORTED THREE FALSE POSITIVES. Read, each one: `models/product_template.py`
    declares the COLUMN's vocabulary; `product_name_resolver.named_form` maps typed
    PHRASE SUFFIXES (" burial vault", " grave liner") to forms; and
    `price_list_analysis_service` maps forms to PRICE-LIST CATEGORY names. None is an
    acceptance check and none sits on a vault door.

    ⚠️ THE PRICE-LIST ONE IS THE INTERESTING NEAR-MISS AND IT IS LEFT ALONE
    DELIBERATELY. Its dict keys are exactly `VAULT_FORMS` — the same four-member
    membership written a second time — so it looks like the drift this test hunts. It
    is not: its question is "what does the price list call this category", and deriving
    it from the vault-acceptance set would make a change to what the VAULT FIELD accepts
    silently rename a price-list heading. Two identical sets with two different reasons
    are allowed to coincide; what is not allowed is two answers to ONE question.
    """
    offenders: dict[str, int] = {}
    for path in (APP / "services" / "capture").rglob("*.py"):
        if path.name == "vault_form.py":
            continue
        src = path.read_text(encoding="utf-8")
        hits = sum(1 for f in VAULT_FORMS if f'"{f}"' in src or f"'{f}'" in src)
        if hits >= 3:
            offenders[str(path.relative_to(APP))] = hits
    assert offenders == {}, (
        "these capture modules name most of the vault forms themselves, which is a "
        f"second form set: {offenders}"
    )


# ── the behavioural door matrix ─────────────────────────────────────────────

#: ⚠️ NAMED, WITH THE FORM EACH ONE REALLY HAS, so a failure says which product and
#: which form got through rather than "a string was wrong".
NON_VAULTS: tuple[tuple[str, str], ...] = (
    ("chairs", FORM_EQUIPMENT),
    ("graveside chairs", FORM_EQUIPMENT),
    ("lowering device", FORM_EQUIPMENT),
    ("grass mats", FORM_EQUIPMENT),
    ("cremation table", FORM_EQUIPMENT),
    ("cemetery tent", FORM_EQUIPMENT),
    ("arlington", FORM_URN),
    ("moon stone", FORM_URN),
    ("pebble dust", FORM_URN),
)


def test_the_candidate_source_refuses_every_one(db):
    """Door 1 and door 2 — both typed paths resolve through `vault_resolution`."""
    idx = build_index(db)
    got = {
        phrase: [(c.display_name, c.form) for c in vault_resolution(idx, phrase).candidates]
        for phrase, _form in NON_VAULTS
    }
    assert all(not v for v in got.values()), {k: v for k, v in got.items() if v}


def test_the_candidate_source_STILL_RESOLVES_REAL_VAULTS(db):
    """⚠️ THE POSITIVE CONTROL ON THE FILTER, AND IT IS WHAT STOPS "refuse everything"
    PASSING THE TEST ABOVE. A `vault_resolution` that returned no candidates ever would
    satisfy every refusal in this file."""
    idx = build_index(db)
    for phrase in ('monticello', 'continental 34', 'graveliner 34"',
                   'salute burial vault', 'universal urn vault'):
        assert vault_resolution(idx, phrase).candidates, phrase


def test_every_door_refuses_a_non_vault(db, tenant):
    """⚠️ THE DOORS, ENUMERATED, AND THE ENUMERATION IS THE POINT OF THE FILE. Each
    entry drives one real entry point with one real phrase and asserts that nothing
    non-vault reaches the `vault` field. A new door added without the check fails only
    if it is listed here — so the structural tests above exist to notice the listing
    going stale, and this comment is the instruction: a new way to set `vault` gets a
    row here in the same commit."""
    forms = FormResolver(db, tenant)
    idx = build_index(db)

    for phrase, form in NON_VAULTS:
        # door: the name-only helper (pills' catalogue fallback, the answer write)
        assert not admits_name(forms, phrase), (phrase, form)
        # door: the typed candidate source (n-gram scan and prefix pass)
        assert not vault_resolution(idx, phrase).candidates, (phrase, form)
        # door: whole-text extraction, which is the path James actually typed
        ex = extract_text(db, tenant_id=tenant, text=f"order for johnson {phrase}")
        assert ex.values.get("vault") is None, (phrase, dict(ex.values))
        # ⚠️ AND NO PICK EITHER. A pick is an OFFER of candidates — asking "which of
        # these non-vaults did you mean?" is the same defect wearing a question.
        assert [p.field_id for p in ex.picks if p.field_id == "vault"] == [], (
            phrase, [(p.field_id, p.options) for p in ex.picks]
        )


def test_the_PILL_LIST_offers_only_vaults(db, tenant):
    """Door: the ⌥4 "Which vault?" pills — the one door that was already correct, kept
    under test so re-pointing it at `admits_name` did not change it.

    ⚠️ THE CATALOGUE FALLBACK IS THE PART THAT MATTERS and it only runs when the
    tenant's ORDER HISTORY does not already supply enough pills, which is why the
    assertion is over whatever comes back rather than over a fixed list. On a tenant
    with a rich history this test passes without exercising the fallback at all — so
    the behavioural cover for it is `test_every_door_refuses_a_non_vault`'s
    `admits_name` leg, which is the predicate the fallback calls."""
    from datetime import date

    from app.services.capture.pills import pills_for
    from app.services.capture.schema import resolve_schema
    from app.services.capture import template_for, SALES_ORDER

    resolved = resolve_schema(
        vault_product_id=None, personalization_config=None,
        platform_fields=template_for(SALES_ORDER), answers={},
    )
    forms = FormResolver(db, tenant)
    offered = [
        p.value
        for p in pills_for(
            db, tenant_id=tenant, field_id="vault", values={},
            resolved_fields=resolved, today=date(2026, 11, 2),
        )
    ]
    bad = [n for n in offered if not admits_name(forms, n)]
    assert bad == [], bad


def test_the_GHOST_VOCABULARY_offers_no_non_vault_as_a_vault(db, tenant):
    """Door: the bar's completion list. ⚠️ KIND MATTERS AS MUCH AS FORM HERE. The
    vault row is filled from `prefix_resolve.KINDS_VAULT` — `vault`, `vault_alias`,
    `product` — so a term of any of those kinds is a vault candidate. Before 2026-11-02
    the platform's equipment and urn variants were emitted as kind `vault`, and every
    tenant product name as kind `product`, which is how "chairs" completed toward the
    price-list name `Extra Chairs (Over 8)`."""
    from app.services.capture.prefix_resolve import KINDS_VAULT
    from app.services.capture.vocabulary import build_vocabulary

    from app.services.product_name_resolver import resolve as raw_resolve

    terms = build_vocabulary(db, tenant)
    vaultish = [t for t in terms if t.kind in KINDS_VAULT]
    assert vaultish, "no vault-filling terms at all — this test is measuring nothing"

    # ⚠️ THE QUESTION IS ASKED THROUGH THE **RAW** RESOLVER, DELIBERATELY, AND THAT IS
    # WHAT MAKES THIS TEST ABLE TO FAIL. Asking `vault_resolution` would be circular —
    # it filters by form, so no term could ever reach a non-vault and the assertion
    # would be true of any vocabulary at all, including the one that shipped the bug.
    # The real question is whether a word the BAR OFFERS can reach a non-vault product,
    # and only the unfiltered resolver can answer it.
    #
    # ⚠️ IT ALSO COVERS THE ALIAS KIND, WHICH `form` CANNOT. A `vault_alias` term
    # carries no form — it is a nickname, and `Veteran` points at two variants — so a
    # form check would have had to skip aliases and the alias door would have stayed
    # open. Measured 2026-11-02: all 56 confirmed aliases point at vault forms, so this
    # passes today on data; `vocabulary.py` filters them by form as well so it stays
    # true by construction.
    bad = [
        (t.text, t.kind, sorted({c.form for c in raw_resolve(idx_for(db), t.text).candidates
                                 if not is_vault_form(c.form)}))
        for t in vaultish
    ]
    bad = [b for b in bad if b[2]]
    assert bad == [], bad


def idx_for(db):
    """⚠️ MEMOISED PER MODULE RUN. `build_index` is a full join over the variant
    catalogue and the alias table, and the test above asks it once per vocabulary
    term — a hundred-odd builds on a module-scoped session."""
    if not hasattr(idx_for, "_cached"):
        idx_for._cached = build_index(db)
    return idx_for._cached


def test_the_ANSWER_WRITE_refuses_a_non_vault(db, tenant):
    """Door: `session_service.answer` — a pill click or a pane action, which supplies a
    VALUE rather than choosing from candidates, so no candidate filter can reach it.

    ⚠️ THIS IS THE DURABLE ONE, WHICH IS WHY IT IS GUARDED SEPARATELY. `answer` writes
    `resolutions`, and resolutions survive whole-text re-extraction — so a non-vault
    written here would be the single hardest one to get rid of."""
    from sqlalchemy import text as sql

    uid = db.execute(
        sql("SELECT id FROM users WHERE company_id = :t LIMIT 1"), {"t": tenant}
    ).scalar()
    sp = db.begin_nested()
    try:
        row = session_service.start(db, company_id=tenant, user_id=uid)
        for name in ("Graveside Chairs", "Extra Chairs (Over 8)", "Vault Placer"):
            with pytest.raises(ValueError, match="not a vault"):
                session_service.answer(
                    db, row.id, company_id=tenant, user_id=uid,
                    field_id="vault", value=name,
                )
        # ⚠️ AND THE POSITIVE CONTROL IN THE SAME TEST, because a guard that refuses
        # everything also passes the three assertions above.
        session_service.answer(
            db, row.id, company_id=tenant, user_id=uid,
            field_id="vault", value="Monticello Burial Vault",
        )
        assert (db.get(type(row), row.id).resolutions or {}).get("vault") == (
            "Monticello Burial Vault"
        )
    finally:
        sp.rollback()


def test_the_PREFILL_WHITELIST_cannot_reach_the_vault(db):
    """Door: `POST /capture/sessions`'s `prefill`. It is whitelisted to one field
    today, and this pins that — so widening the whitelist to include `vault` is a
    visible edit here rather than a quiet new door with no form check."""
    from app.api.routes.capture import PREFILLABLE_FIELDS

    assert "vault" not in PREFILLABLE_FIELDS, sorted(PREFILLABLE_FIELDS)


def test_THE_MODEL_DOOR_IN_CAPTURE_WRITES_NO_FIELD_AT_ALL(db):
    """Door: the model door James names — and there IS one in capture, which my first
    version of this test asserted there was not.

    ⚠️ `rule_draft.py` CALLS A MODEL, AND THE CRUDE VERSION OF THIS TEST FOUND IT BY
    ACCIDENT. I wrote `assert no capture module mentions anthropic` and it failed. What
    `rule_draft` does is turn the director's own "why?" into one RULE SENTENCE for the
    reply line, which a person confirms or types over; its own docstring says "the model
    never writes to the rulebook". So the right question is not "is there a model" but
    "does a model write a capture FIELD", and the answer is no.

    ⚠️ THE ASSERTION IS THEREFORE ABOUT WRITES, NOT ABOUT IMPORTS. Any module in the
    capture package that reaches a model must not assign into `values` or `resolutions`
    — and if one ever does, it goes through `session_service.answer`'s acceptance check
    like every other write, which is the whole reason that check sits on the write
    rather than being repeated per door.
    """
    import re

    model_touchers = []
    for path in (APP / "services" / "capture").rglob("*.py"):
        src = path.read_text(encoding="utf-8")
        if re.search(r"ANTHROPIC|anthropic|ai_service", src):
            model_touchers.append((str(path.relative_to(APP)), src))

    # ⚠️ THE CONTROL: if nothing matched, the assertion below would be vacuous — and
    # that is precisely the state this test wrongly assumed on its first run.
    assert [n for n, _ in model_touchers] == ["services/capture/rule_draft.py"], (
        [n for n, _ in model_touchers]
    )
    for name, src in model_touchers:
        writes = re.findall(r"(?:values|resolutions)\s*\[", src)
        assert writes == [], (name, writes)
